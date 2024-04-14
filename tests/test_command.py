"""Test commands."""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path, PurePath
from typing import Callable, cast

import pytest
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from tests.test_storage import DATABASE_ENGINES, prepare_storage_test

from webchanges import __copyright__, __min_python_version__, __project_name__, __version__
from webchanges.cli import (
    first_run,
    handle_unitialized_actions,
    locate_jobs_files,
    locate_storage_file,
    migrate_from_legacy,
    python_version_warning,
    setup_logger,
)
from webchanges.command import UrlwatchCommand
from webchanges.config import CommandConfig
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, CacheStorage, YamlConfigStorage, YamlJobsStorage
from webchanges.util import import_module_from_source

# Paths
here = Path(__file__).parent
config_path = here.joinpath('data')
tmp_path = Path(tempfile.mkdtemp())

# Copy config file to temporary directory
base_config_file = config_path.joinpath('config.yaml')
config_file = tmp_path.joinpath('config.yaml')
shutil.copyfile(base_config_file, config_file)

# Copy jobs files to temporary directory
for filename in {'jobs-echo_test.yaml', 'jobs-time.yaml'}:
    shutil.copyfile(config_path.joinpath(filename), tmp_path.joinpath(filename))

jobs_file = tmp_path.joinpath('jobs-echo_test.yaml')
cache_file = ':memory:'

# Copy hooks file to temporary directory
base_hooks_file = config_path.joinpath('hooks_example.py')
hooks_file = tmp_path.joinpath('hooks_example.py')
shutil.copyfile(base_hooks_file, hooks_file)

# Set up dummy editor
editor = os.getenv('EDITOR')
if os.name == 'nt':
    os.environ['EDITOR'] = 'rundll32'
else:
    os.environ['EDITOR'] = 'true'
visual = os.getenv('VISUAL')
if visual:
    del os.environ['VISUAL']

py_latest_only = cast(
    Callable[[Callable], Callable],
    pytest.mark.skipif(sys.version_info < (3, 12), reason='Time ' 'consuming; testing latest version only'),
)


def new_command_config(jobs_file: Path = jobs_file, hooks_file: Path = hooks_file) -> CommandConfig:
    return CommandConfig(
        args=[],
        project_name=__project_name__,
        config_path=config_path,
        config_file=config_file,
        jobs_def_file=jobs_file,
        hooks_file=hooks_file,
        cache=cache_file,  # type: ignore[arg-type]
    )


# @pytest.fixture()  # type: ignore[misc]
# def urlwatch_command() -> UrlwatchCommand:
#     command_config = new_command_config(jobs_file=jobs_file)
#     config_storage = YamlConfigStorage(config_file)
#     config_storage.load()
#     cache_storage = CacheSQLite3Storage(cache_file)  # type: ignore[arg-type]
#     jobs_storage = YamlJobsStorage([jobs_file])
#     urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
#     urlwatch_command = UrlwatchCommand(urlwatcher)
#     return urlwatch_command


# Set up classes
command_config = new_command_config(jobs_file=jobs_file)
config_storage = YamlConfigStorage(config_file)
config_storage.load()
cache_storage = CacheSQLite3Storage(cache_file)  # type: ignore[arg-type]
jobs_storage = YamlJobsStorage([jobs_file])
urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
urlwatch_command = UrlwatchCommand(urlwatcher)


@pytest.fixture(scope='module', autouse=True)  # type: ignore[misc]
def cleanup(request: pytest.FixtureRequest) -> None:
    """Cleanup once we are finished."""

    def finalizer() -> None:
        """Cleanup once we are finished."""
        if editor:
            os.environ['EDITOR'] = editor
        if visual:
            os.environ['VISUAL'] = visual
        try:
            urlwatcher.close()
        except AttributeError:
            pass

    request.addfinalizer(finalizer)


def test_python_version_warning(capsys: CaptureFixture[str]) -> None:
    """Test issuance of deprecation warning message when running on minimum version supported."""
    python_version_warning()
    message = capsys.readouterr().out
    if sys.version_info[0:2] == __min_python_version__:
        current_minor_version = '.'.join(str(n) for n in sys.version_info[0:2])
        assert message.startswith(
            f'WARNING: Support for Python {current_minor_version} will be ending three years from the date Python '
        )
    else:
        assert not message


def test_migration() -> None:
    """Test check for existence of legacy urlwatch 2.2 files in urlwatch dir."""
    migrate_from_legacy(
        'urlwatch',
        config_file,
        jobs_file,
        hooks_file,
        cache_file,  # type: ignore[arg-type]
    )


def test_first_run(capsys: CaptureFixture[str], tmp_path: Path) -> None:
    """Test creation of default config and jobs files at first run."""
    config_file2 = tmp_path.joinpath('config.yaml')
    jobs_file2 = tmp_path.joinpath('jobs.yaml')
    command_config2 = CommandConfig(
        [],
        __project_name__,
        tmp_path,
        config_file2,
        jobs_file2,
        hooks_file,
        cache_file,  # type: ignore[arg-type]
    )
    command_config2.edit = False
    first_run(command_config2)
    message = capsys.readouterr().out
    assert 'Created default config file at ' in message
    assert 'Created default jobs file at ' in message


def test_edit() -> None:
    setattr(command_config, 'edit', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.run()
    setattr(command_config, 'edit', False)
    assert pytest_wrapped_e.value.code == 0


def test_edit_using_visual() -> None:
    os.environ['VISUAL'] = os.environ['EDITOR']
    del os.environ['EDITOR']
    setattr(command_config, 'edit', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.run()
    setattr(command_config, 'edit', False)
    os.environ['EDITOR'] = os.environ['VISUAL']
    del os.environ['VISUAL']
    assert pytest_wrapped_e.value.code == 0


def test_edit_fail(capsys: CaptureFixture[str]) -> None:
    editor = os.getenv('EDITOR')
    os.environ['EDITOR'] = 'does_not_exist_and_should_trigger_an_error'
    setattr(command_config, 'edit', True)
    with pytest.raises(OSError) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'edit', False)
    if editor is not None:
        os.environ['EDITOR'] = editor
    else:
        os.unsetenv('EDITOR')
        del os.environ['EDITOR']  # Python 3.9: jobs_edit = jobs_file.with_stem(jobs_file.stem + '_edit')
    jobs_edit = jobs_file.parent.joinpath(jobs_file.stem + '_edit' + ''.join(jobs_file.suffixes))
    jobs_edit.unlink()
    assert pytest_wrapped_e.value.args[0] == (
        'pytest: reading from stdin while output is captured!  Consider using `-s`.'
    )
    message = capsys.readouterr().out
    assert 'Errors in updating file:' in message


def test_edit_config() -> None:
    setattr(command_config, 'edit_config', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.run()
    setattr(command_config, 'edit_config', False)
    assert pytest_wrapped_e.value.code == 0


def test_edit_config_fail(capsys: CaptureFixture[str]) -> None:
    editor = os.getenv('EDITOR')
    os.environ['EDITOR'] = 'does_not_exist_and_should_trigger_an_error'
    setattr(command_config, 'edit_config', True)
    with pytest.raises(OSError) as pytest_wrapped_e:
        urlwatch_command.run()
    setattr(command_config, 'edit_config', False)
    if editor is not None:
        os.environ['EDITOR'] = editor
    else:
        os.unsetenv('EDITOR')
        del os.environ['EDITOR']  # Python 3.9: config_edit = config_file.with_stem(config_file.stem + '_edit')
    config_edit = config_file.parent.joinpath(config_file.stem + '_edit' + ''.join(config_file.suffixes))
    config_edit.unlink()
    assert pytest_wrapped_e.value.args[0] == (
        'pytest: reading from stdin while output is captured!  Consider using `-s`.'
    )
    message = capsys.readouterr().out
    assert 'Errors in updating file:' in message


def test_edit_hooks(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'edit_hooks', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'edit_hooks', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message == f'Saved edits in {urlwatch_command.urlwatch_config.hooks_file}\n'


def test_edit_hooks_fail(capsys: CaptureFixture[str]) -> None:
    editor = os.getenv('EDITOR')
    os.environ['EDITOR'] = 'does_not_exist_and_should_trigger_an_error'
    setattr(command_config, 'edit_hooks', True)
    with pytest.raises(OSError) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'edit_hooks', False)
    if editor is not None:
        os.environ['EDITOR'] = editor
    else:
        os.unsetenv('EDITOR')
        del os.environ['EDITOR']
    hooks_edit = hooks_file.with_stem(hooks_file.stem + '_edit')
    hooks_edit.unlink()
    assert pytest_wrapped_e.value.args[0] == (
        'pytest: reading from stdin while output is captured!  Consider using `-s`.'
    )
    message = capsys.readouterr().out
    assert 'Parsing failed:' in message


def test_show_features_and_verbose(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'features', True)
    setattr(command_config, 'verbose', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'features', False)
    setattr(command_config, 'verbose', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert '* browser - Retrieve a URL using a real web browser (use_browser: true).' in message


def test_show_detailed_versions(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'detailed_versions', 'stdout')
    urlwatch_command.urlwatcher.config_storage.config['report']['stdout']['enabled'] = False
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'detailed_versions', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert f'• {__project_name__}: {__version__}\n' in message


def test_list_jobs_verbose(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'list_jobs', True)
    urlwatch_config_verbose = urlwatcher.urlwatch_config.verbose
    urlwatcher.urlwatch_config.verbose = True
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'list_jobs', False)
    urlwatcher.urlwatch_config.verbose = urlwatch_config_verbose
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.startswith('  1: <command ')
    assert 'index_number=1' in message
    assert "name='Sample webchanges job; used by test_command.py'" in message
    assert "command='echo test'" in message
    assert message.endswith(f'\nJobs file: {command_config.jobs_files[0]}\n')


def test_list_jobs_not_verbose(capsys: CaptureFixture[str]) -> None:
    command_config.jobs_files = [tmp_path.joinpath('jobs-echo_test.yaml'), tmp_path.joinpath('jobs-echo_test.yaml')]
    setattr(command_config, 'list_jobs', True)
    urlwatch_config_verbose = urlwatcher.urlwatch_config.verbose
    urlwatcher.urlwatch_config.verbose = False
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'list_jobs', False)
    urlwatcher.urlwatch_config.verbose = urlwatch_config_verbose
    command_config.jobs_files = [tmp_path.joinpath('jobs-echo_test.yaml')]
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.splitlines() == [
        '  1: Sample webchanges job; used by test_command.py (echo test)',
        'Jobs files concatenated:',
        f'   • {command_config.jobs_files[0]}',
        f'   • {command_config.jobs_files[0]}',
    ]


def test_list_jobs_no_filename(capsys: CaptureFixture[str]) -> None:
    command_config.jobs_files = []
    setattr(command_config, 'list_jobs', True)
    urlwatch_config_verbose = urlwatcher.urlwatch_config.verbose
    urlwatcher.urlwatch_config.verbose = False
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'list_jobs', False)
    urlwatcher.urlwatch_config.verbose = urlwatch_config_verbose
    command_config.jobs_files = [jobs_file]
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.splitlines() == [
        '  1: Sample webchanges job; used by test_command.py (echo test)',
        '',
    ]


def test__find_job() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job('https://example.com/')
    message = str(pytest_wrapped_e.value)
    assert message == "Job https://example.com/ does not match any job's url/user_visible_url or command."


def test__find_job_zero() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job(0)
    message = str(pytest_wrapped_e.value)
    assert message == 'Job index 0 out of range.'


def test__find_job_negative() -> None:
    assert urlwatch_command._find_job(-1) is urlwatcher.jobs[0]


def test__find_job_index_error() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job(100)
    message = str(pytest_wrapped_e.value)
    assert message == 'Job index 100 out of range (found 1 jobs).'


def test__find_job_index_no_match() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command._find_job('nomatch')
    message = str(pytest_wrapped_e.value)
    assert message == "Job nomatch does not match any job's url/user_visible_url or command."


def test__get_job() -> None:
    assert urlwatch_command._find_job_with_defaults(1).get_location() == 'echo test'


def test_test_job(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'test_job', 1)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_job', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.startswith(
        'Sample webchanges job; used by test_command.py\n'
        '----------------------------------------------\n'
        '\n'
        'test\n'
        '\n'
        '\n'
        '--\n'
        'Job tested in '
    )


def test_test_job_all(capsys: CaptureFixture[str]) -> None:
    urlwatch_command.urlwatch_config.hooks_file = hooks_file
    import_module_from_source('hooks', hooks_file)
    setattr(command_config, 'test_job', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_job', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.splitlines() == [
        f'No syntax errors in config file {urlwatch_command.urlwatch_config.config_file},',
        f'jobs file ' f'{urlwatch_command.urlwatch_config.jobs_files[0]},',
        f'and hooks file {urlwatch_command.urlwatch_config.hooks_file}.',
    ]

    # with multiple files
    command_config.jobs_files = [tmp_path.joinpath('jobs-echo_test.yaml'), tmp_path.joinpath('jobs-echo_test.yaml')]
    setattr(command_config, 'test_job', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_job', None)
    command_config.jobs_files = [tmp_path.joinpath('jobs-echo_test.yaml')]
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.splitlines() == [
        f'No syntax errors in config file {urlwatcher.urlwatch_config.config_file},',
        'jobs files',
        f'   • {urlwatch_command.urlwatch_config.jobs_files[0]}',
        f'   • {urlwatch_command.urlwatch_config.jobs_files[0]},',
        f'and hooks file {urlwatch_command.urlwatch_config.hooks_file}.',
    ]


def test_test_job_with_test_reporter(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'test_job', 1)
    setattr(command_config, 'test_reporter', 'stdout')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_job', None)
    setattr(command_config, 'test_reporter', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.startswith(
        'Sample webchanges job; used by test_command.py\n'
        '----------------------------------------------\n'
        '\n'
        'test\n'
        '\n'
        '\n'
        '--\n'
        'Job tested in '
    )


def test_dump_history(capsys: CaptureFixture[str]) -> None:
    jobs_file = config_path.joinpath('jobs-time.yaml')
    jobs_storage = YamlJobsStorage([jobs_file])
    command_config = new_command_config(jobs_file=jobs_file)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    urlwatcher.jobs[0].command = 'echo 1'
    guid = urlwatcher.jobs[0].get_guid()

    try:
        # never run
        setattr(command_config, 'dump_history', 1)
        urlwatch_command = UrlwatchCommand(urlwatcher)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            urlwatch_command.handle_actions()
        setattr(command_config, 'dump_history', None)
        assert pytest_wrapped_e.value.code == 0
        message = capsys.readouterr().out
        assert (
            'History for job Job 1: echo 1:\n(ID: 452b9ef6128065e9e0329ba8d32daf9715595fa4)\nFound 0 snapshots.\n'
        ) in message

        # run once
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        urlwatcher.urlwatch_config.joblist = []

        # test diff (unified) with diff_filter, tz, and contextlines
        setattr(command_config, 'dump_history', 1)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            urlwatch_command.handle_actions()
        setattr(command_config, 'dump_history', None)
        assert pytest_wrapped_e.value.code == 0
        message = capsys.readouterr().out
        assert (
            'History for job Job 1: echo 1:\n'
            '(ID: 452b9ef6128065e9e0329ba8d32daf9715595fa4)\n'
            '==================================================\n'
        ) in message
        assert (
            '--------------------------------------------------\n'
            '1\n'
            '\n'
            '================================================== \n'
            '\n'
            'Found 1 snapshot.\n'
        ) in message

    finally:
        urlwatcher.cache_storage.delete(guid)


def test_test_differ_and_joblist(capsys: CaptureFixture[str]) -> None:
    jobs_file = config_path.joinpath('jobs-time.yaml')
    jobs_storage = YamlJobsStorage([jobs_file])
    command_config = new_command_config(jobs_file=jobs_file)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    if os.name == 'nt':
        urlwatcher.jobs[0].command = 'echo %time% %random%'
    guid = urlwatcher.jobs[0].get_guid()

    try:
        # never run
        setattr(command_config, 'test_differ', 1)
        urlwatch_command = UrlwatchCommand(urlwatcher)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            urlwatch_command.handle_actions()
        setattr(command_config, 'test_differ', None)
        assert pytest_wrapped_e.value.code == 1
        message = capsys.readouterr().out
        assert message == 'This job has never been run before.\n'

        # run once
        # also testing joblist
        urlwatcher.urlwatch_config.joblist = ['1']
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        urlwatcher.urlwatch_config.joblist = []

        setattr(command_config, 'test_differ', [1, 1])
        urlwatcher.jobs[0].compared_versions = 2
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            urlwatch_command.handle_actions()
        setattr(command_config, 'test_differ', None)
        urlwatcher.jobs[0].compared_versions = None
        assert pytest_wrapped_e.value.code == 1
        message = capsys.readouterr().out
        assert message == 'Not enough historic data available (need at least 2 different snapshots).\n'

        # test invalid joblist
        urlwatcher.urlwatch_config.joblist = ['-999']
        with pytest.raises(ValueError) as pytest_wrapped_e2:
            urlwatcher.run_jobs()
        assert pytest_wrapped_e2.value.args[0] == 'Job index -999 out of range (found 1 jobs).'
        urlwatcher.urlwatch_config.joblist = []

        # run twice
        time.sleep(0.0001)
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2

        # test diff (unified) with diff_filter, tz, and contextlines
        setattr(command_config, 'test_differ', 1)
        urlwatcher.jobs[0].diff_filter = [{'strip': ''}]
        urlwatcher.config_storage.config['report']['tz'] = 'Etc/GMT+12'
        urlwatcher.jobs[0].contextlines = 2
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            urlwatch_command.handle_actions()
        setattr(command_config, 'test_differ', None)
        assert pytest_wrapped_e.value.code == 0
        message = capsys.readouterr().out
        assert '01. FILTERED DIFF (SNAPSHOTS  0 AND -1): ' in message
        assert message.splitlines()[10][-6:] == ' -1200'

        # rerun to reuse cached _generated_diff but change timezone
        urlwatcher.config_storage.config['report']['tz'] = 'Etc/UTC'
        setattr(command_config, 'test_differ', 1)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            urlwatch_command.handle_actions()
        setattr(command_config, 'test_differ', None)
        assert pytest_wrapped_e.value.code == 0
        message = capsys.readouterr().out
        assert '01. FILTERED DIFF (SNAPSHOTS  0 AND -1): ' in message
        assert message.splitlines()[10][-12:] == ' +0000 (UTC)'

        # Try another timezone
        urlwatcher.config_storage.config['report']['tz'] = 'Etc/GMT+1'
        setattr(command_config, 'test_differ', 1)
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            urlwatch_command.handle_actions()
        setattr(command_config, 'test_differ', None)
        assert pytest_wrapped_e.value.code == 0
        message = capsys.readouterr().out
        assert '01. FILTERED DIFF (SNAPSHOTS  0 AND -1): ' in message
        assert message.splitlines()[10][-6:] == ' -0100'

    finally:
        urlwatcher.cache_storage.delete(guid)


def test_list_error_jobs(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'errors', 'stdout')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'errors', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    expect = '\n'.join(
        [
            'Jobs with errors or returning no data (after unmodified filters, if any)',
            f'   in jobs file '
            f"{str(urlwatch_command.urlwatch_config.jobs_files[0]) + ':' if urlwatch_command.urlwatch_config.jobs_files else ''}",  # noqa: E501
            '--',
            'Checked 1 enabled jobs for errors in',
        ]
    )
    assert message[: len(expect)] == expect


def test_list_error_jobs_reporter(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'errors', 'garbageinput')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'errors', None)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message == 'Invalid reporter garbageinput\n'


def test_modify_urls(capsys: CaptureFixture[str]) -> None:
    """Test --add JOB and --delete JOB."""
    # save current contents of job file
    before_file = jobs_file.read_text()

    # add new job
    setattr(command_config, 'add', 'url=https://www.example.com/#test_modify_urls')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'add', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.startswith('Adding <url ')
    assert 'index_number=0' in message
    assert "url='https://www.example.com/#test_modify_urls'" in message

    # delete the job just added
    setattr(command_config, 'delete', 'https://www.example.com/#test_modify_urls')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.startswith('Removed <url ')
    assert 'index_number=0' in message
    assert "url='https://www.example.com/#test_modify_urls'" in message

    # check that the job file is identical to before the add/delete operations
    after_file = jobs_file.read_text()
    assert sorted(after_file.split()) == sorted(before_file.split())


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_modify_urls_move_location(
    database_engine: CacheStorage, capsys: CaptureFixture[str], monkeypatch: MonkeyPatch
) -> None:
    """Test --change-location JOB NEW_LOCATION."""
    jobs_file = tmp_path.joinpath('jobs-time.yaml')
    urlwatcher2, cache_storage2, command_config2 = prepare_storage_test(database_engine, jobs_file=jobs_file)
    urlwatch_command2 = UrlwatchCommand(urlwatcher2)

    # monkeypatches the "input" function, so that it simulates the user entering "y" in the terminal:
    monkeypatch.setattr('builtins.input', lambda _: 'y')

    # try changing location of non-existing job
    setattr(command_config2, 'change_location', ('a', 'b'))
    with pytest.raises(ValueError) as pytest_wrapped_e:
        urlwatch_command2.handle_actions()
    setattr(command_config2, 'change_location', None)
    message = str(pytest_wrapped_e.value)
    assert message == "Job a does not match any job's url/user_visible_url or command."

    # try changing location of un-saved job
    old_loc = urlwatch_command2.urlwatcher.jobs[0].get_location()
    old_guid = urlwatch_command2.urlwatcher.jobs[0].get_guid()
    new_loc = old_loc + '  # new location'
    setattr(command_config2, 'change_location', (old_loc, new_loc))
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command2.handle_actions()
    setattr(command_config2, 'change_location', None)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message == f'Moving location of "{old_loc}" to "{new_loc}"\nNo snapshots found for "{old_loc}"\n'

    # run jobs to save
    urlwatcher2.run_jobs()
    if hasattr(cache_storage2, '_copy_temp_to_permanent'):
        cache_storage2._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

    # try changing job database location
    setattr(command_config2, 'change_location', (old_loc, new_loc))
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command2.handle_actions()
    setattr(command_config2, 'change_location', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message == (
        f'Moving location of "{old_loc}" to "{new_loc}"\n'
        f'Searched through 1 snapshots and moved "{old_loc}" to "{new_loc}"\n'
        f'Saving updated list to {str(urlwatcher2.jobs_storage.filename[0])}\n'
    )

    # did it change?
    new_guid = urlwatch_command2.urlwatcher.jobs[0].get_guid()
    assert new_guid != old_guid
    assert urlwatch_command2.urlwatcher.jobs[0].get_location() == new_loc

    # is it in the database?
    old_data = cache_storage2.load(old_guid)
    assert old_data.data == ''
    new_data = cache_storage2.load(new_guid)
    assert new_data.timestamp != 0

    # change back
    setattr(command_config2, 'change_location', (new_loc, old_loc))
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command2.handle_actions()
    setattr(command_config2, 'change_location', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message == (
        f'Moving location of "{new_loc}" to "{old_loc}"\n'
        f'Searched through 1 snapshots and moved "{new_loc}" to "{old_loc}"\n'
        f'Saving updated list to {str(urlwatcher2.jobs_storage.filename[0])}\n'
    )

    # did it change back?
    assert urlwatch_command2.urlwatcher.jobs[0].get_location() == old_loc
    assert cache_storage2.load(old_guid) == new_data


def test_delete_snapshot(capsys: CaptureFixture[str]) -> None:
    jobs_file = config_path.joinpath('jobs-time.yaml')
    jobs_storage = YamlJobsStorage([jobs_file])
    command_config = new_command_config(jobs_file=jobs_file)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    if os.name == 'nt':
        urlwatcher.jobs[0].command = 'echo %time% %random%'

    setattr(command_config, 'delete_snapshot', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete_snapshot', False)
    message = capsys.readouterr().out
    assert message[:43] == 'No snapshots found to be deleted for Job 1:'
    assert pytest_wrapped_e.value.code == 1

    # run once
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    guid = urlwatcher.jobs[0].get_guid()
    history = cache_storage.get_history_data(guid)
    assert len(history) == 1

    # run twice
    time.sleep(0.0001)
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    history = cache_storage.get_history_data(guid)
    assert len(history) == 2

    # delete once
    setattr(command_config, 'delete_snapshot', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete_snapshot', False)
    message = capsys.readouterr().out
    assert message[:31] == 'Deleted last snapshot of Job 1:'
    assert pytest_wrapped_e.value.code == 0

    # delete twice
    setattr(command_config, 'delete_snapshot', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete_snapshot', False)
    message = capsys.readouterr().out
    assert message[:31] == 'Deleted last snapshot of Job 1:'
    assert pytest_wrapped_e.value.code == 0

    # test all empty
    setattr(command_config, 'delete_snapshot', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete_snapshot', False)
    message = capsys.readouterr().out
    assert message[:43] == 'No snapshots found to be deleted for Job 1:'
    assert pytest_wrapped_e.value.code == 1


def test_gc_database(capsys: CaptureFixture[str]) -> None:
    jobs_file = config_path.joinpath('jobs-time.yaml')
    jobs_storage = YamlJobsStorage([jobs_file])
    command_config = new_command_config(jobs_file=jobs_file)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    if os.name == 'nt':
        urlwatcher.jobs[0].command = 'echo %time% %random%'
    guid = urlwatcher.jobs[0].get_guid()

    # run once to save the job from 'jobs-time.yaml'
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    history = cache_storage.get_history_data(guid)
    assert len(history) == 1

    # set job file to a different one
    jobs_storage = YamlJobsStorage([jobs_file])
    command_config = new_command_config(jobs_file=jobs_file)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    urlwatch_command = UrlwatchCommand(urlwatcher)

    # run gc_database and check that it deletes the snapshot of the job no longer being tracked
    setattr(command_config, 'gc_database', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'gc_database', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    if os.name == 'nt':
        assert message == f'Deleting job {guid} (no longer being tracked)\n'
    else:
        # TODO: for some reason, Linux message is ''.  Need to figure out why.
        ...


def test_clean_database(capsys: CaptureFixture[str]) -> None:
    """Test --clean-database [RETAIN_LIMIT]."""
    setattr(command_config, 'clean_database', True)
    urlwatcher.cache_storage = CacheSQLite3Storage(cache_file)  # type: ignore[arg-type]
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'clean_database', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message == ''

    # set up storage for testing
    database_engine = CacheSQLite3Storage(':memory:')  # type: ignore[arg-type]
    urlwatcher2, cache_storage2, command_config2 = prepare_storage_test(database_engine)
    urlwatch_command2 = UrlwatchCommand(urlwatcher2)

    # run jobs to save
    for i in range(3):
        time.sleep(0.0001)
        urlwatcher2.run_jobs()
    if hasattr(cache_storage2, '_copy_temp_to_permanent'):
        cache_storage2._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

    # clean database with RETAIN_LIMIT=2
    setattr(command_config2, 'clean_database', 2)
    urlwatcher2.cache_storage.clean_cache([job.get_guid() for job in urlwatcher2.jobs], command_config2.clean_database)
    setattr(command_config2, 'clean_database', None)
    guid = urlwatch_command2.urlwatcher.jobs[0].get_guid()
    assert len(cache_storage2.get_history_snapshots(guid)) == 2

    # clean database without specifying RETAIN_LIMIT
    setattr(command_config2, 'clean_database', True)
    urlwatcher2.cache_storage.clean_cache([job.get_guid() for job in urlwatcher2.jobs], command_config2.clean_database)
    setattr(command_config2, 'clean_database', None)
    guid = urlwatch_command2.urlwatcher.jobs[0].get_guid()
    assert len(cache_storage2.get_history_snapshots(guid)) == 1


def test_rollback_database(capsys: CaptureFixture[str], monkeypatch: MonkeyPatch) -> None:
    setattr(command_config, 'rollback_database', True)
    # monkeypatches the "input" function, so that it simulates the user entering "y" in the terminal:
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    urlwatcher.cache_storage = CacheSQLite3Storage(cache_file)  # type: ignore[arg-type]
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'rollback_database', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'No snapshots found after' in message


def test_check_telegram_chats(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'telegram_chats', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'telegram_chats', False)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message == 'You need to set up your bot token first (see documentation)\n'

    urlwatch_command.urlwatcher.config_storage.config['report']['telegram']['bot_token'] = 'bogus'  # noqa: S105
    setattr(command_config, 'telegram_chats', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'telegram_chats', False)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message == 'Error with token bogus: Not Found\n'

    if os.getenv('TELEGRAM_TOKEN'):
        if os.getenv('GITHUB_ACTIONS'):
            pytest.skip('Telegram testing no longer working from within GitHub Actions')
        urlwatch_command.urlwatcher.config_storage.config['report']['telegram']['bot_token'] = os.getenv(
            'TELEGRAM_TOKEN',
            '',
        )
        setattr(command_config, 'telegram_chats', True)
        with pytest.raises(SystemExit):
            urlwatch_command.handle_actions()
        setattr(command_config, 'telegram_chats', False)
        message = capsys.readouterr().out
        assert 'Say hello to your bot at https://t.me/' in message
    else:
        print('Cannot fully test Telegram as no TELEGRAM_TOKEN environment variable found')


def test_check_test_reporter(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'test_reporter', 'stdout')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_reporter', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert '01. NEW: ' in message

    setattr(command_config, 'test_reporter', 'stdout')
    urlwatch_command.urlwatcher.config_storage.config['report']['stdout']['enabled'] = False
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_reporter', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'WARNING: Reporter being tested is not enabled: stdout\n' in message

    setattr(command_config, 'test_reporter', 'does_not_exist')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_reporter', None)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert 'No such reporter: does_not_exist\n' in message


def test_check_smtp_login(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'smtp_login', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'smtp_login', False)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message.splitlines() == [
        'Please enable email reporting in the config first.',
        'Please configure the SMTP user in the config first.',
    ]


def test_check_smtp_login_not_config(capsys: CaptureFixture[str]) -> None:
    urlwatcher.config_storage.config['report']['email'].update(
        {
            'enabled': True,
            'method': 'sendmail',
            'smtp': {  # type: ignore[typeddict-item]
                'auth': '',
                'host': '',
                'user': '',
            },
        }
    )
    setattr(command_config, 'smtp_login', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'smtp_login', False)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message.splitlines() == [
        'Please set the method to SMTP for the email reporter.',
        'Authentication must be enabled for SMTP.',
        'Please configure the SMTP hostname in the config first.',
        'Please configure the SMTP user in the config first.',
    ]


@py_latest_only
def test_check_smtp_insecure_password(capsys: CaptureFixture[str]) -> None:
    urlwatcher.config_storage.config['report']['email'].update(
        {
            'enabled': True,
            'method': 'smtp',
            'smtp': {
                'auth': 'blah',  # type: ignore[typeddict-item]
                'host': 'localhost',
                'user': 'me',
                'insecure_password': 'pwd',
                'port': 25,
                'starttls': True,
            },
        }
    )
    setattr(command_config, 'smtp_login', True)
    with pytest.raises(ConnectionRefusedError):
        urlwatch_command.handle_actions()
    setattr(command_config, 'smtp_login', False)
    # assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message.splitlines() == [
        'The SMTP password is set in the config file (key "insecure_password")',
        'Trying to log into the SMTP server...',
    ]


def test_check_xmpp_login(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'xmpp_login', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'xmpp_login', False)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message.splitlines() == [
        'Please enable XMPP reporting in the config first.',
        'Please configure the XMPP sender in the config first.',
        'Please configure the XMPP recipient in the config first.',
    ]


def test_check_xmpp_login_insecure_password(capsys: CaptureFixture[str]) -> None:
    urlwatcher.config_storage.config['report']['xmpp'] = {
        'enabled': True,
        'sender': 'me',
        'recipient': 'you',
        'insecure_password': 'pwd',
    }
    setattr(command_config, 'xmpp_login', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'xmpp_login', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message == 'The XMPP password is already set in the config (key "insecure_password").\n'


def test_setup_logger_verbose(caplog: LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    setup_logger()
    assert f' {__project_name__}: {__version__} {__copyright__}\n' in caplog.text

    # """Set up logging in CLI."""
    # setup_logger(1)
    # assert not os.environ.get('DEBUG')
    # assert 30 == logging.getLogger('webchanges').getEffectiveLevel()
    # teardown_logger(1)
    # assert not os.environ.get('DEBUG')
    #
    # setup_logger(2)
    # assert os.environ['DEBUG'] == 'pw:api pytest -s'
    # assert 20 == logging.getLogger('webchanges').getEffectiveLevel()
    # teardown_logger(2)
    # assert not os.environ.get('DEBUG')
    #
    # setup_logger(3)
    # assert os.environ['DEBUG'] == 'pw:api pytest -s'
    # assert 10 == logging.getLogger('webchanges').getEffectiveLevel()
    # teardown_logger(3)
    # assert not os.environ.get('DEBUG')


@py_latest_only
def test_print_new_version(capsys: CaptureFixture[str]) -> None:
    setattr(command_config, 'check_new', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        handle_unitialized_actions(command_config)
    setattr(command_config, 'check_new', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message.startswith(f'{__project_name__} {__version__}.')


def test_locate_jobs_files() -> None:
    file = locate_jobs_files(Path('test'), Path('nowhere'), '.noext')
    assert file == [PurePath('test')]


def test_locate_storage_file() -> None:
    file = locate_storage_file(Path('test'), Path('nowhere'), '.noext')
    assert file == PurePath('test')


def test_job_states_verb() -> None:
    jobs_file = config_path.joinpath('jobs-time.yaml')
    cache_storage = CacheSQLite3Storage(cache_file)  # type: ignore[arg-type]
    jobs_storage = YamlJobsStorage([jobs_file])
    command_config = new_command_config(jobs_file=jobs_file)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    urlwatcher.jobs[0].command = 'echo TEST'
    urlwatcher.jobs[0].name = 'echo TEST'

    # run once
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    assert urlwatcher.report.job_states[-1].verb == 'new'

    # run twice
    urlwatcher.run_jobs()
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'


def test_job_states_verb_notimestamp_unchanged() -> None:
    jobs_file = config_path.joinpath('jobs-time.yaml')
    cache_storage = CacheSQLite3Storage(cache_file)  # type: ignore[arg-type]
    jobs_storage = YamlJobsStorage([jobs_file])
    command_config = new_command_config(jobs_file=jobs_file)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    urlwatcher.jobs[0].command = 'echo TEST'
    urlwatcher.jobs[0].name = 'echo TEST'

    # run once
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    assert urlwatcher.report.job_states[-1].verb == 'new'

    # modify database
    guid = urlwatcher.cache_storage.get_guids()[0]
    snapshot = urlwatcher.cache_storage.load(guid)
    urlwatcher.cache_storage.delete(guid)
    urlwatcher.cache_storage.save(guid=guid, data=snapshot.data, timestamp=0, tries=1, etag=snapshot.etag)
    cache_storage._copy_temp_to_permanent(delete=True)

    # run twice
    urlwatcher.run_jobs()
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'


def test_job_states_verb_notimestamp_changed() -> None:
    jobs_file = config_path.joinpath('jobs-time.yaml')
    cache_storage = CacheSQLite3Storage(cache_file)  # type: ignore[arg-type]
    jobs_storage = YamlJobsStorage([jobs_file])
    command_config = new_command_config(jobs_file=jobs_file)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    urlwatcher.jobs[0].command = 'echo TEST'
    urlwatcher.jobs[0].name = 'echo TEST'

    # run once
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    assert urlwatcher.report.job_states[-1].verb == 'new'

    # modify database (save no timestamp)
    guid = urlwatcher.jobs[0].get_guid()
    snapshot = urlwatcher.cache_storage.load(guid)
    urlwatcher.cache_storage.delete(guid)
    urlwatcher.cache_storage.save(guid=guid, data=snapshot.data, timestamp=0, tries=snapshot.tries, etag=snapshot.etag)
    cache_storage._copy_temp_to_permanent(delete=True)

    # run twice
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'

    # modify database to 1 try
    snapshot = urlwatcher.cache_storage.load(guid)
    urlwatcher.cache_storage.delete(guid)
    urlwatcher.cache_storage.save(
        guid=guid, data=snapshot.data, timestamp=snapshot.timestamp, tries=1, etag=snapshot.etag
    )
    cache_storage._copy_temp_to_permanent(delete=True)
    # run again
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'

    # modify database to no timestamp
    urlwatcher.cache_storage.delete(guid)
    urlwatcher.cache_storage.save(guid=guid, data=snapshot.data, timestamp=0, tries=snapshot.tries, etag=snapshot.etag)
    cache_storage._copy_temp_to_permanent(delete=True)
    # run again
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'

    # modify database to no timestamp and 1 try
    urlwatcher.cache_storage.delete(guid)
    urlwatcher.cache_storage.save(guid=guid, data=snapshot.data, timestamp=0, tries=1, etag=snapshot.etag)
    cache_storage._copy_temp_to_permanent(delete=True)
    # run again
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'


def test_list_error_jobs_with_error(capsys: CaptureFixture[str]) -> None:
    jobs_file2 = config_path.joinpath('jobs-invalid_url.yaml')
    command_config2 = new_command_config(jobs_file=jobs_file2)
    setattr(command_config2, 'errors', 'stdout')
    config_storage2 = YamlConfigStorage(config_file)
    config_storage2.load()
    cache_storage2 = CacheSQLite3Storage(cache_file)  # type: ignore[arg-type]
    jobs_storage2 = YamlJobsStorage([jobs_file2])
    urlwatcher2 = Urlwatch(command_config2, config_storage2, cache_storage2, jobs_storage2)  # main.py
    urlwatch_command2 = UrlwatchCommand(urlwatcher2)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command2.handle_actions()
    setattr(command_config2, 'errors', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert '\n  1: Error "' in message
