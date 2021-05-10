"""Legacy minidb cache database.

Code is loaded only:

* when reading databases created in version < 3.2.0
* when running with the '--dababase-engine minidb' switch
* testing (to be deprecated)

Having it into a standalone module allows running the program without having the minidb package installed.
"""
from os import PathLike
from typing import Dict, Iterator, Optional, Union

from .storage import CacheStorage

try:
    import minidb
except ImportError:
    class minidb:
        class Model:
            pass


class CacheMiniDBStorage(CacheStorage):

    class CacheEntry(minidb.Model):
        guid = str
        timestamp = int
        data = str
        tries = int
        etag = str

    def __init__(self, filename: Union[str, bytes, PathLike]) -> None:
        super().__init__(filename)

        if isinstance(minidb, type):
            raise ImportError("Python package 'minidb' is missing")

        self.filename.parent.mkdir(parents=True, exist_ok=True)

        self.db = minidb.Store(str(self.filename), debug=True)
        self.db.register(self.CacheEntry)

    def close(self) -> None:
        self.db.close()
        self.db = None

    def get_guids(self) -> Iterator[str]:
        return (guid for guid, in self.CacheEntry.query(self.db, minidb.Function('distinct', self.CacheEntry.c.guid)))

    def load(self, guid: str) -> (Optional[str], Optional[float], int, Optional[str]):
        for data, timestamp, tries, etag in self.CacheEntry.query(
                self.db,
                self.CacheEntry.c.data // self.CacheEntry.c.timestamp // self.CacheEntry.c.tries
                // self.CacheEntry.c.etag,
                order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
                where=self.CacheEntry.c.guid == guid, limit=1):
            return data, timestamp, tries, etag

        return None, None, 0, None

    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        history = {}
        if count is not None and count < 1:
            return history
        for data, timestamp in self.CacheEntry.query(
                self.db, self.CacheEntry.c.data // self.CacheEntry.c.timestamp,
                order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
                where=(self.CacheEntry.c.guid == guid)
                & ((self.CacheEntry.c.tries == 0) | (self.CacheEntry.c.tries is None))):
            if data not in history:
                history[data] = timestamp
                if count is not None and len(history) >= count:
                    break
        return history

    def save(self, guid: str, data: str, timestamp: float, tries: int, etag: Optional[str] = None,
             temporary: Optional[str] = None) -> None:
        self.db.save(self.CacheEntry(guid=guid, timestamp=timestamp, data=data, tries=tries, etag=etag))
        self.db.commit()

    def delete(self, guid: str) -> None:
        self.CacheEntry.delete_where(self.db, self.CacheEntry.c.guid == guid)
        self.db.commit()

    def delete_latest(self, guid: str) -> None:
        raise NotImplementedError("Deleting of latest snapshot no supported by 'minidb' database engine")

    def clean(self, guid: str):
        keep_id = next((self.CacheEntry.query(self.db, self.CacheEntry.c.id, where=self.CacheEntry.c.guid == guid,
                                              order_by=self.CacheEntry.c.timestamp.desc, limit=1)), (None,))[0]

        if keep_id is not None:
            result = self.CacheEntry.delete_where(self.db,
                                                  (self.CacheEntry.c.guid == guid) & (self.CacheEntry.c.id != keep_id))
            self.db.commit()
            return result

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("Rolling back of legacy 'minidb' databases is not supported")
