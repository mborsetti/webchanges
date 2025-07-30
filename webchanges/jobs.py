"""Jobs."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import asyncio
import copy
import email.utils
import hashlib
import html
import logging
import os
import re
import ssl
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.
import sys
import tempfile
import textwrap
import time
import warnings
from ftplib import FTP  # noqa: S402 A FTP-related module is being imported. FTP is considered insecure.
from http.client import responses as response_names
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence, TYPE_CHECKING
from urllib.parse import parse_qsl, quote, SplitResult, SplitResultBytes, urlencode, urlparse, urlsplit

import html2text
import yaml

from webchanges import __project_name__, __user_agent__
from webchanges.filters import FilterBase
from webchanges.util import TrackSubClasses

# https://stackoverflow.com/questions/712791
try:
    import simplejson as jsonlib
except ImportError:  # pragma: no cover
    import json as jsonlib  # type: ignore[no-redef]

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.handler import JobState
    from webchanges.storage import _Config

try:
    import httpx
except ImportError:  # pragma: no cover
    print("Required package 'httpx' not found; will attempt to run using 'requests'")
    httpx = None  # type: ignore[assignment]

if httpx is not None:
    from httpx import Headers

    try:
        import h2
    except ImportError:  # pragma: no cover
        h2 = None  # type: ignore[assignment]
else:
    from webchanges._vendored.headers import Headers

try:
    import requests
    import requests.adapters
    import urllib3
    import urllib3.exceptions
except ImportError as e:  # pragma: no cover
    requests = str(e)  # type: ignore[assignment]
    urllib3 = str(e)  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# reduce logging from httpx's sub-modules
if httpx is not None and logger.getEffectiveLevel() == logging.DEBUG:
    logging.getLogger('hpack').setLevel(logging.INFO)
    logging.getLogger('httpcore').setLevel(logging.INFO)


class NotModifiedError(Exception):
    """Raised when an HTTP 304 response status code (Not Modified client redirection) is received or the strong
    validation ETag matches the previous one; this indicates that there was no change in content."""

    ...


class BrowserResponseError(Exception):
    """Raised by 'url' jobs with 'use_browser: true' (i.e. using Playwright) when an HTTP error response status code is
    received."""

    def __init__(self, args: tuple[Any, ...], status_code: int | None) -> None:
        """

        :param args: Tuple with the underlying error args, typically a string with the error text.
        :param status_code: The HTTP status code received.
        """
        Exception.__init__(self)
        self.args = args
        self.status_code = status_code

    def __str__(self) -> str:
        if self.status_code:
            return (
                f'{self.__class__.__name__}: Received response HTTP {self.status_code} '
                f"{response_names.get(self.status_code, '')}"
                + (f' with content "{self.args[0]}"' if self.args[0] else '')
            )
        else:
            return str(self.args[0])


class JobBase(metaclass=TrackSubClasses):
    """The base class for Jobs."""

    __subclasses__: dict[str, 'JobBase'] = {}
    __anonymous_subclasses__: list['JobBase'] = []

    __kind__: str = ''  # The kind name
    __is_browser__: bool = False  # Whether Playwright is being launched (run separately with less parallelism)
    __required__: tuple[str, ...] = ()  # List of required subdirectives
    __optional__: tuple[str, ...] = ()  # List of optional subdirectives

    index_number: int = 0  # added at job loading

    # __required__ in derived classes
    url: str = ''
    command: str = ''
    use_browser: bool | None = False

    # __optional__ in derived classes
    _delay: float | None = None
    additions_only: bool | None = None
    block_elements: list[str] | None = None
    compared_versions: int | None = None
    contextlines: int | None = None
    cookies: dict[str, str] | None = None
    data: str | list | dict | None = None
    data_as_json: bool | None = None
    deletions_only: bool | None = None
    differ: dict[str, Any] | None = None  # added in 3.21
    diff_filters: str | list[str | dict[str, Any]] | None = None
    diff_tool: str | None = None  # deprecated in 3.21
    enabled: bool | None = None
    encoding: str | None = None
    evaluate: str | None = None  # Playwright
    filters: str | list[str | dict[str, Any]] | None = None
    guid: str = ''
    headers = Headers(encoding='utf-8')
    http_client: Literal['httpx', 'requests'] | None = None
    ignore_cached: bool | None = None
    ignore_connection_errors: bool | None = None
    ignore_default_args: bool | str | list[str] | None = None
    ignore_dh_key_too_small: bool | None = None
    ignore_http_error_codes: int | str | list[str] | None = None
    ignore_https_errors: bool | None = None
    ignore_timeout_errors: bool | None = None
    ignore_too_many_redirects: bool | None = None
    init_script: str | None = None  # Playwright
    initialization_js: str | None = None  # Playwright
    initialization_url: str | None = None  # Playwright
    is_markdown: bool | None = None
    kind: str | None = None  # hooks.py
    loop: asyncio.AbstractEventLoop | None = None
    markdown_padded_tables: bool | None = None
    max_tries: int | None = None
    method: Literal['GET', 'OPTIONS', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'] | None = None
    mime_type: str | None = None
    monospace: bool | None = None
    name: str | None = None
    navigate: str | None = None  # backwards compatibility (deprecated)
    no_conditional_request: bool | None = None
    no_redirects: bool | None = None
    note: str | None = None
    params: str | list | dict | None = None
    proxy: str | None = None
    referer: str | None = None  # Playwright
    retries: int | None = None
    ssl_no_verify: bool | None = None
    stderr: str | None = None  # urlwatch backwards compatibility for ShellJob (not used)
    suppress_repeated_errors: bool | None = None
    switches: list[str] | None = None
    timeout: int | float | None = None
    tz: str | None = None  # added by with_defaults, taken from reporter configuration
    user_data_dir: str | None = None
    user_visible_url: str | None = None
    wait_for: int | str | None = None  # pyppeteer backwards compatibility (deprecated)
    wait_for_function: str | dict[str, Any] | None = None  # Playwright
    wait_for_navigation: str | tuple[str, ...] | None = None
    wait_for_selector: str | dict[str, Any] | list[str | dict[str, Any]] | None = None  # Playwright
    wait_for_timeout: int | float | None = None  # Playwright
    wait_for_url: str | dict[str, Any] | None = None  # Playwright
    wait_until: Literal['commit', 'domcontentloaded', 'load', 'networkidle'] | None = None

    def __init__(self, **kwargs: Any) -> None:
        # backward-compatibility
        if 'filter' in kwargs:
            logger.info(f"Job {kwargs.get('index_number')}: Replacing deprecated directive 'filter' with 'filters'")
            kwargs['filters'] = kwargs.pop('filter')
        if 'diff_filter' in kwargs:
            logger.info(
                f"Job {kwargs.get('index_number')}: Replacing deprecated directive 'diff_filter' with 'diff_filter'"
            )
            kwargs['diff_filters'] = kwargs.pop('diff_filter')
        if 'https_proxy' in kwargs:
            logger.info(f"Job {kwargs.get('index_number')}: Replacing deprecated directive 'https_proxy' with 'proxy'")
            kwargs['proxy'] = kwargs.pop('https_proxy')
            kwargs.pop('http_proxy', None)
        elif 'http_proxy' in kwargs:
            logger.info(f"Job {kwargs.get('index_number')}: Replacing deprecated directive 'http_proxy' with 'proxy'")
            kwargs['proxy'] = kwargs.pop('http_proxy')

        # Fail if any required keys are not provided
        for k in self.__required__:
            if k not in kwargs:
                # do not alert for missing use_browser if kind is explicity stated
                if k != 'use_browser' or not kwargs.get('kind'):
                    raise ValueError(
                        f"Job {kwargs.get('index_number')}: Required directive '{k}' missing: '{kwargs}'"
                        f" ({kwargs.get('user_visible_url', kwargs.get('url', kwargs.get('command')))})"
                    )

        for k, v in list(kwargs.items()):
            setattr(self, k, v)

    @classmethod
    def job_documentation(cls) -> str:
        """Generates simple jobs documentation for use in the --features command line argument.

        :returns: A string to display.
        """
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
        """Get the 'location' of the job, i.e. the (user_visible) URL or command.

        :returns: The user_visible_url, the URL, or the command of the job.
        """
        raise NotImplementedError()

    def get_indexed_location(self) -> str:
        """Get the job number plus its 'location', i.e. the (user_visible) URL or command. Typically used in error
        displays.

        :returns: The job number followed by a colon and the 'location' of the job, i.e. its user_visible_url, URL,
           or command.
        """
        raise NotImplementedError()

    def set_base_location(self, location: str) -> None:
        """Sets the job's location (command or url) to location.  Used for changing location (uuid)."""
        raise NotImplementedError()

    def pretty_name(self) -> str:
        """Get the 'pretty name' of a job, i.e. either its 'name' (if defined) or the 'location' (user_visible_url,
        URL or command).

        :returns: The 'pretty name' the job.
        """
        raise NotImplementedError()

    def serialize(self) -> dict:
        """Serialize the Job object, excluding its index_number (e.g. for saving).

        :returns: A dict with the Job object serialized.
        """
        d = self.to_dict()
        d.pop('index_number', None)
        return d

    @classmethod
    def unserialize(cls, data: dict, filenames: list[Path] | None = None) -> 'JobBase':
        """Unserialize a dict with job data (e.g. from the YAML jobs file) into a JobBase type object.

        :param data: The dict with job data (e.g. from the YAML jobs file).
        :returns: A JobBase type object.
        """
        # Backwards compatibility with 'navigate' directive (deprecated)
        if filenames is None:
            filenames = []

        if data.get('kind') == 'shell':
            data['kind'] = 'command'

        if data.get('navigate') and not data.get('use_browser'):
            warnings.warn(
                f"Error in jobs file: Job directive 'navigate' is deprecated: replace with 'url' and add 'use_browser: "
                f"true':\n{yaml.safe_dump(data)}",
                DeprecationWarning,
            )
            data['url'] = data.get('url', data['navigate'])
            data['use_browser'] = True

        # Backwards-compatible with diff_tool
        if data.get('diff_tool') and not data.get('differ'):
            data['differ'] = {'name': 'command', 'command': data['diff_tool']}
        # Accept differ as a string
        elif isinstance(data.get('differ'), str):
            data['differ'] = {'name': data['differ']}
        elif data.get('differ') and not isinstance(data['differ'], dict):
            raise ValueError(
                f"Error in jobs file: Job directive 'differ: {data['differ']}' has to be a string or dict:\n"
                f'{yaml.safe_dump(data)}'
            )

        if 'kind' in data:
            # Used for hooks.py.
            try:
                job_subclass: JobBase = cls.__subclasses__[data['kind']]  # type: ignore[assignment]
            except KeyError:
                raise ValueError(
                    f"Error in jobs file: Job directive 'kind: {data['kind']}' does not match any known job kinds:\n"
                    f'{yaml.safe_dump(data)}'
                ) from None
        else:
            # Auto-detect the job subclass based on required directives.
            matched_subclasses: list[JobBase] = [
                subclass  # type: ignore[misc]
                for subclass in list(cls.__subclasses__.values())[1:]
                if all(data.get(required) for required in subclass.__required__)
            ]
            if len(matched_subclasses) == 1:
                job_subclass = matched_subclasses[0]
            elif len(matched_subclasses) > 1:
                number_matched: dict[JobBase, int] = {}
                for match in matched_subclasses:
                    number_matched[match] = [data.get(required) is not None for required in match.__required__].count(
                        True
                    )
                # noinspection PyUnresolvedReferences
                job_subclass = sorted(number_matched.items(), key=lambda x: x[1], reverse=True)[0][0]
            else:
                if len(data) == 1:
                    raise ValueError(
                        f"Error in jobs file: Job directive has no value or doesn't match a job type (check for "
                        f'errors/typos/escaping or documentation):\n{yaml.safe_dump(data)}'
                    )
                else:
                    raise ValueError(
                        f"Error in jobs file: Job directives (with values) don't match a job type (check for "
                        f'errors/typos/escaping):\n{yaml.safe_dump(data)}'
                    )

        # Remove extra required directives ("Falsy")
        other_subclasses: list[JobBase] = list(cls.__subclasses__.values())[1:]  # type: ignore[assignment]
        other_subclasses.remove(job_subclass)
        for other_subclass in other_subclasses:
            for k in other_subclass.__required__:
                if k not in job_subclass.__required__:
                    data.pop(k, None)

        job = job_subclass.from_dict(data, filenames)

        # Format headers and cookies (and turn values into strings to avoid httpx Exception):
        if isinstance(job.headers, dict):
            job.headers = Headers({k: str(v) for k, v in (job.headers or {}).items()}, encoding='utf-8')
        if isinstance(job.cookies, dict):
            job.cookies = {k: str(v) for k, v in job.cookies.items()} if job.cookies is not None else None
        return job

    def to_dict(self) -> dict:
        """Return all defined (not None) Job object directives, required and optional, as a serializable dict,
        converting Headers object (which are not JSON serializable) to dicts.

        :returns: A dict with all job directives as keys, ignoring those that are extras.
        """
        return {
            k: dict(getattr(self, k)) if isinstance(getattr(self, k), Headers) else getattr(self, k)
            for keys in {self.__required__, self.__optional__}
            for k in keys
            if getattr(self, k) is not None
        }

    @classmethod
    def from_dict(cls, data: dict, filenames: list[Path]) -> JobBase:
        """Create a JobBase class from a dict, checking that all keys are recognized (i.e. listed in __required__ or
        __optional__).

        :param data: Job data in dict format (e.g. from the YAML jobs file).
        :returns: A JobBase type object.
        """
        for k in data.keys():
            # backward-compatibility
            if k not in cls.__required__ + cls.__optional__ + ('filter', 'diff_filter', 'http_client', 'http_proxy'):
                if len(filenames) > 1:
                    jobs_files = ['in the concatenation of the jobs files:'] + [f'• {file},' for file in filenames]
                elif len(filenames) == 1:
                    jobs_files = [f'in jobs file {filenames[0]}:']
                else:
                    jobs_files = []
                raise ValueError(
                    '\n   '.join(
                        [f"Directive '{k}' is unrecognized in the following job"]
                        + jobs_files
                        + ['']
                        + ['---']
                        + yaml.safe_dump(data).splitlines()
                        + ['---\n']
                        + ['Please check for typos or refer to the documentation.']
                    )
                )
        return cls(**{k: v for k, v in list(data.items())})

    def __repr__(self) -> str:
        """Represent the Job object as a string.

        :returns: A string representing the Job.
        """
        return f"<{self.__kind__} {' '.join(f'{k}={v!r}' for k, v in list(self.to_dict().items()))}"

    def _dict_deep_merge(self, source: dict | Headers, destination: dict) -> dict:
        """Deep merges source dict into destination dict.

        :param source: The source dict.
        :param destination: The destination dict.
        :returns: The merged dict.
        """
        # https://stackoverflow.com/a/20666342
        for key, value in source.items():
            if isinstance(value, (dict, Headers)):
                # get node or create one
                node = destination.setdefault(key, {})
                self._dict_deep_merge(value, node)
            else:
                destination[key] = value

        return destination

    def _set_defaults(self, defaults: dict[str, Any] | None) -> None:
        """Merge default attributes (e.g. from configuration) into those of the Job object.

        :param defaults: The default Job parameters.
        """

        if isinstance(defaults, dict):
            # merge defaults from configuration (including dicts) into Job attributes without overwriting them
            for key, value in defaults.items():
                if key in self.__optional__:
                    if getattr(self, key) is None:  # for speed
                        setattr(self, key, value)
                    elif isinstance(defaults[key], (dict, Headers)) and isinstance(getattr(self, key), (dict, Headers)):
                        for subkey, subvalue in defaults[key].items():
                            if hasattr(self, key) and subkey not in getattr(self, key):
                                getattr(self, key)[subkey] = subvalue
                    # elif isinstance(defaults[key], list) and isinstance(getattr(self, key), list):
                    #     setattr(self, key, list(set(getattr(self, key) + defaults[key])))
                    else:
                        setattr(self, key, value)

    def with_defaults(self, config: _Config) -> JobBase:
        """Obtain a Job object that also contains defaults from the configuration.

        :param config: The configuration as a dict.
        :returns: A JobBase object.
        """
        job_with_defaults = copy.deepcopy(self)

        cfg = config.get('job_defaults')
        if isinstance(cfg, dict):
            if isinstance(self, UrlJob):
                job_with_defaults._set_defaults(cfg.get(UrlJob.__kind__))  # type: ignore[arg-type]
            elif isinstance(self, BrowserJob):
                job_with_defaults._set_defaults(cfg.get(BrowserJob.__kind__))  # type: ignore[arg-type]
            elif isinstance(self, ShellJob):
                job_with_defaults._set_defaults(cfg.get(ShellJob.__kind__))  # type: ignore[arg-type]
            # all is done last, so that more specific defaults are not overwritten
            job_with_defaults._set_defaults(cfg.get('all'))

        # backwards-compatible
        if hasattr(job_with_defaults, 'diff_tool'):
            if isinstance(job_with_defaults.diff_tool, str):
                job_with_defaults.differ = {'command': {'command': job_with_defaults.diff_tool}}
                warnings.warn(
                    f"Job {job_with_defaults.index_number}: 'diff_tool' is a deprecated job directive. Please use"
                    f" differ '{{'command': {job_with_defaults.diff_tool}}}' instead.",
                    DeprecationWarning,
                )
            elif job_with_defaults.diff_tool is not None:
                raise ValueError(
                    f"Job {job_with_defaults.index_number}: 'diff_tool' is a deprecated job directive. Please use "
                    'differ command instead.'
                )

        rep_cfg = config.get('report')
        if isinstance(rep_cfg, dict):
            tz = rep_cfg.get('tz')
            job_with_defaults.tz = tz

        return job_with_defaults

    def get_fips_guid(self) -> str:
        # TODO Implement SHA256 hash GUIDs
        """Calculate the GUID as a SHA256 hash of the location (URL or command).

        :returns: the GUID.
        """
        location = self.get_location()
        return hashlib.sha256(location.encode(), usedforsecurity=False).hexdigest()

    def get_guid(self) -> str:
        """Calculate the GUID, currently a simple SHA1 hash of the location (URL or command).

        :returns: the GUID.
        """
        location = self.get_location()
        return hashlib.sha1(location.encode(), usedforsecurity=False).hexdigest()

    def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved and the ETag.
        """
        raise NotImplementedError()

    def main_thread_enter(self) -> None:
        """Called from the main thread before running the job. No longer needed (does nothing)."""
        ...

    def main_thread_exit(self) -> None:
        """Called from the main thread after running the job. No longer needed (does nothing)."""
        ...

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        return tb

    def ignore_error(self, exception: Exception) -> bool | str:
        """Determine whether the error of the job should be ignored.

        :param exception: The exception.
        :returns: True or the string with the number of the HTTPError code if the error should be ignored,
           False otherwise.
        """
        return False

    def is_enabled(self) -> bool:
        """Returns whether job is enabled.

        :returns: Whether the job is enabled.
        """
        return self.enabled is None or self.enabled

    def set_to_monospace(self) -> None:
        """If unset, sets the monospace flag to True (will not override)."""
        if self.monospace is None:
            self.monospace = True

    def get_proxy(self) -> str | None:
        """Check that URL is http or https and return proxy value."""
        scheme = urlsplit(self.url).scheme
        if scheme not in {'http', 'https'}:
            raise ValueError(
                f'Job {self.index_number}: URL should start with https:// or http:// (check for typos): {self.url}'
            )
        proxy = self.proxy
        if proxy is None:
            if os.getenv((scheme + '_proxy').upper()):
                proxy = os.getenv((scheme + '_proxy').upper())
            logger.debug(
                f"Job {self.index_number}: Setting proxy from environment variable {(scheme + '_proxy').upper()}"
            )
        return proxy


class Job(JobBase):
    """Job class for jobs."""

    __required__: tuple[str, ...] = ()
    __optional__: tuple[str, ...] = (
        'additions_only',
        'compared_versions',
        'contextlines',
        'deletions_only',
        'differ',
        'diff_filters',
        'diff_tool',  # deprecated in 3.21
        'enabled',
        'filters',
        'index_number',
        'is_markdown',
        'kind',  # hooks.py
        'markdown_padded_tables',
        'max_tries',
        'monospace',
        'name',
        'no_conditional_request',
        'note',
        'suppress_repeated_errors',
        'user_visible_url',
    )

    def get_location(self) -> str:  # type: ignore[empty-body]
        """Get the 'location' of the job, i.e. the (user_visible) URL or command.

        :returns: The user_visible_url, the URL, or the command of the job.
        """
        ...

    def get_indexed_location(self) -> str:
        """Get the job number plus its 'location', i.e. the (user_visible) URL or command. Typically used in error
        displays.

        :returns: The job number followed by a colon and the 'location' of the job, i.e. its user_visible_url, URL,
           or command.
        """
        return f'Job {self.index_number}: {self.get_location()}'

    def pretty_name(self) -> str:
        """Get the 'pretty name' of a job, i.e. either its 'name' (if defined) or the 'location' (user_visible_url,
        URL or command).

        :returns: The 'pretty name' the job.
        """
        return self.name or self.get_location()

    def retrieve(  # type: ignore[empty-body]
        self,
        job_state: JobState,
        headless: bool = True,
    ) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved, the ETag, and the mime_type.
        """
        ...


CHARSET_RE = re.compile('text/(html|plain); charset=([^;]*)')


class UrlJobBase(Job):
    """The base class for jobs that use the 'url' key."""

    __required__: tuple[str, ...] = ('url',)
    __optional__: tuple[str, ...] = (
        'ignore_connection_errors',
        'ignore_http_error_codes',
        'ignore_timeout_errors',
        'ignore_too_many_redirects',
    )

    def get_headers(
        self,
        job_state: JobState,
        user_agent: str | None = __user_agent__,
        include_cookies: bool = True,
    ) -> Headers:
        """Get headers and modify them to add cookies and conditional request.

        :param job_state: The job state.
        :param user_agent: The user agent string.

        :returns: The headers.
        """

        if self.headers:
            headers = self.headers.copy()
        else:
            headers = Headers(encoding='utf-8')
        if 'User-Agent' not in headers and user_agent:
            headers['User-Agent'] = user_agent
        if include_cookies and self.cookies:
            if not isinstance(self.cookies, dict):
                raise TypeError(
                    f"Job {self.index_number}: Directive 'cookies' needs to be a dictionary; "
                    f"found a '{type(self.cookies).__name__}' ( {self.get_indexed_location()} ).'"
                )
            if 'Cookie' in headers:
                warnings.warn(
                    f"Job {self.index_number}: Found both a header 'Cookie' and a directive 'cookies'; "
                    f"please specify only one of them (using content of the cookies 'directive') "
                    f'( {self.get_indexed_location()} ).'
                )
            headers['Cookie'] = '; '.join([f'{k}={v}' for k, v in self.cookies.items()])
        if self.no_conditional_request:
            headers.pop('If-Modified-Since', None)
            headers.pop('If-None-Match', None)
        else:
            if self.ignore_cached or job_state.tries > 0:
                headers['Cache-Control'] = 'max-age=172800'
                headers['Expires'] = email.utils.formatdate()
                headers['If-Modified-Since'] = email.utils.formatdate(0)
                headers.pop('If-None-Match', None)
            else:
                if job_state.old_etag:
                    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag#caching_of_unchanged_resources
                    headers['If-None-Match'] = job_state.old_etag
                if job_state.old_timestamp is not None:
                    headers['If-Modified-Since'] = email.utils.formatdate(job_state.old_timestamp)
        return headers


class UrlJob(UrlJobBase):
    """Retrieve a URL from a web server."""

    __kind__ = 'url'

    __optional__: tuple[str, ...] = (
        'cookies',
        'data',
        'data_as_json',
        'encoding',
        'headers',
        'ignore_cached',
        'ignore_dh_key_too_small',
        'method',
        'no_redirects',
        'params',
        'proxy',
        'retries',
        'ssl_no_verify',
        'timeout',
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
        timeout: int | float | None,
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
            context.set_ciphers('DEFAULT@SECLEVEL=1')  # type: ignore[union-attr]
        else:
            context = not self.ssl_no_verify

        client = httpx.Client(
            headers=headers,
            cookies=self.cookies,
            verify=context,
            http2=http2,
            proxy=proxy,
            timeout=timeout,
            follow_redirects=(not self.no_redirects),
        )
        response = client.request(
            method=self.method,  # type: ignore[arg-type]
            url=self.url,
            data=self.data,  # type: ignore[arg-type]
            params=self.params,
        )
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
                    parsed_json = jsonlib.loads(response.text)
                    error_message = jsonlib.dumps(parsed_json, ensure_ascii=False, separators=(',', ': '))
                except jsonlib.JSONDecodeError:
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

            raise httpx.HTTPStatusError(http_error_msg, request=response.request, response=response)

        if response.status_code == 304:
            raise NotModifiedError(response.status_code)

        # Save ETag from response to be used as If-None-Match header in future requests
        if not response.history:  # no redirects
            etag = response.headers.get('ETag', '')
        else:
            logger.info(f'Job {self.index_number}: ETag not captured as response was redirected to {response.url}')
            etag = ''
        # Save the media type (fka MIME type)
        mime_type = response.headers.get('Content-Type', '').split(';')[0]

        if FilterBase.filter_chain_needs_bytes(self.filters):
            return response.content, etag, mime_type

        if self.encoding:
            response.encoding = self.encoding

        return response.text, etag, mime_type

    def _retrieve_requests(
        self, headers: Mapping[str, str | bytes] | None, timeout: int | float | None
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
                urllib3.util.ssl_.DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'  # type: ignore[attr-defined]
            except AttributeError:
                logger.error(
                    'Unable to ignore_dh_key_too_small due to bug in requests.packages.urrlib3.util.ssl.DEFAULT_CIPHERS'
                )
                logger.error('See https://github.com/psf/requests/issues/6443')

        response = requests.request(
            method=self.method,  # type: ignore[arg-type]
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
                    parsed_json = jsonlib.loads(response.text)
                    error_message = jsonlib.dumps(parsed_json, ensure_ascii=False, separators=(',', ': '))
                except jsonlib.JSONDecodeError:
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

            raise requests.HTTPError(http_error_msg, response=response)

        if response.status_code == 304:
            raise NotModifiedError(response.status_code)

        # Save ETag from response to be used as If-None-Match header in future requests
        if not response.history:  # no redirects
            etag = response.headers.get('ETag', '')
        else:
            logger.info(f'Job {self.index_number}: ETag not captured as response was redirected to {response.url}')
            etag = ''
        # Save the media type (fka MIME type)
        mime_type = response.headers.get('Content-Type', '').split(';')[0]

        if FilterBase.filter_chain_needs_bytes(self.filters):
            return response.content, etag, mime_type

        if self.encoding:
            response.encoding = self.encoding
        elif response.encoding == 'ISO-8859-1' and not CHARSET_RE.match(response.headers.get('Content-type', '')):
            # If the Content-Type header contains text and no explicit charset is present in the HTTP headers requests
            # follows RFC 2616 and defaults encoding to ISO-8859-1, but IRL this is often wrong; the below updates it
            # with whatever is detected by the charset_normalizer or chardet libraries used in requests
            # (see https://requests.readthedocs.io/en/latest/user/advanced/#encodings)
            logger.debug(
                f'Job {self.index_number}: Encoding updated to {response.apparent_encoding} from '
                f'{response.encoding}'
            )
            response.encoding = response.apparent_encoding

        return response.text, etag, mime_type

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

            if FilterBase.filter_chain_needs_bytes(self.filters):
                return filename.read_bytes(), '', 'application/octet-stream'
            else:
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
                if FilterBase.filter_chain_needs_bytes(self.filters):
                    data_bytes = b''

                    def callback_bytes(dt: bytes) -> None:
                        """Handle FTP callback."""
                        nonlocal data_bytes
                        data_bytes += dt

                    ftp.retrbinary(f'RETR {url.path}', callback_bytes)

                    return data_bytes, '', 'application/octet-stream'
                else:
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
                    self.data = jsonlib.dumps(self.data, ensure_ascii=False)
                else:
                    self.data = urlencode(self.data)
            elif not isinstance(self.data, str):
                raise TypeError(
                    f"Job {job_state.job.index_number}: Directive 'data' needs to be a string, dictionary or list; "
                    f'found a {type(self.data).__name__} ( {self.get_indexed_location()} ).'
                )

        else:
            if self.method is None:
                self.method = 'GET'

        # if self.headers:
        #     self.add_custom_headers(headers)

        # cookiejar (called by requests) expects strings or bytes-like objects; PyYAML will try to guess int etc.
        if self.timeout is None:
            # default timeout
            timeout: int | float | None = 60.0
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
            or not isinstance(requests, str)
            and isinstance(exception, requests.exceptions.RequestException)
        ):
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
        if httpx and isinstance(exception, httpx.HTTPError):
            if self.ignore_timeout_errors and isinstance(exception, httpx.TimeoutException):
                return True
            if self.ignore_connection_errors and isinstance(exception, httpx.TransportError):
                return True
            if self.ignore_too_many_redirects and isinstance(exception, httpx.TooManyRedirects):
                return True
            elif self.ignore_http_error_codes and isinstance(exception, httpx.HTTPStatusError):
                status_code = exception.response.status_code
                ignored_codes: list[str] = []
                if isinstance(self.ignore_http_error_codes, int) and self.ignore_http_error_codes == status_code:
                    return True
                elif isinstance(self.ignore_http_error_codes, str):
                    ignored_codes = [s.strip().lower() for s in self.ignore_http_error_codes.split(',')]
                elif isinstance(self.ignore_http_error_codes, list):
                    ignored_codes = [str(s).strip().lower() for s in self.ignore_http_error_codes]
                return str(status_code) in ignored_codes or f'{(status_code // 100)}xx' in ignored_codes
        elif not isinstance(requests, str) and isinstance(exception, requests.exceptions.RequestException):
            if self.ignore_connection_errors and isinstance(exception, requests.exceptions.ConnectionError):
                return True
            if self.ignore_timeout_errors and isinstance(exception, requests.exceptions.Timeout):
                return True
            if self.ignore_too_many_redirects and isinstance(exception, requests.exceptions.TooManyRedirects):
                return True
            elif (
                self.ignore_http_error_codes
                and isinstance(exception, requests.exceptions.HTTPError)
                and exception.response is not None
            ):
                status_code = exception.response.status_code
                ignored_codes = []
                if isinstance(self.ignore_http_error_codes, int) and self.ignore_http_error_codes == status_code:
                    return True
                elif isinstance(self.ignore_http_error_codes, str):
                    ignored_codes = [s.strip().lower() for s in self.ignore_http_error_codes.split(',')]
                elif isinstance(self.ignore_http_error_codes, list):
                    ignored_codes = [str(s).strip().lower() for s in self.ignore_http_error_codes]
                return str(status_code) in ignored_codes or f'{(status_code // 100)}xx' in ignored_codes
        return False


class BrowserJob(UrlJobBase):
    """Retrieve a URL using a real web browser (use_browser: true)."""

    __kind__ = 'browser'
    __is_browser__ = True

    __required__: tuple[str, ...] = ('use_browser',)
    __optional__: tuple[str, ...] = (
        'block_elements',
        'cookies',
        'data',
        'data_as_json',
        'evaluate',
        'headers',
        'ignore_default_args',  # Playwright
        'ignore_https_errors',
        'init_script',  # Playwright,
        'initialization_js',  # Playwright
        'initialization_url',  # Playwright
        'method',
        'navigate',
        'params',
        'proxy',
        'switches',
        'timeout',
        'user_data_dir',
        'wait_for',  # pyppeteer backwards compatibility (deprecated)
        'wait_for_function',  # Playwright
        'wait_for_navigation',
        'wait_for_selector',  # Playwright
        'wait_for_timeout',  # Playwright
        'wait_for_url',
        'wait_until',
    )

    _playwright: Any = None
    _playwright_browsers: dict = {}

    proxy_username: str = ''
    proxy_password: str = ''

    if TYPE_CHECKING:
        try:
            from playwright.sync_api import Page, Response
        except ImportError:  # pragma: no cover
            pass

    def get_location(self) -> str:
        """Get the 'location' of the job, i.e. the (user_visible) URL.

        :returns: The user_visible_url or URL of the job.
        """
        return self.user_visible_url or self.url

    def set_base_location(self, location: str) -> None:
        """Sets the job's location (command or url) to location.  Used for changing location (uuid)."""
        self.url = location
        self.guid = self.get_guid()

    def retrieve(
        self,
        job_state: JobState,
        headless: bool = True,
        response_handler: Callable[[Page], Response] | None = None,
        content_handler: Callable[[Page], tuple[str | bytes, str, str]] | None = None,
    ) -> tuple[str | bytes, str, str]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.

        :raises ValueError: If there is a problem with the value supplied in one of the keys in the configuration file.
        :raises TypeError: If the value provided in one of the directives is not of the correct type.
        :raises ImportError: If the playwright package is not installed.
        :raises BrowserResponseError: If a browser error or an HTTP response code between 400 and 599 is received.
        :returns: The data retrieved and the ETag.
        """
        job_state._http_client_used = 'playwright'

        if self._delay:  # pragma: no cover  TODO not yet implemented.
            logger.debug(f'Delaying for {self._delay} seconds (duplicate network location)')
            time.sleep(self._delay)

        try:
            from playwright._repo_version import version as playwright_version
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import Route, sync_playwright
        except ImportError:  # pragma: no cover
            raise ImportError(
                f"Python package 'playwright' is not installed; cannot run jobs with the 'use_browser: true' "
                f"directive. Please install dependencies with 'pip install webchanges[use_browser]' and run again. "
                f'({job_state.job.get_indexed_location()})'
            ) from None
        try:
            import psutil
        except ImportError:  # pragma: no cover
            raise ImportError(
                f"Python package 'psutil' is not installed; cannot run jobs with the 'use_browser: true' "
                f"directive. Please install dependencies with 'pip install webchanges[use_browser]' and run again. "
                f'({job_state.job.get_indexed_location()})'
            ) from None

        # deprecations
        if self.wait_for:
            raise ValueError(
                f"Job {job_state.job.index_number}: Directive 'wait_for' is deprecated with Playwright; replace with "
                f"'wait_for_function', 'wait_for_selector' or 'wait_for_timeout'."
            )
        if self.wait_until in {'networkidle0', 'networkidle2'}:
            warnings.warn(
                f"Job {self.index_number}: Value '{self.wait_until}' of the 'wait_until' directive is deprecated "
                f"with Playwright; for future compatibility replace it with 'networkidle'.",
                DeprecationWarning,
            )
            self.wait_until = 'networkidle'
        if self.wait_for_navigation:
            warnings.warn(
                f"Job {self.index_number}: Directive 'wait_for_navigation' is deprecated with Playwright; "
                "for future compatibility replace it with 'wait_for_url'.",
                DeprecationWarning,
            )
            if isinstance(self.wait_for_navigation, str):
                self.wait_for_url = self.wait_for_navigation
            else:
                warnings.warn(
                    f"Job {self.index_number}: Directive 'wait_for_navigation' is "
                    f'of type {type(self.wait_for_navigation).__name__} and cannot be converted for use with '
                    f"Playwright; please use 'wait_for_url' (see documentation)  ( {self.get_indexed_location()} ).",
                    DeprecationWarning,
                )

        headers = self.get_headers(job_state, user_agent=None)

        proxy_str = self.get_proxy()
        if proxy_str is not None:
            proxy_split: SplitResult | SplitResultBytes = urlsplit(proxy_str)
            proxy = {
                'server': (
                    f'{proxy_split.scheme!s}://{proxy_split.hostname!s}:{proxy_split.port!s}'
                    if proxy_split.port
                    else ''
                ),
                'username': str(proxy_split.username),
                'password': str(proxy_split.password),
            }
            logger.debug(f'Job {self.index_number}: Proxy: {proxy}')
        else:
            proxy = None

        if self.switches:
            if isinstance(self.switches, str):
                self.switches = self.switches.split(',')
            if not isinstance(self.switches, list):
                raise TypeError(
                    f"Job {job_state.job.index_number}: Directive 'switches' needs to be a string or list; found a "
                    f'{type(self.switches).__name__} ( {self.get_indexed_location()} ).'
                )
            args: list[str] | None = [f"--{switch.removeprefix('--')}" for switch in self.switches]
        else:
            args = None

        if self.ignore_default_args:
            if isinstance(self.ignore_default_args, str):
                self.ignore_default_args = self.ignore_default_args.split(',')
            ignore_default_args = self.ignore_default_args
            if isinstance(ignore_default_args, list):
                ignore_default_args = [f"--{a.removeprefix('--')}" for a in ignore_default_args]
            elif not isinstance(self.ignore_default_args, bool):
                raise TypeError(
                    f"Job {job_state.job.index_number}: Directive 'ignore_default_args' needs to be a bool, string or "
                    f'list; found a {type(self.ignore_default_args).__name__} ( {self.get_indexed_location()} ).'
                )
        else:
            ignore_default_args = None

        timeout = self.timeout * 1000 if self.timeout else 120000  # Playwright's default of 30 seconds is too short

        # memory
        virtual_memory = psutil.virtual_memory().available
        swap_memory = psutil.swap_memory().free
        start_free_mem = virtual_memory + swap_memory
        logger.debug(
            f'Job {job_state.job.index_number}: Found {virtual_memory / 1e6:,.0f} MB of available physical memory '
            f'(plus {swap_memory / 1e6:,.0f} MB of swap) before launching the browser.'
        )

        # launch browser
        with sync_playwright() as p:
            executable_path = os.getenv('WEBCHANGES_BROWSER_PATH')
            channel = None if executable_path else 'chrome'
            browser_name = executable_path or 'Chrome'
            no_viewport = False if not self.switches else any('--window-size' in switch for switch in self.switches)
            if not self.user_data_dir:
                browser = p.chromium.launch(
                    executable_path=executable_path,
                    channel=channel,
                    args=args,
                    ignore_default_args=ignore_default_args,
                    timeout=timeout,
                    headless=headless,
                    proxy=proxy,  # type: ignore[arg-type]
                )
                browser_version = browser.version
                user_agent = headers.pop(
                    'User-Agent',
                    f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                    f"Chrome/{browser_version.split('.', maxsplit=1)[0]}.0.0.0 Safari/537.36",
                )
                context = browser.new_context(
                    no_viewport=no_viewport,
                    ignore_https_errors=self.ignore_https_errors,
                    user_agent=user_agent,  # will be detected if in headers
                    extra_http_headers=dict(headers),
                )
                logger.info(
                    f'Job {self.index_number}: Playwright {playwright_version} launched {browser_name} browser'
                    f' {browser_version}'
                )

            else:
                user_agent = headers.pop('User-Agent', '')

                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    channel=channel,
                    executable_path=executable_path,
                    args=args,
                    ignore_default_args=ignore_default_args,
                    headless=headless,
                    proxy=proxy,  # type: ignore[arg-type]
                    no_viewport=no_viewport,
                    ignore_https_errors=self.ignore_https_errors,
                    extra_http_headers=dict(headers),
                    user_agent=user_agent,  # will be detected if in headers
                )
                browser_version = ''
                logger.info(
                    f'Job {self.index_number}: Playwright {playwright_version} launched {browser_name} browser '
                    f'from user data directory {self.user_data_dir}'
                )

            if self.init_script:
                context.add_init_script(self.init_script)

            # set default timeout
            context.set_default_timeout(timeout)

            # # launch playwright (memoized)
            # if self._playwright is None:
            #     logger.info('Starting the instance of playwright')
            #     self._playwright = sync_playwright().start()  # TODO This should be in a context manager with .stop()

            # # launch browser (memoized)
            # executable_path = os.getenv('WEBCHANGES_BROWSER_PATH')
            # browser_key = msgpack.packb({1: executable_path, 2: args, 3: self.headless})
            # browser = self._playwright_browsers.get(browser_key)
            # print(f'playwright about to start browser for job {job_state.job.index_number}')
            # if not browser:
            #     logger.info(f'Starting a new browser with key {browser_key}')
            #     print(f'Starting a new browser with key {browser_key}')
            #     channel = None if executable_path else 'chrome'
            #     playwright = job_state.playwright
            #     if not playwright:
            #         print(f'No playwright found for job {job_state.job.index_number}')
            #         playwright = sync_playwright().start()
            #     browser = playwright.chromium.launch(
            #         executable_path=executable_path,
            #         channel=channel,
            #         args=args,
            #         headless=self.headless,
            #         proxy={'server': 'http://per-context'},
            #     )
            #     print(f'playwright browser launched for job {job_state.job.index_number}')
            #     self._playwright_browsers[browser_key] = browser
            #
            # # launch new browser context for this job
            #
            # context = browser.new_context(
            #     ignore_https_errors=self.ignore_https_errors,
            #     extra_http_headers=dict(headers),
            #     proxy=proxy,
            # )

            # open a page
            page = context.new_page()
            # the below to bypass detection; from https://intoli.com/blog/not-possible-to-block-chrome-headless/
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined });"
                'window.chrome = {runtime: {},};'  # This is abbreviated: entire content is huge!!
                "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5] });"
            )

            url = self.url
            if self.initialization_url:
                logger.info(f'Job {self.index_number}: Initializing website by navigating to {self.initialization_url}')
                try:
                    response = page.goto(
                        self.initialization_url,
                    )
                except PlaywrightError as e:
                    logger.info(f'Job {self.index_number}: Website initialization page returned error {e}')
                    context.close()
                    raise e

                if not response:
                    context.close()
                    raise BrowserResponseError(('No response received from browser',), None)

                if self.initialization_js:
                    logger.info(f"Job {self.index_number}: Running init script '{self.initialization_js}'")
                    page.evaluate(self.initialization_js)
                    if self.wait_for_url:
                        logger.info(f'Job {self.index_number}: Waiting for page to navigate to {self.wait_for_url}')
                        page.wait_for_url(self.wait_for_url, wait_until=self.wait_until)  # type: ignore[arg-type]
                updated_url = page.url
                init_url_params = dict(parse_qsl(urlparse(updated_url).params))
                try:
                    new_url = url.format(**init_url_params)
                except KeyError as e:
                    context.close()
                    raise ValueError(
                        f"Job {job_state.job.index_number}: Directive 'initialization_url' did not find key"
                        f" {e} to substitute in 'url'."
                    )
                if new_url != url:
                    url = new_url
                    logger.info(f'Job {self.index_number}: URL updated to {url}')

            data = None
            if self.data:
                if not self.method:
                    self.method = 'POST'
                logger.info(f'Job {self.index_number}: Sending POST request to {url}')
                if 'Content-Type' not in headers:
                    if self.data_as_json:
                        headers['Content-Type'] = 'application/json'
                    else:
                        headers['Content-Type'] = 'application/x-www-form-urlencoded'
                if isinstance(self.data, (dict, list)):
                    if self.data_as_json:
                        data = jsonlib.dumps(self.data, ensure_ascii=False)
                    else:
                        data = urlencode(self.data)
                elif isinstance(self.data, str):
                    data = quote(self.data)
                else:
                    raise ValueError(
                        f"Job {job_state.job.index_number}: Directive 'data' needs to be a string, dictionary or list; "
                        f'found a {type(self.data).__name__} ( {self.get_indexed_location()} ).'
                    )

            if self.params is not None:
                if isinstance(self.params, (dict, list)):
                    params = urlencode(self.params)
                elif isinstance(self.params, str):
                    params = quote(self.params)
                else:
                    raise ValueError(
                        f"Job {job_state.job.index_number}: Directive 'params' needs to be a string, dictionary or "
                        f'list; found a {type(self.params).__name__} ( {self.get_indexed_location()} ).'
                    )
                self.url += f'?{params}'

            if self.method and self.method != 'GET':

                def handle_route(route: Route) -> None:
                    """Handler function to change the route (a pyee.EventEmitter callback)."""
                    logger.info(f'Job {self.index_number}: Intercepted route to change request method to {self.method}')
                    route.continue_(method=str(self.method), post_data=data)

                page.route(url, handler=handle_route)

            if self.block_elements:
                if isinstance(self.block_elements, str):
                    self.block_elements = self.block_elements.split(',')
                if not isinstance(self.block_elements, list):
                    context.close()
                    raise TypeError(
                        f"'block_elements' needs to be a string or list, not {type(self.block_elements)} "
                        f'( {self.get_indexed_location()} )'
                    )
                playwright_request_resource_types = [
                    # https://playwright.dev/docs/api/class-request#request-resource-type
                    'document',
                    'stylesheet',
                    'image',
                    'media',
                    'font',
                    'script',
                    'texttrack',
                    'xhr',
                    'fetch',
                    'eventsource',
                    'websocket',
                    'manifest',
                    'other',
                ]
                for element in self.block_elements:
                    if element not in playwright_request_resource_types:
                        context.close()
                        raise ValueError(
                            f"Unknown '{element}' resource type in 'block_elements' "
                            f'( {self.get_indexed_location()} )'
                        )
                logger.info(f"Job {self.index_number}: Found 'block_elements' and adding a route to intercept elements")

                def handle_elements(route: Route) -> None:
                    """Handler function to block elements (a pyee.EventEmitter callback)."""
                    if route.request.resource_type in self.block_elements:  # type: ignore[operator]
                        logger.debug(
                            f'Job {self.index_number}: Intercepted retrieval of resource_type '
                            f"'{route.request.resource_type}' and aborting"
                        )
                        route.abort()
                    else:
                        route.continue_()

                page.route('**/*', handler=handle_elements)

            # navigate page
            logger.info(f'Job {self.index_number}: {browser_name} {browser_version} navigating to {url}')
            logger.debug(f'Job {self.index_number}: User agent {user_agent}')
            logger.debug(f'Job {self.index_number}: Extra headers {headers}')

            # def handle_response(response: Response) -> None:
            #     """TODO: Handler function to detect if a 304 is returned."""
            #     logger.debug(f'Job {self.index_number}: Intercepted response with {response.status} status')
            #     if response.status == 304 and response.url == url:
            #         # context.close()
            #         raise NotModifiedError(response.status)
            #
            # page.on('response', handle_response)

            try:
                if response_handler is not None:
                    response_handler(page)
                else:
                    response = page.goto(
                        url,
                        wait_until=self.wait_until,
                        referer=self.referer,
                    )

                if not response:
                    context.close()
                    raise BrowserResponseError(('No response received from browser',), None)

                if response.ok:
                    if self.wait_for_url:
                        logger.info(f'Job {self.index_number}: Waiting for page to navigate to {self.wait_for_url}')
                        if isinstance(self.wait_for_url, str):
                            page.wait_for_url(
                                self.wait_for_url,
                                wait_until=self.wait_until,
                                timeout=timeout,
                            )
                        elif isinstance(self.wait_for_url, dict):
                            page.wait_for_url(**self.wait_for_url)
                        else:
                            context.close()
                            raise ValueError(
                                f"Job {job_state.job.index_number}: Directive 'wait_for_url' can only be a string or a "
                                f'dictionary; found a {type(self.wait_for_url.__name__)} '
                                f'( {self.get_indexed_location()} ).'
                            )
                    if self.wait_for_selector:
                        logger.info(f'Job {self.index_number}: Waiting for selector {self.wait_for_selector}')
                        if not isinstance(self.wait_for_selector, list):
                            self.wait_for_selector = [self.wait_for_selector]
                        for selector in self.wait_for_selector:
                            if isinstance(selector, str):
                                page.wait_for_selector(selector)
                            elif isinstance(selector, dict):
                                page.wait_for_selector(**selector)
                            else:
                                context.close()
                                raise ValueError(
                                    f"Job {job_state.job.index_number}: Directive 'wait_for_selector' can only be a "
                                    f'string or a dictionary, or a list of these; found a '
                                    f'{type(self.wait_for_selector).__name__} ( {self.get_indexed_location()} ).'
                                )
                    if self.wait_for_function:
                        logger.info(f'Job {self.index_number}: Waiting for function {self.wait_for_function}')
                        if isinstance(self.wait_for_function, str):
                            page.wait_for_function(self.wait_for_function)
                        elif isinstance(self.wait_for_function, dict):
                            page.wait_for_function(**self.wait_for_function)
                        else:
                            context.close()
                            raise ValueError(
                                f"Job {job_state.job.index_number}: Directive 'wait_for_function' can only be a string "
                                f'or a dictionary; found a {type(self.wait_for_function).__name__}'
                                f' ( {self.get_indexed_location()} ).'
                            )
                    if self.wait_for_timeout:
                        logger.info(f'Job {self.index_number}: Waiting for timeout {self.wait_for_timeout}')
                        if isinstance(self.wait_for_timeout, (int, float)) and not isinstance(
                            self.wait_for_timeout, bool
                        ):
                            page.wait_for_timeout(self.wait_for_timeout * 1000)
                        else:
                            context.close()
                            raise ValueError(
                                f"Job {job_state.job.index_number}: Directive 'wait_for_timeout' can only be a number; "
                                f'found a {type(self.wait_for_timeout).__name__}'
                                f' ( {self.get_indexed_location()} ).'
                            )

            except PlaywrightError as e:
                logger.info(f'Job {self.index_number}: Browser returned error {e}\n({url})')
                if logger.root.level <= 20:  # logging.INFO
                    screenshot_filename = tempfile.NamedTemporaryFile(
                        prefix=f'{__project_name__}_screenshot_{self.index_number}_', suffix='.png', delete=False
                    ).name
                    try:
                        page.screenshot(path=screenshot_filename)
                        logger.info(f'Job {self.index_number}: Screenshot saved at {screenshot_filename}')
                    except PlaywrightError:
                        Path(screenshot_filename).unlink()
                    full_filename = tempfile.NamedTemporaryFile(
                        prefix=f'{__project_name__}_screenshot-full_{self.index_number}_',
                        suffix='.png',
                        delete=False,
                    ).name
                    try:
                        page.screenshot(path=full_filename, full_page=True)
                        logger.info(f'Job {self.index_number}: Full page image saved at {full_filename}')
                    except PlaywrightError:
                        Path(full_filename).unlink()
                    html_filename = tempfile.NamedTemporaryFile(
                        prefix=f'{__project_name__}_content_{self.index_number}_', suffix='.html', delete=False
                    ).name
                    try:
                        Path(html_filename).write_text(page.content())
                        logger.info(f'Job {self.index_number}: Page HTML content saved at {html_filename}')
                    except PlaywrightError:
                        Path(html_filename).unlink()
                context.close()
                raise BrowserResponseError(e.args, None) from None

            # if response.status and 400 <= response.status < 600:
            #     context.close()
            #     raise BrowserResponseError((response.status_text,), response.status)
            if not response.ok:
                # logger.info(
                #     f'Job {self.index_number}: Received response HTTP {response.status} {response.status_text} from '
                #     f'{response.url}'
                # )
                # logger.debug(f'Job {self.index_number}: Response headers {response.all_headers()}')
                message = response.status_text
                if response.status != 404:
                    body = page.text_content('body')
                    if body is not None:
                        message = f'{message}\n{body.strip()}' if message else body.strip()
                context.close()
                raise BrowserResponseError((message,), response.status)

            # extract content
            if content_handler is not None:
                return content_handler(page)
            else:
                if self.evaluate is not None:
                    content = page.evaluate(self.evaluate)
                    mime_type = 'text'
                else:
                    content = page.content()
                    mime_type = response.header_value('content-type') or ''
                etag = response.header_value('etag') or ''
                virtual_memory = psutil.virtual_memory().available
                swap_memory = psutil.swap_memory().free
                used_mem = start_free_mem - (virtual_memory + swap_memory)
                logger.debug(
                    f'Job {job_state.job.index_number}: Found {virtual_memory / 1e6:,.0f} MB of available physical '
                    f'memory (plus {swap_memory / 1e6:,.0f} MB of swap) before closing the browser (a decrease of '
                    f'{used_mem / 1e6:,.0f} MB).'
                )

                # if no name directive is given, set to title tag if found in HTML or XML, truncated to 60 chars
                if not self.name and content:
                    title = re.search(r'<title.*?>(.+?)</title>', content)
                    if title:
                        self.name = html.unescape(title.group(1))[:60]

                context.close()
                return content, etag, mime_type

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        exception_str = str(exception).strip()
        if self.proxy and 'net::ERR' in exception_str:
            exception_str += f'\n\n(Job has proxy {self.proxy})'
            return exception_str
        return exception_str

    def ignore_error(self, exception: Exception) -> bool | str:
        """Determine whether the error of the job should be ignored.

        :param exception: The exception.
        :returns: True or the string with the number of the HTTPError code if the error should be ignored,
           False otherwise.
        """
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
            'INVALID_ECH_CONFIG_LIST',
        ]

        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        if isinstance(exception, (BrowserResponseError, PlaywrightError)):
            if self.ignore_connection_errors:
                if isinstance(exception, (BrowserResponseError, PlaywrightError)) or any(
                    str(exception.args[0]).split()[0] == f'net::ERR_{error}' for error in CHROMIUM_CONNECTION_ERRORS
                ):
                    return True
            if self.ignore_timeout_errors:
                if (
                    isinstance(exception, PlaywrightTimeoutError)
                    or str(exception.args[0].split()[0]) == 'net::ERR_TIMED_OUT'
                ):
                    return True
            if self.ignore_too_many_redirects:
                if str(exception.args[0].split()[0]) == 'net::ERR_TOO_MANY_REDIRECTS':
                    return True

        if isinstance(exception, BrowserResponseError) and self.ignore_http_error_codes:
            status_code = exception.status_code
            ignored_codes: list[str] = []
            if isinstance(self.ignore_http_error_codes, int) and self.ignore_http_error_codes == status_code:
                return True
            elif isinstance(self.ignore_http_error_codes, str):
                ignored_codes = [s.strip().lower() for s in self.ignore_http_error_codes.split(',')]
            elif isinstance(self.ignore_http_error_codes, list):
                ignored_codes = [str(s).strip().lower() for s in self.ignore_http_error_codes]
            if isinstance(status_code, int):
                return str(status_code) in ignored_codes or f'{(status_code // 100) in ignored_codes}xx'
            else:
                return str(status_code)
        return False


class ShellJob(Job):
    """Run a shell command and get its standard output."""

    __kind__ = 'command'

    __required__: tuple[str, ...] = ('command',)
    __optional__: tuple[str, ...] = ('stderr',)  # ignored; here for backwards compatibility

    def get_location(self) -> str:
        """Get the 'location' of the job, i.e. the command.

        :returns: The command of the job.
        """
        return self.user_visible_url or self.command

    def set_base_location(self, location: str) -> None:
        """Sets the job's location (command or url) to location.  Used for changing location (uuid)."""
        self.command = location
        self.guid = self.get_guid()

    def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data, ETag (which is blank) and mime_type (also blank).

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved and the ETag and mime_type.
        :raises subprocess.CalledProcessError: Subclass of SubprocessError, raised when a process returns a non-zero
           exit status.
        :raises subprocess.TimeoutExpired: Subclass of SubprocessError, raised when a timeout expires while waiting for
           a child process.
        """
        needs_bytes = FilterBase.filter_chain_needs_bytes(self.filters)
        try:
            return (
                subprocess.run(
                    self.command,
                    capture_output=True,
                    shell=True,  # noqa: S602 subprocess call with shell=True identified, security issue.
                    check=True,
                    text=(not needs_bytes),
                ).stdout,
                '',
                'application/octet-stream' if needs_bytes else 'text/plain',
            )
        except subprocess.CalledProcessError as e:
            logger.info(f'Job {self.index_number}: Command: {e.cmd} ')
            logger.info(f'Job {self.index_number}: Failed with returncode {e.returncode}')
            logger.info(f'Job {self.index_number}: stderr : {e.stderr}')
            logger.info(f'Job {self.index_number}: stdout : {e.stdout}')
            raise

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        if isinstance(exception, subprocess.CalledProcessError):
            # Instead of a full traceback, just show the HTTP error
            return (
                f'Error: Exit status {exception.returncode} returned from subprocess:\n'
                f'{(exception.stderr or exception.stdout).strip()}'
            )
        elif isinstance(exception, FileNotFoundError):
            return f'Error returned by OS: {str(exception).strip()}'
        return tb
