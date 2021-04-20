"""Test running of jobs"""

import logging
import os
import sys

import pytest

from webchanges import __project_name__
from webchanges.config import BaseConfig
from webchanges.handler import JobState
from webchanges.jobs import JobBase, NotModifiedError
from webchanges.main import Urlwatch
from webchanges.storage import CacheDirStorage, CacheSQLite3Storage, YamlConfigStorage, YamlJobsStorage

py37_required = pytest.mark.skipif(sys.version_info < (3, 7), reason='requires Python 3.7')

logger = logging.getLogger(__name__)

here = os.path.dirname(__file__)

TEST_JOBS = [
    ({'url': 'https://www.google.com/#a',
      'name': 'testing url basic job',
      'cookies': {'X-test': ''},
      'encoding': 'ascii',  # required for testing Python 3.6 in Windows as it has a tendency of erroring on cp1252
      'headers': {'Accept-Language': 'en-US,en'},
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

TEST_JOBS_ETAG = [
    {'url': 'https://github.githubassets.com/images/search-key-slash.svg'},
    {'url': 'https://github.githubassets.com/images/search-key-slash.svg',
            'use_browser': True}
]


@pytest.mark.parametrize('input_job, output', TEST_JOBS)
def test_run_job(input_job, output):
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


@pytest.mark.parametrize('job_data', TEST_JOBS_ETAG)
def test_check_etag(job_data):
    if job_data.get('use_browser') and os.getenv('GITHUB_ACTIONS') and sys.version_info < (3, 7):
        logger.warning('Skipping test on legacy code for Pyppeteer in GitHub Actions as it fails with error'
                       'pyppeteer.errors.BrowserError: Browser closed unexpectedly')
        return
    if job_data.get('use_browser') and sys.version_info < (3, 7):
        logger.warning('Skipping test on legacy code for Pyppeteer as it does not capture ETags')
        return
    job = JobBase.unserialize(job_data)
    cache_storage = CacheDirStorage(os.path.join(here, 'data'))
    job_state = JobState(cache_storage, job)
    job.main_thread_enter()
    data, etag = job.retrieve(job_state)
    assert etag
    job.main_thread_exit()


@pytest.mark.parametrize('job_data', TEST_JOBS_ETAG)
def test_check_etag_304_request(job_data):
    if job_data.get('use_browser'):
        logger.warning('Skipping test on Pyppeteer since capturing of 304 codes is not implemented in Chromium 89')
        return

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


class ConfigForTest(BaseConfig):
    def __init__(self, config_file, urls_file, cache_file, hooks_file, verbose):
        super().__init__(__project_name__, here, config_file, urls_file, cache_file, hooks_file, verbose)
        self.edit = False
        self.edit_hooks = False


@py37_required
# Legacy code for Pyppeteer is not optimized for concurrency and fails in Github Actions with error
# pyppeteer.errors.BrowserError: Browser closed unexpectedly.
def test_stress_use_browser():
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
