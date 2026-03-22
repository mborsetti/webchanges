"""Redis snapshot storage."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import msgpack

from webchanges.handler import Snapshot
from webchanges.storage._ssdb import SsdbStorage

try:
    import redis
except ImportError as e:  # pragma: no cover
    redis = str(e)  # ty:ignore[invalid-assignment]

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class SsdbRedisStorage(SsdbStorage):
    """Class for storing snapshots using redis."""

    def __init__(self, filename: str | Path) -> None:
        super().__init__(filename)

        if isinstance(redis, str):
            raise ImportError(f"Python package 'redis' cannot be imported.\n{redis}")

        self.db = redis.from_url(str(filename))
        logger.info(f'Using {self.filename} for database')

    @staticmethod
    def _make_key(guid: str) -> str:
        return 'guid:' + guid

    def close(self) -> None:
        self.db.connection_pool.disconnect()
        del self.db

    def get_guids(self) -> list[str]:
        return [guid[5:].decode() for guid in self.db.keys('guid:*')]

    def load(self, guid: str) -> Snapshot:
        key = self._make_key(guid)
        data = self.db.lindex(key, 0)

        if data:
            r = msgpack.unpackb(data)
            return Snapshot(
                r['data'], r['timestamp'], r['tries'], r['etag'], r.get('mime_type', ''), r.get('err_data', {})
            )

        return Snapshot('', 0, 0, '', '', {})

    def get_history_data(self, guid: str, count: int | None = None) -> dict[str | bytes, float]:
        if count is not None and count < 1:
            return {}

        history = {}
        key = self._make_key(guid)
        for i in range(self.db.llen(key)):
            r = self.db.lindex(key, i)
            c = msgpack.unpackb(r)
            if (c['tries'] == 0 or c['tries'] is None) and c['data'] not in history:
                history[c['data']] = c['timestamp']
                if count is not None and len(history) >= count:
                    break
        return history

    def get_history_snapshots(self, guid: str, count: int | None = None) -> list[Snapshot]:
        if count is not None and count < 1:
            return []

        history: list[Snapshot] = []
        key = self._make_key(guid)
        for i in range(self.db.llen(key)):
            r = self.db.lindex(key, i)
            c = msgpack.unpackb(r)
            if c['tries'] == 0 or c['tries'] is None:
                history.append(
                    Snapshot(
                        c['data'],
                        c['timestamp'],
                        c['tries'],
                        c['etag'],
                        c.get('mime_type', ''),
                        c.get('error_data', {}),
                    )
                )
                if count is not None and len(history) >= count:
                    break
        return history

    def save(self, *args: Any, guid: str, snapshot: Snapshot, **kwargs: Any) -> None:
        r = {
            'data': snapshot.data,
            'timestamp': snapshot.timestamp,
            'tries': snapshot.tries,
            'etag': snapshot.etag,
            'mime_type': snapshot.mime_type,
            'error_data': snapshot.error_data,
        }
        packed_data = msgpack.packb(r)
        if packed_data:
            self.db.lpush(self._make_key(guid), packed_data)

    def delete(self, guid: str) -> None:
        self.db.delete(self._make_key(guid))

    def delete_latest(self, guid: str, delete_entries: int = 1, **kwargs: Any) -> int:
        """For the given 'guid', delete the latest 'delete_entries' entry and keep all other (older) ones.

        :param guid: The guid.
        :param delete_entries: The number of most recent entries to delete (only 1 is supported by this Redis code).

        :returns: Number of records deleted.
        """
        if delete_entries != 1:
            raise NotImplementedError('Only deleting of the latest 1 entry is supported by this Redis code.')

        if self.db.lpop(self._make_key(guid)) is None:
            return 0

        return 1

    def delete_all(self) -> int:
        """Delete all entries; used for testing only.

        :returns: Number of records deleted.
        """
        raise NotImplementedError('This method is not implemented for Redis.')

    def clean(self, guid: str, keep_entries: int = 1) -> int:
        if keep_entries != 1:
            raise NotImplementedError('Only keeping latest 1 entry is supported.')

        key = self._make_key(guid)
        i = self.db.llen(key)
        if self.db.ltrim(key, 0, 0):
            return i - self.db.llen(key)

        return 0

    def move(self, guid: str, new_guid: str) -> int:
        if guid == new_guid:
            return 0
        key = self._make_key(guid)
        new_key = self._make_key(new_guid)
        # Note if a list with 'new_key' already exists, the data stored there
        # will be overwritten.
        self.db.rename(key, new_key)
        return self.db.llen(new_key)

    def rollback(self, timestamp: float) -> None:
        """Rolls back the database to timestamp.

        :raises: NotImplementedError: This function is not implemented for 'redis' database engine.
        """
        raise NotImplementedError("Rolling back the database is not supported by 'redis' database engine")

    def flushdb(self) -> None:
        """Delete all entries of the database.  Use with care, there is no undo!"""
        self.db.flushdb()
