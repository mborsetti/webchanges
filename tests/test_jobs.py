"""Test running of jobs.
"""

from __future__ import annotations

import ftplib  # noqa: S402 A FTP-related module is being imported.
import importlib.util
import os
import socket
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.
import sys
from pathlib import Path
from typing import Any, Callable, cast

import pytest
import yaml
from _pytest.logging import LogCaptureFixture
from httpx import HTTPStatusError
from requests import HTTPError

from webchanges.config import CommandConfig
from webchanges.handler import JobState
from webchanges.jobs import BrowserJob, BrowserResponseError, JobBase, NotModifiedError, ShellJob, UrlJob
from webchanges.main import Urlwatch
from webchanges.storage import _Config, SsdbSQLite3Storage, YamlConfigStorage, YamlJobsStorage

here = Path(__file__).parent
data_path = here.joinpath('data')
ssdb_file = ':memory:'
ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # type: ignore[arg-type]


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


connection_required = cast(
    Callable[[Callable], Callable], pytest.mark.skipif(not is_connected(), reason='no Internet connection')
)

py_latest_only = cast(
    Callable[[Callable], Callable],
    pytest.mark.skipif(
        sys.version_info < (3, 13),
        reason='Time consuming; testing latest version only',
    ),
)

TEST_JOBS = [
    (
        {
            'url': 'https://www.google.com/',
            'note': 'Google with no name (grab title)',
            'cookies': {'X-test': 'test'},
            'encoding': 'ascii',
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/118.0.0.0 Safari/537.36'
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
            'init_script': "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });",
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
        '  "json": {\n    "fieldname": "fieldvalue"\n  },',
    ),
    (
        {
            'url': 'https://postman-echo.com/post',
            'name': 'testing POST url job with use_browser and Playwright',
            'use_browser': True,
            'data': {'fieldname': 'fieldvalue'},
        },
        '"data": "fieldname=fieldvalue"',
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
TEST_ALL_URL_JOBS: list[dict[str, str | bool]] = [
    {},
    {'use_browser': True},
]
if importlib.util.find_spec('requests') is not None:
    TEST_ALL_URL_JOBS.append({'http_client': 'requests'})


def new_command_config(config_file: Path, jobs_file: Path, hooks_file: Path) -> CommandConfig:
    """Create a new command config.

    :param config_file: The location of the config file.
    :param jobs_file: The location of the jobs file.
    :param hooks_file: The location of the hooks file.
    :return: The CommandConfig.
    """
    return CommandConfig(
        args=[],
        config_path=here,
        config_file=config_file,
        jobs_def_file=jobs_file,
        hooks_def_file=hooks_file,
        ssdb_file=ssdb_file,  # type: ignore[arg-type]
    )


def test_kind() -> None:
    with pytest.raises(ValueError) as e:
        JobBase.unserialize({'kind': 'url'})
    assert e.value.args[0] == "Job None: Required directive 'url' missing: '{'kind': 'url'}' (None)"

    with pytest.raises(ValueError) as e:
        JobBase.unserialize({'kind': 'anykind'})
    assert e.value.args[0] == (
        "Error in jobs file: Job directive 'kind: anykind' does not match any known job kinds:\nkind: anykind\n"
    )


def test__dict_deep__merge() -> None:
    job = JobBase.unserialize({'url': 'test'})
    assert JobBase._dict_deep_merge(job, {'a': {'b': 'c'}}, {'a': {'d': 'e'}}) == {'a': {'b': 'c', 'd': 'e'}}
    assert JobBase._dict_deep_merge(job, {'a': {'b': 'c'}}, {'a': {'b': 'e'}}) == {'a': {'b': 'c'}}
    assert JobBase._dict_deep_merge(job, {'a': {}}, {'a': {'b': 'c'}}) == {'a': {'b': 'c'}}
    assert JobBase._dict_deep_merge(job, {'a': 1}, {'b': 2}) == {'a': 1, 'b': 2}


@connection_required  # type: ignore[misc]
@pytest.mark.parametrize(  # type: ignore[misc]
    'input_job, output',
    TEST_JOBS,
    ids=(f'{type(JobBase.unserialize(v[0])).__name__}: {v[1]}' for v in TEST_JOBS),  # type: ignore[arg-type]
)
def test_run_job(
    input_job: dict[str, str | dict[str, str] | bool | int],
    output: str,
    caplog: LogCaptureFixture,
) -> None:
    job = JobBase.unserialize(input_job)
    with JobState(ssdb_storage, job) as job_state:
        data, etag, mime_type = job.retrieve(job_state)
        if job.filter == [{'pdf2text': {}}]:
            assert isinstance(data, bytes)
        assert output in data


@connection_required  # type: ignore[misc]
@pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout, socket.gaierror))  # type: ignore[misc]
def test_run_ftp_job() -> None:
    job = JobBase.unserialize({'url': 'ftp://tgftp.nws.noaa.gov/logmsg.txt', 'timeout': 2})
    with JobState(ssdb_storage, job) as job_state:
        data, etag, mime_type = job.retrieve(job_state)
        assert len(data) == 319


# @connection_required  # type: ignore[misc]
# @pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout, EOFError, OSError))  # type: ignore[misc]
# def test_run_ftp_job_needs_bytes() -> None:
#     if os.getenv('GITHUB_ACTIONS'):
#         pytest.skip('Test website cannot be reached from GitHub Actions')
#
#     job = JobBase.unserialize(
#         {'url': 'ftp://speedtest.tele2.net/1KB.zip', 'timeout': 2, 'filter': [{'pdf2text': {}}]}
#     )
#     with JobState(ssdb_storage, job) as job_state:
#         data, etag, mime_type = job.retrieve(job_state)
#         assert isinstance(data, bytes)
#         assert len(data) == 1024


@connection_required  # type: ignore[misc]
@pytest.mark.parametrize(  # type: ignore[arg-type,misc]
    'job_data',
    TEST_ALL_URL_JOBS,
    ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS),  # type: ignore[attr-defined]
)
def test_check_etag(job_data: dict[str, Any]) -> None:
    job_data['url'] = 'https://github.githubassets.com/assets/discussions-1958717f4567.css'
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        data, etag, mime_type = job.retrieve(job_state)
        assert etag


@connection_required  # type: ignore[misc]
@pytest.mark.parametrize(  # type: ignore[arg-type,misc]
    'job_data',
    TEST_ALL_URL_JOBS,
    ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS),  # type: ignore[attr-defined]
)
def test_check_etag_304_request(job_data: dict[str, Any], doctest_namespace: dict) -> None:
    """Check for 304 Not Modified response."""
    if job_data.get('use_browser'):
        pytest.skip('Capturing of 304 cannot be implemented in Chrome')  # last tested with Chromium 89
    job_data['url'] = 'https://github.githubassets.com/assets/discussions-1958717f4567.css'
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        if 'check__etag_304_etag' not in doctest_namespace:
            job.index_number = 1
            data, etag, mime_type = job.retrieve(job_state)
            doctest_namespace['check_etag_304_etag'] = etag
            doctest_namespace['check_etag_304_timestamp'] = job_state.old_timestamp

        job_state.old_etag = doctest_namespace['check_etag_304_etag']
        job_state.old_timestamp = doctest_namespace['check_etag_304_timestamp']
        job.index_number = 2
        with pytest.raises(NotModifiedError) as pytest_wrapped_e:
            job.retrieve(job_state)

        assert str(pytest_wrapped_e.value) == '304'


@connection_required  # type: ignore[misc]
@pytest.mark.parametrize(  # type: ignore[arg-type,misc]
    'job_data',
    TEST_ALL_URL_JOBS,
    ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS),  # type: ignore[attr-defined]
)
def test_check_ignore_connection_errors(job_data: dict[str, Any]) -> None:
    job_data['url'] = 'http://localhost'
    job_data['timeout'] = 0.0001
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        assert job_state.exception and any(
            x in str(job_state.exception.args)
            for x in {'Max retries exceeded', 'Timeout 0.1ms exceeded.', 'timed out', 'Connection refused'}
        )
        assert getattr(job_state, 'error_ignored', False) is False

    job_data['ignore_connection_errors'] = True
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        assert job_state.error_ignored is True
        # also check that it's using the correct HTTP client library
        if not job_data.get('use_browser'):
            assert job_state._http_client_used == job_data.get('http_client', 'HTTPX')
    job_data['ignore_connection_errors'] = None


@connection_required  # type: ignore[misc]
@pytest.mark.parametrize(  # type: ignore[arg-type,misc]
    'job_data',
    TEST_ALL_URL_JOBS,
    ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS),  # type: ignore[attr-defined]
)
def test_check_bad_proxy(job_data: dict[str, Any]) -> None:
    job_data['url'] = 'http://connectivitycheck.gstatic.com/generate_204'
    job_data['http_proxy'] = 'http://notworking:ever@localhost:8080'
    job_data['timeout'] = 0.0001
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        if job_state.exception and not isinstance(job_state.exception, BrowserResponseError):
            assert job_state.exception and any(
                x in str(job_state.exception.args)
                for x in {
                    'Max retries exceeded',
                    'Read timed out',
                    'Timeout 0.1ms exceeded.',
                    'timed out',
                    'Connection refused',
                }
            )
        assert job_state.error_ignored is False


@connection_required  # type: ignore[misc]
@pytest.mark.parametrize(  # type: ignore[arg-type,misc]
    'job_data',
    TEST_ALL_URL_JOBS,
    ids=('BrowserJob' if v.get('use_browser') else 'UrlJob' for v in TEST_ALL_URL_JOBS),  # type: ignore[attr-defined]
)
def test_check_ignore_http_error_codes_and_error_message(job_data: dict[str, Any]) -> None:
    if job_data.get('use_browser'):
        pytest.skip('Cannot debug due to Playwrigth/Windows bug')  # TODO Remove this and fix

    job_data['url'] = 'https://www.google.com/teapot'
    job_data['http_proxy'] = None
    job_data['timeout'] = 30
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        if isinstance(job_state.exception, (HTTPError, HTTPStatusError)):
            assert job_state.exception.args[0].lower() == (
                "418 client error: i'm a teapot for url: https://www.google.com/teapot\n[](https://www.google.com/)\n"
                '**418.** i’m a teapot.\nthe requested entity body is short and stout. tip me over and pour me out.'
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
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        assert job_state.error_ignored is True
    job_data['ignore_http_error_codes'] = None


@py_latest_only
@connection_required
def test_stress_use_browser() -> None:
    jobs_file = data_path.joinpath('jobs-use_browser.yaml')
    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path('')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])

    if not os.getenv('GITHUB_ACTIONS'):
        from webchanges.cli import setup_logger

        setup_logger()

    urlwatch_config = new_command_config(config_file, jobs_file, hooks_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
    urlwatcher.run_jobs()


def test_shell_exception_and_with_defaults() -> None:
    job_data = {'command': 'this_command_does_not_exist'}
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, Exception)
        assert str(job_state.exception)


def test_no_required_directive() -> None:
    job_data = {'url_typo': 'this directive does not exist'}
    with pytest.raises(ValueError) as pytest_wrapped_e:
        JobBase.unserialize(job_data)
    assert str(pytest_wrapped_e.value) == (
        f"Error in jobs file: Job directive has no value or doesn't match a job type (check for errors/typos/escaping "
        f'or documentation):\n{yaml.safe_dump(job_data)}'
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
        '   Please check for typos or refer to the documentation.'
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
#         f"Job directive 'kind' is deprecated and ignored: delete from job ({job_data})"  # noqa: S608
#     )


def test_url_job_without_kind() -> None:
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, UrlJob)


def test_url_job_use_browser_false_without_kind() -> None:
    job_data = {'url': 'https://www.example.com', 'use_browser': False}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, UrlJob)


def test_browser_job_without_kind() -> None:
    job_data = {'url': 'https://www.example.com', 'use_browser': True}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, BrowserJob)


def test_shell_job_without_kind() -> None:
    job_data = {'command': 'ls'}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, ShellJob)


def test_with_defaults() -> None:
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    config: _Config = {'job_defaults': {'all': {'timeout': 999}}}  # type: ignore[typeddict-item]
    job = job.with_defaults(config)
    assert job.timeout == 999
    assert job.get_indexed_location() == 'Job 0: https://www.example.com'


def test_with_defaults_headers() -> None:
    """Tests that the default headers are overwritten correctly: those more specific (i.e. ``url`` and ``browser``)
    override those more generic (i.e. ``all``)."""
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    config: _Config = {  # type: ignore[typeddict-item]
        'job_defaults': {
            'all': {'headers': {'a': '1', 'b': '2'}},
            'url': {'headers': {'b': '3', 'c': '4'}},
            'browser': {'headers': {'c': '5', 'd': '6'}},
        }
    }
    job = job.with_defaults(config)
    assert job.headers == {'a': '1', 'b': '3', 'c': '4'}
    assert job.get_indexed_location() == 'Job 0: https://www.example.com'


def test_ignore_error() -> None:
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    assert job.ignore_error(Exception()) is False


def test_browser_switches_not_str_or_list() -> None:
    job_data = {
        'url': 'https://www.example.com',
        'use_browser': True,
        'switches': {'dict key': ''},
    }
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, TypeError)


# def test_browser_block_elements_not_str_or_list():
#     job_data = {
#         'url': 'https://www.example.com',
#         'use_browser': True,
#         'block_elements': {'dict key': ''},
#     }
#     job = JobBase.unserialize(job_data)
#     with JobState(ssdb_storage, job) as job_state:
#         job_state.process()
#         assert isinstance(job_state.exception, TypeError)
#
#
# def test_browser_block_elements_invalid():
#     job_data = {
#         'url': 'https://www.example.com',
#         'use_browser': True,
#         'block_elements': ['fake element'],
#     }
#     job = JobBase.unserialize(job_data)
#     with JobState(ssdb_storage, job) as job_state:
#         job_state.process()
#         assert isinstance(job_state.exception, ValueError)


def test_shell_error() -> None:
    job_data = {'command': 'this_command_does_not_exist'}
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, subprocess.CalledProcessError)


def test_compared_versions() -> None:
    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path('')
    jobs_file = data_path.joinpath('jobs-time.yaml')
    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    urlwatch_config = new_command_config(config_file, jobs_file, hooks_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)

    # compared_versions = 2
    urlwatcher.jobs[0].command = 'python3 -c "import random; print(random.randint(0, 1))"'
    urlwatcher.jobs[0].compared_versions = 2
    results = set()
    for i in range(20):
        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        if urlwatcher.report.job_states[-1].new_data in results:
            assert urlwatcher.report.job_states[-1].verb == 'unchanged'
        else:
            results.add(urlwatcher.report.job_states[-1].new_data)
            assert urlwatcher.report.job_states[-1].verb in {'new', 'changed'}

    # compared_versions = 3  (may trigger fuzzy match search)
    ssdb_storage.flushdb()
    urlwatcher.jobs[0].command = 'python3 -c "import random; print(random.randint(0, 2))"'
    urlwatcher.jobs[0].compared_versions = 3
    results = set()
    for i in range(20):
        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        if urlwatcher.report.job_states[-1].new_data in results:
            assert urlwatcher.report.job_states[-1].verb == 'unchanged'
        else:
            results.add(urlwatcher.report.job_states[-1].new_data)
            assert urlwatcher.report.job_states[-1].verb in {'new', 'changed'}
    print(0)
    ssdb_storage.close()


def test_differ_name_not_str_dict_raises_valueerror() -> None:
    job_data = {'differ': [2]}
    with pytest.raises(ValueError) as pytest_wrapped_e:
        JobBase.unserialize(job_data)
    assert str(pytest_wrapped_e.value).splitlines() == [
        "Error in jobs file: Job directive 'differ: [2]' has to be a string or dict:",
        'differ:',
        '- 2',
    ]
