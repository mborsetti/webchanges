"""Jobs."""

import asyncio
import email.utils
import hashlib
import logging
import os
import re
import subprocess
import sys
import textwrap
import warnings
from ftplib import FTP
from http.client import responses as response_names
from typing import Any, AnyStr, Dict, List, Optional, TYPE_CHECKING, Tuple, Type, Union
from urllib.parse import urldefrag, urlparse, urlsplit

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from . import __user_agent__
from .filters import FilterBase
from .util import TrackSubClasses

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from .handler import JobState

# required to suppress warnings with 'ssl_no_verify: true'
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)

DEFAULT_CHROMIUM_REVISION = {
    'linux': 843831,
    'win64': 843846,
    'win32': 843832,
    'mac': 843846,
}


class NotModifiedError(Exception):
    """Exception raised on HTTP 304 responses."""
    ...


class BrowserResponseError(Exception):
    """Exception for use_browser: true jobs with error HTTP response code."""

    def __init__(self, args: tuple, status_code: int) -> None:
        Exception.__init__(self)
        self.args = args
        self.status_code = status_code

    def __str__(self) -> str:
        return (f'{self.__class__.__name__}: Received response HTTP {self.status_code} '
                f'{response_names[self.status_code]}')


class ShellError(Exception):
    """Exception for shell commands with non-zero exit code."""

    def __init__(self, result: int) -> None:
        Exception.__init__(self)
        self.result = result

    def __str__(self) -> str:
        return f'{self.__class__.__name__}: Exit status {self.result}'


class JobBase(object, metaclass=TrackSubClasses):
    __subclasses__: dict = {}

    __required__: Tuple[str] = ()
    __optional__: Tuple[str] = ()

    # PyCharm IDE compatibility
    __kind__: str = ''

    index_number: int = 0  # added at job loading

    # __required__ in derived classes
    url: Optional[str] = ''
    command: Optional[str] = ''
    use_browser: Optional[bool] = False

    # __optional__ in derived classes
    additions_only: Optional[bool] = None
    block_elements: Optional[list] = None
    chromium_revision: Optional[Union[Dict[str, Union[str, int]], Union[str, int]]] = None
    compared_versions: Optional[int] = None
    contextlines: Optional[int] = None
    cookies: Optional[Dict[str, str]] = None
    data: Optional[AnyStr] = None
    deletions_only: Optional[bool] = None
    diff_filter: Optional[str] = None
    diff_tool: Optional[str] = None
    encoding: Optional[str] = None
    filter: Optional[Union[str, List[Union[str, Dict[str, Any]]]]] = None
    headers: Optional[Dict[str, str]] = None
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    ignore_cached: Optional[bool] = None
    ignore_connection_errors: Optional[bool] = None
    ignore_http_error_codes: Optional[bool] = None
    ignore_https_errors: Optional[bool] = None
    ignore_timeout_errors: Optional[bool] = None
    ignore_too_many_redirects: Optional[bool] = None
    is_markdown: Optional[bool] = None
    loop: Optional[asyncio.AbstractEventLoop] = None
    markdown_padded_tables: Optional[bool] = None
    max_tries: Optional[int] = None
    method: Optional[str] = None
    name: Optional[str] = None
    navigate: Optional[str] = None  # backwards compatibility (deprecated)
    no_redirects: Optional[bool] = None
    note: Optional[str] = None
    ssl_no_verify: Optional[bool] = None
    switches: Optional[List[str]] = None
    timeout: Optional[int] = None
    user_data_dir: Optional[str] = None
    user_visible_url: Optional[str] = None
    wait_for: Optional[Union[int, str]] = None
    wait_for_navigation: Optional[Union[str, Tuple[str, ...]]] = None
    wait_until: Optional[str] = None

    def __init__(self, **kwargs) -> None:
        # # Set optional keys to None -- legacy (explicit declarations added to support typing)
        # for k in self.__optional__:
        #     if k not in kwargs:
        #         setattr(self, k, None)

        # Fail if any required keys are not provided
        for k in self.__required__:
            if k not in kwargs:
                raise ValueError(f"Required directive '{k}' missing: '{kwargs}' ({self.get_indexed_location()})")

        for k, v in list(kwargs.items()):
            setattr(self, k, v)

    @classmethod
    def job_documentation(cls) -> str:
        result = []
        for sc in TrackSubClasses.sorted_by_kind(cls):
            if sc.__doc__:
                result.append(f'  * {sc.__kind__} - {sc.__doc__}')
            else:
                result.append(f'  * {sc.__kind__}')

            for msg, value in (('    Required: ', sc.__required__), ('    Optional: ', sc.__optional__)):
                if value:
                    values = ('\n' + (len(msg) * ' ')).join(textwrap.wrap(', '.join(value), 79 - len(msg)))
                    result.append(f'{msg}{values}')
            result.append('')
        return '\n'.join(result)

    def get_location(self) -> str:
        raise NotImplementedError()

    def get_indexed_location(self) -> str:
        """Returns the Job's index and url/command.
        Typically used in error displays."""
        raise NotImplementedError()

    def pretty_name(self) -> str:
        raise NotImplementedError()

    def serialize(self) -> dict:
        d = {'kind': self.__kind__}
        d.update(self.to_dict())
        return d

    @classmethod
    def unserialize(cls, data: dict) -> 'JobBase':
        # Backwards compatibility with 'navigate' directive (deprecated)
        if data.get('navigate') and not data.get('use_browser'):
            warnings.warn(f"Job directive 'navigate' is deprecated: replace with 'url' and add 'use_browser: true'"
                          f' ({data})', DeprecationWarning)
            data['url'] = data.get('url', data['navigate'])
            data['use_browser'] = True

        # Backwards compatibility with 'kind' directive (deprecated)
        if 'kind' in data:
            warnings.warn(f"Job directive 'kind' is deprecated and ignored; delete from job file' ({data})",
                          DeprecationWarning)
            data.pop('kind')

        # Auto-detect the job subclass based on required directives
        matched_subclasses = [subclass for subclass in list(cls.__subclasses__.values())[1:] if
                              all(data.get(required) for required in subclass.__required__)]

        if len(matched_subclasses) == 1:
            job_subclass = matched_subclasses[0]
        elif len(matched_subclasses) > 1:
            number_matched = {}
            for match in matched_subclasses:
                number_matched[match] = [data.get(required) is not None
                                         for required in match.__required__].count(True)
            job_subclass = sorted(number_matched.items(), key=lambda x: x[1], reverse=True)[0][0]
        else:
            if len(data) == 1:
                raise ValueError(
                    f"Job directive has no value or doesn't match a job type; check for errors/typos/escaping:\n{data}")
            else:
                raise ValueError(
                    f"Job directives (with values) don't match a job type; check for errors/typos/escaping:\n{data}")

        # remove extra required directives ("falsy")
        other_subclasses = list(cls.__subclasses__.values())[1:]
        other_subclasses.remove(job_subclass)
        for other_subclass in other_subclasses:
            for k in other_subclass.__required__:
                if k not in job_subclass.__required__:
                    data.pop(k, None)

        return job_subclass.from_dict(data)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for keys in (self.__required__, self.__optional__) for k in keys
                if getattr(self, k) is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'JobBase':
        for k in data.keys():
            if k not in (cls.__required__ + cls.__optional__):
                raise ValueError(f"Job directive '{k}' is unrecognized; check for errors/typos/escaping:\n{data}")
        return cls(**{k: v for k, v in list(data.items())})

    def __repr__(self) -> str:
        return f'<{self.__kind__} {" ".join(f"{k}={v!r}" for k, v in list(self.to_dict().items()))}'

    def _set_defaults(self, defaults) -> None:
        if isinstance(defaults, dict):
            for key, value in defaults.items():
                if key in self.__optional__ and getattr(self, key) is None:
                    setattr(self, key, value)

    def with_defaults(self, config: dict) -> 'JobBase':
        new_job = JobBase.unserialize(self.serialize())
        cfg = config.get('job_defaults')
        if isinstance(cfg, dict):
            new_job._set_defaults(cfg.get(self.__kind__))
            new_job._set_defaults(cfg.get('all'))
        return new_job

    def get_guid(self) -> str:
        location = self.get_location()
        return hashlib.sha1(location.encode()).hexdigest()

    def retrieve(self, job_state: 'JobState') -> (AnyStr, str):
        """Runs job and returns data and etag"""
        raise NotImplementedError()

    def main_thread_enter(self) -> None:
        """Called from the main thread before running the job"""
        ...

    def main_thread_exit(self) -> None:
        """Called from the main thread after running the job"""
        ...

    def format_error(self, exception: Exception, tb: str) -> str:
        return tb

    def ignore_error(self, exception: Exception) -> bool:
        return False


class Job(JobBase):
    __required__ = ()
    __optional__ = ('index_number', 'name', 'note', 'additions_only', 'compared_versions', 'contextlines',
                    'deletions_only', 'diff_filter', 'diff_tool', 'filter', 'markdown_padded_tables', 'max_tries',
                    'is_markdown', 'ignore_connection_errors', 'ignore_http_error_codes', 'ignore_timeout_errors',
                    'ignore_too_many_redirects')

    def get_location(self) -> str:
        pass

    def get_indexed_location(self) -> str:
        return f'Job {self.index_number}: {self.get_location()}'

    def pretty_name(self) -> str:
        return self.name or self.get_location()

    def retrieve(self, job_state: 'JobState') -> (AnyStr, str):
        pass


CHARSET_RE = re.compile('text/(html|plain); charset=([^;]*)')


class UrlJob(Job):
    """Retrieve a URL from a web server."""

    __kind__ = 'url'

    __required__ = ('url',)
    __optional__ = ('cookies', 'data', 'encoding', 'headers', 'http_proxy', 'https_proxy', 'ignore_cached',
                    'method', 'no_redirects', 'ssl_no_verify', 'timeout', 'user_visible_url')

    def get_location(self) -> str:
        return self.user_visible_url or self.url

    def retrieve(self, job_state: 'JobState') -> (AnyStr, str):
        headers = {
            'User-Agent': __user_agent__,
        }

        proxies = {
            'http': os.getenv('HTTP_PROXY'),
            'https': os.getenv('HTTPS_PROXY'),
        }

        if job_state.old_etag:
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag#caching_of_unchanged_resources
            headers['If-None-Match'] = job_state.old_etag

        if job_state.old_timestamp is not None:
            headers['If-Modified-Since'] = email.utils.formatdate(job_state.old_timestamp)

        if self.ignore_cached or job_state.tries > 0:
            headers['If-None-Match'] = None
            headers['If-Modified-Since'] = email.utils.formatdate(0)
            headers['Cache-Control'] = 'max-age=172800'
            headers['Expires'] = email.utils.formatdate()

        if self.method is None:
            self.method = 'GET'

        if self.data is not None:
            if self.method is None:
                self.method = 'POST'
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            logger.info(f'Job {self.index_number}: Sending POST request to {self.url}')

        if self.http_proxy is not None:
            proxies['http'] = self.http_proxy
        if self.https_proxy is not None:
            proxies['https'] = self.https_proxy

        if urlparse(self.url).scheme == 'file':
            logger.info(f'Job {self.index_number}: Using local filesystem (file URI scheme)')
            if FilterBase.filter_chain_needs_bytes(self.filter):
                file_mode = 'rb'
            else:
                file_mode = 'rt'
            filename = urlparse(self.url).path
            if os.name == 'nt':
                filename = filename.lstrip('/')
            with open(filename, mode=file_mode) as f:
                file = f.read()
            return file, None

        if urlparse(self.url).scheme == 'ftp':
            url = urlparse(self.url)
            username = url.username or 'anonymous'
            password = url.password or 'anonymous'

            with FTP(url.hostname, username, password, timeout=self.timeout) as ftp:
                if FilterBase.filter_chain_needs_bytes(self.filter):
                    data = b''

                    def callback(dt):
                        nonlocal data
                        data += dt
                    ftp.retrbinary(f'RETR {url.path}', callback)
                else:
                    data = []

                    def callback(dt):
                        data.append(dt)
                    ftp.retrlines(f'RETR {url.path}', callback)
                    data = '\n'.join(data)

            return data, None

        if self.headers:
            self.add_custom_headers(headers)

        if self.timeout is None:
            # default timeout
            timeout = 60
        elif self.timeout == 0:
            # never timeout
            timeout = None
        else:
            timeout = self.timeout

        response = requests.request(method=self.method,
                                    url=self.url,
                                    data=self.data,
                                    headers=headers,
                                    cookies=self.cookies,
                                    timeout=timeout,
                                    allow_redirects=(not self.no_redirects),
                                    proxies=proxies,
                                    verify=(not self.ssl_no_verify))

        response.raise_for_status()
        if response.status_code == requests.codes.not_modified:
            raise NotModifiedError(response.status_code)

        # Save ETag from response into job_state, saved in cache and used in future requests in If-None-Match header
        etag = None
        if not response.history:  # no redirects
            etag = response.headers.get('ETag')

        if FilterBase.filter_chain_needs_bytes(self.filter):
            return response.content, etag

        if self.encoding:
            response.encoding = self.encoding
        elif response.encoding == 'ISO-8859-1' and not CHARSET_RE.match(response.headers.get('Content-type', '')):
            # requests follows RFC 2616 and defaults to ISO-8859-1 if no explicit charset is present in the HTTP headers
            # and the Content-Type header contains text, but this IRL is often wrong; the below updates it with
            # whatever response detects it to be by its use of the chardet library
            logger.debug(f'Job {self.index_number}: Encoding updated to {response.apparent_encoding} from '
                         f'{response.encoding}')
            response.encoding = response.apparent_encoding

        # if no name is given, set it to the title element if found in HTML or XML truncated to 60 characters
        if not self.name:
            title = re.search(r'<title.*?>(.+?)</title>', response.text)
            if title:
                self.name = title.group(1)[:60]

        return response.text, etag

    def add_custom_headers(self, headers: Dict[str, Any]) -> None:
        """
        Adds custom request headers from the job list (URLs) to the pre-filled dictionary `headers`.
        Pre-filled values of conflicting header keys (case-insensitive) are overwritten by custom value.
        """
        headers_to_remove = [x for x in headers if x.lower() in (y.lower() for y in self.headers)]
        for header in headers_to_remove:
            headers.pop(header, None)
        headers.update(self.headers)

    def format_error(self, exception: Exception, tb: str) -> str:
        if isinstance(exception, requests.exceptions.RequestException):
            # Instead of a full traceback, just show the HTTP error
            return str(exception)
        return tb

    def ignore_error(self, exception: Exception) -> Union[bool, str]:
        if isinstance(exception, requests.exceptions.ConnectionError) and self.ignore_connection_errors:
            return True
        if isinstance(exception, requests.exceptions.Timeout) and self.ignore_timeout_errors:
            return True
        if isinstance(exception, requests.exceptions.TooManyRedirects) and self.ignore_too_many_redirects:
            return True
        elif isinstance(exception, requests.exceptions.HTTPError) and self.ignore_http_error_codes:
            status_code = exception.response.status_code
            ignored_codes = []
            if isinstance(self.ignore_http_error_codes, int) and self.ignore_http_error_codes == status_code:
                return True
            elif isinstance(self.ignore_http_error_codes, str):
                ignored_codes = [s.strip().lower() for s in self.ignore_http_error_codes.split(',')]
            elif isinstance(self.ignore_http_error_codes, list):
                ignored_codes = [str(s).strip().lower() for s in self.ignore_http_error_codes]
            return str(status_code) in ignored_codes or f'{(status_code // 100) in ignored_codes}xx'
        return False


class BrowserJob(Job):
    """Retrieve a URL, emulating a real web browser (use_browser: true)."""

    __kind__ = 'browser'

    __required__ = ('url', 'use_browser')
    __optional__ = ('block_elements', 'chromium_revision', 'cookies', 'headers', 'http_proxy', 'https_proxy',
                    'ignore_https_errors', 'navigate', 'switches', 'timeout', 'user_visible_url', 'user_data_dir',
                    'wait_for', 'wait_for_navigation', 'wait_until')

    ctx = None  # Python 3.6

    proxy_username: str = ''
    proxy_password: str = ''

    def get_location(self) -> str:
        return self.user_visible_url or self.url

    def main_thread_enter(self) -> None:
        if sys.version_info < (3, 7):
            # check if proxy is being used
            from .jobs_browser import BrowserContext, get_proxy
            proxy_server, self.proxy_username, self.proxy_password = get_proxy(self.url, self.http_proxy,
                                                                               self.https_proxy)
            self.ctx = BrowserContext(self.chromium_revision, proxy_server, self.ignore_https_errors,
                                      self.user_data_dir, self.switches)

    def main_thread_exit(self) -> None:
        if sys.version_info < (3, 7):
            self.ctx.close()

    def retrieve(self, job_state: 'JobState') -> (str, str):
        if sys.version_info < (3, 7):
            response = self.ctx.process(self.url, self.headers, self.cookies, self.timeout, self.proxy_username,
                                        self.proxy_password, self.wait_until, self.wait_for, self.wait_for_navigation)
            etag = None
        else:
            response, etag = asyncio.run(self._retrieve())

        # if no name is found, set it to the title of the page if found
        if not self.name:
            title = re.findall(r'<title.*?>(.+?)</title>', response)
            if title:
                self.name = title[0]

        return response, etag

    @staticmethod
    def current_platform() -> str:
        """Get current platform name by short string as used by Pyppeteer for downloading Chromium.
        Originally from pyppeteer.chromium_downloader, but we cannot simply import it as it will trigger
        pyppeteer reading os.environ['PYPPETEER_CHROMIUM_REVISION'] before we can modify it ourselves."""
        # TODO: see if you can use importlib.reload for the new value to stick
        if sys.platform.startswith('linux'):
            return 'linux'
        elif sys.platform.startswith('darwin'):
            return 'mac'
        elif sys.platform.startswith('win') or sys.platform.startswith('msys') or sys.platform.startswith('cyg'):
            if sys.maxsize > 2 ** 31 - 1:
                return 'win64'
            return 'win32'
        raise OSError('Platform unsupported by Pyppeteer (use_browser: true): ' + sys.platform)

    async def _retrieve(self) -> (str, str):
        # launch browser
        if not self.chromium_revision:
            self.chromium_revision = DEFAULT_CHROMIUM_REVISION
        if isinstance(self.chromium_revision, dict):
            for key, value in DEFAULT_CHROMIUM_REVISION.items():
                if key not in self.chromium_revision:
                    self.chromium_revision[key] = value
            try:
                _revision = self.chromium_revision[self.current_platform()]
            except KeyError:
                raise KeyError(f"No 'chromium_revision' key for operating system {self.current_platform()} found")
        else:
            _revision = self.chromium_revision
        os.environ['PYPPETEER_CHROMIUM_REVISION'] = str(_revision)

        logger.debug(f'Job {self.index_number}: '
                     f"PYPPETEER_CHROMIUM_REVISION={os.environ.get('PYPPETEER_CHROMIUM_REVISION')}, "
                     f"PYPPETEER_NO_PROGRESS_BAR={os.environ.get('PYPPETEER_NO_PROGRESS_BAR')}, "
                     f"PYPPETEER_DOWNLOAD_HOST={os.environ.get('PYPPETEER_DOWNLOAD_HOST')}")
        try:
            from pyppeteer import launch  # pyppeteer must be imported after setting os.environ variables
        except ImportError:
            raise ImportError(f'Python package pyppeteer is not installed; cannot use the "use_browser: true" directive'
                              f' ( {self.get_indexed_location()} )')
        from pyppeteer.errors import PageError

        headers = self.headers if self.headers else {}

        # Setting of 'If-None-Match' or 'If-Modified-Since' headers can trigger a 'net::ERR_ABORTED [...]'
        # browsing error that is returned by page.goto as a PageError(); cannot find a workable way to determine whether
        # it's due to an HTTP 304 Not Modified code (goto) or something else (bad) as PageError only passes the text,
        # not the full response.  Keeping code here for future ETag handling development.
        # if self.ignore_cached or job_state.tries > 0:
        #     headers.pop('If-None-Match', None)
        #     headers['If-Modified-Since'] = email.utils.formatdate(0)
        #     headers['Cache-Control'] = 'max-age=172800'
        #     headers['Expires'] = email.utils.formatdate()
        # else:
        #     if job_state.old_etag:
        #         # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag#caching_of_unchanged_resources
        #         headers['If-None-Match'] = job_state.old_etag
        #     if job_state.old_timestamp is not None:
        #         headers['If-Modified-Since'] = email.utils.formatdate(job_state.old_timestamp)

        args = []
        proxy = ''
        if self.http_proxy or self.https_proxy:
            if urlsplit(self.url).scheme == 'http':
                proxy = self.http_proxy
            elif urlsplit(self.url).scheme == 'https':
                proxy = self.https_proxy
            if proxy:
                proxy_server = f'{urlsplit(proxy).scheme}://{urlsplit(proxy).hostname}' + (
                    f':{urlsplit(proxy).port}' if urlsplit(proxy).port else '')
                args.append(f'--proxy-server={proxy_server}')
        if self.user_data_dir:
            args.append(f'--user-data-dir={self.user_data_dir}')
        if self.switches:
            if isinstance(self.switches, str):
                self.switches = self.switches.split(',')
            if not isinstance(self.switches, list):
                raise TypeError(f"'switches' needs to be a string or list, not {type(self.switches)} "
                                f'( {self.get_indexed_location()} )')
            self.switches = [f"--{switch.lstrip('--')}" for switch in self.switches]
            args.extend(self.switches)
        # as signals only work single-threaded, must set handleSIGINT, handleSIGTERM and handleSIGHUP to False
        browser = await launch(ignoreHTTPSErrors=self.ignore_https_errors, args=args, handleSIGINT=False,
                               handleSIGTERM=False, handleSIGHUP=False, loop=asyncio.get_running_loop())
        logger.debug(f'Job {self.index_number}: Launched browser with args={args}')

        # browse to page and get content
        page = await browser.newPage()

        if headers:
            logger.debug(f'Job {self.index_number}: setExtraHTTPHeaders={headers}')
            await page.setExtraHTTPHeaders(headers)
        if self.cookies:
            await page.setExtraHTTPHeaders({'Cookies': '; '.join([f'{k}={v}' for k, v in self.cookies.items()])})
        if self.http_proxy or self.https_proxy:
            proxy_username = urlsplit(proxy).username if urlsplit(proxy).username else ''
            proxy_password = urlsplit(proxy).password if urlsplit(proxy).password else ''
            if proxy_username or proxy_password:
                await page.authenticate({'username': proxy_username, 'password': proxy_password})
                logger.debug(f'Job {self.index_number}: Set page.authenticate with username={proxy_username}, '
                             f'password={proxy_password}')
        options = {}
        if self.timeout:
            options['timeout'] = self.timeout * 1000
        if self.wait_until:
            options['waitUntil'] = self.wait_until
        if self.block_elements:  # FIXME: Pyppeteer freezes on certain sites if this is on; contribute if you know why
            if isinstance(self.block_elements, str):
                self.block_elements = self.block_elements.split(',')
            if not isinstance(self.block_elements, list):
                await browser.close()
                raise TypeError(f"'block_elements' needs to be a string or list, not {type(self.block_elements)} "
                                f'( {self.get_indexed_location()} )')
            # web_request_resource_types = [
            #     # https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest/ResourceType
            #     'beacon', 'csp_report', 'font', 'image', 'imageset', 'media', 'main_frame', 'media', 'object',
            #     'object_subrequest', 'ping', 'script', 'speculative', 'stylesheet', 'sub_frame', 'web_manifest',
            #     'websocket', 'xbl', 'xml_dtd', 'xmlhttprequest', 'xslt', 'other'
            #     ]
            chrome_web_request_resource_types = [
                # https://developer.chrome.com/docs/extensions/reference/webRequest/#type-ResourceType
                'main_frame', 'sub_frame', 'stylesheet', 'script', 'image', 'font', 'object', 'xmlhttprequest', 'ping',
                'csp_report', 'media', 'websocket', 'other'
            ]
            for element in self.block_elements:
                if element not in chrome_web_request_resource_types:
                    await browser.close()
                    raise ValueError(f"Unknown or unsupported '{element}' resource type in 'block_elements' "
                                     f'( {self.get_indexed_location()} )')

            async def handle_request(request_event, block_elements):
                logger.info(f'Job {self.index_number}: resource_type={request_event.resourceType} '
                            f'elements={block_elements}')
                if any(request_event.resourceType == el for el in block_elements):
                    logger.info(f'Job {self.index_number}: Aborting request {request_event.resourceType}')
                    await request_event.abort()
                else:
                    logger.info(f'Job {self.index_number}: Continuing request {request_event.resourceType}')
                    await request_event.continue_()  # broken -- many sites hang here!

            await page.setRequestInterception(True)
            page.on('request', lambda request_event: asyncio.create_task(
                handle_request(request_event, self.block_elements)))  # inherited from pyee.EventEmitter

        async def store_etag(response_event):
            """Store the ETag for future use as well as the response code."""
            nonlocal etag
            nonlocal response_code
            logger.debug(f'Job {self.index_number}: response.status={response_event.status} '
                         f'response.url={response_event.url}')
            if urldefrag(response_event.url)[0] == urldefrag(self.url)[0]:
                response_code = response_event.status
                if response_event.status == requests.codes.ok:
                    etag = response_event.headers.get('etag')

        etag: Optional[str] = None
        response_code: Optional[int] = None

        # page.on inherited from pyee's EventEmitter class
        # https://pyee.readthedocs.io/en/latest/#pyee.EventEmitter
        page.on('response', lambda response_event: asyncio.create_task(store_etag(response_event)))

        try:
            logger.debug(f'Job {self.index_number}: page.goto options={options}')
            await page.goto(self.url, options=options)
        except PageError as e:
            logger.debug(f'Job {self.index_number}: Page returned error {str(e.args)}')
            await browser.close()
            if response_code and 400 <= response_code < 600:
                raise BrowserResponseError(e.args, response_code)
            else:
                raise PageError(e)

        # For future ETag handling development, the code in remarks below triggers NotModifiedError if HTTP 304 Not
        # Modified is returned
        # page_response = await page.goto(self.url, options=options)
        # if not request_response and response_code == requests.codes.not_modified:
        #     logger.debug(f'Job {self.index_number}: page_response={page_response}; response_code={response_code}')
        #     await browser.close()
        #     raise NotModifiedError(response_code)

        if self.wait_for_navigation:
            while not page.url.startswith(self.wait_for_navigation):
                logger.info(f'Job {self.index_number}: Waiting for redirection from {page.url}')
                await page.waitForNavigation(option=options)
        if self.wait_for:
            if isinstance(self.wait_for, (int, float, complex)) and not isinstance(self.wait_for, bool):
                self.wait_for *= 1000
            await page.waitFor(self.wait_for, options=options)

        content = await page.content()
        await browser.close()

        if response_code and 400 <= response_code < 600:
            raise BrowserResponseError(('',), response_code)
        elif response_code is not None and response_code != requests.codes.ok:
            logger.info(f'Job {self.index_number}: Received response HTTP {response_code} '
                        f'{response_names[response_code]}')

        return content, etag

    def ignore_error(self, exception: Exception) -> Union[bool, str]:
        from pyppeteer.errors import PageError  # pyppeteer must be imported after setting os.environ variables

        if isinstance(exception, PageError):
            # See https://source.chromium.org/chromium/chromium/src/+/master:net/base/net_error_list.h
            CHROMIUM_CONNECTION_ERRORS = [  # range 100-199 Connection related errors
                'CONNECTION_CLOSED',
                'CONNECTION_RESET',
                'CONNECTION_REFUSED',
                'CONNECTION_ABORTED',
                'CONNECTION_FAILED',
                'NAME_NOT_RESOLVED',
                'INTERNET_DISCONNECTED',
                'SSL_PROTOCOL_ERROR',
                'ADDRESS_INVALID',
                'ADDRESS_UNREACHABLE',
                'SSL_CLIENT_AUTH_CERT_NEEDED',
                'TUNNEL_CONNECTION_FAILED',
                'NO_SSL_VERSIONS_ENABLED',
                'SSL_VERSION_OR_CIPHER_MISMATCH',
                'SSL_RENEGOTIATION_REQUESTED',
                'PROXY_AUTH_UNSUPPORTED',
                'CERT_ERROR_IN_SSL_RENEGOTIATION',
                'BAD_SSL_CLIENT_AUTH_CERT',
                'CONNECTION_TIMED_OUT',
                'HOST_RESOLVER_QUEUE_TOO_LARGE',
                'SOCKS_CONNECTION_FAILED',
                'SOCKS_CONNECTION_HOST_UNREACHABLE',
                'ALPN_NEGOTIATION_FAILED',
                'SSL_NO_RENEGOTIATION',
                'WINSOCK_UNEXPECTED_WRITTEN_BYTES',
                'SSL_DECOMPRESSION_FAILURE_ALERT',
                'SSL_BAD_RECORD_MAC_ALERT',
                'PROXY_AUTH_REQUESTED',
                'PROXY_CONNECTION_FAILED',
                'MANDATORY_PROXY_CONFIGURATION_FAILED',
                'PRECONNECT_MAX_SOCKET_LIMIT',
                'SSL_CLIENT_AUTH_PRIVATE_KEY_ACCESS_DENIED',
                'SSL_CLIENT_AUTH_CERT_NO_PRIVATE_KEY',
                'PROXY_CERTIFICATE_INVALID',
                'NAME_RESOLUTION_FAILED',
                'NETWORK_ACCESS_DENIED',
                'TEMPORARILY_THROTTLED',
                'HTTPS_PROXY_TUNNEL_RESPONSE_REDIRECT',
                'SSL_CLIENT_AUTH_SIGNATURE_FAILED',
                'MSG_TOO_BIG',
                'WS_PROTOCOL_ERROR',
                'ADDRESS_IN_USE',
                'SSL_HANDSHAKE_NOT_COMPLETED',
                'SSL_BAD_PEER_PUBLIC_KEY',
                'SSL_PINNED_KEY_NOT_IN_CERT_CHAIN',
                'CLIENT_AUTH_CERT_TYPE_UNSUPPORTED',
                'SSL_DECRYPT_ERROR_ALERT',
                'WS_THROTTLE_QUEUE_TOO_LARGE',
                'SSL_SERVER_CERT_CHANGED',
                'SSL_UNRECOGNIZED_NAME_ALERT',
                'SOCKET_SET_RECEIVE_BUFFER_SIZE_ERROR',
                'SOCKET_SET_SEND_BUFFER_SIZE_ERROR',
                'SOCKET_RECEIVE_BUFFER_SIZE_UNCHANGEABLE',
                'SOCKET_SEND_BUFFER_SIZE_UNCHANGEABLE',
                'SSL_CLIENT_AUTH_CERT_BAD_FORMAT',
                'ICANN_NAME_COLLISION',
                'SSL_SERVER_CERT_BAD_FORMAT',
                'CT_STH_PARSING_FAILED',
                'CT_STH_INCOMPLETE',
                'UNABLE_TO_REUSE_CONNECTION_FOR_PROXY_AUTH',
                'CT_CONSISTENCY_PROOF_PARSING_FAILED',
                'SSL_OBSOLETE_CIPHER',
                'WS_UPGRADE',
                'READ_IF_READY_NOT_IMPLEMENTED',
                'NO_BUFFER_SPACE',
                'SSL_CLIENT_AUTH_NO_COMMON_ALGORITHMS',
                'EARLY_DATA_REJECTED',
                'WRONG_VERSION_ON_EARLY_DATA',
                'TLS13_DOWNGRADE_DETECTED',
                'SSL_KEY_USAGE_INCOMPATIBLE',
            ]

            if self.ignore_connection_errors:
                if any(str(exception.args[0]) == f'net::ERR_{error}' for error in CHROMIUM_CONNECTION_ERRORS):
                    return True
            if self.ignore_timeout_errors:
                if str(exception.args[0]) == 'net::ERR_TIMED_OUT':
                    return True
            if self.ignore_too_many_redirects:
                if str(exception.args[0]) == 'net::ERR_TOO_MANY_REDIRECTS':
                    return True
        elif isinstance(exception, BrowserResponseError) and self.ignore_http_error_codes:
            status_code = exception.status_code
            ignored_codes = []
            if isinstance(self.ignore_http_error_codes, int) and self.ignore_http_error_codes == status_code:
                return True
            elif isinstance(self.ignore_http_error_codes, str):
                ignored_codes = [s.strip().lower() for s in self.ignore_http_error_codes.split(',')]
            elif isinstance(self.ignore_http_error_codes, list):
                ignored_codes = [str(s).strip().lower() for s in self.ignore_http_error_codes]
            return str(status_code) in ignored_codes or f'{(status_code // 100) in ignored_codes}xx'
        return False


class ShellJob(Job):
    """Run a shell command and get its standard output."""

    __kind__ = 'shell'

    __required__ = ('command',)
    __optional__ = ()

    def get_location(self) -> str:
        return self.command

    def retrieve(self, job_state: Type['JobState']) -> (AnyStr, str):
        needs_bytes = FilterBase.filter_chain_needs_bytes(self.filter)
        if sys.version_info < (3, 7):
            process = subprocess.run(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     shell=True)  # noqa: DUO116 use of "shell=True" is insecure
            result = process.returncode
            if result != 0:
                raise ShellError(process.stderr)

            if needs_bytes:
                return process.stdout, None
            else:
                return process.stdout.decode(), None
        else:
            try:
                return subprocess.run(self.command, capture_output=True, shell=True, check=True,
                                      text=(not needs_bytes)).stdout, None  # noqa: DUO116 use of "shell=True" is insec
            except subprocess.CalledProcessError as e:
                raise ShellError(e.stderr).with_traceback(e.__traceback__)
