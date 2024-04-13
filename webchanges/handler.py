"""Handles the running of jobs and, afterward, of the reports."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import logging
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.
import time
import traceback
from concurrent.futures import Future
from pathlib import Path
from types import TracebackType
from typing import Any, ContextManager, Iterator, Literal, NamedTuple, Optional, TYPE_CHECKING, Union

from webchanges.differs import DifferBase
from webchanges.filters import FilterBase
from webchanges.jobs import NotModifiedError
from webchanges.reporters import ReporterBase

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.jobs import JobBase
    from webchanges.main import Urlwatch
    from webchanges.storage import _Config, CacheStorage

logger = logging.getLogger(__name__)


class SnapshotShort(NamedTuple):
    """Type for value of snapshot dict object.

    * 0: timestamp: float
    * 1: tries: int
    * 2: etag: str
    """

    timestamp: float
    tries: int
    etag: str


class JobState(ContextManager):
    """The JobState class, which contains run information about a job."""

    _http_client_used: Optional[str] = None
    error_ignored: Union[bool, str]
    exception: Optional[Exception] = None
    generated_diff: dict[Literal['text', 'markdown', 'html'], str]
    history_dic_snapshots: dict[str, SnapshotShort] = {}
    new_data: str
    new_etag: str
    new_timestamp: float
    old_data: str = ''
    old_etag: str = ''
    old_timestamp: float = 1605147837.511478  # initialized to the first release of webchanges!
    traceback: str
    tries: int = 0  # if >1, an error; value is the consecutive number of runs leading to an error
    unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] = {}
    verb: Literal['new', 'changed', 'changed,no_report', 'unchanged', 'error']

    def __init__(self, cache_storage: CacheStorage, job: JobBase) -> None:
        """
        Initializes the class

        :param cache_storage: The CacheStorage object with the snapshot database methods.
        :param job: A JobBase object with the job information.
        """
        self.cache_storage = cache_storage
        self.job = job

        self.generated_diff = {}
        self.unfiltered_diff = {}

    def __enter__(self) -> 'JobState':
        """Context manager invoked on entry to the body of a with statement to make it possible to factor out standard
        uses of try/finally statements. Calls the main_thread_enter method of the Job.

        :returns: Class object.
        """
        # Below is legacy code that now does nothing, so it's being skipped
        # try:
        #     self.job.main_thread_enter()
        # except Exception as e:
        #     logger.info(f'Job {self.job.index_number}: Exception while creating resources for job', exc_info=True)
        #     self.exception = e
        #     self.traceback = self.job.format_error(e, traceback.format_exc())

        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Context manager invoked on exit from the body of a with statement to make it possible to factor out standard
        uses of try/finally statements. Calls the main_thread_exit() method of the Job.

        :returns: None.
        """
        # Below is legacy code that now does nothing, so it's being skipped
        # try:
        #     self.job.main_thread_exit()
        # except Exception:
        #     # We don't want exceptions from releasing resources to override job run results
        #     logger.warning(f'Job {self.index_number}: Exception while releasing resources for job', exc_info=True)
        if isinstance(exc_value, subprocess.CalledProcessError):
            raise subprocess.SubprocessError(exc_value.stderr)
        elif isinstance(exc_value, FileNotFoundError):
            raise OSError(exc_value)
        return None

    def added_data(self) -> dict[str, Optional[Union[bool, str, Exception, float]]]:
        """Returns a dict with the data added in the processing of the job."""
        attrs = ('error_ignored', 'exception', 'new_data', 'new_etag', 'new_timestamp')
        return {attr: getattr(self, attr) for attr in attrs if hasattr(self, attr)}

    def load(self) -> None:
        """Loads form the database the last snapshot(s) for the job."""
        guid = self.job.get_guid()
        self.old_data, self.old_timestamp, self.tries, self.old_etag = self.cache_storage.load(guid)
        if self.job.compared_versions and self.job.compared_versions > 1:
            self.history_dic_snapshots = {
                s.data: SnapshotShort(s.timestamp, s.tries, s.etag)
                for s in self.cache_storage.get_history_snapshots(guid, self.job.compared_versions)
            }

    def save(self, use_old_data: bool = False) -> None:
        """Saves new data retrieved by the job into the snapshot database.

        :param use_old_data: Whether old data (and ETag) should be used (e.g. due to error, leading to new data or
           data being an error message instead of the relevant data).
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

    def process(self, headless: bool = True) -> JobState:
        """Processes the job: loads it (i.e. runs it) and handles Exceptions (errors).

        :returns: a JobState object containing information of the job run.
        """
        logger.info(f'{self.job.get_indexed_location()} started processing ({type(self.job).__name__})')
        logger.debug(f'Job {self.job.index_number}: {self.job}')

        if self.exception:
            self.new_timestamp = time.time()
            logger.info(f'{self.job.get_indexed_location()} ended processing due to exception: {self.exception}')
            return self

        try:
            try:
                self.load()

                self.new_timestamp = time.time()
                data, self.new_etag = self.job.retrieve(self, headless)
                logger.debug(f'Job {self.job.index_number}: Retrieved data {dict(data=data, new_etag=self.new_etag)}')

                # Apply automatic filters first
                filtered_data = FilterBase.auto_process(self, data)

                # Apply any specified filters
                for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.filter, self.job.index_number):
                    filtered_data = FilterBase.process(filter_kind, subfilter, self, filtered_data)

                self.new_data = str(filtered_data)

            except Exception as e:
                # Job has a chance to format and ignore its error
                self.exception = e
                self.traceback = self.job.format_error(e, traceback.format_exc())
                self.error_ignored = self.job.ignore_error(e)
                if not (self.error_ignored or isinstance(e, NotModifiedError)):
                    self.tries += 1
                    logger.info(
                        f'Job {self.job.index_number}: Job ended with error; incrementing cumulative error runs to '
                        f'{self.tries}'
                    )
        except Exception as e:
            # Job failed its chance to handle error
            self.exception = e
            self.traceback = self.job.format_error(e, traceback.format_exc())
            self.error_ignored = False
            if not isinstance(e, NotModifiedError):
                self.tries += 1
                logger.info(
                    f'Job {self.job.index_number}: Job ended with error (internal handling failed); incrementing '
                    f'cumulative error runs to {self.tries}'
                )

        logger.debug(f'Job {self.job.index_number}: Processed as {self.added_data()}')
        logger.info(f'{self.job.get_indexed_location()} ended processing')
        return self

    def get_diff(
        self,
        report_kind: Literal['text', 'markdown', 'html'] = 'text',
        differ: Optional[dict[str, Any]] = None,
        tz: Optional[str] = None,
    ) -> str:
        """Generates the job's diff and applies diff_filters to it (if any). Memoized.

        :parameter report_kind: the kind of report that needs the differ.
        :parameter differ: the name of the differ to override self.job.differ.
        :parameter tz: The IANA tz_info name of the timezone to use for diff in the job's report (e.g. 'Etc/UTC').
        :returns: The job's diff.
        """
        # generated_diff must be initialized as None
        if self.generated_diff is not {} and report_kind in self.generated_diff:
            return self.generated_diff[report_kind]

        if self.generated_diff is {} or report_kind not in self.unfiltered_diff:
            differ_kind, subdiffer = DifferBase.normalize_differ(differ or self.job.differ, self.job.index_number)
            unfiltered_diff = DifferBase.process(differ_kind, subdiffer, self, report_kind, tz, self.unfiltered_diff)
            self.unfiltered_diff.update(unfiltered_diff)
        _generated_diff = self.unfiltered_diff[report_kind]
        if _generated_diff:
            # Apply any specified diff_filters
            for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.diff_filter, self.job.index_number):
                _generated_diff = FilterBase.process(filter_kind, subfilter, self, _generated_diff)
        self.generated_diff[report_kind] = _generated_diff

        return self.generated_diff[report_kind]


class Report:
    """The base class for reporting."""

    job_states: list[JobState] = []
    new_release_future: Optional[Future[Union[str, bool]]] = None
    start: float = time.perf_counter()

    def __init__(self, urlwatch: Urlwatch) -> None:
        """

        :param urlwatch: The Urlwatch object with the program configuration information.
        """
        self.config: _Config = urlwatch.config_storage.config

    def _result(
        self,
        verb: Literal['new', 'changed', 'changed,no_report', 'unchanged', 'error'],
        job_state: JobState,
    ) -> None:
        """Logs error and appends the verb to the job_state.

        :param verb: Description of the result of the job run. Can be one of 'new', 'changed', 'changed,no_report',
        'unchanged', 'error', which have a meaning, or a custom message such as 'test'.
        :param job_state: The JobState object with the information of the job run.
        """
        if job_state.exception is not None and job_state.exception is not NotModifiedError:
            logger.info(
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
        """Sets the verb of the job in job_state to 'changed,no_report'. Called by :py:func:`run_jobs` and tests.

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

    def custom(
        self,
        job_state: JobState,
        label: Literal['new', 'changed', 'changed,no_report', 'unchanged', 'error'],
    ) -> None:
        """Sets the verb of the job in job_state to a custom label. Called by
        :py:func:`UrlwatchCommand.check_test_reporter`.

        :param job_state: The JobState object with the information of the job run.
        :param label: The label to set the information of the job run to.
        """
        self._result(label, job_state)

    def get_filtered_job_states(self, job_states: list[JobState]) -> Iterator[JobState]:
        """Returns JobStates that have reportable changes per config['display'].  Called from :py:Class:`ReporterBase`.

        :param job_states: The list of JobState objects with the information of the job runs.
        :returns: An iterable of JobState objects that have reportable changes per config['display'].
        """
        for job_state in job_states:
            if (
                not any(
                    job_state.verb == verb and not self.config['display'][verb]  # type: ignore[literal-required]
                    for verb in {'unchanged', 'new', 'error'}
                )
                and job_state.verb != 'changed,no_report'
            ):
                if (
                    job_state.verb == 'changed'
                    and not self.config['display'].get('empty-diff', True)
                    and job_state.get_diff() == ''
                ):
                    continue

                yield job_state

    def finish(self, jobs_file: Optional[list[Path]] = None) -> None:
        """Finish job run: determine its duration and generate reports by submitting job_states to
        :py:Class:`ReporterBase` :py:func:`submit_all`.

        :param jobs_file: The path to the file containing the list of jobs (optional, used in footers).
        """
        end = time.perf_counter()
        duration = end - self.start

        ReporterBase.submit_all(self, self.job_states, duration, jobs_file)

    def finish_one(
        self, name: str, jobs_file: Optional[list[Path]] = None, check_enabled: Optional[bool] = True
    ) -> None:
        """Finish job run of one: determine its duration and generate reports by submitting job_states to
        :py:Class:`ReporterBase` :py:func:`submit_one`.  Used in testing.

        :param name: The name of the reporter to run.
        :param jobs_file: The path to the file containing the list of jobs (optional, used in footers).
        :param check_enabled: If True (default), run reports only if they are enabled in the configuration.
        """
        end = time.perf_counter()
        duration = end - self.start

        ReporterBase.submit_one(name, self, self.job_states, duration, jobs_file, check_enabled)
