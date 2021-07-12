"""Handles all storage: job files, config files, hooks file, and cache database engines."""
import copy
import email.utils
import getpass
import logging
import os
import shutil
import sqlite3
import stat
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, NamedTuple, Optional, TextIO, Tuple, Union

import msgpack
import yaml

from . import __docs_url__, __project_name__, __version__
from .filters import FilterBase
from .jobs import JobBase, ShellJob
from .util import edit_file

try:
    import pwd
except ImportError:
    pwd = None  # type: ignore[assignment]

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    'display': {  # select whether the report include the categories below
        'new': True,
        'error': True,
        'unchanged': False,
    },
    'report': {
        'tz': None,  # the timezone as a IANA time zone name, e.g. 'America/Los_Angeles', or null for machine's'
        # the directives below are for the report content types (text, html or markdown)
        'text': {
            'line_length': 75,
            'details': True,  # whether the diff is sent
            'footer': True,
            'minimal': False,
        },
        'html': {
            'diff': 'unified',  # 'unified' or 'table'
        },
        'markdown': {
            'details': True,  # whether the diff is sent
            'footer': True,
            'minimal': False,
        },
        # the directives below control where a report is displayed and/or sent
        'stdout': {  # the console / command line display; uses text
            'enabled': True,
            'color': True,
        },
        'browser': {  # the system's default browser; uses html
            'enabled': False,
            'title': f'[{__project_name__}] {{count}} changes: {{jobs}}',
        },
        'email': {  # email (except mailgun); uses text or both html and text if 'html' is set to true
            'enabled': False,
            'html': True,
            'to': '',
            'from': '',
            'subject': f'[{__project_name__}] {{count}} changes: {{jobs}}',
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
            },
        },
        'pushover': {  # uses text
            'enabled': False,
            'app': '',
            'device': None,
            'sound': 'spacealarm',
            'user': '',
            'priority': 'normal',
        },
        'pushbullet': {  # uses text
            'enabled': False,
            'api_key': '',
        },
        'telegram': {  # uses markdown (from 3.7)
            'enabled': False,
            'bot_token': '',
            'chat_id': '',
            'silent': False,
        },
        'webhook': {  # uses text
            'enabled': False,
            'webhook_url': '',
            'max_message_length': None,
        },
        'webhook_markdown': {  # uses markdown
            'enabled': False,
            'webhook_url': '',
            'max_message_length': None,
        },
        'matrix': {  # uses text
            'enabled': False,
            'homeserver': '',
            'access_token': '',
            'room_id': '',
        },
        'mailgun': {  # uses text
            'enabled': False,
            'region': 'us',
            'api_key': '',
            'domain': '',
            'from_mail': '',
            'from_name': '',
            'to': '',
            'subject': f'[{__project_name__}] {{count}} changes: {{jobs}}',
        },
        'ifttt': {  # uses text
            'enabled': False,
            'key': '',
            'event': '',
        },
        'xmpp': {  # uses text
            'enabled': False,
            'sender': '',
            'recipient': '',
        },
        'prowl': {  # uses text
            'enabled': False,
            'api_key': '',
            'priority': 0,
            'application': '',
            'subject': f'[{__project_name__}] {{count}} changes: {{jobs}}',
        },
        'run_command': {  # uses text
            'enabled': False,
            'command': '',
        },
    },
    'job_defaults': {  # default settings for jobs
        'all': {},
        'url': {},  # these are used for url jobs without use_browser
        'browser': {},  # these are used for url jobs with use_browser: true
        # TODO rename 'shell' to 'command' for clarity
        'shell': {},  # these are used for 'command' jobs
    },
}


class BaseStorage(ABC):
    """Base class for storage."""

    @abstractmethod
    def load(self, *args: Any) -> Any:
        ...

    @abstractmethod
    def save(self, *args: Any, **kwargs: Any) -> Any:
        ...


class BaseFileStorage(BaseStorage, ABC):
    """Base class for file storage."""

    def __init__(self, filename: Optional[Union[str, os.PathLike]]) -> None:
        if isinstance(filename, (str, bytes, Path)):
            self.filename = Path(filename)
        else:
            self.filename = None  # type: ignore[assignment]


class BaseTextualFileStorage(BaseFileStorage, ABC):
    """Base class for textual files."""

    def __init__(self, filename: Optional[Union[str, os.PathLike]]) -> None:
        super().__init__(filename)
        self.config: Dict[str, Any] = {}
        if not isinstance(self, JobsBaseFileStorage):
            self.load()

    @classmethod
    @abstractmethod
    def parse(cls, *args: Any) -> Any:
        ...

    def edit(self, example_file: Optional[Union[str, os.PathLike]] = None) -> int:
        # Python 3.9: file_edit = self.filename.with_stem(self.filename.stem + '_edit')
        file_edit = self.filename.parent.joinpath(self.filename.stem + '_edit' + ''.join(self.filename.suffixes))

        if self.filename.is_file():
            shutil.copy(self.filename, file_edit)
        elif example_file is not None and Path(example_file).is_file():
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
                print('The file', self.filename, 'was NOT updated.')
                user_input = input('Do you want to retry the same edit? (Y/n)')
                if not user_input or user_input.lower()[0] == 'y':
                    continue
                print('Your changes have been saved in', file_edit)
                return 1

        file_edit.replace(self.filename)
        print('Saving edit changes in', self.filename)
        return 0

    @classmethod
    def write_default_config(cls, filename: Path) -> None:
        config_storage = cls(cls)
        config_storage.filename = filename
        config_storage.save()


class JobsBaseFileStorage(BaseTextualFileStorage, ABC):
    """Class for jobs textual files storage."""

    def __init__(self, filename: Path) -> None:
        super().__init__(filename)
        self.filename = filename

    def shelljob_security_checks(self) -> List[str]:
        """Check security of jobs file and its directory, i.e. that they belong to the current UID and only the owner
        can write to. Return list of errors if any. Linux only."""

        if os.name == 'nt':
            return []

        shelljob_errors = []
        current_uid = os.getuid()  # type: ignore[attr-defined]  # not defined in Windows

        dirname = self.filename.parent
        dir_st = dirname.stat()
        if (dir_st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)) != 0:
            shelljob_errors.append(f'{dirname} is group/world-writable')
        if dir_st.st_uid != current_uid:
            shelljob_errors.append(f'{dirname} not owned by {getpass.getuser()}')

        file_st = self.filename.stat()
        if (file_st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)) != 0:
            shelljob_errors.append(f'{self.filename} is group/world-writable')
        if file_st.st_uid != current_uid:
            shelljob_errors.append(f'{self.filename} not owned by {getpass.getuser()}')

        return shelljob_errors

    def load_secure(self) -> List[JobBase]:
        jobs: List[JobBase] = self.load()

        def is_shell_job(job: JobBase) -> bool:
            """Check if the job uses subprocess.run(Shell=True) (insecure).

            :return: True if subprocess.run(Shell=True) is invoked by job."""
            if isinstance(job, ShellJob):
                return True

            for filter_kind, subfilter in FilterBase.normalize_filter_list(job.filter):
                if filter_kind == 'shellpipe':
                    return True

                if job.diff_tool is not None:
                    return True

            return False

        shelljob_errors = self.shelljob_security_checks()
        if shelljob_errors and any(is_shell_job(job) for job in jobs):
            print(
                f"Removing 'command' job(s) and/or jobs with 'diff_tool' because  {' and '.join(shelljob_errors)} (see "
                f'{__docs_url__}jobs.html#important-note-for-command-jobs)'
            )
            jobs = [job for job in jobs if not is_shell_job(job)]

        return jobs


class BaseYamlFileStorage(BaseTextualFileStorage, ABC):
    """Base class for YAML textual files storage."""

    @classmethod
    def parse(cls, *args: Any) -> Any:
        """Return contents of YAML file if it exists"""
        filename = args[0]
        if filename is not None and filename.is_file():
            with open(filename) as fp:
                return yaml.safe_load(fp)


class YamlConfigStorage(BaseYamlFileStorage):
    """Class for configuration file (is a YAML textual file)."""

    def dict_deep_difference(self, d1: dict, d2: dict) -> dict:
        """Return a new dict with elements in the first dict that are not in the second."""

        def _sub_dict_deep_difference(d1: dict, d2: dict) -> dict:
            for key, value in d1.copy().items():
                if isinstance(value, dict) and isinstance(d2.get(key), dict):
                    _sub_dict_deep_difference(value, d2[key])
                    if not len(value):
                        d1.pop(key)
                else:
                    if key in d2:
                        d1.pop(key)
            return d1

        return _sub_dict_deep_difference(copy.deepcopy(d1), d2)

    def dict_deep_merge(self, source: dict, destination: dict) -> dict:
        """Deep merges source dict into destination dict."""
        # https://stackoverflow.com/a/20666342

        def _sub_dict_deep_merge(source: dict, destination: dict) -> dict:
            for key, value in source.items():
                if isinstance(value, dict):
                    # get node or create one
                    node = destination.setdefault(key, {})
                    _sub_dict_deep_merge(value, node)
                else:
                    destination[key] = value

            return destination

        return _sub_dict_deep_merge(source, copy.deepcopy(destination))

    def check_for_unrecognized_keys(self, config: Dict[str, Any]) -> None:
        """Test if config has keys not in DEFAULT_CONFIG (bad keys, e.g. typos); if so, raise ValueError."""

        config_for_extras = copy.deepcopy(config)
        if 'job_defaults' in config_for_extras:
            for key in DEFAULT_CONFIG['job_defaults']:  # 'job_defaults' are not set in DEFAULT_CONFIG
                config_for_extras['job_defaults'][key] = {}
        if 'slack' in config_for_extras.get('report', {}):  # legacy key; ignore
            config_for_extras['report'].pop('slack')
        extras = self.dict_deep_difference(config_for_extras, DEFAULT_CONFIG)
        if extras:
            raise ValueError(
                f'Unrecognized directive(s) in the configuration file {self.filename}:\n'
                f'{yaml.safe_dump(extras)}Check for typos (documentation at {__docs_url__})'
            )

    def load(self, *args: Any) -> None:
        """Load configuration file from self.filename into self.config with missing keys from DEFAULT_CONFIG."""
        config: Dict[str, Any] = self.parse(self.filename)

        if config:
            self.check_for_unrecognized_keys(config)

            # If config is missing keys in DEFAULT_CONFIG, log the missing keys and deep merge DEFAULT_CONFIG
            missing = self.dict_deep_difference(DEFAULT_CONFIG, config)
            if missing:
                logger.info(
                    f'Default values used for the missing directive(s) in the configuration file {self.filename}:\n'
                    f'{yaml.safe_dump(missing)}See documentation at {__docs_url__}'
                )
                config = self.dict_deep_merge(config or {}, DEFAULT_CONFIG)
        else:
            logger.info(f'No directives found in the configuration file {self.filename}; using default directives.')
            config = DEFAULT_CONFIG

        self.config = config

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save self.config into self.filename using YAML."""
        with open(self.filename, 'w') as fp:
            fp.write(
                f'# {__project_name__} configuration file. See {__docs_url__}\n'
                f'# Written on {datetime.now().replace(microsecond=0).isoformat()} using version {__version__}\n'
                f'\n'
            )
            yaml.safe_dump(self.config, fp, default_flow_style=False, sort_keys=False, allow_unicode=True)


class YamlJobsStorage(BaseYamlFileStorage, JobsBaseFileStorage):
    """Class for jobs file (is a YAML textual file)."""

    @classmethod
    def _parse(cls, fp: TextIO) -> List[JobBase]:
        jobs = []
        jobs_by_guid = defaultdict(list)
        for i, job_data in enumerate((job for job in yaml.safe_load_all(fp) if job)):
            job_data['_index_number'] = i + 1
            job = JobBase.unserialize(job_data)
            jobs.append(job)
            jobs_by_guid[job.get_guid()].append(job)

        conflicting_jobs = []
        for guid, guid_jobs in jobs_by_guid.items():
            if len(guid_jobs) != 1:
                conflicting_jobs.append(guid_jobs[0].get_location())

        if conflicting_jobs:
            raise ValueError(
                '\n   '.join(
                    ['Each job must have a unique URL/command (for URLs, append #1, #2, etc. to ' 'make them unique):']
                    + conflicting_jobs
                )
            )

        return jobs

    @classmethod
    def parse(cls, *args: Any) -> List[JobBase]:
        filename = args[0]
        if filename is not None and filename.is_file():
            with open(filename) as fp:
                return cls._parse(fp)
        return []

    def load(self, *args: Any) -> List[JobBase]:
        with open(self.filename) as fp:
            return self._parse(fp)

    def save(self, *args: Any, **kwargs: Any) -> None:
        jobs = args[0]
        print(f'Saving updated list to {self.filename}')

        with open(self.filename, 'w') as fp:
            yaml.safe_dump_all(
                [job.serialize() for job in jobs], fp, default_flow_style=False, sort_keys=False, allow_unicode=True
            )


class CacheStorage(BaseFileStorage, ABC):
    """Base class for snapshots storage."""

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def get_guids(self) -> List[str]:
        ...

    @abstractmethod
    def load(self, *args: Any) -> Tuple[Union[str, bytes], float, int, str]:
        ...

    @abstractmethod
    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        ...

    @abstractmethod
    def save(self, *args: Any, guid: str, data: str, timestamp: float, tries: int, etag: str, **kwargs: Any) -> None:
        ...

    @abstractmethod
    def delete(self, guid: str) -> None:
        ...

    @abstractmethod
    def delete_latest(self, guid: str) -> Optional[int]:
        ...

    @abstractmethod
    def clean(self, guid: str) -> int:
        ...

    @abstractmethod
    def rollback(self, timestamp: float) -> Optional[int]:
        ...

    def backup(self) -> Iterator[Tuple[str, str, float, int, str]]:
        """Return the most recent entry for each 'guid'.

        :returns: An generator of tuples, each consisting of (guid, data, timestamp, tries, etag)
        """
        for guid in self.get_guids():
            data, timestamp, tries, etag = self.load(guid)
            yield guid, data, timestamp, tries, etag

    def restore(self, entries: Iterator[Tuple[str, str, float, int, str]]) -> None:
        """Save multiple entries into the database.

        :param entries: An iterator of tuples WHERE each consists of (guid, data, timestamp, tries, etag)
        """
        for guid, data, timestamp, tries, etag in entries:
            self.save(guid=guid, data=data, timestamp=timestamp, tries=tries, etag=etag, temporary=False)

    def gc(self, known_guids: Iterable[str]) -> None:
        """Garbage collect the database: delete all guids not included in known_guids and keep only last snapshot for
        the others.

        :param known_guids: Thfe guids to keep
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
                if count:
                    print(f'Deleted {count} old snapshots of {guid}')

    def rollback_cache(self, timestamp: float) -> None:
        """Calls rollback() and prints out the result.

        :param timestamp: The timestamp
        """

        count = self.rollback(timestamp)
        timestamp_date = email.utils.formatdate(timestamp, localtime=True)
        if count:
            print(f'Deleted {count} snapshots taken after {timestamp_date}')
        else:
            print(f'No snapshots found after {timestamp_date}')


class Snapshot(NamedTuple):
    """Type for Snapshot object."""

    data: str
    timestamp: float
    tries: int
    etag: str


class CacheDirStorage(CacheStorage):
    """Class for snapshots stored as individual textual files in a directory 'dirname'"""

    def __init__(self, dirname: Union[str, os.PathLike]) -> None:
        super().__init__(dirname)
        self.filename.mkdir(parents=True, exist_ok=True)  # filename is a dir (confusing!)

    def close(self) -> None:
        # No need to close
        return

    def _get_filename(self, guid: str) -> Path:
        return self.filename.joinpath(guid)  # filename is a dir (confusing!)

    def get_guids(self) -> List[str]:
        return [str(filename) for filename in self.filename.iterdir()]

    def load(self, guid: str) -> Snapshot:
        filename = self._get_filename(guid)
        if not filename.is_file():
            return Snapshot('', 0, 0, '')

        try:
            data = filename.read_text()
        except UnicodeDecodeError:
            data = filename.read_text(errors='ignore')
            logger.warning(f'Found and ignored Unicode-related errors when retrieving saved snapshot {guid}')

        timestamp = filename.stat().st_mtime

        return Snapshot(data, timestamp, 0, '')

    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        if isinstance(count, int) and count < 1:
            return {}
        else:
            data, timestamp, tries, etag = self.load(guid)
            return {data: timestamp} if data and timestamp else {}

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
        # Timestamp is not saved as is read from the file's timestamp; ETag is ignored
        filename = self._get_filename(guid)
        with open(filename, 'w+') as fp:
            fp.write(data)

    def delete(self, guid: str) -> None:
        filename = self._get_filename(guid)
        # Python 3.8: replace with filename.unlink(missing_ok=True)
        if filename.is_file():
            filename.unlink()
        return

    def delete_latest(self, guid: str) -> int:
        filename = self._get_filename(guid)
        if filename.is_file():
            filename.unlink()
            return 1
        return 0

    def clean(self, guid: str) -> int:
        # We only store the latest version, no need to clean
        return 0

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("'textfiles' databases cannot be rolled back as new snapshots overwrite old ones")


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

    def __init__(self, filename: Union[str, os.PathLike], max_snapshots: int = 4) -> None:
        """
        :param filename: The full filename of the database file
        :param max_snapshots: The maximum number of snapshots to retain in the database for each 'guid'
        """
        # Opens the database file and, if new, creates a table and index.

        self.max_snapshots = max_snapshots

        logger.debug(f'sqlite3.version={sqlite3.version}, sqlite3.sqlite_version={sqlite3.sqlite_version}')
        logger.info(f'Opening permanent sqlite3 database file {filename}')
        super().__init__(filename)

        self.filename.parent.mkdir(parents=True, exist_ok=True)

        # https://stackoverflow.com/questions/26629080
        self.lock = threading.RLock()

        self.db = sqlite3.connect(filename, check_same_thread=False)
        self.cur = self.db.cursor()
        self.cur.execute('PRAGMA temp_store = MEMORY;')
        tables = self._execute("SELECT name FROM sqlite_master WHERE type='table';").fetchone()

        def _initialize_table(self: CacheSQLite3Storage) -> None:
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
            # Python 3.9: minidb_filename = filename.with_stem(filename.stem + '_minidb')
            minidb_filename = self.filename.parent.joinpath(
                self.filename.stem + '_minidb' + ''.join(self.filename.suffixes)
            )
            self.filename.replace(minidb_filename)
            self.db = sqlite3.connect(filename, check_same_thread=False)
            self.cur = self.db.cursor()
            _initialize_table(self)
            # migrate the minidb legacy database renamed above
            self.migrate_from_minidb(minidb_filename)
        elif tables != ('webchanges',):
            _initialize_table(self)

        # create temporary database in memory for writing during execution (fault tolerance)
        logger.debug('Creating temp sqlite3 database file in memory')
        self.temp_lock = threading.RLock()
        self.temp_db = sqlite3.connect('', check_same_thread=False)
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
        """Execute SQL command on temp database."""
        if args is None:
            logger.debug(f"Executing (temp) '{sql}'")
            return self.temp_cur.execute(sql)
        else:
            logger.debug(f"Executing (temp) '{sql}' with {args[:2]}...")
            return self.temp_cur.execute(sql, args)

    def _copy_temp_to_permanent(self, delete: bool = False) -> None:
        """Copy contents of temporary database to permanent one.

        :param:delete: also delete contents of temporary cache (used for testing)
        """
        logger.debug('Saving new snapshots to permanent sqlite3 database')
        # with self.temp_lock:
        #     self.temp_db.commit()
        # with self.lock:
        #     self._execute('ATTACH DATABASE ? AS temp_db', (str(self.temp_filename),))
        #     self._execute('INSERT INTO webchanges SELECT * FROM temp_db.webchanges')
        #     logger.debug(f'Wrote {self.cur.rowcount} new snapshots to permanent sqlite3 database')
        #     self.db.commit()
        #     self._execute('DETACH DATABASE temp_db')
        with self.temp_lock:
            with self.lock:
                for row in self._temp_execute('SELECT * FROM webchanges').fetchall():
                    self._execute('INSERT INTO webchanges VALUES (?, ?, ?)', row)
                self.db.commit()
            if delete:
                self._temp_execute('DELETE FROM webchanges')

    def close(self) -> None:
        """Writes the temporary database to the permanent one, purges old entries if required, and closes all database
        connections."""
        self._copy_temp_to_permanent()
        with self.temp_lock:
            self.temp_db.close()
            logger.debug('Cleaning up the permanent sqlite3 database and closing the connection')
        with self.lock:
            if self.max_snapshots:
                num_del = self.keep_latest(self.max_snapshots)
                logger.debug(
                    f'Keeping no more than {self.max_snapshots} snapshots per job: ' f'purged {num_del} older entries'
                )
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
            row = self._execute(
                'SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? ' 'ORDER BY timestamp DESC LIMIT 1',
                (guid,),
            ).fetchone()
        if row:
            msgpack_data, timestamp = row
            r = msgpack.unpackb(msgpack_data)
            return Snapshot(r['d'], timestamp, r['t'], r['e'])

        return Snapshot('', 0, 0, '')

    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        """Return data and timestamp from the last 'count' (None = all) entries matching a 'guid'.

        :param guid: The guid
        :param count: The maximum number of entries to return; if None return all

        :returns: A dict (key: value)
            WHERE
            key is the data;
            value is the timestamp.
        """
        history: Dict[str, float] = {}
        if isinstance(count, int) and count < 1:
            return history

        with self.lock:
            rows = self._execute(
                'SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? ' 'ORDER BY timestamp DESC', (guid,)
            ).fetchall()
        if rows:
            for msgpack_data, timestamp in rows:
                r = msgpack.unpackb(msgpack_data)
                if not r['t']:
                    if r['d'] not in history:
                        history[r['d']] = timestamp
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
        temporary: Optional[bool] = True,
        **kwargs: Any,
    ) -> None:
        """Save the data from a job.

        By default it is saved into the temporary database. Call close() to transfer the contents of the temporary
        database to the permanent one.

        :param guid: The guid
        :param data: The data
        :param timestamp: The timestamp
        :param tries: The number of tries
        :param etag: The ETag (could be empty string)
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

    def delete_latest(self, guid: str, delete_entries: int = 1) -> int:
        """For the given 'guid', delete only the latest 'delete_entries' number of entries and keep all other (older)
        ones.

        :param guid: The guid
        :param delete_entries: Number of most recent entries to delete

        :returns: Number of records deleted
        """
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
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def clean(self, guid: str, keep_entries: int = 1) -> int:
        """For the given 'guid', keep only the latest 'keep_entries' number of entries and delete all other (older)
        ones. To delete older entries from all guids, use clean_all() instead.

        :param guid: The guid
        :param keep_entries: Number of entries to keep after deletion

        :returns: Number of records deleted
        """
        with self.lock:
            self._execute(
                'DELETE FROM webchanges '
                'WHERE ROWID IN ( '
                '    SELECT ROWID FROM webchanges '
                '    WHERE uuid = ? '
                '    ORDER BY timestamp DESC '
                '    LIMIT -1 OFFSET ? '
                ')',
                (guid, keep_entries),
            )
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def clean_all(self) -> int:
        """Delete all older entries for each 'guid' (keep only last one).

        :returns: Number of records deleted
        """
        with self.lock:
            self._execute(
                'DELETE FROM webchanges '
                'WHERE EXISTS ( '
                '    SELECT 1 FROM webchanges w '
                '    WHERE w.uuid = webchanges.uuid AND w.timestamp > webchanges.timestamp '
                ')'
            )
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def keep_latest(self, keep_entries: int = 1) -> int:
        """Delete all older entries keeping only the 'keep_num' per guid.

        :param keep_entries: Number of entries to keep after deletion

        :returns: Number of records deleted
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

    def rollback(self, timestamp: float) -> int:
        """Rollback database to timestamp.

        :param timestamp: The timestamp

        :returns: Number of records deleted
        """
        with self.lock:
            self._execute(
                'DELETE FROM webchanges '
                'WHERE EXISTS ( '
                '     SELECT 1 FROM webchanges w '
                '     WHERE w.uuid = webchanges.uuid AND webchanges.timestamp > ? AND w.timestamp > ? '
                ')',
                (timestamp, timestamp),
            )
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
        return num_del

    def migrate_from_minidb(self, minidb_filename: Union[str, os.PathLike]) -> None:
        """Migrate the data of a legacy minidb database to the current database.

        :param minidb_filename: The filename of the legacy minidb database
        """

        print("Found 'minidb' database and upgrading it to the new engine (note: only the last snapshot is retained).")
        logger.info(
            "Found legacy 'minidb' database and converting it to 'sqlite3' and new schema. Package 'minidb' needs to be"
            ' installed for the conversion.'
        )

        from .storage_minidb import CacheMiniDBStorage

        legacy_db = CacheMiniDBStorage(minidb_filename)
        self.restore(legacy_db.backup())
        legacy_db.close()
        print(f'Database upgrade finished; the following backup file can be safely deleted: {minidb_filename}\n')
        print("The 'minidb' package can be removed (unless used by another program): $ pip uninstall minidb")
        print('-' * 80)


class CacheRedisStorage(CacheStorage):
    """Class for storing snapshots using redis."""

    def __init__(self, filename: Union[str, os.PathLike]) -> None:
        super().__init__(filename)

        if redis is None:
            raise ImportError("Python package 'redis' is missing")

        self.db = redis.from_url(str(filename))

    @staticmethod
    def _make_key(guid: str) -> str:
        return 'guid:' + guid

    def close(self) -> None:
        self.db.connection_pool.disconnect()
        del self.db

    def get_guids(self) -> List[str]:
        guids = []
        for guid in self.db.keys(b'guid:*'):
            guids.append(str(guid[len('guid:') :]))
        return guids

    def load(self, guid: str) -> Snapshot:
        key = self._make_key(guid)
        data = self.db.lindex(key, 0)

        if data:
            r = msgpack.unpackb(data)
            return Snapshot(r['data'], r['timestamp'], r['tries'], r['etag'])

        return Snapshot('', 0, 0, '')

    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        history: Dict[str, float] = {}
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
        r = {
            'data': data,
            'timestamp': timestamp,
            'tries': tries,
            'etag': etag,
        }
        self.db.lpush(self._make_key(guid), msgpack.packb(r))

    def delete(self, guid: str) -> None:
        self.db.delete(self._make_key(guid))

    def delete_latest(self, guid: str) -> None:
        if self.db.lpop(self._make_key(guid)) is None:
            return 0

        return 1

    def clean(self, guid: str) -> int:
        key = self._make_key(guid)
        i = self.db.llen(key)
        if self.db.ltrim(key, 0, 0):
            return i - self.db.llen(key)

        return 0

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("Rolling back the database is not supported by 'redis' database engine")
