"""Legacy minidb cache database

Code loaded only:
* when reading databases created in version < 3.2.0
* when running with the '--dababase-engine minidb' switch
* testing (to be deprecated)

Having it into a standalone module allows running the program without having the minidb package installed
"""

import os
from typing import Iterator, Optional

from .storage import CacheStorage

try:
    import minidb
except ImportError:
    minidb = None


class CacheMiniDBStorage(CacheStorage):

    class CacheEntry(minidb.Model):
        guid = str
        timestamp = int
        data = str
        tries = int
        etag = str

    def __init__(self, filename) -> None:
        super().__init__(filename)

        if minidb is None:
            raise ImportError("Python package 'minidb' is missing")

        dirname = os.path.dirname(filename)
        if dirname and not os.path.isdir(dirname):
            os.makedirs(dirname)

        self.db = minidb.Store(self.filename, debug=True)
        self.db.register(self.CacheEntry)

    def close(self) -> None:
        self.db.close()
        self.db = None

    def get_guids(self) -> Iterator[str]:
        return (guid for guid, in self.CacheEntry.query(self.db, minidb.Function('distinct', self.CacheEntry.c.guid)))

    def load(self, guid: str) -> (Optional[str], Optional[float], Optional[int], Optional[str]):
        for data, timestamp, tries, etag in self.CacheEntry.query(
                self.db,
                self.CacheEntry.c.data // self.CacheEntry.c.timestamp // self.CacheEntry.c.tries
                // self.CacheEntry.c.etag,
                order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
                where=self.CacheEntry.c.guid == guid, limit=1):
            return data, timestamp, tries, etag

        return None, None, 0, None

    def get_history_data(self, guid: str, count: int = 1):
        history = {}
        if count < 1:
            return history
        for data, timestamp in self.CacheEntry.query(
                self.db, self.CacheEntry.c.data // self.CacheEntry.c.timestamp,
                order_by=minidb.columns(self.CacheEntry.c.timestamp.desc, self.CacheEntry.c.tries.desc),
                where=(self.CacheEntry.c.guid == guid)
                & ((self.CacheEntry.c.tries == 0) | (self.CacheEntry.c.tries is None))):
            if data not in history:
                history[data] = timestamp
                if len(history) >= count:
                    break
        return history

    def save(self, guid: str, data: str, timestamp: float, tries: int, etag: Optional[str] = None) -> None:
        self.db.save(self.CacheEntry(guid=guid, timestamp=timestamp, data=data, tries=tries, etag=etag))
        self.db.commit()

    def delete(self, guid: str) -> None:
        self.CacheEntry.delete_where(self.db, self.CacheEntry.c.guid == guid)
        self.db.commit()

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
