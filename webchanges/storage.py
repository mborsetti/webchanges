"""Handles all storage: jobs files, config files, hooks file, and cache database engines."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import copy
import inspect
import io
import logging
import os
import shutil
import sqlite3
import sys
import threading
import warnings
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime  # py311 use UTC instead of timezone.utc
from datetime import timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal, TextIO, TypedDict

import msgpack
import yaml
import yaml.scanner

from webchanges import __docs_url__, __project_name__, __version__
from webchanges.filters import FilterBase
from webchanges.handler import ErrorData, Snapshot
from webchanges.jobs import JobBase, ShellJob
from webchanges.reporters import ReporterBase
from webchanges.util import edit_file, file_ownership_checks

try:
    from httpx import Headers
except ImportError:  # pragma: no cover
    from webchanges._vendored.headers import Headers  # type: ignore[assignment]

try:
    from types import NoneType
except ImportError:  # pragma: no cover # Python 3.9
    NoneType = type(None)  # type: ignore[assignment,misc]

try:
    import redis
except ImportError as e:  # pragma: no cover
    redis = str(e)  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_ConfigDisplay = TypedDict(
    '_ConfigDisplay',
    {
        'new': bool,
        'error': bool,
        'unchanged': bool,
        'empty-diff': bool,
    },
)
_ConfigReportText = TypedDict(
    '_ConfigReportText',
    {
        'line_length': int,
        'details': bool,
        'footer': bool,
        'minimal': bool,
        'separate': bool,
    },
)
_ConfigReportHtml = TypedDict(
    '_ConfigReportHtml',
    {
        'diff': Literal['unified', 'table'],
        'footer': bool,
        'separate': bool,
        'title': str,
    },
)
_ConfigReportMarkdown = TypedDict(
    '_ConfigReportMarkdown',
    {
        'details': bool,
        'footer': bool,
        'minimal': bool,
        'separate': bool,
    },
)
_ConfigReportStdout = TypedDict(
    '_ConfigReportStdout',
    {
        'enabled': bool,
        'color': bool,
    },
)
_ConfigReportBrowser = TypedDict(
    '_ConfigReportBrowser',
    {
        'enabled': bool,
    },
)
_ConfigReportDiscord = TypedDict(
    '_ConfigReportDiscord',
    {
        'enabled': bool,
        'webhook_url': str,
        'embed': bool,
        'subject': str,
        'colored': bool,
        'max_message_length': int | None,
    },
)
_ConfigReportEmailSmtp = TypedDict(
    '_ConfigReportEmailSmtp',
    {
        'host': str,
        'user': str,
        'port': int,
        'starttls': bool,
        'auth': bool,
        'insecure_password': str,
    },
)
_ConfigReportEmailSendmail = TypedDict(
    '_ConfigReportEmailSendmail',
    {
        'path': str | Path,
    },
)
_ConfigReportEmail = TypedDict(
    '_ConfigReportEmail',
    {
        'enabled': bool,
        'html': bool,
        'to': str,
        'from': str,
        'subject': str,
        'method': Literal['sendmail', 'smtp'],
        'smtp': _ConfigReportEmailSmtp,
        'sendmail': _ConfigReportEmailSendmail,
    },
)
_ConfigReportGotify = TypedDict(
    '_ConfigReportGotify',
    {
        'enabled': bool,
        'priority': int,
        'server_url': str,
        'title': str,
        'token': str,
    },
)
_ConfigReportIfttt = TypedDict(
    '_ConfigReportIfttt',
    {
        'enabled': bool,
        'key': str,
        'event': str,
    },
)
_ConfigReportMailgun = TypedDict(
    '_ConfigReportMailgun',
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
_ConfigReportMatrix = TypedDict(
    '_ConfigReportMatrix',
    {
        'enabled': bool,
        'homeserver': str,
        'access_token': str,
        'room_id': str,
    },
)
_ConfigReportProwl = TypedDict(
    '_ConfigReportProwl',
    {
        'enabled': bool,
        'api_key': str,
        'priority': int,
        'application': str,
        'subject': str,
    },
)
_ConfigReportPushbullet = TypedDict(
    '_ConfigReportPushbullet',
    {
        'enabled': bool,
        'api_key': str,
    },
)
_ConfigReportPushover = TypedDict(
    '_ConfigReportPushover',
    {
        'enabled': bool,
        'app': str,
        'device': str | None,
        'sound': str,
        'user': str,
        'priority': str,
    },
)
_ConfigReportRunCommand = TypedDict(
    '_ConfigReportRunCommand',
    {
        'enabled': bool,
        'command': str,
    },
)
_ConfigReportTelegram = TypedDict(
    '_ConfigReportTelegram',
    {
        'enabled': bool,
        'bot_token': str,
        'chat_id': str | int | list[str | int],
        'silent': bool,
    },
)
_ConfigReportWebhook = TypedDict(
    '_ConfigReportWebhook',
    {
        'enabled': bool,
        'markdown': bool,
        'webhook_url': str,
        'rich_text': bool | None,
        'max_message_length': int | None,
    },
)
_ConfigReportXmpp = TypedDict(
    '_ConfigReportXmpp',
    {
        'enabled': bool,
        'sender': str,
        'recipient': str,
        'insecure_password': str | None,
    },
)

_ConfigReport = TypedDict(
    '_ConfigReport',
    {
        'tz': str | None,
        'text': _ConfigReportText,
        'html': _ConfigReportHtml,
        'markdown': _ConfigReportMarkdown,
        'stdout': _ConfigReportStdout,
        'browser': _ConfigReportBrowser,
        'discord': _ConfigReportDiscord,
        'email': _ConfigReportEmail,
        'gotify': _ConfigReportGotify,
        'ifttt': _ConfigReportIfttt,
        'mailgun': _ConfigReportMailgun,
        'matrix': _ConfigReportMatrix,
        'prowl': _ConfigReportProwl,
        'pushbullet': _ConfigReportPushbullet,
        'pushover': _ConfigReportPushover,
        'run_command': _ConfigReportRunCommand,
        'telegram': _ConfigReportTelegram,
        'webhook': _ConfigReportWebhook,
        'xmpp': _ConfigReportXmpp,
    },
)
_ConfigJobDefaults = TypedDict(
    '_ConfigJobDefaults',
    {
        '_note': str,
        'all': dict[str, Any],
        'url': dict[str, Any],
        'browser': dict[str, Any],
        'command': dict[str, Any],
    },
    total=False,
)
_ConfigDifferDefaults = TypedDict(
    '_ConfigDifferDefaults',
    {
        '_note': str,
        'unified': dict[str, Any],
        'ai_google': dict[str, Any],
        'command': dict[str, Any],
        'deepdiff': dict[str, Any],
        'image': dict[str, Any],
        'table': dict[str, Any],
        'wdiff': dict[str, Any],
    },
    total=False,
)
_ConfigDatabase = TypedDict(
    '_ConfigDatabase',
    {
        'engine': Literal['sqlite3', 'redis', 'minidb', 'textfiles'] | str,
        'max_snapshots': int,
    },
)
_Config = TypedDict(
    '_Config',
    {
        'display': _ConfigDisplay,
        'report': _ConfigReport,
        'job_defaults': _ConfigJobDefaults,
        'differ_defaults': _ConfigDifferDefaults,
        'database': _ConfigDatabase,
        'footnote': str | None,
    },
)

DEFAULT_CONFIG: _Config = {
    'display': {  # select whether the report include the categories below
        'new': True,
        'error': True,
        'unchanged': False,
        'empty-diff': False,
    },
    'report': {
        'tz': None,  # the timezone as a IANA time zone name, e.g. 'America/Los_Angeles', or null for machine's
        # the directives below are for the report content types (text, html or markdown)
        'text': {
            'details': True,  # whether the diff is sent
            'footer': True,
            'line_length': 75,
            'minimal': False,
            'separate': False,
        },
        'html': {
            'diff': 'unified',  # 'unified' or 'table'
            'footer': True,
            'separate': False,
            'title': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
        },
        'markdown': {
            'details': True,  # whether the diff is sent
            'footer': True,
            'minimal': False,
            'separate': False,
        },
        # the directives below control 'reporters', i.e. where a report is displayed and/or sent
        'stdout': {  # the console / command line display; uses text
            'enabled': True,
            'color': True,
        },
        'browser': {  # the system's default browser; uses html
            'enabled': False,
        },
        'discord': {
            'enabled': False,
            'webhook_url': '',
            'embed': True,
            'subject': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
            'colored': True,
            'max_message_length': None,
        },
        'email': {  # email (except mailgun); uses text or both html and text if 'html' is set to true
            'enabled': False,
            'html': True,
            'from': '',
            'to': '',
            'subject': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
            'method': 'smtp',  # either 'smtp' or 'sendmail'
            'smtp': {
                'host': 'localhost',
                'port': 25,
                'starttls': True,
                'auth': True,
                'user': '',
                'insecure_password': '',
            },
            'sendmail': {
                'path': 'sendmail',
            },
        },
        'gotify': {  # uses markdown
            'enabled': False,
            'priority': 0,
            'server_url': '',
            'title': '',
            'token': '',
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
            'subject': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
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
            'subject': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
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
        'telegram': {  # uses markdown (from version 3.7)
            'enabled': False,
            'bot_token': '',
            'chat_id': '',
            'silent': False,
        },
        'webhook': {
            'enabled': False,
            'webhook_url': '',
            'markdown': False,
            'rich_text': None,
            'max_message_length': None,
        },
        'xmpp': {  # uses text
            'enabled': False,
            'sender': '',
            'recipient': '',
            'insecure_password': '',
        },
    },
    'job_defaults': {
        '_note': 'Default directives that are applied to jobs.',
        'all': {'_note': 'These are used for all type of jobs, including those in hooks.py.'},
        'url': {'_note': "These are used for 'url' jobs without 'use_browser'."},
        'browser': {'_note': "These are used for 'url' jobs with 'use_browser: true'."},
        'command': {'_note': "These are used for 'command' jobs."},
    },
    'differ_defaults': {
        '_note': 'Default directives that are applied to individual differs.',
        'unified': {},
        'ai_google': {},
        'command': {},
        'deepdiff': {},
        'image': {},
        'table': {},
        'wdiff': {},
    },
    'database': {
        'engine': 'sqlite3',
        'max_snapshots': 4,
    },
    'footnote': None,
}


# Custom YAML constructor for !include
def yaml_include(loader: yaml.SafeLoader, node: yaml.Node) -> list[Any]:
    file_path = Path(loader.name).parent.joinpath(node.value)
    with file_path.open('r') as f:
        return list(yaml.safe_load_all(f))


# Add the custom constructor to the YAML loader
yaml.add_constructor('!include', yaml_include, Loader=yaml.SafeLoader)


@dataclass
class BaseStorage(ABC):
    """Base class for storage."""


class BaseFileStorage(BaseStorage, ABC):
    """Base class for file storage."""

    def __init__(self, filename: str | Path) -> None:
        """

        :param filename: The filename or directory name to storage.
        """
        if isinstance(filename, str):
            self.filename = Path(filename)
        else:
            self.filename = filename


class BaseTextualFileStorage(BaseFileStorage, ABC):
    """Base class for textual files."""

    def __init__(self, filename: str | Path) -> None:
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
    def parse(cls, filename: Path) -> Any:
        """Parse storage contents.

        :param filename: The filename.
        :return: Specified by the subclass.
        """
        pass

    def edit(self) -> int:
        """Edit file.

        :returns: None if edit is successful, 1 otherwise.
        """
        # Similar code to UrlwatchCommand.edit_hooks()
        logger.debug(f'Edit file {self.filename}')
        if isinstance(self.filename, list):
            if len(self.filename) > 1:
                raise ValueError(f'Only one jobs file can be specified for editing; found {len(self.filename)}.')
            filename = self.filename[0]
        else:
            filename = self.filename
        file_edit = filename.with_stem(filename.stem + '_edit')

        if filename.is_file():
            shutil.copy(filename, file_edit)
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
                print('Errors in updating file:')
                print('======')
                print(e)
                print('======')
                print('')
                print(f'The file {filename} was NOT updated.')
                user_input = input('Do you want to retry the same edit? [Y/n] ')
                if not user_input or user_input.lower().startswith('y'):
                    continue
                file_edit.unlink()
                print('No changes have been saved.')
                return 1

        if filename.is_symlink():
            filename.write_text(file_edit.read_text())
        else:
            file_edit.replace(filename)
        file_edit.unlink(missing_ok=True)
        print('Saved edits in', filename)
        return 0


class JobsBaseFileStorage(BaseTextualFileStorage, ABC):
    """Class for jobs textual files storage."""

    filename: list[Path]  # type: ignore[assignment]

    def __init__(self, filename: list[Path]) -> None:
        """

        :param filename: The filenames of the jobs file.
        """
        super().__init__(filename)  # type: ignore[arg-type]
        self.filename = filename

    def load_secure(self) -> list[JobBase]:
        """Load the jobs from a text file checking that the file is secure (i.e. belongs to the current UID and only
        the owner can write to it - Linux only).

        :return: List of JobBase objects.
        """
        jobs: list[JobBase] = self.load()

        def is_shell_job(job: JobBase) -> bool:
            """Check if the job uses filter 'shellpipe' or an external differ, as they call
            subprocess.run(shell=True) (insecure).

            :returns: True if subprocess.run(shell=True) is invoked by job, False otherwise.
            """
            if isinstance(job, ShellJob):
                return True

            for filter_kind, _ in FilterBase.normalize_filter_list(job.filters, job.index_number):
                if filter_kind == 'shellpipe':
                    return True

                if job.differ and job.differ.get('name') == 'command':
                    return True

            return False

        shelljob_errors = []
        for file in self.filename:
            shelljob_errors.extend(file_ownership_checks(file))
        removed_jobs = (job for job in jobs if is_shell_job(job))
        if shelljob_errors and any(removed_jobs):
            print(
                f'ERROR: Removing the following jobs because '
                f" {' and '.join(shelljob_errors)}: {' ,'.join(str(job.index_number) for job in removed_jobs)}\n"
                f'(see {__docs_url__}en/stable/jobs.html#important-note-for-command-jobs).'
            )
            jobs = [job for job in jobs if job not in removed_jobs]

        logger.info(f"Loaded {len(jobs)} jobs from {', '.join(str(file) for file in self.filename)}.")
        return jobs


class BaseYamlFileStorage(BaseTextualFileStorage, ABC):
    """Base class for YAML textual files storage."""

    @classmethod
    def parse(cls, filename: Path) -> Any:
        """Return contents of YAML file if it exists

        :param filename: The filename Path.
        :return: Specified by the subclass.
        """
        if filename is not None and filename.is_file():
            with filename.open() as fp:
                return yaml.safe_load(fp)


class YamlConfigStorage(BaseYamlFileStorage):
    """Class for configuration file (is a YAML textual file)."""

    config: _Config = {}  # type: ignore[typeddict-item]

    @staticmethod
    def dict_deep_difference(d1: _Config, d2: _Config, ignore_underline_keys: bool = False) -> _Config:
        """Recursively find elements in the first dict that are not in the second.

        :param d1: The first dict.
        :param d2: The second dict.
        :param ignore_underline_keys: If true, keys starting with _ are ignored (treated as remarks)
        :return: A dict with all the elements on the first dict that are not in the second.
        """

        def _sub_dict_deep_difference(d1_: _Config, d2_: _Config) -> _Config:
            """Recursive sub-function to find elements in the first dict that are not in the second.

            :param d1_: The first dict.
            :param d2_: The second dict.
            :return: A dict with elements on the first dict that are not in the second.
            """
            for key, value in d1_.copy().items():
                if ignore_underline_keys and key.startswith('_'):
                    d1_.pop(key, None)  # type: ignore[misc]
                elif isinstance(value, dict) and isinstance(d2_.get(key), dict):
                    _sub_dict_deep_difference(value, d2_[key])  # type: ignore[arg-type,literal-required]
                    if not len(value):
                        d1_.pop(key)  # type: ignore[misc]
                else:
                    if key in d2_:
                        d1_.pop(key)  # type: ignore[misc]
            return d1_

        return _sub_dict_deep_difference(copy.deepcopy(d1), d2)

    @staticmethod
    def dict_deep_merge(source: _Config, destination: _Config) -> _Config:
        """Recursively deep merges source dict into destination dict.

        :param source: The first dict.
        :param destination: The second dict.
        :return: The deep merged dict.
        """

        # https://stackoverflow.com/a/20666342

        def _sub_dict_deep_merge(source_: _Config, destination_: _Config) -> _Config:
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

    def check_for_unrecognized_keys(self, config: _Config) -> None:
        """Test if config has keys not in DEFAULT_CONFIG (bad keys, e.g. typos); if so, raise ValueError.

        :param config: The configuration.
        :raises ValueError: If the configuration has keys not in DEFAULT_CONFIG (bad keys, e.g. typos)
        """
        config_for_extras = copy.deepcopy(config)
        if 'job_defaults' in config_for_extras:
            # Create missing 'job_defaults' keys from DEFAULT_CONFIG
            for key in DEFAULT_CONFIG['job_defaults']:
                if 'job_defaults' not in config_for_extras:
                    config_for_extras['job_defaults'] = {}
                config_for_extras['job_defaults'][key] = None  # type: ignore[literal-required]
            for key in DEFAULT_CONFIG['differ_defaults']:
                if 'differ_defaults' not in config_for_extras:
                    config_for_extras['differ_defaults'] = {}
                config_for_extras['differ_defaults'][key] = None  # type: ignore[literal-required]
        if 'hooks' in sys.modules:
            # Remove extra keys in config used in hooks (they are not in DEFAULT_CONFIG)
            for _, obj in inspect.getmembers(
                sys.modules['hooks'], lambda x: inspect.isclass(x) and x.__module__ == 'hooks'
            ):
                if issubclass(obj, JobBase):
                    if obj.__kind__ not in DEFAULT_CONFIG['job_defaults'].keys():
                        config_for_extras['job_defaults'].pop(obj.__kind__, None)  # type: ignore[misc]
                    elif obj.__kind__ not in DEFAULT_CONFIG['job_defaults'].keys():
                        config_for_extras['job_defaults'].pop(obj.__kind__, None)  # type: ignore[misc]
                elif issubclass(obj, ReporterBase):
                    if obj.__kind__ not in DEFAULT_CONFIG['report'].keys():
                        config_for_extras['report'].pop(obj.__kind__, None)  # type: ignore[misc]
        if 'slack' in config_for_extras.get('report', {}):
            # Ignore legacy key
            config_for_extras['report'].pop('slack')  # type: ignore[typeddict-item]
        extras: _Config = self.dict_deep_difference(config_for_extras, DEFAULT_CONFIG, ignore_underline_keys=True)
        if not extras.get('report'):
            extras.pop('report', None)  # type: ignore[misc]
        if extras:
            warnings.warn(
                f'Found unrecognized directive(s) in the configuration file {self.filename}:\n'
                f'{yaml.safe_dump(extras)}Check for typos or the hooks.py file (if any); documentation is at '
                f'{__docs_url__}\n',
                RuntimeWarning,
            )

    @staticmethod
    def replace_none_keys(config: _Config) -> None:
        """Fixes None keys in loaded config that should be empty dicts instead."""
        if 'job_defaults' not in config:
            config['job_defaults'] = DEFAULT_CONFIG['job_defaults']
        else:
            if 'shell' in config['job_defaults']:
                if 'command' in config['job_defaults']:
                    raise KeyError(
                        "Found both 'shell' and 'command' job_defaults in config, a duplicate. Please remove 'shell' "
                        'ones.'
                    )
                else:
                    config['job_defaults']['command'] = config[  # pyright: ignore[reportGeneralTypeIssues]
                        'job_defaults'
                    ].pop(
                        'shell'  # type: ignore[typeddict-item]
                    )
            for key in {'all', 'url', 'browser', 'command'}:
                if key not in config['job_defaults']:
                    config['job_defaults'][key] = {}  # type: ignore[literal-required]
                elif config['job_defaults'][key] is None:  # type: ignore[literal-required]
                    config['job_defaults'][key] = {}  # type: ignore[literal-required]

    def load(self, *args: Any) -> None:
        """Load configuration file from self.filename into self.config adding missing keys from DEFAULT_CONFIG.

        :param args: None used.
        """
        config: _Config = self.parse(self.filename)

        if config:
            self.replace_none_keys(config)
            self.check_for_unrecognized_keys(config)

            # If config is missing keys in DEFAULT_CONFIG, log the missing keys and deep merge DEFAULT_CONFIG
            missing = self.dict_deep_difference(DEFAULT_CONFIG, config, ignore_underline_keys=True)
            if missing:
                logger.info(
                    f'The configuration file {self.filename} is missing directive(s); the following default '
                    f'values are being used:\n'
                    f'{yaml.safe_dump(missing)}'
                    f'See documentation at {__docs_url__}en/stable/configuration.html'
                )
                config = self.dict_deep_merge(config or {}, DEFAULT_CONFIG)

            # format headers
            for job_defaults_type in {'all', 'url', 'browser'}:
                if 'headers' in config['job_defaults'][job_defaults_type]:  # type: ignore[literal-required]
                    config['job_defaults'][job_defaults_type]['headers'] = Headers(  # type: ignore[literal-required]
                        {
                            k: str(v)
                            for k, v in config['job_defaults'][job_defaults_type][  # type: ignore[literal-required]
                                'headers'
                            ].items()
                        },
                        encoding='utf-8',
                    )
                if 'cookies' in config['job_defaults'][job_defaults_type]:  # type: ignore[literal-required]
                    config['job_defaults'][job_defaults_type]['cookies'] = {  # type: ignore[literal-required]
                        k: str(v)
                        for k, v in config['job_defaults'][job_defaults_type][  # type: ignore[literal-required]
                            'cookies'
                        ].items()
                    }
            logger.info(f'Loaded configuration from {self.filename}')

        else:
            logger.warning(f'No directives found in the configuration file {self.filename}; using default directives.')
            config = DEFAULT_CONFIG

        self.config = config

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save self.config into self.filename using YAML.

        :param args: None used.
        :param kwargs: None used.
        """
        with self.filename.open('w') as fp:
            fp.write(
                f'# {__project_name__} configuration file. See {__docs_url__}en/stable/configuration.html\n'
                f'# Originally written on {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}Z by version'
                f' {__version__}.\n'
                f'\n'
            )
            yaml.safe_dump(self.config, fp, allow_unicode=True, sort_keys=False)

    @classmethod
    def write_default_config(cls, filename: Path) -> None:
        """Write default configuration to file.

        :param filename: The filename.
        """
        config_storage = cls(filename)
        config_storage.config = DEFAULT_CONFIG
        config_storage.save()


class YamlJobsStorage(BaseYamlFileStorage, JobsBaseFileStorage):
    """Class for jobs file (is a YAML textual file)."""

    @classmethod
    def _parse(cls, fp: TextIO, filenames: list[Path]) -> list[JobBase]:
        """Parse the contents of a jobs YAML file.

        :param fp: The text stream to parse.
        :return: A list of JobBase objects.
        :raise yaml.YAMLError: If a YAML error is found in the file.
        :raise ValueError: If a duplicate URL/command is found in the list.
        """

        def job_files_for_error() -> list[str]:
            """
            :return: A list of line containing the names of the job files.
            """
            if len(filenames) > 1:
                jobs_files = ['in the concatenation of the jobs files:'] + [f'• {file},' for file in filenames]
            elif len(filenames) == 1:
                jobs_files = [f'in jobs file {filenames[0]}.']
            else:
                jobs_files = []
            return jobs_files

        jobs = []
        jobs_by_guid = defaultdict(list)
        try:
            for i, job_data in enumerate((job for job in yaml.safe_load_all(fp) if job)):
                if not isinstance(job_data, dict):
                    raise ValueError(
                        '\n   '.join(
                            [f'Found invalid job data (consisting of the {type(job_data).__name__} {job_data})']
                            + job_files_for_error()
                        )
                    )
                job_data['index_number'] = i + 1
                job = JobBase.unserialize(job_data, filenames)
                # TODO Implement 100% validation and remove it from jobs.py
                # TODO Try using pydantic to do this.
                if not isinstance(job.data, (NoneType, str, dict, list)):
                    raise ValueError(
                        '\n   '.join(
                            [
                                f"The 'data' key needs to contain a string, a dictionary or a list; found a"
                                f' {type(job.data).__name__} ',
                                f'in {job.get_indexed_location()}',
                            ]
                            + job_files_for_error()
                        )
                    )
                if not isinstance(job.filters, (NoneType, list)):
                    raise ValueError(
                        '\n   '.join(
                            [
                                f"The 'filter' key needs to contain a list; found a {type(job.filters).__name__} ",
                                f'in {job.get_indexed_location()}',
                            ]
                            + job_files_for_error()
                        )
                    )
                if not isinstance(job.headers, (NoneType, dict, Headers)):
                    raise ValueError(
                        '\n   '.join(
                            [
                                f"The 'headers' key needs to contain a dictionary; found a "
                                f'{type(job.headers).__name__} ',
                                f'in {job.get_indexed_location()})',
                            ]
                            + job_files_for_error()
                        )
                    )
                if not isinstance(job.cookies, (NoneType, dict)):
                    raise ValueError(
                        '\n   '.join(
                            [
                                f"The 'cookies' key needs to contain a dictionary; found a "
                                f'{type(job.headers).__name__} ',
                                f'in {job.get_indexed_location()})',
                            ]
                            + job_files_for_error()
                        )
                    )
                if not isinstance(job.switches, (NoneType, str, list)):
                    raise ValueError(
                        '\n   '.join(
                            [
                                f"The 'switches' key needs to contain a string or a list; found a "
                                f'{type(job.switches).__name__} ',
                                f'in {job.get_indexed_location()}',
                            ]
                            + job_files_for_error()
                        )
                    )
                # We add GUID here to speed things up and to allow hooks to programmatically change job.url and/or
                # job.user_visible_url
                job.guid = job.get_guid()
                jobs.append(job)
                jobs_by_guid[job.guid].append(job)
        except yaml.scanner.ScannerError as e:
            raise ValueError(
                '\n   '.join(
                    [
                        f"YAML parser {e.args[2].replace('here', '')} in line {e.args[3].line + 1}, column"
                        f' {e.args[3].column + 1}'
                    ]
                    + job_files_for_error()
                )
            ) from None

        conflicting_jobs = []
        for guid, guid_jobs in jobs_by_guid.items():
            if len(guid_jobs) != 1:
                conflicting_jobs.append(guid_jobs[0].get_location())

        if conflicting_jobs:
            raise ValueError(
                '\n   '.join(
                    ['Each job must have a unique URL/command (for URLs, append #1, #2, etc. to make them unique):']
                    + [f'• {job}' for job in conflicting_jobs]
                    + ['']
                    + job_files_for_error()
                )
            ) from None

        return jobs

    @classmethod
    def parse(cls, filename: Path) -> list[JobBase]:
        """Parse the contents of a jobs YAML file and return a list of jobs.

        :param filename: The filename Path.
        :return: A list of JobBase objects.
        """
        if filename is not None and filename.is_file():
            with filename.open() as fp:
                return cls._parse(fp, [filename])
        return []

    def load(self, *args: Any) -> list[JobBase]:
        """Parse the contents of the jobs YAML file(s) and return a list of jobs.

        :return: A list of JobBase objects.
        """
        if len(self.filename) == 1:
            with self.filename[0].open() as f:
                return self._parse(f, self.filename)
        else:
            fp = io.StringIO('\n---\n'.join(f.read_text(encoding='utf-8-sig') for f in self.filename if f.is_file()))
            return self._parse(fp, self.filename)

    def save(self, jobs: Iterable[JobBase]) -> None:
        """Save jobs to the job YAML file.

        :param jobs: An iterable of JobBase objects to be written.
        """
        print(f'Saving updated list to {self.filename[0]}.')

        with self.filename[0].open('w') as fp:
            yaml.safe_dump_all([job.serialize() for job in jobs], fp, allow_unicode=True, sort_keys=False)


class SsdbStorage(BaseFileStorage, ABC):
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
        pass

    @abstractmethod
    def delete_all(self) -> int:
        """Delete all entries; used for testing only.

        :returns: Number of records deleted.
        """
        pass

    @abstractmethod
    def clean(self, guid: str, keep_entries: int = 1) -> int:
        pass

    @abstractmethod
    def move(self, guid: str, new_guid: str) -> int:
        pass

    @abstractmethod
    def rollback(self, timestamp: float) -> int | None:
        pass

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
            count = self.clean_all(keep_entries)  # pyright: ignore[reportAttributeAccessIssue]
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
        pass


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
        else:
            snapshot = self.load(guid)
            return {snapshot.data: snapshot.timestamp} if snapshot.data and snapshot.timestamp else {}

    def get_history_snapshots(self, guid: str, count: int | None = None) -> list[Snapshot]:
        if count is not None and count < 1:
            return []
        else:
            snapshot = self.load(guid)
            return [snapshot] if snapshot.data and snapshot.timestamp else []

    def save(self, *args: Any, guid: str, snapshot: Snapshot, **kwargs: Any) -> None:
        # ETag and mime_type are ignored
        filename = self._get_filename(guid)
        with filename.open('w+') as fp:
            fp.write(str(snapshot.data))
        os.utime(filename, times=(datetime.now().timestamp(), snapshot.timestamp))

    def delete(self, guid: str) -> None:
        filename = self._get_filename(guid)
        filename.unlink(missing_ok=True)
        return

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
        if guid == new_guid:
            return 0
        os.rename(self._get_filename(guid), self._get_filename(new_guid))
        return 1

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("'textfiles' databases cannot be rolled back as new snapshots overwrite old ones")

    def flushdb(self) -> None:
        for file in self.filename.iterdir():
            if file.is_file():
                file.unlink()


class SsdbSQLite3Storage(SsdbStorage):
    """
    Handles storage of the snapshot as a SQLite database in the 'filename' file using Python's built-in sqlite3 module
    and the msgpack package.

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
        """
        :param filename: The full filename of the database file
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
        self.temp_db = sqlite3.connect('', check_same_thread=False)
        self.temp_cur = self.temp_db.cursor()
        self._temp_execute('CREATE TABLE webchanges (uuid TEXT, timestamp REAL, msgpack_data BLOB)')
        self.temp_db.commit()

    def _execute(self, sql: str, args: tuple | None = None) -> sqlite3.Cursor:
        """Execute SQL command on main database"""
        if args is None:
            logger.debug(f"Executing (perm) '{sql}'")
            return self.cur.execute(sql)
        else:
            logger.debug(f"Executing (perm) '{sql}' with {args}")
            return self.cur.execute(sql, args)

    def _temp_execute(self, sql: str, args: tuple | None = None) -> sqlite3.Cursor:
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
                if not r['t']:  # No data is saved when errors are encountered; use get_history_snapshots()
                    if r['d'] not in history:
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
                f'{command} '  # noqa: ignore S608 Possible SQL injection
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

        from webchanges.storage_minidb import SsdbMiniDBStorage

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
        guids = []
        for guid in self.db.keys('guid:*'):
            guids.append(guid[5:].decode())
        return guids

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
        for i in range(0, self.db.llen(key)):
            r = self.db.lindex(key, i)
            c = msgpack.unpackb(r)
            if c['tries'] == 0 or c['tries'] is None:
                if c['data'] not in history:
                    history[c['data']] = c['timestamp']
                    if count is not None and len(history) >= count:
                        break
        return history

    def get_history_snapshots(self, guid: str, count: int | None = None) -> list[Snapshot]:
        if count is not None and count < 1:
            return []

        history: list[Snapshot] = []
        key = self._make_key(guid)
        for i in range(0, self.db.llen(key)):
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
        self.db.rename(key, new_key)  # type: ignore[no-untyped-call]
        return self.db.llen(new_key)

    def rollback(self, timestamp: float) -> None:
        raise NotImplementedError("Rolling back the database is not supported by 'redis' database engine")

    def flushdb(self) -> None:
        """Delete all entries of the database.  Use with care, there is no undo!"""
        self.db.flushdb()
