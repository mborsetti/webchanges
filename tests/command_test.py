"""tests filters based on a set of patterns"""

import logging
import os

import pytest

from webchanges import __project_name__
from webchanges.cli import migrate_from_urlwatch
from webchanges.command import UrlwatchCommand
from webchanges.config import CommandConfig
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, JobsYaml, YamlConfigStorage

logger = logging.getLogger(__name__)

here = os.path.dirname(__file__)

project_name = __project_name__
config_dir = os.path.join(here, 'data')
prefix, bindir = os.path.split(config_dir)
config_file = os.path.join(here, 'data', 'config.yaml')
jobs_file = os.path.join(here, 'data', 'command_jobs.yaml')
cache_file = os.path.join(here, 'data', 'cache.db')
hooks_file = os.path.join(here, 'data', 'hooks_test.py')

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
    """test migration of legacy urlwatch files"""
    assert not migrate_from_urlwatch(config_file, jobs_file, hooks_file, cache_file)


def test_edit_hooks():
    setattr(command_config, 'edit_hooks', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'edit_hooks', False)
    assert pytest_wrapped_e.value.code is None


def test_show_features():
    setattr(command_config, 'features', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'features', False)
    assert pytest_wrapped_e.value.code is None


def test_list_jobs():
    setattr(command_config, 'list', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'list', False)
    assert pytest_wrapped_e.value.code is None


def test__find_job():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    assert not urlwatch_command._find_job('https://example.com/')


def test__get_job():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    assert 'echo test' == urlwatch_command._get_job(1).get_location()


def test_test_job():
    setattr(command_config, 'test_job', 1)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_job', None)
    assert pytest_wrapped_e.value.code is None


def test_test_diff():
    setattr(command_config, 'test_diff', 1)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'test_diff', None)
    assert pytest_wrapped_e.value.code == 1


def test_list_error_jobs():
    setattr(command_config, 'errors', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    setattr(command_config, 'errors', False)
    assert pytest_wrapped_e.value.code is None


# def test_modify_urls():
#     pass


def test_check_edit_config():
    setattr(command_config, 'edit', True)
    urlwatch_command = UrlwatchCommand(urlwatcher)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        urlwatch_command.handle_actions()
    urlwatch_command.urlwatcher.close()
    setattr(command_config, 'edit', False)
    assert pytest_wrapped_e.value.code is None
    #
    # urlwatch_command = UrlwatchCommand(urlwatcher)
    # assert not urlwatch_command.check_edit_config()
    # urlwatch_command.urlwatcher.close()


def test_check_telegram_chats():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'telegram_chats', False)
    assert not urlwatch_command.check_telegram_chats()
    setattr(command_config, 'telegram_chats', True)
    try:
        urlwatch_command.check_telegram_chats()
    except SystemExit as e:
        assert e.code == 1


def test_check_test_reporter():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'test_reporter', 'stdout')
    try:
        urlwatch_command.check_test_reporter()
    except SystemExit as e:
        assert e.code == 0


def test_check_smtp_login():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'smtp_login', False)
    assert not urlwatch_command.check_smtp_login()
    setattr(command_config, 'smtp_login', True)
    try:
        urlwatch_command.check_smtp_login()
    except SystemExit as e:
        assert e.code == 1


def test_check_xmpp_login():
    urlwatch_command = UrlwatchCommand(urlwatcher)
    setattr(command_config, 'xmpp_login', False)
    assert not urlwatch_command.check_xmpp_login()
    setattr(command_config, 'xmpp_login', True)
    try:
        urlwatch_command.check_xmpp_login()
    except SystemExit as e:
        assert e.code == 1


@pytest.fixture(scope='session', autouse=True)
def cleanup(request):
    """Cleanup once we are finished."""
    def finalizer():
        if editor:
            os.environ['EDITOR'] = editor
        if visual:
            os.environ['VISUAL'] = visual
        for filename in (cache_file,):
            if os.path.exists(filename):
                os.remove(filename)

    request.addfinalizer(finalizer)
