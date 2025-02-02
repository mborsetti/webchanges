"""Legacy minidb cache database.

Code is loaded only:

* when reading databases created in version < 3.2.0 or in urlwatch;
* when running with the '--database-engine minidb' switch;
* testing migration of legacy database.

Having it into a standalone module allows running the program without requiring minidb package to be installed.
"""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

from pathlib import Path
from typing import Any

from webchanges.handler import Snapshot
from webchanges.storage import SsdbStorage

try:
    import minidb
except ImportError as e:  # pragma: no cover

    class minidb:  # type: ignore[no-redef]
        class Model:
            pass

    minidb_error = str(e)


class SsdbMiniDBStorage(SsdbStorage):
    class CacheEntry(minidb.Model):
        guid = str
        timestamp = int
        data = str
        tries = int
        etag = str

    def __init__(self, filename: str | Path) -> None:
        super().__init__(filename)

        if isinstance(minidb, type):
            raise ImportError(f"Python package 'minidb' cannot be imported.\n{minidb_error}")

        self.filename.parent.mkdir(parents=True, exist_ok=True)

        self.db = minidb.Store(str(self.filename), debug=True)
        self.db.register(self.CacheEntry)

    def close(self) -> None:
        self.db.close()
        self.db = None

    def get_guids(self) -> list[str]:
        return [guid for guid, in self.CacheEntry.query(self.db, minidb.Function('distinct', self.CacheEntry.c.guid))]

    def load(self, guid: str) -> Snapshot:
        for data, timestamp, tries, etag in self.CacheEntry.query(
            self.db,
            self.CacheEntry.c.data // self.CacheEntry.c.timestamp // self.CacheEntry.c.tries // self.CacheEntry.c.etag,
            order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
            where=self.CacheEntry.c.guid == guid,
            limit=1,
        ):
            return Snapshot(data, timestamp, tries, etag, '', {})

        return Snapshot('', 0, 0, '', '', {})

    def get_history_data(self, guid: str, count: int | None = None) -> dict[str | bytes, float]:
        history: dict[str | bytes, float] = {}
        if count is not None and count < 1:
            return history
        for data, timestamp in self.CacheEntry.query(
            self.db,
            self.CacheEntry.c.data // self.CacheEntry.c.timestamp,
            order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
            where=(self.CacheEntry.c.guid == guid)
            & ((self.CacheEntry.c.tries == 0) | (self.CacheEntry.c.tries is None)),
        ):
            if data not in history:
                history[data] = timestamp
                if count is not None and len(history) >= count:
                    break
        return history

    def get_history_snapshots(self, guid: str, count: int | None = None) -> list[Snapshot]:
        if count is not None and count < 1:
            return []
        history: list[Snapshot] = []
        for data, timestamp in self.CacheEntry.query(
            self.db,
            self.CacheEntry.c.data // self.CacheEntry.c.timestamp,
            order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
            where=(self.CacheEntry.c.guid == guid)
            & ((self.CacheEntry.c.tries == 0) | (self.CacheEntry.c.tries is None)),
        ):
            history.append(Snapshot(data, timestamp, 0, '', '', {}))
            if count is not None and len(history) >= count:
                break
        return history

    def save(self, *args: Any, guid: str, snapshot: Snapshot, **kwargs: Any) -> None:
        self.db.save(
            self.CacheEntry(
                guid=guid,
                timestamp=snapshot.timestamp,
                data=snapshot.data,
                tries=snapshot.tries,
                etag=snapshot.etag,
            )
        )
        self.db.commit()

    def delete(self, guid: str) -> None:
        self.CacheEntry.delete_where(self.db, self.CacheEntry.c.guid == guid)
        self.db.commit()

    def delete_latest(self, guid: str, delete_entries: int = 1, **kwargs: Any) -> int:
        raise NotImplementedError("Deleting of latest snapshot not supported by 'minidb' database engine")

    def delete_all(self) -> int:
        raise NotImplementedError("Deleting of all data not supported by 'minidb' database engine")

    def clean(self, guid: str, retain_limit: int = 1) -> int:
        retain_limit = max(1, retain_limit)
        keep_ids = [
            row[0]
            for row in self.CacheEntry.query(
                self.db,
                self.CacheEntry.c.id,
                where=self.CacheEntry.c.guid == guid,
                order_by=self.CacheEntry.c.timestamp.desc,
                limit=retain_limit,
            )
        ]
        # If nothing's returned from the query, the given guid is not in the db
        # and no action is needed.
        if keep_ids:
            where_clause = self.CacheEntry.c.guid == guid
            for keep_id in keep_ids:
                where_clause = where_clause & (self.CacheEntry.c.id != keep_id)
            result: int = self.CacheEntry.delete_where(self.db, where_clause)
            self.db.commit()
            self.db.vacuum()
            return result

        return 0

    def move(self, guid: str, new_guid: str) -> int:
        total_moved = 0
        if guid != new_guid:
            # Note if there are existing records with 'new_guid', they will
            # not be overwritten and the job histories will be merged.
            for entry in self.CacheEntry.load(self.db, self.CacheEntry.c.guid == guid):
                entry.guid = new_guid
                entry.save()
                total_moved += 1
            self.db.commit()

        return total_moved

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("Rolling back of legacy 'minidb' databases is not supported")

    def flushdb(self) -> None:
        """Delete all entries of the database.  Use with care, there is no undo!"""
        for guid in self.get_guids():
            self.delete(guid)
