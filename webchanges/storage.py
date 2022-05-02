"""Handles all storage: job files, config files, hooks file, and cache database engines."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import copy
import email.utils
import getpass
import inspect
import logging
import os
import shutil
import sqlite3
import stat
import sys
import threading
import warnings
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, NamedTuple, Optional, TextIO, Tuple, TYPE_CHECKING, Union

import msgpack
import yaml

from . import __docs_url__, __project_name__, __version__
from .filters import FilterBase
from .jobs import JobBase, ShellJob
from .reporters import ReporterBase
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

if TYPE_CHECKING:
    from typing import Literal, TypedDict  # not available in Python < 3.8

    ConfigDisplay = TypedDict(
        'ConfigDisplay',
        {
            'new': bool,
            'error': bool,
            'unchanged': bool,
        },
    )
    ConfigReportText = TypedDict(
        'ConfigReportText',
        {
            'line_length': int,
            'details': bool,
            'footer': bool,
            'minimal': bool,
        },
    )
    ConfigReportHtml = TypedDict(
        'ConfigReportHtml',
        {
            'diff': Literal['unified', 'table'],
        },
    )
    ConfigReportMarkdown = TypedDict(
        'ConfigReportMarkdown',
        {
            'details': bool,
            'footer': bool,
            'minimal': bool,
        },
    )
    ConfigReportStdout = TypedDict(
        'ConfigReportStdout',
        {
            'enabled': bool,
            'color': bool,
        },
    )
    ConfigReportBrowser = TypedDict(
        'ConfigReportBrowser',
        {
            'enabled': bool,
            'title': str,
        },
    )
    ConfigReportDiscord = TypedDict(
        'ConfigReportDiscord',
        {
            'enabled': bool,
            'webhook_url': str,
            'embed': bool,
            'subject': str,
            'colored': bool,
            'max_message_length': Optional[int],
        },
    )
    ConfigReportEmailSmtp = TypedDict(
        'ConfigReportEmailSmtp',
        {
            'host': str,
            'user': str,
            'port': int,
            'starttls': bool,
            'auth': bool,
            'insecure_password': str,
        },
    )
    ConfigReportEmailSendmail = TypedDict(
        'ConfigReportEmailSendmail',
        {
            'path': Union[str, Path],
        },
    )
    ConfigReportEmail = TypedDict(
        'ConfigReportEmail',
        {
            'enabled': bool,
            'html': bool,
            'to': str,
            'from': str,
            'subject': str,
            'method': Literal['sendmail', 'smtp'],
            'smtp': ConfigReportEmailSmtp,
            'sendmail': ConfigReportEmailSendmail,
        },
    )
    ConfigReportIfttt = TypedDict(
        'ConfigReportIfttt',
        {
            'enabled': bool,
            'key': str,
            'event': str,
        },
    )
    ConfigReportMailgun = TypedDict(
        'ConfigReportMailgun',
        {
            'enabled': bool,
            'region': str,
            'api_key': str,
            'domain': str,
            'from_mail': str,
            'from_name': str,
            'to': str,
            'subject': str,
        },
    )
    ConfigReportMatrix = TypedDict(
        'ConfigReportMatrix',
        {
            'enabled': bool,
            'homeserver': str,
            'access_token': str,
            'room_id': str,
        },
    )
    ConfigReportProwl = TypedDict(
        'ConfigReportProwl',
        {
            'enabled': bool,
            'api_key': str,
            'priority': int,
            'application': str,
            'subject': str,
        },
    )
    ConfigReportPushbullet = TypedDict(
        'ConfigReportPushbullet',
        {
            'enabled': bool,
            'api_key': str,
        },
    )
    ConfigReportPushover = TypedDict(
        'ConfigReportPushover',
        {
            'enabled': bool,
            'app': str,
            'device': Optional[str],
            'sound': str,
            'user': str,
            'priority': str,
        },
    )
    ConfigReportRunCommand = TypedDict(
        'ConfigReportRunCommand',
        {
            'enabled': bool,
            'command': str,
        },
    )
    ConfigReportTelegram = TypedDict(
        'ConfigReportTelegram',
        {
            'enabled': bool,
            'bot_token': str,
            'chat_id': Union[str, int, List[Union[str, int]]],
            'silent': bool,
        },
    )
    ConfigReportWebhook = TypedDict(
        'ConfigReportWebhook',
        {
            'enabled': bool,
            'markdown': bool,
            'webhook_url': str,
            'max_message_length': Optional[int],
        },
    )
    ConfigReportXmpp = TypedDict(
        'ConfigReportXmpp',
        {
            'enabled': bool,
            'sender': str,
            'recipient': str,
            'insecure_password': Optional[str],
        },
    )

    ConfigReport = TypedDict(
        'ConfigReport',
        {
            'tz': Optional[str],
            'text': ConfigReportText,
            'html': ConfigReportHtml,
            'markdown': ConfigReportMarkdown,
            'stdout': ConfigReportStdout,
            'browser': ConfigReportBrowser,
            'discord': ConfigReportDiscord,
            'email': ConfigReportEmail,
            'ifttt': ConfigReportIfttt,
            'mailgun': ConfigReportMailgun,
            'matrix': ConfigReportMatrix,
            'prowl': ConfigReportProwl,
            'pushbullet': ConfigReportPushbullet,
            'pushover': ConfigReportPushover,
            'run_command': ConfigReportRunCommand,
            'telegram': ConfigReportTelegram,
            'webhook': ConfigReportWebhook,
            'xmpp': ConfigReportXmpp,
        },
    )
    ConfigJobDefaults = TypedDict(
        'ConfigJobDefaults',
        {
            'all': Dict[str, Any],
            'url': Dict[str, Any],
            'browser': Dict[str, Any],
            'shell': Dict[str, Any],
        },
    )
    Config = TypedDict(
        'Config',
        {
            'display': ConfigDisplay,
            'report': ConfigReport,
            'job_defaults': ConfigJobDefaults,
        },
    )

DEFAULT_CONFIG: Config = {
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
        # the directives below control 'reporters', i.e. where a report is displayed and/or sent
        'stdout': {  # the console / command line display; uses text
            'enabled': True,
            'color': True,
        },
        'browser': {  # the system's default browser; uses html
            'enabled': False,
            'title': f'[{__project_name__}] {{count}} changes: {{jobs}}',
        },
        'discord': {
            'enabled': False,
            'webhook_url': '',
            'embed': True,
            'subject': '{count} changes: {jobs}',
            'colored': True,
            'max_message_length': None,
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
                'port': 25,
                'starttls': True,
                'user': '',
                'auth': True,
                'insecure_password': '',
            },
            'sendmail': {
                'path': 'sendmail',
            },
        },
        'ifttt': {  # uses text
            'enabled': False,
            'key': '',
            'event': '',
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
        'matrix': {  # uses text
            'enabled': False,
            'homeserver': '',
            'access_token': '',
            'room_id': '',
        },
        'prowl': {  # uses text
            'enabled': False,
            'api_key': '',
            'priority': 0,
            'application': '',
            'subject': f'[{__project_name__}] {{count}} changes: {{jobs}}',
        },
        'pushbullet': {  # uses text
            'enabled': False,
            'api_key': '',
        },
        'pushover': {  # uses text
            'enabled': False,
            'app': '',
            'user': '',
            'device': None,
            'sound': 'spacealarm',
            'priority': 'normal',
        },
        'run_command': {  # uses text
            'enabled': False,
            'command': '',
        },
        'telegram': {  # uses markdown (from 3.7)
            'enabled': False,
            'bot_token': '',
            'chat_id': '',
            'silent': False,
        },
        'webhook': {
            'enabled': False,
            'webhook_url': '',
            'markdown': False,
            'max_message_length': None,
        },
        'xmpp': {  # uses text
            'enabled': False,
            'sender': '',
            'recipient': '',
            'insecure_password': '',
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


@dataclass
class BaseStorage(ABC):
    """Base class for storage."""

    filename: Path


class BaseFileStorage(BaseStorage, ABC):
    """Base class for file storage."""

    def __init__(self, filename: Union[str, Path]) -> None:
        """

        :param filename: The filename or directory name to storage.
        """
        if isinstance(filename, str):
            self.filename = Path(filename)
        else:
            self.filename = filename


class BaseTextualFileStorage(BaseFileStorage, ABC):
    """Base class for textual files."""

    def __init__(self, filename: Union[str, Path]) -> None:
        """

        :param filename: The filename or directory name to storage.
        """
        super().__init__(filename)
        # if not isinstance(self, JobsBaseFileStorage):
        #     self.load()

    @abstractmethod
    def load(self, *args: Any) -> Any:
        """Load from storage.

        :param args: Specified by the subclass.
        :return: Specified by the subclass.
        """
        pass

    @abstractmethod
    def save(self, *args: Any, **kwargs: Any) -> Any:
        """Save to storage.

        :param args: Specified by the subclass.
        :param kwargs: Specified by the subclass.
        :return: Specified by the subclass.
        """
        pass

    @classmethod
    @abstractmethod
    def parse(cls, *args: Any) -> Any:
        """Parse storage contents.

        :param args: Specified by the subclass.
        :return: Specified by the subclass.
        """
        pass

    def edit(self) -> int:
        """Edit file.

        :returns: None if edit is successful, 1 otherwise.
        """
        # Similar code to UrlwatchCommand.edit_hooks()
        # Python 3.9: file_edit = self.filename.with_stem(self.filename.stem + '_edit')
        file_edit = self.filename.parent.joinpath(self.filename.stem + '_edit' + ''.join(self.filename.suffixes))

        if self.filename.is_file():
            shutil.copy(self.filename, file_edit)
        # elif example_file is not None and Path(example_file).is_file():
        #     shutil.copy(example_file, file_edit, follow_symlinks=False)

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
                print(f'The file {self.filename} was NOT updated.')
                user_input = input('Do you want to retry the same edit? (Y/n)')
                if not user_input or user_input.lower()[0] == 'y':
                    continue
                file_edit.unlink()
                print('No changes have been saved.')
                return 1

        if self.filename.is_symlink():
            self.filename.write_text(file_edit.read_text())
        else:
            file_edit.replace(self.filename)
        # Python 3.8: replace with file_edit.unlink(missing_ok=True)
        if file_edit.is_file():
            file_edit.unlink()
        print('Saved edits in', self.filename)
        return 0

    @classmethod
    def write_default_config(cls, filename: Path) -> None:
        """Write default configuration to file.

        :param filename: The filename.
        """
        config_storage = cls(filename)
        config_storage.save()


class JobsBaseFileStorage(BaseTextualFileStorage, ABC):
    """Class for jobs textual files storage."""

    def __init__(self, filename: Path) -> None:
        """

        :param filename: The filename of the jobs file.
        """
        super().__init__(filename)
        self.filename = filename

    def shelljob_security_checks(self) -> List[str]:
        """Check security of jobs file and its directory, i.e. that they belong to the current UID and only the owner
        can write to them. Return list of errors if any. Linux only.

        :returns: List of errors encountered (if any).
        """

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
        """Load the jobs from a text file checking that the file is secure (i.e. belongs to the current UID and only
        the owner can write to it - Linux only).

        :return: List of JobBase objects.
        """
        jobs: List[JobBase] = self.load()

        def is_shell_job(job: JobBase) -> bool:
            """Check if the job uses filter 'shellpipe' or an external differ, as they call subprocess.run(
            Shell=True) (insecure).

            :returns: True if subprocess.run(Shell=True) is invoked by job, False otherwise.
            """
            if isinstance(job, ShellJob):
                return True

            for filter_kind, subfilter in FilterBase.normalize_filter_list(job.filter):
                if filter_kind == 'shellpipe':
                    return True

                if job.diff_tool is not None and not job.diff_tool.startswith('deepdiff'):
                    return True

            return False

        shelljob_errors = self.shelljob_security_checks()
        removed_jobs = (job for job in jobs if is_shell_job(job))
        if shelljob_errors and any(removed_jobs):
            print(
                f'ERROR: Removing the following jobs because '
                f" {' and '.join(shelljob_errors)}: {' ,'.join(str(job.index_number) for job in removed_jobs)}\n"
                f'(see {__docs_url__}en/stable/jobs.html#important-note-for-command-jobs)'
            )
            jobs = [job for job in jobs if job not in removed_jobs]

        return jobs


class BaseYamlFileStorage(BaseTextualFileStorage, ABC):
    """Base class for YAML textual files storage."""

    @classmethod
    def parse(cls, *args: Any) -> Any:
        """Return contents of YAML file if it exists

        :param args: Specified by the subclass.
        :return: Specified by the subclass.
        """
        filename = args[0]
        if filename is not None and filename.is_file():
            with filename.open() as fp:
                return yaml.safe_load(fp)


class YamlConfigStorage(BaseYamlFileStorage):
    """Class for configuration file (is a YAML textual file)."""

    config: Config = {}  # type: ignore[typeddict-item]

    @staticmethod
    def dict_deep_difference(d1: Config, d2: Config) -> Config:
        """Recursively find elements in the first dict that are not in the second.

        :param d1: The first dict.
        :param d2: The second dict.
        :return: A dict with all the elements on the first dict that are not in the second.
        """

        def _sub_dict_deep_difference(d1_: Config, d2_: Config) -> Config:
            """Recursive sub-function to find elements in the first dict that are not in the second.

            :param d1_: The first dict.
            :param d2_: The second dict.
            :return: A dict with elements on the first dict that are not in the second.
            """
            for key, value in d1_.copy().items():
                if isinstance(value, dict) and isinstance(d2_.get(key), dict):  # type: ignore[misc]
                    _sub_dict_deep_difference(value, d2_[key])  # type: ignore[arg-type,literal-required]
                    if not len(value):
                        d1_.pop(key)  # type: ignore[misc]
                else:
                    if key in d2_:
                        d1_.pop(key)  # type: ignore[misc]
            return d1_

        return _sub_dict_deep_difference(copy.deepcopy(d1), d2)

    @staticmethod
    def dict_deep_merge(source: Config, destination: Config) -> Config:
        """Recursively deep merges source dict into destination dict.

        :param source: The first dict.
        :param destination: The second dict.
        :return: The deep merged dict.
        """

        # https://stackoverflow.com/a/20666342

        def _sub_dict_deep_merge(source_: Config, destination_: Config) -> Config:
            """Recursive sub-function to merges source_ dict into destination_ dict.

            :param source_: The first dict.
            :param destination_: The second dict.
            :return: The merged dict.
            """
            for key, value in source_.items():
                if isinstance(value, dict):
                    # get node or create one
                    node = destination_.setdefault(key, {})  # type: ignore[misc]
                    _sub_dict_deep_merge(value, node)  # type: ignore[arg-type]
                else:
                    destination_[key] = value  # type: ignore[literal-required]

            return destination_

        return _sub_dict_deep_merge(source, copy.deepcopy(destination))

    def check_for_unrecognized_keys(self, config: Config) -> None:
        """Test if config has keys not in DEFAULT_CONFIG (bad keys, e.g. typos); if so, raise ValueError.

        :param config: The configuration.
        :raises ValueError: If the configuration has keys not in DEFAULT_CONFIG (bad keys, e.g. typos)
        """
        for key in ('_beta_use_playwright', 'chromium_revision'):
            if key in config['job_defaults']['all'] or key in config['job_defaults']['browser']:
                warnings.warn(
                    f'Directive {key} found in the configuration file {self.filename} has been deprecated'
                    f'with the use of Playright. Please delete it (webchanges --edit-config)',
                    DeprecationWarning,
                )

        config_for_extras = copy.deepcopy(config)
        if 'job_defaults' in config_for_extras:
            # 'job_defaults' is not set in DEFAULT_CONFIG
            for key in DEFAULT_CONFIG['job_defaults']:
                config_for_extras['job_defaults'][key] = {}  # type: ignore[literal-required]
        if 'slack' in config_for_extras.get('report', {}):  # legacy key; ignore
            config_for_extras['report'].pop('slack')  # type: ignore[typeddict-item]
        extras: Config = self.dict_deep_difference(config_for_extras, DEFAULT_CONFIG)
        if extras.get('report') and 'hooks' in sys.modules:
            # skip reports added by hooks
            for name, obj in inspect.getmembers(sys.modules['hooks'], inspect.isclass):
                if obj.__module__ == 'hooks' and issubclass(obj, ReporterBase):
                    extras['report'].pop(obj.__kind__, None)  # type: ignore[misc]
            if not len(extras['report']):
                extras.pop('report')  # type: ignore[misc]
        if extras:
            warnings.warn(
                f'Found unrecognized directive(s) in the configuration file {self.filename}:\n'
                f'{yaml.safe_dump(extras)}Check for typos (documentation at {__docs_url__})\n',
                RuntimeWarning,
            )

    @staticmethod
    def replace_none_keys(config: Config) -> None:
        """Fixes None keys in loaded config that should be empty dicts instead."""
        if 'job_defaults' not in config:
            config['job_defaults'] = {
                'all': {},
                'url': {},
                'browser': {},
                'shell': {},
            }
        else:
            for key in ('all', 'url', 'browser', 'shell'):
                if key not in config['job_defaults']:
                    config['job_defaults'][key] = {}  # type: ignore[literal-required]
                elif config['job_defaults'][key] is None:  # type: ignore[literal-required]
                    config['job_defaults'][key] = {}  # type: ignore[literal-required]

    def load(self, *args: Any) -> None:
        """Load configuration file from self.filename into self.config adding missing keys from DEFAULT_CONFIG.

        :param args: None used.
        """
        config: Config = self.parse(self.filename)

        if config:
            self.replace_none_keys(config)
            self.check_for_unrecognized_keys(config)

            # If config is missing keys in DEFAULT_CONFIG, log the missing keys and deep merge DEFAULT_CONFIG
            missing = self.dict_deep_difference(DEFAULT_CONFIG, config)
            if missing:
                logger.info(
                    f'The configuration file {self.filename} is missing directive(s); the following default '
                    f'values are being used:\n'
                    f'{yaml.safe_dump(missing)}'
                    f'See documentation at {__docs_url__}/en/stable/configuration.html'
                )
                config = self.dict_deep_merge(config or {}, DEFAULT_CONFIG)
        else:
            logger.info(f'No directives found in the configuration file {self.filename}; using default directives.')
            config = DEFAULT_CONFIG

        self.config = config

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save self.config into self.filename using YAML.

        :param args: None used.
        :param kwargs: None used.
        """
        with self.filename.open('w') as fp:
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
        """Parse the contents of a jobs YAML file.

        :param fp: The text stream to parse.
        :return: A list of JobBase objects.
        :raise yaml.YAMLError: If a YAML error is found in the file.
        :raise ValueError: If a duplicate URL/command is found in the list.
        """
        jobs = []
        jobs_by_guid = defaultdict(list)
        for i, job_data in enumerate((job for job in yaml.safe_load_all(fp) if job)):
            job_data['index_number'] = i + 1
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
                    ['Each job must have a unique URL/command (for URLs, append #1, #2, etc. to make them unique):']
                    + conflicting_jobs
                )
            )

        return jobs

    @classmethod
    def parse(cls, *args: Path) -> List[JobBase]:
        """Parse the contents of the job YAML file and return a list of jobs.

        :param args: The filename.
        :return: A list of JobBase objects.
        """
        filename = args[0]
        if filename is not None and filename.is_file():
            with filename.open() as fp:
                return cls._parse(fp)
        return []

    def load(self, *args: Any) -> List[JobBase]:
        """Parse the contents of the job YAML file and return a list of jobs.

        :return: A list of JobBase objects.
        """
        with self.filename.open() as fp:
            return self._parse(fp)

    def save(self, *args: Iterable[JobBase], **kwargs: Any) -> None:
        """Save jobs to the job YAML file.

        :param args: An iterable of JobBase objects to be written.
        """
        jobs = args[0]
        print(f'Saving updated list to {self.filename}')

        with self.filename.open('w') as fp:
            yaml.safe_dump_all(
                [job.serialize() for job in jobs], fp, default_flow_style=False, sort_keys=False, allow_unicode=True
            )


class Snapshot(NamedTuple):
    """Type for Snapshot object."""

    data: str
    timestamp: float
    tries: int
    etag: str


class CacheStorage(BaseFileStorage, ABC):
    """Base class for snapshots storage."""

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def get_guids(self) -> List[str]:
        pass

    @abstractmethod
    def load(self, guid: str) -> Snapshot:
        pass

    @abstractmethod
    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        pass

    @abstractmethod
    def get_rich_history_data(self, guid: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save(self, *args: Any, guid: str, data: str, timestamp: float, tries: int, etag: str, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def delete(self, guid: str) -> None:
        pass

    @abstractmethod
    def delete_latest(self, guid: str, delete_entries: int = 1) -> int:
        """For the given 'guid', delete only the latest 'delete_entries' entries and keep all other (older) ones.

        :param guid: The guid.
        :param delete_entries: The number of most recent entries to delete.

        :returns: Number of records deleted.
        """
        pass

    @abstractmethod
    def clean(self, guid: str, keep_entries: int = 1) -> int:
        pass

    @abstractmethod
    def rollback(self, timestamp: float) -> Optional[int]:
        pass

    def backup(self) -> Iterator[Tuple[str, str, float, int, str]]:
        """Return the most recent entry for each 'guid'.

        :returns: An generator of tuples, each consisting of (guid, data, timestamp, tries, etag)
        """
        for guid in self.get_guids():
            data, timestamp, tries, etag = self.load(guid)
            yield guid, data, timestamp, tries, etag

    def restore(self, entries: Iterable[Tuple[str, str, float, int, str]]) -> None:
        """Save multiple entries into the database.

        :param entries: An iterator of tuples WHERE each consists of (guid, data, timestamp, tries, etag)
        """
        for guid, data, timestamp, tries, etag in entries:
            self.save(guid=guid, data=data, timestamp=timestamp, tries=tries, etag=etag, temporary=False)

    def gc(self, known_guids: Iterable[str]) -> None:
        """Garbage collect the database: delete all guids not included in known_guids and keep only last snapshot for
        the others.

        :param known_guids: The guids to keep.
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
            count = self.clean_all()  # type: ignore[attr-defined]
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


class CacheDirStorage(CacheStorage):
    """Class for snapshots stored as individual textual files in a directory 'dirname'."""

    def __init__(self, dirname: Union[str, Path]) -> None:
        super().__init__(dirname)
        self.filename.mkdir(parents=True, exist_ok=True)  # filename is a dir (confusing!)

    def close(self) -> None:
        # No need to close
        return

    def _get_filename(self, guid: str) -> Path:
        return self.filename.joinpath(guid)  # filename is a dir (confusing!)

    def get_guids(self) -> List[str]:
        return [filename.name for filename in self.filename.iterdir()]

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
        if count is not None and count < 1:
            return {}
        else:
            data, timestamp, tries, etag = self.load(guid)
            return {data: timestamp} if data and timestamp else {}

    def get_rich_history_data(self, guid: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        if count is not None and count < 1:
            return []
        else:
            data, timestamp, tries, etag = self.load(guid)
            return [{'timestamp': timestamp, 'data': data}] if data and timestamp else []

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
        # ETag is ignored
        filename = self._get_filename(guid)
        with filename.open('w+') as fp:
            fp.write(data)
        os.utime(filename, times=(datetime.now().timestamp(), timestamp))

    def delete(self, guid: str) -> None:
        filename = self._get_filename(guid)
        # Python 3.8: replace with filename.unlink(missing_ok=True)
        if filename.is_file():
            filename.unlink()
        return

    def delete_latest(self, guid: str, delete_entries: int = 1) -> int:
        """For the given 'guid', delete the latest entry and keep all other (older) ones.

        :param guid: The guid.
        :param delete_entries: The number of most recent entries to delete.

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

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("'textfiles' databases cannot be rolled back as new snapshots overwrite old ones")


class CacheSQLite3Storage(CacheStorage):
    """
    Handles storage of the snapshot as a SQLite database in the 'filename' file using Python's built-in sqlite3 module
    and the msgpack package.

    A temporary database is created by __init__ and will be written by the 'save()' function (unless temporary=False).
    This data will be written to the permanent one by the 'close()' function, which is called at the end of program
    execution.

    The database contains the 'webchanges' table with the following columns:

    * guid: unique hash of the "location", i.e. the URL/command; indexed
    * timestamp: the Unix timestamp of when then the snapshot was taken; indexed
    * msgpack_data: a msgpack blob containing 'data', 'tries' and 'etag' in a dict of keys 'd', 't' and 'e'
    """

    def __init__(self, filename: Union[str, Path], max_snapshots: int = 4) -> None:
        """
        :param filename: The full filename of the database file
        :param max_snapshots: The maximum number of snapshots to retain in the database for each 'guid'
        """
        # Opens the database file and, if new, creates a table and index.

        self.max_snapshots = max_snapshots

        logger.debug(f'Run-time SQLite library: {sqlite3.sqlite_version}')
        logger.info(f'Opening permanent sqlite3 database file {filename}')
        super().__init__(filename)

        self.filename.parent.mkdir(parents=True, exist_ok=True)

        # https://stackoverflow.com/questions/26629080
        self.lock = threading.RLock()

        self.db = sqlite3.connect(filename, check_same_thread=False)
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
            _initialize_table()
            # Migrate the minidb legacy database renamed above
            self.migrate_from_minidb(minidb_filename)
        elif tables != ('webchanges',):
            _initialize_table()

        # Create temporary database in memory for writing during execution (fault tolerance)
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

        :param delete: also delete contents of temporary cache (used for testing)
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

    def get_guids(self) -> List[str]:
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
            return Snapshot(r['d'], timestamp, r['t'], r['e'])

        return Snapshot('', 0, 0, '')

    def get_history_data(self, guid: str, count: Optional[int] = None) -> Dict[str, float]:
        """Return data and timestamp from the last 'count' (None = all) entries matching a 'guid'.

        :param guid: The guid.
        :param count: The maximum number of entries to return; if None return all.

        :returns: A dict (key: value)
            WHERE

            - key is the data;
            - value is the timestamp.
        """
        history: Dict[str, float] = {}
        if count is not None and count < 1:
            return history

        with self.lock:
            rows = self._execute(
                'SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? ORDER BY timestamp DESC', (guid,)
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

    def get_rich_history_data(self, guid: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return all data from the last 'count' (None = all) entries matching a 'guid'.

        :param guid: The guid.
        :param count: The maximum number of entries to return; if None return all.

        :returns: A list of dicts
            WHERE the keys are:

            - timestamp: The timestamp (float);
            - data: The data (str);
            - tries (optional): The number of tries (int);
            - etag (optional): The ETag (str, could be empty).
        """
        history: List[Dict[str, Any]] = []
        if count is not None and count < 1:
            return history

        with self.lock:
            rows = self._execute(
                'SELECT msgpack_data, timestamp FROM webchanges WHERE uuid = ? ORDER BY timestamp DESC', (guid,)
            ).fetchall()
        if rows:
            for msgpack_data, timestamp in rows:
                r = msgpack.unpackb(msgpack_data)
                history.append(
                    {
                        'timestamp': timestamp,
                        'data': r['d'],
                        'tries': r['t'],
                        'etag': r['e'],
                    }
                )
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

        :param guid: The guid.
        :param data: The data.
        :param timestamp: The timestamp.
        :param tries: The number of tries.
        :param etag: The ETag (could be empty string).
        :param temporary: If true, saved to temporary database (default).
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

        :param guid: The guid.
        """
        with self.lock:
            self._execute('DELETE FROM webchanges WHERE uuid = ?', (guid,))
            self.db.commit()

    def delete_latest(self, guid: str, delete_entries: int = 1) -> int:
        """For the given 'guid', delete the latest 'delete_entries' number of entries and keep all other (older) ones.

        :param guid: The guid.
        :param delete_entries: The number of most recent entries to delete.

        :returns: Number of records deleted.
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
                '    LIMIT -1 OFFSET ? '
                ')',
                (guid, keep_entries),
            )
            num_del: int = self._execute('SELECT changes()').fetchone()[0]
            self.db.commit()
            self._execute('VACUUM')
        return num_del

    def clean_all(self) -> int:
        """Delete all older entries for each 'guid' (keep only last one).

        :returns: Number of records deleted.
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

    def rollback(self, timestamp: float) -> int:
        """Rollback database to the entries present at timestamp.

        :param timestamp: The timestamp.

        :returns: Number of records deleted.
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

    def migrate_from_minidb(self, minidb_filename: Union[str, Path]) -> None:
        """Migrate the data of a legacy minidb database to the current database.

        :param minidb_filename: The filename of the legacy minidb database.
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

    def flushdb(self) -> None:
        """Delete all entries of the database.  Use with care, there is no undo!"""
        with self.lock:
            self._execute('DELETE FROM webchanges')
            self.db.commit()


class CacheRedisStorage(CacheStorage):
    """Class for storing snapshots using redis."""

    def __init__(self, filename: Union[str, Path]) -> None:
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
        for guid in self.db.keys('guid:*'):
            guids.append(guid.decode()[5:])
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
        if count is not None and count < 1:
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

    def get_rich_history_data(self, guid: str, count: Optional[int] = None) -> List[Dict[str, Any]]:
        if count is not None and count < 1:
            return []
        else:
            data, timestamp, tries, etag = self.load(guid)
            return [{'timestamp': timestamp, 'data': data}] if data and timestamp else []

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

    def delete_latest(self, guid: str, delete_entries: int = 1) -> int:
        """For the given 'guid', delete the latest 'delete_entries' entry and keep all other (older) ones.

        :param guid: The guid.
        :param delete_entries: The number of most recent entries to delete (only 1 is supported by this Redis code).

        :returns: Number of records deleted.
        """
        if delete_entries != 1:
            raise NotImplementedError('Only deleting of the latest 1 entry is supported by this Redis code.')

        if self.db.lpop(self._make_key(guid)) is None:  # type: ignore[no-untyped-call]
            return 0

        return 1

    def clean(self, guid: str, keep_entries: int = 1) -> int:
        if keep_entries != 1:
            raise NotImplementedError('Only keeping latest 1 entry is supported by this Redis code.')

        key = self._make_key(guid)
        i = self.db.llen(key)
        if self.db.ltrim(key, 0, 0):
            return i - self.db.llen(key)

        return 0

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("Rolling back the database is not supported by 'redis' database engine")

    def flushdb(self) -> None:
        """Delete all entries of the database.  Use with care, there is no undo!"""
        self.db.flushdb()
