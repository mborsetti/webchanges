"""Handles the running of jobs and, afterwards, of the reports."""

from __future__ import annotations

import difflib
import logging
import shlex
import subprocess
import tempfile
import time
import traceback
from concurrent.futures import Future
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, ContextManager, Dict, Iterable, List, Optional, TYPE_CHECKING, Type, Union

from .filters import FilterBase
from .jobs import NotModifiedError
from .reporters import ReporterBase

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports import zoneinfo as ZoneInfo

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from .jobs import JobBase
    from .main import Urlwatch
    from .storage import CacheStorage

logger = logging.getLogger(__name__)


class JobState(ContextManager):
    """The JobState class, which contains run information about a job."""

    verb: str
    old_data: str = ''
    new_data: str
    old_timestamp: float = 1605147837.511478  # initialized to the first release of webchanges!
    new_timestamp: float
    exception: Optional[Exception] = None
    traceback: str
    tries: int = 0
    old_etag: str = ''
    new_etag: str
    error_ignored: Union[bool, str] = False
    _generated_diff: Optional[str] = None

    def __init__(self, cache_storage: CacheStorage, job: JobBase) -> None:
        """

        :param cache_storage: The CacheStorage object with the snapshot database methods.
        :param job: A JobBase object with the job information.
        """
        self.cache_storage = cache_storage
        self.job = job

    def __enter__(self) -> 'JobState':
        """Context manager invoked on entry to the body of a with statement to make it possible to factor out standard
        uses of try/finally statements. Calls the main_thread_enter() method of the Job.

        :returns: Class object.
        """
        try:
            self.job.main_thread_enter()
        except Exception as ex:
            logger.info(f'Job {self.job.index_number}: Exception while creating resources for job', exc_info=True)
            self.exception = ex
            self.traceback = traceback.format_exc()

        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        """Context manager invoked on exit from the body of a with statement to make it possible to factor out standard
        uses of try/finally statements. Calls the main_thread_exit() method of the Job.

        :returns: None.
        """
        try:
            self.job.main_thread_exit()
        except Exception:
            # We don't want exceptions from releasing resources to override job run results
            logger.warning(f'Job {self.job.index_number}: Exception while releasing resources for job', exc_info=True)

        return

    def load(self) -> None:
        """Loads form the database the last snapshot for the job."""
        guid = self.job.get_guid()
        self.old_data, self.old_timestamp, self.tries, self.old_etag = self.cache_storage.load(guid)

    def save(self, use_old_data: bool = False) -> None:
        """Saves new data retrieved by the job into the snapshot database.

        :param use_old_data: Whether old data should be used (e.g. due to error, leading to new data or data being an
           error message instead of the relevant data). Also uses the old ETag.
        """
        if use_old_data:
            self.new_data = self.old_data
            self.new_etag = self.old_etag

        self.cache_storage.save(
            guid=self.job.get_guid(),
            data=self.new_data,
            timestamp=self.new_timestamp,
            tries=self.tries,
            etag=self.new_etag,
        )

    def process(self) -> 'JobState':
        """Processes the job: loads it (i.e. runs it) and handles Exceptions (errors).

        :returns: a JobState object containing information of the job run.
        """
        logger.info(f'Job {self.job.index_number}: Processing job {self.job}')

        if self.exception:
            return self

        try:
            try:
                self.load()

                self.new_timestamp = time.time()
                data, self.new_etag = self.job.retrieve(self)

                # Apply automatic filters first
                filtered_data = FilterBase.auto_process(self, data)

                # Apply any specified filters
                for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.filter):
                    filtered_data = FilterBase.process(filter_kind, subfilter, self, filtered_data)

                self.new_data = filtered_data

            except Exception as e:
                # Job has a chance to format and ignore its error
                self.exception = e
                self.traceback = self.job.format_error(e, traceback.format_exc())
                self.error_ignored = self.job.ignore_error(e)
                if not (self.error_ignored or isinstance(e, NotModifiedError)):
                    self.tries += 1
                    logger.debug(
                        f'Job {self.job.index_number}: Job ended with error; incrementing cumulative tries to '
                        f'{self.tries} ({str(e).strip()})'
                    )
        except Exception as e:
            # Job failed its chance to handle error
            self.exception = e
            self.traceback = traceback.format_exc()
            self.error_ignored = False
            if not isinstance(e, NotModifiedError):
                self.tries += 1
                logger.debug(
                    f'Job {self.job.index_number}: Job ended with error (internal handling failed); '
                    f'incrementing cumulative tries to {self.tries} ({str(e).strip()})'
                )

        return self

    def get_diff(self, tz: Optional[str] = None) -> str:
        """Generates the job's diff and applies diff_filters to it (if any). Memoized.

        :parameter tz: The IANA tz_info name of the timezone to use for diff in the job's report (e.g. 'Etc/UTC')
        """
        # Must be initialized as None
        if self._generated_diff is not None:
            return self._generated_diff

        _generated_diff = self._generate_diff(tz)
        if _generated_diff:
            # Apply any specified diff_filters
            for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.diff_filter):
                _generated_diff = FilterBase.process(filter_kind, subfilter, self, _generated_diff)
        self._generated_diff = _generated_diff

        return self._generated_diff

    def _generate_diff(self, tz: Optional[str] = None) -> str:
        """Generates the job's diff.

        :parameter tz: The IANA tz_info name of the timezone to use for diff in the job's report (e.g. 'Etc/UTC') (
           not used if an external diff tool is used.
        :returns: An empty string if there is no change, otherwise the diff.
        :raises RuntimeError: If the external diff tool returns an error.
        """
        if tz:
            tz_info = ZoneInfo(tz)
        else:
            tz_info = None
        timestamp_old = (
            datetime.fromtimestamp(self.old_timestamp).astimezone(tz=tz_info).strftime('%a, %d %b %Y %H:%M:%S %z')
        )
        timestamp_new = (
            datetime.fromtimestamp(self.new_timestamp).astimezone(tz=tz_info).strftime('%a, %d %b %Y %H:%M:%S %z')
        )

        if self.job.diff_tool is not None:
            # External diff tool
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                old_file_path = tmp_path.joinpath('old_file')
                new_file_path = tmp_path.joinpath('new_file')
                old_file_path.write_text(str(self.old_data))
                new_file_path.write_text(str(self.new_data))
                cmdline = shlex.split(self.job.diff_tool) + [str(old_file_path), str(new_file_path)]
                proc = subprocess.run(cmdline, capture_output=True, text=True)
                # Diff tools return 0 for "nothing changed" or 1 for "files differ", anything else is an error
                if proc.returncode == 0:
                    return ''
                elif proc.returncode == 1:
                    head = (
                        f'Using external diff tool "{self.job.diff_tool}"\n'
                        f'Old: {timestamp_old}\n'
                        f'New: {timestamp_new}\n' + '-' * 36 + '\n'
                    )
                    return head + proc.stdout
                else:
                    raise RuntimeError(proc.stderr) from subprocess.CalledProcessError(proc.returncode, cmdline)

        if self.job.contextlines is not None:
            contextlines = self.job.contextlines
        else:
            contextlines = 0 if self.job.additions_only or self.job.deletions_only else 3
        diff = list(
            difflib.unified_diff(
                str(self.old_data).splitlines(),
                str(self.new_data).splitlines(),
                '@',
                '@',
                timestamp_old,
                timestamp_new,
                contextlines,
                lineterm='',
            )
        )
        diff[0] = diff[0].replace('\t', ' ')
        diff[1] = diff[1].replace('\t', ' ')
        if self.job.additions_only:
            if len(self.old_data) and len(self.new_data) / len(self.old_data) <= 0.25:
                diff = (
                    diff[:2]
                    + ['/**Comparison type: Additions only**']
                    + ['/**Deletions are being shown as 75% or more of the content has been deleted**']
                    + diff[2:]
                )
            else:
                head = '...' + diff[0][3:]
                diff = [line for line in diff if line.startswith('+') or line.startswith('@')]
                diff = [
                    line1
                    for line1, line2 in zip([''] + diff, diff + [''])
                    if not (line1.startswith('@') and line2.startswith('@'))
                ][1:]
                diff = diff[:-1] if diff[-1].startswith('@') else diff
                if len(diff) == 1 or len([line for line in diff if line.lstrip('+').rstrip()]) == 2:
                    self.verb = 'changed,no_report'
                    return ''
                diff = [head, diff[0], '/**Comparison type: Additions only**'] + diff[1:]
        elif self.job.deletions_only:
            head = '...' + diff[1][3:]
            diff = [line for line in diff if line.startswith('-') or line.startswith('@')]
            diff = [
                line1
                for line1, line2 in zip([''] + diff, diff + [''])
                if not (line1.startswith('@') and line2.startswith('@'))
            ][1:]
            diff = diff[:-1] if diff[-1].startswith('@') else diff
            if len(diff) == 1 or len([line for line in diff if line.lstrip('-').rstrip()]) == 2:
                self.verb = 'changed,no_report'
                return ''
            diff = [diff[0], head, '/**Comparison type: Deletions only**'] + diff[1:]

        return '\n'.join(diff)


class Report(object):
    """The base class for reporting."""

    new_release_future: Future[str]

    def __init__(self, urlwatch_config: Urlwatch) -> None:
        """

        :param urlwatch_config: The Urlwatch object with the program configuration information.
        """
        self.start = time.perf_counter()

        self.config: Dict[str, Any] = urlwatch_config.config_storage.config
        self.job_states: List[JobState] = []

    def _result(self, verb: str, job_state: JobState) -> None:
        """Logs error and appends the verb to the job_state.

        :param verb: One of 'changed', 'error', 'new', 'unchanged', plus optionally 'no_report' joined by a
           comma, describing the result of the job run.
        :param job_state: The JobState object with the information of the job run.
        """
        if job_state.exception is not None and job_state.exception is not NotModifiedError:
            logger.debug(
                f'Job {job_state.job.index_number}: Got exception while processing job {job_state.job}',
                exc_info=job_state.exception,
            )

        job_state.verb = verb
        self.job_states.append(job_state)

    def new(self, job_state: JobState) -> None:
        """Sets the verb of the job in job_state to 'new'. Called by :py:func:`run_jobs` and tests.

        :param job_state: The JobState object with the information of the job run.
        """
        self._result('new', job_state)

    def changed(self, job_state: JobState) -> None:
        """Sets the verb of the job in job_state to 'changed'. Called by :py:func:`run_jobs` and tests.

        :param job_state: The JobState object with the information of the job run.
        """
        self._result('changed', job_state)

    def changed_no_report(self, job_state: JobState) -> None:
        """Sets the verb of the job in job_state to 'changed' and 'no_report. Called by :py:func:`run_jobs` and tests.

        :param job_state: The JobState object with the information of the job run.
        """
        self._result('changed,no_report', job_state)

    def unchanged(self, job_state: JobState) -> None:
        """Sets the verb of the job in job_state to 'unchanged'. Called by :py:func:`run_jobs` and tests.

        :param job_state: The JobState object with the information of the job run.
        """
        self._result('unchanged', job_state)

    def error(self, job_state: JobState) -> None:
        """Sets the verb of the job in job_state to 'error'. Called by :py:func:`run_jobs` and tests.

        :param job_state: The JobState object with the information of the job run.
        """
        self._result('error', job_state)

    def get_filtered_job_states(self, job_states: List[JobState]) -> Iterable[JobState]:
        """Returns JobStates that have reportable changes per config['display'].  Called from :py:Class:`ReporterBase`.

        :param job_state: The JobState objects with the information of the job runs.
        :returns: An iterable of JobState objects that have reportable changes per config['display'].
        """
        for job_state in job_states:
            if (
                not any(
                    job_state.verb == verb and not self.config['display'][verb]
                    for verb in ('unchanged', 'new', 'error')
                )
                and job_state.verb != 'changed,no_report'
            ):
                yield job_state

    def finish(self) -> None:
        """Finish job run: determine its duration and generate reports by submitting job_states to
        :py:Class:`ReporterBase` :py:func:`submit_all`."""
        end = time.perf_counter()
        duration = end - self.start

        ReporterBase.submit_all(self, self.job_states, duration)

    def finish_one(self, name: str, check_enabled: Optional[bool] = True) -> None:
        """Finish job run of one: determine its duration and generate reports by submitting job_states to
        :py:Class:`ReporterBase` :py:func:`submit_one`.  Used in testing.

        :param check_enabled: If True (default), run reports only if they are enabled in the configuration.
        """
        end = time.perf_counter()
        duration = end - self.start

        ReporterBase.submit_one(name, self, self.job_states, duration, check_enabled)
