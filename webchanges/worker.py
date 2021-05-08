"""The worker that runs jobs in parallel."""

import difflib
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from typing import Callable, Iterable, Optional, TYPE_CHECKING

from .handler import JobState
from .jobs import BrowserJob, NotModifiedError

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from .main import Urlwatch

logger = logging.getLogger(__name__)


def run_parallel(func: Callable, items: Iterable, max_workers: Optional[int] = None):
    """Convenience function to run parallel threads."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for result in executor.map(func, items):
            yield result


def run_jobs(urlwatcher: 'Urlwatch') -> None:
    """Process jobs."""
    cache_storage = urlwatcher.cache_storage
    if urlwatcher.urlwatch_config.joblist:
        jobs = [job.with_defaults(urlwatcher.config_storage.config) for job in urlwatcher.jobs
                if job.index_number in urlwatcher.urlwatch_config.joblist]
        logger.debug(f'Processing {len(jobs)} job as specified (# {urlwatcher.urlwatch_config.joblist})')
    else:
        jobs = [job.with_defaults(urlwatcher.config_storage.config) for job in urlwatcher.jobs]
        logger.debug(f'Processing {len(jobs)} jobs')
    report = urlwatcher.report

    with ExitStack() as stack:
        max_workers = min(32, os.cpu_count()) if any(type(job) == BrowserJob for job in jobs) else None
        logger.debug(f'Max_workers set to {max_workers}')
        for job_state in run_parallel(
            lambda job_state: job_state.process(),
            (stack.enter_context(JobState(cache_storage, job)) for job in jobs),
            max_workers=max_workers
        ):

            max_tries = 0 if not job_state.job.max_tries else job_state.job.max_tries

            if job_state.exception is not None:
                # Oops, we have captured an error!
                if job_state.error_ignored:
                    logger.info(f'Job {job_state.job.index_number}: Error while executing job was ignored due to job '
                                f'config')
                elif isinstance(job_state.exception, NotModifiedError):
                    logger.info(f'Job {job_state.job.index_number}: Job has not changed (HTTP 304 response or same '
                                f'strong ETag)')
                    if job_state.tries > 0:
                        job_state.tries = 0
                        job_state.save()
                    report.unchanged(job_state)
                elif job_state.tries < max_tries:
                    logger.debug(f'Job {job_state.job.index_number}: Error suppressed as cumulative number of '
                                 f'failures ({job_state.tries}) does not exceed max_tries={max_tries}')
                    job_state.save()
                elif job_state.tries >= max_tries:
                    logger.debug(f'Job {job_state.job.index_number}: Flag as error as max_tries={max_tries} has been '
                                 f'met or exceeded ({job_state.tries}')
                    job_state.save()
                    report.error(job_state)
                else:
                    logger.debug(f'Job {job_state.job.index_number}: Job finished with no exceptions')
            elif job_state.old_data is not None or job_state.old_timestamp is not None:
                # This is not the first time running this job (we have snapshots)
                if job_state.old_timestamp:
                    if job_state.new_data == job_state.old_data:
                        if job_state.tries > 0:
                            job_state.tries = 0
                            job_state.save()
                        report.unchanged(job_state)
                    else:
                        job_state.tries = 0
                        job_state.save()
                        report.changed(job_state)
                else:
                    # legacy code used when timestamp was not saved
                    matched_history_time = job_state.history_data.get(job_state.new_data)
                    if matched_history_time:
                        job_state.old_timestamp = matched_history_time
                    if matched_history_time or job_state.new_data == job_state.old_data:
                        if job_state.tries > 0:
                            job_state.tries = 0
                            job_state.save()
                        report.unchanged(job_state)
                    else:
                        close_matches = difflib.get_close_matches(job_state.new_data, job_state.history_data, n=1)
                        if close_matches:
                            job_state.old_data = close_matches[0]
                            job_state.old_timestamp = job_state.history_data[close_matches[0]]
                        job_state.tries = 0
                        job_state.save()
                        report.changed(job_state)
            else:
                # We have never run this job before (there are no snapshots)
                job_state.tries = 0
                job_state.save()
                report.new(job_state)
