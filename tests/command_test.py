"""tests filters based on a set of patterns"""

import logging
import os

import pytest

from webchanges import __project_name__ as project_name
from webchanges.cli import migrate_from_urlwatch
from webchanges.command import UrlwatchCommand
from webchanges.config import CommandConfig
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, JobsYaml, YamlConfigStorage

logger = logging.getLogger(__name__)

here = os.path.dirname(__file__)

config_dir = os.path.join(here, 'data')
prefix, bindir = os.path.split(config_dir)
config_file = os.path.join(here, 'data', 'config.yaml')
jobs_file = os.path.join(here, 'data', 'jobs-echo_test.yaml')
cache_file = os.path.join(here, 'data', 'cache.db')
hooks_file = os.path.join(here, 'data', 'hooks.py')

config_storage = YamlConfigStorage(config_file)
cache_storage = CacheSQLite3Storage(cache_file)
jobs_storage = JobsYaml(jobs_file)
command_config = CommandConfig(project_name, config_dir, bindir, prefix, config_file, jobs_file, hooks_file,
                               cache_file, verbose=False)
urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py

editor = os.getenv('EDITOR')
if os.name == 'nt':
    os.environ['EDITOR'] = 'rundll32'
else:
    os.environ['EDITOR'] = 'true'
visual = os.getenv('VISUAL')
if visual:
    del os.environ['VISUAL']


def test_migration():
    """test check for existence of legacy urlwatch 2.2 files in urlwatch dirdir """
    assert migrate_from_urlwatch(config_file, jobs_file, hooks_file, cache_file) is None


def test_edit_hooks():
    setattr(command_config, 'edit_hooks', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'edit_hooks', False)
    assert pytest_wrapped_e.value.code is None


def test_edit_hooks_fail():
    editor = os.getenv('EDITOR')
    os.environ['EDITOR'] = 'does_not_exist_and_should_trigger_an_error'
    setattr(command_config, 'edit_hooks', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'edit_hooks', False)
    os.environ['EDITOR'] = editor
    assert pytest_wrapped_e.value.code == 1


def test_show_features_and_verbose():
    setattr(command_config, 'features', True)
    setattr(command_config, 'verbose', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'features', False)
    setattr(command_config, 'verbose', False)
    assert pytest_wrapped_e.value.code is None


def test_list_jobs_verbose():
    setattr(command_config, 'list', True)
    urlwatch_config_verbose = urlwatcher.urlwatch_config.verbose
    urlwatcher.urlwatch_config.verbose = False
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'list', False)
    urlwatcher.urlwatch_config.verbose = urlwatch_config_verbose
    assert pytest_wrapped_e.value.code is None


def test_list_jobs_not_verbose():
    setattr(command_config, 'list', True)
    urlwatch_config_verbose = urlwatcher.urlwatch_config.verbose
    urlwatcher.urlwatch_config.verbose = False
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'list', False)
    urlwatcher.urlwatch_config.verbose = urlwatch_config_verbose
    assert pytest_wrapped_e.value.code is None


def test__find_job():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    assert urlwatch_command._find_job('https://example.com/') is None


def test__find_job_index_error():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    assert urlwatch_command._find_job(100) is None


def test__get_job():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    assert urlwatch_command._get_job(1).get_location() == 'echo test'


def test__get_job_index_error():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command._get_job(100).get_location()
    assert pytest_wrapped_e.value.code == 1


def test_test_job():
    setattr(command_config, 'test_job', 1)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_job', None)
    assert pytest_wrapped_e.value.code is None


def test_test_diff():
    jobs_file2 = os.path.join(here, 'data', 'jobs-time.yaml')
    jobs_storage2 = JobsYaml(jobs_file2)
    command_config2 = CommandConfig(project_name, config_dir, bindir, prefix, config_file, jobs_file2, hooks_file,
                                    cache_file, verbose=False)
    urlwatcher2 = Urlwatch(command_config2, config_storage, cache_storage, jobs_storage2)  # main.py

    setattr(command_config2, 'test_diff', 1)
    urlwatch_command = UrlwatchCommand(urlwatcher2)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config2, 'test_diff', None)
    assert pytest_wrapped_e.value.code == 1

    job = urlwatcher2.jobs[0]
    if os.name == 'nt':
        job.command = 'echo %time%'
    job.filter = []
    guid = job.get_guid()

    # run once
    urlwatcher2.run_jobs()
    cache_storage.close()
    cache_storage.__init__(cache_file)

    # run twice
    urlwatcher2.run_jobs()
    cache_storage.close()
    cache_storage.__init__(cache_file)
    history = cache_storage.get_history_data(guid)
    assert len(history) == 2

    setattr(command_config2, 'test_diff', 1)
    urlwatch_command = UrlwatchCommand(urlwatcher2)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config2, 'test_diff', None)
    assert pytest_wrapped_e.value.code is None


def test_list_error_jobs():
    setattr(command_config, 'errors', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'errors', False)
    assert pytest_wrapped_e.value.code is None


def test_modify_urls():
    setattr(command_config, 'add', 'url=https://www.example.com/#test_modify_urls')
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'add', None)
    assert pytest_wrapped_e.value.code is None
    setattr(command_config, 'delete', 'https://www.example.com/#test_modify_urls')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'delete', None)
    assert pytest_wrapped_e.value.code is None


def test_gc_cache():
    setattr(command_config, 'gc_cache', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'gc_cache', False)
    assert pytest_wrapped_e.value.code == 0


def test_clean_cache():
    setattr(command_config, 'clean_cache', True)
    urlwatcher.cache_storage = CacheSQLite3Storage(cache_file)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'clean_cache', False)
    assert pytest_wrapped_e.value.code == 0


def test_rollback_cache():
    setattr(command_config, 'rollback_cache', True)
    urlwatcher.cache_storage = CacheSQLite3Storage(cache_file)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'rollback_cache', False)
    assert pytest_wrapped_e.value.code == 0


def test_check_edit_config():
    setattr(command_config, 'edit_config', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_edit_config()
    setattr(command_config, 'edit_config', False)
    assert pytest_wrapped_e.value.code is None


def test_check_edit_config_fail():
    editor = os.getenv('EDITOR')
    os.environ['EDITOR'] = 'does_not_exist_and_should_trigger_an_error'
    setattr(command_config, 'edit_config', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(OSError) as pytest_wrapped_e:
        urlwatch_command.check_edit_config()
    setattr(command_config, 'edit_config', False)
    os.environ['EDITOR'] = editor
    assert 'pytest: ' in str(pytest_wrapped_e.value)


def test_check_telegram_chats():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'telegram_chats', False)
    assert not urlwatch_command.check_telegram_chats()
    setattr(command_config, 'telegram_chats', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_telegram_chats()
    assert pytest_wrapped_e.value.code == 1


def test_check_test_reporter():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'test_reporter', 'stdout')
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_test_reporter()
    assert pytest_wrapped_e.value.code == 0


def test_check_smtp_login():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'smtp_login', False)
    assert not urlwatch_command.check_smtp_login()
    setattr(command_config, 'smtp_login', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_smtp_login()
    assert pytest_wrapped_e.value.code == 1


def test_check_xmpp_login():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'xmpp_login', False)
    assert not urlwatch_command.check_xmpp_login()
    setattr(command_config, 'xmpp_login', True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.check_xmpp_login()
    assert pytest_wrapped_e.value.code == 1


@pytest.fixture(scope='session', autouse=True)
def cleanup(request):
    """Cleanup once we are finished."""
    def finalizer():
        if editor:
            os.environ['EDITOR'] = editor
        if visual:
            os.environ['VISUAL'] = visual
        try:
            urlwatcher.close()
        except AttributeError:
            pass
        fn_base, fn_ext = os.path.splitext(config_file)
        config_edit = f'{fn_base}.edit{fn_ext}'
        fn_base, fn_ext = os.path.splitext(hooks_file)
        hooks_edit = f'{fn_base}.edit{fn_ext}'
        for filename in (cache_file, config_edit, hooks_edit):
            if os.path.exists(filename):
                os.remove(filename)

    request.addfinalizer(finalizer)
