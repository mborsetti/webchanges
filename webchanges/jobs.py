import asyncio
import email.utils
import hashlib
import logging
import os
import re
import subprocess
import sys
import textwrap
from urllib.parse import urlsplit

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

import webchanges as project
from .filters import FilterBase
from .util import TrackSubClasses

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)


class ShellError(Exception):
    """Exception for shell commands with non-zero exit code"""

    def __init__(self, result):
        Exception.__init__(self)
        self.result = result

    def __str__(self):
        return f'{self.__class__.__name__}: Exit status {self.result}'


class NotModifiedError(Exception):
    """Exception raised on HTTP 304 responses"""
    ...


class JobBase(object, metaclass=TrackSubClasses):
    __subclasses__ = {}

    __required__ = ()
    __optional__ = ()

    def __init__(self, **kwargs):
        # Set optional keys to None
        for k in self.__optional__:
            if k not in kwargs:
                setattr(self, k, None)

        # backwards-compatibility
        if (self.__kind__ == 'browser' or 'navigate' in kwargs) and 'use_browser' not in kwargs:
            logger.warning("'kind: browser' is deprecated: replace with 'use_browser: true'")
            kwargs['use_browser'] = True

        # Fail if any required keys are not provided
        for k in self.__required__:
            if k not in kwargs:
                raise ValueError(f'Required field {k} missing: {kwargs!r}')

        for k, v in list(kwargs.items()):
            setattr(self, k, v)

        # if self.__kind__ in ('url', 'shell'):
        #     logger.warning(f"'kind: {self.__kind__}' is deprecated and not needed: please delete")
        # elif self.__kind__ == 'browser':
        #     logger.warning("'kind: browser' is deprecated: replace with 'use_browser: true'")

    @classmethod
    def job_documentation(cls):
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

    def get_location(self):
        raise NotImplementedError()

    def pretty_name(self):
        raise NotImplementedError()

    def serialize(self):
        d = {'kind': self.__kind__}
        d.update(self.to_dict())
        return d

    @classmethod
    def unserialize(cls, data):
        if 'kind' not in data:
            # Try to auto-detect the kind of job based on the available keys
            kinds = [subclass.__kind__ for subclass in list(cls.__subclasses__.values())
                     if all(required in data for required in subclass.__required__) and not any(
                     key not in subclass.__required__ and key not in subclass.__optional__ for key in data)]

            if len(kinds) == 1 or (len(kinds) == 2 and kinds[0] == 'url'):  # url defaults to kind: url
                kind = kinds[0]
            elif len(kinds) == 0:
                if 'url' in data and data.get('use_browser'):
                    kind = 'browser'
                elif 'url' in data:
                    kind = 'url'
                elif 'command' in data:
                    kind = 'shell'
                else:
                    raise ValueError(
                        f"Parameters don't match a job type; check for errors/typos/text escaping:\n{data!r}")
            else:
                raise ValueError(f'Multiple kinds of jobs match {data!r}: {kinds!r}')
        else:
            kind = data['kind']

        return cls.__subclasses__[kind].from_dict(data)

    def to_dict(self):
        return {k: getattr(self, k) for keys in (self.__required__, self.__optional__) for k in keys
                if getattr(self, k) is not None}

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in list(data.items()) if k in cls.__required__ or k in cls.__optional__})

    def __repr__(self):
        return f'<{self.__kind__} {" ".join(f"{k}={v!r}" for k, v in list(self.to_dict().items()))}'

    def _set_defaults(self, defaults):
        if isinstance(defaults, dict):
            for key, value in defaults.items():
                if key in self.__optional__ and getattr(self, key) is None:
                    setattr(self, key, value)

    def with_defaults(self, config):
        new_job = JobBase.unserialize(self.serialize())
        cfg = config.get('job_defaults')
        if isinstance(cfg, dict):
            new_job._set_defaults(cfg.get(self.__kind__))
            new_job._set_defaults(cfg.get('all'))
        return new_job

    def get_guid(self):
        location = self.get_location()
        sha_hash = hashlib.new('sha1')
        sha_hash.update(location.encode())
        return sha_hash.hexdigest()

    def retrieve(self, job_state):
        raise NotImplementedError()

    def main_thread_enter(self):
        """Called from the main thread before running the job"""
        ...

    def main_thread_exit(self):
        """Called from the main thread after running the job"""
        ...

    def format_error(self, exception, tb):
        return tb

    def ignore_error(self, exception):
        return False


class Job(JobBase):
    __required__ = ()
    __optional__ = ('name', 'note', 'filter', 'max_tries', 'diff_tool', 'additions_only', 'deletions_only',
                    'contextlines', 'compared_versions', 'is_markdown', 'markdown_padded_tables', 'diff_filter')

    def pretty_name(self):
        return self.name or self.get_location()


class UrlJob(Job):
    """Retrieve a URL from a web server"""

    __kind__ = 'url'

    __required__ = ('url',)
    __optional__ = ('cookies', 'data', 'method', 'ssl_no_verify', 'ignore_cached', 'http_proxy', 'https_proxy',
                    'headers', 'ignore_connection_errors', 'ignore_http_error_codes', 'encoding', 'timeout',
                    'ignore_timeout_errors', 'ignore_too_many_redirects', 'user_visible_url')

    CHARSET_RE = re.compile('text/(html|plain); charset=([^;]*)')

    def get_location(self):
        return self.user_visible_url or self.url

    def retrieve(self, job_state):
        headers = {
            'User-agent': project.__user_agent__,
        }

        proxies = {
            'http': os.getenv('HTTP_PROXY'),
            'https': os.getenv('HTTPS_PROXY'),
        }

        if job_state.etag is not None:
            headers['If-None-Match'] = job_state.etag

        if job_state.timestamp is not None:
            headers['If-Modified-Since'] = email.utils.formatdate(job_state.timestamp)

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
            headers['Content-type'] = 'application/x-www-form-urlencoded'
            logger.info(f'Sending POST request to {self.url}')

        if self.http_proxy is not None:
            proxies['http'] = self.http_proxy
        if self.https_proxy is not None:
            proxies['https'] = self.https_proxy

        file_scheme = 'file://'
        if self.url.startswith(file_scheme):
            logger.info(f'Using local filesystem ({file_scheme} URI scheme)')
            with open(self.url[len(file_scheme):], 'rt') as f:
                file = f.read()
            return file

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
                                    proxies=proxies,
                                    verify=(not self.ssl_no_verify))

        response.raise_for_status()
        if response.status_code == requests.codes.not_modified:
            raise NotModifiedError()

        # Save ETag from response into job_state, which will be saved in cache
        job_state.etag = response.headers.get('ETag')

        if FilterBase.filter_chain_needs_bytes(self.filter):
            return response.content

        # # If we can't find the encoding in the headers, requests gets all
        # # old-RFC-y and assumes ISO-8859-1 instead of UTF-8. Use the old
        # # behavior and try UTF-8 decoding first.
        # content_type = response.headers.get('Content-type', '')
        # content_type_match = self.CHARSET_RE.match(content_type)
        # if not content_type_match and not self.encoding:
        #     try:
        #         try:
        #             try:
        #                 return response.content.decode()
        #             except UnicodeDecodeError:
        #                 return response.content.decode('latin1')
        #         except UnicodeDecodeError:
        #             return response.content.decode(errors='ignore')
        #     except LookupError:
        #         # If this is an invalid encoding, decode as ascii (Debian bug 731931)
        #         return response.content.decode('ascii', 'ignore')
        if self.encoding:
            response.encoding = self.encoding
        elif response.encoding == 'ISO-8859-1' and not self.CHARSET_RE.match(response.headers.get('Content-type', '')):
            # requests follows RFC 2616 and defaults to ISO-8859-1 if no explicit charset is present in the HTTP headers
            # and the Content-Type header contains text, but this IRL is often wrong; the below replaces it with
            # whatever the chardet library detects it to be
            response.encoding = response.apparent_encoding

        # if no name is given, set it to the title of the page if found in HTML/XML
        if not self.name:
            title = re.findall(r'<title.*?>(.+?)</title>', response.text)
            if title:
                self.name = title[0]

        return response.text

    def add_custom_headers(self, headers):
        """
        Adds custom request headers from the job list (URLs) to the pre-filled dictionary `headers`.
        Pre-filled values of conflicting header keys (case-insensitive) are overwritten by custom value.
        """
        headers_to_remove = [x for x in headers if x.lower() in [y.lower() for y in self.headers]]
        for header in headers_to_remove:
            headers.pop(header, None)
        headers.update(self.headers)

    def format_error(self, exception, tb):
        if isinstance(exception, requests.exceptions.RequestException):
            # Instead of a full traceback, just show the HTTP error
            return str(exception)
        return tb

    def ignore_error(self, exception):
        if isinstance(exception, requests.exceptions.ConnectionError) and self.ignore_connection_errors:
            return True
        if isinstance(exception, requests.exceptions.Timeout) and self.ignore_timeout_errors:
            return True
        if isinstance(exception, requests.exceptions.TooManyRedirects) and self.ignore_too_many_redirects:
            return True
        elif isinstance(exception, requests.exceptions.HTTPError):
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
    """Retrieve a URL, emulating a real web browser (use_browser: true)"""

    __kind__ = 'browser'

    __required__ = ('url', 'use_browser')
    __optional__ = ('chromium_revision', 'headers', 'cookies', 'timeout', 'ignore_http_error_codes',
                    'http_proxy', 'https_proxy', 'user_data_dir', 'switches', 'wait_until', 'wait_for',
                    'wait_for_navigation', 'user_visible_url', 'block_elements', 'navigate')

    DEFAULT_CHROMIUM_REVISION = {
        'linux': 843831,
        'win64': 843846,
        'win32': 843832,
        'macos': 843846,
    }

    def get_location(self):
        if not self.url and self.navigate:
            logger.warning("'navigate:' key is deprecated. Replace with 'url:' and 'use_browser: true")
        return self.user_visible_url or self.url or self.navigate

    def main_thread_enter(self):
        if sys.version_info < (3, 7):
            # check if proxy is being used
            from .browser import BrowserContext, get_proxy
            proxy_server, self.proxy_username, self.proxy_password = get_proxy(self.url, self.http_proxy,
                                                                               self.https_proxy)
            self.ctx = BrowserContext(self.chromium_revision, proxy_server, self.ignore_http_error_codes,
                                      self.user_data_dir, self.switches)

    def main_thread_exit(self):
        if sys.version_info < (3, 7):
            self.ctx.close()

    def retrieve(self, job_state):
        if sys.version_info < (3, 7):
            response = self.ctx.process(self.url, self.headers, self.cookies, self.timeout, self.proxy_username,
                                        self.proxy_password, self.wait_until, self.wait_for, self.wait_for_navigation)
        else:
            response = asyncio.run(self._retrieve())

        # if no name is found, set it to the title of the page if found
        if not self.name:
            title = re.findall(r'<title.*?>(.+?)</title>', response)
            if title:
                self.name = title[0]

        return response

    @staticmethod
    def current_platform() -> str:
        """Get current platform name by short string.
        Originally from pyppeteer.chromium_downloader"""
        if sys.platform.startswith('linux'):
            return 'linux'
        elif sys.platform.startswith('darwin'):
            return 'mac'
        elif sys.platform.startswith('win') or sys.platform.startswith('msys') or sys.platform.startswith('cyg'):
            if sys.maxsize > 2 ** 31 - 1:
                return 'win64'
            return 'win32'
        raise OSError('Platform unsupported by Pyppeteer (use_browser: true): ' + sys.platform)

    async def _retrieve(self):
        # launch browser
        if not self.chromium_revision:
            self.chromium_revision = self.DEFAULT_CHROMIUM_REVISION
        if isinstance(self.chromium_revision, dict):
            for key, value in self.DEFAULT_CHROMIUM_REVISION.items():
                if key not in self.chromium_revision:
                    self.chromium_revision[key] = value
            try:
                _revision = self.chromium_revision[self.current_platform()]
            except KeyError:
                raise KeyError(f"No 'chromium_revision' key for operating system {self.current_platform()} found")
        else:
            _revision = self.chromium_revision
        os.environ['PYPPETEER_CHROMIUM_REVISION'] = str(_revision)

        logger.info(f"os.environ.get('PYPPETEER_DOWNLOAD_HOST')={os.environ.get('PYPPETEER_DOWNLOAD_HOST')}")
        logger.info(f"os.environ.get('PYPPETEER_CHROMIUM_REVISION')="
                    f"{os.environ.get('PYPPETEER_CHROMIUM_REVISION')}")
        logger.info(f"os.environ.get('PYPPETEER_NO_PROGRESS_BAR')={os.environ.get('PYPPETEER_NO_PROGRESS_BAR')}")
        try:
            from pyppeteer import launch  # must be imported after setting os.environ variables
        except ImportError:
            raise ImportError(f'Python package pyppeteer is not installed; cannot use the "use_browser: true" directive'
                              f' ( {self.job.get_location()} )')

        args = []
        if self.http_proxy or self.https_proxy:
            if urlsplit(self.url).scheme == 'http':
                proxy = self.http_proxy
            elif urlsplit(self.url).scheme == 'https':
                proxy = self.https_proxy
            else:
                proxy = ''
            if proxy:
                proxy_server = f'{urlsplit(proxy).scheme}://{urlsplit(proxy).hostname}' + (
                    f':{urlsplit(proxy).port}' if urlsplit(proxy).port else '')
                proxy_username = str(urlsplit(proxy).username) if urlsplit(proxy).username else ''
                proxy_password = str(urlsplit(proxy).password) if urlsplit(proxy).password else ''
                args.append(f'--proxy-server={proxy_server}')
        if self.user_data_dir:
            args.append(f'--user-data-dir={os.path.expanduser(os.path.expandvars(self.user_data_dir))}')
        if self.switches:
            if isinstance(self.switches, str):
                self.switches = self.switches.split(',')
            if not isinstance(self.switches, list):
                raise TypeError(f"'switches' needs to be a string or list, not {type(self.switches)} "
                                f'( {self.get_location()} )')
            self.switches = [f"--{switch.lstrip('--')}" for switch in self.switches]
            args.extend(self.switches)
        # as signals only work single-threaded, must set handleSIGINT, handleSIGTERM and handleSIGHUP to False
        browser = await launch(ignoreHTTPSErrors=self.ignore_http_error_codes, args=args, handleSIGINT=False,
                               handleSIGTERM=False, handleSIGHUP=False)

        # browse to page and get content
        page = await browser.newPage()

        if self.headers:
            await page.setExtraHTTPHeaders(self.headers)
        if self.cookies:
            await page.setExtraHTTPHeaders({'Cookies': '; '.join([f'{k}={v}' for k, v in self.cookies.items()])})
        if (self.http_proxy or self.https_proxy) and (proxy_username or proxy_password):
            await page.authenticate({'username': proxy_username, 'password': proxy_password})
        options = {}
        if self.timeout:
            options['timeout'] = self.timeout * 1000
        if self.wait_until:
            options['waitUntil'] = self.wait_until
        if self.block_elements:  # FIXME: Pyppeteer freezes on certain sites if this is on; contribute if you know why
            if isinstance(self.block_elements, str):
                self.block_elements = self.block_elements.split(',')
            if not isinstance(self.block_elements, list):
                raise TypeError(f"'block_elements' needs to be a string or list, not {type(self.block_elements)} "
                                f'( {self.get_location()} )')
            # web_request_resource_types = [
            #     # https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest/ResourceType
            #     'beacon', 'csp_report', 'font', 'image', 'imageset', 'media', 'main_frame', 'media', 'object',
            #     'object_subrequest', 'ping', 'script', 'speculative', 'stylesheet', 'sub_frame', 'web_manifest',
            #     'websocket', 'xbl', 'xml_dtd', 'xmlhttprequest', 'xslt', 'other']
            chrome_web_request_resource_types = [
                # https://developer.chrome.com/docs/extensions/reference/webRequest/#type-ResourceType
                'main_frame', 'sub_frame', 'stylesheet', 'script', 'image', 'font', 'object', 'xmlhttprequest', 'ping',
                'csp_report', 'media', 'websocket', 'other']
            for element in self.block_elements:
                if element not in chrome_web_request_resource_types:
                    await browser.close()
                    raise ValueError(f"Unknown or unsupported '{element}' resource type in 'block_elements' "
                                     f'( {self.get_location()} )')

            async def intercept(request, elements):
                if any(request.resourceType == _ for _ in elements):
                    await request.abort()
                else:
                    await request.continue_()

            def handle_request(intercepted_request):
                asyncio.create_task(intercept(intercepted_request, self.block_elements))

            await page.setRequestInterception(True)
            page.on('request', handle_request)  # inherited from Bases: pyee.EventEmitter

        await page.goto(self.url, options=options)

        # TODO understand if the below is required
        # if self.block_elements:
        #     page.remove_listener('request', handle_request)
        #     await page.setRequestInterception(False)
        if self.wait_for_navigation:
            while not page.url.startswith(self.wait_for_navigation):
                logger.info(f'Waiting for redirection from {page.url}')
                await page.waitForNavigation(option=options)
        if self.wait_for:
            if isinstance(self.wait_for, (int, float, complex)) and not isinstance(self.wait_for, bool):
                self.wait_for *= 1000
            await page.waitFor(self.wait_for, options=options)

        content = await page.content()
        await browser.close()

        return content


class ShellJob(Job):
    """Run a shell command and get its standard output"""

    __kind__ = 'shell'

    __required__ = ('command',)
    __optional__ = ()

    def get_location(self):
        return self.command

    def retrieve(self, job_state):
        needs_bytes = FilterBase.filter_chain_needs_bytes(self.filter)
        if sys.version_info < (3, 7):
            process = subprocess.run(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     shell=True)  # noqa: DUO116 use of "shell=True" is insecure
            result = process.returncode
            if result != 0:
                raise ShellError(process.stderr)

            if needs_bytes:
                return process.stdout
            else:
                return process.stdout.decode()
        else:
            try:
                return subprocess.run(self.command, capture_output=True, shell=True, check=True,
                                      text=(not needs_bytes)).stdout  # noqa: DUO116 use of "shell=True" is insecure
            except subprocess.CalledProcessError as e:
                raise ShellError(e.stderr).with_traceback(e.__traceback__)
