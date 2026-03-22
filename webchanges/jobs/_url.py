"""UrlJob — retrieve a URL from a web server."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import html
import json
import logging
import re
import ssl
import sys
import time
from ftplib import FTP
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Sequence
from urllib.parse import urlencode, urlparse, urlsplit

import html2text

from webchanges.filters import FilterBase
from webchanges.jobs._base import CHARSET_RE, UrlJobBase
from webchanges.jobs._exceptions import NotModifiedError, TransientHTTPError

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.handler import JobState

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # ty:ignore[invalid-assignment]

if httpx is not None:
    try:
        import h2
    except ImportError:  # pragma: no cover
        h2 = None  # ty:ignore[invalid-assignment]

try:
    import requests
    import urllib3
    import urllib3.exceptions
except ImportError as e:  # pragma: no cover
    requests = str(e)  # ty:ignore[invalid-assignment]
    urllib3 = str(e)  # ty:ignore[invalid-assignment]

logger = logging.getLogger(__name__)


class UrlJob(UrlJobBase):
    """Retrieve a URL from a web server."""

    __kind__ = 'url'

    __optional__: tuple[str, ...] = (
        'empty_as_transient',
        'http_client',
        'ignore_dh_key_too_small',
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
        http2: bool = h2 is not None
        if http2:
            logger.info(f'Job {self.index_number}: Using the HTTPX HTTP client library with HTTP/2 support')
        else:
            logger.info(
                f'Job {self.index_number}: Using the HTTPX HTTP client library (HTTP/2 support is not available since '
                f'h2 is not installed)'
            )

        proxy = self.get_proxy()
        if proxy is not None:
            logger.debug(f'Job {self.index_number}: Proxy: {proxy}')

        if self.ignore_dh_key_too_small:
            logger.debug(
                'Setting default cipher list to ciphers that do not make any use of Diffie Hellman Key Exchange '
                "and thus are not affected by the server's weak DH key"
            )
            context: ssl.SSLContext | str | bool = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.set_ciphers('DEFAULT@SECLEVEL=1')
        else:
            context = not self.ssl_no_verify

        with httpx.Client(
            headers=headers,
            cookies=self.cookies,
            verify=context,
            http2=http2,
            proxy=proxy,
            timeout=timeout,
            follow_redirects=(not self.no_redirects),
        ) as http_client:
            try:
                response = http_client.request(
                    method=self.method,  # ty:ignore[invalid-argument-type]
                    url=self.url,
                    data=self.data,  # ty:ignore[invalid-argument-type]
                    params=self.params,
                )
            except httpx.HTTPError as e:
                logger.info(f'Job {self.index_number}: httpx error: {e}')
                raise
        logger.debug(f'Job {self.index_number}: Response headers: {response.headers}')

        if 400 <= response.status_code < 600:
            # Custom version of request.raise_for_status() to include returned text.
            # https://www.python-httpx.org/exceptions/
            reason = response.reason_phrase

            if response.status_code < 500:
                http_error_msg = f'{response.status_code} Client Error: {reason} for url: {response.url}'
            else:
                http_error_msg = f'{response.status_code} Server Error: {reason} for url: {response.url}'

            if response.status_code != 404:
                try:
                    parsed_json = json.loads(response.text)
                    error_message = json.dumps(parsed_json, ensure_ascii=False, separators=(',', ':'))
                except json.JSONDecodeError:
                    html_text = (
                        response.text.split('<title', maxsplit=1)[0] + response.text.split('</title>', maxsplit=1)[-1]
                    )
                    parser = html2text.HTML2Text()
                    parser.unicode_snob = True
                    parser.body_width = 0
                    parser.single_line_break = True
                    parser.ignore_images = True
                    error_message = parser.handle(html_text).strip()
                http_error_msg += f'\n{error_message}'

            if response.status_code in (429, 500, 502, 503, 504):
                logger.debug(f'Job {self.index_number}: Intercepted response with {response.status_code} status')
                raise TransientHTTPError(http_error_msg, status_code=response.status_code)

            raise httpx.HTTPStatusError(http_error_msg, request=response.request, response=response)

        if response.status_code == 304:
            logger.debug(f'Job {self.index_number}: Intercepted response with {response.status_code} status')
            raise NotModifiedError(response.status_code)

        # Save ETag from response to be used as If-None-Match header in future requests
        if not response.history:  # no redirects
            etag = response.headers.get('ETag', '')
        else:
            logger.info(f'Job {self.index_number}: ETag not captured as response was redirected to {response.url}')
            etag = ''
        # Save the media type (fka MIME type)
        mime_type = response.headers.get('Content-Type', '').split(';')[0]

        if FilterBase.filter_chain_needs_bytes(self.filters):  # ty:ignore[invalid-argument-type]
            return response.content, etag, mime_type

        if self.encoding:
            response.encoding = self.encoding

        if self.no_redirects and response.is_redirect:
            new_location = response.headers['Location']
            if mime_type == 'text/plain':
                data = f'Redirect {response.status_code} {response.reason_phrase} to {new_location}:\n{response.text}'
            elif mime_type == 'text/html':
                data = (
                    f'Redirect <b>{response.status_code} {response.reason_phrase}</b> to <a href="{new_location}">'
                    f'{new_location}</a>:<br>{response.text}'
                )
            elif mime_type == 'application/json':
                data = f'{{"Redirect {response.status_code} {response.reason_phrase}":"{new_location}"}}'
            else:
                data = f'Redirect {response.status_code} {response.reason_phrase} to {new_location}.'
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
        logger.info(f'Job {self.index_number}: Using the requests HTTP client library')
        proxy_str = self.get_proxy()
        if proxy_str is not None:
            scheme = urlsplit(self.url).scheme
            proxies = {scheme: proxy_str}
            logger.debug(f'Job {self.index_number}: Proxies: {proxies}')
        else:
            proxies = None

        if self.ssl_no_verify:
            # required to suppress warnings with 'ssl_no_verify: true'
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if self.ignore_dh_key_too_small:
            # https://stackoverflow.com/questions/38015537
            logger.debug(
                'Setting default cipher list to ciphers that do not make any use of Diffie Hellman Key Exchange '
                "and thus are not affected by the server's weak DH key"
            )
            try:
                # only works with urllib3 <2.0
                urllib3.util.ssl_.DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
            except AttributeError:
                logger.error(
                    'Unable to ignore_dh_key_too_small due to bug in requests.packages.urrlib3.util.ssl.DEFAULT_CIPHERS'
                )
                logger.error('See https://github.com/psf/requests/issues/6443')

        response = requests.request(
            method=self.method,  # ty:ignore[invalid-argument-type]
            url=self.url,
            params=self.params,
            data=self.data,
            headers=headers,
            cookies=self.cookies,
            timeout=timeout,
            allow_redirects=(not self.no_redirects),
            proxies=proxies,
            verify=(not self.ssl_no_verify),
        )

        if 400 <= response.status_code < 600:
            # Custom version of request.raise_for_status() to include returned text.
            # https://requests.readthedocs.io/en/master/_modules/requests/models/#Response.raise_for_status
            if isinstance(response.reason, bytes):
                # If the reason isn't utf-8 (HTML5 standard), we fall back to iso-8859-1
                # (legacy standard for HTML <= 4.01).
                try:
                    reason = response.reason.decode()
                except UnicodeDecodeError:
                    reason = response.reason.decode('iso-8859-1')
            else:
                reason = response.reason

            if response.status_code < 500:
                http_error_msg = f'{response.status_code} Client Error: {reason} for url: {response.url}'
            else:
                http_error_msg = f'{response.status_code} Server Error: {reason} for url: {response.url}'

            if response.status_code != 404:
                try:
                    parsed_json = json.loads(response.text)
                    error_message = json.dumps(parsed_json, ensure_ascii=False, separators=(',', ':'))
                except json.JSONDecodeError:
                    html_text = (
                        response.text.split('<title', maxsplit=1)[0] + response.text.split('</title>', maxsplit=1)[-1]
                    )
                    parser = html2text.HTML2Text()
                    parser.unicode_snob = True
                    parser.body_width = 0
                    parser.single_line_break = True
                    parser.ignore_images = True
                    error_message = parser.handle(html_text).strip()
                http_error_msg += f'\n{error_message}'

            if response.status_code in (429, 500, 502, 503, 504):
                logger.debug(f'Job {self.index_number}: Response error is transient.')
                raise TransientHTTPError(http_error_msg, status_code=response.status_code)

            raise requests.HTTPError(http_error_msg, response=response)

        if response.status_code == 304:
            logger.debug(f'Job {self.index_number}: Intercepted response with {response.status_code} status')
            raise NotModifiedError(response.status_code)

        # Save ETag from response to be used as If-None-Match header in future requests
        if not response.history:  # no redirects
            etag = response.headers.get('ETag', '')
        else:
            logger.info(f'Job {self.index_number}: ETag not captured as response was redirected to {response.url}')
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
                f'Job {self.index_number}: Encoding updated to {response.apparent_encoding} from {response.encoding}'
            )
            response.encoding = response.apparent_encoding

        if self.no_redirects and response.is_redirect:
            new_location = response.headers['Location']
            if mime_type == 'text/plain':
                data = f'Redirect {response.status_code} {response.reason} to {new_location}:\n{response.text}'
            elif mime_type == 'text/html':
                data = (
                    f'Redirect <b>{response.status_code} {response.reason}</b> to <a href="{new_location}">'
                    f'{new_location}</a>:<br>{response.text}'
                )
            elif mime_type == 'application/json':
                data = f'{{"Redirect {response.status_code} {response.reason}":"{new_location}"}}'
            else:
                data = f'Redirect {response.status_code} {response.reason} to {new_location}.'
        else:
            data = response.text

        return data, etag, mime_type

    def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved, the ETag, and the media type (fka MIME type)
        :raises NotModifiedError: If an HTTP 304 response is received.
        """
        if self._delay:  # pragma: no cover  TODO not yet implemented.
            logger.debug(f'Delaying for {self._delay} seconds (duplicate network location)')
            time.sleep(self._delay)

        if urlparse(self.url).scheme == 'file':
            logger.info(f'Job {self.index_number}: Using local filesystem (file URI scheme)')

            if sys.platform == 'win32':
                filename = Path(str(urlparse(self.url).path).lstrip('/'))
            else:
                filename = Path(str(urlparse(self.url).path))

            if FilterBase.filter_chain_needs_bytes(self.filters):  # ty:ignore[invalid-argument-type]
                return filename.read_bytes(), '', 'application/octet-stream'
            return filename.read_text(), '', 'text/plain'

        if urlparse(self.url).scheme == 'ftp':
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

        headers = self.get_headers(job_state, include_cookies=False)

        if self.data is not None:
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
                    f"Job {job_state.job.index_number}: Directive 'data' needs to be a string, dictionary or list; "
                    f'found a {type(self.data).__name__} ( {self.get_indexed_location()} ).'
                )

        elif self.method is None:
            self.method = 'GET'

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

        logger.info(f'Job {self.index_number}: Sending {self.method} request to {self.url}')
        logger.debug(f'Job {self.index_number}: Headers: {headers}')
        logger.debug(f'Job {self.index_number}: Cookies: {self.cookies}')

        if self.http_client == 'requests' or not httpx:
            if isinstance(requests, str):
                message = f'Job {job_state.job.index_number} cannot be run '
                if self.http_client == 'requests':
                    message += "with 'http_client: requests "
                message += (
                    f'( {self.get_indexed_location()} ):\n{requests}\n'
                    f"Please install module using e.g. 'pip install --upgrade webchanges[requests]'."
                )
                raise ImportError(message)
            job_state._http_client_used = 'requests'
            data, etag, mime_type = self._retrieve_requests(headers=headers, timeout=timeout)
        elif not self.http_client or self.http_client == 'httpx':
            if isinstance(httpx, str):
                message = f'Job {job_state.job.index_number} cannot be run '
                if self.http_client == 'httpx':
                    message += "with 'http_client: httpx "
                message += (
                    f'( {self.get_indexed_location()} ):\n{httpx}\n'
                    f"Please install module using e.g. 'pip install --upgrade httpx[http2,zstd]'."
                )
                raise ImportError(message)
            job_state._http_client_used = 'HTTPX'
            data, etag, mime_type = self._retrieve_httpx(headers=headers, timeout=timeout)
        else:
            raise ValueError(
                f"Job {job_state.job.index_number}: http_client '{self.http_client}' is not supported; cannot run job "
                f'( {self.get_indexed_location()} )'
            )

        # If empty_as_transient is set and no data, then raise transient error
        if self.empty_as_transient and not data:
            logger.info(f'Job {self.index_number}: No data received; treating it as a transient error.')
            raise TransientHTTPError('No data received and empty_is_transient is set', status_code=999)

        # If no name directive is given, set it to the title element if found in HTML or XML truncated to 60 characters
        if not self.name and isinstance(data, str):
            title = re.search(r'<title.*?>(.+?)</title>', data)
            if title:
                self.name = html.unescape(title.group(1))[:60]

        return data, etag, mime_type

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
        if (
            httpx
            and isinstance(exception, (httpx.HTTPError, httpx.InvalidURL, httpx.CookieConflict, httpx.StreamError))
        ) or (not isinstance(requests, str) and isinstance(exception, requests.exceptions.RequestException)):
            # Instead of a full traceback, just show the error
            exception_str = str(exception).strip()
            if self.proxy and (
                (httpx and isinstance(exception, httpx.TransportError))
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
        return tb

    def ignore_error(self, exception: Exception) -> bool:
        """Determine whether the error of the job should be ignored.

        :param exception: The exception.
        :returns: True if the error should be ignored, False otherwise.
        """
        if httpx and isinstance(exception, (httpx.HTTPError, TransientHTTPError)):
            if self.ignore_timeout_errors and (
                isinstance(exception, httpx.TimeoutException)
                or (isinstance(exception, TransientHTTPError) and exception.status_code == 504)
            ):
                return True
            if self.ignore_connection_errors and isinstance(exception, (httpx.TransportError, TransientHTTPError)):
                return True
            if self.ignore_too_many_redirects and isinstance(exception, httpx.TooManyRedirects):
                return True
            if self.ignore_http_error_codes:
                if isinstance(exception, httpx.HTTPStatusError):
                    return self._ignore_http_error_code(exception.response.status_code)
                if isinstance(exception, TransientHTTPError):
                    return self._ignore_http_error_code(exception.status_code)

        elif not isinstance(requests, str) and isinstance(
            exception, (requests.exceptions.RequestException, TransientHTTPError)
        ):
            if self.ignore_timeout_errors and (
                isinstance(exception, requests.exceptions.Timeout)
                or (isinstance(exception, TransientHTTPError) and exception.status_code == 504)
            ):
                return True
            if self.ignore_connection_errors and (
                isinstance(exception, (requests.exceptions.ConnectionError, TransientHTTPError))
            ):
                return True
            if self.ignore_too_many_redirects and isinstance(exception, requests.exceptions.TooManyRedirects):
                return True
            if self.ignore_http_error_codes:
                if isinstance(exception, requests.exceptions.HTTPError) and exception.response is not None:
                    return self._ignore_http_error_code(exception.response.status_code)
                if isinstance(exception, TransientHTTPError):
                    return self._ignore_http_error_code(exception.status_code)

        return False
