"""SsdbStorage abstract base and SsdbDirStorage (text-file backend)."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import os
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from webchanges.handler import ErrorData, Snapshot
from webchanges.storage._base import BaseFileStorage

logger = logging.getLogger(__name__)


class SsdbStorage(BaseFileStorage):
    """Base class for snapshots storage."""

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def get_guids(self) -> list[str]:
        pass

    @abstractmethod
    def load(self, guid: str) -> Snapshot:
        pass

    @abstractmethod
    def get_history_data(self, guid: str, count: int | None = None) -> dict[str | bytes, float]:
        pass

    @abstractmethod
    def get_history_snapshots(self, guid: str, count: int | None = None) -> list[Snapshot]:
        pass

    @abstractmethod
    def save(self, *args: Any, guid: str, snapshot: Snapshot, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def delete(self, guid: str) -> None:
        pass

    @abstractmethod
    def delete_latest(self, guid: str, delete_entries: int = 1, **kwargs: Any) -> int:
        """For the given 'guid', delete only the latest 'delete_entries' entries and keep all other (older) ones.

        :param guid: The guid.
        :param delete_entries: The number of most recent entries to delete.

        :returns: Number of records deleted.
        """

    @abstractmethod
    def delete_all(self) -> int:
        """Delete all entries; used for testing only.

        :returns: Number of records deleted.
        """

    @abstractmethod
    def clean(self, guid: str, keep_entries: int = 1) -> int:
        """Removes the entries for guid except the latest n keep_entries.

        :param guid: The guid.
        :param keep_entries: The number of most recent entries to keep.

        :returns: Number of records deleted.
        """

    @abstractmethod
    def move(self, guid: str, new_guid: str) -> int:
        """Replace uuid in records matching the 'guid' with the 'new_guid' value.

        If there are existing records with 'new_guid', they will not be overwritten and the job histories will be
        merged.

        :returns: Number of records searched for replacement.
        """

    @abstractmethod
    def rollback(self, timestamp: float) -> int | None:
        """Rolls back the database to timestamp.

        :param timestamp: The timestamp.

        :returns: Number of records deleted.
        :raises: NotImplementedError for those classes where this method is not implemented.
        """

    def backup(self) -> Iterator[tuple[str, str | bytes, float, int, str, str, ErrorData]]:
        """Return the most recent entry for each 'guid'.

        :returns: A generator of tuples, each consisting of (guid, data, timestamp, tries, etag, mime_type)
        """
        for guid in self.get_guids():
            data, timestamp, tries, etag, mime_type, error_data = self.load(guid)
            yield guid, data, timestamp, tries, etag, mime_type, error_data

    def restore(self, entries: Iterable[tuple[str, str | bytes, float, int, str, str, ErrorData]]) -> None:
        """Save multiple entries into the database.

        :param entries: An iterator of tuples WHERE each consists of (guid, data, timestamp, tries, etag, mime_type)
        """
        for guid, data, timestamp, tries, etag, mime_type, error_data in entries:
            new_snapshot = Snapshot(
                data=data, timestamp=timestamp, tries=tries, etag=etag, mime_type=mime_type, error_data=error_data
            )
            self.save(guid=guid, snapshot=new_snapshot, temporary=False)

    def gc(self, known_guids: Iterable[str], keep_entries: int = 1) -> None:
        """Garbage collect the database: delete all guids not included in known_guids and keep only last n snapshot for
        the others.

        :param known_guids: The guids to keep.
        :param keep_entries: Number of entries to keep after deletion for the guids to keep.
        """
        for guid in set(self.get_guids()) - set(known_guids):
            print(f'Deleting job {guid} (no longer being tracked).')
            self.delete(guid)
        self.clean_ssdb(known_guids, keep_entries)

    def clean_ssdb(self, known_guids: Iterable[str], keep_entries: int = 1) -> None:
        """Convenience function to clean the cache.

        If self.clean_all is present, runs clean_all(). Otherwise, runs clean() on all known_guids, one at a time.
        Prints the number of snapshots deleted.

        :param known_guids: An iterable of guids
        :param keep_entries: Number of entries to keep after deletion.
        """
        if hasattr(self, 'clean_all'):
            count = self.clean_all(keep_entries)  # ty:ignore[call-non-callable]
            if count:
                print(f'Deleted {count} old snapshots.')
        else:
            for guid in known_guids:
                count = self.clean(guid, keep_entries)
                if count:
                    print(f'Deleted {count} old snapshots of {guid}.')

    @abstractmethod
    def flushdb(self) -> None:
        """Delete all entries of the database.  Use with care, there is no undo!"""


class SsdbDirStorage(SsdbStorage):
    """Class for snapshots stored as individual textual files in a directory 'dirname'."""

    def __init__(self, dirname: str | Path) -> None:
        super().__init__(dirname)
        self.filename.mkdir(parents=True, exist_ok=True)  # using the attr filename because it is a Path (confusing!)
        logger.info(f'Using directory {self.filename} to store snapshot data as individual text files')

    def close(self) -> None:
        # Nothing to close
        return

    def _get_filename(self, guid: str) -> Path:
        return self.filename.joinpath(guid)  # filename is a dir (confusing!)

    def get_guids(self) -> list[str]:
        return [filename.name for filename in self.filename.iterdir()]

    def load(self, guid: str) -> Snapshot:
        filename = self._get_filename(guid)
        if not filename.is_file():
            return Snapshot('', 0, 0, '', '', {})

        try:
            data = filename.read_text()
        except UnicodeDecodeError:
            data = filename.read_text(errors='ignore')
            logger.warning(f'Found and ignored Unicode-related errors when retrieving saved snapshot {guid}')

        timestamp = filename.stat().st_mtime

        return Snapshot(data, timestamp, 0, '', '', {})

    def get_history_data(self, guid: str, count: int | None = None) -> dict[str | bytes, float]:
        if count is not None and count < 1:
            return {}
        snapshot = self.load(guid)
        return {snapshot.data: snapshot.timestamp} if snapshot.data and snapshot.timestamp else {}

    def get_history_snapshots(self, guid: str, count: int | None = None) -> list[Snapshot]:
        if count is not None and count < 1:
            return []
        snapshot = self.load(guid)
        return [snapshot] if snapshot.data and snapshot.timestamp else []

    def save(self, *args: Any, guid: str, snapshot: Snapshot, **kwargs: Any) -> None:
        # ETag and mime_type are ignored
        filename = self._get_filename(guid)
        with filename.open('w+') as fp:
            fp.write(str(snapshot.data))
        os.utime(filename, times=(datetime.now().timestamp(), snapshot.timestamp))  # noqa: DTZ005

    def delete(self, guid: str) -> None:
        filename = self._get_filename(guid)
        filename.unlink(missing_ok=True)

    def delete_latest(self, guid: str, delete_entries: int = 1, **kwargs: Any) -> int:
        """For the given 'guid', delete the latest entry and keep all other (older) ones.

        :param guid: The guid.
        :param delete_entries: The number of most recent entries to delete.

        :raises NotImplementedError: This function is not implemented for 'textfiles' databases.
        """
        raise NotImplementedError(
            "Deleting of latest snapshot not supported by 'textfiles' database engine since only one snapshot is "
            "saved. Delete all snapshots if that's what you are trying to do."
        )

    def delete_all(self) -> int:
        """Delete all entries; used for testing only.

        :raises NotImplementedError: This function is not implemented for 'textfiles' databases.
        """
        raise NotImplementedError(
            "Deleting of latest snapshot not supported by 'textfiles' database engine since only one snapshot is "
            "saved. Delete all snapshots if that's what you are trying to do."
        )

    def clean(self, guid: str, keep_entries: int = 1) -> int:
        if keep_entries != 1:
            raise NotImplementedError('Only keeping latest 1 entry is supported.')
        # We only store the latest version, no need to clean
        return 0

    def move(self, guid: str, new_guid: str) -> int:
        """Moves the data from guid to new_guid.

        :param guid: The guid.
        :param new_guid: The new guid.

        :returns: Number of records moved.
        """
        if guid == new_guid:
            return 0
        old_filepath = Path(self._get_filename(guid))
        new_filepath = Path(self._get_filename(new_guid))
        if old_filepath.exists():
            new_filepath.parent.mkdir(parents=True, exist_ok=True)
            old_filepath.rename(new_filepath)
        else:
            raise ValueError(f'Old snapshot file {old_filepath} does not exist')
        return 1

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("'textfiles' databases cannot be rolled back as new snapshots overwrite old ones")

    def flushdb(self) -> None:
        for file in self.filename.iterdir():
            if file.is_file():
                file.unlink()
