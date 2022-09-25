"""Take actions from command line arguments."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import contextlib
import difflib
import logging
import os
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Union

import requests

try:
    from zoneinfo import ZoneInfo  # not available in Python < 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

from . import __docs_url__, __project_name__, __version__
from .filters import FilterBase
from .handler import JobState, Report, SnapshotShort
from .jobs import BrowserJob, JobBase, UrlJob
from .mailer import smtp_have_password, smtp_set_password, SMTPMailer
from .main import Urlwatch
from .reporters import ReporterBase, xmpp_have_password, xmpp_set_password
from .util import dur_text, edit_file, import_module_from_source

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .reporters import ConfigReportersList
    from .storage import ConfigReportEmail, ConfigReportEmailSmtp, ConfigReportTelegram, ConfigReportXmpp


class UrlwatchCommand:
    """The class that runs the program after initialization and CLI arguments parsing."""

    def __init__(self, urlwatcher: Urlwatch) -> None:
        self.urlwatcher = urlwatcher
        self.urlwatch_config = urlwatcher.urlwatch_config

    @staticmethod
    def _exit(arg: object) -> None:
        logger.info(f'Exiting with exit code {arg}')
        sys.exit(arg)

    def edit_hooks(self) -> int:
        """Edit hooks file.

        :returns: 0 if edit is successful, 1 otherwise.
        """
        # Similar code to BaseTextualFileStorage.edit()
        # Python 3.9: hooks_edit = self.urlwatch_config.hooks.with_stem(self.urlwatch_config.hooks.stem + '_edit')
        hooks_edit = self.urlwatch_config.hooks_file.parent.joinpath(
            self.urlwatch_config.hooks_file.stem + '_edit' + ''.join(self.urlwatch_config.hooks_file.suffixes)
        )
        if self.urlwatch_config.hooks_file.exists():
            shutil.copy(self.urlwatch_config.hooks_file, hooks_edit)
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
                print(f'The file {self.urlwatch_config.hooks_file} was NOT updated.')
                user_input = input('Do you want to retry the same edit? (Y/n)')
                if not user_input or user_input.lower()[0] == 'y':
                    continue
                hooks_edit.unlink()
                print('No changes have been saved.')
                return 1

        if self.urlwatch_config.hooks_file.is_symlink():
            self.urlwatch_config.hooks_file.write_text(hooks_edit.read_text())
        else:
            hooks_edit.replace(self.urlwatch_config.hooks_file)
        # python 3.8: replace with hooks_edit.unlink(missing_ok=True)
        if hooks_edit.is_file():
            hooks_edit.unlink()
        print(f'Saved edits in {self.urlwatch_config.hooks_file}')
        return 0

    @staticmethod
    def show_features() -> int:
        """
        Prints the "features", i.e. a list of job types, filters and reporters.

        :return: 0.
        """
        print(f'Please see full documentation at {__docs_url__}')
        print()
        print('Supported jobs:\n')
        print(JobBase.job_documentation())
        print('Supported filters:\n')
        print(FilterBase.filter_documentation())
        print()
        print('Supported reporters:\n')
        print(ReporterBase.reporter_documentation())
        print()
        print(f'Please see full documentation at {__docs_url__}')

        return 0

    def list_jobs(self) -> None:
        """
        Lists the job and their respective _index_number.

        :return: None.
        """
        for job in self.urlwatcher.jobs:
            if self.urlwatch_config.verbose:
                print(f'{job.index_number:3}: {job!r}')
            else:
                pretty_name = job.pretty_name()
                location = job.get_location()
                if pretty_name != location:
                    print(f'{job.index_number:3}: {pretty_name} ({location})')
                else:
                    print(f'{job.index_number:3}: {pretty_name}')
        if len(self.urlwatch_config.jobs_files) > 1:
            jobs_files = ['Jobs files concatenated:'] + [f'• {file}' for file in self.urlwatch_config.jobs_files]
        elif len(self.urlwatch_config.jobs_files) == 1:
            jobs_files = [f'Jobs file: {self.urlwatch_config.jobs_files[0]}']
        else:
            jobs_files = []
        print('\n   '.join(jobs_files))

    def _find_job(self, query: Union[str, int]) -> Optional[JobBase]:
        try:
            index = int(query)
            if index == 0:
                return None
            try:
                if index <= 0:
                    return self.urlwatcher.jobs[index]
                else:
                    return self.urlwatcher.jobs[index - 1]
            except IndexError:
                return None
        except ValueError:
            return next((job for job in self.urlwatcher.jobs if job.get_location() == query), None)

    def _get_job(self, job_id: Union[str, int]) -> JobBase:
        """
        Finds the job based on job_id, which could match an index, be a range, or match a url or command field.

        :param job_id:
        :return: JobBase.
        :raises SystemExit: If job is not found, setting argument to 1.
        """
        try:
            job_id = int(job_id)
            if job_id < 0:
                job_id = len(self.urlwatcher.jobs) + job_id + 1
        except ValueError:
            pass
        job = self._find_job(job_id)
        if job is None:
            print(f'Job not found: {job_id}')
            raise SystemExit(1)
        return job.with_defaults(self.urlwatcher.config_storage.config)

    def test_job(self, job_id: Union[bool, str, int]) -> None:
        """
        Tests the running of a single job outputting the filtered text to stdout or whatever reporter is selected with
        --test-reporter.  If job_id is True, don't run any jobs as it's a test of loading config, jobs and hook files
        for syntax.

        :param job_id: The job_id or True.

        :return: None.

        :raises Exception: The Exception when raised by a job. loading of hooks files, etc.
        """
        if job_id is True:
            message = [f'No syntax errors in config file {self.urlwatch_config.config_file}']
            conj = ',\n' if 'hooks' in sys.modules else '\nand '
            if len(self.urlwatch_config.jobs_files) == 1:
                message.append(f'{conj}jobs file {self.urlwatch_config.jobs_files[0]}')
            else:
                message.append(
                    '\n   '.join([f'{conj}jobs files'] + [f'• {file}' for file in self.urlwatch_config.jobs_files])
                )
            if 'hooks' in sys.modules:
                message.append(f",\nand hooks file {sys.modules['hooks'].__file__}")
            print(f"{''.join(message)}.")
            return

        job = self._get_job(job_id)
        start = time.perf_counter()

        if isinstance(job, UrlJob):
            # Force re-retrieval of job, as we're testing filters
            job.ignore_cached = True

        with JobState(self.urlwatcher.cache_storage, job) as job_state:
            job_state.process(headless=not self.urlwatch_config.no_headless)
            duration = time.perf_counter() - start
            if job_state.exception is not None:
                raise job_state.exception
            print(job_state.job.pretty_name())
            print('-' * len(job_state.job.pretty_name()))
            if job_state.job.note:
                print(job_state.job.note)
            print()
            print(job_state.new_data)
            print()
            print('--')
            print(f'Job tested in {dur_text(duration)} with {__project_name__} {__version__}.')

        return

        # We do not save the job state or job on purpose here, since we are possibly modifying the job
        # (ignore_cached) and we do not want to store the newly-retrieved data yet (filter testing)

    def test_diff(self, job_id: str) -> int:
        """
        Runs diffs for a job on all the saved snapshots and outputs the result to stdout or whatever reporter is
        selected with --test-reporter.

        :param job_id: The job_id.
        :return: 1 if error, 0 if successful.
        """
        report = Report(self.urlwatcher)
        self.urlwatch_config.jobs_files = [Path('--test-diff')]  # for report footer
        job = self._get_job(job_id)

        history_data = self.urlwatcher.cache_storage.get_history_snapshots(job.get_guid())

        num_snapshots = len(history_data)
        if num_snapshots == 0:
            print('This job has never been run before.')
            return 1
        elif num_snapshots < 2:
            print('Not enough historic data available (need at least 2 different snapshots).')
            return 1

        if job.compared_versions and job.compared_versions != 1:
            print(f"Note: The job's 'compared_versions' directive is set to {job.compared_versions}.")

        for i in range(num_snapshots - 1):
            with JobState(self.urlwatcher.cache_storage, job) as job_state:
                job_state.new_data = history_data[i].data
                job_state.new_timestamp = history_data[i].timestamp
                job_state.new_etag = history_data[i].etag
                if not job.compared_versions or job.compared_versions == 1:
                    job_state.old_data = history_data[i + 1].data
                    job_state.old_timestamp = history_data[i + 1].timestamp
                    job_state.old_etag = history_data[i + 1].etag
                else:
                    history_dic_snapshots = {
                        s.data: SnapshotShort(s.timestamp, s.tries, s.etag)
                        for s in history_data[i + 1 : i + 1 + job.compared_versions]
                    }
                    close_matches: list[str] = difflib.get_close_matches(
                        job_state.new_data, history_dic_snapshots.keys(), n=1
                    )
                    if close_matches:
                        job_state.old_data = close_matches[0]
                        job_state.old_timestamp = history_dic_snapshots[close_matches[0]].timestamp
                        job_state.old_etag = history_dic_snapshots[close_matches[0]].etag

                # TODO: setting of job_state.job.is_markdown = True when it had been set by a filter.
                # Ideally it should be saved as an attribute when saving "data".
                if self.urlwatch_config.test_reporter is None:
                    self.urlwatch_config.test_reporter = 'stdout'  # default
                report.job_states = []  # required
                if job_state.new_data == job_state.old_data:
                    label = (
                        f'No change (snapshots {-i:2} AND {-(i + 1):2}) with '
                        f"'compared_versions: {job.compared_versions}'"
                    )
                else:
                    label = f'Filtered diff (snapshots {-i:2} and {-(i + 1):2})'
                errorlevel = self.check_test_reporter(job_state, label=label, report=report)
                if errorlevel:
                    self._exit(errorlevel)

        # We do not save the job state or job on purpose here, since we are possibly modifying the job
        # (ignore_cached) and we do not want to store the newly-retrieved data yet (filter testing)

        return 0

    def dump_history(self, job_id: str) -> int:
        job = self._get_job(job_id)
        history_data = self.urlwatcher.cache_storage.get_history_snapshots(job.get_guid())

        print(f'History for job {job.get_indexed_location()}:')
        print(f'(ID: {job.get_guid()})')
        total_failed = 0
        for i, snapshot in enumerate(history_data):
            etag = f'; ETag: {snapshot[3]}' if snapshot[3] else ''
            tries = f'; error run (number {snapshot[2]})' if snapshot[2] else ''
            total_failed += snapshot[2] > 0
            tz = self.urlwatcher.report.config['report']['tz'] or 'Etc/UTC'
            dt = datetime.fromtimestamp(snapshot[1], ZoneInfo(tz))
            header = f"{i + 1}) {dt.strftime('%Y-%m-%d %H:%M %Z')}{etag}{tries}"
            sep_len = max(50, min(50, len(header)))
            print('=' * sep_len)
            print(header)
            print('-' * sep_len)
            print(snapshot[0])
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

    def list_error_jobs(self) -> None:
        start = time.perf_counter()
        if len(self.urlwatch_config.jobs_files) == 1:
            jobs_files = [f'in jobs file {self.urlwatch_config.jobs_files[0]}:']
        else:
            jobs_files = ['in the concatenation of the jobs files'] + [
                f'• {file}' for file in self.urlwatch_config.jobs_files
            ]
        print('\n   '.join(['Jobs with errors or returning no data (after filters, if any)'] + jobs_files))

        # extract subset of jobs to run if joblist CLI was set
        if self.urlwatcher.urlwatch_config.joblist:
            for idx in self.urlwatcher.urlwatch_config.joblist:
                if not (-len(self.urlwatcher.jobs) <= idx <= -1 or 1 <= idx <= len(self.urlwatcher.jobs)):
                    raise IndexError(f'Job index {idx} out of range (found {len(self.urlwatcher.jobs)} jobs).')
            self.urlwatcher.urlwatch_config.joblist = [
                jn if jn > 0 else len(self.urlwatcher.jobs) + jn + 1 for jn in self.urlwatcher.urlwatch_config.joblist
            ]
            jobs = [
                job.with_defaults(self.urlwatcher.config_storage.config)
                for job in self.urlwatcher.jobs
                if job.index_number in self.urlwatcher.urlwatch_config.joblist
            ]
            logger.debug(
                f'Processing {len(jobs)} job{"s" if len(jobs) else ""} as specified in command line: # '
                f'{", ".join(str(j) for j in self.urlwatcher.urlwatch_config.joblist)}'
            )
            print(
                f'Processing {len(jobs)} job{"s" if len(jobs) else ""} as specified in command line: # '
                f'{", ".join(str(j) for j in self.urlwatcher.urlwatch_config.joblist)}'
            )
        else:
            jobs = [job.with_defaults(self.urlwatcher.config_storage.config) for job in self.urlwatcher.jobs]
            logger.debug(f'Processing {len(jobs)} job{"s" if len(jobs) else ""}')

        for job in jobs:
            # Force re-retrieval of job, as we're testing for errors
            job.ignore_cached = True
        with contextlib.ExitStack() as stack:
            max_workers = min(32, os.cpu_count() or 1) if any(type(job) == BrowserJob for job in jobs) else None
            logger.debug(f'Max_workers set to {max_workers}')
            executor = ThreadPoolExecutor(max_workers=max_workers)

            for job_state in executor.map(
                lambda jobstate: jobstate.process(headless=not self.urlwatch_config.no_headless),
                (stack.enter_context(JobState(self.urlwatcher.cache_storage, job)) for job in jobs),
            ):
                if job_state.exception is not None:
                    pretty_name = job_state.job.pretty_name()
                    location = job_state.job.get_location()
                    if pretty_name != location:
                        print(
                            f'{job_state.job.index_number:3}: Error "{job_state.exception}": {pretty_name} ({location})'
                        )
                    else:
                        print(f'{job_state.job.index_number:3}: Error "{job_state.exception}": {pretty_name})')
                elif len(job_state.new_data.strip()) == 0:
                    if self.urlwatch_config.verbose:
                        print(f'{job_state.job.index_number:3}: No data: {job_state.job!r}')
                    else:
                        pretty_name = job_state.job.pretty_name()
                        location = job_state.job.get_location()
                        if pretty_name != location:
                            print(f'{job_state.job.index_number:3}: No data: {pretty_name} ({location})')
                        else:
                            print(f'{job_state.job.index_number:3}: No data: {pretty_name}')

        end = time.perf_counter()
        duration = end - start
        print('--')
        print(f"Checked {len(jobs)} job{'s' if len(jobs) else ''} in {dur_text(duration)}.")

        # We do not save the job state or job on purpose here, since we are possibly modifying the job
        # (ignore_cached) and we do not want to store the newly-retrieved data yet (just showing errors)

    def delete_snapshot(self, job_id: Union[str, int]) -> int:
        job = self._get_job(job_id)

        deleted = self.urlwatcher.cache_storage.delete_latest(job.get_guid())
        if deleted:
            print(f'Deleted last snapshot of {job.get_indexed_location()}')
            return 0
        else:
            print(f'No snapshots found to be deleted for {job.get_indexed_location()}')
            return 1

    def modify_urls(self) -> None:
        save = True
        if self.urlwatch_config.delete is not None:
            job = self._find_job(self.urlwatch_config.delete)
            if job is not None:
                self.urlwatcher.jobs.remove(job)
                print(f'Removed {job}')
            else:
                print(f'Job not found: {self.urlwatch_config.delete}')
                save = False

        if self.urlwatch_config.add is not None:
            # Allow multiple specifications of filter=, so that multiple filters can be specified on the CLI
            items = [item.split('=', 1) for item in self.urlwatch_config.add.split(',')]
            filters = [v for k, v in items if k == 'filter']
            items2 = [(k, v) for k, v in items if k != 'filter']
            d = {k: v for k, v in items2}
            if filters:
                d['filter'] = ','.join(filters)

            job = JobBase.unserialize(d)
            print(f'Adding {job}')
            self.urlwatcher.jobs.append(job)

        if save:
            self.urlwatcher.jobs_storage.save(self.urlwatcher.jobs)

    def edit_config(self) -> int:
        result = self.urlwatcher.config_storage.edit()
        return result

    def check_telegram_chats(self) -> None:
        config: ConfigReportTelegram = self.urlwatcher.config_storage.config['report']['telegram']

        bot_token = config['bot_token']
        if not bot_token:
            print('You need to set up your bot token first (see documentation)')
            self._exit(1)

        info = requests.get(f'https://api.telegram.org/bot{bot_token}/getMe').json()
        if not info['ok']:
            print(f"Error with token {bot_token}: {info['description']}")
            self._exit(1)

        chats = {}
        updates = requests.get(f'https://api.telegram.org/bot{bot_token}/getUpdates').json()
        if 'result' in updates:
            for chat_info in updates['result']:
                chat = chat_info['message']['chat']
                if chat['type'] == 'private':
                    chats[chat['id']] = (
                        ' '.join((chat['first_name'], chat['last_name'])) if 'last_name' in chat else chat['first_name']
                    )

        if not chats:
            print(f"No chats found. Say hello to your bot at https://t.me/{info['result']['username']}")
            self._exit(1)

        headers = ('Chat ID', 'Name')
        maxchat = max(len(headers[0]), max((len(k) for k, v in chats.items()), default=0))
        maxname = max(len(headers[1]), max((len(v) for k, v in chats.items()), default=0))
        fmt = f'%-{maxchat}s  %s'
        print(fmt % headers)
        print(fmt % ('-' * maxchat, '-' * maxname))
        for k, v in sorted(chats.items(), key=lambda kv: kv[1]):
            print(fmt % (k, v))
        print(f"\nChat up your bot here: https://t.me/{info['result']['username']}")

        self._exit(0)

    def check_test_reporter(
        self,
        job_state: Optional[JobState] = None,
        label: str = 'test',
        report: Optional[Report] = None,
    ) -> int:
        """
        Tests a reporter.

        :param job_state: The JobState (Optional).
        :param label: The label to be used in the report; defaults to 'test'.
        :param report: A Report class to use for testing (Optional).
        :return: 0 if successful, 1 otherwise.
        """

        def build_job(job_name: str, url: str, old: str, new: str) -> JobState:
            """Builds a pseudo-job for the reporter to run on."""
            job = JobBase.unserialize({'name': job_name, 'url': url})

            # Can pass in None for cache_storage, as we are not going to load or save the job state for
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
            print(f'No such reporter: {reporter_name}')
            print(f'\nSupported reporters:\n{ReporterBase.reporter_documentation()}\n')
            return 1

        cfg: ConfigReportersList = self.urlwatcher.config_storage.config['report'][
            reporter_name  # type: ignore[literal-required]
        ]
        if job_state:  # we want a full report
            cfg['enabled'] = True
            self.urlwatcher.config_storage.config['report']['text']['details'] = True
            self.urlwatcher.config_storage.config['report']['text']['footer'] = True
            self.urlwatcher.config_storage.config['report']['text']['minimal'] = False
            self.urlwatcher.config_storage.config['report']['markdown']['details'] = True
            self.urlwatcher.config_storage.config['report']['markdown']['footer'] = True
            self.urlwatcher.config_storage.config['report']['markdown']['minimal'] = False
        if not cfg['enabled']:
            print(f'Reporter is not enabled/configured: {reporter_name}')
            print(f'Use {__project_name__} --edit-config to configure reporters')
            return 1

        if report is None:
            report = Report(self.urlwatcher)

        if job_state:
            report.custom(job_state, label)
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
        config: ConfigReportEmail = self.urlwatcher.config_storage.config['report']['email']
        smtp_config: ConfigReportEmailSmtp = config['smtp']

        success = True

        if not config['enabled']:
            print('Please enable e-mail reporting in the config first.')
            success = False

        if config['method'] != 'smtp':
            print('Please set the method to SMTP for the e-mail reporter.')
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
            print('The SMTP password is set in the config file (key "insecure_password")')
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
        print('Successfully logged into SMTP server')

        self._exit(0)

    def check_xmpp_login(self) -> None:
        xmpp_config: ConfigReportXmpp = self.urlwatcher.config_storage.config['report']['xmpp']

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
            from playwright._impl._driver import compute_driver_executable
        except ImportError:
            raise ImportError('Python package playwright is not installed; cannot install the Chrome browser') from None

        driver_executable = compute_driver_executable()
        env = os.environ.copy()
        env['PW_CLI_TARGET_LANG'] = 'python'
        cmd = [str(driver_executable), 'install', 'chrome']
        logger.info(f"Running playwright CLI: {' '.join(cmd)}")
        completed_process = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if completed_process.returncode:
            print(completed_process.stderr)
            return completed_process.returncode
        if completed_process.stdout:
            logger.info(f'Success! Output of Playwright CLI: {completed_process.stdout}')
        return 0

    def handle_actions(self) -> None:
        """Handles the actions for command line arguments and exits."""
        if self.urlwatch_config.list:
            self.list_jobs()
            self._exit(0)

        if self.urlwatch_config.errors:
            self.list_error_jobs()
            self._exit(0)

        if self.urlwatch_config.test_job:
            self.test_job(self.urlwatch_config.test_job)
            self._exit(0)

        if self.urlwatch_config.test_diff:
            self._exit(self.test_diff(self.urlwatch_config.test_diff))

        if self.urlwatch_config.dump_history:
            sys.exit(self.dump_history(self.urlwatch_config.dump_history))

        if self.urlwatch_config.add or self.urlwatch_config.delete:
            self.modify_urls()
            self._exit(0)

        if self.urlwatch_config.test_reporter:
            self._exit(self.check_test_reporter())

        if self.urlwatch_config.smtp_login:
            self.check_smtp_login()

        if self.urlwatch_config.telegram_chats:
            self.check_telegram_chats()

        if self.urlwatch_config.xmpp_login:
            self.check_xmpp_login()

        if self.urlwatch_config.edit:
            result = self.urlwatcher.jobs_storage.edit()
            self._exit(result)

        if self.urlwatch_config.edit_config:
            self._exit(self.edit_config())

        if self.urlwatch_config.edit_hooks:
            self._exit(self.edit_hooks())

        if self.urlwatch_config.gc_database:
            self.urlwatcher.cache_storage.gc([job.get_guid() for job in self.urlwatcher.jobs])
            self.urlwatcher.cache_storage.close()
            self._exit(0)

        if self.urlwatch_config.clean_database:
            self.urlwatcher.cache_storage.clean_cache([job.get_guid() for job in self.urlwatcher.jobs])
            self.urlwatcher.cache_storage.close()
            self._exit(0)

        if self.urlwatch_config.rollback_database:
            self.urlwatcher.cache_storage.rollback_cache(self.urlwatch_config.rollback_database)
            self.urlwatcher.cache_storage.close()
            self._exit(0)

        if self.urlwatch_config.delete_snapshot:
            self._exit(self.delete_snapshot(self.urlwatch_config.delete_snapshot))

        if self.urlwatch_config.features:
            self._exit(self.show_features())

    def run(self) -> None:  # pragma: no cover
        """The main run logic."""
        self.urlwatcher.report.config = self.urlwatcher.config_storage.config

        self.handle_actions()

        self.urlwatcher.run_jobs()

        self.urlwatcher.close()

        self._exit(0)
