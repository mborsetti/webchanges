"""The worker that runs jobs in parallel.  Called from main module."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import gc
import logging
import os
import random
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from typing import Iterable, TYPE_CHECKING

from webchanges.command import UrlwatchCommand
from webchanges.handler import JobState
from webchanges.jobs import NotModifiedError

try:
    import psutil
except ImportError as e:  # pragma: no cover
    psutil = str(e)  # type: ignore[assignment]

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.jobs import JobBase
    from webchanges.main import Urlwatch

logger = logging.getLogger(__name__)


def run_jobs(urlwatcher: Urlwatch) -> None:
    """Process (run) jobs in parallel.

    :raises IndexError: If any index(es) is/are out of range.
    """

    def insert_delay(jobs: set[JobBase]) -> set[JobBase]:  # pragma: no cover
        """
        TODO Evaluate whether this is necessary; currently not being called. Remove pragma no cover and move import.

        Sets a _delay value for URL jobs having the same network location as previous ones. Used to prevent
        multiple jobs hitting the same network location at the exact same time and being blocked as a result.

        CHANGELOG:
        * When multiple URL jobs have the same network location (www.example.com), a random delay between 0.1 and 1.0
          seconds is added to all jobs to that network location after the first one. This prevents being blocked by
          the site as a result of being flooded by **webchanges**'s parallelism sending multiple requests from the same
          source at the same exact time.

        :param jobs: The list of jobs.
        :return: The list of jobs with the _delay value set.
        """
        from webchanges.jobs import UrlJobBase

        previous_netlocs = set()
        for job in jobs:
            if isinstance(job, UrlJobBase):
                netloc = urllib.parse.urlparse(job.url).netloc
                if netloc in previous_netlocs:
                    job._delay = random.uniform(0.1, 1)  # noqa: S311 Standard pseudo-random generator not suitable.
                else:
                    previous_netlocs.add(netloc)
        return jobs

    def job_runner(
        stack: ExitStack,
        jobs: Iterable[JobBase],
        max_workers: int | None = None,
    ) -> None:
        """
        Runs the jobs in parallel.

        :param stack: The context manager.
        :param jobs: The jobs to run.
        :param max_workers: The number of maximum workers for ThreadPoolExecutor.
        :return: None
        """
        executor = ThreadPoolExecutor(max_workers=max_workers)

        # launch future to retrieve if new version is available
        if urlwatcher.report.new_release_future is None:
            urlwatcher.report.new_release_future = executor.submit(urlwatcher.get_new_release_version)

        job_state: JobState
        for job_state in executor.map(
            lambda jobstate: jobstate.process(headless=not urlwatcher.urlwatch_config.no_headless),
            (stack.enter_context(JobState(urlwatcher.ssdb_storage, job)) for job in jobs),
        ):
            max_tries = 0 if not job_state.job.max_tries else job_state.job.max_tries
            # tries is incremented by JobState.process when an exception (including 304) is encountered.

            if job_state.exception is not None:
                # Oops, we have captured an error (which could also be 304 or a Playwright timeout)
                if job_state.error_ignored:
                    # We captured an error to ignore
                    logger.info(
                        f'Job {job_state.job.index_number}: Error while executing job was ignored (e.g. due to job '
                        f'config or browser timing out)'
                    )
                elif isinstance(job_state.exception, NotModifiedError):
                    # We captured a 304 Not Modified
                    logger.info(
                        f'Job {job_state.job.index_number}: Job has not changed (HTTP 304 response or same strong '
                        f'ETag)'
                    )
                    if job_state.tries > 0:
                        job_state.tries = 0
                        job_state.save()
                    if job_state.old_error_data and job_state.job.suppress_repeated_errors:
                        urlwatcher.report.unchanged_from_error(job_state)
                    else:
                        urlwatcher.report.unchanged(job_state)
                elif job_state.tries < max_tries:
                    # We're not reporting the error yet because we haven't yet hit 'max_tries'
                    logger.debug(
                        f'Job {job_state.job.index_number}: Error suppressed as cumulative number of '
                        f'failures ({job_state.tries}) does not exceed max_tries={max_tries}'
                    )
                    job_state.save()
                else:
                    # Reporting the error
                    logger.debug(
                        f'Job {job_state.job.index_number}: Flagged as error as max_tries={max_tries} has been '
                        f'met or exceeded ({job_state.tries}'
                    )
                    job_state.save()
                    if job_state.new_error_data == job_state.old_error_data:
                        urlwatcher.report.error_same_error(job_state)
                    else:
                        urlwatcher.report.error(job_state)
            elif job_state.old_data or job_state.old_timestamp != 0:
                # This is not the first time running this job (we have snapshots)
                if (
                    job_state.new_data == job_state.old_data
                    or job_state.new_data in job_state.history_dic_snapshots.keys()
                ):
                    # Exactly matches one of the previous snapshots
                    if job_state.tries > 0:
                        job_state.tries = 0
                        job_state.save()
                    if job_state.old_error_data and job_state.job.suppress_repeated_errors:
                        urlwatcher.report.unchanged_from_error(job_state)
                    else:
                        urlwatcher.report.unchanged(job_state)
                else:
                    # # No exact match to previous snapshot  [fuzzy matching, untested and no longer makes sense]
                    # if len(job_state.history_dic_snapshots) > 1:
                    #     # Find the closest fuzzy matching saved snapshot ("good enough") and use it to diff against it
                    #     close_matches: list[str] = difflib.get_close_matches(
                    #         str(job_state.new_data), (str(k) for k in job_state.history_dic_snapshots.keys()), n=1
                    #     )
                    #     if close_matches:
                    #         logger.warning(
                    #             f'Job {job_state.job.index_number}: Did not find an existing run in the database,
                    #             f'but fuzzy matched it based on the contents of the data'
                    #         )
                    #         job_state.old_data = close_matches[0]
                    #         job_state.old_timestamp = job_state.history_dic_snapshots[close_matches[0]].timestamp
                    #         job_state.old_etag = job_state.history_dic_snapshots[close_matches[0]].etag
                    #         job_state.old_mime_type = job_state.history_dic_snapshots[close_matches[0]].mime_type

                    # It has different data, so we save it
                    job_state.tries = 0
                    job_state.save()
                    urlwatcher.report.changed(job_state)
            else:
                # We have never run this job before (there are no snapshots)
                job_state.tries = 0
                job_state.save()
                urlwatcher.report.new(job_state)

    jobs = set(UrlwatchCommand(urlwatcher).jobs_from_joblist())

    jobs = insert_delay(jobs)

    with ExitStack() as stack:  # This code is also present in command.list_error_jobs (change there too!)
        # run non-BrowserJob jobs first
        jobs_to_run = [job for job in jobs if not job.__is_browser__]
        if jobs_to_run:
            logger.debug(
                "Running jobs that do not require Chrome (without 'use_browser: true') in parallel with Python's "
                'default max_workers.'
            )
            job_runner(stack, jobs_to_run, urlwatcher.urlwatch_config.max_workers)
        else:
            logger.debug("Found no jobs that do not require Chrome (i.e. without 'use_browser: true').")

        # run BrowserJob jobs after
        jobs_to_run = [job for job in jobs if job.__is_browser__]
        if jobs_to_run:
            gc.collect()
            virt_mem = get_virt_mem()
            if urlwatcher.urlwatch_config.max_workers:
                max_workers = urlwatcher.urlwatch_config.max_workers
            else:
                max_workers = max(int(virt_mem / 400e6), 1)
                max_workers = min(max_workers, os.cpu_count() or 1)
            logger.debug(
                f"Running jobs that require Chrome (i.e. with 'use_browser: true') in parallel with {max_workers} "
                f'max_workers.'
            )
            job_runner(stack, jobs_to_run, max_workers)
        else:
            logger.debug("Found no jobs that require Chrome (i.e. with 'use_browser: true').")


def get_virt_mem() -> int:
    """Return the amount of virtual memory available, i.e. the memory that can be given instantly to processes
    without the system going into swap. Expressed in bytes."""
    if isinstance(psutil, str):
        raise ImportError(
            "Error when loading package 'psutil'; cannot use 'use_browser: true'. Please install "
            f"dependencies with 'pip install webchanges[use_browser]'.\n{psutil}"
        ) from None
    try:
        virt_mem: int = psutil.virtual_memory().available
        logger.debug(
            f'Found {virt_mem / 1e6:,.0f} MB of available physical memory (plus '
            f'{psutil.swap_memory().free / 1e6:,.0f} MB of swap).'
        )
    except psutil.Error as e:  # pragma: no cover
        virt_mem = 0
        logger.debug(f'Could not read memory information: {e}')

    return virt_mem
