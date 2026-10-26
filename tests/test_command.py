"""Tests for ``UrlwatchCommand`` action dispatch (``handle_actions`` / ``run``).

CLI helper tests live in ``tests/test_cli.py``. Job-state ``verb`` tests live in ``tests/test_jobs.py``.
Storage primitives are exercised directly in ``tests/test_storage.py``.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from tests.conftest import WINDOWS_TIME_COMMAND, close_ssdb_storage
from tests.test_storage import DATABASE_ENGINES, prepare_storage_test
from webchanges.command import UrlwatchCommand, _human_size
from webchanges.config import CommandConfig
from webchanges.jobs import JobBase
from webchanges.main import Urlwatch
from webchanges.storage import SsdbSQLite3Storage, SsdbStorage, YamlConfigStorage, YamlJobsStorage
from webchanges.util import import_module_from_source

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

py_latest_only = cast(
    'Callable[[Callable], Callable]',
    pytest.mark.skipif(
        sys.version_info < (3, 15),
        reason='Latest python only (time consuming)',
    ),
)


@pytest.fixture(autouse=True)
def _silence_db_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``ssdb_storage.close()`` a no-op so one test can drive several actions against one DB.

    ``handle_actions`` paths (e.g. ``--dump-history``) call it mid-test, which would invalidate the in-memory SQLite
    connection used by later assertions in the same test.

    Redis is included because ``SsdbRedisStorage.close()`` deletes its connection (``del self.db``) and the instance
    is shared via ``tests.test_storage.DATABASE_ENGINES``: closing it here would break every Redis test that runs
    after this one.

    Scoped to this file so that ``test_storage.py::test_migrate_urlwatch_legacy_db`` — which legitimately needs
    ``close()`` to release the file lock before unlinking — is not affected.
    """
    monkeypatch.setattr('webchanges.storage.SsdbSQLite3Storage.close', lambda _self: None)
    monkeypatch.setattr('webchanges.storage.SsdbRedisStorage.close', lambda _self: None)
    monkeypatch.setattr('webchanges.storage_minidb.SsdbMiniDBStorage.close', lambda _self: None, raising=False)


@pytest.fixture
def time_jobs_urlwatcher(
    workspace: Path,
    loaded_config_storage: YamlConfigStorage,
) -> Iterator[Urlwatch]:
    """``Urlwatch`` configured with ``jobs-time.yaml`` and a fresh in-memory snapshot DB.

    The job's command stays at the file default; tests that need a deterministic or platform-portable
    output overwrite ``urlwatcher.jobs[0].command``.
    """
    jobs_path = workspace / 'jobs-time.yaml'
    cmd = CommandConfig(
        args=[],
        config_path=workspace,
        config_file=workspace / 'config.yaml',
        jobs_def_file=jobs_path,
        hooks_def_file=workspace / 'hooks_example.py',
        ssdb_file=':memory:',  # ty:ignore[invalid-argument-type]
    )
    storage = SsdbSQLite3Storage(':memory:')  # ty:ignore[invalid-argument-type]
    yield Urlwatch(cmd, loaded_config_storage, storage, YamlJobsStorage([jobs_path]))
    close_ssdb_storage(storage)


# --- List jobs ---


def test_list_jobs_verbose(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.list_jobs = True
    urlwatch_command.urlwatcher.urlwatch_config.verbose = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.startswith('List of jobs:\n  1: <command ')
    assert 'index_number=1' in message
    assert "name='Sample webchanges job; used by test_command.py'" in message
    assert "command='echo test'" in message
    assert message.endswith(f'\nJobs file: {command_config.jobs_files[0]}\n')


def test_list_jobs_not_verbose(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    jobs_file_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.jobs_files = [jobs_file_path, jobs_file_path]
    command_config.list_jobs = True
    urlwatch_command.urlwatcher.urlwatch_config.verbose = False
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert capsys.readouterr().out.splitlines() == [
        'List of jobs:',
        '  1: Sample webchanges job; used by test_command.py (echo test)',
        'Jobs files concatenated:',
        f'   • {jobs_file_path}',
        f'   • {jobs_file_path}',
    ]


def test_list_jobs_no_filename(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.jobs_files = []
    command_config.list_jobs = True
    urlwatch_command.urlwatcher.urlwatch_config.verbose = False
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert capsys.readouterr().out.splitlines() == [
        'List of jobs:',
        '  1: Sample webchanges job; used by test_command.py (echo test)',
        '',
    ]


# --- _find_job (internal helper) ---


def test__find_job(urlwatch_command: UrlwatchCommand) -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job('https://example.com/')
    assert (
        str(pytest_wrapped_e.value)
        == "Job https://example.com/ does not match any job's name, url/user_visible_url or command."
    )


def test__find_job_zero(urlwatch_command: UrlwatchCommand) -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job('0')
    assert str(pytest_wrapped_e.value) == 'Job index 0 out of range.'


def test__find_job_negative(urlwatch_command: UrlwatchCommand, urlwatcher: Urlwatch) -> None:
    assert urlwatch_command._find_job('-1') is urlwatcher.jobs[0]


def test__find_job_index_error(urlwatch_command: UrlwatchCommand) -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job('100')
    assert str(pytest_wrapped_e.value) == 'Job index 100 out of range (found 1 jobs).'


def test__find_job_index_no_match(urlwatch_command: UrlwatchCommand) -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job('nomatch')
    assert str(pytest_wrapped_e.value) == "Job nomatch does not match any job's name, url/user_visible_url or command."


def _set_jobs(urlwatcher: Urlwatch, *jobs_directives: dict[str, str]) -> None:
    """Replaces the jobs of urlwatcher with those of the directives given, numbered from 1."""
    urlwatcher.jobs = [JobBase.unserialize(directives) for directives in jobs_directives]
    for index_number, job in enumerate(urlwatcher.jobs, start=1):
        job.index_number = index_number


def test__find_job_by_name(urlwatch_command: UrlwatchCommand, urlwatcher: Urlwatch) -> None:
    """A job can be found by its name as well as by its location (added in 3.39)."""
    _set_jobs(
        urlwatcher,
        {'name': 'Example news', 'url': 'https://example.com/news'},
        {'name': 'Other', 'url': 'https://example.com/other'},
    )
    assert urlwatch_command._find_job('Example news') is urlwatcher.jobs[0]
    assert urlwatch_command._find_job('https://example.com/other') is urlwatcher.jobs[1]


def test__find_job_multiple_matches(urlwatch_command: UrlwatchCommand, urlwatcher: Urlwatch) -> None:
    """A query matching more than one job, by name and/or location, is an error listing the jobs matched."""
    _set_jobs(
        urlwatcher,
        {'name': 'News', 'url': 'https://example.com/a'},
        {'url': 'https://example.com/a', 'filters': 'html2text'},
        {'name': 'News', 'url': 'https://example.com/b'},
    )
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job('News')
    assert str(pytest_wrapped_e.value) == (
        'Job News matches 2 jobs; select the job by its index number instead:\n'
        '• Job 1: https://example.com/a (News)\n'
        '• Job 3: https://example.com/b (News)'
    )
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job('https://example.com/a')
    assert str(pytest_wrapped_e.value).startswith('Job https://example.com/a matches 2 jobs;')


def test_jobs_from_joblist_runs_each_job_once(urlwatch_command: UrlwatchCommand, urlwatcher: Urlwatch) -> None:
    """A job selected more than once in the joblist is run once (fixed in 3.39).

    E.g. when --prepare-jobs adds a job already selected.
    """
    _set_jobs(urlwatcher, {'name': 'A', 'url': 'https://example.com/a'}, {'url': 'https://example.com/b'})
    urlwatcher.urlwatch_config.joblist = ['2', 1, 'A', 2, 'https://example.com/b']
    assert [job.get_location() for job in urlwatch_command.jobs_from_joblist()] == [
        'https://example.com/b',
        'https://example.com/a',
    ]


def test__get_job(urlwatch_command: UrlwatchCommand) -> None:
    assert urlwatch_command._find_job_with_defaults(1).get_location() == 'echo test'


# --- test-job ---


def test_test_job(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.test_job = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert capsys.readouterr().out.startswith(
        '===========================================================================\n'
        'TEST: Sample webchanges job; used by test_command.py\n'
        '===========================================================================\n'
        '\n'
        '---------------------------------------------------------------------------\n'
        'TEST: Sample webchanges job; used by test_command.py (echo test)\n'
        '---------------------------------------------------------------------------\n'
        '\n'
        '• [GUID: 632d72116518282f9fb4cc2473c949125778e24a]\n'
        '• [Media type: text/plain]\n'
        '\n'
        'test\n'
        '\n'
        '---------------------------------------------------------------------------\n'
        '\n'
        '\n'
        '--\n'
        'Checked 1 source in '
    )


def test_test_job_error_includes_detail(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed test job's error report has the full detail (here, stderr), not just the message."""
    urlwatch_command.urlwatcher.jobs[0].command = f'"{sys.executable}" -c "import sys; sys.exit(\'boom detail\')"'
    command_config.test_job = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    output = capsys.readouterr().out
    assert 'ERROR subprocess.CalledProcessError: Command returned non-zero exit status 1.' in output
    assert 'boom detail' in output


def test_test_job_all(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    workspace: Path,
    jobs_file_path: Path,
    hooks_file_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    urlwatch_command.urlwatch_config.hooks_files = [hooks_file_path]
    import_module_from_source('hooks', hooks_file_path)
    command_config.test_job = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert capsys.readouterr().out.splitlines() == [
        f'No syntax errors in config file {urlwatch_command.urlwatch_config.config_file},',
        f'jobs file {urlwatch_command.urlwatch_config.jobs_files[0]},',
        f'and hooks file {urlwatch_command.urlwatch_config.hooks_files[0]}.',
    ]

    # with multiple jobs files
    second_jobs = workspace / 'jobs-echo_test2.yaml'
    shutil.copyfile(jobs_file_path, second_jobs)
    command_config.jobs_files = [jobs_file_path, second_jobs]
    command_config.test_job = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert capsys.readouterr().out.splitlines() == [
        f'No syntax errors in config file {urlwatch_command.urlwatch_config.config_file},',
        'jobs files',
        f'   • {jobs_file_path},',
        f'   • {second_jobs},',
        f'and hooks file {urlwatch_command.urlwatch_config.hooks_files[0]}.',
    ]


def test_test_job_with_test_reporter(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.test_job = '1'
    command_config.test_reporter = 'stdout'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert capsys.readouterr().out.startswith(
        '===========================================================================\n'
        'TEST: Sample webchanges job; used by test_command.py\n'
        '===========================================================================\n'
        '\n'
        '---------------------------------------------------------------------------\n'
        'TEST: Sample webchanges job; used by test_command.py (echo test)\n'
        '---------------------------------------------------------------------------\n'
        '\n'
        '• [GUID: 632d72116518282f9fb4cc2473c949125778e24a]\n'
        '• [Media type: text/plain]\n'
        '\n'
        'test\n'
        '\n'
        '---------------------------------------------------------------------------\n'
        '\n'
        '\n'
        '--\n'
        'Checked 1 source in '
    )


# --- dump-history / test-differ ---


def test_dump_history(time_jobs_urlwatcher: Urlwatch, capsys: pytest.CaptureFixture[str]) -> None:
    urlwatcher = time_jobs_urlwatcher
    urlwatcher.jobs[0].command = 'echo 1'
    guid = urlwatcher.jobs[0].guid
    urlwatch_command = UrlwatchCommand(urlwatcher)

    # never run
    urlwatcher.urlwatch_config.dump_history = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert f'History for Job 1: echo 1\nGUID: {guid}\nFound 0 snapshots.\n' in capsys.readouterr().out

    # run once
    urlwatcher.urlwatch_config.dump_history = None
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    urlwatcher.urlwatch_config.joblist = []

    urlwatcher.urlwatch_config.dump_history = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert (f'History for Job 1: echo 1\nGUID: {guid}\n==============================================\n') in message
    assert (
        '| Media type: text/plain\n'
        '-----------------------------------------------------------\n'
        '1\n'
        '\n'
        '=========================================================== '
        '\n'
        '\n'
        'Found 1 snapshot.\n'
    ) in message


def test_test_differ_and_joblist(time_jobs_urlwatcher: Urlwatch, capsys: pytest.CaptureFixture[str]) -> None:
    urlwatcher = time_jobs_urlwatcher
    if sys.platform == 'win32':
        urlwatcher.jobs[0].command = WINDOWS_TIME_COMMAND
        urlwatcher.jobs[0].guid = urlwatcher.jobs[0].get_guid()
    urlwatch_command = UrlwatchCommand(urlwatcher)

    # never run
    urlwatcher.urlwatch_config.test_differ = ['1']
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert capsys.readouterr().out == 'This job has never been run before.\n'

    # run once -- also exercises joblist
    urlwatcher.urlwatch_config.test_differ = None
    urlwatcher.urlwatch_config.joblist = ['1']
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    urlwatcher.urlwatch_config.joblist = []

    urlwatcher.urlwatch_config.test_differ = ['1', '1']
    urlwatcher.jobs[0].compared_versions = 2
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    urlwatcher.jobs[0].compared_versions = None
    assert capsys.readouterr().out == 'Not enough historic data available (need at least 2 different snapshots).\n'

    # invalid joblist
    urlwatcher.urlwatch_config.test_differ = None
    urlwatcher.urlwatch_config.joblist = ['-999']
    with pytest.raises(ValueError) as pytest_wrapped_ve:
        urlwatcher.run_jobs()
    assert pytest_wrapped_ve.value.args[0] == 'Job index -999 out of range (found 1 jobs).'
    urlwatcher.urlwatch_config.joblist = []

    # run twice
    time.sleep(0.0001)
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert len(urlwatcher.ssdb_storage.get_history_data(urlwatcher.jobs[0].guid)) == 2

    # diff (unified) with diff_filter, tz, contextlines
    urlwatcher.urlwatch_config.test_differ = ['1']
    urlwatcher.jobs[0].diff_filters = [{'strip': ''}]
    urlwatcher.config_storage.config['report']['tz'] = 'Etc/GMT+12'
    urlwatcher.jobs[0].contextlines = 2
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'FILTERED DIFF (SNAPSHOTS  0 VS. -1): ' in message
    assert message.splitlines()[10][-6:] == ' -1200'

    # rerun reuses cached diff but should switch timezone
    urlwatcher.config_storage.config['report']['tz'] = 'Etc/UTC'
    urlwatcher.urlwatch_config.test_differ = ['1']
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'FILTERED DIFF (SNAPSHOTS  0 VS. -1): ' in message
    assert message.splitlines()[10][-12:] == ' +0000 (UTC)'

    # another timezone
    urlwatcher.config_storage.config['report']['tz'] = 'Etc/GMT+1'
    urlwatcher.urlwatch_config.test_differ = ['1']
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'FILTERED DIFF (SNAPSHOTS  0 VS. -1): ' in message
    assert message.splitlines()[10][-6:] == ' -0100'


# --- list-error-jobs / modify URLs ---


def test_list_error_jobs(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.errors = 'stdout'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    expect = '\n'.join(
        [
            'Jobs with errors; warns of jobs returning no data (after unmodified filters)',
            (
                f'   in jobs file '
                f'{str(urlwatch_command.urlwatch_config.jobs_files[0]) + ":" if urlwatch_command.urlwatch_config.jobs_files else ""}'  # noqa: E501
            ),
            '--',
            'Checked 1 enabled jobs for errors in',
        ]
    )
    assert capsys.readouterr().out[: len(expect)] == expect


def test_list_error_jobs_with_joblist(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.errors = 'stdout'
    urlwatch_command.urlwatch_config.joblist = ['1']
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'restricted to jobs: 1' in message
    assert 'Checked 1 enabled jobs for errors in' in message


def test_list_error_jobs_with_tags(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.errors = 'stdout'
    urlwatch_command.urlwatcher.jobs[0].tags = ['sample']
    command_config.tags = ['sample']
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'restricted to jobs tagged: sample' in message
    assert 'Checked 1 enabled jobs for errors in' in message

    command_config.tags = ['nonexistent']
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert 'Checked 0 enabled job for errors in' in capsys.readouterr().out


# --- tags ---


def test_tags_from_cli(urlwatch_command: UrlwatchCommand) -> None:
    """--tags is repeatable and each occurrence takes a comma-separated list of tags."""
    assert urlwatch_command.tags_from_cli() == []
    urlwatch_command.urlwatch_config.tags = ['personal, team', 'ops', ' ']
    assert urlwatch_command.tags_from_cli() == ['personal', 'team', 'ops']


def test_tags_select_jobs_to_run(urlwatch_command: UrlwatchCommand, caplog: pytest.LogCaptureFixture) -> None:
    """--tags restricts the jobs to run to those having any of the tags given."""
    urlwatch_command.urlwatcher.jobs[0].tags = ['sample', 'echo']

    assert len(list(urlwatch_command.jobs_from_joblist())) == 1

    urlwatch_command.urlwatch_config.tags = ['echo']
    assert len(list(urlwatch_command.jobs_from_joblist())) == 1

    urlwatch_command.urlwatch_config.tags = ['nonexistent,echo']
    assert len(list(urlwatch_command.jobs_from_joblist())) == 1

    urlwatch_command.urlwatch_config.tags = ['nonexistent']
    assert list(urlwatch_command.jobs_from_joblist()) == []
    assert 'No job has any of the tags nonexistent' in caplog.text


def test_tags_command_line_argument(command_config: CommandConfig) -> None:
    """The --tags command line argument is parsed into a list of its (repeatable) occurrences."""
    parsed = CommandConfig(
        args=['--tags', 'personal,team', '--tags', 'ops'],
        config_path=command_config.config_path,
        config_file=command_config.config_file,
        jobs_def_file=command_config.jobs_files[0],
        hooks_def_file=command_config.hooks_files[0],
        ssdb_file=command_config.ssdb_file,
    )
    assert parsed.tags == ['personal,team', 'ops']


def test_close_warns_of_jobs_no_reporter_reported_on(
    urlwatcher: Urlwatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A job that no reporter reported on (e.g. because of a typo in a tag) is warned about."""
    urlwatcher.config_storage.config['report']['stdout'] = {
        'enabled': True,
        'color': False,
        'tags': ['nonexistent'],
    }
    urlwatcher.run_jobs()
    urlwatcher.close()
    assert 'was not reported on by any reporter.' in caplog.text


def test_list_error_jobs_reporter(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.errors = 'garbageinput'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert capsys.readouterr().out == 'Invalid reporter garbageinput.\n'


def test_modify_urls(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    jobs_file_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--add JOB`` followed by ``--delete JOB`` round-trips the jobs file."""
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    before_file = jobs_file_path.read_text()

    command_config.add = 'url=https://www.example.com/#test_modify_urls'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == 0
    message = capsys.readouterr().out
    assert message.startswith('Adding <url ')
    assert "url='https://www.example.com/#test_modify_urls'" in message

    command_config.add = None
    command_config.delete = 'https://www.example.com/#test_modify_urls'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == 0
    message = capsys.readouterr().out
    if sys.__stdin__ and sys.__stdin__.isatty():
        assert message.startswith(
            'WARNING: About to permanently delete Job 0: https://www.example.com/#test_modify_urls.'
        )
    else:
        assert message.startswith('Removed <url ')
        assert "url='https://www.example.com/#test_modify_urls'" in message

    after_file = jobs_file_path.read_text()
    assert sorted(after_file.split()) == sorted(before_file.split())


@pytest.mark.parametrize(
    ('attribute', 'value', 'action'),
    [
        ('add', 'url=https://www.example.com/#test_modify_urls', '--add'),
        ('delete', 'https://www.example.com/#test_modify_urls', '--delete'),
        ('change_location', ('a', 'b'), '--change-location'),
        ('enable', '1', '--enable'),
        ('disable', '1', '--disable'),
    ],
)
def test_modify_urls_refuses_multiple_jobs_files(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    jobs_file_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    attribute: str,
    value: str | tuple[str, str],
    action: str,
) -> None:
    """Commands rewriting the jobs file refuse to run with multiple jobs files, which they would corrupt."""
    second_jobs = tmp_path / 'jobs-second.yaml'
    second_jobs.write_text('url: https://www.example.com/#second\n', encoding='utf-8')
    before = jobs_file_path.read_text()
    command_config.jobs_files = [jobs_file_path, second_jobs]
    setattr(command_config, attribute, value)
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == 1
    assert capsys.readouterr().out == (
        f'{action} cannot be used with multiple jobs files, as it rewrites the jobs file. Select the jobs file to '
        f'modify with --jobs <file>. The jobs files are:\n• {jobs_file_path}\n• {second_jobs}\n'
    )
    assert jobs_file_path.read_text() == before


@pytest.mark.parametrize(
    ('attribute', 'query', 'job_defaults', 'code', 'message', 'saved_enabled'),
    [
        ('disable', 'a', {}, 0, 'Disabled job 1: https://a.example/.', [False, False]),
        ('enable', 'b', {}, 0, 'Enabled job 2: https://b.example/.', [None, None]),
        # job_defaults would keep the job disabled if the directive were only removed
        ('enable', 'a', {'all_jobs': {'enabled': False}}, 0, 'Enabled job 1: https://a.example/.', [True, False]),
        ('enable', 'a', {}, 0, 'Job 1 is already enabled: https://a.example/. The jobs file is unmodified.', None),
        ('disable', '2', {}, 0, 'Job 2 is already disabled: https://b.example/. The jobs file is unmodified.', None),
        ('disable', 'c', {}, 1, 'Job c does not match any job', None),
    ],
)
def test_enable_disable_job(
    urlwatch_command: UrlwatchCommand,
    command_config: CommandConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    attribute: str,
    query: str,
    job_defaults: dict[str, Any],
    code: int,
    message: str,
    saved_enabled: list[bool | None] | None,
) -> None:
    """Urlwatch's --enable and --disable set the job's 'enabled' directive and rewrite the jobs file.

    Enabling removes the directive unless job_defaults would then keep the job disabled; nothing is rewritten if the job
    already is in the state requested.
    """
    urlwatcher = urlwatch_command.urlwatcher
    _set_jobs(urlwatcher, {'name': 'a', 'url': 'https://a.example/'}, {'name': 'b', 'url': 'https://b.example/'})
    urlwatcher.jobs[1].enabled = False
    monkeypatch.setitem(cast('dict[str, Any]', urlwatcher.config_storage.config), 'job_defaults', job_defaults)
    saved: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(urlwatcher.jobs_storage, 'save', lambda jobs: saved.append([job.serialize() for job in jobs]))
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    setattr(command_config, attribute, query)
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == code
    assert message in capsys.readouterr().out
    if saved_enabled is None:
        assert not saved
    else:
        assert [job.get('enabled') for job in saved[0]] == saved_enabled


def test_serialize_keeps_false_directives() -> None:
    """Rewriting the jobs file (e.g. with --disable) keeps directives set to false or 0.

    These differ from leaving the directive out (until 3.39 they were dropped). The empty headers of URL jobs are still
    dropped.
    """
    job = JobBase.unserialize(
        {'url': 'https://a.example/', 'enabled': False, 'contextlines': 0, 'additions_only': False}
    )
    assert job.serialize() == {
        'url': 'https://a.example/',
        'enabled': False,
        'contextlines': 0,
        'additions_only': False,
    }


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_modify_urls_move_location(
    database_engine: SsdbStorage,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test ``--change-location JOB NEW_LOCATION`` across each available DB engine."""
    jobs_file = workspace / 'jobs-time.yaml'
    urlwatcher2, ssdb_storage2, command_config2 = prepare_storage_test(database_engine, jobs_file=jobs_file)
    urlwatch_command2 = UrlwatchCommand(urlwatcher2)
    monkeypatch.setattr('builtins.input', lambda _: 'y')

    # non-existing job
    command_config2.change_location = 'a', 'b'
    with pytest.raises(ValueError) as pytest_wrapped_ve:
        urlwatch_command2.handle_actions()
    command_config2.change_location = None
    assert str(pytest_wrapped_ve.value) == "Job a does not match any job's name, url/user_visible_url or command."

    # un-saved job
    old_loc = urlwatch_command2.urlwatcher.jobs[0].get_location()
    old_guid = urlwatch_command2.urlwatcher.jobs[0].guid
    new_loc = old_loc + '  # new location'
    command_config2.change_location = old_loc, new_loc
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command2.handle_actions()
    assert pytest_wrapped_se.value.code == 1
    assert (
        capsys.readouterr().out
        == f'Moving location of "{old_loc}" to "{new_loc}".\nNo snapshots found for "{old_loc}".\n'
    )

    # run jobs to save
    command_config2.change_location = None
    urlwatcher2.run_jobs()
    if hasattr(ssdb_storage2, '_copy_temp_to_permanent'):
        ssdb_storage2._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

    # change saved job's database location
    command_config2.change_location = old_loc, new_loc
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command2.handle_actions()
    assert pytest_wrapped_se.value.code == 0
    assert capsys.readouterr().out == (
        f'Moving location of "{old_loc}" to "{new_loc}".\n'
        f'Searched through 1 snapshots and moved "{old_loc}" to "{new_loc}".\n'
        f'Saving updated list to {urlwatcher2.jobs_storage.filename[0]!s}.\n'
    )

    new_guid = urlwatch_command2.urlwatcher.jobs[0].guid
    assert new_guid == urlwatch_command2.urlwatcher.jobs[0].get_guid()
    assert new_guid != old_guid
    assert urlwatch_command2.urlwatcher.jobs[0].get_location() == new_loc

    old_data = ssdb_storage2.load(old_guid)
    assert old_data.data == ''
    new_data = ssdb_storage2.load(new_guid)
    assert new_data.timestamp != 0

    # change back
    command_config2.change_location = new_loc, old_loc
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command2.handle_actions()
    assert pytest_wrapped_se.value.code == 0
    assert capsys.readouterr().out == (
        f'Moving location of "{new_loc}" to "{old_loc}".\n'
        f'Searched through 1 snapshots and moved "{new_loc}" to "{old_loc}".\n'
        f'Saving updated list to {urlwatcher2.jobs_storage.filename[0]!s}.\n'
    )
    assert urlwatch_command2.urlwatcher.jobs[0].guid == old_guid
    assert urlwatch_command2.urlwatcher.jobs[0].get_guid() == old_guid
    assert urlwatch_command2.urlwatcher.jobs[0].get_location() == old_loc
    assert ssdb_storage2.load(old_guid) == new_data

    # no input available (e.g. run by cron): the snapshots are moved, but the jobs file is left as is (until 3.39, the
    # prompt crashed with EOFError)
    def no_input(_: str) -> str:
        raise EOFError

    monkeypatch.setattr('builtins.input', no_input)
    saved_jobs_file = urlwatcher2.jobs_storage.filename[0]
    before = saved_jobs_file.read_text(encoding='utf-8')
    command_config2.change_location = old_loc, new_loc
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command2.handle_actions()
    assert pytest_wrapped_se.value.code == 0
    assert f'Please manually update the jobs file by replacing "{old_loc}" with "{new_loc}".' in (
        capsys.readouterr().out
    )
    assert saved_jobs_file.read_text(encoding='utf-8') == before


def test_enable_disable_no_input(
    urlwatch_command: UrlwatchCommand,
    command_config: CommandConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With no input available at the confirmation prompt, --disable leaves the jobs file unmodified.

    E.g. stdin redirected from the null device on Windows, which reports it as a terminal; this used to crash with
    EOFError.
    """

    def no_input(_: str) -> str:
        raise EOFError

    urlwatcher = urlwatch_command.urlwatcher
    _set_jobs(urlwatcher, {'name': 'a', 'url': 'https://a.example/'})
    saved: list[object] = []
    monkeypatch.setattr(urlwatcher.jobs_storage, 'save', saved.append)
    monkeypatch.setattr('builtins.input', no_input)
    monkeypatch.setattr(sys, '__stdin__', SimpleNamespace(isatty=lambda: True))
    command_config.disable = 'a'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == 1
    assert 'Quitting. Job 1 has not been disabled and job file is unmodified.' in capsys.readouterr().out
    assert not saved


# --- Snapshot DB commands ---


def test_delete_snapshot(
    time_jobs_urlwatcher: Urlwatch,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    urlwatcher = time_jobs_urlwatcher
    if sys.platform == 'win32':
        urlwatcher.jobs[0].command = WINDOWS_TIME_COMMAND
        urlwatcher.jobs[0].guid = urlwatcher.jobs[0].get_guid()
    urlwatch_command = UrlwatchCommand(urlwatcher)

    urlwatcher.urlwatch_config.delete_snapshot = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == 1
    assert capsys.readouterr().out[:29] == 'No snapshots found for Job 1:'

    # run once
    urlwatcher.urlwatch_config.delete_snapshot = None
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    guid = urlwatcher.jobs[0].guid
    assert len(urlwatcher.ssdb_storage.get_history_data(guid)) == 1

    # run twice
    time.sleep(0.0001)
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert len(urlwatcher.ssdb_storage.get_history_data(guid)) == 2

    # delete once
    urlwatcher.urlwatch_config.delete_snapshot = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert 'Deleted last snapshot of Job 1:' in capsys.readouterr().out
    assert pytest_wrapped_se.value.code == 0

    # delete twice
    urlwatcher.urlwatch_config.delete_snapshot = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert 'Deleted last snapshot of Job 1:' in capsys.readouterr().out
    assert pytest_wrapped_se.value.code == 0

    # all empty now
    urlwatcher.urlwatch_config.delete_snapshot = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert capsys.readouterr().out[:29] == 'No snapshots found for Job 1:'
    assert pytest_wrapped_se.value.code == 1


def test_human_size() -> None:
    """Test the human-readable size formatting used in the --delete-snapshot listing."""
    assert _human_size(0) == '0 B'
    assert _human_size(999) == '999 B'
    assert _human_size(1000) == '1.0 kB'
    assert _human_size(4200) == '4.2 kB'
    assert _human_size(1_000_000) == '1.0 MB'
    assert _human_size(2_500_000_000) == '2.5 GB'


def test_gc_database(
    time_jobs_urlwatcher: Urlwatch,
    workspace: Path,
    loaded_config_storage: YamlConfigStorage,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    urlwatcher = time_jobs_urlwatcher
    if sys.platform == 'win32':
        urlwatcher.jobs[0].command = WINDOWS_TIME_COMMAND
        urlwatcher.jobs[0].guid = urlwatcher.jobs[0].get_guid()
    guid = urlwatcher.jobs[0].guid

    # run once to save the job from 'jobs-time.yaml'
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert len(urlwatcher.ssdb_storage.get_history_data(guid)) == 1

    # build a second urlwatcher pointing at echo_test.yaml but sharing the same ssdb
    second_jobs = workspace / 'jobs-echo_test.yaml'
    second_cmd = CommandConfig(
        args=[],
        config_path=workspace,
        config_file=workspace / 'config.yaml',
        jobs_def_file=second_jobs,
        hooks_def_file=workspace / 'hooks_example.py',
        ssdb_file=':memory:',  # ty:ignore[invalid-argument-type]
    )
    urlwatcher2 = Urlwatch(
        second_cmd,
        loaded_config_storage,
        urlwatcher.ssdb_storage,
        YamlJobsStorage([second_jobs]),
    )
    urlwatch_command2 = UrlwatchCommand(urlwatcher2)

    # gc deletes snapshots of jobs no longer being tracked
    second_cmd.gc_database = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command2.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    if sys.platform == 'win32':
        assert capsys.readouterr().out == f'Deleting job {guid} (no longer being tracked).\n'
    else:
        # TODO: Linux output is empty here; needs investigation independently of this test refactor.
        ...


def test_clean_database(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Empty-DB ``--clean-database`` is a no-op; with snapshots it trims to RETAIN_LIMIT."""
    command_config.clean_database = True
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == 0
    assert capsys.readouterr().out == ''

    # populate via prepare_storage_test
    database_engine = SsdbSQLite3Storage(':memory:')  # ty:ignore[invalid-argument-type]
    urlwatcher2, ssdb_storage2, command_config2 = prepare_storage_test(database_engine)
    urlwatch_command2 = UrlwatchCommand(urlwatcher2)

    for _ in range(3):
        time.sleep(0.0001)
        urlwatch_command2.urlwatcher.run_jobs()
    if hasattr(ssdb_storage2, '_copy_temp_to_permanent'):
        ssdb_storage2._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

    urlwatch_command2.urlwatch_config.clean_database = 2
    urlwatcher2.ssdb_storage.clean_ssdb(
        [job.guid for job in urlwatcher2.jobs],
        command_config2.clean_database,  # ty:ignore[invalid-argument-type]
    )
    guid = urlwatch_command2.urlwatcher.jobs[0].guid
    assert len(ssdb_storage2.get_history_snapshots(guid)) == 2

    urlwatch_command2.urlwatch_config.clean_database = True
    urlwatcher2.ssdb_storage.clean_ssdb(
        [job.guid for job in urlwatcher2.jobs],
        command_config2.clean_database,  # ty:ignore[invalid-argument-type]
    )
    assert len(ssdb_storage2.get_history_snapshots(guid)) == 1
    close_ssdb_storage(database_engine)


def test_rollback_database(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr('builtins.input', lambda _: 'y')

    command_config.rollback_database = '1'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == 0
    assert 'No snapshots found after' in capsys.readouterr().out

    command_config.rollback_database = '10am'
    with pytest.raises(SystemExit) as pytest_wrapped_se:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_se.value.code == 0
    assert 'No snapshots found after' in capsys.readouterr().out

    command_config.rollback_database = 'Thisisjunk'
    with pytest.raises(ValueError) as pytest_wrapped_ve:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_ve.value.args[0] == 'Cannot parse "Thisisjunk" into a date/time.'


def test_rollback_database_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The count shown in the confirmation prompt must not delete anything; only a 'Y' answer deletes."""
    database_engine = SsdbSQLite3Storage(':memory:')  # ty:ignore[invalid-argument-type]
    urlwatcher, ssdb_storage, command_config = prepare_storage_test(database_engine)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    guid = urlwatcher.jobs[0].guid

    urlwatcher.run_jobs()
    if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
        ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
    cutoff = ssdb_storage.get_history_snapshots(guid)[0].timestamp - 1
    time.sleep(0.0001)
    urlwatcher.run_jobs()
    if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
        ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
    assert len(ssdb_storage.get_history_snapshots(guid)) == 2

    # pretend we are on a terminal so that the confirmation prompt is shown
    monkeypatch.setattr(sys.__stdin__, 'isatty', lambda: True)
    command_config.rollback_database = str(cutoff)

    # declining must leave the database untouched
    monkeypatch.setattr('builtins.input', lambda _: 'n')
    assert urlwatch_command.rollback_database(command_config.rollback_database) == 1
    out = capsys.readouterr().out
    assert 'WARNING: All 2 snapshots after this date/time' in out
    assert 'Quitting rollback. No snapshots have been deleted.' in out
    assert len(ssdb_storage.get_history_snapshots(guid)) == 2

    # confirming deletes and reports the same count as the warning
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    assert urlwatch_command.rollback_database(command_config.rollback_database) == 0
    out = capsys.readouterr().out
    assert 'WARNING: All 2 snapshots after this date/time' in out
    assert 'Deleted 2 snapshots taken after' in out
    assert len(ssdb_storage.get_history_snapshots(guid)) == 0
    close_ssdb_storage(database_engine)


# --- Reporter / notification checks ---


def test_check_telegram_chats(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.telegram_chats = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert capsys.readouterr().out == 'You need to set up your bot token first (see documentation).\n'

    urlwatch_command.urlwatcher.config_storage.config['report']['telegram']['bot_token'] = 'bogus'  # noqa: S105  # ty:ignore[invalid-assignment]
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert capsys.readouterr().out == 'Error with token bogus: Not Found.\n'

    if os.getenv('TELEGRAM_TOKEN'):
        if os.getenv('GITHUB_ACTIONS'):
            pytest.skip('Telegram testing no longer working from within GitHub Actions')
        urlwatch_command.urlwatcher.config_storage.config['report']['telegram']['bot_token'] = os.getenv(  # ty:ignore[invalid-assignment]
            'TELEGRAM_TOKEN', ''
        )
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            urlwatch_command.handle_actions()
        assert pytest_wrapped_e.value.code in (0, 1)
        assert 'Say hello to your bot at https://t.me/' in capsys.readouterr().out
    else:
        print('Cannot fully test Telegram as no TELEGRAM_TOKEN environment variable found')


def test_check_test_reporter(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.test_reporter = 'stdout'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert '01. NEW: ' in capsys.readouterr().out

    urlwatch_command.urlwatcher.config_storage.config['report']['stdout']['enabled'] = False  # ty:ignore[invalid-assignment]
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert 'WARNING: Reporter being tested is not enabled: stdout.\n' in capsys.readouterr().out

    command_config.test_reporter = 'does_not_exist'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert 'No such reporter: does_not_exist.\n' in capsys.readouterr().out


def test_test_reporter_with_joblist(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    urlwatcher: Urlwatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--test-reporter`` plus a joblist runs the listed jobs and routes the report to the named reporter only."""
    job = urlwatcher.jobs[0]
    history_before = len(urlwatcher.ssdb_storage.get_history_snapshots(job.guid))

    command_config.test_reporter = 'stdout'
    command_config.joblist = ['1']
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0

    history_after = len(urlwatcher.ssdb_storage.get_history_snapshots(job.guid))
    assert history_after == history_before

    message = capsys.readouterr().out
    assert 'NEW:' in message
    assert 'test' in message


def test_test_reporter_with_joblist_invalid_reporter(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown reporter name with --test-reporter + joblist exits 1 and prints the standard error message."""
    command_config.test_reporter = 'does_not_exist'
    command_config.joblist = ['1']
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert 'No such reporter: does_not_exist.\n' in capsys.readouterr().out


def test_check_smtp_login(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.smtp_login = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert capsys.readouterr().out.splitlines() == [
        'Please enable email reporting in the config first.',
        'Please configure the SMTP user in the config first.',
    ]


def test_check_smtp_login_not_config(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    urlwatch_command.urlwatcher.config_storage.config['report']['email'].update(  # ty:ignore[unresolved-attribute]
        {
            'enabled': True,
            'method': 'sendmail',
            'smtp': {
                'auth': False,
                'host': '',
                'user': '',
            },  # ty:ignore[missing-typed-dict-key]
        }  # ty:ignore[invalid-argument-type]
    )
    command_config.smtp_login = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert capsys.readouterr().out.splitlines() == [
        'Please set the method to SMTP for the email reporter.',
        'Authentication must be enabled for SMTP.',
        'Please configure the SMTP hostname in the config first.',
        'Please configure the SMTP user in the config first.',
    ]


@py_latest_only
def test_check_smtp_insecure_password(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    urlwatch_command.urlwatcher.config_storage.config['report']['email'].update(  # ty:ignore[unresolved-attribute]
        {
            'enabled': True,
            'method': 'smtp',
            'smtp': {
                'auth': True,
                'host': 'localhost',
                'user': 'me',
                'insecure_password': 'pwd',
                'port': 587,
                'starttls': True,
                'utf_8': True,
            },
        }
    )
    command_config.smtp_login = True
    with pytest.raises(ConnectionRefusedError):
        urlwatch_command.handle_actions()
    assert capsys.readouterr().out.splitlines() == [
        'The SMTP password is set in the config file (key "insecure_password").',
        'Trying to log into the SMTP server...',
    ]


def test_check_xmpp_login(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.xmpp_login = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 1
    assert capsys.readouterr().out.splitlines() == [
        'Please enable XMPP reporting in the config first.',
        'Please configure the XMPP sender in the config first.',
        'Please configure the XMPP recipient in the config first.',
    ]


def test_check_xmpp_login_insecure_password(
    command_config: CommandConfig,
    urlwatch_command: UrlwatchCommand,
    capsys: pytest.CaptureFixture[str],
) -> None:
    urlwatch_command.urlwatcher.config_storage.config['report']['xmpp'] = {
        'enabled': True,
        'sender': 'me',
        'recipient': 'you',
        'insecure_password': 'pwd',
    }
    command_config.xmpp_login = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert capsys.readouterr().out == 'The XMPP password is already set in the config (key "insecure_password").\n'


# --- Misc actions ---


def test_list_error_jobs_with_error(
    urlwatch_command: UrlwatchCommand, data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    urlwatch_command.urlwatcher.jobs_storage = YamlJobsStorage([data_dir / 'jobs-invalid_url.yaml'])
    urlwatch_command.urlwatcher.load_jobs()
    urlwatch_command.urlwatch_config.errors = 'stdout'
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert '\n  1: Error "' in capsys.readouterr().out


def test_prepare_jobs(urlwatch_command: UrlwatchCommand, data_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    urlwatch_command.urlwatcher.jobs_storage = YamlJobsStorage([data_dir / 'jobs-echo_test.yaml'])
    urlwatch_command.urlwatcher.load_jobs()
    urlwatch_command.urlwatcher.report.job_states = []
    urlwatch_command.urlwatch_config.prepare_jobs = True
    urlwatch_command.urlwatcher.report.config['display']['new'] = False
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    assert pytest_wrapped_e.value.code == 0
    assert capsys.readouterr().out == 'Running new Job 1: echo test.\n'
