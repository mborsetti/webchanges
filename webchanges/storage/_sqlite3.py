"""SQLite3 snapshot storage."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import sqlite3
import sys
import threading
from typing import TYPE_CHECKING, Any

import msgpack

from webchanges import __project_name__
from webchanges.handler import Snapshot
from webchanges.storage._ssdb import SsdbStorage

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class SsdbSQLite3Storage(SsdbStorage):
    """Handles storage of the snapshot as a SQLite database in the 'filename' file using Python's built-in sqlite3
    module and the msgpack package.

    A temporary database is created by __init__ and will be written by the 'save()' function (unless temporary=False).
    This data will be written to the permanent one by the 'close()' function, which is called at the end of program
    execution.

    The database contains the 'webchanges' table with the following columns:

    * guid: unique hash of the "location", i.e. the URL/command; indexed
    * timestamp: the Unix timestamp of when then the snapshot was taken; indexed
    * msgpack_data: a msgpack blob containing 'data', 'tries', 'etag' and 'mime_type' in a dict of keys 'd', 't',
      'e' and 'm'
    """

    def __init__(self, filename: Path, max_snapshots: int = 4) -> None:
        """:param filename: The full filename of the database file
        :param max_snapshots: The maximum number of snapshots to retain in the database for each 'guid'
        """
        # Opens the database file and, if new, creates a table and index.

        self.max_snapshots = max_snapshots

        logger.debug(f'Run-time SQLite library: {sqlite3.sqlite_version}')
        super().__init__(filename)

        self.filename.parent.mkdir(parents=True, exist_ok=True)

        # https://stackoverflow.com/questions/26629080
        self.lock = threading.RLock()

        self.db = sqlite3.connect(filename, check_same_thread=False)
        logger.info(f'Using sqlite3 {sqlite3.sqlite_version} database at {filename}')
        self.cur = self.db.cursor()
        self.cur.execute('PRAGMA temp_store = MEMORY;')
        tables = self._execute("SELECT name FROM sqlite_master WHERE type='table';").fetchone()

        def _initialize_table() -> None:
            logger.debug('Initializing sqlite3 database')
            self._execute('CREATE TABLE webchanges (uuid TEXT, timestamp REAL, msgpack_data BLOB)')
            self._execute('CREATE INDEX idx_uuid_time ON webchanges(uuid, timestamp)')
            self.db.commit()

        if tables == ('CacheEntry',):
            logger.info("Found legacy 'minidb' database to convert")

            # Found a minidb legacy database; close it, rename it for migration and create new sqlite3 one
            import importlib.util

            if importlib.util.find_spec('minidb') is None:
                print('You have an old snapshot database format that needs to be converted to a current one.')
                print(
                    f"Please install the Python package 'minidb' for this one-time conversion and rerun "
                    f'{__project_name__}.'
                )
                print('Use e.g. `pip install -U minidb`.')
                print()
                print("After the conversion, you can uninstall 'minidb' with e.g. `pip uninstall minidb`.")
                sys.exit(1)

            print('Performing one-time conversion from old snapshot database format.')
            self.db.close()
            minidb_filename = filename.with_stem(filename.stem + '_minidb')
            self.filename.replace(minidb_filename)
            self.db = sqlite3.connect(filename, check_same_thread=False)
            self.cur = self.db.cursor()
            _initialize_table()
            # Migrate the minidb legacy database renamed above
            self.migrate_from_minidb(minidb_filename)
        elif tables != ('webchanges',):
            _initialize_table()

        # Create temporary database in memory for writing during execution (fault tolerance)
        logger.debug('Creating temp sqlite3 database file in memory')
        self.temp_lock = threading.RLock()
        self.temp_db = sqlite3.connect(':memory:', check_same_thread=False)
        self.temp_cur = self.temp_db.cursor()
        self._temp_execute('CREATE TABLE webchanges (uuid TEXT, timestamp REAL, msgpack_data BLOB)')
        self.temp_db.commit()

    def _execute(self, sql: str, args: tuple | None = None) -> sqlite3.Cursor:
        """Execute SQL command on main database"""
        if args is None:
            logger.debug(f"Executing (perm) '{sql}'")
            return self.cur.execute(sql)
        logger.debug(f"Executing (perm) '{sql}' with {args}")
        return self.cur.execute(sql, args)

    def _temp_execute(self, sql: str, args: tuple | None = None) -> sqlite3.Cursor:
        """Execute SQL command on temp database."""
        if args is None:
            logger.debug(f"Executing (temp) '{sql}'")
            return self.temp_cur.execute(sql)
        logger.debug(f"Executing (temp) '{sql}' with {args[:2]}...")
        return self.temp_cur.execute(sql, args)

    def _copy_temp_to_permanent(self, delete: bool = False) -> None:
        """Copy contents of temporary database to permanent one.

        :param delete: also delete contents of temporary cache (used for testing)
        """
        logger.debug('Saving new snapshots to permanent sqlite3 database')
        with self.temp_lock:
            with self.lock:
                for row in self._temp_execute('SELECT * FROM webchanges').fetchall():
                    self._execute('INSERT INTO webchanges VALUES (?, ?, ?)', row)
                self.db.commit()
            if delete:
                self._temp_execute('DELETE FROM webchanges')

    def close(self) -> None:
        """Writes the temporary database to the permanent one, purges old entries if required, and closes all database
        connections.
        """
        self._copy_temp_to_permanent()
        with self.temp_lock:
            self.temp_db.close()
            logger.debug('Cleaning up the permanent sqlite3 database and closing the connection')
        with self.lock:
            if self.max_snapshots:
                num_del = self.keep_latest(self.max_snapshots)
                logger.debug(
                    f'Keeping no more than {self.max_snapshots} snapshots per job: purged {num_del} older entries'
                )
            else:
                self.db.commit()
            self.db.close()
            logger.info(f'Closed main sqlite3 database file {self.filename}')
        del self.temp_cur
        del self.temp_db
        del self.temp_lock
        del self.cur
        del self.db
        del self.lock

    def get_guids(self) -> list[str]:
        """Lists the unique 'guid's contained in the database.

        :returns: A list of guids.
        """
        with self.lock:
            self.cur.row_factory = lambda cursor, row: row[0]
            guids = self._execute('SELECT DISTINCT uuid FROM webchanges').fetchall()
            self.cur.row_factory = None
        return guids

    def load(self, guid: str) -> Snapshot:
        """Return the most recent entry matching a 'guid'.

        :param guid: The guid.

        :returns: A tuple (data, timestamp, tries, etag)
            WHERE

            - data is the data;
            - timestamp is the timestamp;
            - tries is the number of tries;
            - etag is the ETag.
        """
        with self.lock:
            row = self._execute(
                'SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? ORDER BY timestamp DESC LIMIT 1',
                (guid,),
            ).fetchone()
        if row:
            msgpack_data, timestamp = row
            r = msgpack.unpackb(msgpack_data)
            return Snapshot(r['d'], timestamp, r['t'], r['e'], r.get('m', ''), r.get('err', {}))

        return Snapshot('', 0, 0, '', '', {})

    def get_history_data(self, guid: str, count: int | None = None) -> dict[str | bytes, float]:
        """Return max 'count' (None = all) records of data and timestamp of **successful** runs for a 'guid'.

        :param guid: The guid.
        :param count: The maximum number of entries to return; if None return all.

        :returns: A dict (key: value)
            WHERE

            - key is the snapshot data;
            - value is the most recent timestamp for such snapshot.
        """
        if count is not None and count < 1:
            return {}

        with self.lock:
            rows = self._execute(
                'SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? ORDER BY timestamp DESC', (guid,)
            ).fetchall()
        history = {}
        if rows:
            for msgpack_data, timestamp in rows:
                r = msgpack.unpackb(msgpack_data)
                if not r['t'] and r['d'] not in history:
                    history[r['d']] = timestamp
                    if count is not None and len(history) >= count:
                        break
        return history

    def get_history_snapshots(self, guid: str, count: int | None = None) -> list[Snapshot]:
        """Return max 'count' (None = all) entries of all data (including from error runs) saved for a 'guid'.

        :param guid: The guid.
        :param count: The maximum number of entries to return; if None return all.

        :returns: A list of Snapshot tuples (data, timestamp, tries, etag).
            WHERE the values are:

            - data: The data (str, could be empty);
            - timestamp: The timestamp (float);
            - tries: The number of tries (int);
            - etag: The ETag (str, could be empty).
        """
        if count is not None and count < 1:
            return []

        with self.lock:
            rows = self._execute(
                'SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? ORDER BY timestamp DESC', (guid,)
            ).fetchall()
        history: list[Snapshot] = []
        if rows:
            for msgpack_data, timestamp in rows:
                r = msgpack.unpackb(msgpack_data)
                history.append(Snapshot(r['d'], timestamp, r['t'], r['e'], r.get('m', ''), r.get('err', {})))
                if count is not None and len(history) >= count:
                    break
        return history

    def save(
        self,
        *args: Any,
        guid: str,
        snapshot: Snapshot,
        temporary: bool | None = True,
        **kwargs: Any,
    ) -> None:
        """Save the data from a job.

        By default, it is saved into the temporary database. Call close() to transfer the contents of the temporary
        database to the permanent one.

        Note: the logic is such that any attempts that end in an exception will have tries >= 1, and we replace the data
        with the one from the most recent successful attempt.

        :param guid: The guid.
        :param data: The data.
        :param timestamp: The timestamp.
        :param tries: The number of tries.
        :param etag: The ETag (could be empty string).
        :param temporary: If true, saved to temporary database (default).
        """
        c = {
            'd': snapshot.data,
            't': snapshot.tries,
            'e': snapshot.etag,
            'm': snapshot.mime_type,
            'err': snapshot.error_data,
        }
        msgpack_data = msgpack.packb(c)
        if temporary:
            with self.temp_lock:
                self._temp_execute('INSERT INTO webchanges VALUES (?, ?, ?)', (guid, snapshot.timestamp, msgpack_data))
                # we do not commit to temporary as it's being used as write-only (we commit at the end)
        else:
            with self.lock:
                self._execute('INSERT INTO webchanges VALUES (?, ?, ?)', (guid, snapshot.timestamp, msgpack_data))
                self.db.commit()

    def delete(self, guid: str) -> None:
        """Delete all entries matching a 'guid'.

        :param guid: The guid.
        """
        with self.lock:
            self._execute('DELETE FROM webchanges WHERE uuid = ?', (guid,))
            self.db.commit()

    def delete_latest(
        self,
        guid: str,
        delete_entries: int = 1,
        temporary: bool | None = False,
        **kwargs: Any,
    ) -> int:
        """For the given 'guid', delete the latest 'delete_entries' number of entries and keep all other (older) ones.

        :param guid: The guid.
        :param delete_entries: The number of most recent entries to delete.
        :param temporary: If False, deleted from permanent database (default).

        :returns: Number of records deleted.
        """
        if temporary:
            with self.temp_lock:
                self._temp_execute(
                    'DELETE FROM webchanges '
                    'WHERE ROWID IN ( '
                    '    SELECT ROWID FROM webchanges '
                    '    WHERE uuid = ? '
                    '    ORDER BY timestamp DESC '
                    '    LIMIT ? '
                    ')',
                    (guid, delete_entries),
                )
                num_del: int = self._execute('SELECT changes()').fetchone()[0]
        else:
            with self.lock:
                self._execute(
                    'DELETE FROM webchanges '
                    'WHERE ROWID IN ( '
                    '    SELECT ROWID FROM webchanges '
                    '    WHERE uuid = ? '
                    '    ORDER BY timestamp DESC '
                    '    LIMIT ? '
                    ')',
                    (guid, delete_entries),
                )
                num_del = self._execute('SELECT changes()').fetchone()[0]
                self.db.commit()
        return num_del

    def delete_all(self) -> int:
        """Delete all entries; used for testing only.

        :returns: Number of records deleted.
        """
        with self.lock:
            self._execute('DELETE FROM webchanges')
            self.db.commit()
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()

        return num_del

    def clean(self, guid: str, keep_entries: int = 1) -> int:
        """For the given 'guid', keep only the latest 'keep_entries' number of entries and delete all other (older)
        ones. To delete older entries from all guids, use clean_all() instead.

        :param guid: The guid.
        :param keep_entries: Number of entries to keep after deletion.

        :returns: Number of records deleted.
        """
        with self.lock:
            self._execute(
                'DELETE FROM webchanges '
                'WHERE ROWID IN ( '
                '    SELECT ROWID FROM webchanges '
                '    WHERE uuid = ? '
                '    ORDER BY timestamp DESC '
                '    LIMIT -1 '
                '    OFFSET ? '
                ') ',
                (guid, keep_entries),
            )
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
            self._execute('VACUUM')
        return num_del

    def move(self, guid: str, new_guid: str) -> int:
        """Replace uuid in records matching the 'guid' with the 'new_guid' value.

        If there are existing records with 'new_guid', they will not be overwritten and the job histories will be
        merged.

        :returns: Number of records searched for replacement.
        """
        total_searched = 0
        if guid != new_guid:
            with self.lock:
                self._execute(
                    'UPDATE webchanges SET uuid = REPLACE(uuid, ?, ?)',
                    (guid, new_guid),
                )
                total_searched = self._execute('SELECT changes()').fetchone()[0]
                self.db.commit()
                self._execute('VACUUM')

        return total_searched

    def clean_all(self, keep_entries: int = 1) -> int:
        """Delete all older entries for each 'guid' (keep only keep_entries).

        :returns: Number of records deleted.
        """
        with self.lock:
            if keep_entries == 1:
                self._execute(
                    'DELETE FROM webchanges '
                    'WHERE EXISTS ( '
                    '    SELECT 1 FROM webchanges '
                    '    w WHERE w.uuid = webchanges.uuid AND w.timestamp > webchanges.timestamp '
                    ')'
                )
            else:
                self._execute(
                    'DELETE FROM webchanges '
                    'WHERE ROWID IN ( '
                    '    WITH rank_added AS ('
                    '        SELECT '
                    '             ROWID,'
                    '             uuid,'
                    '             timestamp, '
                    '             ROW_NUMBER() OVER (PARTITION BY uuid ORDER BY timestamp DESC) AS rn'
                    '        FROM webchanges '
                    '    ) '
                    '    SELECT ROWID FROM rank_added '
                    '    WHERE rn > ?'
                    ')',
                    (keep_entries,),
                )
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
            self._execute('VACUUM')
        return num_del

    def keep_latest(self, keep_entries: int = 1) -> int:
        """Delete all older entries keeping only the 'keep_num' per guid.

        :param keep_entries: Number of entries to keep after deletion.

        :returns: Number of records deleted.
        """
        with self.lock:
            self._execute(
                'WITH '
                'cte AS ( SELECT uuid, timestamp, ROW_NUMBER() OVER ( PARTITION BY uuid '
                '                                                     ORDER BY timestamp DESC ) rn '
                '         FROM webchanges ) '
                'DELETE '
                'FROM webchanges '
                'WHERE EXISTS ( SELECT 1 '
                '               FROM cte '
                '               WHERE webchanges.uuid = cte.uuid '
                '                 AND webchanges.timestamp = cte.timestamp '
                '                 AND cte.rn > ? );',
                (keep_entries,),
            )
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def rollback(self, timestamp: float, count: bool = False) -> int:
        """Rollback database to the entries present at timestamp.

        :param timestamp: The timestamp.
        :param count: If set to true, only count the number that would be deleted without doing so.

        :returns: Number of records deleted (or to be deleted).
        """
        command = 'SELECT COUNT(*)' if count else 'DELETE'
        with self.lock:
            self._execute(
                f'{command} '  # noqa: S608 Possible SQL injection
                'FROM webchanges '
                'WHERE EXISTS ( '
                '     SELECT 1 '
                '     FROM webchanges AS w '
                '     WHERE w.uuid = webchanges.uuid '
                '     AND webchanges.timestamp > ? '
                '     AND w.timestamp > ? '
                ')',
                (timestamp, timestamp),
            )
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def migrate_from_minidb(self, minidb_filename: str | Path) -> None:
        """Migrate the data of a legacy minidb database to the current database.

        :param minidb_filename: The filename of the legacy minidb database.
        """
        print("Found 'minidb' database and upgrading it to the new engine (note: only the last snapshot is retained).")
        logger.info(
            "Found legacy 'minidb' database and converting it to 'sqlite3' and new schema. Package 'minidb' needs to be"
            ' installed for the conversion.'
        )

        from webchanges.storage._minidb import SsdbMiniDBStorage

        legacy_db = SsdbMiniDBStorage(minidb_filename)
        self.restore(legacy_db.backup())
        legacy_db.close()
        print(f'Database upgrade finished; the following backup file can be safely deleted: {minidb_filename}.\n')
        print("The 'minidb' package can be removed (unless used by another program): $ pip uninstall minidb.")
        print('-' * 80)

    def flushdb(self) -> None:
        """Delete all entries of the database.  Use with care, there is no undo!"""
        with self.lock:
            self._execute('DELETE FROM webchanges')
            self.db.commit()
