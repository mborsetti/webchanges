"""The worker that runs jobs in parallel.  Called from main module."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

__lazy_modules__ = ['concurrent.futures', 'contextlib', 'gc', 'urllib.parse']

import gc
import logging
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from typing import TYPE_CHECKING

from webchanges.command import UrlwatchCommand
from webchanges.handler import JobState
from webchanges.jobs import NotModifiedError, TransientHTTPError, UrlJobBase
from webchanges.util import missing_dependency

# The optional dependency psutil is imported only when browser jobs are run (see missing_dependency() in
# webchanges/util.py).

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

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
        logger.debug('Could not tear down CDP cache on worker thread: %s', e)


def run_jobs(urlwatcher: Urlwatch, read_only: bool = False) -> None:
    """Process (run) jobs in parallel.

    :param urlwatcher: The :py:class:`Urlwatch` orchestrator.
    :param read_only: If True, skip every ``job_state.save()`` call so the snapshot DB is
        unchanged. Used by ``--test-reporter`` + joblist to preview a reporter without
        committing new snapshots.

    :raises IndexError: If any index(es) is/are out of range.
    """

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
                if job_state.exception is not None:
                    # Oops, we have captured an error (which could also be 304 or a Playwright timeout)
                    _classify_error(urlwatcher, job_state, read_only)
                else:
                    _classify_data(urlwatcher, job_state, read_only)

    jobs = list(UrlwatchCommand(urlwatcher).jobs_from_joblist())

    jobs = _activate_same_site_delays(jobs)

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


def _activate_same_site_delays(jobs: list[JobBase]) -> list[JobBase]:
    """Activate each URL job's ``same_site_delay`` when it shares a network location with an earlier job.

    Because jobs run in parallel, several jobs pointing at the same site (network location, e.g. ``www.example.com``)
    can hit it at the exact same instant and get rate-limited or blocked. The first job for a given network location
    runs with no delay; for each subsequent one, its configured ``same_site_delay`` (if any) is copied into the internal
    ``_delay`` that :py:meth:`JobBase.retrieve` sleeps for before fetching. Jobs without the directive set, and jobs
    whose network location is unique, are never delayed.

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
                    'Job %s: Will wait %ss before retrieving '
                    '(shares network location %r with an earlier job; same_site_delay directive)',
                    job.index_number,
                    job._delay,
                    netloc,
                )
    return jobs


def _classify_unchanged(urlwatcher: Urlwatch, job_state: JobState, read_only: bool) -> None:
    """Reset the job's failure count and report it as unchanged.

    :param urlwatcher: The :py:class:`Urlwatch` orchestrator.
    :param job_state: The processed job state.
    :param read_only: If True, do not save the job state.
    """
    if job_state.tries > 0:
        job_state.tries = 0
        if not read_only:
            job_state.save()
    if job_state.old_error_data and job_state.job.suppress_repeated_errors:
        urlwatcher.report.unchanged_from_error(job_state)
    else:
        urlwatcher.report.unchanged(job_state)


def _classify_error(urlwatcher: Urlwatch, job_state: JobState, read_only: bool) -> None:
    """Save and report a job whose run raised an exception (including HTTP 304).

    ``tries`` was incremented by :py:meth:`JobState.process`; the error is only reported once it reaches the job's
    ``max_tries``.

    :param urlwatcher: The :py:class:`Urlwatch` orchestrator.
    :param job_state: The processed job state.
    :param read_only: If True, do not save the job state.
    """
    max_tries = job_state.job.max_tries or 0
    if job_state.error_ignored:
        # We captured an error but are ignoring it
        logger.info('Job %s: Job resulted in an error that is ignored due to directives', job_state.job.index_number)
    elif isinstance(job_state.exception, NotModifiedError):
        # We captured a 304 Not Modified
        logger.info('Job %s: Job has not changed (HTTP 304 response)', job_state.job.index_number)
        _classify_unchanged(urlwatcher, job_state, read_only)
    elif job_state.tries < max_tries:
        # We're not reporting the error yet because we haven't yet hit 'max_tries'
        logger.debug(
            'Job %s: Job error suppressed as cumulative number of failures (%s) does not exceed max_tries=%s',
            job_state.job.index_number,
            job_state.tries,
            max_tries,
        )
        if not read_only:
            job_state.save()
    else:
        # Reporting the error
        logger.debug(
            'Job %s: Job error flagged as error as max_tries=%s has been met or exceeded (%s',
            job_state.job.index_number,
            max_tries,
            job_state.tries,
        )
        if isinstance(job_state.exception, TransientHTTPError):
            # We captured a transient error
            logger.info(
                'Job %s: Job has received an HTTP response of a typically transient nature',
                job_state.job.index_number,
            )
            job_state.new_data = job_state.old_data
            job_state.new_etag = job_state.old_etag
            job_state.new_mime_type = job_state.old_mime_type
        if not read_only:
            job_state.save()
        # The first error reported is never a repeated one, even if the same error was saved by the runs whose errors
        # max_tries kept from being reported
        if job_state.tries > max(max_tries, 1) and job_state.new_error_data == job_state.old_error_data:
            urlwatcher.report.error_same_error(job_state)
        else:
            urlwatcher.report.error(job_state)


def _classify_data(urlwatcher: Urlwatch, job_state: JobState, read_only: bool) -> None:
    """Save and report a job that ran successfully as new, changed or unchanged.

    :param urlwatcher: The :py:class:`Urlwatch` orchestrator.
    :param job_state: The processed job state.
    :param read_only: If True, do not save the job state.
    """
    if job_state.old_data or (job_state.old_timestamp != 0 and not job_state.old_error_data):
        # This is not the first time running this job successfully (we have snapshots of data, not only of errors)
        if job_state.new_data == job_state.old_data or job_state.new_data in job_state.history_dic_snapshots:
            # Exactly matches one of the previous snapshots
            _classify_unchanged(urlwatcher, job_state, read_only)
        else:
            # It has different data, so we save it. We used to do fuzzy matching, but it no longer makes sense.
            job_state.tries = 0
            if not read_only:
                job_state.save()
            urlwatcher.report.changed(job_state)
    else:
        # We have never run this job successfully before (there are no snapshots, or only of errors)
        job_state.tries = 0
        if not read_only:
            job_state.save()
        if job_state.job.treat_new_as_changed:
            # Report it as a change from empty content, so that its differ and diff_filters apply
            logger.debug('Job %s: New job reported as changed (treat_new_as_changed)', job_state.job.index_number)
            urlwatcher.report.changed(job_state)
        else:
            urlwatcher.report.new(job_state)


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
            'Running %s CDP browser job(s) on a single dedicated thread (one manual browser '
            'authorization per unique connect_over_cdp URL per run) concurrently with '
            '%s non-CDP browser job(s) using up to %s workers.',
            len(cdp_jobs),
            len(non_cdp_browser_jobs),
            max_workers,
        )
        with ThreadPoolExecutor(max_workers=2) as runner_executor:
            cdp_future = runner_executor.submit(job_runner, cdp_jobs, 1)
            other_future = runner_executor.submit(job_runner, non_cdp_browser_jobs, max_workers)
            cdp_future.result()
            other_future.result()
    elif cdp_jobs:
        logger.debug(
            'Running %s CDP browser job(s) on a single dedicated thread (one manual browser '
            'authorization per unique connect_over_cdp URL per run).',
            len(cdp_jobs),
        )
        job_runner(cdp_jobs, 1)
    else:
        logger.debug(
            "Running jobs that require Chrome (i.e. with 'use_browser: true') in parallel with %s max_workers.",
            max_workers,
        )
        job_runner(non_cdp_browser_jobs, max_workers)


def get_virt_mem_mib() -> float:
    """Return the amount of virtual memory available.

    This is the memory that can be given instantly to processes without the system going into swap.

    :returns: The amount of virtual memory available in MiB (IEC).
    """
    try:
        import psutil
    except ImportError as e:  # pragma: no cover
        raise missing_dependency(
            e, 'psutil', used_by="the 'use_browser: true' job directive", extra='use_browser'
        ) from e
    try:
        virt_mem: float = psutil.virtual_memory().available
        virt_mem /= 1_048_576
        logger.debug(
            'Found %.0f MiB of available physical memory (plus %.0f MiB of swap).', virt_mem, psutil.swap_memory().free
        )
    except psutil.Error as e:  # pragma: no cover
        virt_mem = 0
        logger.debug('Could not read memory information: %s', e)

    return virt_mem
