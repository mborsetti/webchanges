"""Handles all storage: job files, config files, hooks file, and cache database engines."""
import copy
import getpass
import logging
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
import threading
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Hashable, Iterable, Iterator, List, NamedTuple, Optional, TextIO, Tuple, Type, Union

import msgpack

try:
    import pwd
except ImportError:
    pwd = None

try:
    import redis
except ImportError:
    redis = None

import yaml

import webchanges as project

from .filters import FilterBase
from .jobs import JobBase, ShellJob, UrlJob
from .util import edit_file

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    'display': {  # select whether the report include the categories below
        'new': True,
        'error': True,
        'unchanged': False,
    },

    'report': {
        # text, html and markdown are three content types of reports
        'html': {
            'diff': 'unified',  # 'unified' or 'table'
        },

        'text': {
            'line_length': 75,
            'details': True,
            'footer': True,
            'minimal': False,
        },

        'markdown': {
            'details': True,
            'footer': True,
            'minimal': False,
        },

        # the keys below control where a report is displayed and/or sent

        'stdout': {  # the console / command line display
            'enabled': True,
            'color': True,
        },

        'browser': {  # the system's default browser
            'enabled': False,
            'title': f'[{project.__project_name__}] {{count}} changes: {{jobs}}',
        },

        'email': {  # email (except mailgun)
            'enabled': False,
            'html': True,
            'to': '',
            'from': '',
            'subject': f'[{project.__project_name__}] {{count}} changes: {{jobs}}',
            'method': 'smtp',  # either 'smtp' or 'sendmail'
            'smtp': {
                'host': 'localhost',
                'user': '',
                'port': 25,
                'starttls': True,
                'auth': True,
                'insecure_password': '',
            },
            'sendmail': {
                'path': 'sendmail',
            }
        },
        'pushover': {
            'enabled': False,
            'app': '',
            'device': None,
            'sound': 'spacealarm',
            'user': '',
            'priority': 'normal',
        },
        'pushbullet': {
            'enabled': False,
            'api_key': '',
        },
        'telegram': {
            'enabled': False,
            'bot_token': '',
            'chat_id': '',
        },
        'webhook': {
            'enabled': False,
            'webhook_url': '',
            'max_message_length': None,
        },
        'webhook_markdown': {
            'enabled': False,
            'webhook_url': '',
            'max_message_length': None,
        },
        'matrix': {
            'enabled': False,
            'homeserver': '',
            'access_token': '',
            'room_id': '',
        },
        'mailgun': {
            'enabled': False,
            'region': 'us',
            'api_key': '',
            'domain': '',
            'from_mail': '',
            'from_name': '',
            'to': '',
            'subject': f'[{project.__project_name__}] {{count}} changes: {{jobs}}',
        },
        'ifttt': {
            'enabled': False,
            'key': '',
            'event': '',
        },
        'xmpp': {
            'enabled': False,
            'sender': '',
            'recipient': '',
        },
        'prowl': {
            'enabled': False,
            'api_key': '',
            'priority': 0,
            'application': '',
            'subject': f'[{project.__project_name__}] {{count}} changes: {{jobs}}',
        },
    },

    'job_defaults': {  # default settings for jobs
        'all': {},
        'url': {},  # these are used for url jobs without use_browser
        'browser': {},  # these are used for url jobs with use_browser: true
        # TODO rename 'shell' to 'command' for clarity
        'shell': {},  # these are used for 'command' jobs
    }
}


def merge(source: dict, destination: dict) -> dict:
    # https://stackoverflow.com/a/20666342
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        else:
            destination[key] = value

    return destination


class BaseStorage(metaclass=ABCMeta):
    @abstractmethod
    def load(self, *args):
        ...

    @abstractmethod
    def save(self, *args):
        ...


class BaseFileStorage(BaseStorage, metaclass=ABCMeta):
    def __init__(self, filename: str) -> None:
        self.filename = filename


class BaseTextualFileStorage(BaseFileStorage, metaclass=ABCMeta):
    def __init__(self, filename: Optional[str]) -> None:
        super().__init__(filename)
        self.config = {}
        if not isinstance(self, JobsBaseFileStorage):
            self.load()

    @classmethod
    @abstractmethod
    def parse(cls, *args) -> Iterator:
        ...

    def edit(self, example_file: Optional[str] = None) -> int:
        fn_base, fn_ext = os.path.splitext(self.filename)
        file_edit = fn_base + '.edit' + fn_ext

        if os.path.exists(self.filename):
            shutil.copy(self.filename, file_edit)
        elif example_file is not None and os.path.exists(example_file):
            shutil.copy(example_file, file_edit)

        while True:
            try:
                edit_file(file_edit)
                # Check if we can still parse it
                if self.parse is not None:
                    self.parse(file_edit)
                break  # stop if no exception on parser
            except SystemExit:
                raise
            except Exception as e:
                print()
                print('Errors in file:')
                print('======')
                print(e)
                print('======')
                print('')
                print('The file', file_edit, 'was NOT updated.')
                user_input = input('Do you want to retry the same edit? (Y/n)')
                if not user_input or user_input.lower()[0] == 'y':
                    continue
                print('Your changes have been saved in', file_edit)
                return 1

        os.replace(file_edit, self.filename)
        print('Saving edit changes in', self.filename)

    @classmethod
    def write_default_config(cls, filename: str) -> None:
        config_storage = cls(None)
        config_storage.filename = filename
        config_storage.save()


class JobsBaseFileStorage(BaseTextualFileStorage, metaclass=ABCMeta):
    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self.filename = filename

    def shelljob_security_checks(self) -> List[str]:

        if os.name == 'nt':
            return []

        shelljob_errors = []
        current_uid = os.getuid()

        dirname = os.path.dirname(self.filename) or '.'
        dir_st = os.stat(dirname)
        if (dir_st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)) != 0:
            shelljob_errors.append(f'{dirname} is group/world-writable')
        if dir_st.st_uid != current_uid:
            shelljob_errors.append(f'{dirname} not owned by {getpass.getuser()}')

        file_st = os.stat(self.filename)
        if (file_st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)) != 0:
            shelljob_errors.append(f'{self.filename} is group/world-writable')
        if file_st.st_uid != current_uid:
            shelljob_errors.append(f'{self.filename} not owned by {getpass.getuser()}')

        return shelljob_errors

    def load_secure(self) -> Union[list, bool]:
        jobs = self.load()

        def is_shell_job(job: JobBase) -> bool:
            if isinstance(job, ShellJob):
                return True

            for filter_kind, subfilter in FilterBase.normalize_filter_list(job.filter):
                if filter_kind == 'shellpipe':
                    return True

                if job.diff_tool is not None:
                    return True

            return False

        # Security checks for shell jobs - only execute if the current UID
        # is the same as the file/directory owner and only owner can write
        shelljob_errors = self.shelljob_security_checks()
        if shelljob_errors and any(is_shell_job(job) for job in jobs):
            print(f"Removing 'command' job(s) because {' and '.join(shelljob_errors)} (see "
                  f'https://webchanges.readthedocs.io/en/stable/jobs.html#important-note-for-command-jobs)')
            jobs = [job for job in jobs if not is_shell_job(job)]

        return jobs


class BaseTxtFileStorage(BaseTextualFileStorage, metaclass=ABCMeta):
    @classmethod
    def parse(cls, *args) -> Iterator[Type[JobBase]]:
        filename = args[0]
        if filename is not None and os.path.exists(filename):
            with open(filename) as fp:
                for line in fp:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    if line.startswith('|'):
                        yield ShellJob(command=line[1:])
                    else:
                        args = line.split(None, 2)
                        if len(args) == 1:
                            yield UrlJob(url=args[0])
                        elif len(args) == 2:
                            yield UrlJob(url=args[0], post=args[1])
                        else:
                            raise ValueError(f'Unsupported line format: {line}')


class BaseYamlFileStorage(BaseTextualFileStorage, metaclass=ABCMeta):
    @classmethod
    def parse(cls, *args) -> Union[Dict[Hashable, Any], list, None]:
        filename = args[0]
        if filename is not None and os.path.exists(filename):
            with open(filename) as fp:
                return yaml.safe_load(fp)


class YamlConfigStorage(BaseYamlFileStorage):
    def load(self, *args) -> None:
        self.config = merge(self.parse(self.filename) or {}, copy.deepcopy(DEFAULT_CONFIG))

    def save(self, *args) -> None:
        with open(self.filename, 'w') as fp:
            yaml.safe_dump(self.config, fp, default_flow_style=False, sort_keys=False, allow_unicode=True)


class YamlJobsStorage(BaseYamlFileStorage, JobsBaseFileStorage):
    @classmethod
    def _parse(cls, fp: TextIO) -> List[JobBase]:
        jobs = []
        jobs_by_guid = defaultdict(list)
        for i, job_data in enumerate(yaml.safe_load_all(fp)):
            if job_data is not None:
                job_data['index_number'] = i + 1
                job = JobBase.unserialize(job_data)
                jobs.append(job)
                jobs_by_guid[job.get_guid()].append(job)

        conflicting_jobs = []
        for guid, guid_jobs in jobs_by_guid.items():
            if len(guid_jobs) != 1:
                conflicting_jobs.append(guid_jobs[0].get_location())

        if conflicting_jobs:
            raise ValueError('\n   '.join(['Each job must have a unique URL, append #1, #2, ... to make them unique:']
                                          + conflicting_jobs))

        return jobs

    @classmethod
    def parse(cls, *args) -> List[JobBase]:
        filename = args[0]
        if filename is not None and os.path.exists(filename):
            with open(filename) as fp:
                return cls._parse(fp)

    def load(self, *args) -> List[JobBase]:
        with open(self.filename) as fp:
            return self._parse(fp)

    def save(self, *args) -> None:
        jobs = args[0]
        print(f'Saving updated list to {self.filename}')

        with open(self.filename, 'w') as fp:
            yaml.safe_dump_all([job.serialize() for job in jobs], fp, default_flow_style=False, sort_keys=False,
                               allow_unicode=True)


class CacheStorage(BaseFileStorage, metaclass=ABCMeta):
    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def get_guids(self) -> List[str]:
        ...

    @abstractmethod
    def load(self, guid: str) -> (Optional[str], Optional[float], int, Optional[str]):
        ...

    @abstractmethod
    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        ...

    @abstractmethod
    def save(self, guid: str, data: str, timestamp: float, tries: int, etag: Optional[str], *args) -> None:
        ...

    @abstractmethod
    def delete(self, guid: str) -> None:
        ...

    @abstractmethod
    def clean(self, guid: str) -> Optional[int]:
        ...

    @abstractmethod
    def rollback(self, timestamp: float) -> Union[int, NotImplementedError]:
        ...

    def backup(self) -> Iterator[Tuple[str, str, float, int, str]]:
        """Return the most recent entry for each 'guid'.

        :returns: An generator of tuples, each consisting of (guid, data, timestamp, tries, etag)
        """
        for guid in self.get_guids():
            data, timestamp, tries, etag = self.load(guid)
            yield guid, data, timestamp, tries, etag

    def restore(self, entries: Iterator[Tuple[str, str, float, int, Optional[str]]]) -> None:
        """Save multiple entries into the database.

        :param entries: An iterator of tuples WHERE each consists of (guid, data, timestamp, tries, etag)
        """
        for guid, data, timestamp, tries, etag in entries:
            self.save(guid, data, timestamp, tries, etag, temporary=False)

    def gc(self, known_guids: Iterable[str]) -> None:
        """Garbage collect the database: delete all guids not included in known_guids and keep only last snapshot for
        the others.

        :param known_guids: The guids to keep
        """
        for guid in set(self.get_guids()) - set(known_guids):
            print(f'Deleting: {guid} (no longer being tracked)')
            self.delete(guid)
        self.clean_cache(known_guids)

    def clean_cache(self, known_guids: Iterable[str]) -> None:
        """Convenience function to clean the cache.

        If self.clean_all is present, runs clean_all(). Otherwise runs clean() on all known_guids, one at a time.
        Prints the number of snapshots deleted

        :param known_guids: An iterable of guids
        """
        if hasattr(self, 'clean_all'):
            count = self.clean_all()
            if count:
                print(f'Deleted {count} old snapshots')
        else:
            for guid in known_guids:
                count = self.clean(guid)
                if count > 0:
                    print(f'Deleted {count} old snapshots of {guid}')

    def rollback_cache(self, timestamp: float) -> None:
        """Calls rollback() and prints out the result.

        :param timestamp: The timestamp
        """

        count = self.rollback(timestamp)
        try:
            timestamp_date = datetime.fromtimestamp(timestamp).astimezone().isoformat()
        except OSError:
            timestamp_date = datetime.fromtimestamp(timestamp).isoformat()
        if count:
            print(f'Deleted {count} snapshots taken after {timestamp_date}')
        else:
            print(f'No snapshots taken after {timestamp_date} found to delete')


class CacheDirStorage(CacheStorage):
    """Stores the information in individual files in a directory 'filename'"""
    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        if not os.path.exists(filename):
            os.makedirs(filename)

    def close(self) -> None:
        """No need to close"""

    def _get_filename(self, guid: str) -> str:
        return os.path.join(self.filename, guid)

    def get_guids(self) -> List[str]:
        return os.listdir(self.filename)

    def load(self, guid: str) -> (Optional[str], Optional[float], int, Optional[str]):
        filename = self._get_filename(guid)
        if not os.path.exists(filename):
            return None, None, 0, None

        try:
            with open(filename) as fp:
                data = fp.read()
        except UnicodeDecodeError:
            with open(filename, 'rb') as fp:
                data = fp.read().decode(errors='ignore')

        timestamp = os.stat(filename)[stat.ST_MTIME]

        return data, timestamp, 0, None

    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        """We only store the latest version, no history data"""
        return {}

    def save(self, guid: str, data: str, timestamp: float, tries: int, etag: Optional[str], *args) -> None:
        # Timestamp is not saved as is read from the file's timestamp; ETag is ignored
        filename = self._get_filename(guid)
        with open(filename, 'w+') as fp:
            fp.write(data)

    def delete(self, guid: str) -> None:
        filename = self._get_filename(guid)
        if os.path.exists(filename):
            os.unlink(filename)

    def clean(self, guid: str) -> None:
        """We only store the latest version, no need to clean"""

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("'textfiles' databases cannot be rolled back as new snapshots overwrite old ones")


class Snapshot(NamedTuple):
    data: Optional[str]
    timestamp: Optional[float]
    tries: int
    etag: Optional[str]


class CacheSQLite3Storage(CacheStorage):
    """
    Handles storage of the snapshot as a SQLite database in the 'filename' file using Python's built-in sqlite3 module
    and the msgpack package.

    A temporary database is created by __init__ and will be written by the 'save()' function (unless temporaru=False).
    This data will be written to the permanent one bythe 'close()' function, which is called at the end of program
    execution.

    The database contains the 'webchanges' table with the following columns:

    * guid: unique hash of the "location", i.e. the URL/command; indexed
    * timestamp: the Unix timestamp of when then the snapshot was taken; indexed
    * msgpack_data: a msgpack blob containing 'data' 'tries' and 'etag' in a dict of keys 'd', 't' and 'e'
    """
    def __init__(self, filename: str, max_snapshots: int = 4) -> None:
        """
        :param filename: The full filename of the database file
        :param max_snapshots: The maximum number of snapshots to retain in the database for each 'guid'
        """
        # Opens the database file and, if new, creates a table and index.

        self.max_snapshots = max_snapshots

        logger.debug(f'sqlite3.version={sqlite3.version}, sqlite3.sqlite_version={sqlite3.sqlite_version}')
        logger.info(f'Opening permanent sqlite3 database file {filename}')
        super().__init__(filename)

        dirname = os.path.dirname(filename)
        if dirname and not os.path.isdir(dirname):
            os.makedirs(dirname)
        fn_base, fn_ext = os.path.splitext(filename)

        # https://stackoverflow.com/questions/26629080
        self.lock = threading.RLock()

        self.db = sqlite3.connect(filename, check_same_thread=False)
        self.cur = self.db.cursor()
        tables = self._execute("SELECT name FROM sqlite_master WHERE type='table';").fetchone()

        def _initialize_table(self) -> None:
            logger.debug('Initializing sqlite3 database')
            self._execute('CREATE TABLE webchanges (uuid TEXT, timestamp REAL, msgpack_data BLOB)')
            self._execute('CREATE INDEX idx_uuid_time ON webchanges(uuid, timestamp)')
            self.db.commit()

        if tables == ('CacheEntry',):
            logger.info("Found legacy 'minidb' database to convert")
            # found a minidb legacy database; close it, rename it for migration and create new sqlite3 one
            import importlib.util

            if importlib.util.find_spec('minidb') is None:
                raise ImportError(
                    "Python package 'minidb' is not installed; cannot upgrade the legacy 'minidb' database"
                )

            self.db.close()
            minidb_filename = f'{fn_base}_minidb{fn_ext}'
            os.replace(filename, minidb_filename)
            self.db = sqlite3.connect(filename, check_same_thread=False)
            self.cur = self.db.cursor()
            _initialize_table(self)
            # migrate the minidb legacy database renamed above
            self.migrate_from_minidb(minidb_filename)
        elif tables != ('webchanges',):
            _initialize_table(self)

        # create temporary file for writing (fault tolerant)
        self.temp_filename = tempfile.NamedTemporaryFile().name
        logger.debug(f'Creating temp sqlite3 database file {self.temp_filename}')
        self.temp_lock = threading.RLock()
        self.temp_db = sqlite3.connect(self.temp_filename, check_same_thread=False)
        self.temp_cur = self.temp_db.cursor()
        self._temp_execute('CREATE TABLE webchanges (uuid TEXT, timestamp REAL, msgpack_data BLOB)')
        self.temp_db.commit()

    def _execute(self, sql: str, args: Optional[tuple] = None) -> sqlite3.Cursor:
        """Execute SQL command on main database"""
        if args is None:
            logger.debug(f"Executing (perm) '{sql}'")
            return self.cur.execute(sql)
        else:
            logger.debug(f"Executing (perm) '{sql}' with {args}")
            return self.cur.execute(sql, args)

    def _temp_execute(self, sql: str, args: Optional[tuple] = None) -> sqlite3.Cursor:
        """Execute SQL command on temp database"""
        if args is None:
            logger.debug(f"Executing (temp) '{sql}'")
            return self.temp_cur.execute(sql)
        else:
            logger.debug(f"Executing (temp) '{sql}' with {args[:2]}...")
            return self.temp_cur.execute(sql, args)

    def close(self) -> None:
        """Writes the temporary database to the permanent one, purges old entries if required, and closes all database
        connections."""
        logger.debug('Saving new snapshots to permanent sqlite3 database')
        with self.temp_lock:
            self.temp_db.commit()
            self.temp_db.close()
        with self.lock:
            self._execute('ATTACH DATABASE ? AS temp_db', (self.temp_filename,))
            self._execute('INSERT INTO webchanges SELECT * FROM temp_db.webchanges')
            logger.debug(f'Wrote {self.cur.rowcount} new snapshots to permanent sqlite3 database')
            self.db.commit()
            self._execute('DETACH DATABASE temp_db')
            if os.path.exists(self.temp_filename):
                logger.debug(f'Deleting temp sqlite3 database file {self.temp_filename}')
                os.remove(self.temp_filename)
            logger.debug('Cleaning up the permanent sqlite3 database and closing the connection')
            if self.max_snapshots:
                num_del = self.keep_latest(self.max_snapshots)
                logger.debug(f'Keeping no more than {self.max_snapshots} snapshots per job: '
                             f'purged {num_del} older entries')
            else:
                self.db.commit()
            self._execute('VACUUM')
            self.db.close()
            logger.info(f'Closed main sqlite3 database file {self.filename}')
        del self.temp_cur
        del self.temp_db
        del self.temp_lock
        del self.cur
        del self.db
        del self.lock

    def get_guids(self) -> List[str]:
        """Lists the unique 'guid's contained in the database.

        :returns: A list of guids
        """
        with self.lock:
            self.cur.row_factory = lambda cursor, row: row[0]
            guids = self._execute('SELECT DISTINCT uuid FROM webchanges').fetchall()
            self.cur.row_factory = None
        return guids

    def load(self, guid: str) -> Snapshot:
        """Return the most recent entry matching a 'guid'.

        :param guid: The guid

        :returns: A tuple (data, timestamp, tries, etag)
            WHERE
            data is the data;
            timestamp is the timestamp;
            tries is the number of tries;
            etag is the ETag.
        """
        with self.lock:
            row = self._execute('SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? '
                                'ORDER BY timestamp DESC LIMIT 1', (guid,)).fetchone()
        if row:
            msgpack_data, timestamp = row
            r = msgpack.unpackb(msgpack_data)
            return Snapshot(r['d'], timestamp, r['t'], r['e'])

        return Snapshot(None, None, 0, None)

    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        """Return data and timestamp from the last 'count' (None = all) entries matching a 'guid'.

        :param guid: The guid
        :param count: The maximum number of entries to return; if None return all

        :returns: A dict (key: value)
            WHERE
            key is the data;
            value is the timestamp.
        """
        history = {}
        if isinstance(count, int) and count < 1:
            return history

        with self.lock:
            rows = self._execute('SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? '
                                 'ORDER BY timestamp DESC', (guid,)).fetchall()
        if rows:
            for msgpack_data, timestamp in rows:
                r = msgpack.unpackb(msgpack_data)
                if not r['t']:
                    if r['d'] not in history:
                        history[r['d']] = timestamp
                        if count is not None and len(history) >= count:
                            break
        return history

    def save(self, guid: str, data: str, timestamp: float, tries: int, etag: Optional[str],
             temporary: Optional[bool] = True) -> None:
        """Save the data from a job.

        By default it is saved into the temporary database.  Call close() to tranfer the contents of the temporary
        database to the permament one.

        :param guid: The guid
        :param data: The data
        :param timestamp: The timestamp
        :param tries: The number of tries
        :param etag: The ETag (could be None)
        :param temporary: If true, saved to temporary database (default)
        """
        c = {
            'd': data,
            't': tries,
            'e': etag,
        }
        msgpack_data = msgpack.packb(c)
        if temporary:
            with self.temp_lock:
                self._temp_execute('INSERT INTO webchanges VALUES (?, ?, ?)', (guid, timestamp, msgpack_data))
                # we do not commit to temporary as it's being used as write-only (we commit at the end)
        else:
            with self.lock:
                self._execute('INSERT INTO webchanges VALUES (?, ?, ?)', (guid, timestamp, msgpack_data))
                self.db.commit()

    def delete(self, guid: str) -> None:
        """Delete all entries matching a 'guid'.

        :param guid: The guid
        """
        with self.lock:
            self._execute('DELETE FROM webchanges WHERE uuid = ?', (guid,))
            self.db.commit()

    def clean(self, guid: str, keep_entries: int = 1) -> int:
        """For the given 'guid', keep only the latest 'keep_entries' number of entries and delete all other (older)
        ones. To older entries from all guids, use clean_all() instead.

        :param guid: The guid
        :param keep_entries: Number of entries to keep after deletion

        :returns: Number of records deleted
        """
        with self.lock:
            self._execute('DELETE FROM webchanges '
                          'WHERE ROWID IN ( '
                          '    SELECT ROWID FROM webchanges '
                          '    WHERE uuid = ? '
                          '    ORDER BY timestamp DESC '
                          '    LIMIT -1 OFFSET ? '
                          ')', (guid, keep_entries))
            num_del = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def clean_all(self) -> int:
        """Delete all older entries for each 'guid' (keep only last one).

        :returns: Number of records deleted
        """
        with self.lock:
            self._execute('DELETE FROM webchanges '
                          'WHERE EXISTS ( '
                          '    SELECT 1 FROM webchanges w '
                          '    WHERE w.uuid = webchanges.uuid AND w.timestamp > webchanges.timestamp '
                          ')')
            num_del = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def keep_latest(self, keep_entries: int = 1) -> int:
        """Delete all older entries keeping only the 'keep_num' per guid.
        Only works for Python => 3.7; does nothing otherwise.

        :param keep_entries: Number of entries to keep after deletion

        :returns: Number of records deleted
        """
        if sys.version_info < (3, 7):
            self.db.commit()
            return 0

        with self.lock:
            self._execute('WITH '
                          'cte AS ( SELECT uuid, timestamp, ROW_NUMBER() OVER ( PARTITION BY uuid '
                          '                                                     ORDER BY timestamp DESC ) rn '
                          '         FROM webchanges ) '
                          'DELETE '
                          'FROM webchanges '
                          'WHERE EXISTS ( SELECT 1 '
                          '               FROM cte '
                          '               WHERE webchanges.uuid = cte.uuid '
                          '                 AND webchanges.timestamp = cte.timestamp '
                          '                 AND cte.rn > ? );', (keep_entries,))
            num_del = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def rollback(self, timestamp: float) -> int:
        """Rollback database to timestamp.

        :param timestamp: The timestamp

        :returns: Number of records deleted
        """
        with self.lock:
            self._execute('''
                DELETE FROM webchanges
                WHERE EXISTS (
                     SELECT 1 FROM webchanges w
                     WHERE w.uuid = webchanges.uuid AND webchanges.timestamp > ? AND w.timestamp > ?
                )''', (timestamp, timestamp))
            num_del = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def migrate_from_minidb(self, minidb_filename: str) -> None:
        """Migrate the data of a legacy minidb database to the current database.

        :param minidb_filename: The filename of the legacy minidb database
        """

        print("Found 'minidb' database and upgrading it to the new engine (note: only the last snapshot is retained).")
        logger.info("Found legacy 'minidb' database and converting it to 'sqlite3' and new schema. "
                    "Package 'minidb' needs to be installed for the conversion.")

        from .storage_minidb import CacheMiniDBStorage

        legacy_db = CacheMiniDBStorage(minidb_filename)
        self.restore(legacy_db.backup())
        legacy_db.close()
        print(f'Database upgrade finished; the following backup file can be safely deleted: {minidb_filename}')
        print("and the 'minidb' package can be removed (unless used by another program): $ pip uninstall minidb")
        print('-' * 80)


class CacheRedisStorage(CacheStorage):
    def __init__(self, filename: str) -> None:
        super().__init__(filename)

        if redis is None:
            raise ImportError("Python package 'redis' is missing")

        self.db = redis.from_url(filename)

    @staticmethod
    def _make_key(guid: str) -> str:
        return 'guid:' + guid

    def close(self) -> None:
        self.db.connection_pool.disconnect()
        self.db = None

    def get_guids(self) -> List[str]:
        guids = []
        for guid in self.db.keys(b'guid:*'):
            guids.append(str(guid[len('guid:'):]))
        return guids

    def load(self, guid: str) -> (Optional[str], Optional[float], int, Optional[str]):
        key = self._make_key(guid)
        data = self.db.lindex(key, 0)

        if data:
            r = msgpack.unpackb(data)
            return r['data'], r['timestamp'], r['tries'], r['etag']

        return None, None, 0, None

    def get_history_data(self, guid: str, count: Optional[int] = None):
        history = {}
        if isinstance(count, int) and count < 1:
            return history

        key = self._make_key(guid)
        for i in range(0, self.db.llen(key)):
            r = self.db.lindex(key, i)
            c = msgpack.unpackb(r)
            if c['tries'] == 0 or c['tries'] is None:
                if c['data'] not in history:
                    history[c['data']] = c['timestamp']
                    if count is not None and len(history) >= count:
                        break
        return history

    def save(self, guid: str, data: str, timestamp: float, tries: int, etag: Optional[str], *args) -> None:
        r = {
            'data': data,
            'timestamp': timestamp,
            'tries': tries,
            'etag': etag,
        }
        self.db.lpush(self._make_key(guid), msgpack.packb(r))

    def delete(self, guid: str) -> None:
        self.db.delete(self._make_key(guid))

    def clean(self, guid: str) -> int:
        key = self._make_key(guid)
        i = self.db.llen(key)
        if self.db.ltrim(key, 0, 0):
            return i - self.db.llen(key)

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("Rolling back of 'redis' databases is not supported")
