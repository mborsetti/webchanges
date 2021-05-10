"""Filters."""

import hashlib
import io
import itertools
import json
import logging
import os
import re
import subprocess
import sys
import warnings
from abc import ABC
from enum import Enum
from html.parser import HTMLParser
from typing import Any, AnyStr, Dict, Iterator, List, Optional, TYPE_CHECKING, Tuple, Union
from xml.dom import minidom

import html2text
import yaml
from lxml import etree  # noqa: DUO107 insecure use of XML modules, prefer "defusedxml"
from lxml.cssselect import CSSSelector  # noqa: DUO107 insecure use of XML modules, prefer "defusedxml"

from .util import TrackSubClasses

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from .handler import JobState
    from .jobs import JobBase

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import cssbeautifier
except ImportError:
    cssbeautifier = None

try:
    import jq
except ImportError:
    jq = None

try:
    import jsbeautifier
except ImportError:
    jsbeautifier = None

try:
    import pdftotext
except ImportError:
    pdftotext = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import vobject
except ImportError:
    vobject = None


logger = logging.getLogger(__name__)


class FilterBase(object, metaclass=TrackSubClasses):
    __subclasses__ = {}
    __anonymous_subclasses__ = []

    def __init__(self, job: 'JobBase', state: 'JobState') -> None:
        self.job = job
        self.state = state

    @classmethod
    def filter_documentation(cls) -> str:
        result = []
        for sc in TrackSubClasses.sorted_by_kind(cls):
            default_subfilter = getattr(sc, '__default_subfilter__', None)
            result.extend((f'  * {sc.__kind__} - {sc.__doc__}',))
            if hasattr(sc, '__supported_subfilters__'):
                for key, doc in sc.__supported_subfilters__.items():
                    result.append('      %s%s%s ... %s' % ('[' if key == default_subfilter else '', key,
                                                           ']' if key == default_subfilter else '', doc))
        result.append('\n[] ... Parameter can be supplied as unnamed value\n')
        return '\n'.join(result)

    @classmethod
    def auto_process(cls, state: 'JobState', data: AnyStr) -> str:
        filters = itertools.chain((filtercls for _, filtercls in
                                   sorted(cls.__subclasses__.items(), key=lambda k_v: k_v[0])),
                                  cls.__anonymous_subclasses__)

        for filtercls in filters:
            filter_instance = filtercls(state.job, state)
            if filter_instance.match():
                logger.info(f'Job {state.job.index_number}: Auto-applying filter {filter_instance}')
                data = filter_instance.filter(data, None)  # all filters take a subfilter

        return data

    @classmethod
    def normalize_filter_list(cls, filter_spec: Union[str, List[Union[str, Dict[str, Any]]]]
                              ) -> Iterator[Union[str, Union[str, dict]]]:
        for filter_kind, subfilter in cls._internal_normalize_filter_list(filter_spec):
            filtercls = cls.__subclasses__.get(filter_kind, None)

            if filtercls is None:
                raise ValueError(f'Unknown filter kind: {filter_kind} (subfilter {subfilter})')

            if getattr(filtercls, '__no_subfilter__', False) and subfilter:
                raise ValueError(f'No subfilters supported for {filter_kind}')

            if hasattr(filtercls, '__supported_subfilters__'):
                provided_keys = set(subfilter.keys())
                allowed_keys = set(filtercls.__supported_subfilters__.keys())
                unknown_keys = provided_keys.difference(allowed_keys)
                if unknown_keys and '<any>' not in allowed_keys:
                    raise ValueError(f'Filter {filter_kind} does not support subfilter(s): {unknown_keys} '
                                     f'(supported: {allowed_keys})')

            yield filter_kind, subfilter

    @classmethod
    def _internal_normalize_filter_list(cls, filter_spec: Union[str, List[Union[str, Dict[str, Any]]]]
                                        ) -> Iterator[Tuple[str, Union[str, Dict[str, Any]]]]:
        if isinstance(filter_spec, str):
            old_filter_spec = filter_spec

            # Legacy string-based filter list specification:
            # "filter1:param1,filter2,filter3,filter4:param4"
            filter_spec = [{filter_kind.split(':', 1)} if ':' in filter_kind else filter_kind
                           for filter_kind in old_filter_spec.split(',')]
            warnings.warn(
                f'String-based filter definitions ({old_filter_spec}) are deprecated, please convert to dict-style:\n\n'
                f'{yaml.safe_dump(filter_spec, default_flow_style=False, allow_unicode=True)}', DeprecationWarning)

        if isinstance(filter_spec, list):
            for item in filter_spec:
                if isinstance(item, str):
                    filter_kind, subfilter = item, None
                elif isinstance(item, dict):
                    filter_kind, subfilter = next(iter(item.items()))
                else:
                    raise ValueError('Subfilter(s) must be a string or a dictionary')

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
    def process(cls, filter_kind: str, subfilter: Dict[str, Any], state: 'JobState',
                data: AnyStr) -> AnyStr:
        logger.info(f'Job {state.job.index_number}: Applying filter {filter_kind}, subfilter {subfilter}')
        filtercls = cls.__subclasses__.get(filter_kind, None)
        return filtercls(state.job, state).filter(data, subfilter)

    @classmethod
    def filter_chain_needs_bytes(cls, filter_name: Union[str, List[Union[str, Dict[str, Any]]]]) -> bool:
        """Returns True if the first filter requires data in bytes (not Unicode)."""
        first_filter = next(cls.normalize_filter_list(filter_name), None)
        if first_filter is not None:
            filter_kind, subfilter = first_filter
            return cls.is_bytes_filter_kind(filter_kind)

        return False

    @classmethod
    def is_bytes_filter_kind(cls, filter_kind: str) -> bool:
        return (filter_kind in (name for name, class_ in cls.__subclasses__.items()
                                if getattr(class_, '__uses_bytes__', False)))

    def match(self) -> bool:
        return False

    def filter(self, data: str, subfilter: Dict[str, Any]) -> None:
        raise NotImplementedError()


class AutoMatchFilter(FilterBase):
    """Automatically matches subclass filters with a given location."""
    MATCH = None

    def match(self) -> bool:
        if self.MATCH is None:
            return False

        d = self.job.to_dict()
        result = all(d.get(k, None) == v for k, v in self.MATCH.items())
        logger.debug(f'Matching {self} with {self.job} result: {result}')
        return result

    def filter(self, data: str, subfilter: Dict[str, Any]) -> None:
        pass


class RegexMatchFilter(FilterBase):
    """Same as AutoMatchFilter but matching is done with regexes."""
    MATCH = None

    def match(self) -> bool:
        if self.MATCH is None:
            return False

        d = self.job.to_dict()

        # It's a match if we have at least one key/value pair that matches,
        # and no key/value pairs that do not match
        matches = [v.match(d[k]) for k, v in self.MATCH.items() if k in d]
        result = len(matches) > 0 and all(matches)
        logger.debug(f'Matching {self} with {self.job} result: {result}')
        return result

    def filter(self, data: str, subfilter: Dict[str, Any]) -> None:
        pass


class BeautifyFilter(FilterBase):
    """Beautify HTML (requires Python package 'BeautifulSoup' and optionally 'jsbeautifier' and/or 'cssbeautifier')."""

    __kind__ = 'beautify'

    __no_subfilter__ = True

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        if BeautifulSoup is None:
            raise ImportError(f"Python package 'BeautifulSoup' is not installed; cannot use the '{self.__kind__}' "
                              f'filter ({self.job.get_indexed_location()})')

        soup = BeautifulSoup(data, features='lxml')

        if jsbeautifier is None:
            logger.info(f"Python package 'jsbeautifier' is not installed; will not beautify <script> tags"
                        f' ({self.job.get_indexed_location()})')
        else:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    beautified_js = jsbeautifier.beautify(script.string)
                    script.string = beautified_js

        if cssbeautifier is None:
            logger.info("Python package 'cssbeautifier' is not installed; will not beautify <style> tags"
                        f' ({self.job.get_indexed_location()})')
        else:
            styles = soup.find_all('style')
            for style in styles:
                if style.string:
                    beautified_css = cssbeautifier.beautify(style.string)
                    style.string = beautified_css

        return soup.prettify()


class Html2TextFilter(FilterBase):
    """Convert HTML to Markdown text."""

    __kind__ = 'html2text'

    __supported_subfilters__ = {
        'method': 'Method to use for conversion (html2text [default], bs4, or strip_tags)',
        '<any>': 'Method-specific options passed to html2text',
    }

    __default_subfilter__ = 'method'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        """
        Convert a string consisting of HTML to plain text for easy difference checking.
        Method may be one of:
        'html2text' (DEFAULT): Use html2text library to extract text (in Markdown) from html.
        - options: https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options
        - default options optimized as follows: parser.unicode_snob = True,
        parser.body_width = 0, parser.single_line_break = True, parser.ignore_images = True
        'bs4': Use Beautiful Soup library to prettify the HTML
        - options: "parser" only, bs4 supports "lxml", "html5lib", and "html.parser"
        - https://www.crummy.com/software/BeautifulSoup/bs4/doc/#specifying-the-parser-to-use
        'strip_tags': A simple regex-based HTML tag stripper
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
                warnings.warn(f"filter html2text's method 'pyhtml2text' is deprecated: remove method as it's now the "
                              f"filter's default) ({self.job.get_indexed_location()})", DeprecationWarning)
            self.job.is_markdown = True

            parser = html2text.HTML2Text()
            parser.unicode_snob = True
            parser.body_width = 0
            parser.single_line_break = True
            parser.ignore_images = True
            if hasattr(self.job, 'url'):
                parser.baseurl = self.job.url
            for k, v in options.items():
                setattr(parser, k.lower(), v)
                if k == 'pad_tables':
                    self.job.markdown_padded_tables = v

            return parser.handle(data)

        elif method == 'bs4':
            if BeautifulSoup is None:
                raise ImportError(f"Python package 'BeautifulSoup' is not installed; cannot use the '{self.__kind__}: "
                                  f"{method}' filter ({self.job.get_indexed_location()})")

            parser = options.pop('parser', 'lxml')
            soup = BeautifulSoup(data, parser)
            return soup.get_text(strip=True)

        elif method in ('strip_tags', 're'):  # re for backward compatibility
            if method == 're':
                warnings.warn(f"filter html2text's method 're' is deprecated: replace with 'strip_tags' "
                              f'({self.job.get_indexed_location()})', DeprecationWarning)
            stripped_tags = re.sub(r'<[^>]*>', '', data)
            return '\n'.join((line.rstrip() for line in stripped_tags.splitlines() if line.strip() != ''))

        elif method == 'lynx':
            logger.error(f"'filter html2text's method 'lynx' is no longer supported; use the 'html2text' filter instead"
                         f' ({self.job.get_indexed_location()})')

        else:
            raise ValueError(f'Unknown filter html2text method: {method} ({self.job.get_indexed_location()})')


class Pdf2TextFilter(FilterBase):
    """Convert PDF to plaintext (requires Python package 'pdftotext' and its dependencies)."""
    # Dependency: pdftotext (https://github.com/jalan/pdftotext), itself based
    # on poppler (https://poppler.freedesktop.org/)
    # Note: check pdftotext website for OS-specific dependencies for install

    __kind__ = 'pdf2text'
    __uses_bytes__ = True  # Requires data to be in bytes (not unicode)

    __supported_subfilters__ = {
        'password': 'PDF password for decryption',
    }

    def filter(self, data: bytes, subfilter: Dict[str, Any]) -> str:
        if pdftotext is None:
            raise ImportError(f"Python package 'pdftotext' (and OS-specific dependencies) is not installed; cannot use"
                              f" 'html2text: pdf2text' filter ({self.job.get_indexed_location()})")

        # data must be bytes
        if not isinstance(data, bytes):
            raise ValueError(f"The 'html2text: pdf2text' filter needs bytes input (is it the first filter?)"
                             f' ({self.job.get_indexed_location()})')

        return '\n\n'.join(pdftotext.PDF(io.BytesIO(data), password=subfilter.get('password', '')))


class Ical2TextFilter(FilterBase):
    """Convert iCalendar to plaintext (requires Python package 'vobject')."""

    __kind__ = 'ical2text'

    __no_subfilter__ = True

    def filter(self, data: AnyStr, subfilter: Dict[str, Any]) -> str:
        if vobject is None:
            raise ImportError(f"Python package 'vobject' is not installed; cannot use 'html2text: ical2text' filter"
                              f' ({self.job.get_indexed_location()})')

        result = []
        if isinstance(data, str):
            parsedCal = vobject.readOne(data)
        else:
            try:
                parsedCal = vobject.readOne(data)
            except vobject.ParseError:
                parsedCal = vobject.readOne(data.decode(errors='ignore'))

        for event in parsedCal.getChildren():
            if event.name == 'VEVENT':
                if hasattr(event, 'dtstart'):
                    start = event.dtstart.value.strftime('%F %H:%M')
                else:
                    start = 'unknown start date'

                if hasattr(event, 'dtend'):
                    end = event.dtend.value.strftime('%F %H:%M')
                else:
                    end = start

                if start == end:
                    date_str = start
                else:
                    date_str = f'{start} -- {end}'

                result.append(f'{date_str}: {event.summary.value}')

        return '\n'.join(result)


class JsonFormatFilter(FilterBase):
    """Convert to formatted JSON."""

    __kind__ = 'format-json'

    __supported_subfilters__ = {
        'indentation': 'Indentation level for pretty-printing',
        'sort_keys': 'Sort the output of dictionaries by key',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        sort_keys = subfilter.get('sort_keys', False)
        indentation = int(subfilter.get('indentation', 4))
        parsed_json = json.loads(data)
        return json.dumps(parsed_json, ensure_ascii=False, sort_keys=sort_keys, indent=indentation,
                          separators=(',', ': '))


class XMLFormatFilter(FilterBase):
    """Convert to formatted XML using lxml.etree."""

    __kind__ = 'format-xml'

    __no_subfilter__ = True

    # __supported_subfilters__ = {
    #     'indentation': 'Indentation level for pretty-printing',
    # }
    #
    # __default_subfilter__ = 'indentation'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        parsed_xml = etree.XML(data)
        return etree.tostring(parsed_xml, encoding='unicode', pretty_print=True)


class PrettyXMLFilter(FilterBase):
    """Pretty-print XML using built-in xml.minidom."""

    __kind__ = 'pretty-xml'

    __supported_subfilters__ = {
        'indentation': 'Indentation level for pretty-printing',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data, subfilter):
        indentation = int(subfilter.get('indentation', 2))
        return minidom.parseString(data).toprettyxml(indent=' ' * indentation)


class KeepLinesFilter(FilterBase):
    """Filter only lines matching a regular expression."""

    __kind__ = 'keep_lines_containing'

    __supported_subfilters__ = {
        'text': 'Lines matching this text are kept (default)',
        're': 'Lines matching this expression are kept',
    }

    __default_subfilter__ = 'text'

    def filter(self: Union['KeepLinesFilter', 'GrepFilter'], data: str, subfilter: Dict[str, Any]) -> str:
        if 'text' in subfilter:
            return '\n'.join(line for line in data.splitlines() if subfilter['text'] in line)
        if 're' in subfilter:
            return '\n'.join(line for line in data.splitlines() if re.search(subfilter['re'], line))
        else:
            raise ValueError(f'The keep_lines_containing filter needs a text or re expression'
                             f' ({self.job.get_indexed_location()})')


class GrepFilter(FilterBase):
    """Deprecated; use keep_lines_containing instead."""

    __kind__ = 'grep'

    __supported_subfilters__ = {
        're': 'Lines matching this expression are kept (required)',
    }

    __default_subfilter__ = 're'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        warnings.warn(f"'grep' filter is deprecated; replace with 'keep_lines_containing' (+ 're' subfilter)"
                      f' ({self.job.get_indexed_location()})', DeprecationWarning)
        return KeepLinesFilter.filter(self, data, subfilter)


class DeleteLinesFilter(FilterBase):
    """Remove lines matching a regular expression."""

    __kind__ = 'delete_lines_containing'

    __supported_subfilters__ = {
        'text': 'Lines matching this text are deleted (default)',
        're': 'Lines matching this expression deleted kept',
    }

    __default_subfilter__ = 'text'

    def filter(self: Union['DeleteLinesFilter', 'InverseGrepFilter'], data: str, subfilter: Dict[str, Any]) -> str:
        if 'text' in subfilter:
            return '\n'.join(line for line in data.splitlines() if subfilter['text'] not in line)
        if 're' in subfilter:
            return '\n'.join(line for line in data.splitlines() if re.search(subfilter['re'], line) is None)
        else:
            raise ValueError(f'The delete_lines_containing filter needs a text or re expression'
                             f' ({self.job.get_indexed_location()})')


class InverseGrepFilter(FilterBase):
    """Deprecated; use delete_lines_containing instead."""

    __kind__ = 'grepi'

    __supported_subfilters__ = {
        're': 'Lines matching this expression are removed (required)',
    }

    __default_subfilter__ = 're'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        warnings.warn(f"'grepi' filter is deprecated; replace with 'delete_lines_containing (+ 're' subfilter')"
                      f' ({self.job.get_indexed_location()})', DeprecationWarning)
        return DeleteLinesFilter.filter(self, data, subfilter)


class StripFilter(FilterBase):
    """Strip leading and trailing whitespace."""

    __kind__ = 'strip'

    __supported_subfilters__ = {
        'splitlines': 'Apply the filter on each line of text (default: false, apply to the entire data)',
        'chars': 'String specifying the set of characters to be removed. If omitted, defaults to removing whitespace',
        'side': "One-sided removal: either 'left' (leading characters) or 'right' (trailing characters)"
    }

    __default_subfilter__ = 'chars'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        if subfilter.get('splitlines'):

            data = data.splitlines()

            if 'side' in subfilter:
                if subfilter['side'] == 'right':
                    return '\n'.join([line.rstrip(subfilter.get('chars')) for line in data])
                if subfilter['side'] == 'left':
                    return '\n'.join([line.lstrip(subfilter.get('chars')) for line in data])

                raise ValueError(f"The strip filter's 'side' sub-directive can only be 'right' or 'left' "
                                 f'({self.job.get_indexed_location()})')

            return '\n'.join([line.strip(subfilter.get('chars')) for line in data])

        else:
            if 'side' in subfilter:
                if subfilter['side'] == 'right':
                    return data.rstrip(subfilter.get('chars'))
                if subfilter['side'] == 'left':
                    return data.lstrip(subfilter.get('chars'))

                raise ValueError(f"The strip filter's 'side' sub-directive can only be 'right' or 'left' "
                                 f'({self.job.get_indexed_location()})')

            return data.strip(subfilter.get('chars'))


class StripEachLineFilter(FilterBase):
    """Strip leading and trailing whitespace from each line."""

    __kind__ = 'strip_each_line'

    __no_subfilter__ = True

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        warnings.warn(f"'strip_each_line' filter is deprecated; replace with 'strip' and sub-directive 'splitlines: "
                      f"true' ({self.job.get_indexed_location()})", DeprecationWarning)
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

        self._result = []
        self._inside = False
        self._elts = []

    def get_html(self) -> str:
        return ''.join(self._result)

    def handle_starttag(self, tag: str, attrs: Optional[List[Tuple[str, str]]]) -> None:
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


class GetElementById(FilterBase):
    """Get an HTML element by its ID."""

    __kind__ = 'element-by-id'

    __supported_subfilters__ = {
        'id': 'ID of the element to filter for (required)',
    }

    __default_subfilter__ = 'id'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        if 'id' not in subfilter:
            raise ValueError(f'The element-by-id filter needs an id for filtering ({self.job.get_indexed_location()})')

        element_by_id = ElementsBy(FilterBy.ATTRIBUTE, 'id', subfilter['id'])
        element_by_id.feed(data)
        return element_by_id.get_html()


class GetElementByClass(FilterBase):
    """Get all HTML elements by class."""

    __kind__ = 'element-by-class'

    __supported_subfilters__ = {
        'class': 'HTML class attribute to filter for (required)',
    }

    __default_subfilter__ = 'class'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        if 'class' not in subfilter:
            raise ValueError(f'The element-by-class filter needs a class for filtering '
                             f'({self.job.get_indexed_location()})')

        element_by_class = ElementsBy(FilterBy.ATTRIBUTE, 'class', subfilter['class'])
        element_by_class.feed(data)
        return element_by_class.get_html()


class GetElementByStyle(FilterBase):
    """Get all HTML elements by style."""

    __kind__ = 'element-by-style'

    __supported_subfilters__ = {
        'style': 'HTML style attribute value to filter for (required)',
    }

    __default_subfilter__ = 'style'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        if 'style' not in subfilter:
            raise ValueError(f'The element-by-style filter needs a style for filtering '
                             f'({self.job.get_indexed_location()})')

        element_by_style = ElementsBy(FilterBy.ATTRIBUTE, 'style', subfilter['style'])
        element_by_style.feed(data)
        return element_by_style.get_html()


class GetElementByTag(FilterBase):
    """Get an HTML element by its tag"""

    __kind__ = 'element-by-tag'

    __supported_subfilters__ = {
        'tag': 'HTML tag name to filter for (required)',
    }

    __default_subfilter__ = 'tag'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        if 'tag' not in subfilter:
            raise ValueError(f'The element-by-tag filter needs a tag for filtering ({self.job.get_indexed_location()})')

        element_by_tag = ElementsBy(FilterBy.TAG, subfilter['tag'])
        element_by_tag.feed(data)
        return element_by_tag.get_html()


class Sha1Filter(FilterBase):
    """Calculate the SHA-1 checksum of the content."""

    __kind__ = 'sha1sum'

    __no_subfilter__ = True

    def filter(self, data: AnyStr, subfilter: Dict[str, Any]) -> str:
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        return hashlib.sha1(data).hexdigest()  # noqa: DUO130 insecure use of "hashlib" module


class HexdumpFilter(FilterBase):
    """Convert string to hex dump format."""

    __kind__ = 'hexdump'

    __no_subfilter__ = True

    def filter(self, data: AnyStr, subfilter: Dict[str, Any]) -> str:
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        data = bytearray(data)
        blocks = [data[i * 16:(i + 1) * 16] for i in range(int((len(data) + (16 - 1)) / 16))]
        return '\n'.join(f"{' '.join(f'{c:02x}' for c in block):49}"
                         f"{''.join((chr(c) if (31 < c < 127) else '.') for c in block)}" for block in blocks)


class LxmlParser:
    EXPR_NAMES = {'css': 'a CSS selector',
                  'xpath': 'an XPath expression'}

    def __init__(self: Union['LxmlParser', 'CssFilter', 'XPathFilter'], filter_kind: str, subfilter: Dict[str, Any],
                 expr_key: str) -> None:
        self.filter_kind = filter_kind
        if expr_key not in subfilter:
            raise ValueError(f'The {filter_kind} filter needs {self.EXPR_NAMES[filter_kind]} for filtering'
                             f' ({self.job.get_indexed_location()})')
        self.expression = subfilter[expr_key]
        self.method = subfilter.get('method', 'html')
        self.exclude = subfilter.get('exclude')
        self.namespaces = subfilter.get('namespaces')
        self.skip = int(subfilter.get('skip', 0))
        self.maxitems = int(subfilter.get('maxitems', 0))
        if self.method not in ('html', 'xml'):
            raise ValueError(f"The {filter_kind} filter's method must be 'html' or 'xml', got {self.method}"
                             f' ({self.job.get_indexed_location()})')
        if self.method == 'html' and self.namespaces:
            raise ValueError(f"Namespace prefixes only supported with 'xml' method"
                             f' ({self.job.get_indexed_location()})')
        self.parser = (etree.HTMLParser if self.method == 'html' else etree.XMLParser)()
        self.data = ''

    def feed(self, data: str) -> None:
        self.data += data

    @staticmethod
    def _to_string(element: Union[etree.Element, str]) -> str:
        # Handle "/text()" selector, which returns lxml.etree._ElementUnicodeResult (Issue #282)
        if isinstance(element, str):
            return element

        return etree.tostring(element, pretty_print=True, encoding='unicode', with_tail=False).strip()

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

    def _reevaluate(self, element: etree.Element) -> etree.Element:
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

    def _orphaned(self, element: etree.Element) -> Union[etree.Element, bool]:
        if isinstance(element, etree._ElementUnicodeResult):
            parent = element.getparent()
            if ((element.is_tail and parent.tail is None)
                    or (element.is_text and parent.text is None)
                    or (element.is_attribute and parent.attrib.get(element.attrname) is None)):
                return True
            else:
                element = parent
        try:
            tree = element.getroottree()
            path = tree.getpath(element)
            return element is not tree.xpath(path, namespaces=self.namespaces)[0]
        except (ValueError, IndexError):
            return True

    def _get_filtered_elements(self) -> List[etree.Element]:
        try:
            root = etree.fromstring(self.data, self.parser)
        except ValueError:
            # Strip XML declaration, for example: '<?xml version="1.0" encoding="utf-8"?>'
            # for https://heronebag.com/blog/index.xml, an error happens, as we get a
            # a (Unicode) string, but the XML contains its own "encoding" declaration
            self.data = re.sub(r'^<[?]xml[^>]*[?]>', '', self.data)
            # Retry parsing with XML declaration removed (Fixes #281)
            root = etree.fromstring(self.data, self.parser)
        if root is None:
            return []
        selected_elems = None
        excluded_elems = None
        if self.filter_kind == 'css':
            selected_elems = CSSSelector(self.expression, namespaces=self.namespaces).evaluate(root)
            excluded_elems = CSSSelector(self.exclude,
                                         namespaces=self.namespaces).evaluate(root) if self.exclude else None
        elif self.filter_kind == 'xpath':
            selected_elems = root.xpath(self.expression, namespaces=self.namespaces)
            excluded_elems = root.xpath(self.exclude, namespaces=self.namespaces) if self.exclude else None
        if excluded_elems is not None:
            for el in excluded_elems:
                self._remove_element(el)
        return [el for el in map(self._reevaluate, selected_elems) if el is not None]

    def get_filtered_data(self) -> str:
        elements = list(self._get_filtered_elements())
        if self.skip:
            elements = elements[self.skip:]
        if self.maxitems:
            elements = elements[:self.maxitems]
        return '\n'.join(self._to_string(element) for element in elements)


LXML_PARSER_COMMON_SUBFILTERS = {
    'method': 'The method (html or xml) used for parsing',
    'exclude': 'Elements to remove from the final result',
    'namespaces': 'Mapping of XML namespaces for matching',
    'skip': 'Number of elements to skip from the beginning (default: 0)',
    'maxitems': 'Maximum number of items to return (default: all)',
}


class CssFilter(FilterBase):
    """Filter XML/HTML using CSS selectors."""

    __kind__ = 'css'

    __supported_subfilters__ = {
        'selector': 'The CSS selector to use for filtering (required)',
        **LXML_PARSER_COMMON_SUBFILTERS,
    }

    __default_subfilter__ = 'selector'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        lxml_parser = LxmlParser('css', subfilter, 'selector')
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

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        lxml_parser = LxmlParser('xpath', subfilter, 'path')
        lxml_parser.feed(data)
        return lxml_parser.get_filtered_data()


class RegexSub(FilterBase):
    """Replace text with regular expressions using Python's re.sub."""

    __kind__ = 're.sub'

    __supported_subfilters__ = {
        'pattern': 'Regular expression to search for (required)',
        'repl': 'Replacement string (default: empty string)',
    }

    __default_subfilter__ = 'pattern'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        if 'pattern' not in subfilter:
            raise ValueError(f'The re.sub filter needs a pattern ({self.job.get_indexed_location()})')

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

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        reverse = (isinstance(subfilter, dict) and subfilter.get('reverse', False) is True)
        separator = subfilter.get('separator', '\n')
        return separator.join(sorted(data.split(separator), key=str.casefold, reverse=reverse))


class ReverseFilter(FilterBase):
    """Reverse sort input items."""

    __kind__ = 'reverse'

    __supported_subfilters__ = {
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        separator = subfilter.get('separator', '\n')
        return separator.join(reversed(data.split(separator)))


class ShellPipeFilter(FilterBase):
    """Filter using a shell command."""

    __kind__ = 'shellpipe'

    __supported_subfilters__ = {
        'command': 'Shell command to execute for filtering (required)',
    }

    __default_subfilter__ = 'command'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:
        if 'command' not in subfilter:
            raise ValueError(f'The shellpipe filter needs a command ({self.job.get_indexed_location()})')

        encoding = sys.getdefaultencoding()

        # Work on a copy to not modify the outside environment
        env = dict(os.environ)
        env.update({
            'URLWATCH_JOB_NAME': self.job.pretty_name() if self.job else '',
            'URLWATCH_JOB_LOCATION': self.job.get_location() if self.job else '',
        })

        try:
            return subprocess.run(subfilter['command'], input=data.encode(encoding), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, shell=True, check=True,
                                  env=env).stdout.decode(encoding)  # noqa: DUO116 use of "shell=True" is insecure
        # Python 3.7
        # return subprocess.run(subfilter['command'], input=data.encode(encoding), capture_output=True,
        #                       shell=True, check=True,
        #                       env=env).stdout.decode(encoding)  # noqa: DUO116 use of "shell=True" is insecure
        except subprocess.CalledProcessError as e:
            logger.error(f"filter 'shellpipe' returned error ({self.job.get_indexed_location()}):")
            logger.error(e.stderr.decode())
            raise e


class OCRFilter(FilterBase):
    """Convert text in images to plaintext (requires Python packages 'pytesseract' and 'Pillow')."""

    __kind__ = 'ocr'
    __uses_bytes__ = True

    __supported_subfilters__ = {
        'language': 'Language of the text (e.g. "fra" or "eng+fra")',
        'timeout': 'Timeout (in seconds) for OCR (default 10 seconds)',
    }

    def filter(self, data: bytes, subfilter: Dict[str, Any]) -> str:
        if not isinstance(data, bytes):
            raise ValueError(f'The ocr filter needs bytes input (is it the first filter?)'
                             f' ({self.job.get_indexed_location()})')

        language = subfilter.get('language', None)
        timeout = int(subfilter.get('timeout', 10))

        if pytesseract is None:
            raise ImportError(f"Python package 'pytesseract' is not installed; cannot use the '{self.__kind__}' filter"
                              f' ({self.job.get_indexed_location()})')

        if Image is None:
            raise ImportError(f"Python package 'Pillow' is not installed; cannot use the '{self.__kind__}' filter"
                              f' ({self.job.get_indexed_location()})')

        return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=language, timeout=timeout).strip()


class JQFilter(FilterBase):
    """Parse, transform, and extract data from json as text using `jq`."""
    # contributed by robgmills https://github.com/thp/urlwatch/pull/626

    __kind__ = 'jq'

    __supported_subfilters__ = {
        'query': 'jq query function to execute on data',
    }

    __default_subfilter__ = 'query'

    def filter(self, data: str, subfilter: Dict[str, Any]) -> str:

        if jq is None:
            raise ImportError(f"Python package 'jq' is not installed; cannot use the '{self.__kind__}' filter"
                              f' ({self.job.get_indexed_location()})')

        try:
            jsondata = json.loads(data)
        except ValueError:
            raise ValueError(f'The jq filter needs valid JSON ({self.job.get_indexed_location()})')

        if 'query' not in subfilter:
            raise ValueError(f'The jq filter needs a query ({self.job.get_indexed_location()})')

        return jq.text(subfilter['query'], jsondata)
        # Unicode solution is below https://github.com/mwilliamson/jq.py/issues/59
        # however it aborts execution(!) during testing
        # return '\n'.join(json.dumps(v, ensure_ascii=False) for v in (jq.compile(subfilter['query'], jsondata)))
