"""The worker that runs jobs in parallel.  Called from main module."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import gc
import logging
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from typing import TYPE_CHECKING, Callable, Iterable

from webchanges.command import UrlwatchCommand
from webchanges.handler import JobState
from webchanges.jobs import NotModifiedError, TransientHTTPError, UrlJobBase

try:
    import psutil
except ImportError as e:  # pragma: no cover
    psutil = str(e)  # ty:ignore[invalid-assignment]

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.jobs import JobBase
    from webchanges.main import Urlwatch

logger = logging.getLogger(__name__)


def _close_worker_cdp_cache(executor: ThreadPoolExecutor) -> None:
    """Run the CDP cache teardown on one of ``executor``'s worker threads.

    Playwright's sync API is thread-bound, so the cached instance must be stopped on the thread that created it.
    Submitting onto the still-running executor reaches a worker thread. Best-effort: failures (e.g. an already
    broken executor) are logged at debug level and never mask a propagating exception.
    """
    from webchanges.jobs import _browser  # local import to keep monkeypatching of the helper effective in tests

    try:
        executor.submit(_browser._close_current_thread_cdp_cache).result()
    except Exception as e:  # noqa: BLE001  best-effort cleanup
        logger.debug(f'Could not tear down CDP cache on worker thread: {e}')


def run_jobs(urlwatcher: Urlwatch, read_only: bool = False) -> None:
    """Process (run) jobs in parallel.

    :param urlwatcher: The :py:class:`Urlwatch` orchestrator.
    :param read_only: If True, skip every ``job_state.save()`` call so the snapshot DB is
        unchanged. Used by ``--test-reporter`` + joblist to preview a reporter without
        committing new snapshots.

    :raises IndexError: If any index(es) is/are out of range.
    """

    def activate_same_site_delays(jobs: list[JobBase]) -> list[JobBase]:
        """Activate each URL job's ``same_site_delay`` when it shares a network location with an earlier job.

        Because jobs run in parallel, several jobs pointing at the same site (network location, e.g.
        ``www.example.com``) can hit it at the exact same instant and get rate-limited or blocked. The first job for a
        given network location runs with no delay; for each subsequent one, its configured ``same_site_delay`` (if any)
        is copied into the internal ``_delay`` that :py:meth:`JobBase.retrieve` sleeps for before fetching. Jobs without
        the directive set, and jobs whose network location is unique, are never delayed.

        :param jobs: The list of jobs.
        :return: The same list of jobs, with ``_delay`` activated where applicable.
        """
        previous_netlocs: set[str] = set()
        for job in jobs:
            if isinstance(job, UrlJobBase):
                netloc = urllib.parse.urlparse(job.url).netloc
                if netloc not in previous_netlocs:
                    previous_netlocs.add(netloc)
                elif job.same_site_delay:
                    job._delay = job.same_site_delay
                    logger.debug(
                        f'Job {job.index_number}: Will wait {job._delay}s before retrieving '
                        f'(shares network location {netloc!r} with an earlier job; same_site_delay directive)'
                    )
        return jobs

    def job_runner(
        jobs: Iterable[JobBase],
        max_workers: int | None = None,
    ) -> None:
        """Runs the jobs in parallel.

        Owns its own ``ExitStack`` so the function is safe to call from multiple worker threads
        concurrently (e.g. CDP-pinned jobs alongside the regular browser-job pool).

        :param jobs: The jobs to run.
        :param max_workers: The number of maximum workers for ThreadPoolExecutor.
        :return: None
        """
        with ExitStack() as stack:
            executor = ThreadPoolExecutor(max_workers=max_workers)

            # launch future to retrieve if new version is available
            if urlwatcher.report.new_release_future is None:
                urlwatcher.report.new_release_future = executor.submit(urlwatcher.get_new_release_version)

            # Tear down any thread-local CDP cache on the worker thread that owns it (Playwright's sync API is
            # thread-bound, so this can't be done from the main thread / atexit). Registered as a stack callback
            # so it runs on normal exit AND on exceptions, while the executor is still alive (it is intentionally
            # not shut down here: shutting it down would block on the background new-release-check future). A
            # no-op for non-CDP runs; only the pinned max_workers=1 CDP runner (see _run_browser_jobs) ever holds
            # a populated cache, so a single submit().result() reliably reaches the owning thread.
            stack.callback(_close_worker_cdp_cache, executor)

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
                        # We captured an error but are ignoring it
                        logger.info(
                            f'Job {job_state.job.index_number}: Job resulted in an error that is ignored due to '
                            f'directives'
                        )
                    elif isinstance(job_state.exception, NotModifiedError):
                        # We captured a 304 Not Modified
                        logger.info(f'Job {job_state.job.index_number}: Job has not changed (HTTP 304 response)')
                        if job_state.tries > 0:
                            job_state.tries = 0
                            if not read_only:
                                job_state.save()
                        if job_state.old_error_data and job_state.job.suppress_repeated_errors:
                            urlwatcher.report.unchanged_from_error(job_state)
                        else:
                            urlwatcher.report.unchanged(job_state)
                    elif job_state.tries < max_tries:
                        # We're not reporting the error yet because we haven't yet hit 'max_tries'
                        logger.debug(
                            f'Job {job_state.job.index_number}: Job error suppressed as cumulative number of '
                            f'failures ({job_state.tries}) does not exceed max_tries={max_tries}'
                        )
                        if not read_only:
                            job_state.save()
                    else:
                        # Reporting the error
                        logger.debug(
                            f'Job {job_state.job.index_number}: Job error flagged as error as max_tries={max_tries} '
                            f'has been met or exceeded ({job_state.tries}'
                        )
                        if isinstance(job_state.exception, TransientHTTPError):
                            # We captured a transient error
                            logger.info(
                                f'Job {job_state.job.index_number}: Job has received an HTTP response of a typically '
                                'transient nature'
                            )
                            job_state.new_data = job_state.old_data
                            job_state.new_etag = job_state.old_etag
                            job_state.new_mime_type = job_state.old_mime_type
                        if not read_only:
                            job_state.save()
                        if job_state.new_error_data == job_state.old_error_data:
                            urlwatcher.report.error_same_error(job_state)
                        else:
                            urlwatcher.report.error(job_state)
                elif job_state.old_data or job_state.old_timestamp != 0:
                    # This is not the first time running this job (we have snapshots)
                    if (
                        job_state.new_data == job_state.old_data
                        or job_state.new_data in job_state.history_dic_snapshots
                    ):
                        # Exactly matches one of the previous snapshots
                        if job_state.tries > 0:
                            job_state.tries = 0
                            if not read_only:
                                job_state.save()
                        if job_state.old_error_data and job_state.job.suppress_repeated_errors:
                            urlwatcher.report.unchanged_from_error(job_state)
                        else:
                            urlwatcher.report.unchanged(job_state)
                    else:
                        # # No exact match to previous snapshot  [fuzzy matching, untested and no longer makes sense]
                        # if len(job_state.history_dic_snapshots) > 1:
                        #     # Find the closest fuzzy matching saved snapshot ("good enough") and use it to diff
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
                        if not read_only:
                            job_state.save()
                        urlwatcher.report.changed(job_state)
                else:
                    # We have never run this job before (there are no snapshots)
                    job_state.tries = 0
                    if not read_only:
                        job_state.save()
                    urlwatcher.report.new(job_state)

    jobs = list(UrlwatchCommand(urlwatcher).jobs_from_joblist())

    jobs = activate_same_site_delays(jobs)

    # run non-BrowserJob jobs first
    jobs_to_run = [job for job in jobs if not job.__is_browser__]
    if jobs_to_run:
        logger.debug(
            "Running jobs that do not require Chrome (without 'use_browser: true') in parallel with Python's "
            'default max_workers.'
        )
        job_runner(jobs_to_run, urlwatcher.urlwatch_config.max_workers)
    else:
        logger.debug("Found no jobs that do not require Chrome (i.e. without 'use_browser: true').")

    # run BrowserJob jobs after
    browser_jobs = [job for job in jobs if job.__is_browser__]
    if browser_jobs:
        _run_browser_jobs(browser_jobs, urlwatcher.urlwatch_config.max_workers, job_runner)
    else:
        logger.debug("Found no jobs that require Chrome (i.e. with 'use_browser: true').")


def _run_browser_jobs(
    browser_jobs: list[JobBase],
    configured_max_workers: int | None,
    job_runner: Callable[[Iterable[JobBase], int | None], None],
) -> None:
    """Run browser jobs, pinning CDP-attached jobs to a single dedicated thread.

    Playwright's sync API can only host one ``PlaywrightContextManager`` per OS thread, and
    ``connect_over_cdp`` typically requires a manual browser authorization per unique URL. Sharing one
    worker thread for all CDP jobs means each unique ``connect_over_cdp`` URL only needs to be authorized
    once per run (the thread-local cache in ``_browser.py`` only deduplicates within a thread).

    Non-CDP browser jobs run concurrently on the regular thread pool, sized by available memory and CPU.

    :param browser_jobs: All jobs with ``__is_browser__`` set.
    :param configured_max_workers: User-configured ``max_workers``, or ``None`` to derive from memory/CPU.
    :param job_runner: The inner job runner (closure that captures the ``Urlwatch`` orchestrator).
    """
    gc.collect()
    virt_mem = get_virt_mem_mib()  # in MiB
    virt_mem = virt_mem * 0.85  # reserve 15% for misc. overhead
    if configured_max_workers:
        max_workers = configured_max_workers
    else:
        max_workers = max(int(virt_mem / 800), 1)
        max_workers = min(max_workers, os.cpu_count() or 1)

    cdp_jobs = [j for j in browser_jobs if getattr(j, 'connect_over_cdp', None)]
    non_cdp_browser_jobs = [j for j in browser_jobs if not getattr(j, 'connect_over_cdp', None)]

    if cdp_jobs and non_cdp_browser_jobs:
        logger.debug(
            f'Running {len(cdp_jobs)} CDP browser job(s) on a single dedicated thread (one manual browser '
            f'authorization per unique connect_over_cdp URL per run) concurrently with '
            f'{len(non_cdp_browser_jobs)} non-CDP browser job(s) using up to {max_workers} workers.'
        )
        with ThreadPoolExecutor(max_workers=2) as runner_executor:
            cdp_future = runner_executor.submit(job_runner, cdp_jobs, 1)
            other_future = runner_executor.submit(job_runner, non_cdp_browser_jobs, max_workers)
            cdp_future.result()
            other_future.result()
    elif cdp_jobs:
        logger.debug(
            f'Running {len(cdp_jobs)} CDP browser job(s) on a single dedicated thread (one manual browser '
            f'authorization per unique connect_over_cdp URL per run).'
        )
        job_runner(cdp_jobs, 1)
    else:
        logger.debug(
            f"Running jobs that require Chrome (i.e. with 'use_browser: true') in parallel with {max_workers} "
            f'max_workers.'
        )
        job_runner(non_cdp_browser_jobs, max_workers)


def get_virt_mem_mib() -> float:
    """Return the amount of virtual memory available.

    This is the memory that can be given instantly to processes without the system going into swap.

    :returns: The amount of virtual memory available in MiB (IEC).
    """
    if isinstance(psutil, str):
        raise ImportError(
            "Error when loading package 'psutil'; cannot use 'use_browser: true'. Please install "
            f"dependencies with 'pip install webchanges[use_browser]'.\n{psutil}"
        ) from None
    try:
        virt_mem: float = psutil.virtual_memory().available
        virt_mem /= 1_048_576
        logger.debug(
            f'Found {virt_mem:,.0f} MiB of available physical memory (plus '
            f'{psutil.swap_memory().free:,.0f} MiB of swap).'
        )
    except psutil.Error as e:  # pragma: no cover
        virt_mem = 0
        logger.debug(f'Could not read memory information: {e}')

    return virt_mem
