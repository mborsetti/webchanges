"""Test running of jobs.

Note: for '-use_browser: true' jobs, using the --disable-dev-shm-usage switch as per
https://playwright.dev/python/docs/ci#docker since GitHub Actions runs the tests in a Docker container.
"""
import asyncio
import ftplib  # nosec: B402 A FTP-related module is being imported.
import importlib.util
import logging
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from webchanges import __project_name__ as project_name
from webchanges.config import CommandConfig
from webchanges.handler import JobState
from webchanges.jobs import (
    BrowserJob,
    BrowserResponseError,
    DEFAULT_CHROMIUM_REVISION,
    JobBase,
    NotModifiedError,
    ShellError,
    ShellJob,
    UrlJob,
)
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, YamlConfigStorage, YamlJobsStorage

try:
    from pyppeteer.chromium_downloader import current_platform

    chromium_revision_num = DEFAULT_CHROMIUM_REVISION[current_platform()]
except ImportError:
    current_platform = None
    chromium_revision_num = None

logger = logging.getLogger(__name__)

here = Path(__file__).parent
data_path = here.joinpath('data')
cache_file = ':memory:'
cache_storage = CacheSQLite3Storage(cache_file)

if sys.version_info[0:2] < (3, 8) and sys.platform == 'win32':
    # https://docs.python.org/3/library/asyncio-platforms.html#asyncio-windows-subprocess
    loop = asyncio.ProactorEventLoop()

    @pytest.fixture
    def event_loop():
        return loop


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
py38_required = pytest.mark.skipif(sys.version_info < (3, 8), reason='requires Python 3.8')
py310_skip = pytest.mark.skipif(sys.version_info >= (3, 10), reason='Python 3.10 not supported by pyppeteer')
playwright_is_installed = (
    importlib.util.find_spec('playwright') is not None and importlib.util.find_spec('psutil') is not None
)
playwright_skip = pytest.mark.skipif(not playwright_is_installed, reason='Playwright and psutil are not installed')

TEST_JOBS = [
    (
        {
            'url': 'https://www.google.com/',
            'note': 'Google with no name (grab title)',
            'cookies': {'X-test': 'test'},
            'encoding': 'ascii',
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/90.0.4430.93 Safari/537.36'
            },
            'ignore_cached': True,
            'ignore_connection_errors': False,
            'ignore_http_error_codes': 200,
            'ignore_timeout_errors': False,
            'ignore_too_many_redirects': False,
            'method': 'GET',
            'no_redirects': False,
            'ssl_no_verify': False,
            'timeout': 0,
            'user_visible_url': 'https://www.google.com/',
        },
        'Google',
    ),
    (
        {
            'url': 'http://www.google.com/',
            'name': 'testing url job with use_browser',
            'use_browser': True,
            'block_elements': ['stylesheet', 'font', 'image', 'media'],
            'chromium_revision': chromium_revision_num,
            'cookies': {'X-test': 'test'},
            'headers': {'Accept-Language': 'en-US,en'},
            'ignore_https_errors': False,
            'switches': ['--window-size=1298,1406', '--disable-dev-shm-usage'],
            'timeout': 15,
            'user_visible_url': 'https://www.google.com/',
            'wait_for': 1,
            'wait_for_navigation': 'https://www.google.com/',
            'wait_until': 'load',
        },
        'Google',
    ),
    (
        {
            'url': 'https://www.google.com/',
            'name': 'testing url job with use_browser and Playwright',
            '_beta_use_playwright': True,
            'use_browser': True,
            'block_elements': ['stylesheet', 'font', 'image', 'media'],
            'cookies': {'X-test': '', 'X-test-2': ''},
            'headers': {'Accept-Language': 'en-US,en'},
            'ignore_https_errors': False,
            'switches': ['--window-size=1298,1406', '--disable-dev-shm-usage'],
            'timeout': 15,
            'user_visible_url': 'https://www.google.com/',
            'wait_for_navigation': 'https://www.google.com/',
            'wait_until': 'load',
        },
        'Google',
    ),
    (
        {
            'url': 'https://postman-echo.com/post',
            'name': 'testing POST url job without use_browser',
            'data': {'fieldname': 'fieldvalue'},
        },
        '"json":{"fieldname":"fieldvalue"}',
    ),
    (
        {
            'url': 'https://postman-echo.com/post',
            'name': 'testing POST url job with use_browser',
            'use_browser': True,
            'switches': ['--disable-dev-shm-usage'],
            'data': {'fieldname': 'fieldvalue'},
        },
        '"json":{"fieldname":"fieldvalue"}',
    ),
    (
        {
            'url': 'https://postman-echo.com/post',
            'name': 'testing POST url job with use_browser and Playwright',
            '_beta_use_playwright': True,
            'use_browser': True,
            'switches': ['--disable-dev-shm-usage'],
            'data': {'fieldname': 'fieldvalue'},
        },
        '"json":{"fieldname":"fieldvalue"}',
    ),
    (
        {
            'url': data_path.joinpath('file-test.txt').as_uri(),
        },
        'This is text\n',
    ),
    (
        {
            'url': data_path.joinpath('file-test.txt').as_uri(),
            'filter': [{'pdf2text': {}}],
        },
        b'This is text\n',
    ),
    (
        {
            'command': 'echo test',
        },
        'test',
    ),
]

TEST_ALL_URL_JOBS = [
    {},
    {'use_browser': True, 'switches': ['--disable-dev-shm-usage']},
    {'use_browser': True, 'switches': ['--disable-dev-shm-usage'], '_beta_use_playwright': True},
]


@connection_required
@pytest.mark.parametrize('input_job, output', TEST_JOBS)
def test_run_job(input_job: Dict[str, Any], output: str, caplog, event_loop) -> None:
    job = JobBase.unserialize(input_job)
    if current_platform is None and job.use_browser and not job._beta_use_playwright:
        pytest.skip('Pyppeteer not installed')
        return
    elif not playwright_is_installed and job.use_browser and job._beta_use_playwright:
        pytest.skip('Playwright and psutil not installed')
        return
    elif sys.version_info < (3, 8) and job.use_browser and job._beta_use_playwright:
        pytest.skip('Playwright testing requires Python 3.8')
        return
    # if sys.version_info == (3, 7) and job.use_browser and not job._beta_use_playwright and sys.platform == 'linux':
    #     pytest.skip('Pyppeteer throws "Page crashed!" errors in Python 3.7 in Ubuntu')
    #     return
    if sys.version_info >= (3, 10):
        caplog.set_level(logging.DEBUG)
        if job.use_browser and not job._beta_use_playwright:
            pytest.skip('Pyppeteer freezes in Python 3.10')
            return
    # if (
    #     input_job
    #     == {
    #         'url': 'https://postman-echo.com/post',
    #         'name': 'testing POST url job with use_browser and Playwright',
    #         '_beta_use_playwright': True,
    #         'use_browser': True,
    #         'switches': ['--disable-dev-shm-usage'],
    #         'data': {'fieldname': 'fieldvalue'},
    #     }
    #     and sys.platform == 'linux'
    # ):
    #     pytest.skip('Triggers exit code 141 on Ubuntu in GitHub Actions')
    #     return

    with JobState(cache_storage, job) as job_state:
        data, etag = job.retrieve(job_state)
        if job.filter == [{'pdf2text': {}}]:
            assert isinstance(data, bytes)
        assert output in data


@connection_required
@pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout, socket.gaierror))
def test_run_ftp_job() -> None:
    job = JobBase.unserialize({'url': 'ftp://tgftp.nws.noaa.gov/logmsg.txt', 'timeout': 2})
    with JobState(cache_storage, job) as job_state:
        data, etag = job.retrieve(job_state)
        assert len(data) == 319


@connection_required
@pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout))
def test_run_ftp_job_needs_bytes() -> None:
    if os.getenv('GITHUB_ACTIONS'):
        pytest.skip('Test website cannot be reached from GitHub Actions')
        return
    job = JobBase.unserialize({'url': 'ftp://speedtest.tele2.net/1KB.zip', 'timeout': 2, 'filter': [{'pdf2text': {}}]})
    with JobState(cache_storage, job) as job_state:
        data, etag = job.retrieve(job_state)
        assert isinstance(data, bytes)
        assert len(data) == 1024


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_etag(job_data: Dict[str, Any], event_loop) -> None:
    if current_platform is None and job_data.get('use_browser') and not job_data.get('_beta_use_playwright'):
        pytest.skip('Pyppeteer not installed')
        return
    elif not playwright_is_installed and job_data.get('use_browser') and job_data.get('_beta_use_playwright'):
        pytest.skip('Playwright and psutil not installed')
        return
    if sys.version_info >= (3, 10):
        if job_data.get('use_browser') and not job_data.get('_beta_use_playwright'):
            pytest.skip('Pyppeteer freezes in Python 3.10')
            return
    job_data['url'] = 'https://github.githubassets.com/images/search-key-slash.svg'
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        data, etag = job.retrieve(job_state)
        assert etag


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_etag_304_request(job_data: Dict[str, Any], event_loop) -> None:
    if current_platform is None and (job_data.get('use_browser') and not job_data.get('_beta_use_playwright')):
        pytest.skip('Pyppeteer not installed')
        return
    elif sys.version_info < (3, 8) and job_data.get('use_browser') and job_data.get('_beta_use_playwright'):
        pytest.skip('Playwright testing requires Python 3.8')
        return
    elif sys.version_info >= (3, 10) and job_data.get('use_browser') and not job_data.get('_beta_use_playwright'):
        pytest.skip('Pyppeteer freezes in Python 3.10')
        return
    if job_data.get('use_browser'):
        pytest.skip('Capturing of 304 cannot be implemented in Chromium')  # last tested with Chromium 89
        return

    job_data['url'] = 'https://github.githubassets.com/images/search-key-slash.svg'
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job.index_number = 1
        data, etag = job.retrieve(job_state)
        job_state.old_etag = etag

        job.index_number = 2
        with pytest.raises(NotModifiedError) as pytest_wrapped_e:
            job.retrieve(job_state)

        assert str(pytest_wrapped_e.value) == '304'


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_ignore_connection_errors_and_bad_proxy(job_data: Dict[str, Any], event_loop) -> None:
    if current_platform is None and job_data.get('use_browser') and not job_data.get('_beta_use_playwright'):
        pytest.skip('Pyppeteer not installed')
        return
    elif sys.version_info < (3, 8) and job_data.get('use_browser') and job_data.get('_beta_use_playwright'):
        pytest.skip('Playwright testing requires Python 3.8')
        return
    if sys.version_info >= (3, 10) and job_data.get('use_browser') and not job_data.get('_beta_use_playwright'):
        pytest.skip('Pyppeteer freezes in Python 3.10')
        return
    if job_data.get('use_browser') and not job_data.get('_beta_use_playwright'):
        pytest.skip('Pyppeteer times out after 90 seconds or so')
        return
    job_data['url'] = 'http://connectivitycheck.gstatic.com/generate_204'
    job_data['http_proxy'] = 'http://notworking:ever@google.com:8080'
    job_data['timeout'] = 0.001
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        if not isinstance(job_state.exception, BrowserResponseError):
            assert sum(
                list(x in str(job_state.exception.args) for x in ('Max retries exceeded', 'Timeout 1ms exceeded.'))
            )
        assert job_state.error_ignored is False

    job_data['ignore_connection_errors'] = True
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        assert job_state.error_ignored is True


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_ignore_http_error_codes(job_data: Dict[str, Any], event_loop) -> None:
    if current_platform is None and job_data.get('use_browser') and not job_data.get('_beta_use_playwright'):
        pytest.skip('Pyppeteer not installed')
        return
    elif not playwright_is_installed and job_data.get('use_browser') and job_data.get('_beta_use_playwright'):
        pytest.skip('Playwright and psutil not installed')
        return
    elif sys.version_info < (3, 8) and job_data.get('use_browser') and job_data.get('_beta_use_playwright'):
        pytest.skip('Playwright testing requires Python 3.8')
        return
    if sys.version_info >= (3, 10) and job_data.get('use_browser') and not job_data.get('_beta_use_playwright'):
        pytest.skip('Pyppeteer freezes in Python 3.10')
        return
    job_data['url'] = 'https://www.google.com/teapot'
    job_data['http_proxy'] = None
    job_data['timeout'] = 30
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        if isinstance(job_state.exception, BrowserResponseError):
            assert job_state.exception.status_code == 418
        else:
            assert '418' in str(job_state.exception.args)
        assert job_state.error_ignored is False

    job_data['ignore_http_error_codes'] = [418]
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        assert job_state.error_ignored is True


@py310_skip
@connection_required
# Legacy code for Pyppeteer is not optimized for concurrency and fails in Github Actions with error
# pyppeteer.errors.BrowserError: Browser closed unexpectedly.
def test_stress_use_browser() -> None:
    jobs_file = data_path.joinpath('jobs-use_browser.yaml')
    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path('')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage(jobs_file)

    if not os.getenv('GITHUB_ACTIONS'):
        from webchanges.cli import setup_logger

        setup_logger()

    urlwatch_config = CommandConfig(project_name, here, config_file, jobs_file, hooks_file, cache_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)
    urlwatcher.run_jobs()


@py38_required
@playwright_skip
@connection_required
def test_stress_use_browser_playwright(event_loop) -> None:
    jobs_file = data_path.joinpath('jobs-use_browser_pw.yaml')
    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path('')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage(jobs_file)

    if not os.getenv('GITHUB_ACTIONS'):
        from webchanges.cli import setup_logger

        setup_logger()

    urlwatch_config = CommandConfig(project_name, here, config_file, jobs_file, hooks_file, cache_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)
    urlwatcher.run_jobs()


def test_shell_exception_and_with_defaults() -> None:
    job_data = {'command': 'this_command_does_not_exist'}
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, Exception)
        assert str(job_state.exception)


def test_no_required_directive() -> None:
    job_data = {'url_typo': 'this directive does not exist'}
    with pytest.raises(ValueError) as pytest_wrapped_e:
        JobBase.unserialize(job_data)
    assert str(pytest_wrapped_e.value) == (
        f"Job directive has no value or doesn't match a job type; check for errors/typos/escaping:\n{job_data}"
    )


def test_no_required_directive_plural() -> None:
    job_data = {'url_typo': 'this directive does not exist', 'timeout': '10'}
    with pytest.raises(ValueError) as pytest_wrapped_e:
        JobBase.unserialize(job_data)
    assert str(pytest_wrapped_e.value) == (
        f"Job directives (with values) don't match a job type; check for errors/typos/escaping:\n{job_data}"
    )


def test_invalid_directive() -> None:
    job_data = {'url': 'https://www.example.com', 'directive_with_typo': 'this directive does not exist'}
    with pytest.raises(ValueError) as pytest_wrapped_e:
        JobBase.unserialize(job_data)
    assert str(pytest_wrapped_e.value) == (
        f"Job directive 'directive_with_typo' is unrecognized; check for errors/typos/escaping:\n{job_data}"
    )


def test_navigate_directive() -> None:
    job_data = {'navigate': 'http://www.example.com'}
    with pytest.deprecated_call() as pytest_wrapped_warning:
        JobBase.unserialize(job_data.copy())
    assert str(pytest_wrapped_warning.list[0].message) == (
        f"Job directive 'navigate' is deprecated: replace with 'url' and add 'use_browser: true' ({job_data})"
    )


def test_kind_directive_deprecation() -> None:
    job_data = {'kind': 'url', 'url': 'http://www.example.com'}
    with pytest.deprecated_call() as pytest_wrapped_warning:
        JobBase.unserialize(job_data.copy())
    assert str(pytest_wrapped_warning.list[0].message) == (
        f"Job directive 'kind' is deprecated and ignored: delete from job ({job_data})"  # nosec: B608
    )


def test_url_job_without_kind():
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, UrlJob)


def test_url_job_use_browser_false_without_kind():
    job_data = {'url': 'https://www.example.com', 'use_browser': False}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, UrlJob)


@py310_skip
def test_browser_job_without_kind():
    job_data = {'url': 'https://www.example.com', 'use_browser': True, 'switches': ['--disable-dev-shm-usage']}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, BrowserJob)


def test_browser_job_playwright_without_kind():
    job_data = {
        'url': 'https://www.example.com',
        'use_browser': True,
        'switches': ['--disable-dev-shm-usage'],
        '_beta_use_playwright': True,
    }
    job = JobBase.unserialize(job_data)
    assert isinstance(job, BrowserJob)


def test_shell_job_without_kind():
    job_data = {'command': 'ls'}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, ShellJob)


def test_with_defaults():
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    config = {'job_defaults': {'all': {'timeout': 999}}}
    job = job.with_defaults(config)
    assert job.timeout == 999
    assert job.get_indexed_location() == 'Job 0: https://www.example.com'


def test_ignore_error():
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    assert job.ignore_error(Exception) is False


@py310_skip
def test_browser_switches_not_str_or_list():
    if current_platform:
        job_data = {
            'url': 'https://www.example.com',
            'use_browser': True,
            'switches': {'dict key': ''},
        }
        job = JobBase.unserialize(job_data)
        with JobState(cache_storage, job) as job_state:
            job_state.process()
            assert isinstance(job_state.exception, TypeError)
    else:
        pytest.skip('Pyppeteer not installed')


@py38_required
@playwright_skip
def test_browser_switches_not_str_or_list_playwright(event_loop):
    job_data = {
        'url': 'https://www.example.com',
        'use_browser': True,
        '_beta_use_playwright': True,
        'switches': {'dict key': ''},
    }
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, TypeError)


@py310_skip
def test_browser_block_elements_not_str_or_list():
    if current_platform:
        job_data = {
            'url': 'https://www.example.com',
            'use_browser': True,
            'block_elements': {'dict key': ''},
        }
        job = JobBase.unserialize(job_data)
        with JobState(cache_storage, job) as job_state:
            job_state.process()
            assert isinstance(job_state.exception, TypeError)
    else:
        pytest.skip('Pyppeteer not installed')


@py310_skip
def test_browser_block_elements_invalid():
    if current_platform:
        job_data = {
            'url': 'https://www.example.com',
            'use_browser': True,
            'block_elements': ['fake element'],
        }
        job = JobBase.unserialize(job_data)
        with JobState(cache_storage, job) as job_state:
            job_state.process()
            assert isinstance(job_state.exception, ValueError)
    else:
        pytest.skip('Pyppeteer not installed')


def test_shell_error():
    job_data = {'command': 'this_command_does_not_exist'}
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, ShellError)
