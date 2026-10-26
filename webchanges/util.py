"""A few utilities used elsewhere."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.
from __future__ import annotations

__lazy_modules__ = [
    'getpass',
    'importlib.machinery',
    'importlib.util',
    'json',
    'math',
    'platformdirs',
    're',
    'shlex',
    'stat',
    'subprocess',
    'textwrap',
    'time',
]

import getpass
import importlib.machinery
import importlib.util
import json
import logging
import os
import re
import shlex
import stat
import subprocess
import sys
import textwrap
import time
from math import floor, log10
from os import PathLike
from typing import TYPE_CHECKING, Any, Callable, Iterable, Match

import platformdirs

from webchanges import __project_name__, __version__

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    from webchanges.handler import JobState

logger = logging.getLogger(__name__)


def _parse_version(value: str):  # noqa: ANN202 returns packaging.version.Version (lazy import)
    """Lazily import packaging's ``parse`` (with vendored fallback) and return the parsed Version."""
    try:
        from packaging.version import parse
    except ImportError:  # pragma: no cover
        from webchanges._vendored.packaging_version import parse
    return parse(value)


class TrackSubClasses(type):
    """A metaclass that stores subclass name-to-class mappings in the base class."""

    # __subclasses__ gets redefined from default "Callable[[_TT], list[_TT]]
    __subclasses__: dict[str, TrackSubClasses]  # ty:ignore[invalid-attribute-override]
    __anonymous_subclasses__: list[TrackSubClasses]
    __required__: tuple[str, ...] = ()
    __optional__: tuple[str, ...] = ()
    __supported_directives__: dict[str, str] = {}
    __supported_subfilters__: dict[str, str] = {}

    __kind__: str

    job_states: list[JobState]

    def sorted_by_kind(cls: TrackSubClasses) -> list[TrackSubClasses]:
        """Generates a list of all members of a class sorted by the value of their __kind__ attribute.

        Useful for documentation.

        :param cls: The class.
        :return: The sorted list of class members.
        """
        return [item for _, item in sorted((it.__kind__, it) for it in cls.__subclasses__.values() if it.__kind__)]

    def __init__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """_summary_. # TODO.

        :param name: _description_.  # TODO.
        :param bases: _description_.  # TODO.
        :param namespace: _description_.  # TODO.
        """
        for base in bases:
            if base is object:
                continue

            for attr in ('__required__', '__optional__'):
                if not hasattr(base, attr):
                    continue

                inherited = getattr(base, attr, ())
                new_value = tuple(namespace.get(attr, ())) + tuple(inherited)
                namespace[attr] = new_value
                setattr(cls, attr, new_value)

        for base in bases:
            if base is object:
                continue

            if hasattr(cls, '__kind__'):
                subclasses = getattr(base, '__subclasses__', None)
                if subclasses is not None:
                    logger.debug(
                        f'Registering Class {cls.__module__}.{cls.__qualname__}'
                        + (f' as {cls.__kind__}' if cls.__kind__ else '')
                    )
                    subclasses[cls.__kind__] = cls
                    break
            else:
                anonymous_subclasses = getattr(base, '__anonymous_subclasses__', None)
                if anonymous_subclasses is not None:
                    logger.debug(f'Registering Class {cls.__module__}.{cls.__qualname__}')
                    anonymous_subclasses.append(cls)
                    break

        super().__init__(name, bases, namespace, **kwargs)


def edit_file(filename: str | bytes | PathLike) -> None:
    """Opens the editor to edit a file.

    :param filename: The filename.
    """
    editor = os.environ.get('EDITOR')
    if not editor:
        editor = os.environ.get('VISUAL')
    if not editor:
        if sys.platform == 'win32':
            editor = 'notepad.exe'
        else:
            print('Please set the path to the editor in the environment variable $EDITOR, e.g. "export EDITOR=nano"')
            raise SystemExit(1)

    subprocess.run(  # noqa: S603 subprocess call - check for execution of untrusted input.
        [*shlex.split(editor), str(filename)], check=True
    )


def import_module_from_source(module_name: str, source_path: str | bytes | PathLike) -> ModuleType:
    """Loads a module and executes it in its own namespace.

    :param module_name: The name of the module to import.
    :param source_path: The path where the module is located.
    :return: A ModuleType object.
    """
    source_path = str(source_path)
    loader = importlib.machinery.SourceFileLoader(module_name, source_path)
    spec = importlib.util.spec_from_file_location(module_name, source_path, loader=loader)
    module = importlib.util.module_from_spec(spec)  # ty:ignore[invalid-argument-type]
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


def chunk_string(text: str, length: int, numbering: bool = False) -> list[str]:
    """Chunks a string.

    :param text: The text to be chunked.
    :param length: The length of the chunked text.
    :param numbering: Whether to number each chunk on the left if more than one chunk is generated.

    :returns: a list of chunked strings
    """
    if numbering and len(text) > length:
        try:
            text_length = length - 4 - 2
            digits_try = 1 if text_length <= 0 else floor(log10(len(text) / text_length))  # initialization floor
            digits_guess = digits_try + 1
            while digits_guess > digits_try:
                digits_try += 1
                text_length = length - 4 - 2 * digits_try
                if text_length <= 0:
                    raise ValueError('Not enough space to chunkify string with line numbering (1)')
                lines_guess = len(text) / text_length
                digits_guess = floor(log10(lines_guess)) + 1

            chunks = textwrap.wrap(text, text_length, replace_whitespace=False)
            actual_digits = floor(log10(len(chunks))) + 1
            while actual_digits > digits_try:
                digits_try += 1
                text_length = length - 4 - 2 * digits_try
                if text_length <= 0:
                    raise ValueError('Not enough space to chunkify string with line numbering (2)')
                chunks = textwrap.wrap(text, text_length, replace_whitespace=False)
                actual_digits = floor(log10(len(chunks))) + 1

            length = len(chunks)
            return [f'{line} ({i + 1:{digits_try}d}/{length})' for i, line in enumerate(chunks)]

        except ValueError as e:
            logger.error(f'{e}')

    return textwrap.wrap(text, length, replace_whitespace=False)


def linkify(
    text: str,
    shorten: bool = False,
    extra_params: str | Callable[[str], str] = '',
    require_protocol: bool = False,
    permitted_protocols: tuple[str, ...] = (
        'http',
        'https',
        'mailto',
    ),
) -> str:
    """Converts plain text into HTML with links.

    For example linkify("Hello http://tornadoweb.org!") would return 'Hello
    <a href="http://tornadoweb.org">http://tornadoweb.org</a>!'.

    We are using a regex from tornado library https://github.com/tornadoweb/tornado/blob/master/tornado/escape.py.
    This regex should avoid character entities other than &amp; so that we won't pick up &quot;, etc., but it is
    vulnerable to Regular expression Denial of Service (ReDoS), which would divert computational resources to an
    expensive regex match. The risk in this application is limited.

    In the future, consider using linkify from the bleach project instead (requires importing another package).

    :parameter text: The text to linkify.
    :parameter shorten: Long urls will be shortened for display.
    :parameter extra_params: Extra text to include in the link tag, or a callable taking the link as an argument and
        returning the extra text, e.g. linkify(text, extra_params='rel="nofollow" class="external"').
    :parameter require_protocol: Only linkify urls which include a protocol; if this is False, urls such as
        www.facebook.com will also be linkified.
    :parameter permitted_protocols: Protocols which should be linkified, e.g. linkify(text,
        permitted_protocols=('http', 'ftp', 'mailto')); it is very unsafe to include protocols such as javascript.
    """
    # original _url_re was the following:
    #     r'\b('
    #     r'(?:([\w-]+):(/{1,3})|www[.])'
    #     r'(?:('
    #     r'?:(?:[^\s&()]|&amp;|&quot;)*(?:[^!"#$%&'
    #     r"'()*+,.:;<=>?@\[\]^`{|}~\s])"
    #     r")"
    #     r'|(?:\((?:[^\s&()]|&amp;|&quot;)*\))'
    #     r')+'
    #     r')'

    _url_re = re.compile(  # modified to catch all URL parameters
        r'\b('
        r'(?:([\w-]+):(/{1,3})|www[.])'
        r'(?:('
        r'?:(?:[^\s()])*(?:[^!"#$%&'
        r"'()*+,.:;<=>?@\[\]^`{|}~\s])"
        r')'
        r'|(?:\((?:[^\s()])*\))'
        r')+'
        r')'
    )

    if extra_params and not callable(extra_params):
        extra_params = f' {extra_params.strip()}'

    def make_link(m: Match) -> str:
        """Replacement function for re.sub using re.match as input to convert plain text into HTML with links."""
        url: str = m.group(1)
        proto: str = m.group(2)
        if require_protocol and not proto:
            return url  # not protocol, no linkify

        if proto and proto not in permitted_protocols:
            return url  # bad protocol, no linkify

        href: str = m.group(1)
        if not proto:
            proto = 'https'
            href = f'https://{href}'  # no proto specified, use https

        params = extra_params if isinstance(extra_params, str) else f' {extra_params(href).strip()}'

        # clip long urls. max_len is just an approximation
        max_len = 30
        if shorten and len(url) > max_len:
            before_clip = url
            proto_len = len(proto) + 1 + len(m.group(3) or '') if proto else 0

            parts = url[proto_len:].split('/')
            if len(parts) > 1:
                # Grab the whole host part plus the first bit of the path
                # The path is usually not that interesting once shortened
                # (no more slug, etc), so it really just provides a little
                # extra indication of shortening.
                url = url[:proto_len] + parts[0] + '/' + parts[1][:8].split('?')[0].split('.')[0]

            if len(url) > max_len * 1.5:  # still too long
                url = url[:max_len]

            if url != before_clip:
                amp = url.rfind('&')
                # avoid splitting html char entities
                if amp > max_len - 5:
                    url = url[:amp]
                url += '...'

                if len(url) >= len(before_clip):
                    url = before_clip
                else:
                    # full url is visible on mouse-over (for those who don't
                    # have a status bar, such as Safari by default)
                    params += f' title={href}'

        return f'<a href="{href}"{params}>{url}</a>'

    # text = html.escape(text)
    return _url_re.sub(make_link, text)


_PYPI_CHECK_TTL_SECONDS = 86_400


def _pypi_cache_path() -> Path:
    """Return the on-disk cache path for the PyPi version-check result."""
    return platformdirs.user_data_path(__project_name__, __project_name__.capitalize()) / 'pypi_version_cache.json'


def _read_pypi_cache(path: Path) -> tuple[float, str] | None:
    """Read the cached PyPi version. Returns (checked_at, latest) or None if missing/corrupt."""
    try:
        data = json.loads(path.read_text())
        return float(data['checked_at']), str(data['latest'])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_pypi_cache(path: Path, latest: str) -> None:
    """Atomically write the PyPi version cache. Failures are swallowed (cache is best-effort)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps({'checked_at': time.time(), 'latest': latest}))
        tmp.replace(path)
    except OSError as e:
        logger.info(f'Could not write PyPi version cache: {e}')


def _fetch_latest_from_pypi(timeout: float | None) -> str | None:
    """Query PyPi's Simple JSON API for the latest non-prerelease version.

    Uses the lightweight ``application/vnd.pypi.simple.v1+json`` endpoint via stdlib ``urllib.request`` to avoid
    pulling in ``httpx`` (and its transitive ``rich``/``pygments`` deps) on every program startup. Pre-releases are
    filtered out unless they are the only releases available (mirroring PyPi's own ``info.version`` policy).
    Yanked-version filtering is intentionally skipped: parsing ``files[*].yanked`` would add significant code for a
    vanishingly rare case.

    :returns: The highest released version string, or ``None`` on any failure.
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f'https://pypi.org/simple/{__project_name__}/',
        headers={'Accept': 'application/vnd.pypi.simple.v1+json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 trusted host
            body = r.read()
            logger.info(f'Downloaded {len(body):,} bytes from PyPi querying for latest release.')
    except urllib.error.HTTPError as e:
        logger.info(f'HTTP error when querying PyPi for latest release: {e}')
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.info(f'Exception when querying PyPi for latest release: {e}')
        return None
    try:
        versions: list[str] = json.loads(body)['versions']
    except (ValueError, KeyError, TypeError) as e:
        logger.info(f'Unexpected PyPi response when querying for latest release: {e}')
        return None
    if not versions:
        return None
    parsed = [(_parse_version(v), v) for v in versions]
    stable = [(p, v) for p, v in parsed if not p.is_prerelease]
    candidates = stable or parsed
    return max(candidates, key=lambda pv: pv[0])[1]


def get_new_version_number(
    timeout: float | None = None, cache_path: Path | None = None, force_refresh: bool = False
) -> str | bool:
    """Check PyPi for newer version of project, with a 24h on-disk cache.

    The result is cached at ``cache_path`` (default: a platform-appropriate user data directory) for
    ``_PYPI_CHECK_TTL_SECONDS`` seconds, so repeated invocations within that window do not hit the network.
    If PyPi is unreachable but a (possibly expired) cache exists, the cached value is used as a fallback so
    the upgrade nudge survives outages.

    :parameter timeout: Timeout in seconds for the PyPi request.
    :parameter cache_path: Optional override for the cache file location (used by tests).
    :parameter force_refresh: If True, bypass the fresh-cache shortcut and always query PyPi (the cache is
      still updated on success, and a stale cache is still used as a fallback when PyPi is unreachable).
    :returns: The new version number if a newer version of project is found on PyPi, empty string if running
      the latest version, ``False`` if no version information is available (no cache and PyPi unreachable),
      and ``True`` if running a newer-than-released version.
    """
    path = cache_path if cache_path is not None else _pypi_cache_path()
    cached = _read_pypi_cache(path)

    if not force_refresh and cached is not None and time.time() - cached[0] < _PYPI_CHECK_TTL_SECONDS:
        latest = cached[1]
    else:
        fetched = _fetch_latest_from_pypi(timeout)
        if fetched is not None:
            _write_pypi_cache(path, fetched)
            logger.info(f'Updated {path} cache with release {fetched}.')
            latest = fetched
        elif cached is not None:
            latest = cached[1]
        else:
            return False

    if _parse_version(latest) == _parse_version(__version__):
        return ''
    if _parse_version(latest) > _parse_version(__version__):
        return latest
    return True


def dur_text(duration: float) -> str:
    """Returns a formatted string optimized to the number of seconds for use in footers.

    :parameter duration: The duration in seconds.
    :returns: The formatted string.
    """
    if duration < 60:
        return f'{float(f"{duration:.2g}"):g} seconds'
    m, s = divmod(duration, 60)
    return f'{m:.0f}:{s:02.0f}'


def file_ownership_checks(filename: Path) -> list[str]:
    """Check security of file and its directory.

    Ensures that they belong to the current UID or root and only the owner can write to them. Return list of errors if
    any. Linux only.

    :returns: List of errors encountered (if any).
    """
    if sys.platform == 'win32':
        return []

    file_ownership_errors = []
    current_uid = os.getuid()

    dirname = filename.parent
    dir_st = dirname.stat()
    if (dir_st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)) != 0:
        file_ownership_errors.append(f'{dirname} is group/world-writable')
    if dir_st.st_uid not in {current_uid, 0}:
        file_ownership_errors.append(f'{dirname} not owned by {getpass.getuser()} or root')

    file_st = filename.stat()
    if (file_st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)) != 0:
        file_ownership_errors.append(f'{filename} is group/world-writable')
    if file_st.st_uid not in {current_uid, 0}:
        file_ownership_errors.append(f'{filename} not owned by {getpass.getuser()} or root')

    return file_ownership_errors


# The markdown2 extras always used by mark_to_html(); a job's markdown_extras directive adds to or overrides them.
MARKDOWN2_DEFAULT_EXTRAS: dict[str, Any] = {
    'strike': None,  # text marked by double tildes is ~~strikethrough~~
    'target-blank-links': None,  # <a> tags have rel="noopener" for added security
    'middle-word-em': False,  # no emphasis within words, e.g. snake_case_names stay as they are
}


def mark_to_html(
    text: str,
    markdown_padded_tables: bool | None = False,
    extras: Iterable[str] | dict[str, Any] | None = None,
) -> str:
    """Converts a line of Markdown (e.g. as generated by html2text filter) to html.

    :param text: The text in Markdown format.
    :param markdown_padded_tables: If true, monospace the tables for alignment.
    :param extras: Additional markdown2 extras, as names or as a dict of name: options (None if it has none); they
       are applied over MARKDOWN2_DEFAULT_EXTRAS, e.g. ``{'middle-word-em': True}`` restores emphasis within words.
    :return: The text in html format.
    """
    from markdown2 import Markdown

    markdowner_extras = MARKDOWN2_DEFAULT_EXTRAS.copy()
    if extras:
        markdowner_extras.update(extras if isinstance(extras, dict) else dict.fromkeys(extras))
    markdowner = Markdown(extras=markdowner_extras)
    if text == '* * *':  # manually expand horizontal ruler since <hr> is used to separate jobs
        return '-' * 80
    pre = ''
    post = ''
    if text.lstrip()[:2] == '* ':  # item of unordered list
        lstripped = text.lstrip(' ')
        indent = len(text) - len(lstripped)
        pre += '&nbsp;' * indent
        pre += '● ' if indent == 2 else '⯀ ' if indent == 4 else '○ '
        text = text.split('* ', 1)[1]
    if text[:1] == ' ':
        # replace leading spaces with NBSP or converter will strip them all
        stripped = text.lstrip()
        text = '&nbsp;' * (len(text) - len(stripped)) + stripped
    text = text.replace('` ', '`&nbsp;')  # replace leading spaces within code blocks
    if markdown_padded_tables and '|' in text:
        # a padded row in a table; keep it monospaced for alignment
        pre += '<span style="font-family:monospace;white-space:pre-wrap">'
        post += '</span>'
    text = text.replace('[](', '[[_Link with no text_]](')  # Add link text where missing
    html_out = str(markdowner.convert(text)).rstrip('\n')  # convert markdown to html
    # fixes for Gmail
    html_out = html_out.replace('<a', '<a style="font-family:inherit"')  # fix <a> tag styling
    html_out = html_out.replace('<img', '<img style="max-width:100%;height:auto;max-height:100%"')
    html_out = html_out.replace('<code>', '<span style="font-family:monospace;white-space:pre-wrap">')
    html_out = html_out.replace('</code>', '</span>')
    if 'tables' in markdowner_extras:
        html_out = html_out.replace('<table>', '<table border="1" cellspacing="0">')
    # remove <p> tags wrapping
    html_out, sub = re.subn(r'^<p>|</p>$', '', html_out)  # remove paragraph tags
    if sub:
        return pre + html_out + post
    html_out = re.sub(r'<(/?)h\d>', r'<\g<1>strong>', html_out)  # replace heading tags with <strong>
    return pre + html_out + post


# Optional dependencies are imported inside the functions that use them, so that start-up only pays for what a run
# needs (several of them take tens of milliseconds to import). The ImportError of a failed import is turned into the
# standard message below, e.g.:
#
#     try:
#         import pdftotext
#     except ImportError as e:
#         raise missing_dependency(e, 'pdftotext', used_by="the 'pdf2text' filter", extra='pdf2text') from e
#
# (FilterBase, DifferBase and ReporterBase wrap this in their raise_import_error() methods.) To check whether a package
# is available without importing it, use importlib.util.find_spec(); to use it only if it was already imported (e.g. to
# classify an exception), use sys.modules.get().


def missing_dependency(
    error: ImportError | str,
    package: str,
    *,
    used_by: str,
    extra: str | None = None,
    location: str | None = None,
) -> ImportError:
    """Return the standard ImportError for an optional dependency that cannot be imported (to be raised).

    :param error: The ImportError raised when importing the package (or its message).
    :param package: The name to install the package with (e.g. 'beautifulsoup4', not its module name 'bs4').
    :param used_by: What needs the package, e.g. "the 'pdf2text' filter".
    :param extra: The webchanges extra that installs the package (e.g. 'pdf2text' for webchanges[pdf2text]); if None,
       the message suggests installing the package itself.
    :param location: Where the package is needed, e.g. a job's indexed location.
    :returns: The ImportError, whose message includes how to install the package.
    """
    subject = f'{used_by[:1].upper()}{used_by[1:]}'
    if location:
        subject += f' ({location})'
    install = f'webchanges[{extra}]' if extra else package
    return ImportError(
        f"{subject} requires the Python package '{package}', which cannot be imported ({error}). Install it with "
        f"e.g. 'uv pip install --upgrade {install}'."
    )
