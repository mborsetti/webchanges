"""Test running of jobs."""

from __future__ import annotations

import ftplib
import importlib.util
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

import pytest
import yaml
from httpx import HTTPStatusError
from requests import HTTPError

from webchanges.config import CommandConfig
from webchanges.handler import JobState, Snapshot
from webchanges.jobs import (
    BrowserJob,
    BrowserResponseError,
    JobBase,
    NotModifiedError,
    ShellJob,
    TransientHTTPError,
    UrlJob,
)
from webchanges.main import Urlwatch
from webchanges.storage import SsdbSQLite3Storage, YamlConfigStorage, YamlJobsStorage, _Config

if TYPE_CHECKING:
    from unittest.mock import Mock

    import pytest_mock

playwright_is_installed = importlib.util.find_spec('playwright') is not None
if playwright_is_installed:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
else:
    PlaywrightTimeoutError = Exception

curl_cffi_is_installed = importlib.util.find_spec('curl_cffi') is not None

here = Path(__file__).parent
data_path = here.joinpath('data')


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
    'Callable[[Callable], Callable]', pytest.mark.skipif(not is_connected(), reason='no Internet connection')
)
py_latest_only = cast(
    'Callable[[Callable], Callable]',
    pytest.mark.skipif(
        sys.version_info < (3, 14),
        reason='Latest python only (time consuming)',
    ),
)
playwright_required = cast(
    'Callable[[Callable], Callable]', pytest.mark.skipif(not playwright_is_installed, reason='Playwright not installed')
)

TEST_JOBS: list[tuple[dict[str, Any], str | bytes]] = [
    (
        {
            'url': 'https://www.google.com/',
            'note': 'Google with no name (grab title)',
            'cookies': {'X-test': 'test'},
            'encoding': 'ascii',
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/141.0.0.0 Safari/537.36'
            },
            'ignore_cached': True,
            'ignore_connection_errors': False,
            'ignore_dh_key_too_small': False,  # as of Jan25 weak cyphers no longer supported
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
            'url': 'https://www.cloudflare.com/cdn-cgi/trace',
            'note': 'Cloudflare with requests',
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/118.0.0.0 Safari/537.36'
            },
            'http_client': 'requests',
            'filter': [{'keep_lines_containing': 'h='}],
            'timeout': 0,
        },
        'h=www.cloudflare.com',
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
            'timeout': 60,
            'user_visible_url': 'https://www.google.com/',
            'wait_for_navigation': 'https://www.google.com/*',
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
ALL_JOB_TYPES: list[dict[str, str | bool]] = [
    {},
    {'use_browser': True},
]
if importlib.util.find_spec('requests') is not None:
    ALL_JOB_TYPES.append({'http_client': 'requests'})


def job_type_str(v: dict[str, Any]) -> str:
    return 'BrowserJob' if v.get('use_browser') else f'UrlJob-{v.get("http_client", "httpx")}'


def new_command_config(config_file: Path, jobs_file: Path, hooks_file: Path) -> CommandConfig:
    """Create a new command config (in-memory ssdb)."""
    return CommandConfig(
        args=[],
        config_path=here,
        config_file=config_file,
        jobs_def_file=jobs_file,
        hooks_def_file=hooks_file,
        ssdb_file=':memory:',  # ty:ignore[invalid-argument-type]
    )


def test_check_429_transient_error(ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture) -> None:
    """Check for 429 Too Many Requests response, which should raise a TransientError."""
    job = JobBase.unserialize({'url': 'https://www.google.com/'})

    # Process the job for the first time
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()

        # Create a mock response object
        mock_response = mocker.Mock()
        mock_response.status_code = 429
        mock_response.reason_phrase = 'Too Many Requests'
        mock_response.url = 'https://example.com/too-many-requests'
        mock_response.request = mocker.Mock()
        mock_response.text = 'Rate limit exceeded'
        mock_response.history = []
        mock_response.headers = {'Content-Type': 'text/plain'}

        # Mock the httpx client's request method to return our mock response
        mocker.patch('httpx.Client.request', return_value=mock_response)

        job_state.save()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        job_state.load()

        job_state.process()

    # 4. Assert that a TransientError was raised and handled
    assert isinstance(job_state.exception, TransientHTTPError)
    assert '429 Client Error: Too Many Requests' in str(job_state.exception)
    assert job_state.error_ignored is False
    assert job_state.new_data == job_state.old_data


def test_check_429_transient_error_requests(
    ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture
) -> None:
    """Check for 429 Too Many Requests response, which should raise a TransientError."""
    job = JobBase.unserialize({'url': 'https://www.google.com/', 'http_client': 'requests'})

    # Process the job for the first time
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()

        ###########################################################################################################
        # Create a mock response object
        mock_response = mocker.Mock()
        mock_response.status_code = 429
        mock_response.reason = 'Too Many Requests'
        mock_response.url = 'https://example.com/too-many-requests'
        mock_response.request = mocker.Mock()
        mock_response.text = 'Rate limit exceeded'
        mock_response.history = []
        mock_response.headers = {'Content-Type': 'text/plain'}

        # Mock the requests Session's request method to return our mock response
        mocker.patch('requests.sessions.Session.request', return_value=mock_response)

        job_state.save()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        job_state.load()

        job_state.process()

    # 4. Assert that a TransientError was raised and handled
    assert isinstance(job_state.exception, TransientHTTPError)
    assert '429 Client Error: Too Many Requests' in str(job_state.exception)
    assert job_state.error_ignored is False
    assert job_state.new_data == job_state.old_data


@pytest.mark.skipif(not curl_cffi_is_installed, reason='curl_cffi not installed')
def test_check_429_transient_error_curl_cffi(
    ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture
) -> None:
    """Check for 429 Too Many Requests response with curl_cffi backend, which should raise a TransientError."""
    job = JobBase.unserialize({'url': 'https://www.google.com/', 'http_client': 'curl_cffi'})

    # Process the job for the first time
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()

        ###########################################################################################################
        # Create a mock response object
        mock_response = mocker.Mock()
        mock_response.status_code = 429
        mock_response.reason = 'Too Many Requests'
        mock_response.url = 'https://example.com/too-many-requests'
        mock_response.request = mocker.Mock()
        mock_response.text = 'Rate limit exceeded'
        mock_response.history = []
        mock_response.headers = {'Content-Type': 'text/plain'}

        # Mock the curl_cffi Session's request method to return our mock response
        mocker.patch('curl_cffi.requests.Session.request', return_value=mock_response)

        job_state.save()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        job_state.load()

        job_state.process()

    # 4. Assert that a TransientError was raised and handled
    assert isinstance(job_state.exception, TransientHTTPError)
    assert '429 Client Error: Too Many Requests' in str(job_state.exception)
    assert job_state.error_ignored is False
    assert job_state.new_data == job_state.old_data


@pytest.mark.skipif(not curl_cffi_is_installed, reason='curl_cffi not installed')
def test_curl_cffi_impersonate_passthrough(ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture) -> None:
    """Verify the impersonate directive is passed to curl_cffi.requests.Session, defaulting to 'chrome'."""
    captured: dict[str, object] = {}

    def fake_session(**kwargs: object) -> Mock:
        captured.update(kwargs)
        instance = mocker.MagicMock()
        instance.__enter__ = lambda self: self
        instance.__exit__ = lambda self, *a: None
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.reason = 'OK'
        mock_response.url = 'https://example.com/'
        mock_response.text = 'ok'
        mock_response.content = b'ok'
        mock_response.history = []
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.encoding = 'utf-8'
        instance.request.return_value = mock_response
        return instance

    mocker.patch('curl_cffi.requests.Session', side_effect=fake_session)

    # Default impersonate
    job = JobBase.unserialize({'url': 'https://example.com/', 'http_client': 'curl_cffi'})
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
    assert captured.get('impersonate') == 'chrome'

    # Explicit impersonate
    captured.clear()
    job = JobBase.unserialize({'url': 'https://example.com/', 'http_client': 'curl_cffi', 'impersonate': 'safari17_0'})
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
    assert captured.get('impersonate') == 'safari17_0'


def test_httpx_http_version_passthrough(ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture) -> None:
    """Verify http_version=v1 forces http2=False on httpx.Client, and v2 forces http2=True."""
    captured: dict[str, object] = {}

    def fake_client(**kwargs: object) -> Mock:
        captured.update(kwargs)
        instance = mocker.MagicMock()
        instance.__enter__ = lambda self: self
        instance.__exit__ = lambda self, *a: None
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.reason_phrase = 'OK'
        mock_response.url = 'https://example.com/'
        mock_response.text = 'ok'
        mock_response.content = b'ok'
        mock_response.history = []
        mock_response.is_redirect = False
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.encoding = 'utf-8'
        instance.request.return_value = mock_response
        return instance

    mocker.patch('httpx.Client', side_effect=fake_client)

    job = JobBase.unserialize({'url': 'https://example.com/', 'http_version': 'v1'})
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
    assert captured.get('http1') is True
    assert captured.get('http2') is False

    if importlib.util.find_spec('h2') is not None:
        captured.clear()
        job = JobBase.unserialize({'url': 'https://example.com/', 'http_version': 'v2'})
        with JobState(ssdb_storage, job) as job_state:
            job_state.process()
        assert captured.get('http2') is True


def test_httpx_http_version_invalid(ssdb_storage: SsdbSQLite3Storage) -> None:
    """http_version=v3 with httpx should raise ValueError at retrieve time."""
    job = JobBase.unserialize({'url': 'https://example.com/', 'http_version': 'v3'})
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
    assert isinstance(job_state.exception, ValueError)
    assert 'http_version' in str(job_state.exception)


def test_http_version_invalid_with_requests(ssdb_storage: SsdbSQLite3Storage) -> None:
    """http_version with http_client: requests should raise ValueError at retrieve time."""
    job = JobBase.unserialize({'url': 'https://example.com/', 'http_client': 'requests', 'http_version': 'v1'})
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
    assert isinstance(job_state.exception, ValueError)
    assert 'http_version' in str(job_state.exception)


@pytest.mark.skipif(not curl_cffi_is_installed, reason='curl_cffi not installed')
def test_curl_cffi_http_version_passthrough(
    ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture
) -> None:
    """Verify http_version is forwarded to curl_cffi.requests.Session kwargs."""
    captured: dict[str, object] = {}

    def fake_session(**kwargs: object) -> Mock:
        captured.update(kwargs)
        instance = mocker.MagicMock()
        instance.__enter__ = lambda self: self
        instance.__exit__ = lambda self, *a: None
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.reason = 'OK'
        mock_response.url = 'https://example.com/'
        mock_response.text = 'ok'
        mock_response.content = b'ok'
        mock_response.history = []
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.encoding = 'utf-8'
        instance.request.return_value = mock_response
        return instance

    mocker.patch('curl_cffi.requests.Session', side_effect=fake_session)

    job = JobBase.unserialize({'url': 'https://example.com/', 'http_client': 'curl_cffi', 'http_version': 'v3'})
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
    assert captured.get('http_version') == 'v3'


@pytest.mark.skipif(not curl_cffi_is_installed, reason='curl_cffi not installed')
def test_curl_cffi_fingerprints_passthrough(
    ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture
) -> None:
    """Verify the fingerprints directive forwards ja3/akamai/extra_fp to curl_cffi.requests.Session kwargs."""
    captured: dict[str, object] = {}

    def fake_session(**kwargs: object) -> Mock:
        captured.update(kwargs)
        instance = mocker.MagicMock()
        instance.__enter__ = lambda self: self
        instance.__exit__ = lambda self, *a: None
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.reason = 'OK'
        mock_response.url = 'https://example.com/'
        mock_response.text = 'ok'
        mock_response.content = b'ok'
        mock_response.history = []
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.encoding = 'utf-8'
        instance.request.return_value = mock_response
        return instance

    mocker.patch('curl_cffi.requests.Session', side_effect=fake_session)

    fingerprints = {
        'ja3': '771,4865-4866,0',
        'akamai': '1:65536;4:6291456|15663105|0|m,s,a,p',
        'extra_fp': {'tls_grease': True},
    }
    job = JobBase.unserialize(
        {
            'url': 'https://example.com/',
            'http_client': 'curl_cffi',
            'fingerprints': fingerprints,
        }
    )
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
    assert captured.get('ja3') == fingerprints['ja3']
    assert captured.get('akamai') == fingerprints['akamai']
    assert captured.get('extra_fp') == fingerprints['extra_fp']


@pytest.mark.skipif(not curl_cffi_is_installed, reason='curl_cffi not installed')
def test_curl_cffi_fingerprints_unknown_key(
    ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture
) -> None:
    """Unknown fingerprints keys should raise ValueError."""
    mocker.patch('curl_cffi.requests.Session', side_effect=AssertionError('should not be called'))
    job = JobBase.unserialize(
        {
            'url': 'https://example.com/',
            'http_client': 'curl_cffi',
            'fingerprints': {'bogus': 'x'},
        }
    )
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
    assert isinstance(job_state.exception, ValueError)
    assert 'fingerprints' in str(job_state.exception)


def test_check_429_ignore_4xx(ssdb_storage: SsdbSQLite3Storage, mocker: pytest_mock.MockerFixture) -> None:
    """Check for 429 Too Many Requests response, which should raise a TransientError."""
    job = JobBase.unserialize({'url': 'https://www.google.com/', 'ignore_http_error_codes': '4xx, 5xx'})

    # Process the job for the first time
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()

        # Create a mock response object
        mock_response = mocker.Mock()
        mock_response.status_code = 429
        mock_response.reason_phrase = 'Too Many Requests'
        mock_response.url = 'https://example.com/too-many-requests'
        mock_response.request = mocker.Mock()
        mock_response.text = 'Rate limit exceeded'
        mock_response.history = []
        mock_response.headers = {'Content-Type': 'text/plain'}

        # Mock the httpx client's request method to return our mock response
        mocker.patch('httpx.Client.request', return_value=mock_response)

        job_state.save()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        job_state.load()

        job_state.process()

    # 4. Assert that a TransientError was raised and handled
    assert isinstance(job_state.exception, TransientHTTPError)
    assert '429 Client Error: Too Many Requests' in str(job_state.exception)
    assert job_state.error_ignored is True
    assert job_state.new_data == job_state.old_data


# TODO: Failing with Error
# 'It looks like you are using Playwright Sync API inside the asyncio loop.\nPlease use the Async API instead.'
# def test_check_transient_errors_browser(page: Page) -> None:
#     """Check for 429 Too Many Requests response and for a 'net::ERR_CONNECTION_CLOSED' browser error, both of which
#     should raise a TransientError."""
#     job = JobBase.unserialize({'url': 'https://www.google.com/', 'use_browser': True})

#     # Process the job for the first time
#     with JobState(ssdb_storage, job) as job_state:
#         job_state.process()

#         ###########################################################################################################
#         # Create a mock response object
#         page.route(
#             job.url,
#             lambda route: route.fulfill(
#                 status=429,
#                 ok=False,
#                 content_type='text/html',
#                 status_text='Too Many Requests',
#                 url=job.url,
#                 headers={'Content-Type': 'text/plain'},
#                 body='',
#             ),
#         )

#         job_state.save()
#         ssdb_storage._copy_temp_to_permanent(delete=True)
#         job_state.load()

#         job_state.process()

#         # 4. Assert that a TransientError was raised and handled
#         assert isinstance(job_state.exception, TransientError)
#         assert '429 Client Error: Too Many Requests' in str(job_state.exception)
#         assert job_state.error_ignored is False
#         assert job_state.new_data == job_state.old_data

#         # 5. Create a mock response object
#         page.route(job.url, lambda route: route.abort('connectionclosed'))

#         job_state.save()
#         ssdb_storage._copy_temp_to_permanent(delete=True)
#         job_state.load()

#         job_state.process()

#         # 6. Assert that a TransientError was raised and handled
#         assert isinstance(job_state.exception, TransientError)
#         assert 'net::ERR_CONNECTION_CLOSED' in str(job_state.exception)
#         assert job_state.error_ignored is False
#         assert job_state.new_data == job_state.old_data


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


@connection_required
@pytest.mark.parametrize(
    ('input_job', 'output'),
    TEST_JOBS,
    ids=(f'{job_type_str(v[0])}: {v[1]!r}' for v in TEST_JOBS),
)
def test_run_job(
    input_job: dict[str, str | dict[str, str] | bool | int],
    output: str | bytes,
    ssdb_storage: SsdbSQLite3Storage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    job = JobBase.unserialize(input_job)
    if job.use_browser and not playwright_is_installed:
        pytest.skip('Playwright not installed')
    else:
        with JobState(ssdb_storage, job) as job_state:
            data, _, _ = job.retrieve(job_state)
            if job.filters == [{'pdf2text': {}}]:
                assert isinstance(data, bytes)
            assert output in data  # ty:ignore[unsupported-operator]


@connection_required
@pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout, socket.gaierror))
def test_run_ftp_job(ssdb_storage: SsdbSQLite3Storage) -> None:
    job = JobBase.unserialize({'url': 'ftp://tgftp.nws.noaa.gov/logmsg.txt', 'timeout': 2})
    with JobState(ssdb_storage, job) as job_state:
        data, _, _ = job.retrieve(job_state)
        assert len(data) == 319


# @connection_required
# @pytest.mark.xfail(raises=(ftplib.error_temp, socket.timeout, EOFError, OSError))
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


@connection_required
@pytest.mark.parametrize(
    'job_data',
    ALL_JOB_TYPES,
    ids=(job_type_str(v) for v in ALL_JOB_TYPES),
)
def test_check_etag(job_data: dict[str, Any], ssdb_storage: SsdbSQLite3Storage) -> None:
    job_data['url'] = 'https://github.githubassets.com/assets/discussions-1958717f4567.css'
    job = JobBase.unserialize(job_data)
    if job.use_browser and not playwright_is_installed:
        pytest.skip('Playwright not installed')
    else:
        with JobState(ssdb_storage, job) as job_state:
            _, etag, _ = job.retrieve(job_state)
            assert etag


@connection_required
@pytest.mark.parametrize(
    'job_data',
    ALL_JOB_TYPES,
    ids=(job_type_str(v) for v in ALL_JOB_TYPES),
)
def test_check_etag_304_request(
    job_data: dict[str, Any], ssdb_storage: SsdbSQLite3Storage, doctest_namespace: dict
) -> None:
    """Check for 304 Not Modified response."""
    if job_data.get('use_browser'):
        pytest.skip('Capturing of 304 cannot be implemented in Chrome')  # last tested with Chromium 89
    job_data['url'] = 'https://github.githubassets.com/assets/discussions-1958717f4567.css'
    job = JobBase.unserialize(job_data)
    if job.use_browser and not playwright_is_installed:
        pytest.skip('Playwright not installed')
    else:
        with JobState(ssdb_storage, job) as job_state:
            if 'check__etag_304_etag' not in doctest_namespace:
                job.index_number = 1
                _, etag, _ = job.retrieve(job_state)
                doctest_namespace['check_etag_304_etag'] = etag
                doctest_namespace['check_etag_304_timestamp'] = job_state.old_timestamp

            job_state.old_etag = doctest_namespace['check_etag_304_etag']
            job_state.old_timestamp = doctest_namespace['check_etag_304_timestamp']
            job.index_number = 2
            with pytest.raises(NotModifiedError) as pytest_wrapped_e:
                job.retrieve(job_state)

            assert str(pytest_wrapped_e.value) == '304'


@connection_required
@pytest.mark.parametrize(
    'job_data',
    ALL_JOB_TYPES,
    ids=(job_type_str(v) for v in ALL_JOB_TYPES),
)
def test_check_ignore_connection_errors(job_data: dict[str, Any], ssdb_storage: SsdbSQLite3Storage) -> None:
    job_data['url'] = 'http://localhost:9999'
    job = JobBase.unserialize(job_data)
    if job.use_browser and not playwright_is_installed:
        pytest.skip('Playwright not installed')
    else:
        with JobState(ssdb_storage, job) as job_state:
            job_state.process()
            assert job_state.exception
            assert any(
                x in str(job_state.exception.args)
                for x in ('Connection refused', 'No connection could be made', 'net::ERR_CONNECTION_REFUSED')
            )
            assert getattr(job_state, 'error_ignored', False) is False

        job_data['ignore_connection_errors'] = True
        job = JobBase.unserialize(job_data)
        with JobState(ssdb_storage, job) as job_state:
            job_state.process()
            assert job_state.error_ignored is True
            # also check that it's using the correct HTTP client library
            if not job_data.get('use_browser'):
                assert job_state._http_client_used == job_data.get('http_client', 'httpx')
        job_data['ignore_connection_errors'] = None


@connection_required
@pytest.mark.parametrize(
    'job_data',
    ALL_JOB_TYPES,
    ids=(job_type_str(v) for v in ALL_JOB_TYPES),
)
def test_check_bad_proxy(job_data: dict[str, Any], ssdb_storage: SsdbSQLite3Storage) -> None:
    job_data['url'] = 'http://connectivitycheck.gstatic.com/generate_204'
    job_data['http_proxy'] = 'http://notworking:ever@localhost:8080'
    job = JobBase.unserialize(job_data)
    if job.use_browser and not playwright_is_installed:
        pytest.skip('Playwright not installed')
    else:
        with JobState(ssdb_storage, job) as job_state:
            job_state.process()
            assert job_state.exception
            assert any(
                x in str(job_state.exception.args)
                for x in ('Connection refused', 'No connection could be made', 'ERR_PROXY_CONNECTION_FAILED ')
            )
            assert job_state.error_ignored is False


@connection_required
@pytest.mark.parametrize(
    'job_data',
    ALL_JOB_TYPES,
    ids=(job_type_str(v) for v in ALL_JOB_TYPES),
)
def test_check_ignore_http_error_codes_and_error_message(
    job_data: dict[str, Any], ssdb_storage: SsdbSQLite3Storage
) -> None:
    # if job_data.get('use_browser'):
    #     pytest.skip('Cannot debug due to a Playwright or Windows bug')

    job_data['url'] = 'https://www.google.com/teapot'
    job_data['http_proxy'] = None
    job_data['timeout'] = 30
    job = JobBase.unserialize(job_data)
    if job.use_browser and not playwright_is_installed:
        pytest.skip('Playwright not installed')
    else:
        with JobState(ssdb_storage, job) as job_state:
            job_state.process()
            if isinstance(job_state.exception, (HTTPStatusError, HTTPError)):
                assert job_state.exception.args[0].lower() == (
                    "418 client error: i'm a teapot for url: https://www.google.com/teapot\n[](https://www.google.com/)\n"
                    '**418.** i’m a teapot.\nthe requested entity body is short and stout. '
                    'tip me over and pour me out.'
                )
            elif isinstance(job_state.exception, BrowserResponseError):
                assert job_state.exception.status_code == 418
                assert job_state.exception.args[0] == (
                    '418. I’m a teapot. The requested entity body is short and stout. Tip me over and pour me out.'
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
@playwright_required
def test_stress_use_browser(ssdb_storage: SsdbSQLite3Storage) -> None:
    jobs_file = data_path.joinpath('jobs-use_browser.yaml')
    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path()

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])

    if not os.getenv('GITHUB_ACTIONS'):
        from webchanges.cli import setup_logger

        setup_logger()

    urlwatch_config = new_command_config(config_file, jobs_file, hooks_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
    urlwatcher.run_jobs()


def test_shell_exception_and_with_defaults(ssdb_storage: SsdbSQLite3Storage) -> None:
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
        "Directive 'directive_with_typo' is unrecognized in the following url job\n"
        '   \n'
        '   ---\n'
        '   directive_with_typo: this directive does not exist\n'
        '   url: https://www.example.com\n'
        '   ---\n'
        '\n'
        '   Please check for typos or refer to the documentation.'
    )


def test_validate_wrong_type_bool() -> None:
    job_data = {'url': 'https://www.example.com', 'enabled': 'yes'}
    with pytest.raises(ValueError) as pytest_wrapped_e:
        JobBase.unserialize(job_data)
    assert str(pytest_wrapped_e.value).startswith("Error in directive 'enabled' of job")


def test_validate_wrong_type_numeric() -> None:
    job_data = {'url': 'https://www.example.com', 'timeout': 'soon'}
    with pytest.raises(ValueError, match="Error in directive 'timeout'"):
        JobBase.unserialize(job_data)


def test_validate_wrong_type_list() -> None:
    job_data = {'url': 'https://www.example.com', 'use_browser': True, 'block_elements': 'div'}
    with pytest.raises(ValueError, match="Error in directive 'block_elements'"):
        JobBase.unserialize(job_data)


def test_validate_wrong_literal() -> None:
    job_data = {'url': 'https://www.example.com', 'method': 'BREW'}
    with pytest.raises(ValueError, match="Error in directive 'method'"):
        JobBase.unserialize(job_data)


def test_validate_accepts_valid_types() -> None:
    job_data = {'url': 'https://www.example.com', 'enabled': True, 'timeout': 30.0, 'method': 'POST'}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, UrlJob)
    assert job.enabled is True
    assert job.timeout == 30.0
    assert job.method == 'POST'


def test_validate_accepts_none_for_nullable() -> None:
    job_data = {'url': 'https://www.example.com', 'enabled': None, 'timeout': None}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, UrlJob)
    assert job.enabled is None
    assert job.timeout is None


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
#         f"Job directive 'kind' is deprecated and ignored: delete from job ({job_data})"
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


@pytest.mark.parametrize('value', ['chrome', 'chrome-beta', 'msedge', 'msedge-dev', 'firefox', 'webkit'])
def test_browser_job_use_browser_string(value: str) -> None:
    job_data = {'url': 'https://www.example.com', 'use_browser': value}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, BrowserJob)
    assert job.use_browser == value


def test_browser_job_use_browser_invalid_string(ssdb_storage: SsdbSQLite3Storage) -> None:
    if not playwright_is_installed:
        pytest.skip('Playwright not installed')
    job_data = {'url': 'https://www.example.com', 'use_browser': 'safari'}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, BrowserJob)
    with JobState(ssdb_storage, job) as job_state, pytest.raises(ValueError, match="'use_browser' value 'safari'"):
        job.retrieve(job_state)


def test_shell_job_without_kind() -> None:
    job_data = {'command': 'ls'}
    job = JobBase.unserialize(job_data)
    assert isinstance(job, ShellJob)


def test_with_defaults() -> None:
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    config: _Config = {'job_defaults': {'all': {'timeout': 999}}}  # ty:ignore[missing-typed-dict-key]
    job = job.with_defaults(config)
    assert job.timeout == 999
    assert job.get_indexed_location() == 'Job 0: https://www.example.com'


def test_with_defaults_headers() -> None:
    """Tests that the default headers are overwritten correctly: those more specific (i.e. ``url`` and ``browser``)
    override those more generic (i.e. ``all``).
    """
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    config: _Config = {  # ty:ignore[missing-typed-dict-key]
        'job_defaults': {
            'all': {'headers': {'a': '1', 'b': '2'}},
            'url': {'headers': {'b': '3', 'c': '4'}},
            'browser': {'headers': {'c': '5', 'd': '6'}},
        }
    }
    job = job.with_defaults(config)
    assert dict(job.headers) == {'a': '1', 'b': '3', 'c': '4'}
    assert job.get_indexed_location() == 'Job 0: https://www.example.com'


def test_ignore_error() -> None:
    job_data = {'url': 'https://www.example.com'}
    job = JobBase.unserialize(job_data)
    assert job.ignore_error(Exception()) is False


def test_browser_switches_not_str_or_list() -> None:
    """A non-list/None ``switches`` value is rejected by ``JobBase.unserialize`` (3.36.0+ type check)."""
    job_data = {
        'url': 'https://www.example.com',
        'use_browser': True,
        'switches': {'dict key': ''},
    }
    with pytest.raises(ValueError, match="Error in directive 'switches'"):
        JobBase.unserialize(job_data)


# @playwright_required
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
# @playwright_required
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


def test_shell_error(ssdb_storage: SsdbSQLite3Storage) -> None:
    job_data = {'command': 'this_command_does_not_exist'}
    job = JobBase.unserialize(job_data)
    with JobState(ssdb_storage, job) as job_state:
        job_state.process()
        assert isinstance(job_state.exception, subprocess.CalledProcessError)


def test_compared_versions(ssdb_storage: SsdbSQLite3Storage) -> None:
    config_file = data_path.joinpath('config.yaml')
    hooks_file = Path()
    jobs_file = data_path.joinpath('jobs-time.yaml')
    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    urlwatch_config = new_command_config(config_file, jobs_file, hooks_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)

    # compared_versions = 2
    urlwatcher.jobs[0].command = 'python3 -c "import random; print(random.randint(0, 1))"'
    urlwatcher.jobs[0].compared_versions = 2
    results = set()
    for _ in range(20):
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
    for _ in range(20):
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


@pytest.fixture
def time_jobs_urlwatcher(
    workspace: Path,
    loaded_config_storage: YamlConfigStorage,
) -> Urlwatch:
    """``Urlwatch`` built from ``jobs-time.yaml`` with the job command set to ``echo TEST``.

    Used by the job-state ``verb`` tests below; gives every test a fresh in-memory ssdb that
    supports the ``_copy_temp_to_permanent`` lifecycle.
    """
    jobs_path = workspace / 'jobs-time.yaml'
    cmd = CommandConfig(
        args=[],
        config_path=workspace,
        config_file=workspace / 'config.yaml',
        jobs_def_file=jobs_path,
        hooks_def_file=workspace / 'hooks_example.py',
        ssdb_file=':memory:',  # ty:ignore[invalid-argument-type]
    )
    storage = SsdbSQLite3Storage(':memory:')  # ty:ignore[invalid-argument-type]
    urlwatcher = Urlwatch(cmd, loaded_config_storage, storage, YamlJobsStorage([jobs_path]))
    urlwatcher.jobs[0].command = 'echo TEST'
    urlwatcher.jobs[0].name = 'echo TEST'
    return urlwatcher


def test_job_states_verb(time_jobs_urlwatcher: Urlwatch) -> None:
    """First run produces ``new``; second run with no change produces ``unchanged``."""
    urlwatcher = time_jobs_urlwatcher
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert urlwatcher.report.job_states[-1].verb == 'new'

    urlwatcher.run_jobs()
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'


def test_job_states_verb_notimestamp_unchanged(time_jobs_urlwatcher: Urlwatch) -> None:
    """A snapshot with ``timestamp=0`` and a re-run still classifies as ``unchanged``."""
    urlwatcher = time_jobs_urlwatcher
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert urlwatcher.report.job_states[-1].verb == 'new'

    guid = urlwatcher.ssdb_storage.get_guids()[0]
    snapshot = urlwatcher.ssdb_storage.load(guid)
    urlwatcher.ssdb_storage.delete(guid)
    urlwatcher.ssdb_storage.save(
        guid=guid,
        snapshot=Snapshot(
            data=snapshot.data,
            timestamp=0,
            tries=1,
            etag=snapshot.etag,
            mime_type=snapshot.mime_type,
            error_data=snapshot.error_data,
        ),
    )
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]

    urlwatcher.run_jobs()
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'


def test_job_states_verb_notimestamp_changed(time_jobs_urlwatcher: Urlwatch) -> None:
    """Multiple snapshot rewrites (no timestamp / 1 try / both) all stay ``unchanged`` for the same data."""
    urlwatcher = time_jobs_urlwatcher
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert urlwatcher.report.job_states[-1].verb == 'new'

    guid = urlwatcher.jobs[0].guid
    snapshot = urlwatcher.ssdb_storage.load(guid)
    urlwatcher.ssdb_storage.delete(guid)
    urlwatcher.ssdb_storage.save(guid=guid, snapshot=snapshot)
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]

    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'

    snapshot = urlwatcher.ssdb_storage.load(guid)
    urlwatcher.ssdb_storage.delete(guid)
    urlwatcher.ssdb_storage.save(guid=guid, snapshot=snapshot)
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'

    urlwatcher.ssdb_storage.delete(guid)
    new_snapshot = Snapshot(snapshot.data, 0, snapshot.tries, snapshot.etag, snapshot.mime_type, snapshot.error_data)
    urlwatcher.ssdb_storage.save(guid=guid, snapshot=new_snapshot)
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'

    urlwatcher.ssdb_storage.delete(guid)
    new_snapshot = Snapshot(snapshot.data, 0, 1, snapshot.etag, snapshot.mime_type, {})
    urlwatcher.ssdb_storage.save(guid=guid, snapshot=new_snapshot)
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    urlwatcher.run_jobs()
    urlwatcher.ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[unresolved-attribute]
    assert urlwatcher.report.job_states[-1].verb == 'unchanged'


# def test_suppress_repeated_errors(capsys: pytest.CaptureFixture) -> None:
#     pass
#     jobs_file = data_path.joinpath('jobs-invalid_url.yaml')
#     config_file = data_path.joinpath('config.yaml')
#     hooks_file = Path('')

#     config_storage = YamlConfigStorage(config_file)
#     config_storage.load()
#     jobs_storage = YamlJobsStorage([jobs_file])
#     urlwatch_config = new_command_config(config_file, jobs_file, hooks_file)
#     urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
#     urlwatcher.jobs[0].suppress_repeated_errors = True
#     urlwatcher.run_jobs()
#     urlwatcher.close()
#     ssdb_storage._copy_temp_to_permanent(delete=True)
#     history = ssdb_storage.get_history_snapshots(urlwatcher.jobs[0].get_guid())
#     assert len(history) == 1
#     urlwatcher.run_jobs()
#     ssdb_storage._copy_temp_to_permanent()
#     history = ssdb_storage.get_history_snapshots(urlwatcher.jobs[0].get_guid())
#     print()
#     assert len(history) == 2
#     assert capsys.readouterr().out == 'TEST\n'
