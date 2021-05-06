"""Test running of jobs"""

import logging
import os
import socket
import sys
from typing import Any, Dict

import pytest

from webchanges import __project_name__
from webchanges.config import BaseConfig
from webchanges.handler import JobState
from webchanges.jobs import BrowserResponseError, JobBase, NotModifiedError
from webchanges.main import Urlwatch
from webchanges.storage import CacheDirStorage, CacheSQLite3Storage, YamlConfigStorage, YamlJobsStorage

logger = logging.getLogger(__name__)


def is_connected() -> bool:
    """Check if connected to Internet."""
    try:
        # connect to the host -- tells us if the host is actually reachable
        sock = socket.create_connection(('connectivitycheck.gstatic.com', 80))
        if sock is not None:
            sock.close()
        return True
    except OSError:
        pass
    return False


connection_required = pytest.mark.skipif(not is_connected(), reason='no Internet connection')
py37_required = pytest.mark.skipif(sys.version_info < (3, 7), reason='requires Python 3.7')

here = os.path.dirname(__file__)

TEST_JOBS = [
    ({'url': 'https://www.google.com/#a',
      'name': 'testing url basic job',
      'cookies': {'X-test': ''},
      'encoding': 'ascii',  # required for testing Python 3.6 in Windows as it has a tendency of erroring on cp1252
      'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                'Chrome/90.0.4430.93 Safari/537.36'},
      'ignore_cached': True,
      'ignore_connection_errors': False,
      'ignore_http_error_codes': 200,
      'ignore_timeout_errors': False,
      'ignore_too_many_redirects': False,
      'method': 'GET',
      'no_redirects': True,
      'ssl_no_verify': False,
      'timeout': 15,
      'user_visible_url': 'https://www.google.com/#a_visible',
      },
     'Google'),
    ({'url': 'https://www.google.com/#b',
      'name': 'testing url job with use_browser',
      'use_browser': True,
      'block_elements': ['stylesheet', 'font', 'image', 'media'],
      'cookies': {'X-test': ''},
      'headers': {'Accept-Language': 'en-US,en'},
      'ignore_https_errors': False,
      'switches': ['--window-size=1298,1406'],
      'timeout': 15,
      'user_visible_url': 'https://www.google.com/#b_visible',
      'wait_for': 1,
      'wait_for_navigation': 'https://www.google.com/',
      'wait_until': 'load',
      },
     'Google'),
    ({'command': 'echo test',
      },
     'test'),
]

TEST_ALL_URL_JOBS = [{}, {'use_browser': True}]


@connection_required
@pytest.mark.parametrize('input_job, output', TEST_JOBS)
def test_run_job(input_job: Dict[str, Any], output: str) -> None:
    if input_job.get('use_browser') and os.getenv('GITHUB_ACTIONS') and sys.version_info < (3, 7):
        logger.warning('Skipping test on legacy code for Pyppeteer in GitHub Actions as it fails with error'
                       'pyppeteer.errors.BrowserError: Browser closed unexpectedly')
        return
    job = JobBase.unserialize(input_job)
    cache_storage = CacheDirStorage(os.path.join(here, 'data'))
    job_state = JobState(cache_storage, job)
    job.main_thread_enter()
    data, etag = job.retrieve(job_state)
    assert output in data
    job.main_thread_exit()


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_etag(job_data: Dict[str, Any]) -> None:
    if job_data.get('use_browser') and os.getenv('GITHUB_ACTIONS') and sys.version_info < (3, 7):
        logger.warning('Skipping test on legacy code for Pyppeteer in GitHub Actions as it fails with error'
                       'pyppeteer.errors.BrowserError: Browser closed unexpectedly')
        return
    if job_data.get('use_browser') and sys.version_info < (3, 7):
        logger.warning('Skipping test on legacy code for Pyppeteer as it does not capture ETags')
        return

    job_data['url'] = 'https://github.githubassets.com/images/search-key-slash.svg'
    job = JobBase.unserialize(job_data)
    cache_storage = CacheDirStorage(os.path.join(here, 'data'))
    job_state = JobState(cache_storage, job)
    job.main_thread_enter()
    data, etag = job.retrieve(job_state)
    assert etag
    job.main_thread_exit()


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_etag_304_request(job_data: Dict[str, Any]) -> None:
    if job_data.get('use_browser'):
        logger.warning('Skipping test on Pyppeteer since capturing of 304 cannot be implemented in Chromium 89')
        return

    job_data['url'] = 'https://github.githubassets.com/images/search-key-slash.svg'
    job = JobBase.unserialize(job_data)
    cache_storage = CacheDirStorage(os.path.join(here, 'data'))
    job_state = JobState(cache_storage, job)
    job.main_thread_enter()

    job.index_number = 1
    data, etag = job.retrieve(job_state)
    job_state.old_etag = etag

    job.index_number = 2
    with pytest.raises(NotModifiedError) as pytest_wrapped_e:
        job.retrieve(job_state)

    job.main_thread_exit()
    assert str(pytest_wrapped_e.value) == '304'


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_ignore_connection_errors_and_bad_proxy(job_data: Dict[str, Any]) -> None:
    if job_data.get('use_browser'):
        logger.warning('Skipping test on Pyppeteer since it times out after 90 seconds or so')
        return

    job_data['url'] = 'http://connectivitycheck.gstatic.com/generate_204'
    job_data['http_proxy'] = 'http://notworking:ever@google.com:8080'
    job_data['timeout'] = .001
    job = JobBase.unserialize(job_data)
    cache_storage = CacheDirStorage(os.path.join(here, 'data'))
    job_state = JobState(cache_storage, job)
    job_state.process()
    if not isinstance(job_state.exception, BrowserResponseError):
        assert 'Max retries exceeded' in str(job_state.exception.args)
    assert job_state.error_ignored is False

    job_data['ignore_connection_errors'] = True
    job = JobBase.unserialize(job_data)
    job_state = JobState(cache_storage, job)
    job_state.process()
    assert job_state.error_ignored is True


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_ignore_http_error_codes(job_data: Dict[str, Any]) -> None:
    if job_data.get('use_browser') and sys.version_info < (3, 7):
        logger.warning('Skipping test on legacy code for Pyppeteer as it does not capture exceptions')
        return
    job_data['url'] = 'https://www.google.com/teapot'
    job_data['timeout'] = 30
    job = JobBase.unserialize(job_data)
    cache_storage = CacheDirStorage(os.path.join(here, 'data'))
    job_state = JobState(cache_storage, job)
    job_state.process()
    if isinstance(job_state.exception, BrowserResponseError):
        assert job_state.exception.status_code == 418
    else:
        assert any(x in str(job_state.exception.args) for x in ("I'm a Teapot", '418'))
    assert job_state.error_ignored is False

    job_data['ignore_http_error_codes'] = [418]
    job = JobBase.unserialize(job_data)
    job_state = JobState(cache_storage, job)
    job_state.process()
    assert job_state.error_ignored is True


class ConfigForTest(BaseConfig):
    """BaseConfig class for testing purposes."""
    def __init__(self, config_file: str, urls_file: str, cache_file: str, hooks_file: str, verbose: bool) -> None:
        super().__init__(__project_name__, here, config_file, urls_file, cache_file, hooks_file, verbose)
        self.edit = False
        self.edit_hooks = False


@connection_required
@py37_required
# Legacy code for Pyppeteer is not optimized for concurrency and fails in Github Actions with error
# pyppeteer.errors.BrowserError: Browser closed unexpectedly.
def test_stress_use_browser() -> None:
    jobs_file = os.path.join(here, 'data', 'jobs-use_browser.yaml')
    config_file = os.path.join(here, 'data', 'config.yaml')
    cache_file = os.path.join(here, 'data', 'cache.db')
    hooks_file = ''

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage(jobs_file)
    cache_storage = CacheSQLite3Storage(cache_file)

    if not os.getenv('GITHUB_ACTIONS'):
        from webchanges.cli import setup_logger_verbose
        setup_logger_verbose()

    try:
        urlwatch_config = ConfigForTest(config_file, jobs_file, cache_file, hooks_file, True)
        urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)
        urlwatcher.run_jobs()
    finally:
        cache_storage.close()
        if os.path.exists(cache_file):
            os.remove(cache_file)
