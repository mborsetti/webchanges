"""Test commands."""

import os
import time
from pathlib import Path, PurePath

import pytest

from webchanges import __copyright__, __project_name__, __version__
from webchanges.cli import locate_storage_file, migrate_from_urlwatch, setup_logger_verbose
from webchanges.command import UrlwatchCommand
from webchanges.config import CommandConfig
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, YamlConfigStorage, YamlJobsStorage

here = Path(__file__).parent

config_dir = here.joinpath('data')
config_file = config_dir.joinpath('config.yaml')
jobs_file = config_dir.joinpath('jobs-echo_test.yaml')
cache_file = ':memory:'
hooks_file = config_dir.joinpath('hooks_test.py')

config_storage = YamlConfigStorage(config_file)
cache_storage = CacheSQLite3Storage(cache_file)
jobs_storage = YamlJobsStorage(jobs_file)
command_config = CommandConfig(
    __project_name__, os.path.dirname(__file__), config_file, jobs_file, hooks_file, cache_file, True
)
urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py

editor = os.getenv('EDITOR')
if os.name == 'nt':
    os.environ['EDITOR'] = 'rundll32'
else:
    os.environ['EDITOR'] = 'true'
visual = os.getenv('VISUAL')
if visual:
    del os.environ['VISUAL']


@pytest.fixture(scope='module', autouse=True)
def cleanup(request):
    """Cleanup once we are finished."""

    def finalizer():
        """Cleanup once we are finished."""
        if editor:
            os.environ['EDITOR'] = editor
        if visual:
            os.environ['VISUAL'] = visual
        try:
            urlwatcher.close()
        except AttributeError:
            pass
        # Python 3.9: config_edit = config_file.with_stem(config_file.stem + '_edit')
        # Python 3.9: hooks_edit = hooks_file.with_stem(hooks_file.stem + '_edit')
        config_edit = config_file.joinpath(config_file.stem + '_edit' + ''.join(config_file.suffixes))
        hooks_edit = hooks_file.joinpath(hooks_file.stem + '_edit' + ''.join(hooks_file.suffixes))
        for filename in (config_edit, hooks_edit):
            # Python 3.8: replace with filename.unlink(missing_ok=True)
            if filename.is_file():
                filename.unlink()

    request.addfinalizer(finalizer)


def test_migration():
    """test check for existence of legacy urlwatch 2.2 files in urlwatch dir"""
    assert migrate_from_urlwatch(config_file, jobs_file, hooks_file, Path(cache_file)) is None


def test_edit_hooks(capsys):
    setattr(command_config, 'edit_hooks', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'edit_hooks', False)
    assert pytest_wrapped_e.value.code is None
    message = capsys.readouterr().out
    assert message == f'Saving edit changes in {urlwatch_command.urlwatch_config.hooks}\n'


def test_edit_hooks_fail(capsys):
    editor = os.getenv('EDITOR')
    os.environ['EDITOR'] = 'does_not_exist_and_should_trigger_an_error'
    setattr(command_config, 'edit_hooks', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'edit_hooks', False)
    os.environ['EDITOR'] = editor
    hooks_edit = urlwatch_command.urlwatch_config.hooks.parent.joinpath(
        urlwatch_command.urlwatch_config.hooks.stem + '_edit' + ''.join(urlwatch_command.urlwatch_config.hooks.suffixes)
    )
    hooks_edit.unlink()
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert 'Parsing failed:' in message


def test_show_features_and_verbose(capsys):
    setattr(command_config, 'features', True)
    setattr(command_config, 'verbose', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'features', False)
    setattr(command_config, 'verbose', False)
    assert pytest_wrapped_e.value.code is None
    message = capsys.readouterr().out
    assert '* browser - Retrieve a URL, emulating a real web browser (use_browser: true).' in message


def test_list_jobs_verbose(capsys):
    setattr(command_config, 'list', True)
    urlwatch_config_verbose = urlwatcher.urlwatch_config.verbose
    urlwatcher.urlwatch_config.verbose = False
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'list', False)
    urlwatcher.urlwatch_config.verbose = urlwatch_config_verbose
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message == '  1: Sample webchanges job; used by command_test.py (echo test)\n'


def test_list_jobs_not_verbose(capsys):
    setattr(command_config, 'list', True)
    urlwatch_config_verbose = urlwatcher.urlwatch_config.verbose
    urlwatcher.urlwatch_config.verbose = False
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'list', False)
    urlwatcher.urlwatch_config.verbose = urlwatch_config_verbose
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message == '  1: Sample webchanges job; used by command_test.py (echo test)\n'


def test__find_job():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    assert urlwatch_command._find_job('https://example.com/') is None


def test__find_job_index_error():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    assert urlwatch_command._find_job(100) is None


def test__get_job():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    assert urlwatch_command._get_job(1).get_location() == 'echo test'


def test__get_job_index_error(capsys):
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command._get_job(100).get_location()
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message == 'Not found: 100\n'


def test_test_job(capsys):
    setattr(command_config, 'test_job', 1)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_job', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    message = message.replace('\n\n ', '\n').replace('\r', '')  # Python 3.6
    assert message == (
        '\n'
        'Sample webchanges job; used by command_test.py\n'
        '----------------------------------------------\n'
        '\n'
        'test\n'
        '\n'
    )


def test_test_diff(capsys):
    jobs_file = config_dir.joinpath('jobs-time.yaml')
    jobs_storage = YamlJobsStorage(jobs_file)
    command_config = CommandConfig(__project_name__, config_dir, config_file, jobs_file, hooks_file, cache_file, False)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    if os.name == 'nt':
        urlwatcher.jobs[0].command = 'echo %time% %random%'

    setattr(command_config, 'test_diff', 1)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_diff', None)
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message == 'Not enough historic data available (need at least 2 different snapshots)\n'

    # run once
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)

    # run twice
    time.sleep(0.0001)
    urlwatcher.run_jobs()
    cache_storage._copy_temp_to_permanent(delete=True)
    guid = urlwatcher.jobs[0].get_guid()
    history = cache_storage.get_history_data(guid)
    assert len(history) == 2

    setattr(command_config, 'test_diff', 1)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_diff', None)
    urlwatcher.cache_storage.delete(guid)
    assert pytest_wrapped_e.value.code is None
    message = capsys.readouterr().out
    assert '=== Filtered diff between state 0 and state -1 ===\n' in message


def test_list_error_jobs(capsys):
    setattr(command_config, 'errors', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'errors', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'Jobs, if any, with errors or returning no data after filtering in ' in message


def test_modify_urls(capsys):
    setattr(command_config, 'add', 'url=https://www.example.com/#test_modify_urls')
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'add', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert "Adding <url url='https://www.example.com/#test_modify_urls'" in message
    setattr(command_config, 'delete', 'https://www.example.com/#test_modify_urls')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete', None)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert "Removed <url url='https://www.example.com/#test_modify_urls'" in message


def test_delete_snapshot():
    jobs_file = config_dir.joinpath('jobs-time.yaml')
    jobs_storage = YamlJobsStorage(jobs_file)
    command_config = CommandConfig(__project_name__, config_dir, config_file, jobs_file, hooks_file, cache_file, False)
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    if os.name == 'nt':
        urlwatcher.jobs[0].command = 'echo %time% %random%'

    setattr(command_config, 'delete_snapshot', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete_snapshot', False)
    assert 'No snapshots found to be deleted for Job 1:' in pytest_wrapped_e.value.code

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

    setattr(command_config, 'delete_snapshot', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete_snapshot', False)
    assert 'Deleted last snapshot of Job 1:' in pytest_wrapped_e.value.code


def test_gc_cache(capsys):
    setattr(command_config, 'gc_cache', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'gc_cache', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    if os.name == 'nt':
        assert message == 'Deleting: 695925f99befa832d8aeae8c0f1836a59942866d (no longer being tracked)\n'
    else:
        assert message == 'Deleting: 2f540ba442cd4a368fd3eb918dbe6d621ccae30b (no longer being tracked)\n'


def test_clean_cache(capsys):
    setattr(command_config, 'clean_cache', True)
    urlwatcher.cache_storage = CacheSQLite3Storage(cache_file)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'clean_cache', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert message == ''


def test_rollback_cache(capsys):
    setattr(command_config, 'rollback_cache', True)
    urlwatcher.cache_storage = CacheSQLite3Storage(cache_file)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'rollback_cache', False)
    assert pytest_wrapped_e.value.code == 0
    message = capsys.readouterr().out
    assert 'No snapshots found after' in message


def test_check_edit_config():
    setattr(command_config, 'edit_config', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_edit_config()
    setattr(command_config, 'edit_config', False)
    assert pytest_wrapped_e.value.code == 0


def test_check_edit_config_fail(capsys):
    editor = os.getenv('EDITOR')
    os.environ['EDITOR'] = 'does_not_exist_and_should_trigger_an_error'
    setattr(command_config, 'edit_config', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(OSError):
        urlwatch_command.check_edit_config()
    setattr(command_config, 'edit_config', False)
    os.environ['EDITOR'] = editor
    filename = urlwatcher.config_storage.filename
    file_edit = filename.parent.joinpath(filename.stem + '_edit' + ''.join(filename.suffixes))
    file_edit.unlink()
    message = capsys.readouterr().out
    assert 'Errors in file:' in message


def test_check_telegram_chats(capsys):
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'telegram_chats', False)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_telegram_chats()
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message == 'You need to set up your bot token first (see documentation)\n'
    setattr(command_config, 'telegram_chats', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_telegram_chats()
    assert pytest_wrapped_e.value.code == 1
    message = capsys.readouterr().out
    assert message == 'You need to set up your bot token first (see documentation)\n'


def test_check_test_reporter():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'test_reporter', 'stdout')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_test_reporter()
    assert pytest_wrapped_e.value.code == 0


def test_check_smtp_login():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'smtp_login', False)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_smtp_login()
    assert pytest_wrapped_e.value.code == 1
    setattr(command_config, 'smtp_login', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_smtp_login()
    assert pytest_wrapped_e.value.code == 1


def test_check_xmpp_login():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'xmpp_login', False)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_xmpp_login()
    assert pytest_wrapped_e.value.code == 1
    setattr(command_config, 'xmpp_login', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_xmpp_login()
    assert pytest_wrapped_e.value.code == 1


def test_setup_logger_verbose(caplog):
    setup_logger_verbose()
    assert f' {__project_name__}: {__version__} {__copyright__}\n' in caplog.text


def test_locate_storage_file():
    file = locate_storage_file(Path('test'), Path('nowhere'), '.noext')
    assert file == PurePath('test')
