"""A few utilities used elsewhere."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.
from __future__ import annotations

import getpass
import importlib.machinery
import importlib.util
import logging
import os
import re
import shlex
import stat
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.
import sys
import textwrap
from math import floor, log10
from os import PathLike
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterable, Match

from markdown2 import Markdown

from webchanges import __project_name__, __version__

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]
if httpx is not None:
    try:
        import h2
    except ImportError:  # pragma: no cover
        h2 = None  # type: ignore[assignment]

try:
    from packaging.version import parse as parse_version
except ImportError:  # pragma: no cover
    from webchanges._vendored.packaging_version import parse as parse_version  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def lazy_import(fullname: str) -> ModuleType | None:
    """Lazily imports a module. See https://stackoverflow.com/questions/42703908.

    To identify loading time, run $ python -X importtime webchanges --help
    """
    try:
        return sys.modules[fullname]
    except KeyError:
        spec = importlib.util.find_spec(fullname)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            loader = importlib.util.LazyLoader(spec.loader)
            # Make module with proper locking and get it inserted into sys.modules.
            loader.exec_module(module)
            return module
    return None


class TrackSubClasses(type):
    """A metaclass that stores subclass name-to-class mappings in the base class."""

    # __subclasses__ gets redefined from default "Callable[[_TT], list[_TT]]
    __subclasses__: dict[str, TrackSubClasses]  # type: ignore[assignment]
    __anonymous_subclasses__: list[TrackSubClasses]
    __required__: tuple[str, ...] = ()
    __optional__: tuple[str, ...] = ()

    __kind__: str

    @staticmethod
    def sorted_by_kind(cls: TrackSubClasses) -> list[TrackSubClasses]:
        """Generates a list of all members of a class sorted by the value of their __kind__ attribute. Useful for
        documentation.

        :param cls: The class.
        :return: The sorted list of class members.
        """
        return [item for _, item in sorted((it.__kind__, it) for it in cls.__subclasses__.values() if it.__kind__)]

    def __init__(cls, name: str, bases: tuple[type, ...], namespace: dict) -> None:
        for base in bases:
            if base == object:
                continue

            for attr in {'__required__', '__optional__'}:
                if not hasattr(base, attr):
                    continue

                inherited = getattr(base, attr, ())
                new_value = tuple(namespace.get(attr, ())) + tuple(inherited)
                namespace[attr] = new_value
                setattr(cls, attr, new_value)

        for base in bases:
            if base == object:
                continue

            if hasattr(cls, '__kind__'):
                subclasses = getattr(base, '__subclasses__', None)
                if subclasses is not None:
                    logger.debug(f'Registering {cls} as {cls.__kind__}')
                    subclasses[cls.__kind__] = cls
                    break
            else:
                anonymous_subclasses = getattr(base, '__anonymous_subclasses__', None)
                if anonymous_subclasses is not None:
                    logger.debug(f'Registering {cls}')
                    anonymous_subclasses.append(cls)
                    break

        super().__init__(name, bases, namespace)


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
        shlex.split(editor) + [str(filename)],
        check=True,
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
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = module
    try:
        loader.exec_module(module)
    except Exception:
        sys.tracebacklimit = 1000
        raise
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
            return [line + ' (' + f'{{:{digits_try}d}}'.format(i + 1) + f'/{length})' for i, line in enumerate(chunks)]

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
    # _URL_RE = re.compile(  # original re
    #     r'\b('
    #     r'(?:([\w-]+):(/{1,3})|www[.])'
    #     r'(?:('
    #     r'?:(?:[^\s&()]|&amp;|&quot;)*(?:[^!"#$%&'
    #     r"'()*+,.:;<=>?@\[\]^`{|}~\s])"
    #     r")"
    #     r'|(?:\((?:[^\s&()]|&amp;|&quot;)*\))'
    #     r')+'
    #     r')'
    # )  # noqa: DUO138 catastrophic "re" usage - denial-of-service possible.

    _URL_RE = re.compile(  # modified to catch all URL parameters
        r'\b('
        r'(?:([\w-]+):(/{1,3})|www[.])'
        r'(?:('
        r'?:(?:[^\s()])*(?:[^!"#$%&'
        r"'()*+,.:;<=>?@\[\]^`{|}~\s])"
        r')'
        r'|(?:\((?:[^\s()])*\))'
        r')+'
        r')'
    )  # noqa: DUO138 catastrophic "re" usage - denial-of-service possible.

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

        if callable(extra_params):
            params = f' {extra_params(href).strip()}'
        else:
            params = extra_params

        # clip long urls. max_len is just an approximation
        max_len = 30
        if shorten and len(url) > max_len:
            before_clip = url
            if proto:
                proto_len = len(proto) + 1 + len(m.group(3) or '')  # +1 for :
            else:
                proto_len = 0

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
    return _URL_RE.sub(make_link, text)


def get_new_version_number(timeout: float | None = None) -> str | bool:
    """Check PyPi for newer version of project.

    :parameter timeout: Timeout in seconds after which empty string is returned.
    :returns: The new version number if a newer version of project is found on PyPi, empty string otherwise, False if
      error retrieving the new version number is encountered.
    """
    if httpx is None:
        logger.info('Cannot query PyPi for latest release: HTTPX not installed')
        return False

    try:
        r = httpx.Client(http2=h2 is not None, timeout=timeout).get(f'https://pypi.org/pypi/{__project_name__}/json')
    except httpx.RequestError as e:
        logger.info(f'Exception when querying PyPi for latest release: {e}')
        return False

    if r.is_success:
        latest_release: str = r.json()['info']['version']
        if parse_version(latest_release) > parse_version(__version__):
            return latest_release
    else:
        logger.info(f'HTTP error when querying PyPi for latest release: {r}')

    return ''


def dur_text(duration: float) -> str:
    """Returns a formatted string optimized to the number of seconds for use in footers.

    :parameter duration: The duration in seconds.
    :returns: The formatted string.
    """
    if duration < 60:
        return f'{float(f"{duration:.2g}"):g} seconds'
    else:
        m, s = divmod(duration, 60)
        return f'{m:.0f}:{s:02.0f}'


def file_ownership_checks(filename: Path) -> list[str]:
    """Check security of file and its directory, i.e. that they belong to the current UID or root and only the owner
    can write to them. Return list of errors if any. Linux only.

    :returns: List of errors encountered (if any).
    """

    if sys.platform == 'win32':
        return []

    file_ownership_errors = []
    current_uid = os.getuid()  # type: ignore[attr-defined]  # not defined in Windows

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


def mark_to_html(text: str, markdown_padded_tables: bool | None = False, extras: Iterable[str] | None = None) -> str:
    """Converts a line of Markdown (e.g. as generated by html2text filter) to html.

    :param text: The text in Markdown format.
    :param markdown_padded_tables: If true, monospace the tables for alignment.
    :param extras: Additional extras for Markdown.
    :return: The text in html format.
    """
    markdowner_extras = set(extras) if extras else set()
    markdowner_extras.add('strike')  # text marked by double tildes is ~~strikethrough~~
    markdowner_extras.add('target-blank-links')  # <a> tags have rel="noopener" for added security
    markdowner = Markdown(extras=list(markdowner_extras))
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
