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
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for result in executor.map(func, items):
            yield result


def run_jobs(urlwatcher: 'Urlwatch') -> None:
    cache_storage = urlwatcher.cache_storage
    jobs = [job.with_defaults(urlwatcher.config_storage.config) for job in urlwatcher.jobs]
    report = urlwatcher.report

    logger.debug(f'Processing {len(jobs)} jobs')
    with ExitStack() as stack:
        max_workers = min(32, os.cpu_count()) if any(type(job) == BrowserJob for job in jobs) else None
        logger.debug(f'Max_workers set to {max_workers}')
        for job_state in run_parallel(
            lambda job_state: job_state.process(),
            (stack.enter_context(JobState(cache_storage, job)) for job in jobs),
            max_workers=max_workers
        ):
            logger.debug(f'Job finished: {job_state.job}')

            if not job_state.job.max_tries:
                max_tries = 0
            else:
                max_tries = job_state.job.max_tries
            logger.debug(f'Using max_tries of {max_tries} for {job_state.job}')

            if job_state.exception is not None:
                if job_state.error_ignored:
                    logger.info(f'Error while executing job {job_state.job} ignored due to job config')
                elif isinstance(job_state.exception, NotModifiedError):
                    logger.info(f'Job {job_state.job} has not changed (HTTP 304)')
                    report.unchanged(job_state)
                    if job_state.tries > 0:
                        job_state.tries = 0
                        job_state.save()
                elif job_state.tries < max_tries:
                    logger.debug(f'This was try {job_state.tries} of {max_tries} for job {job_state.job}')
                    job_state.save()
                elif job_state.tries >= max_tries:
                    logger.debug(f'We are now at {job_state.tries} tries ')
                    job_state.save()
                    report.error(job_state)

            elif job_state.old_data is not None:
                matched_history_time = job_state.history_data.get(job_state.new_data)
                if matched_history_time:
                    job_state.timestamp = matched_history_time
                if matched_history_time or job_state.new_data == job_state.old_data:
                    report.unchanged(job_state)
                    if job_state.tries > 0:
                        job_state.tries = 0
                        job_state.save()
                else:
                    close_matches = difflib.get_close_matches(job_state.new_data, job_state.history_data, n=1)
                    if close_matches:
                        job_state.old_data = close_matches[0]
                        job_state.timestamp = job_state.history_data[close_matches[0]]
                    report.changed(job_state)
                    job_state.tries = 0
                    job_state.save()
            else:
                report.new(job_state)
                job_state.tries = 0
                job_state.save()
