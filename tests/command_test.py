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

editor = os.getenv('EDITOR')
os.environ['EDITOR'] = 'echo'
visual = os.getenv('VISUAL')
if visual:
    del os.environ['VISUAL']


def test_migration():
    """test migration of legacy urlwatch files"""
    assert not migrate_from_urlwatch(config_file, jobs_file, hooks_file, cache_file)


def test_command_check_edit_config():
    setattr(command_config, 'edit', False)
    setattr(command_config, 'edit_config', False)
    setattr(command_config, 'edit_hooks', False)
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    assert not urlwatch_command.check_edit_config()
    urlwatch_command.urlwatcher.close()


# def test_command_edit_hooks():
#     urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
#     assert not urlwatch_command.edit_hooks()


def test_command_show_features():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    assert not urlwatch_command.show_features()


def test_command_list_jobs():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    assert not urlwatch_command.list_jobs()


def test_command_find_jobs():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    assert not urlwatch_command._find_job('https://example.com/')


def test_command_get_jobs():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    assert 'echo test' == urlwatch_command._get_job(1).get_location()


# def test_command_test_filter():
#     urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
#     assert not urlwatch_command.test_job(1)
#     urlwatch_command.urlwatcher.close()
#
#
# def test_command_test_diff_filter():
#     urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
#     assert 1 == urlwatch_command.test_diff(1)
#     urlwatch_command.urlwatcher.close()


def test_command_list_error_jobs():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    assert not urlwatch_command.list_error_jobs()


def test_command_check_telegram_chats():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    setattr(command_config, 'telegram_chats', False)
    assert not urlwatch_command.check_telegram_chats()


def test_command_check_test_reporter():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    setattr(command_config, 'test_reporter', True)
    assert not urlwatch_command.check_test_reporter()


def test_command_check_smtp_login():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    setattr(command_config, 'smtp_login', False)
    assert not urlwatch_command.check_smtp_login()


def test_command_check_xmpp_login():
    urlwatch_command = UrlwatchCommand(Urlwatch(command_config, config_storage, cache_storage, jobs_storage))
    setattr(command_config, 'xmpp_login', False)
    assert not urlwatch_command.check_xmpp_login()


@pytest.fixture(scope='session', autouse=True)
def cleanup(request):
    """Cleanup once we are finished."""
    def finalizer():
        if editor:
            os.environ['EDITOR'] = editor
        if visual:
            os.environ['VISUAL'] = visual
        for filename in (cache_file, f'{cache_file}.bak', f'{cache_file}.minidb'):
            if os.path.exists(filename):
                os.remove(filename)

    request.addfinalizer(finalizer)
