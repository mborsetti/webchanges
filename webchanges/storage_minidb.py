"""Legacy minidb cache database.

Code is loaded only:

* when reading databases created in version < 3.2.0
* when running with the '--database-engine minidb' switch
* testing migration of legacy database

Having it into a standalone module allows running the program without requiring minidb package to be installed.
"""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .storage import CacheStorage, Snapshot

try:
    import minidb
except ImportError:

    class minidb:  # type: ignore[no-redef]
        class Model:
            pass


class CacheMiniDBStorage(CacheStorage):
    class CacheEntry(minidb.Model):
        guid = str
        timestamp = int
        data = str
        tries = int
        etag = str

    def __init__(self, filename: Union[str, Path]) -> None:
        super().__init__(filename)

        if isinstance(minidb, type):
            raise ImportError("Python package 'minidb' is missing")

        self.filename.parent.mkdir(parents=True, exist_ok=True)

        self.db = minidb.Store(str(self.filename), debug=True)
        self.db.register(self.CacheEntry)

    def close(self) -> None:
        self.db.close()
        self.db = None

    def get_guids(self) -> List[str]:
        return [guid for guid, in self.CacheEntry.query(self.db, minidb.Function('distinct', self.CacheEntry.c.guid))]

    def load(self, guid: str) -> Snapshot:
        for data, timestamp, tries, etag in self.CacheEntry.query(
            self.db,
            self.CacheEntry.c.data // self.CacheEntry.c.timestamp // self.CacheEntry.c.tries // self.CacheEntry.c.etag,
            order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
            where=self.CacheEntry.c.guid == guid,
            limit=1,
        ):
            return Snapshot(data, timestamp, tries, etag)

        return Snapshot('', 0, 0, '')

    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        history: Dict[str, float] = {}
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

    def get_rich_history_data(self, guid: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        history: List[Dict[str, Any]] = []
        if count is not None and count < 1:
            return history
        for data, timestamp in self.CacheEntry.query(
            self.db,
            self.CacheEntry.c.data // self.CacheEntry.c.timestamp,
            order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
            where=(self.CacheEntry.c.guid == guid)
            & ((self.CacheEntry.c.tries == 0) | (self.CacheEntry.c.tries is None)),
        ):
            history.append({'timestamp': timestamp, 'data': data})
            if count is not None and len(history) >= count:
                break
        return history

    def save(
        self,
        *args: Any,
        guid: str,
        data: str,
        timestamp: float,
        tries: int,
        etag: Optional[str],
        **kwargs: Any,
    ) -> None:
        self.db.save(self.CacheEntry(guid=guid, timestamp=timestamp, data=data, tries=tries, etag=etag))
        self.db.commit()

    def delete(self, guid: str) -> None:
        self.CacheEntry.delete_where(self.db, self.CacheEntry.c.guid == guid)
        self.db.commit()

    def delete_latest(self, guid: str, delete_entries: int = 1) -> int:
        raise NotImplementedError("Deleting of latest snapshot not supported by 'minidb' database engine")

    def clean(self, guid: str, keep_entries: int = 1) -> int:
        if keep_entries != 1:
            raise NotImplementedError("Only keeping latest 1 entry is supported by 'minidb' database engine")

        keep_id = next(
            (
                self.CacheEntry.query(
                    self.db,
                    self.CacheEntry.c.id,
                    where=self.CacheEntry.c.guid == guid,
                    order_by=self.CacheEntry.c.timestamp.desc,
                    limit=1,
                )
            ),
            (None,),
        )[0]

        if keep_id is not None:
            result: int = self.CacheEntry.delete_where(
                self.db, (self.CacheEntry.c.guid == guid) & (self.CacheEntry.c.id != keep_id)
            )
            self.db.commit()
            return result

        return 0

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("Rolling back of legacy 'minidb' databases is not supported")

    def flushdb(self) -> None:
        """Delete all entries of the database.  Use with care, there is no undo!"""
        for guid in self.get_guids():
            self.delete(guid)
