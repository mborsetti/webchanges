"""The worker that runs jobs in parallel.  Called from main.py."""

from __future__ import annotations

import logging
import os
import random
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from typing import Iterable, Optional, TYPE_CHECKING

from .handler import JobState
from .jobs import BrowserJob, NotModifiedError, UrlJobBase

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from typing import List

    from .jobs import JobBase
    from .main import Report, Urlwatch
    from .storage import CacheStorage

logger = logging.getLogger(__name__)


def run_jobs(urlwatcher: Urlwatch) -> None:
    """Process (run) jobs in parallel.

    :raises IndexError: If any index(es) is/are out of range.
    """

    def insert_delay(jobs: List[JobBase]) -> List[JobBase]:
        """
        TODO: Evaluate whether this is necessary.  Currently not being called.

        Sets a _delay value for URL jobs hitting the network location already hit. Used to prevent multiple jobs
        hitting the same network location at the exact same time and being blocked as a result.

        CHANGELOG:
        * When multiple URL jobs have the same network location (www.example.com), a random delay between 0.1 and 1.0
          seconds is added to all jobs to that network location after the first one. This prevents being blocked by
          the site as a result of being flooded by **webchanges**'s parallelism sending multiple requests from the same
          source at the same exact time.

        :param jobs: The list of jobs.
        :return: The list of jobs with the _delay value set.
        """
        previous_netlocs = set()
        for job in jobs:
            if isinstance(job, UrlJobBase):
                netloc = urllib.parse.urlparse(job.url).netloc
                if netloc in previous_netlocs:
                    job._delay = random.uniform(0.1, 1)  # nosec [B311:blacklist] Standard pseudo-random generator
                else:
                    previous_netlocs.add(netloc)
        return jobs

    def job_runner(
        stack: ExitStack,
        jobs: Iterable[JobBase],
        cache_storage: CacheStorage,
        report: Report,
        max_workers: Optional[int] = None,
    ) -> None:
        """
        Runs the jobs in parallel.

        :param stack: The ExitStack used.
        :param jobs: The jobs to run.
        :param max_workers: The number of maximum workers for ThreadPoolExecutor.
        :return: None
        """
        executor = ThreadPoolExecutor(max_workers=max_workers)

        # launch future to retrieve if new version is available
        if urlwatcher.report.new_release_future is None:
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

    # extract subset of jobs to run if joblist CLI was set
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

    #    jobs = insert_delay(jobs)

    cache_storage = urlwatcher.cache_storage
    report = urlwatcher.report
    with ExitStack() as stack:
        # run non-BrowserJob jobs
        jobs_to_run = (job for job in jobs if type(job) != BrowserJob)
        logger.debug("Running jobs without 'use_browser: true' in parallel with Python default max_workers")
        job_runner(stack, jobs_to_run, cache_storage, report)

        # run BrowserJob jobs
        jobs_to_run = (job for job in jobs if type(job) == BrowserJob)
        if any(jobs_to_run):
            if any(job._beta_use_playwright for job in jobs_to_run):
                try:
                    import psutil
                except ImportError:
                    raise ImportError(
                        "Python package psutil is not installed; cannot use 'use_browser: true' directives with "
                        "'_beta_use_playwright: true'. Please install dependencies with 'pip install webchanges["
                        "playwright]'."
                    )
                avail_vm = psutil.virtual_memory().available + psutil.swap_memory().free
                logger.debug(f'Found {avail_vm:,} in available virtual + swap memory')
                max_workers = min(32, max(1, int(avail_vm / 140e6)), os.cpu_count() or 1)
            else:
                max_workers = min(32, os.cpu_count() or 1)
            logger.debug(f"Running 'use_browser: true' jobs in parallel with {max_workers} max_workers")
            job_runner(stack, jobs_to_run, cache_storage, report, max_workers)
