import html
import importlib.machinery
import importlib.util
import logging
import os
import re
import shlex
import subprocess
import sys
import typing
from typing import Callable, Tuple, Union

logger = logging.getLogger(__name__)


class TrackSubClasses(type):
    """A metaclass that stores subclass name-to-class mappings in the base class"""

    @staticmethod
    def sorted_by_kind(cls):
        return [item for _, item in sorted((it.__kind__, it) for it in cls.__subclasses__.values())]

    def __init__(cls, name, bases, namespace):
        for base in bases:
            if base == object:
                continue

            for attr in ('__required__', '__optional__'):
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
                    logger.info('Registering %r as %s', cls, cls.__kind__)
                    subclasses[cls.__kind__] = cls
                    break
            else:
                anonymous_subclasses = getattr(base, '__anonymous_subclasses__', None)
                if anonymous_subclasses is not None:
                    logger.info('Registering %r', cls)
                    anonymous_subclasses.append(cls)
                    break

        super().__init__(name, bases, namespace)


def atomic_rename(old_filename, new_filename):
    """Renames a file"""
    if os.name == 'nt' and os.path.exists(new_filename):
        new_old_filename = new_filename + '.bak'
        if os.path.exists(new_old_filename):
            os.remove(new_old_filename)
        os.rename(new_filename, new_old_filename)
        os.rename(old_filename, new_filename)
        if os.path.exists(new_old_filename):
            os.remove(new_old_filename)
    else:
        os.rename(old_filename, new_filename)


def edit_file(filename):
    """Opens the editor to edit the file"""
    editor = os.environ.get('EDITOR', None)
    if not editor:
        editor = os.environ.get('VISUAL', None)
    if not editor and os.name == 'nt':
        editor = 'notepad.exe'
    else:
        raise SystemExit('Please set the path to the editor in the environment variable $EDITOR'
                         ' e.g. "export EDITOR=nano"')

    subprocess.check_call(shlex.split(editor) + [filename])


def import_module_from_source(module_name, source_path):
    loader = importlib.machinery.SourceFileLoader(module_name, source_path)
    spec = importlib.util.spec_from_file_location(module_name, source_path, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


def chunk_string(string, length, *, numbering=False):
    """Chunks string"""
    if len(string) <= length:
        return [string]

    if numbering:
        # Subtract to fit numbering (FIXME: this breaks for > 9 chunks)
        length -= len(' (0/0)')
        parts = []
        string = string.strip()
        while string:
            if len(string) <= length:
                parts.append(string)
                string = ''
                break

            idx = string.rfind(' ', 1, length + 1)
            if idx == -1:
                idx = string.rfind('\n', 1, length + 1)
            if idx == -1:
                idx = length
            parts.append(string[:idx])
            string = string[idx:].strip()
        return (f'{part} ({i + 1}/{len(parts)})' for i, part in enumerate(parts))

    return (string[i:length + i].strip() for i in range(0, len(string), length))


# Using regex from tornado library
# The regex is modified to avoid character entities other than &amp; so
# that we won't pick up &quot;, etc.
# Note it is vulnerable to Regular expression Denial of Service (ReDoS),
# which would divert computational  resources to an expensive regex match
# (i.e. limited risk in this application)
_URL_RE = re.compile(r"""\b((?:([\w-]+):(/{1,3})|www[.])(?:(?:(?:[^\s&()]|
&amp;|&quot;)*(?:[^!"#$%&'()*+,.:;<=>?@\[\]^`{|}~\s]))|(?:\((?:[^\s&()]|&amp;|
&quot;)*\)))+)""")  # noqa:DUO138 catastrophic "re" usage - denial-of-service possible


def linkify(
    text: str,
    shorten: bool = False,
    extra_params: Union[str, Callable[[str], str]] = '',
    require_protocol: bool = False,
    permitted_protocols: Tuple[str] = ('http', 'https', 'mailto',),
) -> str:
    """Converts plain text into HTML with links.
    For example: ``linkify("Hello http://tornadoweb.org!")`` would return
    ``Hello <a href="http://tornadoweb.org">http://tornadoweb.org</a>!``
    Parameters:
    * ``shorten``: Long urls will be shortened for display.
    * ``extra_params``: Extra text to include in the link tag, or a callable
      taking the link as an argument and returning the extra text
      e.g. ``linkify(text, extra_params='rel="nofollow" class="external"')``,
      or::
          def extra_params_cb(url):
              if url.startswith("http://example.com"):
                  return 'class="internal"'
              else:
                  return 'class="external" rel="nofollow"'
          linkify(text, extra_params=extra_params_cb)
    * ``require_protocol``: Only linkify urls which include a protocol. If
      this is False, urls such as www.facebook.com will also be linkified.
    * ``permitted_protocols``: Tuple (or set) of protocols which should be
      linkified, e.g. ``linkify(text, permitted_protocols=("http", "ftp",
      "mailto"))``. It is very unsafe to include protocols such as
      ``javascript``.
    """
    if extra_params and not callable(extra_params):
        extra_params = ' ' + extra_params.strip()

    def make_link(m: typing.Match) -> str:
        url = m.group(1)
        proto = m.group(2)
        if require_protocol and not proto:
            return url  # not protocol, no linkify

        if proto and proto not in permitted_protocols:
            return url  # bad protocol, no linkify

        href = m.group(1)
        if not proto:
            href = 'http://' + href  # no proto specified, use http

        if callable(extra_params):
            params = " " + extra_params(href).strip()
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
                url = (
                    url[:proto_len]
                    + parts[0]
                    + '/'
                    + parts[1][:8].split('?')[0].split('.')[0]
                )

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
                    params += ' title=' + href

        return f'<a href="{href}"{params}>{url}</a>'

    text = html.escape(text)
    return _URL_RE.sub(make_link, text)
