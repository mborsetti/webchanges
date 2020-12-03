import difflib
import email.utils
import logging
import os.path
import shlex
import subprocess
import tempfile
import time
import timeit
import traceback

from .filters import FilterBase
from .jobs import NotModifiedError
from .reporters import ReporterBase

logger = logging.getLogger(__name__)


class JobState(object):
    def __init__(self, cache_storage, job):
        self.cache_storage = cache_storage
        self.job = job
        self.verb = None
        self.old_data = None
        self.new_data = None
        self.history_data = {}
        self.timestamp = None
        self.current_timestamp = None
        self.exception = None
        self.traceback = None
        self.tries = 0
        self.etag = None
        self.error_ignored = False
        self._generated_diff = None

    def __enter__(self):
        try:
            self.job.main_thread_enter()
        except Exception as ex:
            logger.info('Exception while creating resources for job: %r', self.job, exc_info=True)
            self.exception = ex
            self.traceback = traceback.format_exc()

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.job.main_thread_exit()
        except Exception:
            # We don't want exceptions from releasing resources to override job run results
            logger.warning('Exception while releasing resources for job: %r', self.job, exc_info=True)

    def load(self):
        guid = self.job.get_guid()
        self.old_data, self.timestamp, self.tries, self.etag = self.cache_storage.load(self.job, guid)
        if self.tries is None:
            self.tries = 0
        if self.job.compared_versions and self.job.compared_versions > 1:
            self.history_data = self.cache_storage.get_history_data(guid, self.job.compared_versions)

    def save(self):
        if self.new_data is None and self.exception is not None:
            # If no new data has been retrieved due to an exception, use the old job data
            self.new_data = self.old_data

        self.cache_storage.save(self.job, self.job.get_guid(), self.new_data, time.time(), self.tries, self.etag)

    def process(self):
        logger.info('Processing: %s', self.job)

        if self.exception:
            return self

        try:
            try:
                self.load()
                data = self.job.retrieve(self)

                # Apply automatic filters first
                data = FilterBase.auto_process(self, data)

                # Apply any specified filters
                for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.filter):
                    data = FilterBase.process(filter_kind, subfilter, self, data)

                self.new_data = data

            except Exception as e:
                # job has a chance to format and ignore its error
                self.exception = e
                self.traceback = self.job.format_error(e, traceback.format_exc())
                self.error_ignored = self.job.ignore_error(e)
                if not (self.error_ignored or isinstance(e, NotModifiedError)):
                    self.tries += 1
                    logger.debug('Increasing number of tries to %i for %s', self.tries, self.job)
        except Exception as e:
            # job failed its chance to handle error
            self.exception = e
            self.traceback = traceback.format_exc()
            self.error_ignored = False
            if not isinstance(e, NotModifiedError):
                self.tries += 1
                logger.debug('Increasing number of tries to %i for %s', self.tries, self.job)

        return self

    def get_diff_match_patch(self):
        """WORK IN PROGRESS use of diff_match_patch library"""
        if self._generated_diff_match_patch is None:
            from diff_match_patch import diff_match_patch

            dmp = diff_match_patch()
            diff = dmp.diff_main(self.old_data, self.new_data)
            self._generated_diff_match_patch = dmp.diff_cleanupSemantic(diff)

            # Apply any specified diff filters
            for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.diff_filter):
                self._generated_diff_match_patch = FilterBase.process(filter_kind, subfilter, self,
                                                                      self._generated_diff_match_patch)

        return self._generated_diff_match_patch

    def get_diff(self):
        if self._generated_diff is None:
            self._generated_diff = self._generate_diff()
            # Apply any specified diff filters
            for filter_kind, subfilter in FilterBase.normalize_filter_list(self.job.diff_filter):
                self._generated_diff = FilterBase.process(filter_kind, subfilter, self, self._generated_diff)

        return self._generated_diff

    def _generate_diff(self):
        if self.job.diff_tool is not None:
            with tempfile.TemporaryDirectory() as tmpdir:
                old_file_path = os.path.join(tmpdir, 'old_file')
                new_file_path = os.path.join(tmpdir, 'new_file')
                with open(old_file_path, 'w+b') as old_file, open(new_file_path, 'w+b') as new_file:
                    old_file.write(self.old_data.encode())
                    new_file.write(self.new_data.encode())
                cmdline = shlex.split(self.job.diff_tool) + [old_file_path, new_file_path]
                proc = subprocess.run(cmdline, capture_output=True, text=True)
                # Diff tools return 0 for "nothing changed" or 1 for "files differ", anything else is an error
                if proc.returncode == 0:
                    return False
                elif proc.returncode == 1:
                    head = f'Using external diff tool "{self.job.diff_tool}"\n'
                    head += f'Old: {email.utils.formatdate(self.timestamp, localtime=True)}\n'
                    head += f'New: {email.utils.formatdate(time.time(), localtime=True)}\n'
                    head += '-' * 36 + '\n'
                    return head + proc.stdout
                else:
                    raise RuntimeError(proc.stderr) from subprocess.CalledProcessError(proc.returncode, cmdline)

        timestamp_old = email.utils.formatdate(self.timestamp, localtime=True)
        timestamp_new = email.utils.formatdate(self.current_timestamp or time.time(), localtime=True)
        if self.job.contextlines is not None:
            contextlines = self.job.contextlines
        else:
            contextlines = 0 if self.job.additions_only or self.job.deletions_only else 3
        diff = list(difflib.unified_diff(self.old_data.splitlines(), self.new_data.splitlines(),
                                         '@', '@', timestamp_old, timestamp_new, contextlines, lineterm=''))
        if self.job.additions_only:
            if len(self.old_data) and len(self.new_data) / len(self.old_data) <= .25:
                diff = (diff[:2] + ['/**Comparison type: Additions only**']
                        + ['/**Deletions are being shown as 75% or more of the content has been deleted**']
                        + diff[2:])
            else:
                head = '...' + diff[0][3:]
                diff = [dif for dif in diff if dif.startswith('+') or dif.startswith('@')]
                diff = [dif for dif, dif2 in zip([''] + diff, diff + ['']) if
                        not (dif.startswith('@') and dif2.startswith('@'))][1:]
                diff = diff[:-1] if diff[-1].startswith('@') else diff
                if len(diff) == 1:
                    self.verb = 'changed,no_report'
                    return
                diff = [head, diff[0], '/**Comparison type: Additions only**'] + diff[1:]
        elif self.job.deletions_only:
            head = '...' + diff[1][3:]
            diff = [dif for dif in diff if dif.startswith('-') or dif.startswith('@')]
            diff = [dif for dif, dif2 in zip([''] + diff, diff + ['']) if
                    not (dif.startswith('@') and dif2.startswith('@'))][1:]
            diff = diff[:-1] if diff[-1].startswith('@') else diff
            if len(diff) == 1:
                self.verb = 'changed,no_report'
                return
            diff = [diff[0], head, '/**Comparison type: Deletions only**'] + diff[1:]

        return '\n'.join(diff)


class Report(object):
    def __init__(self, urlwatch_config):
        self.config = urlwatch_config.config_storage.config

        self.job_states = []
        self.start = timeit.default_timer()

    def _result(self, verb, job_state):
        if job_state.exception is not None:
            logger.debug('Got exception while processing %r', job_state.job, exc_info=job_state.exception)

        job_state.verb = verb
        self.job_states.append(job_state)

    def new(self, job_state):
        self._result('new', job_state)

    def changed(self, job_state):
        self._result('changed', job_state)

    def unchanged(self, job_state):
        self._result('unchanged', job_state)

    def error(self, job_state):
        self._result('error', job_state)

    def get_filtered_job_states(self, job_states):
        for job_state in job_states:
            if not any(job_state.verb == verb and not self.config['display'][verb]
                       for verb in ('unchanged', 'new', 'error')) and job_state.verb != 'changed,no_report':
                yield job_state

    def finish(self):
        end = timeit.default_timer()
        duration = (end - self.start)

        ReporterBase.submit_all(self, self.job_states, duration)

    def finish_one(self, name):
        end = timeit.default_timer()
        duration = (end - self.start)

        ReporterBase.submit_one(name, self, self.job_states, duration)
