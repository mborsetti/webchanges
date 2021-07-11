"""Test running of jobs"""
import ftplib  # nosec: B402 A FTP-related module is being imported.
import logging
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict

from pyppeteer.chromium_downloader import current_platform

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

logger = logging.getLogger(__name__)

here = Path(__file__).parent
data_dir = here.joinpath('data')
cache_file = ':memory:'
cache_storage = CacheSQLite3Storage(cache_file)


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
# py37_required = pytest.mark.skipif(sys.version_info < (3, 7), reason='requires Python 3.7')

chromium_revision_num = DEFAULT_CHROMIUM_REVISION[current_platform()]
TEST_JOBS = [
    (
        {
            'url': 'https://www.google.com/#a',
            'note': 'Google with no name (grab title)',
            'cookies': {'X-test': ''},
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
            'user_visible_url': 'https://www.google.com/#a_visible',
        },
        'Google',
    ),
    (
        {
            'url': 'http://www.google.com/#b',
            'name': 'testing url job with use_browser',
            'use_browser': True,
            'block_elements': ['stylesheet', 'font', 'image', 'media'],
            'chromium_revision': chromium_revision_num,
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
        'Google',
    ),
    (
        {
            'url': 'https://postman-echo.com/post',
            'name': 'testing POST job without use_browser',
            'data': {'fieldname': 'fieldvalue'},
        },
        '"json":{"fieldname":"fieldvalue"}',
    ),
    (
        {
            'url': 'https://postman-echo.com/post',
            'name': 'testing POST job with use_browser',
            'use_browser': True,
            'data': {'fieldname': 'fieldvalue'},
        },
        '"json":{"fieldname":"fieldvalue"}',
    ),
    (
        {
            'url': data_dir.joinpath('file-test.txt').as_uri(),
        },
        'This is text\n',
    ),
    (
        {
            'url': data_dir.joinpath('file-test.txt').as_uri(),
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

TEST_ALL_URL_JOBS = [{}, {'use_browser': True}]


@connection_required
@pytest.mark.parametrize('input_job, output', TEST_JOBS)
def test_run_job(input_job: Dict[str, Any], output: str) -> None:
    job = JobBase.unserialize(input_job)
    job_state = JobState(cache_storage, job)
    job.main_thread_enter()
    data, etag = job.retrieve(job_state)
    if job.filter == [{'pdf2text': {}}]:
        assert isinstance(data, bytes)
    assert output in data
    job.main_thread_exit()


@connection_required
@pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout, socket.gaierror))
def test_run_ftp_job() -> None:
    job = JobBase.unserialize({'url': 'ftp://tgftp.nws.noaa.gov/logmsg.txt', 'timeout': 2})
    job_state = JobState(cache_storage, job)
    job.main_thread_enter()
    data, etag = job.retrieve(job_state)
    assert len(data) == 319
    job.main_thread_exit()


@connection_required
@pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout))
def test_run_ftp_job_needs_bytes() -> None:
    job = JobBase.unserialize({'url': 'ftp://speedtest.tele2.net/1KB.zip', 'timeout': 2, 'filter': [{'pdf2text': {}}]})
    job_state = JobState(cache_storage, job)
    job.main_thread_enter()
    data, etag = job.retrieve(job_state)
    assert isinstance(data, bytes)
    assert len(data) == 1024
    job.main_thread_exit()


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_etag(job_data: Dict[str, Any]) -> None:
    job_data['url'] = 'https://github.githubassets.com/images/search-key-slash.svg'
    job = JobBase.unserialize(job_data)
    job_state = JobState(cache_storage, job)
    job.main_thread_enter()
    data, etag = job.retrieve(job_state)
    assert etag
    job.main_thread_exit()


@connection_required
@pytest.mark.parametrize('job_data', TEST_ALL_URL_JOBS)
def test_check_etag_304_request(job_data: Dict[str, Any]) -> None:
    if job_data.get('use_browser'):
        logger.warning(
            f'Skipping test {sys._getframe().f_code.co_name} on Pyppeteer since capturing of 304 cannot be '
            f'implemented in Chromium'  # last tested with Chromium 89
        )
        return

    job_data['url'] = 'https://github.githubassets.com/images/search-key-slash.svg'
    job = JobBase.unserialize(job_data)
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
        logger.warning(
            f'Skipping test {sys._getframe().f_code.co_name} on Pyppeteer since it times out after 90 ' f'seconds or so'
        )
        return

    job_data['url'] = 'http://connectivitycheck.gstatic.com/generate_204'
    job_data['http_proxy'] = 'http://notworking:ever@google.com:8080'
    job_data['timeout'] = 0.001
    job = JobBase.unserialize(job_data)
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
    job_data['url'] = 'https://www.google.com/teapot'
    job_data['timeout'] = 30
    job = JobBase.unserialize(job_data)
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


@connection_required
# @py37_required
# Legacy code for Pyppeteer is not optimized for concurrency and fails in Github Actions with error
# pyppeteer.errors.BrowserError: Browser closed unexpectedly.
def test_stress_use_browser() -> None:
    jobs_file = data_dir.joinpath('jobs-use_browser.yaml')
    config_file = data_dir.joinpath('config.yaml')
    hooks_file = Path('')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage(jobs_file)

    if not os.getenv('GITHUB_ACTIONS'):
        from webchanges.cli import setup_logger_verbose

        setup_logger_verbose()

    urlwatch_config = CommandConfig(project_name, here, config_file, jobs_file, hooks_file, cache_file, True)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)
    urlwatcher.run_jobs()


def test_shell_exception_and_with_defaults() -> None:
    job_data = {'command': 'this_command_does_not_exist'}
    job = JobBase.unserialize(job_data)
    job_state = JobState(cache_storage, job)
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


def test_browser_job_without_kind():
    job_data = {'url': 'https://www.example.com', 'use_browser': True}
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


# @py37_required
def test_browser_switches_not_str_or_list():
    job_data = {'url': 'https://www.example.com', 'use_browser': True, 'switches': {'dict key': ''}}
    job = JobBase.unserialize(job_data)
    job_state = JobState(cache_storage, job)
    job_state.process()
    assert isinstance(job_state.exception, TypeError)


# @py37_required
def test_browser_block_elements_not_str_or_list():
    job_data = {'url': 'https://www.example.com', 'use_browser': True, 'block_elements': {'dict key': ''}}
    job = JobBase.unserialize(job_data)
    job_state = JobState(cache_storage, job)
    job_state.process()
    print('job_state.exception', job_state.exception)
    assert isinstance(job_state.exception, TypeError)


# @py37_required
def test_browser_block_elements_invalid():
    job_data = {'url': 'https://www.example.com', 'use_browser': True, 'block_elements': ['fake element']}
    job = JobBase.unserialize(job_data)
    job_state = JobState(cache_storage, job)
    job_state.process()
    assert isinstance(job_state.exception, ValueError)


def test_shell_error():
    job_data = {'command': 'this_command_does_not_exist'}
    job = JobBase.unserialize(job_data)
    job_state = JobState(cache_storage, job)
    job_state.process()
    assert isinstance(job_state.exception, ShellError)
