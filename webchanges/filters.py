"""Filters."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import csv
import hashlib
import html
import io
import itertools
import json
import logging
import os
import re
import shlex
import subprocess
import warnings
from abc import ABC
from enum import Enum
from html.parser import HTMLParser
from typing import Any, Dict, Iterator, List, Optional, Tuple, Type, TYPE_CHECKING, Union
from xml.dom import minidom  # nosec: B408 Replace minidom with the equivalent defusedxml package TODO

import html2text
import yaml
from lxml import etree  # noqa: DUO107 insecure use of XML modules, prefer "defusedxml"  # nosec: B410 TODO
from lxml.cssselect import CSSSelector  # noqa: DUO107 insecure use of XML ... "defusedxml"  # nosec: B410 TODO

from . import __project_name__
from .util import TrackSubClasses

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from .handler import JobState
    from .jobs import JobBase

try:
    import bs4
except ImportError:  # pragma: has-bs4
    bs4 = None

try:
    import cssbeautifier
except ImportError:
    cssbeautifier = None

try:
    import jq
except ImportError:  # pragma: has-jq
    jq = None

try:
    import jsbeautifier
except ImportError:
    jsbeautifier = None

try:
    import pdftotext
except ImportError:  # pragma: has-pdftotext
    pdftotext = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:  # pragma: has-pytesseract
    pytesseract = None

try:
    import vobject
except ImportError:
    vobject = None
try:
    from packaging.version import parse as parse_version
except ImportError:
    from ._vendored.packaging_version import parse as parse_version  # type: ignore[misc]

logger = logging.getLogger(__name__)


class FilterBase(metaclass=TrackSubClasses):
    """The base class for filters."""

    __subclasses__: Dict[str, Type[FilterBase]] = {}
    __anonymous_subclasses__: List[Type[FilterBase]] = []

    __kind__: str = ''

    # Typing
    __supported_subfilters__: Dict[str, str]
    __default_subfilter__: str
    __no_subfilter__: bool
    __uses_bytes__: bool
    method: str

    def __init__(self, job: JobBase, state: JobState) -> None:
        """

        :param job: the JobBase.
        :param state: the JobState.
        """
        self.job = job
        self.state = state

    @classmethod
    def filter_documentation(cls) -> str:
        """Generates simple filter documentation for use in the --features command line argument.

        :returns: A string to display.
        """
        result: List[str] = []
        for sc in TrackSubClasses.sorted_by_kind(cls):
            default_subfilter = getattr(sc, '__default_subfilter__', None)
            result.extend((f'  * {sc.__kind__} - {sc.__doc__}',))
            if hasattr(sc, '__supported_subfilters__'):
                for key, doc in sc.__supported_subfilters__.items():
                    result.append(
                        '      %s%s%s ... %s'
                        % ('[' if key == default_subfilter else '', key, ']' if key == default_subfilter else '', doc)
                    )
        result.append('\n[] ... Parameter can be supplied as unnamed value\n')
        return '\n'.join(result)

    @classmethod
    def auto_process(cls, state: JobState, data: Union[str, bytes]) -> Union[str, bytes]:
        """Processes all automatic filters (those with "MATCH" set) in JobState.Job over the data.

        :param state: The JobState object.
        :param data: The data to be processed (filtered).
        :returns: The output from the chain of filters (filtered data).
        """
        filters = itertools.chain(
            (filtercls for _, filtercls in sorted(cls.__subclasses__.items(), key=lambda k_v: k_v[0])),
            cls.__anonymous_subclasses__,
        )

        for filtercls in filters:
            filter_instance = filtercls(state.job, state)
            if filter_instance.match():
                logger.info(f'Job {state.job.index_number}: Auto-applying filter {filter_instance}')
                data = filter_instance.filter(data, {})  # All filters take a subfilter

        return data

    @classmethod
    def normalize_filter_list(
        cls, filter_spec: Union[str, List[Union[str, Dict[str, Any]]]]
    ) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """Generates a list of filters that has been checked for its validity.

        :param filter_spec: A list of either filter_kind, subfilter (where subfilter is a dict) or a legacy
           string-based filter list specification.
        :returns: Iterator of filter_kind, subfilter (where subfilter is a dict).
        """
        for filter_kind, subfilter in cls._internal_normalize_filter_list(filter_spec):
            filtercls = cls.__subclasses__.get(filter_kind, None)

            if filtercls is None:
                raise ValueError(f'Unknown filter kind: {filter_kind} (subfilter: {subfilter}).')

            if getattr(filtercls, '__no_subfilter__', False) and subfilter:
                raise ValueError(f'No subfilters supported for {filter_kind}.')

            if hasattr(filtercls, '__supported_subfilters__'):
                provided_keys = set(subfilter.keys())
                allowed_keys = set(filtercls.__supported_subfilters__.keys())
                unknown_keys = provided_keys.difference(allowed_keys)
                if unknown_keys and '<any>' not in allowed_keys:
                    raise ValueError(
                        f'Filter {filter_kind} does not support subfilter(s): {unknown_keys} '
                        f'(supported: {allowed_keys}).'
                    )

            yield filter_kind, subfilter

    @classmethod
    def _internal_normalize_filter_list(
        cls, filter_spec: Union[str, List[Union[str, Dict[str, Any]]]]
    ) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """Generates a list of filters with its default subfilter if not supplied.

        :param filter_spec: A list of either filter_kind, subfilter (where subfilter is a dict) or a legacy
           string-based filter list specification.
        :returns: Iterator of filter_kind, subfilter (where subfilter is a dict)
        """
        if isinstance(filter_spec, str):
            old_filter_spec = filter_spec

            # Legacy string-based filter list specification:
            # "filter1:param1,filter2,filter3,filter4:param4"
            filter_spec = [
                {filter_kind.split(':', maxsplit=1)[0]: filter_kind.split(':', maxsplit=1)[1]}
                if ':' in filter_kind
                else {filter_kind: ''}
                for filter_kind in old_filter_spec.split(',')
            ]
            warnings.warn(
                f'String-based filter definitions ({old_filter_spec}) are deprecated, please convert to dict-style:\n\n'
                f'{yaml.safe_dump(filter_spec, default_flow_style=False, allow_unicode=True)}',
                DeprecationWarning,
            )

        if isinstance(filter_spec, list):
            for item in filter_spec:
                if isinstance(item, str):
                    filter_kind, subfilter = item, None
                elif isinstance(item, dict):
                    filter_kind, subfilter = next(iter(item.items()))
                else:
                    raise ValueError('Subfilter(s) must be a string or a dictionary.')

                filtercls = cls.__subclasses__.get(filter_kind, None)

                if isinstance(subfilter, dict):
                    yield filter_kind, subfilter
                elif subfilter is None:
                    yield filter_kind, {}
                elif hasattr(filtercls, '__default_subfilter__'):
                    yield filter_kind, {getattr(filtercls, '__default_subfilter__'): subfilter}
                else:
                    yield filter_kind, subfilter

    @classmethod
    def process(cls, filter_kind: str, subfilter: Dict[str, Any], job_state: JobState, data: Union[str, bytes]) -> str:
        """Process the filter.

        :param filter_kind: The name of the filter.
        :param subfilter: The subfilter information.
        :param job_state: The JobState object (containing the Job).
        :param data: The data upon which to apply the filter.
        :returns: The data after the filter has been applied.
        """
        logger.info(f'Job {job_state.job.index_number}: Applying filter {filter_kind}, subfilter(s) {subfilter}')
        filtercls: Optional[Type[FilterBase]] = cls.__subclasses__.get(filter_kind)
        if filtercls:
            return filtercls(job_state.job, job_state).filter(data, subfilter)
        else:
            return str(data)

    @classmethod
    def filter_chain_needs_bytes(cls, filter_name: Union[str, List[Union[str, Dict[str, Any]]]]) -> bool:
        """Checks whether the first filter requires data in bytes (not Unicode).

        :param filter_name: The filter.
        :returns: True if the first filter requires data in bytes.
        """
        first_filter = next(cls.normalize_filter_list(filter_name), None)
        if first_filter is not None:
            filter_kind, subfilter = first_filter
            return cls.is_bytes_filter_kind(filter_kind)

        return False

    @classmethod
    def is_bytes_filter_kind(cls, filter_kind: str) -> bool:
        """Checks whether the filter requires data in bytes (not Unicode).

        :param filter_kind: The filter name.
        :returns: True if the filter requires data in bytes.
        """
        return filter_kind in (
            name for name, class_ in cls.__subclasses__.items() if getattr(class_, '__uses_bytes__', False)
        )

    def match(self) -> bool:
        """Method used by automatch filters.

        :returns: True if an automatch filter.
        """
        return False

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Method used by the filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        raise NotImplementedError()


class AutoMatchFilter(FilterBase):
    """Base class for filters that automatically match based on location."""

    MATCH = None

    def match(self) -> bool:
        """Check whether the filter matches (i.e. needs to be executed).

        :returns: True if match is found.
        """
        if self.MATCH is None:
            return False

        d = self.job.to_dict()
        result = all(d.get(k, None) == v for k, v in self.MATCH.items())
        logger.debug(f'Matching {self} with {self.job} result: {result}')
        return result

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Method used by filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        pass


class RegexMatchFilter(FilterBase):
    """Base class for filters that automatically match based on location.
    Same as AutoMatchFilter but matching is done with regexes."""

    MATCH = None

    def match(self) -> bool:
        """Check whether the filter matches (i.e. needs to be executed).

        :returns: True if match is found.
        """
        if self.MATCH is None:
            return False

        d = self.job.to_dict()

        # It's a match if we have at least one key/value pair that matches,
        # and no key/value pairs that do not match
        matches = [v.match(d[k]) for k, v in self.MATCH.items() if k in d]
        result = len(matches) > 0 and all(matches)
        logger.debug(f'Matching {self} with {self.job} result: {result}')
        return result

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Method used by filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        pass


class BeautifyFilter(FilterBase):
    """Beautify HTML (requires Python package ``BeautifulSoup`` and optionally ``jsbeautifier`` and/or
    ``cssbeautifier``)."""

    __kind__ = 'beautify'

    __supported_subfilters__ = {'indent': 'Number of spaces by which to indent HTML output.'}

    __default_subfilter__ = 'indent'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        if bs4 is None:
            raise ImportError(
                f"Python package 'BeautifulSoup' is not installed; cannot use the '{self.__kind__}' filter. "
                f'({self.job.get_indexed_location()})'
            )

        soup = bs4.BeautifulSoup(data, features='lxml')

        if jsbeautifier is None:
            logger.warning(
                f"Python package 'jsbeautifier' is not installed; will not beautify <script> tags"
                f' ({self.job.get_indexed_location()})'
            )
        else:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    beautified_js = jsbeautifier.beautify(script.string)
                    script.string = beautified_js

        if cssbeautifier is None:
            logger.warning(
                "Python package 'cssbeautifier' is not installed; will not beautify <style> tags"
                f' ({self.job.get_indexed_location()})'
            )
        else:
            styles = soup.find_all('style')
            for style in styles:
                if style.string:
                    beautified_css = cssbeautifier.beautify(style.string)
                    style.string = beautified_css

        if parse_version(bs4.__version__) >= parse_version('4.11'):
            indent = subfilter.get('indent', 1)
            return soup.prettify(formatter=bs4.formatter.HTMLFormatter(indent=indent))
        else:
            return soup.prettify()


class Html2TextFilter(FilterBase):
    """Convert a string consisting of HTML to Unicode plain text for easy difference checking."""

    __kind__ = 'html2text'

    __supported_subfilters__ = {
        'method': 'Method to use for conversion (html2text [default], bs4, or strip_tags)',
        'separator': 'bs4: Strings will be concatenated using this separator',
        'strip': 'bs4: If True, strings will be stripped before being concatenated',
        '<any>': 'html2text: Library-specific options (see '
        'https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options)',
    }

    __default_subfilter__ = 'method'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        """Filter (process) the data.

        Subfilter key can be ``method`` and any method-specific option to be passed to it.
        The following ``method`` keys are supported:

        * ``html2text`` (default): Use html2text Python library to extract text (in Markdown).

          * options: See
            https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options,
            however the following options are set to non-default values:

            * ``unicode_snob = True``
            * ``body_width = 0``
            * ``ignore_images = True``
            * ``single_line_break = True``
            * ``wrap_links = False``

        * ``bs4``: Use Beautiful Soup Python library to prettify the HTML.

          * options:

            * parser: the type of markup you want to parse (currently supported are ``html``, ``xml``, and ``html5``)
              or the name of the parser library you want to use (currently supported options are ``lxml``,
              ``html5lib`` and ``html.parser``) as per
              https://www.crummy.com/software/BeautifulSoup/bs4/doc/#specifying-the-parser-to-use.  Different parsers
              are compared at https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser.
              Note: ``html5lib``requires having the ``html5lib`` Python package already installed.
            * separator: Strings will be concatenated using this separator. Defaults to `````` (empty string).
            * strip: If True, strings will be stripped before being concatenated. Defaults to False.

        * ``strip_tags``: A simple and fast regex-based HTML tag stripper.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """

        # extract method and options from subfilter, defaulting to method html2text
        if 'method' in subfilter:
            method = subfilter['method']
            del subfilter['method']
        else:
            method = 'html2text'
        options = subfilter

        if method in ('html2text', 'pyhtml2text'):  # pythtml2text for backward compatibility
            if method == 'pyhtml2text':
                warnings.warn(
                    f"Filter html2text's method 'pyhtml2text' is deprecated: remove method as it's now the "
                    f"filter's default ({self.job.get_indexed_location()})",
                    DeprecationWarning,
                )
            self.job.is_markdown = True

            parser = html2text.HTML2Text()
            parser.unicode_snob = True
            parser.body_width = 0
            parser.ignore_images = True
            parser.single_line_break = True
            parser.wrap_links = False
            if hasattr(self.job, 'url'):
                parser.baseurl = self.job.url
            for k, v in options.items():
                setattr(parser, k.lower(), v)
                if k == 'pad_tables':
                    self.job.markdown_padded_tables = v

            # html2text returns lines with spaces at the end even if they are ignored when rendered
            return '\n'.join(line.rstrip() for line in parser.handle(data).splitlines())

        elif method == 'bs4':
            if bs4 is None:
                raise ImportError(
                    f"Python package 'BeautifulSoup' is not installed; cannot use the '{self.__kind__}: "
                    f"{method}' filter. ({self.job.get_indexed_location()})"
                )

            bs4_parser: str = options.pop('parser', 'lxml')
            soup = bs4.BeautifulSoup(data, bs4_parser)
            separator: str = options.pop('separator', '')
            strip: bool = options.pop('strip', False)
            return soup.get_text(separator=separator, strip=strip)

        elif method in ('strip_tags', 're'):  # re for backward compatibility
            if method == 're':
                warnings.warn(
                    f"Filter html2text's method 're' is deprecated: replace with 'strip_tags' "
                    f'({self.job.get_indexed_location()})',
                    DeprecationWarning,
                )
            stripped_tags = html.unescape(re.sub(r'<[^>]*>', '', data))
            return '\n'.join((line.rstrip() for line in stripped_tags.splitlines() if line.strip() != ''))

        elif method == 'lynx':
            raise NotImplementedError(
                f"Filter html2text's method 'lynx' is no longer supported; for similar results, use the filter without "
                f'specifying a method. ({self.job.get_indexed_location()})'
            )

        else:
            raise ValueError(f"Unknown method {method} for filter 'html2text'. ({self.job.get_indexed_location()})")


class Csv2TextFilter(FilterBase):
    """Convert CSV to plaintext."""

    __kind__ = 'csv2text'

    __supported_subfilters__ = {
        'format_message': 'A format string with the headers that will be outputted for each csv'
        'line (header will be lower-cased)',
        'has_header': 'If specified and true - use the first line as a header. '
        'If false - force ignore first line as header (treat it as data). '
        'If not specified it will be guessed by the has_header method of csv.Sniffer.',
        'ignore_header': 'If your format string is number based, but the CSV has headers, '
        'this flag will force ignoring the header.',
    }

    __default_subfilter__ = 'format_message'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        has_header_config = subfilter.get('has_header')

        if has_header_config is None:
            has_header = csv.Sniffer().has_header(data)
        else:
            has_header = has_header_config

        reader = csv.reader(data.split('\n'))
        data_list = list(reader)
        header = None

        if has_header:
            header = data_list.pop(0)
            header = [i.lower() for i in header]

        message = subfilter['format_message']
        ignore_header = subfilter.get('ignore_header')

        lines = []
        for i in data_list:
            if header and not ignore_header:
                legend = dict(zip(header, i))
                lines.append(message.format(**legend))
            else:
                lines.append(message.format(*i))

        return '\n'.join(lines)


class Pdf2TextFilter(FilterBase):  # pragma: has-pdftotext
    """Convert PDF to plaintext (requires Python package ``pdftotext`` and its dependencies)."""

    # Dependency: pdftotext (https://github.com/jalan/pdftotext), itself based
    # on poppler (https://poppler.freedesktop.org/)
    # Note: check pdftotext website for OS-specific dependencies for install

    __kind__ = 'pdf2text'
    __uses_bytes__ = True

    __supported_subfilters__ = {
        'password': 'PDF password for decryption',
        'raw': 'If true, output text in same order as in PDF content stream',
        'physical': 'If true, try to format text to look the same (columns etc.)',
    }

    __default_subfilter__ = 'password'

    def filter(self, data: bytes, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        # data must be bytes
        if not isinstance(data, bytes):
            raise ValueError(
                f"The 'html2text: pdf2text' filter needs bytes input (is it the first filter?). "
                f'({self.job.get_indexed_location()})'
            )

        if pdftotext is None:
            raise ImportError(
                f"Python package 'pdftotext' (and OS-specific dependencies) is not installed; cannot use "
                f"'html2text: pdf2text' filter. ({self.job.get_indexed_location()})"
            )

        return '\n'.join(
            pdftotext.PDF(
                io.BytesIO(data),
                password=subfilter.get('password', ''),
                raw=subfilter.get('method', False),
                physical=subfilter.get('physical', True),
            ),
        )


class Ical2TextFilter(FilterBase):
    """Convert iCalendar to plaintext (requires Python package ``vobject``)."""

    __kind__ = 'ical2text'

    __no_subfilter__ = True

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        if vobject is None:
            raise ImportError(
                f"Python package 'vobject' is not installed; cannot use 'html2text: ical2text' filter. "
                f'({self.job.get_indexed_location()})'
            )

        result = []
        if isinstance(data, str):
            parsedCal = vobject.readOne(data)
        else:
            try:
                parsedCal = vobject.readOne(data)
            except vobject.ParseError:
                parsedCal = vobject.readOne(data.decode(errors='ignore'))
                logger.warning('Found and ignored Unicode-related errors when reading iCal entry.')

        for event in parsedCal.getChildren():
            if event.name == 'VEVENT':
                if hasattr(event, 'dtstart'):
                    start_date = event.dtstart.value.strftime('%F %H:%M')
                else:
                    start_date = 'unknown start date'

                if hasattr(event, 'dtend'):
                    end_date = event.dtend.value.strftime('%F %H:%M')
                else:
                    end_date = start_date

                if start_date == end_date:
                    date_str = start_date
                else:
                    date_str = f'{start_date} -- {end_date}'

                result.append(f'{date_str}: {event.summary.value}')

        return '\n'.join(result)


class FormatJsonFilter(FilterBase):
    """Convert to formatted JSON."""

    __kind__ = 'format-json'

    __supported_subfilters__ = {
        'indentation': 'Indentation level for pretty-printing',
        'sort_keys': 'Sort the output of dictionaries by key',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        sort_keys = subfilter.get('sort_keys', False)
        indentation = int(subfilter.get('indentation', 4))
        parsed_json = json.loads(data)
        return json.dumps(
            parsed_json, ensure_ascii=False, sort_keys=sort_keys, indent=indentation, separators=(',', ': ')
        )


class FormatXMLFilter(FilterBase):
    """Convert to formatted XML using lxml.etree."""

    __kind__ = 'format-xml'

    __no_subfilter__ = True

    # __supported_subfilters__ = {
    #     'indentation': 'Indentation level for pretty-printing',
    # }
    #
    # __default_subfilter__ = 'indentation'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        parsed_xml = etree.XML(data)
        return etree.tostring(parsed_xml, encoding='unicode', pretty_print=True)


class PrettyXMLFilter(FilterBase):
    """Pretty-print XML using xml.dom.minidom."""

    __kind__ = 'pretty-xml'

    __supported_subfilters__ = {
        'indentation': 'Indentation level for pretty-printing',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        indentation = int(subfilter.get('indentation', 2))
        return minidom.parseString(data).toprettyxml(indent=' ' * indentation)  # nosec: B318 use defusedxml TODO


class KeepLinesContainingFilter(FilterBase):
    """Filter only lines matching a regular expression."""

    __kind__ = 'keep_lines_containing'

    __supported_subfilters__ = {
        'text': 'Lines matching this text are kept (default)',
        're': 'Lines matching this expression are kept',
    }

    __default_subfilter__ = 'text'

    def filter(  # type: ignore[override]
        self: Union['KeepLinesContainingFilter', 'GrepFilter'],
        data: str,
        subfilter: Dict[str, Any],
    ) -> str:
        if 'text' in subfilter:
            if isinstance(subfilter['text'], str):
                return '\n'.join(line for line in data.splitlines() if subfilter['text'] in line)
            else:
                raise TypeError(
                    f"The '{self.__kind__}' filter requires a string but you provided a "
                    f"{type(subfilter['text']).__name__}. ({self.job.get_indexed_location()})"
                )
        if 're' in subfilter:
            if isinstance(subfilter['re'], str):
                return '\n'.join(line for line in data.splitlines() if re.search(subfilter['re'], line))
            else:
                raise TypeError(
                    f"The '{self.__kind__}' filter requires a string but you provided a "
                    f"{type(subfilter['re']).__name__}. ({self.job.get_indexed_location()})"
                )
        else:
            raise ValueError(
                f"The '{self.__kind__}' filter requires a 'text' or 're' sub-directive. "
                f'({self.job.get_indexed_location()})'
            )


class GrepFilter(FilterBase):
    """Deprecated; use ``keep_lines_containing`` instead."""

    __kind__ = 'grep'

    __supported_subfilters__ = {
        're': 'Lines matching this expression are kept (required)',
    }

    __default_subfilter__ = 're'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        warnings.warn(
            f"The 'grep' filter is deprecated; replace with 'keep_lines_containing' + 're' subfilter"
            f' ({self.job.get_indexed_location()})',
            DeprecationWarning,
        )
        return KeepLinesContainingFilter.filter(self, data, subfilter)


class DeleteLinesContainingFilter(FilterBase):
    """Remove lines matching a regular expression."""

    __kind__ = 'delete_lines_containing'

    __supported_subfilters__ = {
        'text': 'Lines matching this text are deleted (default)',
        're': 'Lines matching this expression deleted kept',
    }

    __default_subfilter__ = 'text'

    def filter(  # type: ignore[override]
        self: Union['DeleteLinesContainingFilter', 'GrepIFilter'],
        data: str,
        subfilter: Dict[str, Any],
    ) -> str:
        if 'text' in subfilter:
            if isinstance(subfilter['text'], str):
                return '\n'.join(line for line in data.splitlines() if subfilter['text'] not in line)
            else:
                raise TypeError(
                    f"The '{self.__kind__}' filter requires a string but you provided a "
                    f"{type(subfilter['text']).__name__}. ({self.job.get_indexed_location()})"
                )
        if 're' in subfilter:
            if isinstance(subfilter['re'], str):
                return '\n'.join(line for line in data.splitlines() if re.search(subfilter['re'], line) is None)
            else:
                raise TypeError(
                    f"The '{self.__kind__}' filter requires a string but you provided a "
                    f"{type(subfilter['re']).__name__}. ({self.job.get_indexed_location()})"
                )
        else:
            raise ValueError(
                f"The '{self.__kind__}' filter requires a 'text' or 're' sub-directive. "
                f'({self.job.get_indexed_location()})'
            )


class GrepIFilter(FilterBase):
    """Deprecated; use ``delete_lines_containing`` instead."""

    __kind__ = 'grepi'

    __supported_subfilters__ = {
        're': 'Lines matching this expression are removed (required)',
    }

    __default_subfilter__ = 're'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        warnings.warn(
            f"The 'grepi' filter is deprecated; replace with 'delete_lines_containing' + 're' subfilter"
            f' ({self.job.get_indexed_location()})',
            DeprecationWarning,
        )
        return DeleteLinesContainingFilter.filter(self, data, subfilter)


class StripFilter(FilterBase):
    """Strip leading and trailing whitespace."""

    __kind__ = 'strip'

    __supported_subfilters__ = {
        'splitlines': 'Apply the filter on each line of text (default: false, apply to the entire data)',
        'chars': 'String specifying the set of characters to be removed. If omitted, defaults to removing whitespace',
        'side': "One-sided removal: either 'left' (leading characters) or 'right' (trailing characters)",
    }

    __default_subfilter__ = 'chars'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        if subfilter.get('splitlines'):

            lines = data.splitlines()

            if 'side' in subfilter:
                if subfilter['side'] == 'right':
                    return '\n'.join([line.rstrip(subfilter.get('chars')) for line in lines])
                if subfilter['side'] == 'left':
                    return '\n'.join([line.lstrip(subfilter.get('chars')) for line in lines])

                raise ValueError(
                    f"The 'strip' filter's 'side' sub-directive can only be 'right' or 'left'. "
                    f'({self.job.get_indexed_location()})'
                )

            return '\n'.join([line.strip(subfilter.get('chars')) for line in lines])

        else:
            if 'side' in subfilter:
                if subfilter['side'] == 'right':
                    return data.rstrip(subfilter.get('chars'))
                if subfilter['side'] == 'left':
                    return data.lstrip(subfilter.get('chars'))

                raise ValueError(
                    f"The 'strip' filter's 'side' sub-directive can only be 'right' or 'left'. "
                    f'({self.job.get_indexed_location()})'
                )

            return data.strip(subfilter.get('chars'))


class StripLinesFilter(FilterBase):
    """Deprecated; use ``strip`` with subfilter ``splitlines`` instead."""

    __kind__ = 'striplines'

    __no_subfilter__ = True

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        warnings.warn(
            f"The 'strip_each_line' filter is deprecated; replace with 'strip' and sub-directive 'splitlines: "
            f"true' ({self.job.get_indexed_location()})",
            DeprecationWarning,
        )
        return '\n'.join([line.strip() for line in data.splitlines()])


class FilterBy(Enum):
    ATTRIBUTE = 1
    TAG = 2


class ElementsBy(HTMLParser, ABC):
    def __init__(self, filter_by: FilterBy, name: str, value: Any = None) -> None:
        super().__init__()

        self._filter_by = filter_by
        if self._filter_by == FilterBy.ATTRIBUTE:
            self._attributes = {name: value}
        else:
            # FilterBy.TAG
            self._name = name

        self._result: List[str] = []
        self._inside: bool = False
        self._elts: List[str] = []

    def get_html(self) -> str:
        return ''.join(self._result)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        ad = dict(attrs)

        if self._filter_by == FilterBy.ATTRIBUTE and all(ad.get(k, None) == v for k, v in self._attributes.items()):
            self._inside = True
        elif self._filter_by == FilterBy.TAG and tag == self._name:
            self._inside = True

        if self._inside:
            self._result.append(f"<{tag}{' ' if attrs else ''}%s>" % ' '.join(f'{k}="{v}"' for k, v in attrs))
            self._elts.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._inside:
            self._result.append(f'</{tag}>')
            if tag in self._elts:
                t = self._elts.pop()
                while t != tag and self._elts:
                    t = self._elts.pop()
            if not self._elts:
                self._inside = False

    def handle_data(self, data: str) -> None:
        if self._inside:
            self._result.append(data)


class ElementByIdFilter(FilterBase):
    """Get all HTML elements matching an ID."""

    __kind__ = 'element-by-id'

    __supported_subfilters__ = {
        'id': 'ID of the element to filter for (required)',
    }

    __default_subfilter__ = 'id'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        if 'id' not in subfilter:
            raise ValueError(
                f"The 'element-by-id' filter needs an id for filtering. ({self.job.get_indexed_location()})"
            )

        element_by_id = ElementsBy(FilterBy.ATTRIBUTE, 'id', subfilter['id'])
        element_by_id.feed(data)
        return element_by_id.get_html()


class ElementByClassFilter(FilterBase):
    """Get all HTML elements matching a class."""

    __kind__ = 'element-by-class'

    __supported_subfilters__ = {
        'class': 'HTML class attribute to filter for (required)',
    }

    __default_subfilter__ = 'class'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        if 'class' not in subfilter:
            raise ValueError(
                f"The 'element-by-class' filter needs a class for filtering. ({self.job.get_indexed_location()})"
            )

        element_by_class = ElementsBy(FilterBy.ATTRIBUTE, 'class', subfilter['class'])
        element_by_class.feed(data)
        return element_by_class.get_html()


class ElementByStyleFilter(FilterBase):
    """Get all HTML elements matching a style."""

    __kind__ = 'element-by-style'

    __supported_subfilters__ = {
        'style': 'HTML style attribute value to filter for (required)',
    }

    __default_subfilter__ = 'style'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        if 'style' not in subfilter:
            raise ValueError(
                f"The 'element-by-style' filter needs a style for filtering. ({self.job.get_indexed_location()})"
            )

        element_by_style = ElementsBy(FilterBy.ATTRIBUTE, 'style', subfilter['style'])
        element_by_style.feed(data)
        return element_by_style.get_html()


class ElementByTagFilter(FilterBase):
    """Get all HTML elements matching a tag."""

    __kind__ = 'element-by-tag'

    __supported_subfilters__ = {
        'tag': 'HTML tag name to filter for (required)',
    }

    __default_subfilter__ = 'tag'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        if 'tag' not in subfilter:
            raise ValueError(
                f"The 'element-by-tag' filter needs a tag for filtering. ({self.job.get_indexed_location()})"
            )

        element_by_tag = ElementsBy(FilterBy.TAG, subfilter['tag'])
        element_by_tag.feed(data)
        return element_by_tag.get_html()


class Sha1SumFilter(FilterBase):
    """Calculate the SHA-1 checksum of the content."""

    __kind__ = 'sha1sum'

    __no_subfilter__ = True

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        # Python 3.9: insert usedforsecurity=False argument in sha1() and remove nosec
        return hashlib.sha1(data).hexdigest()  # nosec B324: Use of weak MD4, MD5, or SHA1 hash for security.


class HexDumpFilter(FilterBase):
    """Convert string to hex dump format."""

    __kind__ = 'hexdump'

    __no_subfilter__ = True

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        data = bytearray(data)
        blocks = [data[i * 16 : (i + 1) * 16] for i in range(int((len(data) + (16 - 1)) / 16))]
        return '\n'.join(
            f"{' '.join(f'{c:02x}' for c in block):49}{''.join((chr(c) if (31 < c < 127) else '.') for c in block)}"
            for block in blocks
        )


class LxmlParser:
    EXPR_NAMES = {
        'css': 'a CSS selector',
        'xpath': 'an XPath expression',
    }

    expression: str
    method: str
    namespaces: Optional[Dict[str, str]]
    skip: int

    def __init__(
        self: Union['LxmlParser', 'CSSFilter', 'XPathFilter'],
        filter_kind: str,
        subfilter: Dict[str, Any],
        expr_key: str,
        job: JobBase,
    ) -> None:
        self.filter_kind = filter_kind
        self.method = subfilter.get('method', 'html')
        if self.method not in ('html', 'xml'):
            raise ValueError(
                f"The '{filter_kind}' filter's method must be 'html' or 'xml', got '{self.method}'. "
                f'({job.get_indexed_location()})'
            )
        if expr_key not in subfilter:
            raise ValueError(
                f"The '{filter_kind}' filter needs {self.EXPR_NAMES[filter_kind]} for filtering. "
                f'({job.get_indexed_location()})'
            )
        self.expression = subfilter[expr_key]
        self.exclude = subfilter.get('exclude')
        self.namespaces = subfilter.get('namespaces')
        self.skip = int(subfilter.get('skip', 0))
        self.maxitems = int(subfilter.get('maxitems', 0))
        if self.method == 'html' and self.namespaces:
            raise ValueError(
                f"The '{filter_kind}' filter's namespace prefixes are only supported with 'method: xml'. "
                f'({job.get_indexed_location()})'
            )
        self.parser = etree.HTMLParser() if self.method == 'html' else etree.XMLParser()  # etree._FeedParser
        self.data = ''

    def feed(self, data: str) -> None:
        self.data += data

    @staticmethod
    def _to_string(element: Union[etree.Element, str], method: str) -> str:
        # Handle "/text()" selector, which returns lxml.etree._ElementUnicodeResult
        # (https://github.com/thp/urlwatch/issues/282)
        if isinstance(element, str):
            return element

        return etree.tostring(element, encoding='unicode', method=method, pretty_print=True, with_tail=False).strip()

    @staticmethod
    def _remove_element(element: etree.Element) -> None:
        parent = element.getparent()
        if parent is None:
            # Do not exclude root element
            return
        if isinstance(element, etree._ElementUnicodeResult):
            if element.is_tail:
                parent.tail = None
            elif element.is_text:
                parent.text = None
            elif element.is_attribute:
                del parent.attrib[element.attrname]
        else:
            previous = element.getprevious()
            if element.tail is not None:
                if previous is not None:
                    previous.tail = previous.tail + element.tail if previous.tail else element.tail
                else:
                    parent.text = parent.text + element.tail if parent.text else element.tail
            parent.remove(element)

    def _reevaluate(self, element: etree.Element) -> Optional[Union[etree.Element, str]]:
        if self._orphaned(element):
            return None
        if isinstance(element, etree._ElementUnicodeResult):
            parent = element.getparent()
            if parent is None:
                return element
            if element.is_tail:
                return parent.tail
            elif element.is_text:
                return parent.text
            elif element.is_attribute:
                return parent.attrib.get(element.attrname)
            else:
                return element
        else:
            return element

    def _orphaned(self, element: etree.Element) -> bool:
        if isinstance(element, etree._ElementUnicodeResult):
            parent = element.getparent()
            if (
                (element.is_tail and parent.tail is None)
                or (element.is_text and parent.text is None)
                or (element.is_attribute and parent.attrib.get(element.attrname) is None)
            ):
                return True
            else:
                element = parent
        try:
            tree = element.getroottree()
            path = tree.getpath(element)
            return element is not tree.xpath(path, namespaces=self.namespaces)[0]
        except (ValueError, IndexError):
            return True

    def _get_filtered_elements(self) -> List[Union[etree.Element, str]]:
        if self.method == 'xml' and isinstance(self.data, str):
            # see https://lxml.de/FAQ.html#why-can-t-lxml-parse-my-xml-from-unicode-strings
            data: Union[str, bytes] = self.data.encode(errors='xmlcharrefreplace')
        elif self.method == 'html' and self.data.startswith('<?xml'):
            # handle legacy https://stackoverflow.com/questions/37592045/
            data = self.data.split('>', maxsplit=1)[1]
        else:
            data = self.data
        try:
            root = etree.fromstring(data, self.parser)  # nosec B320: use defusedxml TODO
        except ValueError as e:
            args = (
                f"Filter '{self.filter_kind}' encountered the following error when parsing the data. Check that "
                f"'method: {self.method}' is the correct one.\n    {type(e).__name__}: {e.args[0]}"
            )
            raise RuntimeError(args) from None
        if root is None:
            return []
        selected_elems: Optional[List[etree.Element]] = None
        excluded_elems: Optional[List[etree.Element]] = None
        if self.filter_kind == 'css':
            selected_elems = CSSSelector(self.expression, namespaces=self.namespaces).evaluate(root)
            excluded_elems = (
                CSSSelector(self.exclude, namespaces=self.namespaces).evaluate(root) if self.exclude else None
            )
        elif self.filter_kind == 'xpath':
            selected_elems = root.xpath(self.expression, namespaces=self.namespaces)
            excluded_elems = root.xpath(self.exclude, namespaces=self.namespaces) if self.exclude else None
        if excluded_elems is not None:
            for el in excluded_elems:
                self._remove_element(el)
        if selected_elems is not None:
            return [el for el in map(self._reevaluate, selected_elems) if el is not None]
        else:
            return []

    def get_filtered_data(self) -> str:
        elements = self._get_filtered_elements()
        if self.skip:
            elements = elements[self.skip :]
        if self.maxitems:
            elements = elements[: self.maxitems]
        return '\n'.join(self._to_string(element, self.method) for element in elements)


LXML_PARSER_COMMON_SUBFILTERS = {
    'method': 'The method (html or xml) used for parsing',
    'exclude': 'Elements to remove from the final result',
    'namespaces': 'Mapping of XML namespaces for matching',
    'skip': 'Number of elements to skip from the beginning (default: 0)',
    'maxitems': 'Maximum number of items to return (default: all)',
}


class CSSFilter(FilterBase):
    """Filter XML/HTML using CSS selectors."""

    __kind__ = 'css'

    __supported_subfilters__ = {
        'selector': 'The CSS selector to use for filtering (required)',
        **LXML_PARSER_COMMON_SUBFILTERS,
    }

    __default_subfilter__ = 'selector'

    EXPR_NAMES: Dict[str, str]
    expression: str
    exclude: str
    namespaces: Dict[str, str]
    skip: int
    maxitems: int

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        lxml_parser = LxmlParser('css', subfilter, 'selector', self.job)
        lxml_parser.feed(data)
        return lxml_parser.get_filtered_data()


class XPathFilter(FilterBase):
    """Filter XML/HTML using XPath expressions."""

    __kind__ = 'xpath'

    __supported_subfilters__ = {
        'path': 'The XPath to use for filtering (required)',
        **LXML_PARSER_COMMON_SUBFILTERS,
    }

    __default_subfilter__ = 'path'

    EXPR_NAMES: Dict[str, str]
    expression: str
    exclude: str
    namespaces: Dict[str, str]
    skip: int
    maxitems: int

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        lxml_parser = LxmlParser('xpath', subfilter, 'path', self.job)
        lxml_parser.feed(data)
        return lxml_parser.get_filtered_data()


class ReSubFilter(FilterBase):
    """Replace text with regular expressions using Python's re.sub."""

    __kind__ = 're.sub'

    __supported_subfilters__ = {
        'pattern': 'Regular expression to search for (required)',
        'repl': 'Replacement string (default: empty string)',
    }

    __default_subfilter__ = 'pattern'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> Union[str, bytes]:  # type: ignore[override]
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        if 'pattern' not in subfilter:
            raise ValueError(f"The 're.sub' filter needs a pattern. ({self.job.get_indexed_location()})")

        # Default: Replace with empty string if no "repl" value is set
        return re.sub(subfilter['pattern'], subfilter.get('repl', ''), data)


class SortFilter(FilterBase):
    """Sort input items."""

    __kind__ = 'sort'

    __supported_subfilters__ = {
        'reverse': 'Set to true to reverse sorting order',
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        reverse = isinstance(subfilter, dict) and subfilter.get('reverse', False) is True
        separator = subfilter.get('separator', '\n')
        return separator.join(sorted(data.split(separator), key=str.casefold, reverse=reverse))


class RemoveRepeatedFilter(FilterBase):
    """Remove repeated lines (uniq)."""

    __kind__ = 'remove_repeated'

    __supported_subfilters__ = {
        'separator': 'Item separator (default: newline)',
        'ignore_case': 'Ignore differences in case when comparing',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        separator = subfilter.get('separator', '\n')
        ignore_case = subfilter.get('ignore_case', False)
        data_lines = data.split(separator)
        uniq_lines = [data_lines[0]]
        if not ignore_case:
            for line in data_lines[1:]:
                if line not in uniq_lines[-1]:
                    uniq_lines.append(line)
        else:
            past_lines = [data_lines[0].strip().lower()]
            for line in data_lines[1:]:
                if line.strip().lower() not in past_lines[-1]:
                    past_lines.append(line.strip().lower())
                    uniq_lines.append(line)

        return separator.join(uniq_lines)


class RemoveDuplicateLinesFilter(FilterBase):
    """Remove duplicate lines (case sensitive)."""

    __kind__ = 'remove-duplicate-lines'

    __supported_subfilters__ = {
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        separator = subfilter.get('separator', '\n')
        data_lines = data.split(separator)

        def get_unique_lines(lines: List[str]) -> Iterator[str]:
            seen = set()
            for line in lines:
                if line not in seen:
                    yield line
                    seen.add(line)

        return separator.join(get_unique_lines(data_lines))


class ReverseFilter(FilterBase):
    """Reverse sort input items."""

    __kind__ = 'reverse'

    __supported_subfilters__ = {
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        separator = subfilter.get('separator', '\n')
        return separator.join(reversed(data.split(separator)))


def _pipe_filter(f_cls: FilterBase, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
    if 'command' not in subfilter:
        raise ValueError(f"The '{f_cls.__kind__}' filter needs a command. ({f_cls.job.get_indexed_location()})")

    # Work on a copy of the environment as not to modify the outside environment
    env = os.environ.copy()
    env.update(
        {
            f'{__project_name__.upper()}_JOB_JSON': json.dumps(f_cls.job.to_dict()),
            f'{__project_name__.upper()}_JOB_NAME': f_cls.job.pretty_name(),
            f'{__project_name__.upper()}_JOB_LOCATION': f_cls.job.get_location(),
            f'{__project_name__.upper()}_JOB_INDEX_NUMBER': str(f_cls.job.index_number),
            'URLWATCH_JOB_NAME': f_cls.job.pretty_name(),  # urlwatch 2 compatibility
            'URLWATCH_JOB_LOCATION': f_cls.job.get_location(),  # urlwatch 2 compatibility
        }
    )

    if f_cls.__kind__ == 'execute':
        command = shlex.split(subfilter['command'])
        shell = False
    else:  # 'shellpipe'
        command = subfilter['command']
        shell = True

    try:
        return subprocess.run(  # nosec: B602
            command,
            input=data,
            capture_output=True,
            shell=shell,
            check=True,
            text=True,
            env=env,
        ).stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"The '{f_cls.__kind__}' filter returned error ({f_cls.job.get_indexed_location()}):\n{e.stderr}")
        raise e
    except FileNotFoundError as e:
        logger.error(f"The '{f_cls.__kind__}' filter returned error ({f_cls.job.get_indexed_location()}):\n{e}")
        raise FileNotFoundError(e, f'with command {command}') from None


class ExecuteFilter(FilterBase):
    """Filter using a command."""

    __kind__ = 'execute'

    __supported_subfilters__ = {
        'command': 'Command to execute for filtering (required)',
    }

    __default_subfilter__ = 'command'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        return _pipe_filter(self, data, subfilter)


class ShellPipeFilter(FilterBase):
    """Filter using a shell command."""

    __kind__ = 'shellpipe'

    __supported_subfilters__ = {
        'command': 'Shell command to execute for filtering (required)',
    }

    __default_subfilter__ = 'command'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        return _pipe_filter(self, data, subfilter)


class OCRFilter(FilterBase):  # pragma: has-pytesseract
    """Convert text in images to plaintext (requires Python packages ``pytesseract`` and ``Pillow``)."""

    __kind__ = 'ocr'
    __uses_bytes__ = True

    __supported_subfilters__ = {
        'language': 'Language of the text (e.g. "fra" or "eng+fra")',
        'timeout': 'Timeout (in seconds) for OCR (default 10 seconds)',
    }

    def filter(self, data: bytes, subfilter: Dict[str, Any]) -> str:  # type: ignore[override]
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        if not isinstance(data, bytes):
            raise ValueError(
                f"The 'ocr' filter needs bytes input (is it the first filter?). ({self.job.get_indexed_location()})"
            )

        language = subfilter.get('language', None)
        timeout = int(subfilter.get('timeout', 10))

        if pytesseract is None:
            raise ImportError(
                f"Python package 'pytesseract' is not installed; cannot use the '{self.__kind__}' filter. "
                f'({self.job.get_indexed_location()})'
            )

        if Image is None:
            raise ImportError(
                f"Python package 'Pillow' is not installed; cannot use the '{self.__kind__}' filter. "
                f'({self.job.get_indexed_location()})'
            )

        return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=language, timeout=timeout).strip()


class JQFilter(FilterBase):  # pragma: has-jq
    """Parse, transform, and extract data from json as text using `jq`."""

    # contributed by robgmills https://github.com/thp/urlwatch/pull/626

    __kind__ = 'jq'

    __supported_subfilters__ = {
        'query': 'jq query function to execute on data',
    }

    __default_subfilter__ = 'query'

    def filter(self, data: Union[str, bytes], subfilter: Dict[str, Any]) -> str:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The filtered (processed) data.
        """
        if 'query' not in subfilter:
            raise ValueError(f"The 'jq' filter needs a query. ({self.job.get_indexed_location()})")
        try:
            jsondata = json.loads(data)
        except ValueError:
            raise ValueError(f"The 'jq' filter needs valid JSON. ({self.job.get_indexed_location()})")

        if jq is None:
            raise ImportError(
                f"Python package 'jq' is not installed; cannot use the '{self.__kind__}' filter. "
                f'({self.job.get_indexed_location()})'
            )

        return jq.text(subfilter['query'], jsondata)
        # Unicode solution is below https://github.com/mwilliamson/jq.py/issues/59
        # however it aborts execution(!) during testing
        # return '\n'.join(json.dumps(v, ensure_ascii=False) for v in (jq.compile(subfilter['query'], jsondata)))
