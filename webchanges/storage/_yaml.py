"""YAML file storage (config and jobs)."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import copy
import inspect
import io
import logging
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from types import NoneType
from typing import TYPE_CHECKING, Any, Sized, TextIO

import yaml
import yaml.scanner

from webchanges import __docs_url__, __project_name__, __version__
from webchanges.jobs import JobBase
from webchanges.reporters import ReporterBase
from webchanges.storage._base import BaseYamlFileStorage, JobsBaseFileStorage
from webchanges.storage._config import DEFAULT_CONFIG, _Config

try:
    from httpx import Headers
except ImportError:  # pragma: no cover
    from webchanges._vendored.headers import Headers


try:
    from typeguard import TypeCheckError, check_type  # ty:ignore[unresolved-import]
except ImportError:
    from webchanges._vendored.typeguard import TypeCheckError, check_type


if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class YamlConfigStorage(BaseYamlFileStorage):
    """Class for configuration file (is a YAML textual file)."""

    config: _Config = {}  # ty:ignore[missing-typed-dict-key]

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
                    d1_.pop(key, None)  # ty:ignore[call-non-callable]
                elif isinstance(value, dict) and isinstance(d2_.get(key), dict):
                    _sub_dict_deep_difference(value, d2_[key])  # ty:ignore[invalid-argument-type, invalid-key]
                    if not len(value):
                        d1_.pop(key)  # ty:ignore[call-non-callable]
                elif key in d2_:
                    d1_.pop(key)  # ty:ignore[call-non-callable]
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
                    node = destination_.setdefault(key, {})  # ty:ignore[no-matching-overload]
                    _sub_dict_deep_merge(value, node)  # ty:ignore[invalid-argument-type]
                else:
                    destination_[key] = value  # ty:ignore[invalid-key]

            return destination_

        return _sub_dict_deep_merge(source, copy.deepcopy(destination))

    @staticmethod
    def remove_deprecated_keys(config: _Config) -> _Config:
        """Remove deprecated keys from config."""
        if 'slack' in config.get('report', {}):
            # Ignore legacy key
            config['report'].pop('slack')  # ty:ignore[invalid-key]
        return config

    def check_for_unrecognized_keys(self, config: _Config) -> None:
        """Test if config has keys not in DEFAULT_CONFIG (bad keys, e.g. typos); if so, raise ValueError. Also cleanup
        deprecated keys in config.

        :param config: The configuration.
        :raises ValueError: If the configuration has keys not in DEFAULT_CONFIG (bad keys, e.g. typos)
        """
        config_for_extras = copy.deepcopy(config)
        if 'job_defaults' in config_for_extras:
            # Create missing 'job_defaults' keys from DEFAULT_CONFIG
            for key in DEFAULT_CONFIG['job_defaults']:
                if 'job_defaults' not in config_for_extras:
                    config_for_extras['job_defaults'] = {}
                config_for_extras['job_defaults'][key] = None  # ty:ignore[invalid-key]
            for key in DEFAULT_CONFIG['differ_defaults']:
                if 'differ_defaults' not in config_for_extras:
                    config_for_extras['differ_defaults'] = {}
                config_for_extras['differ_defaults'][key] = None  # ty:ignore[invalid-key]
        if 'hooks' in sys.modules:
            # Remove extra keys in config used in hooks (they are not in DEFAULT_CONFIG)
            for _, obj in inspect.getmembers(
                sys.modules['hooks'], lambda x: inspect.isclass(x) and x.__module__ == 'hooks'
            ):
                if issubclass(obj, JobBase):
                    if (
                        obj.__kind__ not in DEFAULT_CONFIG['job_defaults']
                        or obj.__kind__ not in DEFAULT_CONFIG['job_defaults']
                    ):
                        config_for_extras['job_defaults'].pop(obj.__kind__, None)
                elif issubclass(obj, ReporterBase) and obj.__kind__ not in DEFAULT_CONFIG['report']:
                    config_for_extras['report'].pop(obj.__kind__, None)  # ty:ignore[call-non-callable]
        extras: _Config = self.dict_deep_difference(config_for_extras, DEFAULT_CONFIG, ignore_underline_keys=True)
        if not extras.get('report'):
            extras.pop('report', None)
        if extras:
            warnings.warn(
                f'Found unrecognized directive(s) in the configuration file {self.filename}:\n'
                f'{yaml.safe_dump(extras)}Check for typos or the hooks.py file (if any); documentation is at '
                f'{__docs_url__}\n',
                RuntimeWarning,
                stacklevel=1,
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
                config['job_defaults']['command'] = config['job_defaults'].pop('shell')  # ty:ignore[invalid-key]
            for key in ('all', 'url', 'browser', 'command'):
                if key not in config['job_defaults'] or config['job_defaults'][key] is None:
                    config['job_defaults'][key] = {}  # ty:ignore[invalid-assignment]

    def load(self, *args: Any) -> None:
        """Load configuration file from self.filename into self.config, adding missing keys from DEFAULT_CONFIG.

        :param args: None used.
        """
        logger.debug(f'Loading configuration from {self.filename}')
        config: _Config = self.parse(self.filename)

        if config:
            self.replace_none_keys(config)

            # Fix change in key spelling
            if 'utf-8' in config.get('report', {}).get('email', {}).get('smtp', {}):
                config['report']['email']['smtp']['utf_8'] = config['report']['email']['smtp'].pop('utf-8')

            config = self.remove_deprecated_keys(config)
            self.check_for_unrecognized_keys(config)

            # If config is missing keys in DEFAULT_CONFIG, log the missing keys and deep merge DEFAULT_CONFIG
            missing = self.dict_deep_difference(DEFAULT_CONFIG, config, ignore_underline_keys=True)
            if missing:
                logger.info(
                    f'The configuration file {self.filename} is missing directive(s); using default value for those. '
                    'Run with -vv or -vvv for more detalis.'
                )
                logger.debug(
                    f'The following default values are being used:\n'
                    f'{yaml.safe_dump(missing)}'
                    f'See documentation at {__docs_url__}en/stable/configuration.html'
                )
                config = self.dict_deep_merge(config or {}, DEFAULT_CONFIG)

            # check for correct type
            try:
                config_no_remarks = self.remove_remark_keys(config)
                check_type(config_no_remarks, _Config)
            except TypeCheckError as exc:
                raise ValueError(f'Found invalid data in configuration file {self.filename} entry:\n{exc})') from None

            # format headers
            for job_defaults_type in ('all', 'url', 'browser'):
                if 'headers' in config['job_defaults'][job_defaults_type]:
                    config['job_defaults'][job_defaults_type]['headers'] = Headers(
                        {k: str(v) for k, v in config['job_defaults'][job_defaults_type]['headers'].items()},
                        encoding='utf-8',
                    )
                if 'cookies' in config['job_defaults'][job_defaults_type]:
                    config['job_defaults'][job_defaults_type]['cookies'] = {
                        k: str(v) for k, v in config['job_defaults'][job_defaults_type]['cookies'].items()
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
                f'# yaml-language-server: $schema=config.schema.json\n'
            )
            yaml.safe_dump(self.config, fp, width=120, allow_unicode=True, sort_keys=False)

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
            """:return: A list of line containing the names of the job files."""
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
                            (
                                f'Found invalid job data in entry {i + 1} (consisting of the {type(job_data).__name__} '
                                f'{job_data})',
                                *job_files_for_error(),
                            )
                        )
                    )
                job_data['index_number'] = i + 1
                job = JobBase.unserialize(job_data, filenames)
                # TODO: Implement 100% validation and remove it from jobs.py
                # TODO: Try using pydantic to do this.
                if not isinstance(job.data, (NoneType, str, dict, list)):
                    raise ValueError(
                        '\n   '.join(
                            (
                                f"The 'data' key needs to contain a string, a dictionary or a list; found a "
                                f'{type(job.data).__name__}',
                                f'in {job.get_indexed_location()}',
                                *job_files_for_error(),
                            )
                        )
                    )
                if not isinstance(job.filters, (NoneType, list)):
                    if isinstance(job.filters, str):  # Backwards compatibility
                        warnings.warn(
                            '\n   '.join(
                                (
                                    f"The 'filters' key should contain a list; found a {type(job.filters).__name__}",
                                    f'in {job.get_indexed_location()}',
                                    *job_files_for_error(),
                                )
                            ),
                            RuntimeWarning,
                            stacklevel=1,
                        )
                        job.filters = [job.filters]
                    else:
                        raise ValueError(
                            '\n   '.join(
                                (
                                    f"The 'filters' key needs to contain a list; found a {type(job.filters).__name__} ",
                                    f'in {job.get_indexed_location()}',
                                    *job_files_for_error(),
                                )
                            )
                        )
                if not isinstance(job.headers, (NoneType, dict, Headers)):
                    raise ValueError(
                        '\n   '.join(
                            (
                                f"The 'headers' key needs to contain a dictionary; found a "
                                f'{type(job.headers).__name__}',
                                f'in {job.get_indexed_location()})',
                                *job_files_for_error(),
                            )
                        )
                    )
                if not isinstance(job.cookies, (NoneType, dict)):
                    raise ValueError(
                        '\n   '.join(
                            (
                                f"The 'cookies' key needs to contain a dictionary; found a "
                                f'{type(job.headers).__name__}',
                                f'in {job.get_indexed_location()})',
                                *job_files_for_error(),
                            )
                        )
                    )
                if not isinstance(job.switches, (NoneType, str, list)):
                    raise ValueError(
                        '\n   '.join(
                            (
                                f"The 'switches' key needs to contain a string or a list; found a "
                                f'{type(job.switches).__name__}',
                                f'in {job.get_indexed_location()}',
                                *job_files_for_error(),
                            )
                        )
                    )
                # We add GUID here to speed things up and to allow hooks to programmatically change job.url and/or
                # job.user_visible_url
                jobs.append(job)
                jobs_by_guid[job.guid].append(job)
        except yaml.scanner.ScannerError as e:
            raise ValueError(
                '\n   '.join(
                    (
                        f'YAML parser {e.args[2].replace("here", "")} in line {e.args[3].line + 1}, column'
                        f' {e.args[3].column + 1}',
                        *job_files_for_error(),
                    )
                )
            ) from None

        conflicting_jobs = [guid_jobs[0].get_location() for _, guid_jobs in jobs_by_guid.items() if len(guid_jobs) != 1]
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

    def save(self, jobs: Sized[JobBase]) -> None:
        """Save jobs to the job YAML file.

        :param jobs: An iterable of JobBase objects to be written.
        """
        print(f'Saving updated list to {self.filename[0]}.')

        with self.filename[0].open('w') as fp:
            for i, job in enumerate(jobs):
                if i:
                    fp.write('---\n')
                fp.write('# yaml-language-server: $schema=jobs.schema.json\n')
                yaml.safe_dump(job.serialize(), fp, width=120, allow_unicode=True, sort_keys=False)
