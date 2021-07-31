"""The worker that runs jobs in parallel.  Called from main.py."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from typing import TYPE_CHECKING

from .handler import JobState
from .jobs import BrowserJob, NotModifiedError

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from .main import Urlwatch

logger = logging.getLogger(__name__)


def run_jobs(urlwatcher: Urlwatch) -> None:
    """Process (run) jobs in parallel.

    :raises IndexError: If any index(es) is/are out of range.
    """
    cache_storage = urlwatcher.cache_storage
    if urlwatcher.urlwatch_config.joblist:
        for idx in urlwatcher.urlwatch_config.joblist:
            if not (-len(urlwatcher.jobs) <= idx <= -1 or 1 <= idx <= len(urlwatcher.jobs)):
                raise IndexError(f'Job index {idx} out of range (found {len(urlwatcher.jobs)} jobs)')
        urlwatcher.urlwatch_config.joblist = [
            jn if jn > 0 else len(urlwatcher.jobs) + jn + 1 for jn in urlwatcher.urlwatch_config.joblist
        ]
        jobs = [
            job.with_defaults(urlwatcher.config_storage.config)
            for job in urlwatcher.jobs
            if job.index_number in urlwatcher.urlwatch_config.joblist
        ]
        logger.debug(f'Processing {len(jobs)} job as specified (# {urlwatcher.urlwatch_config.joblist})')
    else:
        jobs = [job.with_defaults(urlwatcher.config_storage.config) for job in urlwatcher.jobs]
        logger.debug(f'Processing {len(jobs)} jobs')
    report = urlwatcher.report

    with ExitStack() as stack:
        max_workers = min(32, os.cpu_count() or 1) if any(type(job) == BrowserJob for job in jobs) else None
        logger.debug(f'Max_workers set to {max_workers}')
        executor = ThreadPoolExecutor(max_workers=max_workers)

        # launch future to retrieve if new version is available
        urlwatcher.report.new_release_future = executor.submit(urlwatcher.get_new_release_version)

        for job_state in executor.map(
            lambda jobstate: jobstate.process(),
            (stack.enter_context(JobState(cache_storage, job)) for job in jobs),
        ):

            max_tries = 0 if not job_state.job.max_tries else job_state.job.max_tries

            if job_state.exception is not None:
                # Oops, we have captured an error to ignore!
                if job_state.error_ignored:
                    logger.info(
                        f'Job {job_state.job.index_number}: Error while executing job was ignored due to job config'
                    )
                elif isinstance(job_state.exception, NotModifiedError):
                    logger.info(
                        f'Job {job_state.job.index_number}: Job has not changed (HTTP 304 response or same strong '
                        f'ETag)'
                    )
                    if job_state.tries > 0:
                        job_state.tries = 0
                        job_state.save(use_old_data=True)  # data is not returned by 304 therefore reuse old data
                    report.unchanged(job_state)
                elif job_state.tries < max_tries:
                    logger.debug(
                        f'Job {job_state.job.index_number}: Error suppressed as cumulative number of '
                        f'failures ({job_state.tries}) does not exceed max_tries={max_tries}'
                    )
                    job_state.save(use_old_data=True)  # do not save error data but reuse old data
                elif job_state.tries >= max_tries:
                    logger.debug(
                        f'Job {job_state.job.index_number}: Flagged as error as max_tries={max_tries} has been '
                        f'met or exceeded ({job_state.tries}'
                    )
                    job_state.save(use_old_data=True)  # do not save error data but reuse old data
                    report.error(job_state)
                else:
                    logger.debug(f'Job {job_state.job.index_number}: Job finished with no exceptions')
            elif job_state.old_data != '' or job_state.old_timestamp != 0:
                # This is not the first time running this job (we have snapshots)
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
                # We have never run this job before (there are no snapshots)
                job_state.tries = 0
                job_state.save()
                report.new(job_state)
