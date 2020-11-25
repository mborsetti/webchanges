import email.utils
import hashlib
import logging
import os
import re
import subprocess
import textwrap

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
                raise ValueError(f'Required field {k} missing: {kwargs}')

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

            for msg, value in (('    Required keys: ', sc.__required__), ('    Optional keys: ', sc.__optional__)):
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
                raise ValueError(f'Kind is not specified, and no job matches: {data}')
            else:
                raise ValueError(f'Multiple kinds of jobs match {data}: {kinds}')
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
        return f'<{self.__kind__} {" ".join(f"{k}={v}" for k, v in list(self.to_dict().items()))}'

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
        sha_hash.update(location.encode('utf-8'))
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
    __optional__ = ('name', 'filter', 'max_tries', 'diff_tool', 'additions_only', 'deletions_only',
                    'contextlines', 'compared_versions', 'is_markdown', 'markdown_padded_tables', 'diff_filter')

    def pretty_name(self):
        return self.name if self.name else self.get_location()


class UrlJob(Job):
    """Retrieve an URL from a web server. Triggered by url key and no (or false) use_browser key"""

    __kind__ = 'url'

    __required__ = ('url',)
    __optional__ = ('cookies', 'data', 'method', 'ssl_no_verify', 'ignore_cached', 'http_proxy', 'https_proxy',
                    'headers', 'ignore_connection_errors', 'ignore_http_error_codes', 'encoding', 'timeout',
                    'ignore_timeout_errors', 'ignore_too_many_redirects')

    CHARSET_RE = re.compile('text/(html|plain); charset=([^;]*)')

    def get_location(self):
        return self.url

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
            logger.info('Sending POST request to %s', self.url)

        if self.http_proxy is not None:
            proxies['http'] = self.http_proxy
        if self.https_proxy is not None:
            proxies['https'] = self.https_proxy

        file_scheme = 'file://'
        if self.url.startswith(file_scheme):
            logger.info('Using local filesystem (%s URI scheme)', file_scheme)
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
        #                 return response.content.decode('utf-8')
        #             except UnicodeDecodeError:
        #                 return response.content.decode('latin1')
        #         except UnicodeDecodeError:
        #             return response.content.decode('utf-8', 'ignore')
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
    """Retrieve an URL, emulating a real web browser. Triggered by url key with use_browser: true"""

    __kind__ = 'browser'

    __required__ = ('url', 'use_browser')
    __optional__ = ('chromium_revision', 'headers', 'cookies', 'timeout', 'ignore_http_error_codes',
                    'http_proxy', 'https_proxy', 'user_data_dir', 'switches', 'wait_until', 'wait_for', 'navigate')

    def get_location(self):
        if not self.url and self.navigate:
            logger.warning("'navigate:' key is deprecated. Replace with 'url:'")
        return self.url if self.url else self.navigate

    def main_thread_enter(self):
        from .browser import BrowserContext, get_proxy

        # check if proxy is being used
        proxy_server, self.proxy_username, self.proxy_password = get_proxy(self.url, self.http_proxy, self.https_proxy)
        self.ctx = BrowserContext(self.chromium_revision, proxy_server, self.ignore_http_error_codes,
                                  self.user_data_dir, self.switches)

    def main_thread_exit(self):
        self.ctx.close()

    def retrieve(self, job_state):
        response = self.ctx.process(self.url, self.headers, self.cookies, self.timeout, self.proxy_username,
                                    self.proxy_password, self.wait_until, self.wait_for)
        # if no name is found, set it to the title of the page if found
        if not self.name:
            title = re.findall(r'<title.*?>(.+?)</title>', response)
            if title:
                self.name = title[0]

        return response


class ShellJob(Job):
    """Run a shell command and get its standard output"""

    __kind__ = 'shell'

    __required__ = ('command',)
    __optional__ = ()

    def get_location(self):
        return self.command

    def retrieve(self, job_state):
        process = subprocess.Popen(self.command, stdout=subprocess.PIPE, shell=True)  # noqa:DUO116 "shell=True" insecr
        stdout_data, stderr_data = process.communicate()
        result = process.wait()
        if result != 0:
            raise ShellError(result)

        if FilterBase.filter_chain_needs_bytes(self.filter):
            return stdout_data

        return stdout_data.decode('utf-8')
