"""Test running of jobs.
"""
import asyncio
import ftplib  # nosec: B402 A FTP-related module is being imported.
import logging
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml
from requests import HTTPError

from webchanges import __project_name__ as project_name
from webchanges.config import CommandConfig
from webchanges.handler import JobState
from webchanges.jobs import BrowserJob, BrowserResponseError, JobBase, NotModifiedError, ShellJob, UrlJob
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, YamlConfigStorage, YamlJobsStorage
from webchanges.worker import run_jobs

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
            'ignore_dh_key_too_small': True,
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
            'url': 'https://www.google.com/',
            'name': 'testing url job with use_browser and Playwright',
            'use_browser': True,
            'block_elements': ['stylesheet', 'font', 'image', 'media'],
            'cookies': {'X-test': '', 'X-test-2': ''},
            'headers': {'Accept-Language': 'en-US,en'},
            'ignore_https_errors': False,
            'switches': ['--window-size=1298,1406'],
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
            'name': 'testing POST url job with use_browser and Playwright',
            'use_browser': True,
            'data': {'fieldname': 'fieldvalue'},
        },
        '"data":"fieldname=fieldvalue"',
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
            'command': 'echo test echo command',
        },
        'test echo command',
    ),
]

TEST_ALL_URL_JOBS = [
    {},
    {'use_browser': True},
]


def test_kind() -> None:
    with pytest.raises(ValueError) as e:
        JobBase.unserialize({'kind': 'url'})
    assert e.value.args[0] == "Job 0: Required directive 'url' missing: '{'kind': 'url'}' (Job 0: )"

    with pytest.raises(ValueError) as e:
        JobBase.unserialize({'kind': 'anykind'})
    assert e.value.args[0] == (
        "Error in jobs file: Job directive 'kind: anykind' does not match any known job kinds:\nkind: anykind\n"
    )


def test__dict_deep__merge():
    job = JobBase.unserialize({'url': 'test'})
    assert JobBase._dict_deep_merge(job, {'a': {'b': 'c'}}, {'a': {'d': 'e'}}) == {'a': {'b': 'c', 'd': 'e'}}
    assert JobBase._dict_deep_merge(job, {'a': {'b': 'c'}}, {'a': {'b': 'e'}}) == {'a': {'b': 'c'}}
    assert JobBase._dict_deep_merge(job, {'a': {}}, {'a': {'b': 'c'}}) == {'a': {'b': 'c'}}
    assert JobBase._dict_deep_merge(job, {'a': 1}, {'b': 2}) == {'a': 1, 'b': 2}


@connection_required
@pytest.mark.parametrize(
    'input_job, output', TEST_JOBS, ids=(f'{type(JobBase.unserialize(v[0])).__name__}: {v[1]}' for v in TEST_JOBS)
)
def test_run_job(input_job: Dict[str, Any], output: str, caplog, event_loop) -> None:
    job = JobBase.unserialize(input_job)
    if sys.version_info < (3, 8) and job.use_browser:
        pytest.skip('Playwright testing requires Python 3.8')
        return

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
@pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout, EOFError, OSError))
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
@pytest.mark.parametrize(
    'job_data', TEST_ALL_URL_JOBS, ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS)
)
def test_check_etag(job_data: Dict[str, Any], event_loop) -> None:
    if sys.version_info < (3, 8) and job_data.get('use_browser'):
        pytest.skip('Playwright testing requires Python 3.8')
        return
    job_data['url'] = 'https://github.githubassets.com/images/search-key-slash.svg'
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        data, etag = job.retrieve(job_state)
        assert etag


@connection_required
@pytest.mark.parametrize(
    'job_data', TEST_ALL_URL_JOBS, ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS)
)
def test_check_etag_304_request(job_data: Dict[str, Any], event_loop) -> None:
    if sys.version_info < (3, 8) and job_data.get('use_browser'):
        pytest.skip('Playwright testing requires Python 3.8')
        return
    if job_data.get('use_browser'):
        pytest.skip('Capturing of 304 cannot be implemented in Chrome')  # last tested with Chromium 89
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
@pytest.mark.parametrize(
    'job_data', TEST_ALL_URL_JOBS, ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS)
)
def test_check_ignore_connection_errors_and_bad_proxy(job_data: Dict[str, Any], event_loop) -> None:
    if sys.version_info < (3, 8) and job_data.get('use_browser'):
        pytest.skip('Playwright testing requires Python 3.8')
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
    job_data['ignore_connection_errors'] = None


@connection_required
@pytest.mark.parametrize(
    'job_data', TEST_ALL_URL_JOBS, ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS)
)
def test_check_ignore_http_error_codes_and_error_message(job_data: Dict[str, Any], event_loop) -> None:
    if job_data.get('use_browser'):
        pytest.skip('Cannot debug due to Playwrigth/Windows bug')  # TODO Remove this and fix
    if sys.version_info < (3, 8) and job_data.get('use_browser'):
        pytest.skip('Playwright testing requires Python 3.8')
        return
    job_data['url'] = 'https://www.google.com/teapot'
    job_data['http_proxy'] = None
    job_data['timeout'] = 30
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        if isinstance(job_state.exception, HTTPError):
            assert job_state.exception.args[0] == (
                "418 Client Error: I'm a Teapot for url: https://www.google.com/teapot\n[](https://www.google.com/)\n"
                '**418.** I’m a teapot.\nThe requested entity body is short and stout. Tip me over and pour me out.'
            )
        elif isinstance(job_state.exception, BrowserResponseError):
            assert job_state.exception.status_code == 418
            assert (
                job_state.exception.args[0]
                == '418. I’m a teapot. The requested entity body is short and stout. Tip me over and pour me out.'
            )
        elif job_state.exception:
            pytest.fail(
                f'418 Teapot raised Exception type {type(job_state.exception)} (incorrect):\n{job_state.traceback}'
            )
        else:
            pytest.fail('No exception raised with 418 Teapot')
        assert job_state.error_ignored is False

    job_data['ignore_http_error_codes'] = [418]
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        assert job_state.error_ignored is True
    job_data['ignore_http_error_codes'] = None


@connection_required
@pytest.mark.parametrize(
    'job_data', TEST_ALL_URL_JOBS, ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS)
)
def test_http_error_message(job_data: Dict[str, Any], event_loop) -> None:
    if sys.version_info < (3, 8) and job_data.get('use_browser'):
        pytest.skip('Playwright testing requires Python 3.8')
        return
    jobs_file = data_path.joinpath('jobs-use_browser.yaml')
    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path('')
    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    urlwatch_config = CommandConfig([], project_name, here, config_file, jobs_file, hooks_file, cache_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)
    job_data['url'] = 'https://www.google.com/teapot'
    urlwatcher.jobs = [JobBase.unserialize(job_data)]

    run_jobs(urlwatcher)


@py38_required
@connection_required
def test_stress_use_browser(event_loop) -> None:
    jobs_file = data_path.joinpath('jobs-use_browser.yaml')
    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path('')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])

    if not os.getenv('GITHUB_ACTIONS'):
        from webchanges.cli import setup_logger

        setup_logger()

    urlwatch_config = CommandConfig([], project_name, here, config_file, jobs_file, hooks_file, cache_file)
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
        f"Error in jobs file: Job directive has no value or doesn't match a job type (check for errors/typos/escaping):"
        f'\n{yaml.safe_dump(job_data)}'
    )


def test_no_required_directive_plural() -> None:
    job_data = {'url_typo': 'this directive does not exist', 'timeout': '10'}
    with pytest.raises(ValueError) as pytest_wrapped_e:
        JobBase.unserialize(job_data)
    assert str(pytest_wrapped_e.value) == (
        f"Error in jobs file: Job directives (with values) don't match a job type (check for errors/typos/escaping):\n"
        f'{yaml.safe_dump(job_data)}'
    )


def test_invalid_directive() -> None:
    job_data = {'url': 'https://www.example.com', 'directive_with_typo': 'this directive does not exist'}
    with pytest.raises(ValueError) as pytest_wrapped_e:
        JobBase.unserialize(job_data)
    assert str(pytest_wrapped_e.value) == (
        "Directive 'directive_with_typo' is unrecognized in the following job\n"
        '   \n'
        '   ---\n'
        '   directive_with_typo: this directive does not exist\n'
        '   url: https://www.example.com\n'
        '   ---\n'
        '\n'
        '   Please check for typos.'
    )


def test_navigate_directive() -> None:
    job_data = {'navigate': 'http://www.example.com'}
    with pytest.deprecated_call() as pytest_wrapped_warning:
        JobBase.unserialize(job_data.copy())
    assert str(pytest_wrapped_warning.list[0].message) == (
        f"Error in jobs file: Job directive 'navigate' is deprecated: replace with 'url' and add 'use_browser: true':\n"
        f'{yaml.safe_dump(job_data)}'
    )


# def test_kind_directive_deprecation() -> None:
#     job_data = {'kind': 'url', 'url': 'http://www.example.com'}
#     with pytest.deprecated_call() as pytest_wrapped_warning:
#         JobBase.unserialize(job_data.copy())
#     assert str(pytest_wrapped_warning.list[0].message) == (
#         f"Job directive 'kind' is deprecated and ignored: delete from job ({job_data})"  # nosec: B608
#     )


def test_url_job_without_kind():
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, UrlJob)


def test_url_job_use_browser_false_without_kind():
    job_data = {'url': 'https://www.example.com', 'use_browser': False}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, UrlJob)


@py38_required
def test_browser_job_without_kind(event_loop):
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
    assert job.ignore_error(Exception()) is False


@py38_required
def test_browser_switches_not_str_or_list(event_loop):
    job_data = {
        'url': 'https://www.example.com',
        'use_browser': True,
        'switches': {'dict key': ''},
    }
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, TypeError)


# @py38_required
# def test_browser_block_elements_not_str_or_list(event_loop):
#     job_data = {
#         'url': 'https://www.example.com',
#         'use_browser': True,
#         'block_elements': {'dict key': ''},
#     }
#     job = JobBase.unserialize(job_data)
#     with JobState(cache_storage, job) as job_state:
#         job_state.process()
#         assert isinstance(job_state.exception, TypeError)
#
#
# @py38_required
# def test_browser_block_elements_invalid(event_loop):
#     job_data = {
#         'url': 'https://www.example.com',
#         'use_browser': True,
#         'block_elements': ['fake element'],
#     }
#     job = JobBase.unserialize(job_data)
#     with JobState(cache_storage, job) as job_state:
#         job_state.process()
#         assert isinstance(job_state.exception, ValueError)


def test_shell_error():
    job_data = {'command': 'this_command_does_not_exist'}
    job = JobBase.unserialize(job_data)
    with JobState(cache_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, subprocess.CalledProcessError)


def test_compared_versions():

    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path('')
    jobs_file = data_path.joinpath('jobs-time.yaml')
    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    urlwatch_config = CommandConfig([], '', here, config_file, jobs_file, hooks_file, cache_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)

    # compared_versions = 2
    urlwatcher.jobs[0].command = 'python3 -c "import random; print(random.randint(0, 1))"'
    urlwatcher.jobs[0].compared_versions = 2
    results = set()
    for i in range(20):
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        if urlwatcher.report.job_states[-1].new_data in results:
            assert urlwatcher.report.job_states[-1].verb == 'unchanged'
        else:
            results.add(urlwatcher.report.job_states[-1].new_data)
            assert urlwatcher.report.job_states[-1].verb in ('new', 'changed')

    # compared_versions = 3  (may trigger fuzzy match search)
    cache_storage.flushdb()
    urlwatcher.jobs[0].command = 'python3 -c "import random; print(random.randint(0, 2))"'
    urlwatcher.jobs[0].compared_versions = 3
    results = set()
    for i in range(20):
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        if urlwatcher.report.job_states[-1].new_data in results:
            assert urlwatcher.report.job_states[-1].verb == 'unchanged'
        else:
            results.add(urlwatcher.report.job_states[-1].new_data)
            assert urlwatcher.report.job_states[-1].verb in ('new', 'changed')
    print(0)
