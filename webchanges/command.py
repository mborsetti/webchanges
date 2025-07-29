"""Take actions from command line arguments."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import difflib
import email.utils
import gc
import importlib.metadata
import logging
import os
import platform
import re
import shutil
import sqlite3
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Iterable, Iterator, TYPE_CHECKING
from urllib.parse import unquote_plus
from zoneinfo import ZoneInfo

from webchanges import __docs_url__, __project_name__, __version__
from webchanges.differs import DifferBase
from webchanges.filters import FilterBase
from webchanges.handler import JobState, Report
from webchanges.jobs import JobBase, NotModifiedError, UrlJob
from webchanges.mailer import smtp_have_password, smtp_set_password, SMTPMailer
from webchanges.reporters import ReporterBase, xmpp_have_password, xmpp_set_password
from webchanges.util import dur_text, edit_file, import_module_from_source

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]
    print("Required package 'httpx' not found; will attempt to run using 'requests'.")
    try:
        import requests
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            f"A Python HTTP client package (either 'httpx' or 'requests' is required to run {__project_name__}; "
            'neither can be imported.'
        ) from e
if httpx is not None:
    try:
        import h2
    except ImportError:  # pragma: no cover
        h2 = None  # type: ignore[assignment]

if os.name == 'posix':
    try:
        import apt
    except ImportError:  # pragma: no cover
        apt = None  # type: ignore[assignment]

try:
    from pip._internal.metadata import get_default_environment  # pyright: ignore[reportPrivateImportUsage]
except ImportError:  # pragma: no cover
    get_default_environment = None  # type: ignore[assignment]

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None  # type: ignore[assignment]

try:
    import psutil
    from psutil._common import bytes2human  # pyright: ignore[reportPrivateImportUsage]
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]
    bytes2human = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from webchanges.main import Urlwatch
    from webchanges.reporters import _ConfigReportersList
    from webchanges.storage import _ConfigReportEmail, _ConfigReportEmailSmtp, _ConfigReportTelegram, _ConfigReportXmpp


class UrlwatchCommand:
    """The class that runs the program after initialization and CLI arguments parsing."""

    def __init__(self, urlwatcher: Urlwatch) -> None:
        self.urlwatcher = urlwatcher
        self.urlwatch_config = urlwatcher.urlwatch_config

    @staticmethod
    def _exit(arg: str | int | None) -> None:
        logger.info(f'Exiting with exit code {arg}')
        sys.exit(arg)

    def jobs_from_joblist(self) -> Iterator[JobBase]:
        """Generates the jobs to process from the joblist entered in the CLI."""
        if self.urlwatcher.urlwatch_config.joblist:
            jobs = {self._find_job(job_entry) for job_entry in self.urlwatcher.urlwatch_config.joblist}
            enabled_jobs = {job for job in jobs if job.is_enabled()}
            disabled = len(enabled_jobs) - len(jobs)
            disabled_str = f' (excluding {disabled} disabled)' if disabled else ''
            logger.debug(
                f"Processing {len(enabled_jobs)} job{'s' if len(enabled_jobs) else ''}{disabled_str} as specified in "
                f"command line: {', '.join(str(j) for j in self.urlwatcher.urlwatch_config.joblist)}"
            )
        else:
            enabled_jobs = {job for job in self.urlwatcher.jobs if job.is_enabled()}
            disabled = len(enabled_jobs) - len(self.urlwatcher.jobs)
            disabled_str = f' (excluding {disabled} disabled)' if disabled else ''
            logger.debug(f"Processing {len(enabled_jobs)} job{'s' if len(enabled_jobs) else ''}{disabled_str}")
        for job in enabled_jobs:
            yield job.with_defaults(self.urlwatcher.config_storage.config)

    def edit_hooks(self) -> int:
        """Edit hooks file.

        :returns: 0 if edit is successful, 1 otherwise.
        """
        # Similar code to BaseTextualFileStorage.edit()
        for hooks_file in self.urlwatch_config.hooks_files:
            logger.debug(f'Edit file {hooks_file}')
            # Python 3.9: hooks_edit = self.urlwatch_config.hooks.with_stem(self.urlwatch_config.hooks.stem + '_edit')
            hooks_edit = hooks_file.parent.joinpath(hooks_file.stem + '_edit' + ''.join(hooks_file.suffixes))
            if hooks_file.exists():
                shutil.copy(hooks_file, hooks_edit)
            # elif self.urlwatch_config.hooks_py_example is not None and os.path.exists(
            #         self.urlwatch_config.hooks_py_example):
            #     shutil.copy(self.urlwatch_config.hooks_py_example, hooks_edit, follow_symlinks=False)

            while True:
                try:
                    edit_file(hooks_edit)
                    import_module_from_source('hooks', hooks_edit)
                    break  # stop if no exception on parser
                except SystemExit:
                    raise
                except Exception as e:
                    print('Parsing failed:')
                    print('======')
                    print(e)
                    print('======')
                    print('')
                    print(f'The file {hooks_file} was NOT updated.')
                    user_input = input('Do you want to retry the same edit? (Y/n)')
                    if not user_input or user_input.lower()[0] == 'y':
                        continue
                    hooks_edit.unlink()
                    print('No changes have been saved.')
                    return 1

            if hooks_file.is_symlink():
                hooks_file.write_text(hooks_edit.read_text())
            else:
                hooks_edit.replace(hooks_file)
            hooks_edit.unlink(missing_ok=True)
            print(f'Saved edits in {hooks_file}.')

        return 0

    @staticmethod
    def show_features() -> int:
        """
        Prints the "features", i.e. a list of job types, filters and reporters.

        :return: 0.
        """
        print(f'Please see full documentation at {__docs_url__}.')
        print()
        print('Supported jobs:\n')
        print(JobBase.job_documentation())
        print('Supported filters:\n')
        print(FilterBase.filter_documentation())
        print()
        print('Supported differs:\n')
        print(DifferBase.differ_documentation())
        print()
        print('Supported reporters:\n')
        print(ReporterBase.reporter_documentation())
        print()
        print(f'Please see full documentation at {__docs_url__}.')

        return 0

    @staticmethod
    def show_detailed_versions() -> int:
        """
        Prints the detailed versions, including of dependencies.

        :return: 0.
        """

        def dependencies() -> list[str]:
            if get_default_environment is not None:
                env = get_default_environment()
                dist = None
                for dist in env.iter_all_distributions():
                    if dist.canonical_name == __project_name__:
                        break
                if dist and dist.canonical_name == __project_name__:
                    return sorted(set(d.split()[0] for d in dist.metadata_dict['requires_dist']), key=str.lower)

            # default list of all possible dependencies
            logger.info(f'Found no pip distribution for {__project_name__}; returning all possible dependencies.')
            return [
                'aioxmpp',
                'beautifulsoup4',
                'chump',
                'colorama',
                'cryptography',
                'cssbeautifier',
                'cssselect',
                'deepdiff',
                'h2',
                'html2text',
                'httpx',
                'jq',
                'jsbeautifier',
                'keyring',
                'lxml',
                'markdown2',
                'matrix_client',
                'msgpack',
                'pdftotext',
                'Pillow',
                'platformdirs',
                'playwright',
                'psutil',
                'pushbullet.py',
                'pypdf',
                'pytesseract',
                'pyyaml',
                'redis',
                'requests',
                'tzdata',
                'vobject',
            ]

        print('Software:')
        print(f'• {__project_name__}: {__version__}')
        print(
            f'• {platform.python_implementation()}: {platform.python_version()} '
            f'{platform.python_build()} {platform.python_compiler()}'
        )
        print(f'• SQLite: {sqlite3.sqlite_version}')

        if psutil:
            print()
            print('System:')
            print(f'• Platform: {platform.platform()}, {platform.machine()}')
            print(f'• Processor: {platform.processor()}')
            print(f'• CPUs (logical): {psutil.cpu_count()}')
            try:
                virt_mem = psutil.virtual_memory().available
                print(
                    f'• Free memory: {bytes2human(virt_mem)} physical plus '  # pyright: ignore[reportOptionalCall]
                    f'{bytes2human(psutil.swap_memory().free)} swap.'  # pyright: ignore[reportOptionalCall]
                )
            except psutil.Error as e:  # pragma: no cover
                print(f'• Free memory: Could not read information: {e}')
            print(
                f"• Free disk '/': {bytes2human(psutil.disk_usage('/').free)} "  # pyright: ignore[reportOptionalCall]
                f"({100 - psutil.disk_usage('/').percent:.1f}%)"
            )
            executor = ThreadPoolExecutor()
            print(f'• --max-threads default: {executor._max_workers}')

        print()
        print('Installed PyPi dependencies:')
        for module_name in dependencies():
            try:
                mod = importlib.metadata.distribution(module_name)
            except ModuleNotFoundError:
                continue
            print(f'• {module_name}: {mod.version}')
            # package requirements
            if mod.requires:
                for req_name in [i.split()[0] for i in mod.requires]:
                    try:
                        req = importlib.metadata.distribution(req_name)
                    except ModuleNotFoundError:
                        continue
                    print(f'  - {req_name}: {req.version}')

        # playwright
        if sync_playwright is not None:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='chrome')
                print()
                print('Playwright browser:')
                print(f'• Name: {browser.browser_type.name}')
                print(f'• Version: {browser.version}')
                if psutil:
                    browser.new_page()
                    try:
                        virt_mem = psutil.virtual_memory().available
                        print(
                            f'• Free memory with browser loaded: '
                            f'{bytes2human(virt_mem)} physical plus '  # pyright: ignore[reportOptionalCall]
                            f'{bytes2human(psutil.swap_memory().free)} swap'  # pyright: ignore[reportOptionalCall]
                        )
                    except psutil.Error:
                        pass

        if os.name == 'posix' and apt:
            apt_cache = apt.Cache()

            def print_version(libs: list[str]) -> None:
                for lib in libs:
                    if lib in apt_cache:
                        if ver := apt_cache[lib].versions:
                            print(f'   - {ver[0].package}: {ver[0].version}')
                return None

            print()
            print('Installed dpkg dependencies:')
            for module, apt_dists in (
                ('jq', ['jq']),
                # https://github.com/jalan/pdftotext#os-dependencies
                ('pdftotext', ['libpoppler-cpp-dev']),
                # https://pillow.readthedocs.io/en/latest/installation.html#external-libraries
                (
                    'Pillow',
                    [
                        'libjpeg-dev',
                        'zlib-dev',
                        'zlib1g-dev',
                        'libtiff-dev',
                        'libfreetype-dev',
                        'littlecms-dev',
                        'libwebp-dev',
                        'tcl/tk-dev',
                        'openjpeg-dev',
                        'libimagequant-dev',
                        'libraqm-dev',
                        'libxcb-dev',
                        'libxcb1-dev',
                    ],
                ),
                ('playwright', ['google-chrome-stable']),
                # https://tesseract-ocr.github.io/tessdoc/Installation.html
                ('pytesseract', ['tesseract-ocr']),
            ):
                try:
                    importlib.metadata.distribution(module)
                    print(f'• {module}')
                    print_version(apt_dists)
                except importlib.metadata.PackageNotFoundError:
                    pass
        return 0

    def list_jobs(self, regex: bool | str) -> None:
        """
        Lists the job and their respective _index_number.

        :return: None.
        """
        if isinstance(regex, str):
            print(f"List of jobs matching the RegEx '{regex}':")
        else:
            print('List of jobs:')
        for job in self.urlwatcher.jobs:
            if self.urlwatch_config.verbose:
                job_desc = f'{job.index_number:3}: {job!r}'
            else:
                pretty_name = job.pretty_name()
                location = job.get_location()
                if pretty_name != location:
                    job_desc = f'{job.index_number:3}: {pretty_name} ({location})'
                else:
                    job_desc = f'{job.index_number:3}: {pretty_name}'
            if isinstance(regex, bool) or re.findall(regex, job_desc):
                print(job_desc)

        if len(self.urlwatch_config.jobs_files) > 1:
            jobs_files = ['Jobs files concatenated:'] + [f'• {file}' for file in self.urlwatch_config.jobs_files]
        elif len(self.urlwatch_config.jobs_files) == 1:
            jobs_files = [f'Jobs file: {self.urlwatch_config.jobs_files[0]}']
        else:
            jobs_files = []
        print('\n   '.join(jobs_files))

    def _find_job(self, query: str | int) -> JobBase:
        """Finds the job based on a query, which is matched to the job index (also negative) or a job location
        (i.e. the url/user_visible_url or command).

        :param query: The query.
        :return: The matching JobBase.
        :raises IndexError: If job is not found.
        """
        if isinstance(query, int):
            index = query
        else:
            try:
                index = int(query)
            except ValueError:
                query = unquote_plus(query)
                try:
                    return next((job for job in self.urlwatcher.jobs if unquote_plus(job.get_location()) == query))
                except StopIteration:
                    raise ValueError(f"Job {query} does not match any job's url/user_visible_url or command.") from None

        if index == 0:
            raise ValueError(f'Job index {index} out of range.')
        try:
            if index <= 0:
                return self.urlwatcher.jobs[index]
            else:
                return self.urlwatcher.jobs[index - 1]
        except IndexError as e:
            raise ValueError(f'Job index {index} out of range (found {len(self.urlwatcher.jobs)} jobs).') from e

    def _find_job_with_defaults(self, query: str | int) -> JobBase:
        """
        Returns the job with defaults based on job_id, which could match an index or match a location
        (url/user_visible_url or command). Accepts negative numbers.

        :param query: The query.
        :return: The matching JobBase with defaults.
        :raises SystemExit: If job is not found.
        """
        job = self._find_job(query)
        return job.with_defaults(self.urlwatcher.config_storage.config)

    def test_job(self, job_id: bool | str | int) -> None:
        """
        Tests the running of a single job outputting the filtered text to --test-reporter (default is stdout). If
        job_id is True, don't run any jobs but load config, jobs and hook files to trigger any syntax errors.

        :param job_id: The job_id or True.

        :return: None.

        :raises Exception: The Exception when raised by a job. loading of hooks files, etc.
        """
        if job_id is True:  # Load to trigger any eventual syntax errors
            message = [f'No syntax errors in config file {self.urlwatch_config.config_file}']
            conj = ',\n' if 'hooks' in sys.modules else '\nand '
            if len(self.urlwatch_config.jobs_files) == 1:
                message.append(f'{conj}jobs file {self.urlwatch_config.jobs_files[0]},')
            else:
                message.append(
                    '\n   '.join(
                        [f'{conj}jobs files'] + [f'• {file},' for file in sorted(self.urlwatch_config.jobs_files)]
                    )
                )
            if 'hooks' in sys.modules:
                message.append(f"\nand hooks file {sys.modules['hooks'].__file__}")
            print(f"{''.join(message)}.")
            return

        job = self._find_job_with_defaults(job_id)

        if isinstance(job, UrlJob):
            # Force re-retrieval of job, as we're testing filters
            job.ignore_cached = True

        # Add defaults, as if when run
        job = job.with_defaults(self.urlwatcher.config_storage.config)

        with JobState(self.urlwatcher.ssdb_storage, job) as job_state:
            # duration = time.perf_counter() - start
            job_state.process(headless=not self.urlwatch_config.no_headless)
            if job_state.job.name is None:
                job_state.job.name = ''
            # if job_state.job.note is None:
            #     job_state.job.note = ''
            data_info = '\n'.join(
                filter(
                    None,
                    (
                        f'• [GUID: {job_state.job.guid}]',
                        f'• [Media type: {job_state.new_mime_type}]' if job_state.new_mime_type else None,
                        f'• [ETag: {job_state.new_etag}]' if job_state.new_etag else None,
                    ),
                )
            )
            job_state.new_data = f'{data_info}\n\n{str(job_state.new_data)}'
            if self.urlwatch_config.test_reporter is None:
                self.urlwatch_config.test_reporter = 'stdout'  # default
            report = Report(self.urlwatcher)
            report.job_states = []  # required
            errorlevel = self.check_test_reporter(
                job_state,
                label='error' if job_state.exception else 'test',
                report=report,
            )
            if errorlevel:
                self._exit(errorlevel)
        return

        # We do not save the job state or job on purpose here, since we are possibly modifying the job
        # (ignore_cached) and we do not want to store the newly-retrieved data yet (filter testing)

    def prepare_jobs(self) -> None:
        """
        Runs jobs that have no history to populate the snapshot database when they're newly added.
        """
        new_jobs = set()
        for idx, job in enumerate(self.urlwatcher.jobs):
            has_history = bool(self.urlwatcher.ssdb_storage.get_history_snapshots(job.guid))
            if not has_history:
                print(f'Running new {job.get_indexed_location()}.')
                new_jobs.add(idx + 1)
        if not new_jobs and not self.urlwatch_config.joblist:
            print('Found no new jobs to run.')
            return
        self.urlwatcher.urlwatch_config.joblist = set(self.urlwatcher.urlwatch_config.joblist).union(new_jobs)
        self.urlwatcher.run_jobs()
        self.urlwatcher.close()
        return

    def test_differ(self, arg_test_differ: list[str]) -> int:
        """
        Runs diffs for a job on all the saved snapshots and outputs the result to stdout or the reporter selected
        with --test-reporter.

        :param arg_test_differ: Either the job_id or a list containing [job_id, max_diffs]
        :return: 1 if error, 0 if successful.
        """
        report = Report(self.urlwatcher)
        self.urlwatch_config.jobs_files = [Path('--test-differ')]  # for report footer
        if len(arg_test_differ) == 1:
            job_id = arg_test_differ[0]
            max_diffs = None
        elif len(arg_test_differ) == 2:
            job_id, max_diffs_str = arg_test_differ
            max_diffs = int(max_diffs_str)
        else:
            raise ValueError('--test-differ takes a maximum of two arguments')

        job = self._find_job_with_defaults(job_id)

        history_data = self.urlwatcher.ssdb_storage.get_history_snapshots(job.guid)

        num_snapshots = len(history_data)
        if num_snapshots == 0:
            print('This job has never been run before.')
            return 1
        elif num_snapshots < 2:
            print('Not enough historic data available (need at least 2 different snapshots).')
            return 1

        if job.compared_versions and job.compared_versions != 1:
            print(f"Note: The job's 'compared_versions' directive is set to {job.compared_versions}.")

        max_diffs = max_diffs or num_snapshots - 1
        for i in range(max_diffs):
            with JobState(self.urlwatcher.ssdb_storage, job) as job_state:
                job_state.new_data = history_data[i].data
                job_state.new_timestamp = history_data[i].timestamp
                job_state.new_etag = history_data[i].etag
                job_state.new_mime_type = history_data[i].mime_type
                if not job.compared_versions or job.compared_versions == 1:
                    job_state.old_data = history_data[i + 1].data
                    job_state.old_timestamp = history_data[i + 1].timestamp
                    job_state.old_etag = history_data[i + 1].etag
                    job_state.old_mime_type = history_data[i + 1].mime_type
                else:
                    history_dic_snapshots = {s.data: s for s in history_data[i + 1 : i + 1 + job.compared_versions]}
                    close_matches: list[str] = difflib.get_close_matches(
                        str(job_state.new_data), history_dic_snapshots.keys(), n=1  # type: ignore[arg-type]
                    )
                    if close_matches:
                        job_state.old_data = close_matches[0]
                        job_state.old_timestamp = history_dic_snapshots[close_matches[0]].timestamp
                        job_state.old_etag = history_dic_snapshots[close_matches[0]].etag
                        job_state.old_mime_type = history_dic_snapshots[close_matches[0]].mime_type

                if self.urlwatch_config.test_reporter is None:
                    self.urlwatch_config.test_reporter = 'stdout'  # default
                report.job_states = []  # required
                if job_state.new_data == job_state.old_data:
                    label = (
                        f'No change (snapshots {-i:2} AND {-(i + 1):2}) with '
                        f"'compared_versions: {job.compared_versions}'"
                    )
                    job_state.verb = 'changed,no_report'
                else:
                    label = f'Filtered diff (snapshots {-i:2} and {-(i + 1):2})'
                errorlevel = self.check_test_reporter(job_state, label=label, report=report)
                if errorlevel:
                    self._exit(errorlevel)

        # We do not save the job state or job on purpose here, since we are possibly modifying the job
        # (ignore_cached) and we do not want to store the newly-retrieved data yet (filter testing)

        return 0

    def dump_history(self, job_id: str) -> int:
        """
        Displays the historical data stored in the snapshot database for a job.

        :param job_id: The Job ID.
        :return: An argument to be used in sys.exit.
        """

        job = self._find_job_with_defaults(job_id)
        history_data = self.urlwatcher.ssdb_storage.get_history_snapshots(job.guid)

        title = f'History for {job.get_indexed_location()}'
        print(f'{title}\nGUID: {job.guid}')
        if history_data:
            print('=' * max(len(title), 46))
        total_failed = 0
        for i, snapshot in enumerate(history_data):
            mime_type = f' | Media type: {snapshot.mime_type}' if snapshot.mime_type else ''
            etag = f' | ETag: {snapshot.etag}' if snapshot.etag else ''
            tries = f' | Error run (number {snapshot.tries})' if snapshot.tries else ''
            total_failed += snapshot.tries > 0
            tz = self.urlwatcher.report.config['report']['tz']
            tz_info = ZoneInfo(tz) if tz else datetime.now().astimezone().tzinfo  # from machine
            dt = datetime.fromtimestamp(snapshot.timestamp, tz_info)
            header = f'{i + 1}) {email.utils.format_datetime(dt)}{mime_type}{etag}{tries}'
            sep_len = max(50, len(header))
            print(header)
            print('-' * sep_len)
            if snapshot.error_data:
                print(f"{snapshot.error_data.get('type')}: {snapshot.error_data.get('message')}")
                print()
                print('Last good data:')
            print(snapshot.data)
            print('=' * sep_len, '\n')

        print(
            f'Found {len(history_data) - total_failed}'
            + (' good' if total_failed else '')
            + ' snapshot'
            + ('s' if len(history_data) - total_failed != 1 else '')
            + (f' and {total_failed} error capture' + ('s' if total_failed != 1 else '') if total_failed else '')
            + '.'
        )

        return 0

    def list_error_jobs(self) -> int:
        if self.urlwatch_config.errors not in ReporterBase.__subclasses__:
            print(f'Invalid reporter {self.urlwatch_config.errors}.')
            return 1

        def error_jobs_lines(jobs: Iterable[JobBase]) -> Iterator[str]:
            """A generator that outputs error text for jobs who fail with an exception or yield no data.

            Do not use it to test newly modified jobs since it does conditional requests on the websites (i.e. uses
            stored data if the website reports no changes in the data since the last time it downloaded it -- see
            https://developer.mozilla.org/en-US/docs/Web/HTTP/Conditional_requests).
            """

            def job_runner(
                stack: ExitStack,
                jobs: Iterable[JobBase],
                max_workers: int | None = None,
            ) -> Iterator[str]:
                """
                Modified worker.job_runner that yields error text for jobs who fail with an exception or yield no data.

                :param stack: The context manager.
                :param jobs: The jobs to run.
                :param max_workers: The number of maximum workers for ThreadPoolExecutor.
                :return: error text for jobs who fail with an exception or yield no data.
                """
                executor = ThreadPoolExecutor(max_workers=max_workers)

                for job_state in executor.map(
                    lambda jobstate: jobstate.process(headless=not self.urlwatch_config.no_headless),
                    (stack.enter_context(JobState(self.urlwatcher.ssdb_storage, job)) for job in jobs),
                ):
                    if not isinstance(job_state.exception, NotModifiedError):
                        if job_state.exception is None:
                            if (
                                len(job_state.new_data.strip()) == 0
                                if hasattr(job_state, 'new_data')
                                else len(job_state.old_data.strip()) == 0
                            ):
                                if self.urlwatch_config.verbose:
                                    yield f'{job_state.job.index_number:3}: No data: {job_state.job!r}'
                                else:
                                    pretty_name = job_state.job.pretty_name()
                                    location = job_state.job.get_location()
                                    if pretty_name != location:
                                        yield f'{job_state.job.index_number:3}: No data: {pretty_name} ({location})'
                                    else:
                                        yield f'{job_state.job.index_number:3}: No data: {pretty_name}'
                        else:
                            pretty_name = job_state.job.pretty_name()
                            location = job_state.job.get_location()
                            if pretty_name != location:
                                yield (
                                    f'{job_state.job.index_number:3}: Error "{job_state.exception}": {pretty_name} '
                                    f'({location})'
                                )
                            else:
                                yield f'{job_state.job.index_number:3}: Error "{job_state.exception}": {pretty_name})'

            with ExitStack() as stack:
                # This code is from worker.run_jobs, modified to yield from job_runner.
                from webchanges.worker import get_virt_mem  # avoid circular imports

                # run non-BrowserJob jobs first
                jobs_to_run = [job for job in jobs if not job.__is_browser__]
                if jobs_to_run:
                    logger.debug(
                        "Running jobs that do not require Chrome (without 'use_browser: true') in parallel with "
                        "Python's default max_workers."
                    )
                    yield from job_runner(stack, jobs_to_run, self.urlwatch_config.max_workers)
                else:
                    logger.debug("Found no jobs that do not require Chrome (i.e. without 'use_browser: true').")

                # run BrowserJob jobs after
                jobs_to_run = [job for job in jobs if job.__is_browser__]
                if jobs_to_run:
                    gc.collect()
                    virt_mem = get_virt_mem()
                    if self.urlwatch_config.max_workers:
                        max_workers = self.urlwatch_config.max_workers
                    else:
                        max_workers = max(int(virt_mem / 200e6), 1)
                        max_workers = min(max_workers, os.cpu_count() or 1)
                    logger.debug(
                        f"Running jobs that require Chrome (i.e. with 'use_browser: true') in parallel with "
                        f'{max_workers} max_workers.'
                    )
                    yield from job_runner(stack, jobs_to_run, max_workers)
                else:
                    logger.debug("Found no jobs that require Chrome (i.e. with 'use_browser: true').")

        start = time.perf_counter()

        # default max_workers (when not specified) to 1
        if self.urlwatch_config.max_workers is None:
            self.urlwatch_config.max_workers = 1

        if len(self.urlwatch_config.jobs_files) == 1:
            jobs_files = [f'in jobs file {self.urlwatch_config.jobs_files[0]}:']
        else:
            jobs_files = ['in the concatenation of the jobs files'] + [
                f'• {file},' for file in self.urlwatch_config.jobs_files
            ]
        header = '\n   '.join(['Jobs with errors or returning no data (after unmodified filters, if any)'] + jobs_files)

        jobs = {
            job.with_defaults(self.urlwatcher.config_storage.config) for job in self.urlwatcher.jobs if job.is_enabled()
        }
        if self.urlwatch_config.errors == 'stdout':
            print(header)
            for line in error_jobs_lines(jobs):
                print(line)
            print('--')
            duration = time.perf_counter() - start
            print(f"Checked {len(jobs)} enabled job{'s' if len(jobs) else ''} for errors in {dur_text(duration)}.")

        else:
            message = '\n'.join(error_jobs_lines(jobs))
            if message:
                # create a dummy job state to run a reporter on
                job_state = JobState(
                    None,  # type: ignore[arg-type]
                    JobBase.unserialize({'command': f'{__project_name__} --errors'}),
                )
                job_state.traceback = f'{header}\n{message}'
                duration = time.perf_counter() - start
                self.urlwatcher.report.config['footnote'] = (
                    f"Checked {len(jobs)} job{'s' if len(jobs) else ''} for errors in {dur_text(duration)}."
                )
                self.urlwatcher.report.config['report']['html']['footer'] = False
                self.urlwatcher.report.config['report']['markdown']['footer'] = False
                self.urlwatcher.report.config['report']['text']['footer'] = False
                self.urlwatcher.report.error(job_state)
                self.urlwatcher.report.finish_one(self.urlwatch_config.errors, check_enabled=False)
            else:
                print(header)
                print('--')
                duration = time.perf_counter() - start
                print('Found no errors.')
                print(f"Checked {len(jobs)} job{'s' if len(jobs) else ''} for errors in {dur_text(duration)}.")

        return 0

    def rollback_database(self, timespec: str) -> int:
        """Issues a warning, calls rollback() and prints out the result.

        :param timestamp: A timespec that if numeric is interpreted as a Unix timestamp otherwise it's passed to
          dateutil.parser (if datetime is installed) or datetime.fromisoformat to be converted into a date.

        :return: A sys.exit code (0 for succcess, 1 for failure)
        """

        def _convert_to_datetime(timespec: str, tz_info: ZoneInfo | tzinfo | None) -> datetime:
            """Converts inputted string to a datetime object, using dateutil if installed.

            :param timespec: The string.
            :param tz_info: The timezone.

            :return: The datetime object.
            """
            try:
                timestamp = float(timespec)
                return datetime.fromtimestamp(timestamp, tz_info)
            except ValueError:
                try:
                    from dateutil import parser as dateutil_parser

                    default_dt_with_tz = datetime.now().replace(second=0, microsecond=0, tzinfo=tz_info)
                    return dateutil_parser.parse(timespec, default=default_dt_with_tz)
                    # return dateutil_parser.parse(timespec)
                except ImportError:
                    dt = datetime.fromisoformat(timespec)
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=tz_info)
                    return dt

        tz = self.urlwatcher.report.config['report']['tz']
        tz_info = ZoneInfo(tz) if tz else datetime.now().astimezone().tzinfo  # from machine
        dt = _convert_to_datetime(timespec, tz_info)
        timestamp_date = email.utils.format_datetime(dt)
        count = self.urlwatcher.ssdb_storage.rollback(dt.timestamp())
        print(f'Rolling back database to {timestamp_date}.')
        if sys.__stdin__ and sys.__stdin__.isatty():
            print(
                f'WARNING: All {count} snapshots after this date/time (check timezone) will be deleted.\n'
                '         💀 This operation cannot be undone!\n'
                '         We suggest you make a backup of the database file before proceeding.\n'
            )
            resp = input("         Please enter 'Y' to proceed: ")
            if not resp.upper().startswith('Y'):
                print('Quitting rollback. No snapshots have been deleted.')
                return 1
        count = self.urlwatcher.ssdb_storage.rollback(dt.timestamp())
        if count:
            print(f'Deleted {count} snapshots taken after {timestamp_date}.')
            self.urlwatcher.ssdb_storage.close()
        else:
            print(f'No snapshots found after {timestamp_date}')
        return 0

    def delete_snapshot(self, job_id: str | int) -> int:
        job = self._find_job_with_defaults(job_id)
        history = self.urlwatcher.ssdb_storage.get_history_snapshots(job.guid)
        if not history:
            print(f'No snapshots found for {job.get_indexed_location()}.')
            return 1
        if sys.__stdin__ and sys.__stdin__.isatty():
            print(f'WARNING: About to delete the latest snapshot of\n         {job.get_indexed_location()}:')
            for i, history_job in enumerate(history):
                print(
                    f"         {i + 1}. {'❌ ' if i == 0 else '   '}"
                    f'{email.utils.format_datetime(datetime.fromtimestamp(history_job.timestamp))}'
                    f"{'  ⬅  ABOUT TO BE DELETED!' if i == 0 else ''}"
                )
            print(
                '         This operation cannot be undone!\n'
                '         We suggest you make a backup of the database file before proceeding.\n'
            )
            resp = input("         Please enter 'Y' to proceed: ")
            if not resp.upper().startswith('Y'):
                print('Quitting. No snapshots have been deleted.')
                return 1
        count = self.urlwatcher.ssdb_storage.delete_latest(job.guid)
        if count:
            print(f'Deleted last snapshot of {job.get_indexed_location()}; {len(history) - 1} snapshots left.')
            return 0
        else:
            print(f'No snapshots found for {job.get_indexed_location()}.')
            return 1

    def modify_urls(self) -> int:
        if self.urlwatch_config.delete is not None:
            job = self._find_job(self.urlwatch_config.delete)
            if job is not None:
                if sys.__stdin__ and sys.__stdin__.isatty():
                    print(
                        f'WARNING: About to permanently delete {job.get_indexed_location()}.\n'
                        '         Job file will be overwritten and all remarks lost.'
                        '         This operation cannot be undone!\n'
                    )
                    resp = input("         Please enter 'Y' to proceed: ")
                    if not resp.upper().startswith('Y'):
                        print(f'Quitting. Job {job.index_number} has not been deleted and job file is unmodified.')
                        return 1
                self.urlwatcher.jobs.remove(job)
                print(f'Removed {job}.')
                self.urlwatcher.jobs_storage.save(self.urlwatcher.jobs)
            else:
                print(f'Job not found: {self.urlwatch_config.delete}.')
                return 1

        if self.urlwatch_config.add is not None:
            # Allow multiple specifications of filter=, so that multiple filters can be specified on the CLI
            items = [item.split('=', 1) for item in self.urlwatch_config.add.split(',')]
            filters = [v for k, v in items if k == 'filter']
            items2 = [(k, v) for k, v in items if k != 'filter']
            d = {k: v for k, v in items2}
            if filters:
                d['filter'] = ','.join(filters)

            job = JobBase.unserialize(d)
            print(f'Adding {job}.')
            self.urlwatcher.jobs.append(job)
            self.urlwatcher.jobs_storage.save(self.urlwatcher.jobs)

        if self.urlwatch_config.change_location is not None:
            new_loc = self.urlwatch_config.change_location[1]
            # Ensure the user isn't overwriting an existing job with the change.
            if new_loc in (j.get_location() for j in self.urlwatcher.jobs):
                print(
                    f'The new location "{new_loc}" already exists for a job. Delete the existing job or choose a '
                    f'different value.\n'
                    f'Hint: you have to run --change-location before you update the jobs.yaml file!'
                )
                return 1
            else:
                job = self._find_job(self.urlwatch_config.change_location[0])
                if job is not None:
                    # Update the job's location (which will also update the guid) and move any history in the database
                    # over to the job's updated guid.
                    old_loc = job.get_location()
                    print(f'Moving location of "{old_loc}" to "{new_loc}".')
                    old_guid = job.guid
                    if old_guid not in self.urlwatcher.ssdb_storage.get_guids():
                        print(f'No snapshots found for "{old_loc}".')
                        return 1
                    job.set_base_location(new_loc)
                    num_searched = self.urlwatcher.ssdb_storage.move(old_guid, job.guid)
                    if num_searched:
                        print(f'Searched through {num_searched:,} snapshots and moved "{old_loc}" to "{new_loc}".')
                else:
                    print(f'Job not found: "{self.urlwatch_config.change_location[0]}".')
                    return 1
            message = 'Do you want me to update the jobs file (remarks will be lost)? [y/N] '
            if not input(message).lower().startswith('y'):
                print(f'Please manually update the jobs file by replacing "{old_loc}" with "{new_loc}".')
            else:
                self.urlwatcher.jobs_storage.save(self.urlwatcher.jobs)

        return 0

    def edit_config(self) -> int:
        result = self.urlwatcher.config_storage.edit()
        return result

    def check_telegram_chats(self) -> None:
        config: _ConfigReportTelegram = self.urlwatcher.config_storage.config['report']['telegram']

        bot_token = config['bot_token']
        if not bot_token:
            print('You need to set up your bot token first (see documentation).')
            self._exit(1)

        if httpx:
            get_client = httpx.Client(http2=h2 is not None).get  # noqa: S113 Call to httpx without timeout
        else:
            get_client = requests.get  # type: ignore[assignment]

        info = get_client(f'https://api.telegram.org/bot{bot_token}/getMe', timeout=60).json()
        if not info['ok']:
            print(f"Error with token {bot_token}: {info['description']}.")
            self._exit(1)

        chats = {}
        updates = get_client(f'https://api.telegram.org/bot{bot_token}/getUpdates', timeout=60).json()
        if 'result' in updates:
            for chat_info in updates['result']:
                chat = chat_info['message']['chat']
                if chat['type'] == 'private':
                    chats[chat['id']] = (
                        ' '.join((chat['first_name'], chat['last_name'])) if 'last_name' in chat else chat['first_name']
                    )

        if not chats:
            print(f"No chats found. Say hello to your bot at https://t.me/{info['result']['username']}.")
            self._exit(1)

        headers = ('Chat ID', 'Name')
        maxchat = max(len(headers[0]), max((len(k) for k, v in chats.items()), default=0))
        maxname = max(len(headers[1]), max((len(v) for k, v in chats.items()), default=0))
        fmt = f'%-{maxchat}s  %s'
        print(fmt % headers)
        print(fmt % ('-' * maxchat, '-' * maxname))
        for k, v in sorted(chats.items(), key=lambda kv: kv[1]):
            print(fmt % (k, v))
        print(f"\nChat up your bot here: https://t.me/{info['result']['username']}.")

        self._exit(0)

    def check_test_reporter(
        self,
        job_state: JobState | None = None,
        label: str = 'test',
        report: Report | None = None,
    ) -> int:
        """
        Tests a reporter by creating pseudo-jobs of new, changed, unchanged, and error outcomes ('verb').

        Note: The report will only show new, unchanged and error content if enabled in the respective `display` keys
        of the configuration file.

        :param job_state: The JobState (Optional).
        :param label: The label to be used in the report; defaults to 'test'.
        :param report: A Report class to use for testing (Optional).
        :return: 0 if successful, 1 otherwise.
        """

        def build_job(job_name: str, url: str, old: str, new: str) -> JobState:
            """Builds a pseudo-job for the reporter to run on."""
            job = JobBase.unserialize({'name': job_name, 'url': url})

            # Can pass in None for ssdb_storage, as we are not going to load or save the job state for
            # testing; also no need to use it as context manager, since no processing is called on the job
            job_state = JobState(None, job)  # type: ignore[arg-type]

            job_state.old_data = old
            job_state.old_timestamp = 1605147837.511478  # initial release of webchanges!
            job_state.new_data = new
            job_state.new_timestamp = time.time()

            return job_state

        def set_error(job_state: 'JobState', message: str) -> JobState:
            """Sets a job error message on a JobState."""
            try:
                raise ValueError(message)
            except ValueError as e:
                job_state.exception = e
                job_state.traceback = job_state.job.format_error(e, traceback.format_exc())

            return job_state

        reporter_name = self.urlwatch_config.test_reporter
        if reporter_name not in ReporterBase.__subclasses__:
            print(
                f'No such reporter: {reporter_name}.\n'
                f'\nSupported reporters:\n{ReporterBase.reporter_documentation()}.\n'
            )
            return 1

        cfg: _ConfigReportersList = self.urlwatcher.config_storage.config['report'][
            reporter_name  # type: ignore[literal-required]
        ]
        if job_state:  # we want a full report
            cfg['enabled'] = True
            self.urlwatcher.config_storage.config['display'][label] = True  # type: ignore[literal-required]
            self.urlwatcher.config_storage.config['report']['text']['details'] = True
            self.urlwatcher.config_storage.config['report']['text']['footer'] = True
            self.urlwatcher.config_storage.config['report']['text']['minimal'] = False
            self.urlwatcher.config_storage.config['report']['markdown']['details'] = True
            self.urlwatcher.config_storage.config['report']['markdown']['footer'] = True
            self.urlwatcher.config_storage.config['report']['markdown']['minimal'] = False
            self.urlwatcher.config_storage.config['report']['stdout']['color'] = False
        elif not cfg['enabled']:
            print(
                f'WARNING: Reporter being tested is not enabled: {reporter_name}.\n'
                f'Will still attempt to test it, but this may not work.\n'
                f'Use {__project_name__} --edit-config to configure reporters.'
            )
            cfg['enabled'] = True

        if report is None:
            report = Report(self.urlwatcher)

        if job_state:
            report.custom(job_state, label)  # type: ignore[arg-type]
        else:
            report.new(
                build_job(
                    'Sample job that was newly added',
                    'https://example.com/new',
                    '',
                    '',
                )
            )
            report.changed(
                build_job(
                    'Sample job where something changed',
                    'https://example.com/changed',
                    'Unchanged Line\nPrevious Content\nAnother Unchanged Line\n',
                    'Unchanged Line\nUpdated Content\nAnother Unchanged Line\n',
                )
            )
            report.unchanged(
                build_job(
                    'Sample job where nothing changed',
                    'http://example.com/unchanged',
                    'Same Old, Same Old\n',
                    'Same Old, Same Old\n',
                )
            )
            report.error(
                set_error(
                    build_job(
                        'Sample job where an error was encountered',
                        'https://example.com/error',
                        '',
                        '',
                    ),
                    'The error message would appear here.',
                )
            )

        report.finish_one(reporter_name, jobs_file=self.urlwatch_config.jobs_files)

        return 0

    def check_smtp_login(self) -> None:
        config: _ConfigReportEmail = self.urlwatcher.config_storage.config['report']['email']
        smtp_config: _ConfigReportEmailSmtp = config['smtp']

        success = True

        if not config['enabled']:
            print('Please enable email reporting in the config first.')
            success = False

        if config['method'] != 'smtp':
            print('Please set the method to SMTP for the email reporter.')
            success = False

        smtp_auth = smtp_config['auth']
        if not smtp_auth:
            print('Authentication must be enabled for SMTP.')
            success = False

        smtp_hostname = smtp_config['host']
        if not smtp_hostname:
            print('Please configure the SMTP hostname in the config first.')
            success = False

        smtp_username = smtp_config['user'] or config['from']
        if not smtp_username:
            print('Please configure the SMTP user in the config first.')
            success = False

        if not success:
            self._exit(1)

        insecure_password = smtp_config['insecure_password']
        if insecure_password:
            print('The SMTP password is set in the config file (key "insecure_password").')
        elif smtp_have_password(smtp_hostname, smtp_username):
            message = f'Password for {smtp_username} / {smtp_hostname} already set, update? [y/N] '
            if not input(message).lower().startswith('y'):
                print('Password unchanged.')
            else:
                smtp_set_password(smtp_hostname, smtp_username)

        smtp_port = smtp_config['port']
        smtp_tls = smtp_config['starttls']

        mailer = SMTPMailer(smtp_username, smtp_hostname, smtp_port, smtp_tls, smtp_auth, insecure_password)
        print('Trying to log into the SMTP server...')
        mailer.send(None)
        print('Successfully logged into SMTP server.')

        self._exit(0)

    def check_xmpp_login(self) -> None:
        xmpp_config: _ConfigReportXmpp = self.urlwatcher.config_storage.config['report']['xmpp']

        success = True

        if not xmpp_config['enabled']:
            print('Please enable XMPP reporting in the config first.')
            success = False

        xmpp_sender = xmpp_config['sender']
        if not xmpp_sender:
            print('Please configure the XMPP sender in the config first.')
            success = False

        if not xmpp_config['recipient']:
            print('Please configure the XMPP recipient in the config first.')
            success = False

        if not success:
            self._exit(1)

        if 'insecure_password' in xmpp_config:
            print('The XMPP password is already set in the config (key "insecure_password").')
            self._exit(0)

        if xmpp_have_password(xmpp_sender):
            message = f'Password for {xmpp_sender} already set, update? [y/N] '
            if input(message).lower() != 'y':
                print('Password unchanged.')
                self._exit(0)

        if success:
            xmpp_set_password(xmpp_sender)

        self._exit(0)

    @staticmethod
    def playwright_install_chrome() -> int:  # pragma: no cover
        """
        Replicates playwright.___main__.main() function, which is called by the playwright executable, in order to
        install the browser executable.

        :return: Playwright's executable return code.
        """
        try:
            from playwright._impl._driver import compute_driver_executable  # pyright: ignore[reportPrivateImportUsage]
        except ImportError:  # pragma: no cover
            raise ImportError('Python package playwright is not installed; cannot install the Chrome browser') from None

        driver_executable = compute_driver_executable()
        env = os.environ.copy()
        env['PW_CLI_TARGET_LANG'] = 'python'
        cmd = [str(driver_executable), 'install', 'chrome']
        logger.info(f"Running playwright CLI: {' '.join(cmd)}")
        completed_process = subprocess.run(cmd, env=env, capture_output=True, text=True)  # noqa: S603 subprocess call
        if completed_process.returncode:
            print(completed_process.stderr)
            return completed_process.returncode
        if completed_process.stdout:
            logger.info(f'Success! Output of Playwright CLI: {completed_process.stdout}')
        return 0

    def handle_actions(self) -> None:
        """Handles the actions for command line arguments and exits."""
        if self.urlwatch_config.list_jobs:
            self.list_jobs(self.urlwatch_config.list_jobs)
            self._exit(0)

        if self.urlwatch_config.errors:
            self._exit(self.list_error_jobs())

        if self.urlwatch_config.test_job:
            self.test_job(self.urlwatch_config.test_job)
            self._exit(0)

        if self.urlwatch_config.prepare_jobs:
            self.prepare_jobs()
            self._exit(0)

        if self.urlwatch_config.test_differ:
            self._exit(self.test_differ(self.urlwatch_config.test_differ))

        if self.urlwatch_config.dump_history:
            self._exit(self.dump_history(self.urlwatch_config.dump_history))

        if self.urlwatch_config.add or self.urlwatch_config.delete or self.urlwatch_config.change_location:
            self._exit(self.modify_urls())

        if self.urlwatch_config.test_reporter:
            self._exit(self.check_test_reporter())

        if self.urlwatch_config.smtp_login:
            self.check_smtp_login()

        if self.urlwatch_config.telegram_chats:
            self.check_telegram_chats()

        if self.urlwatch_config.xmpp_login:
            self.check_xmpp_login()

        if self.urlwatch_config.edit:
            self._exit(self.urlwatcher.jobs_storage.edit())

        if self.urlwatch_config.edit_config:
            self._exit(self.edit_config())

        if self.urlwatch_config.edit_hooks:
            self._exit(self.edit_hooks())

        if self.urlwatch_config.gc_database:
            self.urlwatcher.ssdb_storage.gc(
                [job.guid for job in self.urlwatcher.jobs], self.urlwatch_config.gc_database
            )
            self.urlwatcher.ssdb_storage.close()
            self._exit(0)

        if self.urlwatch_config.clean_database:
            self.urlwatcher.ssdb_storage.clean_ssdb(
                [job.guid for job in self.urlwatcher.jobs], self.urlwatch_config.clean_database
            )
            self.urlwatcher.ssdb_storage.close()
            self._exit(0)

        if self.urlwatch_config.rollback_database:
            exit_arg = self.rollback_database(self.urlwatch_config.rollback_database)
            self.urlwatcher.ssdb_storage.close()
            self._exit(exit_arg)

        if self.urlwatch_config.delete_snapshot:
            self._exit(self.delete_snapshot(self.urlwatch_config.delete_snapshot))

        if self.urlwatch_config.features:
            self._exit(self.show_features())

        if self.urlwatch_config.detailed_versions:
            self._exit(self.show_detailed_versions())

    def run(self) -> None:  # pragma: no cover
        """The main run logic."""
        self.urlwatcher.report.config = self.urlwatcher.config_storage.config
        self.urlwatcher.report.config['footnote'] = self.urlwatch_config.footnote

        self.handle_actions()

        self.urlwatcher.run_jobs()

        self.urlwatcher.close()

        self._exit(0)
