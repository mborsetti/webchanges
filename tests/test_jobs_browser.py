"""Test BrowserJob.retrieve() without a browser, using fakes of the Playwright objects.

The job connects over CDP (``connect_over_cdp``) to a fake browser supplied by a patched ``_acquire_cdp_browser``, so
all of retrieve() after the browser is launched runs as in production. Playwright and psutil must still be importable
because retrieve() imports them up front.
"""

from __future__ import annotations

import importlib.util
import re
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any, Self

import pytest

from webchanges.handler import JobState
from webchanges.jobs import (
    BrowserJob,
    BrowserResponseError,
    JobBase,
    NotModifiedError,
    TransientBrowserError,
    TransientHTTPError,
    _browser,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec('playwright') is None or importlib.util.find_spec('psutil') is None,
    reason='Playwright or psutil not installed',
)

URL = 'https://example.com/'
PAGE_HTML = '<html><head><title>Caf&eacute; prices</title></head><body>Price: 1</body></html>'


def playwright_error(chromium_error: str) -> Exception:
    """Return a Playwright Error with the message format of a failed navigation."""
    from playwright.sync_api import Error

    return Error(f'Page.goto: {chromium_error} at {URL}\nCall log:\n  - navigating to "{URL}", waiting until "load"\n')


class FakeResponse:
    """Fake of a Playwright Response."""

    def __init__(self, status: int = 200, status_text: str = 'OK', headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.status_text = status_text
        self.ok = 200 <= status < 300
        self.url = URL
        self.headers = headers or {}

    def body(self) -> bytes:
        return PAGE_HTML.encode()

    def header_value(self, name: str) -> str | None:
        return self.headers.get(name)

    def all_headers(self) -> dict[str, str]:
        return self.headers


class FakeRoute:
    """Fake of a Playwright Route (with its request)."""

    def __init__(self, resource_type: str = 'document') -> None:
        self.request = type('FakeRequest', (), {'resource_type': resource_type})()
        self.outcome: tuple[str, dict[str, Any]] | None = None

    def continue_(self, **kwargs: Any) -> None:
        self.outcome = ('continue', kwargs)

    def abort(self) -> None:
        self.outcome = ('abort', {})


class FakePage:
    """Fake of a Playwright Page, recording the calls made to it."""

    def __init__(
        self,
        responses: list[FakeResponse | None] | None = None,
        error: Exception | None = None,
        evaluate_result: Any = None,
        url_after_goto: str = URL,
    ) -> None:
        self.responses = responses if responses is not None else [FakeResponse()]
        self.error = error
        self.evaluate_result = evaluate_result
        self.url_after_goto = url_after_goto
        self.url = 'about:blank'
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.routes: dict[str, Callable[[FakeRoute], None]] = {}

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

    def called(self, name: str) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
        return [(args, kwargs) for call, args, kwargs in self.calls if call == name]

    def goto(self, url: str, **kwargs: Any) -> FakeResponse | None:
        self._record('goto', url, **kwargs)
        if self.error is not None:
            raise self.error
        self.url = self.url_after_goto
        return self.responses.pop(0)

    def content(self) -> str:
        return PAGE_HTML

    def text_content(self, selector: str) -> str:
        self._record('text_content', selector)
        return '  Server is down  '

    def evaluate(self, expression: str) -> Any:
        self._record('evaluate', expression)
        return self.evaluate_result

    def route(self, url: str, handler: Callable[[FakeRoute], None]) -> None:
        self.routes[url] = handler

    def wait_for_selector(self, *args: Any, **kwargs: Any) -> None:
        self._record('wait_for_selector', *args, **kwargs)

    def wait_for_function(self, *args: Any, **kwargs: Any) -> None:
        self._record('wait_for_function', *args, **kwargs)

    def wait_for_timeout(self, timeout: float) -> None:
        self._record('wait_for_timeout', timeout)

    def screenshot(self, path: str, full_page: bool = False) -> None:
        from playwright.sync_api import Error

        raise Error('Target page, context or browser has been closed')

    def close(self) -> None:
        pass


class FakeContext:
    """Fake of a Playwright BrowserContext."""

    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.pages: list[Any] = []

    def set_default_timeout(self, timeout: float) -> None:
        pass

    def add_cookies(self, cookies: list[dict[str, str]]) -> None:
        self.page._record('add_cookies', cookies)  # recorded with the page's calls

    def new_page(self) -> FakePage:
        return self.page


class FakeBrowser:
    """Fake of a Playwright Browser attached over CDP."""

    browser_type = type('FakeBrowserType', (), {'name': 'chromium'})()
    version = '999.0'

    def __init__(self, page: FakePage) -> None:
        self.contexts = [FakeContext(page)]


def make_job(monkeypatch: pytest.MonkeyPatch, page: FakePage, **directives: Any) -> BrowserJob:
    """Return a connect_over_cdp BrowserJob whose browser is a fake one opening ``page``."""
    browser = FakeBrowser(page)
    monkeypatch.setattr(_browser, '_acquire_cdp_browser', lambda *_args: (None, browser, False))
    job = JobBase.unserialize({'url': URL, 'use_browser': True, 'connect_over_cdp': True, **directives})
    assert isinstance(job, BrowserJob)
    return job


def retrieve(job: BrowserJob) -> tuple[str | bytes, str, str]:
    return job.retrieve(JobState(None, job))  # ty:ignore[invalid-argument-type]


# --- errors ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    'chromium_error',
    ['net::ERR_NAME_NOT_RESOLVED', 'net::ERR_CONNECTION_REFUSED', 'net::ERR_TIMED_OUT', 'net::ERR_TOO_MANY_REDIRECTS'],
)
def test_navigation_error_is_transient(monkeypatch: pytest.MonkeyPatch, chromium_error: str) -> None:
    """A Chromium network error is raised as a TransientBrowserError carrying its code, for the ignore_* directives."""
    job = make_job(monkeypatch, FakePage(error=playwright_error(chromium_error)))
    with pytest.raises(TransientBrowserError) as exc_info:
        retrieve(job)
    assert exc_info.value.args == (chromium_error,)


def test_navigation_timeout_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    job = make_job(monkeypatch, FakePage(error=PlaywrightTimeoutError('Timeout 120000ms exceeded.')))
    with pytest.raises(TransientBrowserError, match=r'^PlaywrightTimeoutError$'):
        retrieve(job)


def test_other_browser_error_is_reraised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A browser error that is not a network one is re-raised as is."""
    error = playwright_error('net::ERR_ABORTED')
    job = make_job(monkeypatch, FakePage(error=error))
    with pytest.raises(type(error)) as exc_info:
        retrieve(job)
    assert exc_info.value is error


@pytest.mark.parametrize(
    ('chromium_error', 'directive'),
    [
        ('net::ERR_CONNECTION_REFUSED', 'ignore_connection_errors'),
        ('net::ERR_TIMED_OUT', 'ignore_timeout_errors'),
        ('net::ERR_CONNECTION_TIMED_OUT', 'ignore_timeout_errors'),
        ('net::ERR_TOO_MANY_REDIRECTS', 'ignore_too_many_redirects'),
    ],
)
def test_ignore_directives(monkeypatch: pytest.MonkeyPatch, chromium_error: str, directive: str) -> None:
    """The ignore_* directives silence the browser errors they are documented for, and only with the directive."""
    job = make_job(monkeypatch, FakePage(error=playwright_error(chromium_error)))
    with pytest.raises(Exception) as exc_info:
        retrieve(job)
    assert job.ignore_error(exc_info.value) is False
    setattr(job, directive, True)
    assert job.ignore_error(exc_info.value) is True


def test_cdp_sets_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    """With connect_over_cdp, the cookies are set in the context of the connected browser, for the job's host."""
    page = FakePage()
    job = make_job(monkeypatch, page, cookies={'session': 'abc'})
    retrieve(job)
    assert page.called('add_cookies') == [(([{'name': 'session', 'value': 'abc', 'url': URL}],), {})]


def test_save_error_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After a browser error, the page's HTML is saved; screenshots that cannot be taken leave no empty file behind."""
    monkeypatch.setattr('tempfile.tempdir', str(tmp_path))
    job = make_job(monkeypatch, FakePage())
    job._save_error_files(FakePage())  # ty:ignore[invalid-argument-type]
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].name.startswith('webchanges_content_')
    assert files[0].read_text() == PAGE_HTML


# --- HTTP responses --------------------------------------------------------------------------------------------------


def test_no_response(monkeypatch: pytest.MonkeyPatch) -> None:
    job = make_job(monkeypatch, FakePage(responses=[None]))
    with pytest.raises(BrowserResponseError, match='No response received'):
        retrieve(job)


def test_not_modified(monkeypatch: pytest.MonkeyPatch) -> None:
    job = make_job(monkeypatch, FakePage(responses=[FakeResponse(304, 'Not Modified')]))
    with pytest.raises(NotModifiedError):
        retrieve(job)


@pytest.mark.parametrize('status', [429, 500, 502, 503, 504])
def test_transient_http_error(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """A transient HTTP error reports the status and the page's text."""
    job = make_job(monkeypatch, FakePage(responses=[FakeResponse(status, 'Unavailable')]))
    with pytest.raises(TransientHTTPError) as exc_info:
        retrieve(job)
    assert exc_info.value.status_code == status
    assert str(exc_info.value) == 'Unavailable\nServer is down'


def test_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage(responses=[FakeResponse(403, 'Forbidden')])
    job = make_job(monkeypatch, page)
    with pytest.raises(BrowserResponseError) as exc_info:
        retrieve(job)
    assert exc_info.value.status_code == 403
    assert exc_info.value.args == ('Forbidden\nServer is down',)


def test_http_error_404_skips_page_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404 page's text (often a large template) is not added to the error message."""
    page = FakePage(responses=[FakeResponse(404, 'Not Found')])
    job = make_job(monkeypatch, page)
    with pytest.raises(BrowserResponseError) as exc_info:
        retrieve(job)
    assert exc_info.value.status_code == 404
    assert not page.called('text_content')


# --- content ---------------------------------------------------------------------------------------------------------


def test_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rendered page is returned with the response's ETag and media type; the title names an unnamed job."""
    headers = {'content-type': 'text/html; charset=utf-8', 'etag': '"abc"'}
    job = make_job(monkeypatch, FakePage(responses=[FakeResponse(headers=headers)]))
    assert retrieve(job) == (PAGE_HTML, '"abc"', 'text/html; charset=utf-8')
    assert job.name == 'Café prices'


def test_content_keeps_name(monkeypatch: pytest.MonkeyPatch) -> None:
    job = make_job(monkeypatch, FakePage(), name='My job')
    retrieve(job)
    assert job.name == 'My job'


@pytest.mark.parametrize(
    ('result', 'expected'),
    [
        ('text', ('text', 'text/plain')),
        ({'price': 1, 'name': 'café'}, ('{"price": 1, "name": "café"}', 'application/json')),
        ({1, 2}, ('{1, 2}', 'text/plain')),  # not JSON serializable
    ],
    ids=['str', 'json', 'other'],
)
def test_evaluate(monkeypatch: pytest.MonkeyPatch, result: Any, expected: tuple[Any, str]) -> None:
    """The result of the 'evaluate' JavaScript is returned with a media type matching its type."""
    page = FakePage(evaluate_result=result)
    job = make_job(monkeypatch, page, evaluate='window.data')
    data, _etag, mime_type = retrieve(job)
    assert (data, mime_type) == expected
    assert page.called('evaluate') == [(('window.data',), {})]


# --- directives ------------------------------------------------------------------------------------------------------


def test_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wait_for_* directives are passed on to Playwright: strings as is, dicts as keyword arguments."""
    page = FakePage()
    job = make_job(
        monkeypatch,
        page,
        wait_for_selector=['#price', {'selector': '#name', 'state': 'attached'}],
        wait_for_function={'expression': 'window.ready', 'polling': 100},
        wait_for_timeout=1.5,
    )
    retrieve(job)
    assert page.called('wait_for_selector') == [(('#price',), {}), ((), {'selector': '#name', 'state': 'attached'})]
    assert page.called('wait_for_function') == [((), {'expression': 'window.ready', 'polling': 100})]
    assert page.called('wait_for_timeout') == [((1500,), {})]


@pytest.mark.parametrize('value', ['networkidle0', 'networkidle2'])
def test_wait_until_deprecated_value(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, value: str
) -> None:
    """Pyppeteer's values of wait_until still work, as 'networkidle', with a deprecation warning."""
    page = FakePage()
    job = make_job(monkeypatch, page, wait_until=value)
    assert f"'wait_until: {value}' is deprecated" in caplog.text
    retrieve(job)
    assert page.called('goto')[0][1]['wait_until'] == 'networkidle'


def test_params(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage()
    job = make_job(monkeypatch, page, params={'q': 'a b', 'page': 2})
    retrieve(job)
    assert page.called('goto')[0][0] == (f'{URL}?q=a+b&page=2',)
    assert not page.routes  # a GET is not intercepted


def test_block_elements(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requests for the resource types in 'block_elements' are aborted, others continue."""
    page = FakePage()
    job = make_job(monkeypatch, page, block_elements=['image', 'font'])
    retrieve(job)
    outcomes = {}
    for resource_type in ('image', 'font', 'script', 'document'):
        route = FakeRoute(resource_type)
        page.routes['**/*'](route)
        outcomes[resource_type] = route.outcome
    assert outcomes == {
        'image': ('abort', {}),
        'font': ('abort', {}),
        'script': ('continue', {}),
        'document': ('continue', {}),
    }


@pytest.mark.parametrize(
    ('directives', 'message'),
    [
        ({'use_browser': 'opera'}, "'use_browser' of job 0: 'opera' is not 'firefox', 'webkit', 'chrome...' or"),
        ({'http_credentials': 'user:pass:word'}, "'http_credentials' of job 0: must be in the format username:"),
        ({'block_elements': ['image', 'imgs']}, "'block_elements' of job 0: unknown resource type 'imgs'"),
        ({'wait_for_selector': ['#price', 5]}, "'wait_for_selector' of job 0: a list can only contain strings or"),
        ({'wait_for_timeout': True}, "'wait_for_timeout' of job 0: must be a number of seconds; found True"),
        ({'wait_for': '#price'}, "'wait_for' of job 0: deprecated; replace it with 'wait_for_selector'"),
    ],
    ids=['use_browser', 'http_credentials', 'block_elements', 'wait_for_selector', 'wait_for_timeout', 'wait_for'],
)
def test_invalid_directive_value(directives: dict[str, Any], message: str) -> None:
    """Values that the directives' types allow but that cannot work are rejected when the jobs file is loaded."""
    with pytest.raises(ValueError, match=re.escape(message)):
        JobBase.unserialize({'url': URL, 'use_browser': True, **directives})


@pytest.mark.parametrize(
    'http_credentials', ['user:pass', 'https://user:pass@example.com'], ids=['user:password', 'url']
)
def test_valid_http_credentials(http_credentials: str) -> None:
    JobBase.unserialize({'url': URL, 'use_browser': True, 'http_credentials': http_credentials})


def test_wait_for_navigation_deprecated(caplog: pytest.LogCaptureFixture) -> None:
    """Pyppeteer's wait_for_navigation still works, as wait_for_url, with a deprecation warning."""
    job = JobBase.unserialize({'url': URL, 'use_browser': True, 'wait_for_navigation': f'{URL}done'})
    assert "'wait_for_navigation' is deprecated" in caplog.text
    assert isinstance(job, BrowserJob)
    assert (job.wait_for_url, job.wait_for_navigation) == (f'{URL}done', None)
    job = JobBase.unserialize(
        {'url': URL, 'use_browser': True, 'wait_for_navigation': f'{URL}old', 'wait_for_url': f'{URL}new'}
    )
    assert isinstance(job, BrowserJob)
    assert job.wait_for_url == f'{URL}new'


@pytest.mark.parametrize(
    ('landing_url', 'url', 'expected'),
    [
        (f'{URL}landing;token=abc123', f'{URL}data?token={{token}}', f'{URL}data?token=abc123'),
        (f'{URL}landing;token=abc123;sid=x9', f'{URL}data?t={{token}}&s={{sid}}', f'{URL}data?t=abc123&s=x9'),
        (f'{URL}landing', f'{URL}data', f'{URL}data'),
    ],
    ids=['one-param', 'two-params', 'no-params'],
)
def test_initialization_url(monkeypatch: pytest.MonkeyPatch, landing_url: str, url: str, expected: str) -> None:
    """The ';'-separated parameters of the URL that initialization_url lands on are substituted into 'url'."""
    page = FakePage(responses=[FakeResponse(), FakeResponse()], url_after_goto=landing_url)
    job = make_job(monkeypatch, page, url=url, initialization_url=f'{URL}login')
    retrieve(job)
    assert [args[0] for args, _ in page.called('goto')] == [f'{URL}login', expected]


def test_initialization_url_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage(responses=[FakeResponse()], url_after_goto=f'{URL}landing')
    job = make_job(monkeypatch, page, url=f'{URL}data?token={{token}}', initialization_url=f'{URL}login')
    with pytest.raises(ValueError, match="did not find key 'token'"):
        retrieve(job)


def test_initialization_url_no_response(monkeypatch: pytest.MonkeyPatch) -> None:
    job = make_job(monkeypatch, FakePage(responses=[None]), initialization_url=f'{URL}login')
    with pytest.raises(BrowserResponseError, match='on initialization'):
        retrieve(job)


# --- CDP browser cache -----------------------------------------------------------------------------------------------


class FakeCdpConnection:
    """Fake of a Playwright instance whose chromium.connect_over_cdp() hands out new fake browsers."""

    def __init__(self) -> None:
        self.connected: list[FakeCachedBrowser] = []
        self.chromium = self

    def connect_over_cdp(self, cdp_url: str, **_kwargs: Any) -> FakeCachedBrowser:
        browser = FakeCachedBrowser()
        self.connected.append(browser)
        return browser

    def __enter__(self) -> Self:
        """Enter the context."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Exit the context."""

    def stop(self) -> None:
        pass


class FakeCachedBrowser:
    def __init__(self) -> None:
        self.connection: bool | Exception = True
        self.closed = False

    def is_connected(self) -> bool:
        if isinstance(self.connection, Exception):
            raise self.connection
        return self.connection

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def cdp_connection(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeCdpConnection]:
    """A fake CDP connection, with the thread-local CDP cache emptied before and after the test."""
    monkeypatch.delenv('WEBCHANGES_BROWSER_CDP_CACHE', raising=False)
    _browser._close_current_thread_cdp_cache()
    yield FakeCdpConnection()
    _browser._close_current_thread_cdp_cache()


@pytest.mark.parametrize('stale', [False, RuntimeError('Target closed')], ids=['disconnected', 'is_connected-raises'])
def test_cdp_cache_reconnects_stale_browser(cdp_connection: FakeCdpConnection, stale: bool | Exception) -> None:
    """A cached browser that is no longer connected is dropped, closed, and replaced by a new connection."""
    cdp_url = 'ws://127.0.0.1:1/devtools/browser'
    with ExitStack() as stack:
        _p, first, from_cache = _browser._acquire_cdp_browser(cdp_url, stack, lambda: cdp_connection)
        assert from_cache is False
        cdp_connection.connected[0].connection = stale
        _p, second, from_cache = _browser._acquire_cdp_browser(cdp_url, stack, lambda: cdp_connection)
    assert from_cache is False
    assert second is not first
    assert cdp_connection.connected[0].closed
    assert _browser._cdp_cache.browsers == {cdp_url: second}


def test_cdp_cache_disabled(cdp_connection: FakeCdpConnection, monkeypatch: pytest.MonkeyPatch) -> None:
    """With WEBCHANGES_BROWSER_CDP_CACHE=0, each call connects anew and nothing is cached."""
    monkeypatch.setenv('WEBCHANGES_BROWSER_CDP_CACHE', '0')
    cdp_url = 'ws://127.0.0.1:1/devtools/browser'
    with ExitStack() as stack:
        results = [_browser._acquire_cdp_browser(cdp_url, stack, lambda: cdp_connection) for _ in range(2)]
    assert [from_cache for _p, _browser_, from_cache in results] == [False, False]
    assert len(cdp_connection.connected) == 2
    assert _browser._cdp_cache.browsers == {}
    assert _browser._cdp_cache.playwright is None
