"""Base job classes."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

__lazy_modules__ = ['asyncio', 'copy', 'email.utils', 'hashlib', 'textwrap', 'urllib.parse', 'warnings']

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
from webchanges._httpx import Headers, httpx2
from webchanges.filters._base import FiltersList  # noqa: TC001 (required for type check)
from webchanges.jobs._exceptions import TransientHTTPError
from webchanges.util import TrackSubClasses

if httpx2 is None:  # pragma: no cover
    print("Required package 'httpx2' (or 'httpx') not found; will attempt to run using 'requests'")

try:
    from typeguard import TypeCheckError, check_type  # ty:ignore[unresolved-import]
except ImportError:
    from webchanges._vendored.typeguard import TypeCheckError, check_type

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from webchanges.handler import JobState
    from webchanges.storage import _Config

logger = logging.getLogger(__name__)

# The value standing for a header set to null, i.e. removed (a Headers object cannot hold None). It is kept while the
# job_defaults are merged, so that it stops the less specific defaults from supplying that header, and is dropped by
# get_headers() before the request is sent.
REMOVED_HEADER = '\x00removed'


def headers_from_dict(headers: dict[str, Any]) -> Headers:
    """Convert headers read from YAML into a Headers object, with values as strings and null ones marked as removed.

    :param headers: The headers, e.g. from the 'headers' directive of a job or job_defaults.
    :returns: The Headers object.
    """
    return Headers({k: REMOVED_HEADER if v is None else str(v) for k, v in headers.items()}, encoding='utf-8')


def headers_to_dict(headers: Headers) -> dict[str, str | None]:
    """Convert a Headers object into a dict, restoring removed headers to None (the inverse of headers_from_dict).

    :param headers: The Headers object.
    :returns: The headers as a dict.
    """
    return {k: None if v == REMOVED_HEADER else v for k, v in headers.items()}


def cookies_from_dict(cookies: dict[str, Any]) -> dict[str, str | None]:
    """Convert cookies read from YAML into strings, keeping null ones (removed) as None.

    As with headers, a None value is kept while the job_defaults are merged, so that it stops the less specific
    defaults from supplying that cookie, and is dropped by get_cookies() before the request is sent.

    :param cookies: The cookies, e.g. from the 'cookies' directive of a job or job_defaults.
    :returns: The cookies.
    """
    return {k: None if v is None else str(v) for k, v in cookies.items()}


# Custom YAML representer function for Headers
def represent_headers(dumper: yaml.SafeDumper, data: Headers) -> yaml.MappingNode:
    return dumper.represent_dict(headers_to_dict(data))


# Add the custom representer to the SafeDumper
yaml.SafeDumper.add_representer(Headers, represent_headers)

# reduce logging from httpx2's sub-modules (httpcore2; httpcore if the httpx fallback is used)
if httpx2 is not None and logger.getEffectiveLevel() == logging.DEBUG:
    logging.getLogger('hpack').setLevel(logging.INFO)
    logging.getLogger('httpcore2').setLevel(logging.INFO)
    logging.getLogger('httpcore').setLevel(logging.INFO)

# Deprecated job directives and the directive replacing each one. Insertion order matters: 'https_proxy' is
# processed before 'http_proxy' so that, when both are present, 'https_proxy' wins (see below).
DEPRECATED_DIRECTIVES: dict[str, str] = {
    'filter': 'filters',
    'diff_filter': 'diff_filters',
    'https_proxy': 'proxy',
    'http_proxy': 'proxy',
    'json': 'data_as_json',
}


def replace_deprecated_directives(directives: dict[str, Any]) -> None:
    """Renames any deprecated job directive to the directive replacing it, modifying the dict in place.

    :param directives: The job's directives (e.g. as read from the YAML jobs file).
    """
    if 'https_proxy' in directives:
        # Both legacy directives map onto 'proxy', which is scheme-agnostic; 'https_proxy' takes precedence.
        directives.pop('http_proxy', None)

    for old, new in DEPRECATED_DIRECTIVES.items():
        if old in directives:
            logger.warning(
                "Job %s: Replacing deprecated directive '%s' with '%s'", directives.get('index_number'), old, new
            )
            directives[new] = directives.pop(old)


class JobBase(metaclass=TrackSubClasses):
    """The base class for Jobs."""

    __subclasses__: dict[str, JobBase] = {}  # ty:ignore[invalid-assignment]
    __anonymous_subclasses__: list[JobBase] = []  # ty:ignore[invalid-assignment]

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
    _delay: float | None = None  # internal effective delay; set per-run by worker from the same_site_delay directive
    additions_only: bool | float | str | None = None
    block_elements: list[str] | None = None  # BrowserJob
    compared_versions: int | None = None
    contextlines: int | None = None
    connect_over_cdp: str | bool | None = None  # BrowserJob
    cookies: dict[str, str | None] | None = None  # UrlJobBase; a None value is a removed cookie, see get_cookies()
    data: str | list | dict | None = None  # UrlJobBase
    data_as_json: bool | None = None  # UrlJobBase
    deletions_only: bool | None = None
    differ: dict[str, Any] | None = None  # added in 3.21
    diff_filters: str | list[str | dict[str, Any]] | None = None
    diff_tool: str | None = None  # deprecated in 3.21
    empty_as_error: bool | Literal['ignore'] | None = None
    enabled: bool | None = None
    encoding: str | None = None  # UrlJobBase
    evaluate: str | None = None  # BrowserJob
    filters: FiltersList | list[FiltersList | dict[str, Any]] | None = None
    fingerprints: dict[str, str | dict[str, Any]] | None = None  # UrlJob (curl_cffi backend only)
    guid: str = ''
    headers = Headers(encoding='utf-8')  # UrlJobBase; shared by all jobs not setting it: never mutate it in place
    hook_data: Any = None  # hooks.py
    http_client: Literal['httpx2', 'requests', 'curl_cffi', 'httpx'] | None = None  # UrlJob ('httpx' = 'httpx2')
    http_version: Literal['v1', 'v2', 'v2tls', 'v2_prior_knowledge', 'v3', 'v3only'] | None = None  # UrlJob
    http_credentials: str | None = None  # BrowserJob
    ignore_cached: bool | None = None  # UrlJobBase
    ignore_connection_errors: bool | None = None  # UrlJobBase
    ignore_default_args: bool | str | list[str] | None = None  # BrowserJob
    ignore_dh_key_too_small: bool | None = None  # UrlJob
    ignore_http_error_codes: list[int | str] | int | str | None = None  # UrlJobBase
    ignore_https_errors: bool | None = None  # BrowserJob
    ignore_incomplete_reads: bool | None = None  # UrlJob
    ignore_timeout_errors: bool | None = None  # UrlJobBase
    ignore_too_many_redirects: bool | None = None  # UrlJobBase
    impersonate: str | None = None  # UrlJob (curl_cffi backend only)
    init_script: str | None = None  # BrowserJob
    initialization_js: str | None = None  # BrowserJob
    initialization_url: str | None = None  # UrlJob, BrowserJob
    is_markdown: bool | None = None
    is_rst: bool | None = None
    kind: str | None = None  # hooks.py
    markdown_extras: dict[str, Any] | None = None
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
    same_site_delay: float | None = None  # UrlJobBase
    ssl_no_verify: bool | None = None  # UrlJob
    stderr: str | None = None  # ShellJob (from urlwatch)
    stealth: bool | None = None  # BrowserJob
    suppress_error_ended: bool | None = None
    suppress_errors: bool | None = None
    suppress_repeated_errors: bool | None = None
    switches: list[str] | None = None  # BrowserJob
    tags: str | list[str] | None = None
    timeout: float | None = None  # UrlJobBase
    treat_new_as_changed: bool | None = None
    tz: str | None = None  # added by with_defaults, taken from reporter configuration
    user_data_dir: str | None = None  # BrowserJob
    user_visible_url: str | None = None
    wait_for: int | str | None = None  # BrowserJob (DEPRECATED)
    wait_for_function: str | dict[str, Any] | None = None  # BrowserJob
    wait_for_navigation: str | tuple[str, ...] | None = None  # BrowserJob (DEPRECATED)
    wait_for_selector: str | dict[str, Any] | list[str | dict[str, Any]] | None = None  # BrowserJob
    wait_for_timeout: float | None = None  # BrowserJob
    wait_for_url: str | dict[str, Any] | None = None  # BrowserJob
    wait_until: Literal['commit', 'domcontentloaded', 'load', 'networkidle'] | None = None  # BrowserJob

    def __init__(self, **kwargs: Any) -> None:
        replace_deprecated_directives(kwargs)

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
        """Get the job number plus its 'location', i.e. the (user_visible) URL or command.

        Typically used in error displays.

        :returns: The job number followed by a colon and the 'location' of the job, i.e. its user_visible_url, URL,
           or command.
        """
        raise NotImplementedError

    def set_base_location(self, location: str) -> None:
        """Sets the job's location (command or url) to location.  Used for changing location (uuid)."""
        raise NotImplementedError

    def pretty_name(self) -> str:
        """Get the job's 'pretty name': its 'name' if defined, else its user_visible_url, URL or command.

        :returns: The 'pretty name' the job.
        """
        raise NotImplementedError

    def serialize(self) -> dict:
        """Serialize the Job object, excluding its index_number (e.g. for saving).

        Unlike :py:meth:`to_dict`, it keeps the directives set to false or 0 (e.g. ``enabled: false`` or
        ``contextlines: 0``), as these differ from leaving the directive out; empty strings and collections (e.g. the
        empty headers of every URL job) are left out.

        :returns: A dict with the Job object serialized.
        """
        d = {
            k: headers_to_dict(v) if isinstance(v, Headers) else v
            for keys in (self.__required__, self.__optional__)
            for k in keys
            if (v := getattr(self, k, None)) is not None and (isinstance(v, (bool, int, float)) or v)
        }
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
    def unserialize(cls, data: dict, filenames: list[Path] | None = None) -> JobBase:
        """Unserialize a dict with job data (e.g. from the YAML jobs file) into a JobBase type object.

        :param data: The dict with job data (e.g. from the YAML jobs file); it is not modified.
        :returns: A JobBase type object.
        """
        if filenames is None:
            filenames = []

        # Work on a shallow copy, as the backwards-compatibility migrations rewrite and remove keys and the caller's
        # dict (e.g. one owned by hooks.py code) must not be modified.
        data = dict(data)
        cls._migrate_legacy_directives(data)

        # 'url' and 'command' each identify a different job kind and are mutually exclusive (as the jobs.schema.json
        # JSON Schema declares); a job with both used to be silently run as a 'command' one, ignoring the URL.
        if data.get('url') and data.get('command'):
            raise ValueError(
                f"Error in jobs file: Job directives 'url' and 'command' are mutually exclusive (a job monitors "
                f'either a URL or the output of a command):\n{yaml.safe_dump(data)}'
            )

        job_subclass = cls._job_subclass(data)

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

        # Format headers and cookies (and turn values into strings to avoid httpx2 Exception):
        if isinstance(job.headers, dict):
            job.headers = headers_from_dict(job.headers)
        if isinstance(job.cookies, dict):
            job.cookies = cookies_from_dict(job.cookies)

        # Add GUID
        job.guid = job.get_guid()

        return job

    @staticmethod
    def _migrate_legacy_directives(data: dict) -> None:
        """Rewrite deprecated directives (webchanges' own and urlwatch's) into their current form.

        :param data: The dict with job data, modified in place.
        :raises ValueError: If 'differ' is neither a string nor a dict.
        """
        if data.get('kind') == 'shell':
            data['kind'] = 'command'

        # Backwards compatibility with 'navigate' directive (deprecated)
        from_navigate = bool(data.get('navigate'))
        if data.get('navigate') and not data.get('use_browser'):
            warnings.warn(
                f"Error in jobs file: Job directive 'navigate' is deprecated: replace with 'url' and add 'use_browser: "
                f"true':\n{yaml.safe_dump(data)}",
                DeprecationWarning,
                stacklevel=1,
            )
            data['url'] = data.get('url', data['navigate'])
            data['use_browser'] = True
        if data.get('use_browser') and data.get('url'):
            # Translated: a browser job with 'navigate' set fails, and saving the job would write both directives
            data.pop('navigate', None)

        # Backwards compatibility with urlwatch's browser job directives 'useragent' and 'browser' (deprecated)
        if 'useragent' in data:
            logger.warning(
                "Job directive 'useragent' is deprecated: replace it with a 'User-Agent' header in 'headers' (job %s)",
                data.get('url'),
            )
            useragent = data.pop('useragent')
            headers = dict(data.get('headers') or {})
            if useragent and not any(key.lower() == 'user-agent' for key in headers):
                headers['User-Agent'] = useragent
            data['headers'] = headers
        if 'browser' in data:
            logger.warning(
                "Job directive 'browser' is deprecated: replace it with 'use_browser: <browser>' (job %s)",
                data.get('url'),
            )
            browser = data.pop('browser')
            # Only for browser jobs (urlwatch's 'navigate' ones); its default 'chromium' is webchanges' default browser
            if browser and browser != 'chromium' and data.get('use_browser') is True:
                data['use_browser'] = browser
        # urlwatch's 'wait_for' waits for an element matching a selector (webchanges' own former 'wait_for' is rejected)
        if from_navigate and isinstance(data.get('wait_for'), str) and not data.get('wait_for_selector'):
            logger.warning(
                "Job directive 'wait_for' is deprecated: replace it with 'wait_for_selector' (job %s)", data.get('url')
            )
            data['wait_for_selector'] = data.pop('wait_for')

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

    @classmethod
    def _job_subclass(cls, data: dict) -> JobBase:
        """The job class: the one named by 'kind', else the one whose required directives the data best matches.

        :param data: The dict with job data.
        :returns: The job class.
        :raises ValueError: If 'kind' is unknown, or no job class matches.
        """
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
                job_subclass = max(number_matched.items(), key=lambda x: x[1])[0]
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
        return job_subclass

    def to_dict(self) -> dict:
        """Return the job's directives with a truthy value, required and optional, as a serializable dict.

        Headers objects (which are not JSON serializable) are converted to dicts.

        :returns: A dict with all job directives as keys, ignoring those that are extras.
        """
        # Deliberately drops every falsy value (False, 0, '', empty collections), unlike serialize(), which keeps False
        # and 0 because saving must not lose e.g. 'enabled: false'. Do not make the two consistent: RegexMatchFilter
        # (filters/_base.py), also subclassed in users' hooks.py, runs regexes over these values and would raise
        # TypeError on a False or 0; the WEBCHANGES_*_JSON environment variables of reporters and filters also use it.
        return {
            k: headers_to_dict(getattr(self, k)) if isinstance(getattr(self, k), Headers) else getattr(self, k)
            for keys in {self.__required__, self.__optional__}
            for k in keys
            if hasattr(self, k) and getattr(self, k)
        }

    @classmethod
    def from_dict(cls, data: dict, filenames: list[Path]) -> JobBase:
        """Create a JobBase from a dict, checking that all keys are listed in __required__ or __optional__.

        :param data: Job data in dict format (e.g. from the YAML jobs file); it is modified in place.
        :returns: A JobBase type object.
        """
        replace_deprecated_directives(data)
        recognized = set(cls.__required__).union(cls.__optional__)
        for k in data:
            if k not in recognized:
                if len(filenames) > 1:
                    jobs_files = ['in the concatenation of the jobs files:'] + [f'• {file},' for file in filenames]
                elif len(filenames) == 1:
                    jobs_files = [f'in jobs file {filenames[0]}:']
                else:
                    jobs_files = []

                raise ValueError(
                    '\n   '.join(
                        [
                            f"Directive '{k}' is unrecognized in the following job of kind '{cls.__kind__}'",
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
        """Merge default attributes (e.g. from configuration) into those of the Job object, without overwriting any.

        A directive the job already has keeps its value, except that a dict-valued one (e.g. ``headers``, ``cookies``)
        is merged key by key, one level deep: the default's keys missing from the job's are added (case-insensitively
        for ``headers``, as both are ``Headers`` objects), the others are left untouched. A list (e.g. ``filters``) is
        never merged. Called repeatedly, the first call's defaults win over the later ones'.

        :param defaults: The default Job parameters.
        """
        if isinstance(defaults, dict):
            for key, value in defaults.items():
                if key in self.__optional__:
                    attribute = getattr(self, key, None)
                    if attribute is None:  # for speed
                        setattr(self, key, value)
                    elif isinstance(value, (dict, Headers)) and isinstance(attribute, (dict, Headers)):
                        # Merge into a copy and assign it, never merge in place: a directive that this job does not
                        # set itself reads the class attribute (e.g. the shared, mutable JobBase.headers), and
                        # mutating that would leak these defaults into every other job of the run.
                        merged = copy.deepcopy(attribute)
                        for subkey, subvalue in value.items():
                            if subkey not in merged:
                                merged[subkey] = subvalue
                        setattr(self, key, merged)
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
            # Apply defaults specific to this job kind, then 'all_jobs' ones. As _set_defaults never overwrites, the
            # precedence is: the job's directive > the kind's default > the all_jobs default; for headers (and any other
            # dict-valued directive) this holds header by header, e.g. a job's User-Agent replaces only the default
            # User-Agent, and all the other default headers are still sent.
            for class_type in (UrlJob, BrowserJob, ShellJob):
                if isinstance(self, class_type):
                    job_with_defaults._set_defaults(cfg.get(f'{class_type.__kind__}_jobs'))
                    break
            job_with_defaults._set_defaults(cfg.get('all_jobs'))

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
        """Runs job to retrieve the data, and returns the data, ETag, and media type (fka MIME type).

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: A tuple of the data retrieved, the ETag, and the media type.
        """
        raise NotImplementedError

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        if isinstance(exception, TransientHTTPError):
            # Instead of a full traceback, just show the error: it describes a condition of the monitored resource
            # (e.g. an HTTP 503 response, or no data received) and not a failure of webchanges, so a stack trace
            # would only be alarming noise.
            return str(exception).strip()
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

    def tags_set(self) -> set[str]:
        """Returns the job's tags as a set (the 'tags' directive accepts either a single tag or a list of them).

        :returns: The set of the job's tags; empty if the job has no 'tags' directive.
        """
        if not self.tags:
            return set()
        if isinstance(self.tags, str):
            return {self.tags}
        return set(self.tags)

    def matching_tags(self, tags: Iterable[str]) -> set[str]:
        """Returns the job's tags that are also in ``tags``.

        Used to select the jobs to run (``--tags``) and those a reporter reports on (a reporter's 'tags' configuration
        directive).

        :param tags: The tags to match the job's tags against.
        :returns: The intersection of the job's tags and ``tags``; empty (i.e. falsy) if the job matches none of them.
        """
        return self.tags_set().intersection(tags)

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
                    'Job %s: Using proxy from environment variable %s', self.index_number, (scheme + '_proxy').upper()
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
        'empty_as_error',
        'enabled',
        'filters',
        'hook_data',  # hooks.py
        'index_number',
        'is_markdown',
        'is_rst',
        'kind',  # hooks.py
        'markdown_extras',
        'markdown_padded_tables',
        'max_tries',
        'monospace',
        'name',
        'no_conditional_request',
        'note',
        'suppress_error_ended',
        'suppress_errors',
        'suppress_repeated_errors',
        'tags',
        'treat_new_as_changed',
        'user_visible_url',
    )

    def get_location(self) -> str:  # ty:ignore[empty-body]
        """Get the 'location' of the job, i.e. the (user_visible) URL or command.

        :returns: The user_visible_url, the URL, or the command of the job.
        """

    def get_indexed_location(self) -> str:
        """Get the job number plus its 'location', i.e. the (user_visible) URL or command.

        Typically used in error displays.

        :returns: The job number followed by a colon and the 'location' of the job, i.e. its user_visible_url, URL,
           or command.
        """
        return f'Job {self.index_number}: {self.get_location()}'

    def pretty_name(self) -> str:
        """Get the job's 'pretty name': its 'name' if defined, else its user_visible_url, URL or command.

        :returns: The 'pretty name' the job.
        """
        return self.name or self.get_location()

    def retrieve(
        self,
        job_state: JobState,
        headless: bool = True,
    ) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns the data, ETag, and media type (fka MIME type).

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: A tuple of the data retrieved, the ETag, and the media type.
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
        'same_site_delay',
        'timeout',
    )

    def get_cookies(self) -> dict[str, str] | None:
        """Get the cookies to send, i.e. those of the 'cookies' directive (merged with job_defaults) not set to null.

        :returns: The cookies, or None if there are none.
        """
        if not self.cookies:
            return None
        if not isinstance(self.cookies, dict):
            raise TypeError(
                f"Job {self.index_number}: Directive 'cookies' needs to be a dictionary; "
                f"found a '{type(self.cookies).__name__}' ( {self.get_indexed_location()} ).'"
            )
        cookies = {k: v for k, v in self.cookies.items() if v is not None}
        if len(cookies) < len(self.cookies):
            removed = ', '.join(k for k, v in self.cookies.items() if v is None)
            logger.debug('Job %s: Not sending cookie(s) set to null: %s', self.index_number, removed)
        return cookies or None

    def get_headers(
        self,
        job_state: JobState,
        user_agent: str | None = __user_agent__,
        include_cookies: bool = True,
    ) -> Headers:
        """Get the headers, adding cookies and the conditional request ones.

        Headers set to null (removed) are dropped first; then, if there is no `User-Agent`, either the default one or
        `user_agent` is added.

        :param job_state: The job state.
        :param user_agent: The user agent string.
        :include_cookies: Whether to include cookies (from `get_cookies()`) as a `Cookie` header.

        :returns: The headers.
        """
        headers = self.headers.copy() if self.headers else Headers(encoding='utf-8')
        if removed := [k for k, v in headers.items() if v == REMOVED_HEADER]:
            logger.debug('Job %s: Not sending header(s) set to null: %s', self.index_number, ', '.join(removed))
            for name in removed:
                del headers[name]
        if 'User-Agent' not in headers and user_agent:
            headers['User-Agent'] = user_agent
        if include_cookies and (cookies := self.get_cookies()):
            if 'Cookie' in headers:
                warnings.warn(
                    f"Job {self.index_number}: Found both a header 'Cookie' and a directive 'cookies'; "
                    f"please specify only one of them (using content of the cookies 'directive') "
                    f'( {self.get_indexed_location()} ).',
                    RuntimeWarning,
                    stacklevel=1,
                )
            headers['Cookie'] = '; '.join([f'{k}={v}' for k, v in cookies.items()])
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
