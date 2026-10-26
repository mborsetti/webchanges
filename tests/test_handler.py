"""Test the handling of jobs."""

from __future__ import annotations

import copy
import importlib.util
import itertools
import os
import tempfile
import time
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from webchanges import handler as handler_module
from webchanges.config import CommandConfig
from webchanges.differs import UnifiedDiffer
from webchanges.handler import JobState, Report, Snapshot, Verb
from webchanges.jobs import JobBase, NotModifiedError, ShellJob, TransientHTTPError, UrlJob
from webchanges.main import Urlwatch
from webchanges.storage import DEFAULT_CONFIG, SsdbSQLite3Storage, YamlConfigStorage, YamlJobsStorage
from webchanges.util import import_module_from_source

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    import pytest_mock

minidb_is_installed = importlib.util.find_spec('minidb') is not None

if minidb_is_installed:
    from webchanges.storage_minidb import SsdbMiniDBStorage

minidb_required = cast(
    'Callable[[Callable], Callable]',
    pytest.mark.skipif(not minidb_is_installed, reason="requires 'minidb' package to be installed"),
)

here = Path(__file__).parent
data_path = here.joinpath('data')

config_file = data_path.joinpath('config.yaml')
ssdb_file = ':memory:'
hooks_file = Path()
ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # ty:ignore[invalid-argument-type]


@pytest.fixture(scope='module', autouse=True)
def _close_module_ssdb_storage() -> Iterator[None]:
    """Close the module-level ``ssdb_storage`` once this module's tests have run.

    So that its sqlite3 connections don't survive to interpreter shutdown and emit ResourceWarnings.
    """
    yield
    ssdb_storage.close()


def test_required_classattrs_in_subclasses() -> None:
    for subclass in JobBase.__subclasses__.values():
        assert hasattr(subclass, '__kind__')
        assert hasattr(subclass, '__required__')
        assert hasattr(subclass, '__optional__')


def test_save_load_jobs() -> None:
    jobs = [
        UrlJob(name='news', url='https://news.orf.at/'),
        ShellJob(name='list homedir', command='ls ~'),
        ShellJob(name='list proc', command='ls /proc'),
    ]

    # tempfile.NamedTemporaryFile() doesn't work on Windows
    # because the returned file object cannot be opened again
    fd, tmpfile = tempfile.mkstemp()
    name = Path(tmpfile)
    YamlJobsStorage([name]).save(jobs)
    jobs2 = YamlJobsStorage([name]).load()
    name.chmod(0o777)
    jobs3 = YamlJobsStorage([name]).load_secure()
    os.close(fd)
    name.unlink()

    assert len(jobs2) == len(jobs)
    # Assert that the shell jobs have been removed due to secure loading in Linux
    if os.name == 'linux':
        assert len(jobs3) == 1


def test_load_config_yaml() -> None:
    if config_file.is_file():
        config = YamlConfigStorage(config_file)
        config.load()
        assert config is not None
        assert config.config is not None
        assert config.config == DEFAULT_CONFIG
    else:
        warnings.warn(f'{config_file} not found', UserWarning, stacklevel=1)


def test_load_jobs_yaml() -> None:
    jobs_file = data_path.joinpath('jobs.yaml')
    if jobs_file.is_file():
        assert len(YamlJobsStorage([jobs_file]).load_secure()) > 0
    else:
        warnings.warn(f'{jobs_file} not found', UserWarning, stacklevel=1)


def test_duplicates_in_jobs_yaml() -> None:
    jobs_file = data_path.joinpath('jobs-duplicate_url.broken_yaml')
    if jobs_file.is_file():
        with pytest.raises(ValueError) as pytest_wrapped_e:
            YamlJobsStorage([jobs_file]).load_secure()
        expected = '\n'.join(  # noqa: FLY002 one line per item reads better than one long literal
            [
                'Each job must have a unique URL/command (for URLs, append #1, #2, etc. to make them unique):',
                '   • https://dupe_1',
                '   • https://dupe_2',
                '   ',
                '   in jobs file ',
            ]
        )
        assert str(pytest_wrapped_e.value)[: len(expected)] == expected
    else:
        warnings.warn(f'{jobs_file} not found', UserWarning, stacklevel=1)


def test_disabled_job() -> None:
    jobs_file = data_path.joinpath('jobs-disabled.yaml')

    urlwatch_config = CommandConfig(
        [],
        here,
        config_file,
        jobs_file,
        hooks_file,
        ssdb_file,  # ty:ignore[invalid-argument-type]
    )
    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # ty:ignore[invalid-argument-type]
    ssdb_storage.delete_all()
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
    urlwatcher.report.job_states = []
    try:
        urlwatcher.run_jobs()

        assert len(urlwatcher.report.job_states) == 1
        assert urlwatcher.report.job_states[0].new_data == 'enabled job\n'
    finally:
        ssdb_storage.close()


def test_same_site_delay_directive(monkeypatch: pytest.MonkeyPatch) -> None:
    """``same_site_delay`` delays a URL job only when an earlier job targets the same site and the directive is set."""
    from webchanges.jobs import _url

    slept: list[float] = []
    monkeypatch.setattr(_url.time, 'sleep', slept.append)

    jobs_file = data_path.joinpath('jobs-disabled.yaml')

    urlwatch_config = CommandConfig(
        [],
        here,
        config_file,
        jobs_file,
        hooks_file,
        ssdb_file,  # ty:ignore[invalid-argument-type]
    )
    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # ty:ignore[invalid-argument-type]
    ssdb_storage.delete_all()
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
    # All three are file:// URIs, which share the same (empty) network location, so jobs 2 and 3 are same-site
    # repeats of job 1.
    urlwatcher.jobs = [
        UrlJob(url=Path(__file__).as_uri(), same_site_delay=0.5),  # first for this site: never delayed
        UrlJob(url=config_file.as_uri(), same_site_delay=0.25),  # same site, directive set: delayed 0.25s
        UrlJob(url=jobs_file.as_uri()),  # same site, no directive: not delayed
    ]
    urlwatcher.report.job_states = []
    try:
        urlwatcher.run_jobs()

        assert len(urlwatcher.report.job_states) == 3
        # Only job 2 is a same-site repeat that also sets the directive, so exactly one sleep of its value occurs.
        assert slept == [0.25]
    finally:
        ssdb_storage.close()


def test_not_modified_after_error_does_not_wipe_snapshot(
    urlwatcher: Urlwatch, ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture
) -> None:
    """An HTTP 304 arriving while the error counter is >0 must not overwrite the stored snapshot with empty data.

    ``worker.run_jobs`` saves the job state when a 304 follows a failed run (to reset ``tries``). As nothing was
    retrieved, the job state must carry the last snapshot forward, or an empty one is stored and the next successful
    run reports a spurious change.
    """
    job = JobBase.unserialize({'url': 'https://www.example.com/'})
    urlwatcher.jobs = [job]

    # Seed the database as if the previous run had failed (tries=2) over a good snapshot.
    ssdb_storage.save(
        guid=job.guid,
        snapshot=Snapshot(
            data='value: 1',
            timestamp=1605147837.0,
            tries=2,
            etag='"abc"',
            mime_type='text/plain',
            error_data={},
        ),
        temporary=False,
    )

    mock_response = mocker.Mock()
    mock_response.status_code = 304
    mock_response.headers = {}
    mocker.patch('httpx.Client.request', return_value=mock_response)

    urlwatcher.run_jobs()
    ssdb_storage._copy_temp_to_permanent(delete=True)

    snapshot = ssdb_storage.load(job.guid)
    assert snapshot.data == 'value: 1'
    assert snapshot.etag == '"abc"'
    assert snapshot.mime_type == 'text/plain'
    assert snapshot.tries == 0


def test_load_hooks_py() -> None:
    hooks_file = data_path.joinpath('hooks_example.py')
    if hooks_file.is_file():
        import_module_from_source('hooks', hooks_file)
    else:
        warnings.warn(f'{hooks_file} not found', UserWarning, stacklevel=1)


def test_run_watcher_sqlite3() -> None:
    jobs_file = data_path.joinpath('jobs.yaml')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # ty:ignore[invalid-argument-type]
    try:
        urlwatch_config = CommandConfig(
            [],
            here,
            config_file,
            jobs_file,
            hooks_file,
            ssdb_file,  # ty:ignore[invalid-argument-type]
        )
        urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
        urlwatcher.run_jobs()
    finally:
        ssdb_storage.close()


@minidb_required
def test_run_watcher_minidb() -> None:
    jobs_file = data_path.joinpath('jobs.yaml')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    ssdb_storage = SsdbMiniDBStorage(ssdb_file)
    try:
        urlwatch_config = CommandConfig(
            [],
            here,
            config_file,
            jobs_file,
            hooks_file,
            ssdb_file,  # ty:ignore[invalid-argument-type]
        )
        urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
        urlwatcher.run_jobs()
    finally:
        ssdb_storage.close()


def prepare_retry_test_sqlite3() -> tuple[Urlwatch, SsdbSQLite3Storage]:
    jobs_file = data_path.joinpath('jobs-invalid_url.yaml')

    config_storage = YamlConfigStorage(config_file)
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # ty:ignore[invalid-argument-type]
    jobs_storage = YamlJobsStorage([jobs_file])

    urlwatch_config = CommandConfig(
        [],
        here,
        config_file,
        jobs_file,
        hooks_file,
        ssdb_file,  # ty:ignore[invalid-argument-type]
    )
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)

    return urlwatcher, ssdb_storage


def test_number_of_tries_in_cache_is_increased_sqlite3() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        snapshot = ssdb_storage.load(guid)

        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)

        snapshot = ssdb_storage.load(guid)

        assert snapshot.tries == 2
        assert urlwatcher.report.job_states[-1].verb == 'error'  # max_tries: 2, so the first error reported
    finally:
        ssdb_storage.close()


def test_report_error_when_out_of_tries_sqlite3() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        snapshot = ssdb_storage.load(guid)
        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)

        report = urlwatcher.report
        assert report.job_states[-1].verb == 'error'  # max_tries: 2, so the first error reported
    finally:
        ssdb_storage.close()


@pytest.mark.parametrize(
    ('verb', 'directives', 'display_error', 'expected'),
    [
        ('error', {}, True, True),
        ('error', {}, False, False),
        ('error', {'suppress_errors': True}, True, False),
        ('error', {'suppress_errors': False}, False, True),
        ('error,repeated', {}, True, True),
        ('error,repeated', {}, False, False),
        ('error,repeated', {'suppress_repeated_errors': True}, True, False),  # issue #189
        ('error,repeated', {'suppress_repeated_errors': False}, True, True),
        ('error,repeated', {'suppress_errors': True}, True, False),
        ('error,repeated', {'suppress_errors': False}, False, True),
        ('unchanged,error_ended', {}, True, True),
        ('unchanged,error_ended', {}, False, False),
        ('unchanged,error_ended', {'suppress_error_ended': True}, True, False),
        ('unchanged,error_ended', {'suppress_errors': True}, True, False),
        ('unchanged,error_ended', {'suppress_errors': False}, False, True),
    ],
)
def test_job_is_reportable_error_suppression(
    verb: str, directives: dict[str, bool], display_error: bool, expected: bool
) -> None:
    """get_filtered_job_states() honors suppress_errors, suppress_repeated_errors and suppress_error_ended.

    Issue #189: 'error,repeated' was shadowed by the startswith('error') guard, so suppress_repeated_errors was never
    consulted.
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['display']['error'] = display_error
    urlwatch = SimpleNamespace(config_storage=SimpleNamespace(config=config))
    report = Report(urlwatch)  # ty:ignore[invalid-argument-type]
    job_state = JobState(ssdb_storage, UrlJob(url='https://example.com/', **directives))
    job_state.verb = cast('Verb', verb)
    assert (len(list(report.get_filtered_job_states([job_state]))) == 1) is expected


def test_reset_tries_to_zero_when_successful_sqlite3() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        snapshot = ssdb_storage.load(guid)
        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)

        snapshot = ssdb_storage.load(guid)
        assert snapshot.tries == 1

        # use an uri that definitely exists
        job = urlwatcher.jobs[0]
        job.url = Path(__file__).as_uri()
        guid = job.guid

        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)

        snapshot = ssdb_storage.load(guid)
        assert snapshot.tries == 0
    finally:
        ssdb_storage.close()


# ---------------------------------------------------------------- run_jobs(): classification of each run

_ERROR = ValueError('boom')
_OTHER_ERROR = ValueError('a different boom')
_TRANSIENT = TransientHTTPError('503 Server Error: Service Unavailable', status_code=503)

Outcome = str | Exception


@pytest.fixture
def run_once(
    urlwatcher: Urlwatch,
    ssdb_storage: SsdbSQLite3Storage,
    mocker: pytest_mock.MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., JobState | None]:
    """Return a function that runs the single job of ``urlwatcher`` once and commits its snapshot, as a real run does.

    The job's retrieval returns the ``outcome`` passed (data) or raises it (an exception). The function returns the
    job's JobState, or None if the run added nothing to the report. The clock in handler advances one second per
    reading, so that consecutive snapshots never share a timestamp.
    """
    clock = itertools.count(1_700_000_000.0)
    fake_time = SimpleNamespace(time=lambda: next(clock), perf_counter=time.perf_counter)
    monkeypatch.setattr(handler_module, 'time', fake_time)

    def run(outcome: Outcome, read_only: bool = False) -> JobState | None:
        if isinstance(outcome, Exception):
            mocker.patch.object(UrlJob, 'retrieve', side_effect=outcome)
        else:
            mocker.patch.object(UrlJob, 'retrieve', return_value=(outcome, '', 'text/plain'))
        urlwatcher.report.job_states = []
        urlwatcher.run_jobs(read_only=read_only)
        ssdb_storage._copy_temp_to_permanent(delete=True)
        return urlwatcher.report.job_states[0] if urlwatcher.report.job_states else None

    return run


@pytest.mark.parametrize(
    ('directives', 'steps'),
    [
        pytest.param(
            {},
            [('a', 'new', 'a', 0), ('a', 'unchanged', 'a', 0), ('b', 'changed', 'b', 0)],
            id='new-unchanged-changed',
        ),
        pytest.param(
            {},
            [
                ('a', 'new', 'a', 0),
                (_ERROR, 'error', 'a', 1),
                (_ERROR, 'error,repeated', 'a', 2),
                (_OTHER_ERROR, 'error', 'a', 3),
                ('a', 'unchanged', 'a', 0),
            ],
            id='errors-keep-last-good-snapshot',
        ),
        pytest.param(
            {},
            [('a', 'new', 'a', 0), (_ERROR, 'error', 'a', 1), ('b', 'changed', 'b', 0)],
            id='error-then-new-data',
        ),
        pytest.param(
            {'suppress_repeated_errors': True},
            [
                ('a', 'new', 'a', 0),
                (_ERROR, 'error', 'a', 1),
                (_ERROR, 'error,repeated', 'a', 2),
                ('a', 'unchanged,error_ended', 'a', 0),
            ],
            id='suppress_repeated_errors-reports-error-ended',
        ),
        pytest.param(
            {},
            [('a', 'new', 'a', 0), (_TRANSIENT, 'error', 'a', 1), ('a', 'unchanged', 'a', 0)],
            id='transient-error',
        ),
        pytest.param(
            {'max_tries': 3},
            [
                ('a', 'new', 'a', 0),
                (_ERROR, None, 'a', 1),
                (_ERROR, None, 'a', 2),
                ('a', 'unchanged', 'a', 0),
            ],
            id='max_tries-not-reached',
        ),
        pytest.param(
            {'max_tries': 3},
            [
                ('a', 'new', 'a', 0),
                (_ERROR, None, 'a', 1),
                (_ERROR, None, 'a', 2),
                (_ERROR, 'error', 'a', 3),  # the first error reported is not a repeated one
                (_ERROR, 'error,repeated', 'a', 4),
                ('a', 'unchanged', 'a', 0),
            ],
            id='max_tries-reached',
        ),
        pytest.param(
            {},
            [(_ERROR, 'error', '', 1), (_ERROR, 'error,repeated', '', 2), ('a', 'new', 'a', 0)],
            id='first-success-after-errors-is-new',
        ),
        pytest.param(
            {},
            [('', 'new', '', 0), ('a', 'changed', 'a', 0)],
            id='empty-data-is-data',
        ),
        pytest.param(
            {'empty_as_error': 'ignore'},
            [('a', 'new', 'a', 0), (' \n', None, 'a', 0), ('a', 'unchanged', 'a', 0)],
            id='empty_as_error-ignore',
        ),
        pytest.param(
            {'compared_versions': 3},
            [('a', 'new', 'a', 0), ('b', 'changed', 'b', 0), ('a', 'unchanged', 'b', 0), ('c', 'changed', 'c', 0)],
            id='compared_versions',
        ),
        pytest.param(
            {'treat_new_as_changed': True},
            [('a', 'changed', 'a', 0), ('a', 'unchanged', 'a', 0), ('b', 'changed', 'b', 0)],
            id='treat_new_as_changed',
        ),
        pytest.param(
            {'treat_new_as_changed': True},
            [(_ERROR, 'error', '', 1), ('a', 'changed', 'a', 0)],
            id='treat_new_as_changed-after-errors',
        ),
    ],
)
def test_run_classification(
    urlwatcher: Urlwatch,
    ssdb_storage: SsdbSQLite3Storage,
    run_once: Callable[..., JobState | None],
    directives: dict[str, object],
    steps: list[tuple[Outcome, Verb | None, str, int]],
) -> None:
    """Over consecutive runs, each run of a job gets the expected verb and database state.

    The verb is None when nothing is reported; the database keeps the expected snapshot data and count of consecutive
    failed runs ('tries').

    Notably: a failed run never replaces the last good data, so the run after an error is compared against it; the
    'error ended' notice is only produced with suppress_repeated_errors (which mutes the error notices in between);
    an ignored error leaves the database untouched; and with compared_versions, data matching any of the recent
    snapshots is unchanged (and is not saved again).
    """
    job = JobBase.unserialize({'url': 'https://www.example.com/', **directives})
    urlwatcher.jobs = [job]
    for i, (outcome, verb, stored_data, tries) in enumerate(steps):
        job_state = run_once(outcome)
        assert (job_state.verb if job_state else None) == verb, f'run {i}: {outcome!r}'
        snapshot = ssdb_storage.load(job.guid)
        assert (snapshot.data, snapshot.tries) == (stored_data, tries), f'run {i}: {outcome!r}'


def test_run_treat_new_as_changed_diff(urlwatcher: Urlwatch, run_once: Callable[..., JobState | None]) -> None:
    """With treat_new_as_changed, a new job's report is a diff from empty content, every line added."""
    urlwatcher.jobs = [JobBase.unserialize({'url': 'https://www.example.com/', 'treat_new_as_changed': True})]
    job_state = run_once('line 1\nline 2')
    assert job_state is not None
    diff = job_state.get_diff()
    assert '--- @ NEW' in diff
    assert '+line 1\n+line 2' in diff


@pytest.mark.parametrize(
    ('suppress_repeated_errors', 'notified'),
    [(False, [False, False, True, True, False]), (True, [False, False, True, False, True])],
)
def test_run_max_tries_notifications(
    urlwatcher: Urlwatch,
    run_once: Callable[..., JobState | None],
    suppress_repeated_errors: bool,
    notified: list[bool],
) -> None:
    """With max_tries: 3, a failing job is notified from its third consecutive failure.

    Also with suppress_repeated_errors, which then mutes the following failures and notifies the recovery. (The errors
    saved by the unreported failures used to make the third one a repeated error, which suppress_repeated_errors muted.)
    """
    job = JobBase.unserialize(
        {'url': 'https://www.example.com/', 'max_tries': 3, 'suppress_repeated_errors': suppress_repeated_errors}
    )
    urlwatcher.jobs = [job]
    run_once('a')
    job_states = [run_once(outcome) for outcome in [_ERROR, _ERROR, _ERROR, _ERROR, 'a']]
    assert [
        job_state is not None and bool(list(urlwatcher.report.get_filtered_job_states([job_state])))
        for job_state in job_states
    ] == notified


@pytest.mark.parametrize(
    ('outcome', 'verb'),
    [
        ('a', 'unchanged'),  # resets tries, which would otherwise be saved
        ('b', 'changed'),
        (_OTHER_ERROR, 'error'),
        (NotModifiedError(304), 'unchanged'),  # resets tries, which would otherwise be saved
    ],
)
def test_run_read_only_leaves_database_untouched(
    urlwatcher: Urlwatch,
    ssdb_storage: SsdbSQLite3Storage,
    run_once: Callable[..., JobState | None],
    outcome: Outcome,
    verb: Verb,
) -> None:
    """A read-only run (--test-reporter with a joblist) classifies the job as usual but saves nothing.

    On every path, including those that would reset the count of failed runs after an error.
    """
    job = JobBase.unserialize({'url': 'https://www.example.com/'})
    urlwatcher.jobs = [job]
    run_once('a')
    run_once(_ERROR)  # so that tries > 0
    history = ssdb_storage.get_history_snapshots(job.guid)

    job_state = run_once(outcome, read_only=True)

    assert job_state is not None
    assert job_state.verb == verb
    assert ssdb_storage.get_history_snapshots(job.guid) == history


def test_run_new_job_read_only_saves_nothing(
    urlwatcher: Urlwatch, ssdb_storage: SsdbSQLite3Storage, run_once: Callable[..., JobState | None]
) -> None:
    """A read-only run of a job never run before reports it as new without creating its first snapshot."""
    job = JobBase.unserialize({'url': 'https://www.example.com/'})
    urlwatcher.jobs = [job]
    job_state = run_once('a', read_only=True)
    assert job_state is not None
    assert job_state.verb == 'new'
    assert ssdb_storage.get_history_snapshots(job.guid) == []


def test_differ_error_keeps_change_for_next_run(
    urlwatcher: Urlwatch,
    ssdb_storage: SsdbSQLite3Storage,
    run_once: Callable[..., JobState | None],
    mocker: pytest_mock.MockerFixture,
) -> None:
    """When the differ fails, the new snapshot is not kept, so the next run reports the change again.

    The user sees the error instead of the diff, so keeping the snapshot would lose the change.
    """
    job = JobBase.unserialize({'url': 'https://www.example.com/'})
    urlwatcher.jobs = [job]
    run_once('a')

    # A changed run, up to the reporting stage: its snapshot is still in the temporary database at that point.
    mocker.patch.object(UrlJob, 'retrieve', return_value=('b', '', 'text/plain'))
    urlwatcher.report.job_states = []
    urlwatcher.run_jobs()
    job_state = urlwatcher.report.job_states[0]
    assert job_state.verb == 'changed'
    mocker.patch.object(UnifiedDiffer, 'differ', side_effect=RuntimeError('differ bug'))
    diff = job_state.get_diff()
    assert 'Differ unified with directive(s) None encountered an error' in diff
    assert 'differ bug' in diff
    ssdb_storage._copy_temp_to_permanent(delete=True)  # end of the run

    assert ssdb_storage.load(job.guid).data == 'a'
    job_state = run_once('b')
    assert job_state is not None
    assert job_state.verb == 'changed'


@minidb_required
def prepare_retry_test_minidb() -> tuple[Urlwatch, SsdbMiniDBStorage]:
    jobs_file = data_path.joinpath('jobs-invalid_url.yaml')
    config_storage = YamlConfigStorage(config_file)
    ssdb_storage = SsdbMiniDBStorage(ssdb_file)
    jobs_storage = YamlJobsStorage([jobs_file])

    urlwatch_config = CommandConfig(
        [],
        here,
        config_file,
        jobs_file,
        hooks_file,
        ssdb_file,  # ty:ignore[invalid-argument-type]
    )
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)

    return urlwatcher, ssdb_storage


@minidb_required
def test_number_of_tries_in_cache_is_increased_minidb() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.guid)
        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.guid)

        assert snapshot.tries == 2
        assert urlwatcher.report.job_states[-1].verb == 'error'
    finally:
        ssdb_storage.close()


@minidb_required
def test_report_error_when_out_of_tries_minidb() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.guid)
        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        urlwatcher.run_jobs()

        report = urlwatcher.report
        assert report.job_states[-1].verb == 'error'
    finally:
        ssdb_storage.close()


@minidb_required
def test_reset_tries_to_zero_when_successful_minidb() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())
        assert snapshot.tries == 0

        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())
        assert snapshot.tries == 1

        # use an url that definitely exists
        job = urlwatcher.jobs[0]
        job.url = data_path.joinpath('jobs.yaml').as_uri()

        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())
        assert snapshot.tries == 0
    finally:
        ssdb_storage.close()
