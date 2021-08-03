"""Take actions from command line arguments."""

import contextlib
import logging
import os
import shutil
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Union

import requests

from . import __project_name__, __docs_url__
from .filters import FilterBase
from .handler import JobState, Report
from .jobs import BrowserJob, JobBase, UrlJob
from .mailer import SMTPMailer, smtp_have_password, smtp_set_password
from .main import Urlwatch
from .reporters import ReporterBase, xmpp_have_password, xmpp_set_password
from .util import edit_file, import_module_from_source

logger = logging.getLogger(__name__)


class UrlwatchCommand:
    def __init__(self, urlwatcher: Urlwatch) -> None:
        self.urlwatcher = urlwatcher
        self.urlwatch_config = urlwatcher.urlwatch_config

    def print_new_version(self) -> None:
        """Will print alert message if a newer version is found on PyPi."""
        new_release = self.urlwatcher.get_new_release_version()
        if new_release:
            print(f'\nNew release version {new_release} is available; we recommend updating.')
        return

    def edit_hooks(self) -> int:
        """Edit hooks file.

        :returns: 0 if edit is successful, 1 otherwise.
        """
        # Similar code to BaseTextualFileStorage.edit()
        # Python 3.9: hooks_edit = self.urlwatch_config.hooks.with_stem(self.urlwatch_config.hooks.stem + '_edit')
        hooks_edit = self.urlwatch_config.hooks.parent.joinpath(
            self.urlwatch_config.hooks.stem + '_edit' + ''.join(self.urlwatch_config.hooks.suffixes)
        )
        if self.urlwatch_config.hooks.exists():
            shutil.copy(self.urlwatch_config.hooks, hooks_edit)
        # elif self.urlwatch_config.hooks_py_example is not None and os.path.exists(
        #         self.urlwatch_config.hooks_py_example):
        #     shutil.copy(self.urlwatch_config.hooks_py_example, hooks_edit, follow_symlinks=False)

        while True:
            try:
                edit_file(hooks_edit)
                import_module_from_source('hooks', hooks_edit)
                break  # stop if no exception on parser
            except SystemExit:
                self.print_new_version()
                raise
            except Exception as e:
                print()
                print('Parsing failed:')
                print('======')
                print(e)
                print('======')
                print('')
                print(f'The file {self.urlwatch_config.hooks} was NOT updated.')
                user_input = input('Do you want to retry the same edit? (Y/n)')
                if not user_input or user_input.lower()[0] == 'y':
                    continue
                hooks_edit.unlink()
                print('No changes have been saved.')
                return 1

        if self.urlwatch_config.hooks.is_symlink():
            self.urlwatch_config.hooks.write_text(hooks_edit.read_text())
        else:
            hooks_edit.replace(self.urlwatch_config.hooks)
        # python 3.8: replace with hooks_edit.unlink(missing_ok=True)
        if hooks_edit.is_file():
            hooks_edit.unlink()
        print(f'Saved edits in {self.urlwatch_config.hooks}')
        return 0

    def show_features(self) -> int:
        print()
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

        self.print_new_version()
        return 0

    def list_jobs(self) -> None:
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
        self.print_new_version()

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

        :param job_id:
        :return:
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

    def test_job(self, job_id: Union[str, int]) -> None:
        """

        :param job_id:
        :return:
        :raises Exception: The Exception of a job when job raises an Exception.
        """
        job = self._get_job(job_id)

        if isinstance(job, UrlJob):
            # Force re-retrieval of job, as we're testing filters
            job.ignore_cached = True

        with JobState(self.urlwatcher.cache_storage, job) as job_state:
            job_state.process()
            if job_state.exception is not None:
                raise job_state.exception
            print()
            print(job_state.job.pretty_name())
            print('-' * len(job_state.job.pretty_name()))
            if hasattr(job_state.job, 'note') and job_state.job.note:
                print(job_state.job.note)
            print()
            print(job_state.new_data)

        self.print_new_version()
        return

        # We do not save the job state or job on purpose here, since we are possibly modifying the job
        # (ignore_cached) and we do not want to store the newly-retrieved data yet (filter testing)

    def test_diff(self, job_id: str) -> int:
        job = self._get_job(job_id)

        history_data = list(self.urlwatcher.cache_storage.get_history_data(job.get_guid()).items())

        num_snapshots = len(history_data)
        if num_snapshots < 2:
            print('Not enough historic data available (need at least 2 different snapshots)')
            return 1

        for i in range(num_snapshots - 1):
            with JobState(self.urlwatcher.cache_storage, job) as job_state:
                job_state.old_data, job_state.old_timestamp = history_data[i + 1]
                job_state.new_data, job_state.new_timestamp = history_data[i]
                tz = self.urlwatcher.config_storage.config['report']['tz']
                print(f'=== Filtered diff between state {-i} and state {-(i + 1)} ===')
                print(job_state.get_diff(tz))

        # We do not save the job state or job on purpose here, since we are possibly modifying the job
        # (ignore_cached) and we do not want to store the newly-retrieved data yet (filter testing)

        self.print_new_version()
        return 0

    def list_error_jobs(self) -> None:
        start = time.perf_counter()
        print(
            f'Jobs, if any, with errors or returning no data after filtering.\n'
            f'Jobs file: {self.urlwatch_config.jobs}\n'
        )
        jobs = [job.with_defaults(self.urlwatcher.config_storage.config) for job in self.urlwatcher.jobs]
        for job in jobs:
            # Force re-retrieval of job, as we're testing for errors
            job.ignore_cached = True
        with contextlib.ExitStack() as stack:
            max_workers = min(32, os.cpu_count() or 1) if any(type(job) == BrowserJob for job in jobs) else None
            logger.debug(f'Max_workers set to {max_workers}')
            executor = ThreadPoolExecutor(max_workers=max_workers)

            for job_state in executor.map(
                lambda jobstate: jobstate.process(),
                (stack.enter_context(JobState(self.urlwatcher.cache_storage, job)) for job in jobs),
            ):
                if job_state.exception is not None:
                    print(f'{job_state.job.index_number:3}: Error: {job_state.exception}')
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
        dur_str = f'{float(f"{duration:.2g}"):g}' if duration < 10 else f'{duration:.0f}'
        print(f"--\nChecked {len(jobs)} job{'s' if len(jobs) else ''} in {dur_str} seconds")

        self.print_new_version()

        # We do not save the job state or job on purpose here, since we are possibly modifying the job
        # (ignore_cached) and we do not want to store the newly-retrieved data yet (just showing errors)

    def delete_snapshot(self, job_id: Union[str, int]) -> None:
        job = self._get_job(job_id)

        deleted = self.urlwatcher.cache_storage.delete_latest(job.get_guid())
        self.print_new_version()
        if deleted:
            print(f'Deleted last snapshot of {job.get_indexed_location()}')
            self.print_new_version()
            sys.exit(0)
        else:
            print(f'No snapshots found to be deleted for {job.get_indexed_location()}')
            self.print_new_version()
            sys.exit(1)

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

        self.print_new_version()

    def check_edit_config(self) -> None:
        result = self.urlwatcher.config_storage.edit()
        self.print_new_version()
        sys.exit(result)

    def check_telegram_chats(self) -> None:
        config = self.urlwatcher.config_storage.config['report'].get('telegram')

        bot_token = config.get('bot_token')
        if not bot_token:
            print('You need to set up your bot token first (see documentation)')
            self.print_new_version()
            sys.exit(1)

        info = requests.get(f'https://api.telegram.org/bot{bot_token}/getMe').json()
        if not info['ok']:
            print(f"Error with token {bot_token}: {info['description']}")
            self.print_new_version()
            sys.exit(1)

        chats = {}
        for chat_info in requests.get(f'https://api.telegram.org/bot{bot_token}/getUpdates').json()['result']:
            chat = chat_info['message']['chat']
            if chat['type'] == 'private':
                chats[chat['id']] = (
                    ' '.join((chat['first_name'], chat['last_name'])) if 'last_name' in chat else chat['first_name']
                )

        if not chats:
            print(f"No chats found. Say hello to your bot at https://t.me/{info['result']['username']}")
            self.print_new_version()
            sys.exit(1)

        headers = ('Chat ID', 'Name')
        maxchat = max(len(headers[0]), max((len(k) for k, v in chats.items()), default=0))
        maxname = max(len(headers[1]), max((len(v) for k, v in chats.items()), default=0))
        fmt = f'%-{maxchat}s  %s'
        print(fmt % headers)
        print(fmt % ('-' * maxchat, '-' * maxname))
        for k, v in sorted(chats.items(), key=lambda kv: kv[1]):
            print(fmt % (k, v))
        print(f"\nChat up your bot here: https://t.me/{info['result']['username']}")

        self.print_new_version()
        sys.exit(0)

    def check_test_reporter(self) -> None:
        name = self.urlwatch_config.test_reporter

        if name not in ReporterBase.__subclasses__:
            print(f'No such reporter: {name}')
            print(f'\nSupported reporters:\n{ReporterBase.reporter_documentation()}\n')
            self.print_new_version()
            sys.exit(1)

        cfg = self.urlwatcher.config_storage.config['report'].get(name, {'enabled': False})
        if not cfg.get('enabled', False):
            print(f'Reporter is not enabled/configured: {name}')
            print(f'Use {__project_name__} --edit-config to configure reporters')
            self.print_new_version()
            sys.exit(1)

        report = Report(self.urlwatcher)

        def build_job(job_name: str, url: str, old: str, new: str) -> JobState:
            job = JobBase.unserialize({'name': job_name, 'url': url})

            # Can pass in None for cache_storage, as we are not going to load or save the job state for
            # testing; also no need to use it as context manager, since no processing is called on the job
            job_state = JobState(None, job)  # type: ignore[arg-type]

            job_state.old_data = old
            job_state.old_timestamp = 1605147837.511478  # initial release of webchanges!
            job_state.new_data = new
            job_state.new_timestamp = 1605147837.511478

            return job_state

        def set_error(job_state: 'JobState', message: str) -> JobState:
            try:
                raise ValueError(message)
            except ValueError as e:
                job_state.exception = e
                job_state.traceback = job_state.job.format_error(e, traceback.format_exc())

            return job_state

        report.new(build_job('Newly Added', 'http://example.com/new', '', ''))
        report.changed(
            build_job(
                'Something Changed',
                'http://example.com/changed',
                'Unchanged Line\nPrevious Content\nAnother Unchanged Line\n',
                'Unchanged Line\nUpdated Content\nAnother Unchanged Line\n',
            )
        )
        report.unchanged(
            build_job('Same As Before', 'http://example.com/unchanged', 'Same Old, Same Old\n', 'Same Old, Same Old\n')
        )
        report.error(set_error(build_job('Error Reporting', 'http://example.com/error', '', ''), 'Oh Noes!'))

        report.finish_one(name)

        self.print_new_version()
        sys.exit(0)

    def check_smtp_login(self) -> None:
        config = self.urlwatcher.config_storage.config['report']['email']
        smtp_config = config['smtp']

        success = True

        if not config.get('enabled'):
            print('Please enable e-mail reporting in the config first.')
            success = False

        if config.get('method') != 'smtp':
            print('Please set the method to SMTP for the e-mail reporter.')
            success = False

        smtp_auth = smtp_config.get('auth')
        if not smtp_auth:
            print('Authentication must be enabled for SMTP.')
            success = False

        smtp_hostname = smtp_config.get('host')
        if not smtp_hostname:
            print('Please configure the SMTP hostname in the config first.')
            success = False

        smtp_username = smtp_config.get('user') or config['from']
        if not smtp_username:
            print('Please configure the SMTP user in the config first.')
            success = False

        if not success:
            self.print_new_version()
            sys.exit(1)

        insecure_password = smtp_config.get('insecure_password')
        if insecure_password:
            print('The SMTP password is set in the config file (key "insecure_password")')
        elif smtp_have_password(smtp_hostname, smtp_username):
            message = f'Password for {smtp_username} / {smtp_hostname} already set, update? [y/N] '
            if not input(message).lower().startswith('y'):
                print('Password unchanged.')
            else:
                smtp_set_password(smtp_hostname, smtp_username)

        smtp_port = smtp_config.get('port')
        smtp_tls = smtp_config.get('starttls')

        mailer = SMTPMailer(smtp_username, smtp_hostname, smtp_port, smtp_tls, smtp_auth, insecure_password)
        print('Trying to log into the SMTP server...')
        mailer.send(None)
        print('Successfully logged into SMTP server')

        self.print_new_version()
        sys.exit(0)

    def check_xmpp_login(self) -> None:
        xmpp_config = self.urlwatcher.config_storage.config['report']['xmpp']

        success = True

        if not xmpp_config['enabled']:
            print('Please enable XMPP reporting in the config first.')
            success = False

        xmpp_sender = xmpp_config.get('sender')
        if not xmpp_sender:
            print('Please configure the XMPP sender in the config first.')
            success = False

        if not xmpp_config.get('recipient'):
            print('Please configure the XMPP recipient in the config first.')
            success = False

        if not success:
            self.print_new_version()
            sys.exit(1)

        if 'insecure_password' in xmpp_config:
            print('The XMPP password is already set in the config (key "insecure_password").')
            self.print_new_version()
            sys.exit(0)

        if xmpp_have_password(xmpp_sender):
            message = f'Password for {xmpp_sender} already set, update? [y/N] '
            if input(message).lower() != 'y':
                print('Password unchanged.')
                self.print_new_version()
                sys.exit(0)

        if success:
            xmpp_set_password(xmpp_sender)

        self.print_new_version()
        sys.exit(0)

    def handle_actions(self) -> None:
        if self.urlwatch_config.features:
            sys.exit(self.show_features())
        if self.urlwatch_config.gc_cache:
            self.urlwatcher.cache_storage.gc([job.get_guid() for job in self.urlwatcher.jobs])
            self.urlwatcher.cache_storage.close()
            sys.exit(0)
        if self.urlwatch_config.clean_cache:
            self.urlwatcher.cache_storage.clean_cache([job.get_guid() for job in self.urlwatcher.jobs])
            self.urlwatcher.cache_storage.close()
            sys.exit(0)
        if self.urlwatch_config.delete_snapshot:
            self.delete_snapshot(self.urlwatch_config.delete_snapshot)
            sys.exit(0)
        if self.urlwatch_config.rollback_cache:
            self.urlwatcher.cache_storage.rollback_cache(self.urlwatch_config.rollback_cache)
            self.urlwatcher.cache_storage.close()
            sys.exit(0)
        if self.urlwatch_config.edit:
            result = self.urlwatcher.jobs_storage.edit()
            self.print_new_version()
            sys.exit(result)
        if self.urlwatch_config.edit_hooks:
            sys.exit(self.edit_hooks())
        if self.urlwatch_config.test_job:
            self.test_job(self.urlwatch_config.test_job)
            sys.exit(0)
        if self.urlwatch_config.test_diff:
            sys.exit(self.test_diff(self.urlwatch_config.test_diff))
        if self.urlwatch_config.errors:
            self.list_error_jobs()
            sys.exit(0)
        if self.urlwatch_config.list:
            self.list_jobs()
            sys.exit(0)
        if self.urlwatch_config.add or self.urlwatch_config.delete:
            self.modify_urls()
            sys.exit(0)

    def run(self) -> None:  # pragma: no cover
        if self.urlwatch_config.edit_config:
            self.check_edit_config()
        if self.urlwatch_config.smtp_login:
            self.check_smtp_login()
        if self.urlwatch_config.telegram_chats:
            self.check_telegram_chats()
        if self.urlwatch_config.xmpp_login:
            self.check_xmpp_login()
        if self.urlwatch_config.test_reporter:
            self.check_test_reporter()

        self.handle_actions()

        self.urlwatcher.run_jobs()

        self.urlwatcher.close()

        self.print_new_version()
