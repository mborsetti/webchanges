"""Handles the running of jobs and, afterward, of the reports."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

__lazy_modules__ = ['subprocess', 'traceback', 'zoneinfo']

import logging
import os
import subprocess
import sys
import time
import traceback
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Self, TypedDict
from zoneinfo import ZoneInfo

from webchanges.differs import DifferBase, ReportKind
from webchanges.filters import FilterBase
from webchanges.jobs import EMPTY_RESPONSE_STATUS_CODE, NotModifiedError, TransientHTTPError
from webchanges.reporters import ReporterBase

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from collections.abc import Iterator
    from concurrent.futures import Future
    from datetime import tzinfo
    from pathlib import Path
    from types import TracebackType

    from webchanges.jobs import JobBase
    from webchanges.main import Urlwatch
    from webchanges.storage import SsdbStorage, _Config, _ConfigDifferDefaults

logger = logging.getLogger(__name__)


class Snapshot(NamedTuple):
    """Type for Snapshot named tuple.

    * 0: data: str | bytes
    * 1: timestamp: float
    * 2: tries: int
    * 3: etag: str
    * 4: mime_type: mime_type
    * 5: error: ErrorData
    """

    data: str | bytes
    timestamp: float
    tries: int
    etag: str
    mime_type: str
    error_data: ErrorData


Verb = Literal[
    'new',  # new job
    'changed',  # valid data received, and it has changed
    'changed,no_report',  # valid data received, and it has changed, but filtered diff yields no report
    'unchanged',  # valid data received, no changes
    'unchanged,error_ended',  # valid data received, no changes from the last data received before an error
    'error',  # error, prior state was different (either data or different error)
    'error,repeated',  # error, same as before
]


class ErrorData(TypedDict, total=False):
    """An exception's type and message, as saved with the snapshot."""

    type: str
    message: str


class JobState(AbstractContextManager):
    """The JobState class, which contains run information about a job."""

    _http_client_used: Literal['httpx2', 'requests', 'curl_cffi', 'playwright'] | None = None
    error_ignored: bool
    exception: Exception | None = None
    generated_diff: dict[ReportKind, str]
    history_dic_snapshots: dict[str | bytes, Snapshot]
    new_data: str | bytes = ''
    new_error_data: ErrorData = {}
    new_etag: str = ''
    new_mime_type: str = ''
    new_timestamp: float
    old_snapshot = Snapshot(
        data='',
        timestamp=1605147837.511478,  # initialized to the first release of webchanges!
        tries=0,
        etag='',
        mime_type='text/plain',
        error_data={},
    )
    old_data: str | bytes = ''
    old_error_data: ErrorData = {}
    old_etag: str = ''
    old_mime_type: str = 'text/plain'
    old_timestamp: float = 1605147837.511478  # initialized to the first release of webchanges!
    reported_count: int = 0  # the number of reporters this job was submitted to (see ReporterBase.submit_one)
    traceback: str
    tries: int = 0  # if >1, an error; value is the consecutive number of runs leading to an error
    unfiltered_diff: dict[ReportKind, str]
    verb: Verb

    def __init__(self, snapshots_db: SsdbStorage, job: JobBase) -> None:
        """Initializes the class.

        :param snapshots_db: The SsdbStorage object with the snapshot database methods.
        :param job: A JobBase object with the job information.
        """
        self.snapshots_db = snapshots_db
        self.job: JobBase = job

        self.generated_diff = {}
        self.unfiltered_diff = {}
        self.history_dic_snapshots = {}

    def __enter__(self) -> Self:
        """Context manager invoked on entry to the body of a with statement.

        :returns: Class object.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        """Context manager invoked on exit from the body of a with statement.

        :returns: None.
        """
        return None

    @staticmethod
    def debugging_session() -> bool:
        """Checks if running within an external debugger (e.g. IDE) and *NOT* in a testing environment.

        :returns: True if an external debugger is attached and it's not a pytest session, False otherwise.
        """
        return sys.breakpointhook.__module__ != 'sys' and 'PYTEST_CURRENT_TEST' not in os.environ

    def added_data(self) -> dict[str, bool | str | Exception | float | None]:
        """Returns a dict with the data added in the processing of the job."""
        attrs = ('error_ignored', 'exception', 'new_data', 'new_etag', 'new_timestamp')
        return {attr: getattr(self, attr) for attr in attrs if hasattr(self, attr)}

    def load(self) -> None:
        """Loads form the database the last snapshot(s) for the job."""
        guid = self.job.guid
        self.old_snapshot = self.snapshots_db.load(guid)
        # TODO: Remove these
        (
            self.old_data,
            self.old_timestamp,
            self.tries,
            self.old_etag,
            self.old_mime_type,
            self.old_error_data,
        ) = self.old_snapshot
        if self.job.compared_versions and self.job.compared_versions > 1:
            self.history_dic_snapshots = {
                s.data: s for s in self.snapshots_db.get_history_snapshots(guid, self.job.compared_versions)
            }

    def save(self) -> None:
        """Saves new data retrieved by the job into the snapshot database."""
        if self.new_error_data:  # have encountered an exception, so save the old data
            new_snapshot = Snapshot(
                data=self.old_data,
                timestamp=self.new_timestamp,
                tries=self.tries,
                etag=self.old_etag,
                mime_type=self.old_mime_type,
                error_data=self.new_error_data,
            )
        else:
            new_snapshot = Snapshot(
                data=self.new_data,
                timestamp=self.new_timestamp,
                tries=self.tries,
                etag=self.new_etag,
                mime_type=self.new_mime_type,
                error_data=self.new_error_data,
            )
        self.snapshots_db.save(guid=self.job.guid, snapshot=new_snapshot)
        logger.info('Job %s: Saved new data to database', self.job.index_number)

    def delete_latest(self, temporary: bool = True) -> None:
        """Removes the last instance in the snapshot database."""
        self.snapshots_db.delete_latest(guid=self.job.guid, temporary=temporary)

    def _raise_if_empty(self, data: str | bytes, what: str) -> None:
        """Raises the error of the empty_as_error directive if the data is empty or consists only of whitespace.

        :param data: The data retrieved or filtered.
        :param what: The description of the condition, used in the log and in the error message.
        :raises TransientHTTPError: With the synthetic status code EMPTY_RESPONSE_STATUS_CODE, if the data is empty.
        """
        stripped = data.strip() if isinstance(data, (str, bytes)) else data
        if not stripped:
            logger.info('Job %s: %s; treating it as an error.', self.job.index_number, what)
            raise TransientHTTPError(f'{what} and empty_as_error is set', status_code=EMPTY_RESPONSE_STATUS_CODE)

    def process(self, headless: bool = True) -> JobState:
        """Processes the job: loads it (i.e. runs it) and handles Exceptions (errors).

        :returns: a JobState object containing information of the job run.
        """
        logger.info('%s started processing (%s)', self.job.get_indexed_location(), type(self.job).__name__)
        logger.debug('Job %s: %s', self.job.index_number, self.job)

        if self.exception and not isinstance(self.exception, NotModifiedError):
            self.new_timestamp = time.time()
            self.new_error_data = {'type': type(self.exception).__name__, 'message': str(self.exception)}
            logger.info('%s ended processing due to exception: %s', self.job.get_indexed_location(), self.exception)
            return self

        try:
            self.load()

            self.new_timestamp = time.time()
            data, self.new_etag, mime_type = self.job.retrieve(self, headless)
            logger.info('Job %s: Retrieved %s bytes of %s content.', self.job.index_number, len(data), mime_type)

            logger.debug(
                'Job %s: Retrieved data=%r | etag=%s | mime_type=%s',
                self.job.index_number,
                data,
                self.new_etag,
                mime_type,
            )

            # An empty (or whitespace-only) response is treated as an error when empty_as_error is set, so that the
            # last non-empty snapshot is retained instead of being overwritten. The check is made here, before
            # filtering, so that it applies to every job kind including those defined in hooks.py, and again after
            # filtering, as a filter (e.g. an xpath matching nothing on a page that did not render fully) can leave
            # nothing. BrowserJob makes its own, earlier check against the raw network body, as its rendered page
            # source is never empty.
            if self.job.empty_as_error:
                self._raise_if_empty(data, 'No data received')

            # Apply automatic filters first
            filtered_data, mime_type = FilterBase.auto_process(self, data, mime_type)

            # Apply any specified filters
            for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.filters, self.job.index_number):
                filtered_data, mime_type = FilterBase.process(filter_kind, subfilter, self, filtered_data, mime_type)

            if self.job.empty_as_error:
                self._raise_if_empty(filtered_data, 'No data left after filtering')

            self.new_data = filtered_data
            self.new_mime_type = mime_type

        except NotModifiedError as e:
            # HTTP 304 response has been received
            self.exception = e
            self.error_ignored = False
            # Nothing was retrieved, so carry the last snapshot forward: worker.run_jobs saves the job state when a
            # 304 arrives after a failed run (to reset 'tries'), and save() would otherwise store the empty new_data.
            self.new_data = self.old_data
            self.new_etag = self.old_etag
            self.new_mime_type = self.old_mime_type
        except Exception as e:
            # Processing error of job failed its chance to handle error
            # Job has a chance to format and ignore its error
            if self.debugging_session():
                logger.warning('Running in a debugging session: raising the exception instead of processing it')
                raise
            self.exception = e
            self.error_ignored = self.job.ignore_error(e) or (
                self.job.empty_as_error == 'ignore'
                and isinstance(e, TransientHTTPError)
                and e.status_code == EMPTY_RESPONSE_STATUS_CODE
            )
            if not self.error_ignored:
                self.new_timestamp = time.time()
                # Check for specific exception types to provide more detailed tracebacks
                if self.job.__class__.__module__ == 'hooks':
                    logger.info('Job is from hooks.py: including full traceback in error message')
                    self.traceback = ''.join(traceback.format_exception(e)).rstrip()
                elif isinstance(e, subprocess.CalledProcessError):
                    self.traceback = (
                        f'subprocess.CalledProcessError: Command returned non-zero exit status {e.returncode}.\n\n'
                        + '\n'.join(filter(None, (e.stderr, e.stdout)))
                    )
                else:
                    # Generic traceback for other exceptions
                    self.traceback = self.job.format_error(e, traceback.format_exc())

                self.tries += 1
                self.new_error_data = {
                    'type': '.'.join(filter(None, [getattr(e, '__module__', None), e.__class__.__name__])),
                    'message': str(e),
                }
                logger.info(
                    'Job %s: Job ended with an error; incrementing cumulative error runs to %s',
                    self.job.index_number,
                    self.tries,
                )

        logger.debug('Job %s: Processed as %s', self.job.index_number, self.added_data())
        logger.info('%s ended processing', self.job.get_indexed_location())
        return self

    def get_diff(
        self,
        report_kind: ReportKind = 'plain',
        differ: dict[str, Any] | None = None,
        differ_defaults: _ConfigDifferDefaults | None = None,
        tz: tzinfo | None = None,
    ) -> str:
        """Generates the job's diff and applies diff_filters to it (if any). Memoized.

        :parameter report_kind: the kind of report that needs the differ.
        :parameter differ: the name of the differ to override self.job.differ.
        :parameter tz: The IANA tz_info name of the timezone to use for diff in the job's report (e.g. 'Etc/UTC').
        :returns: The job's diff.
        """
        if report_kind in self.generated_diff:
            return self.generated_diff[report_kind]

        if report_kind not in self.unfiltered_diff:
            differ_kind, subdiffer = DifferBase.normalize_differ(
                differ or self.job.differ,
                self.job.index_number,
                differ_defaults,
            )
            unfiltered_diff = DifferBase.process(differ_kind, subdiffer, self, report_kind, tz, self.unfiltered_diff)
            self.unfiltered_diff.update(unfiltered_diff)
        _generated_diff = self.unfiltered_diff[report_kind]
        if _generated_diff:
            # Apply any specified diff_filters
            _mime_type = 'text/plain'
            for filter_kind, subfilter in FilterBase.normalize_filter_list(
                self.job.diff_filters, self.job.index_number
            ):
                _generated_diff, _mime_type = FilterBase.process(
                    filter_kind, subfilter, self, _generated_diff, _mime_type
                )
        self.generated_diff[report_kind] = str(_generated_diff)

        return self.generated_diff[report_kind]

    def is_markdown(self) -> bool:
        """Returns whether the new data is in markdown."""
        return self.new_mime_type == 'text/markdown' or bool(self.job.is_markdown)

    def is_rst(self) -> bool:
        """Returns whether the new data is in rst."""
        return self.new_mime_type == 'text/x-rst' or bool(self.job.is_rst)


class Report:
    """The base class for reporting."""

    new_release_future: Future[str | bool] | None = None
    reporters_enabled: bool = False  # set by finish()/finish_one(): whether at least one reporter ran
    start: float = time.perf_counter()

    def __init__(self, urlwatch: Urlwatch) -> None:
        """:param urlwatch: The Urlwatch object with the program configuration information."""
        # instance attribute: a class-level list would be shared (and polluted) across all Report objects
        self.job_states: list[JobState] = []
        self.config: _Config = urlwatch.config_storage.config
        self.tz = (
            ZoneInfo(self.config['report']['tz'])
            if 'report' in self.config and self.config['report']['tz'] is not None
            else None
        )

    def _result(
        self,
        verb: Verb,
        job_state: JobState,
    ) -> None:
        """Logs error and appends the verb to the job_state.

        :param verb: Description of the result of the job run. Can be one of
          • 'new': new job;
          • 'changed': valid data received, and it has changed;
          • 'changed,no_report': valid data received, and it has changed, but no report;
          • 'unchanged': valid data received, no changes;
          • 'unchanged,error_ended': valid data received, no changes from the last data received before an error;
          • 'error': error, prior state was different (either data or different error);
          • 'error,repeated': error, same as before;
        or a custom message such as  'test'.  Ultimately called by job_runner.

        :param job_state: The JobState object with the information of the job run.
        """
        if job_state.exception is not None:
            logger.info(
                'Job %s: Got exception while processing job %s',
                job_state.job.index_number,
                job_state.job,
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

    def unchanged_from_error(self, job_state: JobState) -> None:
        """Sets the verb of the job in job_state to 'unchanged'. Called by :py:func:`run_jobs` and tests.

        :param job_state: The JobState object with the information of the job run.
        """
        self._result('unchanged,error_ended', job_state)

    def error(self, job_state: JobState) -> None:
        """Sets the verb of the job in job_state to 'error'. Called by :py:func:`run_jobs` and tests.

        :param job_state: The JobState object with the information of the job run.
        """
        self._result('error', job_state)

    def error_same_error(self, job_state: JobState) -> None:
        """Sets the verb of the job in job_state to 'error'. Called by :py:func:`run_jobs` and tests.

        :param job_state: The JobState object with the information of the job run.
        """
        self._result('error,repeated', job_state)

    def custom(
        self,
        job_state: JobState,
        label: Verb,
    ) -> None:
        """Sets the verb of the job in job_state to a custom label.

        Called by :py:func:`UrlwatchCommand.check_test_reporter`.

        :param job_state: The JobState object with the information of the job run.
        :param label: The label to set the information of the job run to.
        """
        self._result(label, job_state)

    def get_filtered_job_states(self, job_states: list[JobState]) -> Iterator[JobState]:
        """Returns JobStates that have reportable changes per config['display'].  Called from :py:Class:`ReporterBase`.

        :param job_states: The list of JobState objects with the information of the job runs.
        :returns: An iterable of JobState objects that have reportable changes per config['display'].
        """

        def job_is_reportable(self: Report, job_state: JobState) -> bool:
            """Whether the job should be reported, given its verb, sub-directives and the reporters' configuration."""
            logger.debug('Job %s: Checking if job is reportable (%s)', job_state.job.index_number, job_state.verb)
            display_cfg = self.config['display']
            match job_state.verb:
                case 'unchanged':
                    return display_cfg['unchanged']
                case 'changed':
                    if not display_cfg['empty-diff']:  # deprecated; should default to false
                        diff = job_state.get_diff(tz=self.tz, differ_defaults=self.config['differ_defaults'])
                        if diff == '':
                            return False
                    return True
                case 'changed,no_report':
                    # set by differ
                    return False
                case 'error':
                    if job_state.job.suppress_errors is not None:
                        return not job_state.job.suppress_errors
                    return display_cfg['error']
                case 'error,repeated':
                    if job_state.job.suppress_errors or job_state.job.suppress_repeated_errors:
                        return False
                    if job_state.job.suppress_errors is not None:  # explicitly False: overrides display config
                        return True
                    return display_cfg['error']
                case 'unchanged,error_ended':
                    if job_state.job.suppress_errors or job_state.job.suppress_error_ended:
                        return False
                    if job_state.job.suppress_errors is not None:  # explicitly False: overrides display config
                        return True
                    return display_cfg['error']
                case 'new':
                    return display_cfg['new']
                case _:
                    return True

        for job_state in job_states:
            if job_is_reportable(self, job_state):
                yield job_state

    def finish(self, jobs_file: list[Path]) -> None:
        """Finish the job run: determine its duration and generate the reports.

        Submits job_states to :py:Class:`ReporterBase` :py:func:`submit_all`.

        :param jobs_file: The path to the file containing the list of jobs (optional, used in footers).
        """
        end = time.perf_counter()
        duration = end - self.start

        self.reporters_enabled = ReporterBase.submit_all(self, self.job_states, duration, jobs_file)

    def finish_one(
        self,
        name: str,
        jobs_file: list[Path] | None = None,
        check_enabled: bool | None = True,
        apply_tags: bool = True,
    ) -> None:
        """Finish the job run for one reporter: determine its duration and generate its report.

        Submits job_states to :py:Class:`ReporterBase` :py:func:`submit_one`. Used in testing.

        :param name: The name of the reporter to run.
        :param jobs_file: The path to the file containing the list of jobs (optional, used in footers).
        :param check_enabled: If True (default), run reports only if they are enabled in the configuration.
        :param apply_tags: If True (default), honor the 'tags' directive of the reporter's configuration(s).
        """
        end = time.perf_counter()
        duration = end - self.start
        if jobs_file is None:
            jobs_file = []

        self.reporters_enabled = ReporterBase.submit_one(
            name, self, self.job_states, duration, jobs_file, check_enabled, apply_tags
        )
