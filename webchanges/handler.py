"""Handles the running of jobs and, afterwards, of the reports."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import difflib
import json
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
from typing import Any, ContextManager, Iterable, List, Optional, Type, TYPE_CHECKING, Union

from .filters import FilterBase
from .jobs import NotModifiedError
from .reporters import ReporterBase

try:
    import deepdiff
except ImportError:
    deepdiff = None  # type: ignore[no-redef]

try:
    import xmltodict
except ImportError:
    xmltodict = None  # type: ignore[no-redef]

try:
    from zoneinfo import ZoneInfo  # not available in Python < 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]


# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    # from typing import Literal  # not available in Python < 3.8

    from .jobs import JobBase
    from .main import Urlwatch
    from .storage import CacheStorage, Config

logger = logging.getLogger(__name__)


class JobState(ContextManager):
    """The JobState class, which contains run information about a job."""

    verb: str  # 'new', 'changed', 'changed,no_report', 'unchanged', 'error' are recognized
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
    _generated_diff_html: Optional[str] = None

    def __init__(self, cache_storage: CacheStorage, job: JobBase, playwright: Any = None) -> None:
        """

        :param cache_storage: The CacheStorage object with the snapshot database methods.
        :param job: A JobBase object with the job information.
        """
        self.cache_storage = cache_storage
        self.job = job
        self.playwright = playwright

    def __enter__(self) -> 'JobState':
        """Context manager invoked on entry to the body of a with statement to make it possible to factor out standard
        uses of try/finally statements. Calls the main_thread_enter method of the Job.

        :returns: Class object.
        """
        # Below is legacy code that now does nothing, so it's being skipped
        # try:
        #     self.job.main_thread_enter()
        # except Exception as ex:
        #     logger.info(f'Job {self.job.index_number}: Exception while creating resources for job', exc_info=True)
        #     self.exception = ex
        #     self.traceback = traceback.format_exc()

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
        # Below is legacy code that now does nothing, so it's being skipped
        # try:
        #     self.job.main_thread_exit()
        # except Exception:
        #     # We don't want exceptions from releasing resources to override job run results
        #     logger.warning(f'Job {self.index_number}: Exception while releasing resources for job', exc_info=True)

        return None

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

    def process(self, headless: bool = True) -> 'JobState':
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
                data, self.new_etag = self.job.retrieve(self, headless)

                # Apply automatic filters first
                filtered_data = FilterBase.auto_process(self, data)

                # Apply any specified filters
                for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.filter):
                    filtered_data = FilterBase.process(filter_kind, subfilter, self, filtered_data)

                self.new_data = str(filtered_data)

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

        :parameter tz: The IANA tz_info name of the timezone to use for diff in the job's report (e.g. 'Etc/UTC').
        :returns: The job's diff.
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

    def get_diff_html(self, tz: Optional[str] = None) -> str:
        """Generates the job's HTML diff and applies diff_filters to it (if any). Memoized.

        :parameter tz: The IANA tz_info name of the timezone to use for diff in the job's report (e.g. 'Etc/UTC').
        :returns: The job's diff.
        """
        # Must be initialized as None
        if self._generated_diff_html is not None:
            return self._generated_diff_html

        _generated_diff_html = self._generate_diff(tz, html_out=True)
        if _generated_diff_html:
            # Apply any specified diff_filters
            for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.diff_filter):
                _generated_diff_html = FilterBase.process(filter_kind, subfilter, self, _generated_diff_html)
        self._generated_diff_html = _generated_diff_html

        return self._generated_diff_html

    def _generate_diff(self, tz: Optional[str] = None, html_out: bool = False) -> str:
        """Generates the job's diff.

        :parameter tz: The IANA tz_info name of the timezone to use for diff in the job's report (e.g. 'Etc/UTC') (
           not used if an external diff tool is used.
        :returns: An empty string if there is no change, otherwise the diff.
        :raises RuntimeError: If the external diff tool returns an error.
        """
        if tz:
            tz_info = ZoneInfo(tz)
        else:
            tz_info = None  # type: ignore[assignment]
        if self.old_timestamp:
            timestamp_old = (
                datetime.fromtimestamp(self.old_timestamp).astimezone(tz=tz_info).strftime('%a, %d %b %Y %H:%M:%S %z')
            )
        else:
            timestamp_old = 'NEW:'
        timestamp_new = (
            datetime.fromtimestamp(self.new_timestamp).astimezone(tz=tz_info).strftime('%a, %d %b %Y %H:%M:%S %z')
        )

        if self.job.diff_tool is not None:
            # TODO: 'deepdiff' is work in progress, not documented, and will most likely change as diffing will
            # become a class to keep the code organized.
            if self.job.diff_tool.startswith('deepdiff'):
                # pragma: no cover
                if deepdiff is None:
                    raise ImportError(
                        f"Python package 'deepdiff' is not installed; cannot use 'diff_tool: {self.job.diff_tool}'"
                        f' ({self.job.get_indexed_location()})'
                    )
                else:
                    from deepdiff.model import DiffLevel

                def _pretty_deepdiff(diff: deepdiff.DeepDiff, html_out: bool = False) -> str:
                    """
                    Customized version of deepdiff.serialization.SerializationMixin.pretty method,
                    edited to include the values deleted or added and an option for colorized HTML output.
                    The pretty human readable string output for the diff object
                    regardless of what view was used to generate the diff.
                    """

                    if html_out:
                        added = '<span style="background-color:#d1ffd1;color:#082b08">'
                        delte = '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through">'
                        PRETTY_FORM_TEXTS = {
                            'type_changes': (
                                'Type of {diff_path} changed from {type_t1} to {type_t2} and value changed '
                                f'from {delte}{{val_t1}}</span> to {added}{{val_t2}}</span>.'
                            ),
                            'values_changed': (
                                f'Value of {{diff_path}} changed from {delte}{{val_t1}}</span> to {added}{{val_t2}}'
                                f'</span>.'
                            ),
                            'dictionary_item_added': (
                                f'Item {{diff_path}} added to dictionary as {added}{{val_t2}}</span>.'
                            ),
                            'dictionary_item_removed': (
                                f'Item {{diff_path}} removed from dictionary (was {delte}{{val_t1}}</span>).'
                            ),
                            'iterable_item_added': f'Item {{diff_path}} added to iterable as {added}{{val_t2}}</span>.',
                            'iterable_item_removed': (
                                f'Item {{diff_path}} removed from iterable (was {delte}{{val_t1}}</span>).'
                            ),
                            'attribute_added': f'Attribute {{diff_path}} added as {added}{{val_t2}}</span>.',
                            'attribute_removed': f'Attribute {{diff_path}} removed (was {delte}{{val_t1}}</span>).',
                            'set_item_added': f'Item root[{{val_t2}}] added to set as {added}{{val_t1}}</span>.',
                            'set_item_removed': (
                                f'Item root[{{val_t1}}] removed from set (was {delte}{{val_t2}}</span>).'
                            ),
                            'repetition_change': 'Repetition change for item {diff_path} ({val_t2}).',
                        }
                    else:
                        PRETTY_FORM_TEXTS = {
                            'type_changes': (
                                'Type of {diff_path} changed from {type_t1} to {type_t2} and value changed '
                                'from {val_t1} to {val_t2}.'
                            ),
                            'values_changed': 'Value of {diff_path} changed from {val_t1} to {val_t2}.',
                            'dictionary_item_added': 'Item {diff_path} added to dictionary as {val_t2}.',
                            'dictionary_item_removed': 'Item {diff_path} removed from dictionary (was {val_t1}).',
                            'iterable_item_added': 'Item {diff_path} added to iterable as {val_t2}.',
                            'iterable_item_removed': 'Item {diff_path} removed from iterable (was {val_t1}).',
                            'attribute_added': 'Attribute {diff_path} added as {val_t2}.',
                            'attribute_removed': 'Attribute {diff_path} removed (was {val_t1}).',
                            'set_item_added': 'Item root[{val_t2}] added to set as {val_t1}.',
                            'set_item_removed': 'Item root[{val_t1}] removed from set (was {val_t2}).',
                            'repetition_change': 'Repetition change for item {diff_path} ({val_t2}).',
                        }

                    def _pretty_print_diff(diff: DiffLevel) -> str:
                        """
                        Customized version of deepdiff.serialization.pretty_print_diff() function, edited to include
                        the values deleted or added.
                        """
                        type_t1 = type(diff.t1).__name__
                        type_t2 = type(diff.t2).__name__

                        val_t1 = (
                            f'"{diff.t1}"'
                            if type_t1 in ('str', 'int', 'float')
                            else json.dumps(diff.t1, ensure_ascii=False, indent=2)
                            if type_t1 == 'dict'
                            else str(diff.t1)
                        )
                        val_t2 = (
                            f'"{diff.t2}"'
                            if type_t2 in ('str', 'int', 'float')
                            else json.dumps(diff.t2, ensure_ascii=False, indent=2)
                            if type_t2 == 'dict'
                            else str(diff.t2)
                        )

                        diff_path = diff.path(root='root')
                        return PRETTY_FORM_TEXTS.get(diff.report_type, '').format(
                            diff_path=diff_path,
                            type_t1=type_t1,
                            type_t2=type_t2,
                            val_t1=val_t1,
                            val_t2=val_t2,
                        )

                    result = []
                    for key in diff.tree.keys():
                        for item_key in diff.tree[key]:
                            result.append(_pretty_print_diff(item_key))

                    return '\n'.join(result)

                data_type = self.job.diff_tool.split('-')[1] if len(self.job.diff_tool.split('-')) > 1 else 'json'
                if data_type == 'json':
                    try:
                        old_data = json.loads(self.old_data)
                    except json.JSONDecodeError:
                        old_data = ''
                    new_data = json.loads(self.new_data)
                elif data_type == 'xml':
                    if xmltodict is None:
                        raise ImportError(
                            f"Python package 'xmltodict' is not installed; cannot use 'diff_tool: {self.job.diff_tool}'"
                            f' ({self.job.get_indexed_location()})'
                        )
                    old_data = xmltodict.parse(self.old_data)
                    new_data = xmltodict.parse(self.new_data)
                else:
                    raise NotImplementedError(
                        f"data_type '{data_type}' is not supported by 'diff_tool: deepdiff'"
                        f' ({self.job.get_indexed_location()})'
                    )
                diff = deepdiff.DeepDiff(old_data, new_data, verbose_level=2)
                diff_text = _pretty_deepdiff(diff, html_out)
                if not diff_text:
                    self.verb = 'changed,no_report'
                    return ''
                head = (
                    f'Using {self.job.diff_tool}\n'
                    f'Old: {timestamp_old}\n'
                    f'New: {timestamp_new}\n' + '-' * 36 + '\n'
                )
                return head + diff_text

            else:
                # External diff tool
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_path = Path(tmp_dir)
                    old_file_path = tmp_path.joinpath('old_file')
                    new_file_path = tmp_path.joinpath('new_file')
                    old_file_path.write_text(str(self.old_data))
                    new_file_path.write_text(str(self.new_data))
                    cmdline = shlex.split(self.job.diff_tool) + [str(old_file_path), str(new_file_path)]
                    proc = subprocess.run(cmdline, capture_output=True, text=True)
                if proc.stderr:
                    raise RuntimeError(
                        f"diff_tool '{self.job.diff_tool}' returned '{proc.stderr}' ({self.job.get_indexed_location()})"
                    ) from subprocess.CalledProcessError(proc.returncode, cmdline)
                head = (
                    f'Using external diff tool "{self.job.diff_tool}"\n'
                    f'Old: {timestamp_old}\n'
                    f'New: {timestamp_new}\n' + '-' * 36 + '\n'
                )
                return head + proc.stdout

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
        if not diff:
            self.verb = 'changed,no_report'
            return ''
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

    job_states: List[JobState] = []
    new_release_future: Optional[Future[str]] = None
    start: float = time.perf_counter()

    def __init__(self, urlwatch_config: Urlwatch) -> None:
        """

        :param urlwatch_config: The Urlwatch object with the program configuration information.
        """
        self.config: Config = urlwatch_config.config_storage.config

    def _result(self, verb: str, job_state: JobState) -> None:
        """Logs error and appends the verb to the job_state.

        :param verb: Description of the result of the job run. Can be one of 'new', 'changed', 'changed,no_report',
        'unchanged', 'error', which have a meaning, or a custom message such as 'test'.
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

    def custom(self, job_state: JobState, label: str) -> None:
        """Sets the verb of the job in job_state to a custom label. Called by
        :py:func:`UrlwatchCommand.check_test_reporter`.

        :param job_state: The JobState object with the information of the job run.
        :param label: The label to set the information of the job run to.
        """
        self._result(label, job_state)

    def get_filtered_job_states(self, job_states: List[JobState]) -> Iterable[JobState]:
        """Returns JobStates that have reportable changes per config['display'].  Called from :py:Class:`ReporterBase`.

        :param job_states: The list of JobState objects with the information of the job runs.
        :returns: An iterable of JobState objects that have reportable changes per config['display'].
        """
        for job_state in job_states:
            if (
                not any(
                    job_state.verb == verb and not self.config['display'][verb]  # type: ignore[literal-required]
                    for verb in ('unchanged', 'new', 'error')
                )
                and job_state.verb != 'changed,no_report'
            ):
                yield job_state

    def finish(self, jobs_file: Optional[Path] = None) -> None:
        """Finish job run: determine its duration and generate reports by submitting job_states to
        :py:Class:`ReporterBase` :py:func:`submit_all`.

        :param jobs_file: The path to the file containing the list of jobs (optional, used in footers).
        """
        end = time.perf_counter()
        duration = end - self.start

        ReporterBase.submit_all(self, self.job_states, duration, jobs_file)

    def finish_one(self, name: str, jobs_file: Optional[Path] = None, check_enabled: Optional[bool] = True) -> None:
        """Finish job run of one: determine its duration and generate reports by submitting job_states to
        :py:Class:`ReporterBase` :py:func:`submit_one`.  Used in testing.

        :param name: The name of the reporter to run.
        :param jobs_file: The path to the file containing the list of jobs (optional, used in footers).
        :param check_enabled: If True (default), run reports only if they are enabled in the configuration.
        """
        end = time.perf_counter()
        duration = end - self.start

        ReporterBase.submit_one(name, self, self.job_states, duration, jobs_file, check_enabled)
