"""UrlJob — retrieve a URL from a web server."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

__lazy_modules__ = [
    'datetime',
    'email.utils',
    'ftplib',
    'html',
    'html2text',
    'importlib.util',
    'json',
    'pathlib',
    're',
    'ssl',
    'time',
    'urllib.parse',
]

import html
import importlib.util
import json
import logging
import re
import ssl
import sys
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from ftplib import FTP
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit

import html2text

from webchanges.filters import FilterBase
from webchanges.jobs._base import CHARSET_RE, UrlJobBase
from webchanges.jobs._exceptions import EMPTY_RESPONSE_STATUS_CODE, NotModifiedError, TransientHTTPError
from webchanges.util import missing_dependency

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from httpx import Headers
    from requests.adapters import HTTPAdapter

    from webchanges.handler import JobState

# The fallback assignments below are hidden from the type checker behind `if not TYPE_CHECKING`. Otherwise the type
# checker infers the union of both bindings (e.g. `<module 'httpx'> | None`), and every reference to a module
# attribute — including in annotations such as `httpx.Response`, which cannot be guarded at runtime — is reported as
# unresolved. Hiding the fallback keeps the module type, which is what these code paths are guarded to run under.
try:
    import httpx
except ImportError:  # pragma: no cover
    if not TYPE_CHECKING:
        httpx = None

if httpx is not None:
    try:
        import h2
    except ImportError:  # pragma: no cover
        h2 = None

# The optional HTTP clients requests and curl_cffi are imported only by the code paths that use them (see
# missing_dependency() in webchanges/util.py); their exceptions are recognized via sys.modules, as they can only have
# been raised if the client was imported.

logger = logging.getLogger(__name__)

# HTTP-version directive mappings.
# httpx supports only HTTP/1.1 and HTTP/2; curl_cffi (via libcurl) supports the full set.
_HTTPX_HTTP_VERSIONS: dict[str, tuple[bool, bool]] = {
    # value -> (http1, http2)
    'v1': (True, False),
    'v2': (True, True),
}
_CURL_CFFI_HTTP_VERSIONS: tuple[str, ...] = ('v1', 'v2', 'v2tls', 'v2_prior_knowledge', 'v3', 'v3only')

# Waits between the attempts made by the 'retries' directive (seconds): exponential backoff (1, 2, 4, ...) up to
# RETRY_BACKOFF_MAX, or the server's Retry-After (on a 429 or 503) up to RETRY_AFTER_MAX, so a job can't stall a run.
RETRY_BACKOFF_MAX = 30.0
RETRY_AFTER_MAX = 60.0


def weak_dh_requests_adapter(verify: bool) -> HTTPAdapter:
    """A requests transport adapter accepting a server's weak (1024-bit) Diffie-Hellman key.

    Its SSL context lowers the OpenSSL security level to 1 (the 'ignore_dh_key_too_small' directive). Works with both
    urllib3 1.x and 2.x.

    :param verify: Whether certificates are verified (i.e. the job has no 'ssl_no_verify').
    :returns: The adapter, to be mounted on the session for 'https://'.
    """
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context

    context = create_urllib3_context(
        ciphers='DEFAULT@SECLEVEL=1', cert_reqs=ssl.CERT_REQUIRED if verify else ssl.CERT_NONE
    )
    if not verify:
        context.check_hostname = False

    class WeakDHAdapter(HTTPAdapter):
        def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
            kwargs['ssl_context'] = context
            super().init_poolmanager(*args, **kwargs)

        def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:  # noqa: ANN401
            proxy_kwargs['ssl_context'] = context
            return super().proxy_manager_for(proxy, **proxy_kwargs)

    return WeakDHAdapter()


def retry_after_seconds(value: str | None) -> float | None:
    """Converts the value of an HTTP Retry-After header, either a number of seconds or an HTTP date, into seconds.

    :param value: The value of the header, if any.
    :returns: The number of seconds to wait (not negative), or None if there is no (valid) value.
    """
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        logger.debug('Ignoring unparseable Retry-After header %r', value)
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max((retry_at - datetime.now(UTC)).total_seconds(), 0.0)


class _ClientErrors(NamedTuple):
    """The exception classes of an HTTP client that the ``ignore_*`` directives silence."""

    timeout: type[Exception]
    connection: type[Exception]
    too_many_redirects: type[Exception]
    incomplete_read: type[Exception] | tuple[type[Exception], ...]
    http_status: type[Exception]


def _client_errors(exception: Exception) -> _ClientErrors | None:
    """The exception classes of the HTTP client that raised the exception.

    A :py:class:`TransientHTTPError` is attributed to the first client imported of httpx, requests and curl_cffi.

    :param exception: The exception.
    :returns: The client's exception classes, or None if the exception is not from an HTTP client.
    """
    # An exception of the optional HTTP clients can only have been raised if that client was imported
    if httpx and isinstance(exception, (httpx.HTTPError, TransientHTTPError)):  # ty: ignore[redundant-condition]
        return _ClientErrors(
            httpx.TimeoutException,
            httpx.TransportError,
            httpx.TooManyRedirects,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        )
    requests = sys.modules.get('requests')
    if requests is not None and isinstance(exception, (requests.exceptions.RequestException, TransientHTTPError)):
        errors = requests.exceptions
        return _ClientErrors(
            errors.Timeout,
            errors.ConnectionError,
            errors.TooManyRedirects,
            errors.ChunkedEncodingError,
            errors.HTTPError,
        )
    errors = sys.modules.get('curl_cffi.requests.exceptions')
    if errors is not None and isinstance(exception, (errors.RequestException, TransientHTTPError)):
        return _ClientErrors(
            errors.Timeout,
            errors.ConnectionError,
            errors.TooManyRedirects,
            (errors.ChunkedEncodingError, errors.IncompleteRead),
            errors.HTTPError,
        )
    return None


def _decode_reason(reason: str | bytes) -> str:
    """Decode an HTTP reason phrase: UTF-8 (HTML5 standard), else ISO-8859-1 (legacy standard for HTML <= 4.01)."""
    if isinstance(reason, str):
        return reason
    try:
        return reason.decode()
    except UnicodeDecodeError:
        return reason.decode('iso-8859-1')


def _error_body(text: str) -> str:
    """The body of an HTTP error response, for the error message: compact JSON, HTML as text, or as is.

    :param text: The body of the response.
    :returns: The text to append to the error message.
    """
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, separators=(',', ':'))
    except json.JSONDecodeError:
        pass
    if '<title' not in text:
        return text
    parser = html2text.HTML2Text()
    parser.unicode_snob = True
    parser.body_width = 0
    parser.single_line_break = True
    parser.ignore_images = True
    return parser.handle(text.split('<title', maxsplit=1)[0] + text.split('</title>', maxsplit=1)[-1]).strip()


def _redirect_data(status_code: int, reason: str, location: str, mime_type: str, text: str) -> str:
    """The data reported for a redirect not followed ('no_redirects' directive), in the response's media type.

    :param status_code: The HTTP status code.
    :param reason: The HTTP reason phrase.
    :param location: The URL redirected to.
    :param mime_type: The media type of the response.
    :param text: The body of the response.
    :returns: The data.
    """
    if mime_type == 'text/plain':
        return f'Redirect {status_code} {reason} to {location}:\n{text}'
    if mime_type == 'text/html':
        return f'Redirect <b>{status_code} {reason}</b> to <a href="{location}">{location}</a>:<br>{text}'
    if mime_type == 'application/json':
        return f'{{"Redirect {status_code} {reason}":"{location}"}}'
    return f'Redirect {status_code} {reason} to {location}.'


class UrlJob(UrlJobBase):
    """Retrieve a URL from a web server."""

    __kind__ = 'url'

    __optional__: tuple[str, ...] = (
        'fingerprints',
        'http_client',
        'http_version',
        'ignore_dh_key_too_small',
        'ignore_incomplete_reads',
        'impersonate',
        'initialization_url',
        'no_redirects',
        'retries',
        'ssl_no_verify',
    )

    def get_location(self) -> str:
        """Get the 'location' of the job, i.e. the (user_visible) URL.

        :returns: The user_visible_url or URL of the job.
        """
        return self.user_visible_url or self.url

    def set_base_location(
        self,
        location: str,
    ) -> None:
        """Sets the job's location (command or url) to location.  Used for changing location (uuid)."""
        self.url = location
        self.guid = self.get_guid()

    def _resolve_initialization_url(self, final_url: str) -> str:
        """Resolves the main URL by substituting parameters extracted from the initialization URL's final redirect.

        Mirrors the behavior of ``initialization_url`` in BrowserJob: parses the URL params (;-separated) from the
        final redirected URL and substitutes them into ``self.url`` via str.format().

        :param final_url: The URL after the initialization request completed (after redirects).
        :returns: The resolved URL to use for the main request.
        """
        init_url_params = dict(parse_qsl(urlparse(final_url).params))
        try:
            url = self.url.format(**init_url_params)
        except KeyError as e:
            raise ValueError(
                f"Job {self.index_number}: Directive 'initialization_url' did not find key {e} to substitute in 'url'."
            ) from None
        if url != self.url:
            logger.info('Job %s: URL updated to %s', self.index_number, url)
        return url

    def _http_error_message(
        self, status_code: int, reason: str | bytes, url: object, text: str, retry_after: str | None
    ) -> str:
        """The message of an HTTP error (4xx or 5xx) response, including its body: a custom ``raise_for_status()``.

        :param status_code: The HTTP status code.
        :param reason: The HTTP reason phrase.
        :param url: The URL of the response.
        :param text: The body of the response.
        :param retry_after: The value of the response's Retry-After header, if any.
        :returns: The message, for the client's own HTTP error exception.
        :raises TransientHTTPError: If the status code is of a typically transient nature (429, 500, 502, 503, 504).
        """
        kind = 'Client' if status_code < 500 else 'Server'
        http_error_msg = f'{status_code} {kind} Error: {_decode_reason(reason)} for url: {url}'
        if status_code != 404:
            http_error_msg += f'\n{_error_body(text)}'
        if status_code in (429, 500, 502, 503, 504):
            logger.debug('Job %s: Response with %s status is transient.', self.index_number, status_code)
            raise TransientHTTPError(
                http_error_msg, status_code=status_code, retry_after=retry_after_seconds(retry_after)
            )
        return http_error_msg

    def _retrieve_httpx(
        self,
        headers: (
            Mapping[str, str] | Mapping[bytes, bytes] | Sequence[tuple[str, str]] | Sequence[tuple[bytes, bytes]] | None
        ),
        timeout: float | None,
    ) -> tuple[str | bytes, str, str]:
        """Retrieves the data and Etag using the HTTPX library.

        :return: The data retrieved and the ETag.
        :raises NotModifiedError: If an HTTP 304 response is received.
        """
        http1: bool = True
        if self.http_version is not None:
            if self.http_version not in _HTTPX_HTTP_VERSIONS:
                raise ValueError(
                    f"Job {self.index_number}: 'http_version: {self.http_version}' is not supported by the httpx "
                    f"HTTP client; httpx only supports 'v1' and 'v2'. Use 'http_client: curl_cffi' for other "
                    f'HTTP versions ( {self.get_indexed_location()} ).'
                )
            http1, http2 = _HTTPX_HTTP_VERSIONS[self.http_version]
            if http2 and h2 is None:
                raise ImportError(
                    f"Job {self.index_number}: 'http_version: v2' requires the 'h2' package, which is not installed. "
                    f"Please install it using e.g. 'uv pip install h2' ( {self.get_indexed_location()} )."
                )
            logger.info(
                'Job %s: Using the HTTPX HTTP client library with http_version=%s', self.index_number, self.http_version
            )
        else:
            http2: bool = h2 is not None
            if http2:
                logger.info('Job %s: Using the HTTPX HTTP client library with HTTP/2 support', self.index_number)
            else:
                logger.info(
                    'Job %s: Using the HTTPX HTTP client library (HTTP/2 support is not available '
                    'since h2 is not installed)',
                    self.index_number,
                )

        proxy = self.get_proxy()
        if proxy is not None:
            logger.debug('Job %s: Proxy: %s', self.index_number, proxy)

        if self.fingerprints:
            logger.warning(
                "Job %s: 'fingerprints' is only supported with 'http_client: curl_cffi'; ignoring the directive.",
                self.index_number,
            )

        if self.ignore_dh_key_too_small:
            logger.debug(
                'Lowering the OpenSSL security level to 1 so that a weak (1024-bit) Diffie-Hellman key is accepted'
            )
            # httpx's own context (its CA certificates, ssl_no_verify honored), as a bare SSLContext verifies nothing
            context: ssl.SSLContext | str | bool = httpx.create_ssl_context(verify=not self.ssl_no_verify)
            context.set_ciphers('DEFAULT@SECLEVEL=1')
        else:
            context = not self.ssl_no_verify

        with httpx.Client(
            headers=headers,
            cookies=self.get_cookies(),
            verify=context,
            http1=http1,
            http2=http2,
            proxy=proxy,
            timeout=timeout,
            follow_redirects=(not self.no_redirects),
        ) as http_client:
            url = self.url
            if self.initialization_url:
                logger.info('Job %s: Initializing by navigating to %s', self.index_number, self.initialization_url)
                init_response = http_client.get(self.initialization_url)
                url = self._resolve_initialization_url(str(init_response.url))

            try:
                response = http_client.request(
                    method=self.method,  # ty:ignore[invalid-argument-type]
                    url=url,
                    # data is already serialized to str by main_thread_enter; httpx deprecated data= for raw content
                    content=self.data,
                    params=self.params,
                )
            except httpx.HTTPError as e:
                logger.info('Job %s: httpx error: %s', self.index_number, e)
                raise
        logger.debug('Job %s: Response headers: %s', self.index_number, response.headers)

        if 400 <= response.status_code < 600:
            # https://www.python-httpx.org/exceptions/
            http_error_msg = self._http_error_message(
                response.status_code,
                response.reason_phrase,
                response.url,
                response.text,
                response.headers.get('Retry-After'),
            )
            raise httpx.HTTPStatusError(http_error_msg, request=response.request, response=response)

        if response.status_code == 304:
            logger.debug('Job %s: Intercepted response with %s status', self.index_number, response.status_code)
            raise NotModifiedError(response.status_code)

        # Save ETag from response to be used as If-None-Match header in future requests
        if not response.history:  # no redirects
            etag = response.headers.get('ETag', '')
        else:
            logger.info('Job %s: ETag not captured as response was redirected to %s', self.index_number, response.url)
            etag = ''
        # Save the media type (fka MIME type)
        mime_type = response.headers.get('Content-Type', '').split(';')[0]

        if FilterBase.filter_chain_needs_bytes(self.filters):  # ty:ignore[invalid-argument-type]
            return response.content, etag, mime_type

        if self.encoding:
            response.encoding = self.encoding

        if self.no_redirects and response.is_redirect:
            data = _redirect_data(
                response.status_code, response.reason_phrase, response.headers['Location'], mime_type, response.text
            )
        else:
            data = response.text

        return data, etag, mime_type

    def _retrieve_requests(
        self, headers: Mapping[str, str | bytes] | None, timeout: float | None
    ) -> tuple[str | bytes, str, str]:
        """Retrieves the data and Etag using the requests library.

        :return: The data retrieved and the ETag.
        :raises NotModifiedError: If an HTTP 304 response is received.
        """
        import requests  # availability already checked by retrieve()
        import urllib3
        import urllib3.exceptions

        logger.info('Job %s: Using the requests HTTP client library', self.index_number)
        proxy_str = self.get_proxy()
        if proxy_str is not None:
            scheme = urlsplit(self.url).scheme
            proxies = {scheme: proxy_str}
            logger.debug('Job %s: Proxies: %s', self.index_number, proxies)
        else:
            proxies = None

        if self.ssl_no_verify:
            # required to suppress warnings with 'ssl_no_verify: true'
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if self.fingerprints:
            logger.warning(
                "Job %s: 'fingerprints' is only supported with 'http_client: curl_cffi'; ignoring the directive.",
                self.index_number,
            )

        with requests.Session() as session:
            if self.ignore_dh_key_too_small:
                logger.debug(
                    'Lowering the OpenSSL security level to 1 so that a weak (1024-bit) Diffie-Hellman key is accepted'
                )
                session.mount('https://', weak_dh_requests_adapter(verify=not self.ssl_no_verify))
            if headers:
                session.headers.update(headers)
            if cookies := self.get_cookies():
                session.cookies.update(cookies)
            if proxies:
                session.proxies.update(proxies)
            session.verify = not self.ssl_no_verify

            url = self.url
            if self.initialization_url:
                logger.info('Job %s: Initializing by navigating to %s', self.index_number, self.initialization_url)
                init_response = session.get(self.initialization_url, timeout=timeout)
                url = self._resolve_initialization_url(str(init_response.url))

            response = session.request(
                method=self.method,  # ty:ignore[invalid-argument-type]
                url=url,
                params=self.params,
                data=self.data,
                timeout=timeout,
                allow_redirects=(not self.no_redirects),
            )

        if 400 <= response.status_code < 600:
            # https://requests.readthedocs.io/en/master/_modules/requests/models/#Response.raise_for_status
            http_error_msg = self._http_error_message(
                response.status_code,
                response.reason,
                response.url,
                response.text,
                response.headers.get('Retry-After'),
            )
            raise requests.HTTPError(http_error_msg, response=response)

        if response.status_code == 304:
            logger.debug('Job %s: Intercepted response with %s status', self.index_number, response.status_code)
            raise NotModifiedError(response.status_code)

        # Save ETag from response to be used as If-None-Match header in future requests
        if not response.history:  # no redirects
            etag = response.headers.get('ETag', '')
        else:
            logger.info('Job %s: ETag not captured as response was redirected to %s', self.index_number, response.url)
            etag = ''
        # Save the media type (fka MIME type)
        mime_type = response.headers.get('Content-Type', '').split(';')[0]

        if FilterBase.filter_chain_needs_bytes(self.filters):  # ty:ignore[invalid-argument-type]
            return response.content, etag, mime_type

        if self.encoding:
            response.encoding = self.encoding
        elif response.encoding == 'ISO-8859-1' and not CHARSET_RE.match(response.headers.get('Content-type', '')):
            # If the Content-Type header contains text and no explicit charset is present in the HTTP headers requests
            # follows RFC 2616 and defaults encoding to ISO-8859-1, but IRL this is often wrong; the below updates it
            # with whatever is detected by the charset_normalizer or chardet libraries used in requests
            # (see https://requests.readthedocs.io/en/latest/user/advanced/#encodings)
            logger.debug(
                'Job %s: Encoding updated to %s from %s',
                self.index_number,
                response.apparent_encoding,
                response.encoding,
            )
            response.encoding = response.apparent_encoding

        if self.no_redirects and response.is_redirect:
            data = _redirect_data(
                response.status_code, response.reason, response.headers['Location'], mime_type, response.text
            )
        else:
            data = response.text

        return data, etag, mime_type

    def _retrieve_curl_cffi(
        self, headers: Mapping[str, str | bytes] | None, timeout: float | None
    ) -> tuple[str | bytes, str, str]:
        """Retrieves the data, Etag, and media type using the curl_cffi library (browser TLS/JA3 impersonation).

        :return: The data retrieved, the ETag and media type.
        :raises NotModifiedError: If an HTTP 304 response is received.
        """
        from curl_cffi import requests as curl_cffi_requests  # availability already checked by retrieve()
        from curl_cffi.requests import exceptions as curl_cffi_exceptions

        impersonate = self.impersonate or 'chrome'
        logger.info(
            'Job %s: Using the curl_cffi HTTP client library (browser TLS impersonation: %s)',
            self.index_number,
            impersonate,
        )
        proxy_str = self.get_proxy()
        if proxy_str is not None:
            scheme = urlsplit(self.url).scheme
            proxies: dict[str, str] | None = {scheme: proxy_str}
            logger.debug('Job %s: Proxies: %s', self.index_number, proxies)
        else:
            proxies = None

        if self.ignore_dh_key_too_small:
            logger.warning(
                'Job %s: ignore_dh_key_too_small is not supported with the curl_cffi HTTP client '
                'library (TLS ciphers are fixed by the impersonated browser profile); ignoring the directive.',
                self.index_number,
            )

        session_kwargs: dict[str, Any] = {
            'headers': headers,
            'cookies': self.get_cookies(),
            'proxies': proxies,
            'verify': (not self.ssl_no_verify),
            'timeout': timeout,
            'impersonate': impersonate,
        }
        if self.http_version is not None:
            if self.http_version not in _CURL_CFFI_HTTP_VERSIONS:
                raise ValueError(
                    f"Job {self.index_number}: 'http_version: {self.http_version}' is not a valid value; expected one "
                    f'of {_CURL_CFFI_HTTP_VERSIONS} ( {self.get_indexed_location()} ).'
                )
            session_kwargs['http_version'] = self.http_version
            logger.info('Job %s: curl_cffi http_version=%s', self.index_number, self.http_version)

        if self.fingerprints:
            allowed_fp_keys = {'ja3', 'akamai', 'extra_fp'}
            unknown_fp_keys = set(self.fingerprints) - allowed_fp_keys
            if unknown_fp_keys:
                raise ValueError(
                    f"Job {self.index_number}: 'fingerprints' contains unknown key(s) {sorted(unknown_fp_keys)}; "
                    f'expected any of {sorted(allowed_fp_keys)} ( {self.get_indexed_location()} ).'
                )
            for key in allowed_fp_keys:
                if key in self.fingerprints:
                    session_kwargs[key] = self.fingerprints[key]
            logger.info('Job %s: curl_cffi fingerprints applied: %s', self.index_number, sorted(self.fingerprints))

        with curl_cffi_requests.Session(**session_kwargs) as session:
            url = self.url
            if self.initialization_url:
                logger.info('Job %s: Initializing by navigating to %s', self.index_number, self.initialization_url)
                init_response = session.get(self.initialization_url)
                url = self._resolve_initialization_url(str(init_response.url))

            response = session.request(
                method=self.method,
                url=url,
                params=self.params,
                data=self.data,
                allow_redirects=(not self.no_redirects),
            )

        if 400 <= response.status_code < 600:
            http_error_msg = self._http_error_message(
                response.status_code,
                response.reason,
                response.url,
                response.text,
                response.headers.get('Retry-After'),
            )
            raise curl_cffi_exceptions.HTTPError(http_error_msg, response=response)

        if response.status_code == 304:
            logger.debug('Job %s: Intercepted response with %s status', self.index_number, response.status_code)
            raise NotModifiedError(response.status_code)

        # Save ETag from response to be used as If-None-Match header in future requests
        if not response.history:  # no redirects
            etag = response.headers.get('ETag', '')
        else:
            logger.info('Job %s: ETag not captured as response was redirected to %s', self.index_number, response.url)
            etag = ''
        # Save the media type (fka MIME type)
        mime_type = response.headers.get('Content-Type', '').split(';')[0]

        if FilterBase.filter_chain_needs_bytes(self.filters):  # ty:ignore[invalid-argument-type]
            return response.content, etag, mime_type

        if self.encoding:
            response.encoding = self.encoding
        # Note: curl_cffi's Response has no apparent_encoding, so we can't replicate the requests-library
        # ISO-8859-1 RFC 2616 override here. curl_cffi's encoding detection is libcurl-driven and reliable enough
        # in practice.

        is_redirect = 300 <= response.status_code < 400 and 'Location' in response.headers
        if self.no_redirects and is_redirect:
            data = _redirect_data(
                response.status_code, response.reason, response.headers['Location'], mime_type, response.text
            )
        else:
            data = response.text

        return data, etag, mime_type

    def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data, ETag and media type.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved, the ETag, and the media type (fka MIME type)
        :raises NotModifiedError: If an HTTP 304 response is received.
        """
        if self._delay:
            logger.debug('Job %s: Sleeping %ss (same_site_delay directive)', self.index_number, self._delay)
            time.sleep(self._delay)

        scheme = urlparse(self.url).scheme
        if scheme == 'file':
            return self._retrieve_file()
        if scheme == 'ftp':
            return self._retrieve_ftp()

        headers = self.get_headers(job_state, include_cookies=False)
        self._prepare_request_data(headers)

        # if self.headers:
        #     self.add_custom_headers(headers)

        # cookiejar (called by requests) expects strings or bytes-like objects; PyYAML will try to guess int etc.
        if self.timeout is None:
            # default timeout
            timeout: float | None = 60.0
        elif self.timeout == 0:
            # never timeout
            timeout = None
        else:
            timeout = self.timeout

        logger.info('Job %s: Sending %s request to %s', self.index_number, self.method, self.url)
        logger.debug('Job %s: Headers: %s', self.index_number, headers)
        logger.debug('Job %s: Cookies: %s', self.index_number, self.cookies)

        retrieve_with_client = self._select_http_client(job_state)
        data, etag, mime_type = self.retrieve_with_retries(retrieve_with_client, headers, timeout)

        # Note: the empty_as_error check is made by JobState.process(), which applies it to every job kind.

        # If no name directive is given, set it to the title element if found in HTML or XML truncated to 60 characters
        if not self.name and isinstance(data, str):
            title = re.search(r'<title.*?>(.+?)</title>', data)
            if title:
                self.name = html.unescape(title.group(1))[:60]

        return data, etag, mime_type

    def _retrieve_file(self) -> tuple[str | bytes, str, str]:
        """Read a local file (file URI scheme).

        :returns: The data read, an empty ETag, and the media type.
        """
        logger.info('Job %s: Using local filesystem (file URI scheme)', self.index_number)

        if sys.platform == 'win32':
            filename = Path(str(urlparse(self.url).path).lstrip('/'))
        else:
            filename = Path(str(urlparse(self.url).path))

        if FilterBase.filter_chain_needs_bytes(self.filters):  # ty:ignore[invalid-argument-type]
            return filename.read_bytes(), '', 'application/octet-stream'
        return filename.read_text(), '', 'text/plain'

    def _retrieve_ftp(self) -> tuple[str | bytes, str, str]:
        """Download a file from an FTP server, logging in anonymously unless the URL has credentials.

        :returns: The data downloaded, an empty ETag, and the media type.
        """
        url = urlparse(self.url)
        username = url.username or 'anonymous'
        password = url.password or 'anonymous'

        with FTP(  # noqa: S321 FTP-related functions are being called. FTP is considered insecure.
            str(url.hostname),
            str(username),
            str(password),
            timeout=self.timeout,
        ) as ftp:
            if FilterBase.filter_chain_needs_bytes(self.filters):  # ty:ignore[invalid-argument-type]
                data_bytes = b''

                def callback_bytes(dt: bytes) -> None:
                    """Handle FTP callback."""
                    nonlocal data_bytes
                    data_bytes += dt

                ftp.retrbinary(f'RETR {url.path}', callback_bytes)

                return data_bytes, '', 'application/octet-stream'
            data_list: list[str] = []

            def callback(dt: str) -> None:
                """Handle FTP callback."""
                data_list.append(dt)

            ftp.retrlines(f'RETR {url.path}', callback)

            return '\n'.join(data_list), '', 'text/plain'

    def _prepare_request_data(self, headers: Headers) -> None:
        """Serialize the 'data' directive and set the default method and Content-Type header.

        :param headers: The request headers, updated in place.
        :raises TypeError: If 'data' is not a string, dictionary or list.
        """
        if self.data is None:
            if self.method is None:
                self.method = 'GET'
            return

        if self.method is None:
            self.method = 'POST'
        if 'Content-Type' not in headers:
            if self.data_as_json:
                headers['Content-Type'] = 'application/json'
            else:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
        if isinstance(self.data, (dict, list)):
            if self.data_as_json:
                self.data = json.dumps(self.data, ensure_ascii=False, separators=(',', ':'))
            else:
                self.data = urlencode(self.data)
        elif not isinstance(self.data, str):
            raise TypeError(
                f"Job {self.index_number}: Directive 'data' needs to be a string, dictionary or list; "
                f'found a {type(self.data).__name__} ( {self.get_indexed_location()} ).'
            )

    def _select_http_client(self, job_state: JobState) -> Callable[..., tuple[str | bytes, str, str]]:
        """Select the HTTP client: per 'http_client', else the first of httpx, requests and curl_cffi installed.

        :param job_state: The JobState object, which records the client used.
        :returns: The method retrieving the data with that client.
        :raises ValueError: If the client is not supported, or does not support the 'http_version' directive.
        """
        if self.http_client == 'curl_cffi' or (
            not self.http_client
            and not httpx  # ty: ignore[redundant-condition]
            and importlib.util.find_spec('requests') is None
        ):
            try:
                from curl_cffi import requests as curl_cffi_requests  # noqa: F401 imported but unused (checks it loads)
            except ImportError as e:
                raise missing_dependency(
                    e,
                    'curl_cffi',
                    used_by=(
                        "the 'http_client: curl_cffi' job directive"
                        if self.http_client == 'curl_cffi'
                        else "retrieving the URL (as neither 'httpx' nor 'requests' is installed)"
                    ),
                    extra='curl_cffi',
                    location=self.get_indexed_location(),
                ) from e
            job_state._http_client_used = 'curl_cffi'
            return self._retrieve_curl_cffi
        if self.http_client == 'requests' or not httpx:  # ty: ignore[redundant-condition]
            try:
                import requests  # noqa: F401 imported but unused (checks that it loads)
            except ImportError as e:
                raise missing_dependency(
                    e,
                    'requests',
                    used_by=(
                        "the 'http_client: requests' job directive"
                        if self.http_client == 'requests'
                        else "retrieving the URL (as 'httpx' is not installed)"
                    ),
                    extra='requests',
                    location=self.get_indexed_location(),
                ) from e
            if self.http_version is not None:
                raise ValueError(
                    f"Job {job_state.job.index_number}: 'http_version' is not supported by the 'requests' HTTP "
                    f"client (HTTP/1.1 only). Use 'http_client: httpx' or 'http_client: curl_cffi' "
                    f'( {self.get_indexed_location()} ).'
                )
            job_state._http_client_used = 'requests'
            return self._retrieve_requests
        if not self.http_client or self.http_client == 'httpx':
            if httpx is None:  # pragma: no cover  # only reachable with an explicit 'http_client: httpx'
                raise missing_dependency(
                    "No module named 'httpx'",
                    'httpx',
                    used_by="the 'http_client: httpx' job directive",
                    location=self.get_indexed_location(),
                )
            job_state._http_client_used = 'httpx'
            return self._retrieve_httpx
        raise ValueError(
            f"Job {job_state.job.index_number}: http_client '{self.http_client}' is not supported; cannot run job "
            f'( {self.get_indexed_location()} )'
        )

    # def add_custom_headers(self, headers: dict[str, Any]) -> None:
    #     """
    #     Adds custom request headers from the job list (URLs) to the pre-filled dictionary `headers`.
    #     Pre-filled values of conflicting header keys (case-insensitive) are overwritten by custom value.
    #     """
    #     headers_to_remove = [x for x in headers if x.lower() in (y.lower() for y in self.headers)]
    #     for header in headers_to_remove:
    #         headers.pop(header, None)
    #     headers.update(self.headers)

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        # An exception of the optional HTTP clients can only have been raised if that client was imported
        requests = sys.modules.get('requests')
        curl_cffi_exceptions = sys.modules.get('curl_cffi.requests.exceptions')
        if (
            (
                httpx  # ty: ignore[redundant-condition]
                and isinstance(exception, (httpx.HTTPError, httpx.InvalidURL, httpx.CookieConflict, httpx.StreamError))
            )
            or (requests is not None and isinstance(exception, requests.exceptions.RequestException))
            or (curl_cffi_exceptions is not None and isinstance(exception, curl_cffi_exceptions.RequestException))
        ):
            # Instead of a full traceback, just show the error
            exception_str = str(exception).strip()
            if self.proxy and (
                (httpx and isinstance(exception, httpx.TransportError))  # ty: ignore[redundant-condition]
                or any(
                    exception_str.startswith(error_string)
                    for error_string in (
                        '[SSL:',
                        # https://mariadb.com/kb/en/operating-system-error-codes/
                        '[Errno 103]',  # ECONNABORTED
                        '[Errno 104]',  # ECONNRESET
                        '[Errno 108]',  # ESHUTDOWN
                        '[Errno 110]',  # ETIMEDOUT
                        '[Errno 111]',  # ECONNREFUSED
                        '[Errno 112]',  # EHOSTDOWN
                        '[Errno 113]',  # EHOSTUNREACH
                        # https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--9000-11999-
                        '[WinError 10053]',  # WSAECONNABORTED
                        '[WinError 10054]',  # WSAECONNRESET
                        '[WinError 10060]',  # WSAETIMEDOUT
                        '[WinError 10061]',  # WSAECONNREFUSED
                        '[WinError 10062]',  # WSAELOOP
                        '[WinError 10063]',  # WSAENAMETOOLONG
                        '[WinError 10064]',  # WSAEHOSTDOWN
                        '[WinError 10065]',  # WSAEHOSTUNREACH
                    )
                )
            ):
                exception_str += f'\n\n(Job has proxy {self.proxy})'
            return exception_str
        return super().format_error(exception, tb)

    def retrieve_with_retries(
        self,
        retrieve_with_client: Callable[..., tuple[str | bytes, str, str]],
        headers: Any,  # noqa: ANN401 Dynamically typed expressions Any are disallowed
        timeout: float | None,
    ) -> tuple[str | bytes, str, str]:
        """Retrieves the data with the HTTP client, retrying transient failures per the 'retries' directive.

        See :py:meth:`is_transient_error`.

        :param retrieve_with_client: The method retrieving the data with the selected HTTP client.
        :param headers: The request headers.
        :param timeout: The request timeout.
        :returns: The data retrieved, the ETag, and the media type (fka MIME type).
        """
        attempts = 1 + max(self.retries or 0, 0)
        for attempt in range(1, attempts):
            try:
                return retrieve_with_client(headers=headers, timeout=timeout)
            except Exception as e:
                if not self.is_transient_error(e):
                    raise
                wait = self.retry_wait(e, attempt)
                logger.info(
                    'Job %s: Attempt %s of %s failed (%s: %s); retrying in %g seconds (retries directive)',
                    self.index_number,
                    attempt,
                    attempts,
                    type(e).__name__,
                    e,
                    wait,
                )
                time.sleep(wait)
        return retrieve_with_client(headers=headers, timeout=timeout)

    @staticmethod
    def is_transient_error(exception: Exception) -> bool:
        """Whether a new attempt could overcome the failure (the ones retried by the 'retries' directive).

        A connection error (e.g. a connection reset by the server), a timeout, or a transient HTTP response (429, 500,
        502, 503 or 504), of any of the HTTP clients.

        :param exception: The exception.
        :returns: True if the request should be retried, False otherwise.
        """
        if isinstance(exception, TransientHTTPError):
            return exception.status_code != EMPTY_RESPONSE_STATUS_CODE
        # An exception of the optional HTTP clients can only have been raised if that client was imported
        requests = sys.modules.get('requests')
        curl_cffi_exceptions = sys.modules.get('curl_cffi.requests.exceptions')
        return bool(
            (httpx and isinstance(exception, httpx.TransportError))
            or (
                requests is not None
                and isinstance(exception, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
            )
            or (
                curl_cffi_exceptions is not None
                and isinstance(exception, (curl_cffi_exceptions.ConnectionError, curl_cffi_exceptions.Timeout))
            )
        )

    @staticmethod
    def retry_wait(exception: Exception, attempt: int) -> float:
        """The number of seconds to wait before the next attempt.

        The server's Retry-After (if any) up to RETRY_AFTER_MAX, otherwise an exponential backoff (1, 2, 4, ... seconds)
        up to RETRY_BACKOFF_MAX.

        :param exception: The exception raised by the failed attempt.
        :param attempt: The number of the failed attempt (starting at 1).
        :returns: The number of seconds to wait.
        """
        if isinstance(exception, TransientHTTPError) and exception.retry_after is not None:
            return min(exception.retry_after, RETRY_AFTER_MAX)
        return min(2.0 ** (attempt - 1), RETRY_BACKOFF_MAX)

    def ignore_error(self, exception: Exception) -> bool:
        """Determine whether the error of the job should be ignored.

        :param exception: The exception.
        :returns: True if the error should be ignored, False otherwise.
        """
        errors = _client_errors(exception)
        if errors is None:
            return False
        if self.ignore_timeout_errors and (
            isinstance(exception, errors.timeout)
            or (isinstance(exception, TransientHTTPError) and exception.status_code == 504)
        ):
            return True
        if self.ignore_connection_errors and (
            # Except the synthetic TransientHTTPError of the empty_as_error directive: the server did respond, so an
            # empty response is not a connection problem and must not be silenced by ignore_connection_errors.
            exception.status_code != EMPTY_RESPONSE_STATUS_CODE
            if isinstance(exception, TransientHTTPError)
            else isinstance(exception, errors.connection)
        ):
            return True
        if self.ignore_too_many_redirects and isinstance(exception, errors.too_many_redirects):
            return True
        # The server closed the connection before sending the complete response body.
        if self.ignore_incomplete_reads and isinstance(exception, errors.incomplete_read):
            return True
        if self.ignore_http_error_codes:
            # Not a truthiness test: a requests Response with an error status is falsy
            response = getattr(exception, 'response', None)
            if isinstance(exception, errors.http_status) and response is not None:
                return self._ignore_http_error_code(response.status_code)
            if isinstance(exception, TransientHTTPError):
                return self._ignore_http_error_code(exception.status_code)
        return False
