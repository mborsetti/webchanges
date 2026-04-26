"""Base job classes."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import asyncio  # noqa: TC003 (required for type check)
import copy
import email.utils
import hashlib
import logging
import os
import re
import textwrap
import warnings
from typing import TYPE_CHECKING, Any, Literal, get_type_hints
from urllib.parse import urlsplit

import yaml

from webchanges import __user_agent__
from webchanges.filters._base import FiltersList  # noqa: TC001 (required for type check)
from webchanges.util import TrackSubClasses

try:
    import httpx
except ImportError:  # pragma: no cover
    print("Required package 'httpx' not found; will attempt to run using 'requests'")
    httpx = None  # ty:ignore[invalid-assignment]

if httpx is not None:
    from httpx import Headers

    try:
        import h2
    except ImportError:  # pragma: no cover
        h2 = None  # ty:ignore[invalid-assignment]
else:
    from webchanges._vendored.headers import Headers

try:
    from typeguard import TypeCheckError, check_type  # ty:ignore[unresolved-import]
except ImportError:
    from webchanges._vendored.typeguard import TypeCheckError, check_type

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from pathlib import Path

    from webchanges.handler import JobState
    from webchanges.storage import _Config

logger = logging.getLogger(__name__)


# Custom YAML representer function for httpx.Headers
def represent_headers(dumper: yaml.SafeDumper, data: Headers) -> yaml.MappingNode:
    return dumper.represent_dict(dict(data))


# Add the custom representer to the SafeDumper
yaml.SafeDumper.add_representer(Headers, represent_headers)

# reduce logging from httpx's sub-modules
if httpx is not None and logger.getEffectiveLevel() == logging.DEBUG:
    logging.getLogger('hpack').setLevel(logging.INFO)
    logging.getLogger('httpcore').setLevel(logging.INFO)


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
    use_browser: bool | str | None = False

    # __optional__ in derived classes
    _delay: float | None = None  # TODO: WIP experiment
    additions_only: bool | float | str | None = None
    block_elements: list[str] | None = None  # BrowserJob
    compared_versions: int | None = None
    contextlines: int | None = None
    cookies: dict[str, str] | None = None  # UrlJobBase
    data: str | list | dict | None = None  # UrlJobBase
    data_as_json: bool | None = None  # UrlJobBase
    deletions_only: bool | None = None
    differ: dict[str, Any] | None = None  # added in 3.21
    diff_filters: str | list[str | dict[str, Any]] | None = None
    diff_tool: str | None = None  # deprecated in 3.21
    empty_as_transient: bool | None = None  # UrlJob
    enabled: bool | None = None
    encoding: str | None = None  # UrlJobBase
    evaluate: str | None = None  # BrowserJob
    filters: FiltersList | list[FiltersList | dict[str, Any]] | None = None
    fingerprints: dict[str, str | dict[str, Any]] | None = None  # UrlJob (curl_cffi backend only)
    guid: str = ''
    headers = Headers(encoding='utf-8')  # UrlJobBase
    http_client: Literal['httpx', 'requests', 'curl_cffi'] | None = None  # UrlJob
    http_version: Literal['v1', 'v2', 'v2tls', 'v2_prior_knowledge', 'v3', 'v3only'] | None = None  # UrlJob
    http_credentials: str | None = None  # BrowserJob
    ignore_cached: bool | None = None  # UrlJobBase
    ignore_connection_errors: bool | None = None  # UrlJobBase
    ignore_default_args: bool | str | list[str] | None = None  # BrowserJob
    ignore_dh_key_too_small: bool | None = None  # UrlJob
    ignore_http_error_codes: list[int | str] | int | str | None = None  # UrlJobBase
    ignore_https_errors: bool | None = None  # BrowserJob
    ignore_timeout_errors: bool | None = None  # UrlJobBase
    ignore_too_many_redirects: bool | None = None  # UrlJobBase
    impersonate: str | None = None  # UrlJob (curl_cffi backend only)
    init_script: str | None = None  # BrowserJob
    initialization_js: str | None = None  # BrowserJob
    initialization_url: str | None = None  # UrlJob, BrowserJob
    is_markdown: bool | None = None
    kind: str | None = None  # hooks.py
    loop: asyncio.AbstractEventLoop | None = None
    markdown_padded_tables: bool | None = None
    max_tries: int | None = None
    method: Literal['GET', 'OPTIONS', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'] | None = None  # UrlJobBase
    mime_type: str | None = None
    monospace: bool | None = None
    name: str | None = None
    navigate: str | None = None  # BrowserJob (DEPRECATED)
    no_conditional_request: bool | None = None
    no_redirects: bool | None = None  # UrlJob
    note: str | None = None
    params: str | list | dict[str, str] | None = None  # UrlJobBase
    proxy: str | None = None  # UrlJobBase
    referer: str | None = None  # BrowserJob
    retries: int | None = None  # UrlJob
    ssl_no_verify: bool | None = None  # UrlJob
    stderr: str | None = None  # urlwatch backwards compatibility for ShellJob (not used)
    suppress_error_ended: bool | None = None
    suppress_errors: bool | None = None
    suppress_repeated_errors: bool | None = None
    switches: list[str] | None = None  # BrowserJob
    timeout: float | None = None  # UrlJobBase
    tz: str | None = None  # added by with_defaults, taken from reporter configuration
    user_data_dir: str | None = None  # BrowserJob
    user_visible_url: str | None = None
    wait_for: int | str | None = None  # BrowserJob (DEPRECATED)
    wait_for_function: str | dict[str, str] | None = None  # BrowserJob
    wait_for_navigation: str | tuple[str, ...] | None = None  # BrowserJob (DEPRECATED)
    wait_for_selector: str | dict[str, str] | list[str | dict[str, str]] | None = None  # BrowserJob
    wait_for_timeout: float | None = None  # BrowserJob
    wait_for_url: str | None = None  # BrowserJob
    wait_until: Literal['commit', 'domcontentloaded', 'load', 'networkidle'] | None = None  # BrowserJob

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
            # do not alert for missing use_browser if kind is explicity stated
            if k not in kwargs and (k != 'use_browser' or not kwargs.get('kind')):
                raise ValueError(
                    f"Job {kwargs.get('index_number')}: Required directive '{k}' missing: '{kwargs}'"
                    f' ({kwargs.get("user_visible_url", kwargs.get("url", kwargs.get("command")))})'
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
        raise NotImplementedError

    def get_indexed_location(self) -> str:
        """Get the job number plus its 'location', i.e. the (user_visible) URL or command. Typically used in error
        displays.

        :returns: The job number followed by a colon and the 'location' of the job, i.e. its user_visible_url, URL,
           or command.
        """
        raise NotImplementedError

    def set_base_location(self, location: str) -> None:
        """Sets the job's location (command or url) to location.  Used for changing location (uuid)."""
        raise NotImplementedError

    def pretty_name(self) -> str:
        """Get the 'pretty name' of a job, i.e. either its 'name' (if defined) or the 'location' (user_visible_url,
        URL or command).

        :returns: The 'pretty name' the job.
        """
        raise NotImplementedError

    def serialize(self) -> dict:
        """Serialize the Job object, excluding its index_number (e.g. for saving).

        :returns: A dict with the Job object serialized.
        """
        d = self.to_dict()
        d.pop('index_number', None)
        return d

    def validate(self) -> None:
        """Checks all instance attributes against class type hints."""
        # Pulls the annotations defined at the class level
        hints = get_type_hints(self.__class__)

        for attr_name, expected_type in hints.items():
            if attr_name.startswith('__'):  # 'attr_name not in dir(self)' test for hooks
                continue

            current_value = getattr(self, attr_name)
            # check for correct types
            try:
                check_type(current_value, expected_type)
            except TypeCheckError as exc:
                raise ValueError(
                    f"Error in directive '{attr_name}' of job {self.index_number}:\n{exc}\n\n"
                    f'{yaml.safe_dump(self.serialize())}'
                ) from None

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
                stacklevel=1,
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
                job_subclass: JobBase = cls.__subclasses__[data['kind']]
            except KeyError:
                raise ValueError(
                    f"Error in jobs file: Job directive 'kind: {data['kind']}' does not match any known job kinds:\n"
                    f'{yaml.safe_dump(data)}'
                ) from None
        else:
            # Auto-detect the job subclass based on required directives.
            matched_subclasses: list[JobBase] = [
                subclass
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
                raise ValueError(
                    f"Error in jobs file: Job directives (with values) don't match a job type (check for "
                    f'errors/typos/escaping):\n{yaml.safe_dump(data)}'
                )

        # Remove extra required directives ("Falsy")
        other_subclasses: list[JobBase] = list(cls.__subclasses__.values())[1:]
        other_subclasses.remove(job_subclass)
        for other_subclass in other_subclasses:
            for k in other_subclass.__required__:
                if k not in job_subclass.__required__:
                    data.pop(k, None)

        job = job_subclass.from_dict(data, filenames)

        # Make sure all the types are correct
        job.validate()

        # Format headers and cookies (and turn values into strings to avoid httpx Exception):
        if isinstance(job.headers, dict):
            job.headers = Headers({k: str(v) for k, v in (job.headers or {}).items()}, encoding='utf-8')
        if isinstance(job.cookies, dict):
            job.cookies = {k: str(v) for k, v in job.cookies.items()} if job.cookies is not None else None

        # Add GUID
        job.guid = job.get_guid()

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
            if hasattr(self, k) and getattr(self, k)
        }

    @classmethod
    def from_dict(cls, data: dict, filenames: list[Path]) -> JobBase:
        """Create a JobBase class from a dict, checking that all keys are recognized (i.e. listed in __required__ or
        __optional__).

        :param data: Job data in dict format (e.g. from the YAML jobs file).
        :returns: A JobBase type object.
        """
        for k in data:
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
                        [
                            f"Directive '{k}' is unrecognized in the following {cls.__kind__} job",
                            *jobs_files,
                            '',
                            '---',
                            *yaml.safe_dump(data).splitlines(),
                            '---\n',
                            'Please check for typos or refer to the documentation.',
                        ]
                    )
                )
        return cls(**data)

    def __repr__(self) -> str:
        """Represent the Job object as a string.

        :returns: A string representing the Job.
        """
        return f'<{self.__kind__} {" ".join(f"{k}={v!r}" for k, v in list(self.to_dict().items()))}'

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
                    elif isinstance(value, (dict, Headers)) and isinstance(getattr(self, key), (dict, Headers)):
                        for subkey, subvalue in value.items():
                            if hasattr(self, key) and subkey not in getattr(self, key):
                                getattr(self, key)[subkey] = subvalue
                    # elif isinstance(defaults[key], list) and isinstance(getattr(self, key), list):
                    #     setattr(self, key, list(set(getattr(self, key) + defaults[key])))

    def with_defaults(self, config: _Config) -> JobBase:
        """Obtain a Job object that also contains defaults from the configuration.

        :param config: The configuration as a dict.
        :returns: A JobBase object.
        """
        from webchanges.jobs import BrowserJob, ShellJob, UrlJob

        job_with_defaults = copy.deepcopy(self)

        cfg = config.get('job_defaults')
        if isinstance(cfg, dict):
            # Apply defaults specific to this job kind, then 'all' defaults (which don't override more specific ones)
            for class_type in (UrlJob, BrowserJob, ShellJob):
                if isinstance(self, class_type):
                    job_with_defaults._set_defaults(cfg.get(class_type.__kind__))
                    break
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
                    stacklevel=1,
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
        # TODO: Implement SHA256 hash GUIDs
        """Calculate the GUID as a SHA256 hash of the location (URL or command).

        :returns: the GUID.
        """
        location = self.get_location()
        return hashlib.sha256(location.encode(), usedforsecurity=False).hexdigest()

    @staticmethod
    def make_guid(name: str) -> str:
        """Calculate the GUID from a string (currently a simple SHA1).

        :returns: the GUID.
        """
        return hashlib.sha1(name.encode(), usedforsecurity=False).hexdigest()

    def get_guid(self) -> str:
        """Calculate the GUID, currently a simple SHA1 hash of the location (URL or command).

        :returns: the GUID.
        """
        location = self.get_location()
        return self.make_guid(location)

    def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved and the ETag.
        """
        raise NotImplementedError

    def main_thread_enter(self) -> None:
        """Called from the main thread before running the job. No longer needed (does nothing)."""

    def main_thread_exit(self) -> None:
        """Called from the main thread after running the job. No longer needed (does nothing)."""

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        return tb

    def ignore_error(self, exception: Exception) -> bool:
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
        """Return the correct proxy, depending on whether the URL is http or https."""
        url = self.url.removeprefix('view-source:')
        scheme = urlsplit(url).scheme
        if scheme not in {'http', 'https'}:
            raise ValueError(
                f'Job {self.index_number}: URL should start with https:// or http:// (check for typos): {self.url}'
            )
        proxy = self.proxy
        if proxy is None:
            if os.getenv((scheme + '_proxy').upper()):
                proxy = os.getenv((scheme + '_proxy').upper())
            if proxy:
                logger.debug(
                    f'Job {self.index_number}: Using proxy from environment variable {(scheme + "_proxy").upper()}'
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
        'suppress_error_ended',
        'suppress_errors',
        'suppress_repeated_errors',
        'user_visible_url',
    )

    def get_location(self) -> str:  # ty:ignore[empty-body]
        """Get the 'location' of the job, i.e. the (user_visible) URL or command.

        :returns: The user_visible_url, the URL, or the command of the job.
        """

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

    def retrieve(
        self,
        job_state: JobState,
        headless: bool = True,
    ) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved, the ETag, and the mime_type.
        """
        raise NotImplementedError


CHARSET_RE = re.compile('text/(html|plain); charset=([^;]*)')


class UrlJobBase(Job):
    """The base class for jobs that use the 'url' key.  Includes UrlJob and BrowserJob."""

    __required__: tuple[str, ...] = ('url',)
    __optional__: tuple[str, ...] = (
        'cookies',
        'data',
        'data_as_json',
        'encoding',
        'headers',
        'ignore_cached',
        'ignore_connection_errors',
        'ignore_http_error_codes',
        'ignore_timeout_errors',
        'ignore_too_many_redirects',
        'method',
        'params',
        'proxy',
        'timeout',
    )

    def get_headers(
        self,
        job_state: JobState,
        user_agent: str | None = __user_agent__,
        include_cookies: bool = True,
    ) -> Headers:
        """Get headers and modify them to add cookies and conditional request. If headers don't
        contain `User-Agent`, either the default one or the one provided as `user_agent` is added.

        :param job_state: The job state.
        :param user_agent: The user agent string.
        :include_cookies: Whether to include cookies (from `self.cookies`) as a `Cookie` header.

        :returns: The headers.
        """
        headers = self.headers.copy() if self.headers else Headers(encoding='utf-8')
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
                    f'( {self.get_indexed_location()} ).',
                    RuntimeWarning,
                    stacklevel=1,
                )
            headers['Cookie'] = '; '.join([f'{k}={v}' for k, v in self.cookies.items()])
        if self.no_conditional_request:
            headers.pop('If-Modified-Since', None)
            headers.pop('If-None-Match', None)
        elif self.ignore_cached or job_state.tries > 0:
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

    def _ignore_http_error_code(self, status_code: int) -> bool:
        """Checks if an HTTP error status code should be ignored based on the job's ignore_http_error_codes directive.

        :param status_code: The HTTP status code.
        :returns: True if the error should be ignored, False otherwise.
        """
        if not self.ignore_http_error_codes:
            return False

        if isinstance(self.ignore_http_error_codes, int):
            return status_code == self.ignore_http_error_codes

        if isinstance(self.ignore_http_error_codes, str):
            ignored_codes = {s.strip().lower() for s in self.ignore_http_error_codes.split(',')}
        else:  # list
            ignored_codes = {str(s).strip().lower() for s in self.ignore_http_error_codes}

        return str(status_code) in ignored_codes or f'{status_code // 100}xx' in ignored_codes
