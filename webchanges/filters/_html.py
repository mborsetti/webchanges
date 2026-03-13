"""HTML/XML/CSS/XPath filters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import html
import importlib.util
import logging
import re
import warnings
from abc import ABC
from enum import Enum
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin
from xml.dom import minidom

import html2text
from lxml import etree
from lxml.cssselect import CSSSelector

from webchanges.filters._base import AutoMatchFilter, FilterBase, RegexMatchFilter

if TYPE_CHECKING:
    from webchanges.jobs import JobBase

try:
    import bs4
except ImportError as e:  # pragma: has-bs4
    bs4 = str(e)  # type: ignore[assignment]

try:
    import cssbeautifier
except ImportError as e:  # pragma: no cover
    cssbeautifier = str(e)  # ty:ignore[invalid-assignment]

try:
    import jsbeautifier
except ImportError as e:  # pragma: no cover
    jsbeautifier = str(e)  # ty:ignore[invalid-assignment]

logger = logging.getLogger(__name__)

__all__ = [
    'AutoMatchFilter',
    'RegexMatchFilter',
]


class BeautifyFilter(FilterBase):
    """Beautify HTML (requires Python package ``BeautifulSoup`` and optionally ``jsbeautifier`` and/or
    ``cssbeautifier``).
    """

    __kind__ = 'beautify'

    __supported_subfilters__: dict[str, str] = {
        'absolute_links': 'Convert relative links to absolute ones.',
        'indent': 'Number of spaces by which to indent HTML output.',
    }

    __default_subfilter__ = 'indent'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        if isinstance(bs4, str):
            self.raise_import_error('BeautifulSoup', self.__kind__, bs4)

        bs4_features = 'lxml' if importlib.util.find_spec('lxml') is not None else 'html'
        soup = bs4.BeautifulSoup(data, features=bs4_features)

        if isinstance(jsbeautifier, str):
            logger.warning(
                f"Python package 'jsbeautifier' cannot be imported; will not beautify <script> tags"
                f' ({self.job.get_indexed_location()})\n{jsbeautifier}'
            )
        else:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    beautified_js = jsbeautifier.beautify(script.string)
                    script.string = beautified_js

        if isinstance(cssbeautifier, str):
            logger.warning(
                "Python package 'cssbeautifier' cannot be imported; will not beautify <style> tags"
                f' ({self.job.get_indexed_location()})\n{cssbeautifier}'
            )
        else:
            styles = soup.find_all('style')
            for style in styles:
                if style.string:
                    beautified_css = cssbeautifier.beautify(style.string)
                    style.string = beautified_css

        if subfilter.get('absolute_links') is None or subfilter.get('absolute_links'):
            for link in soup.find_all('a', href=True):
                link['href'] = urljoin(self.job.url, link['href'])

        indent = subfilter.get('indent', 1)
        return soup.prettify(formatter=bs4.formatter.HTMLFormatter(indent=indent)), mime_type


class AbsoluteLinksFilter(FilterBase):
    """Replace relative HTML <a> href links with absolute ones."""

    __kind__ = 'absolute_links'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        tree = etree.HTML(data)
        elem: etree._Element
        for elem in tree.xpath('//*[@action]'):  # type: ignore[assignment,union-attr]
            elem.attrib['action'] = urljoin(self.job.url, elem.attrib['action'])
        for elem in tree.xpath('//object[@data]'):  # type: ignore[assignment,union-attr]
            elem.attrib['data'] = urljoin(self.job.url, elem.attrib['data'])
        for elem in tree.xpath('//*[@href]'):  # type: ignore[assignment,union-attr]
            elem.attrib['href'] = urljoin(self.job.url, elem.attrib['href'])
        for elem in tree.xpath('//*[@src]'):  # type: ignore[assignment,union-attr]
            elem.attrib['src'] = urljoin(self.job.url, elem.attrib['src'])
        return etree.tostring(tree, encoding='unicode', method='html'), mime_type


class Html2TextFilter(FilterBase):
    """Convert a string consisting of HTML to Unicode plain text for easy difference checking."""

    __kind__ = 'html2text'

    __supported_subfilters__: dict[str, str] = {
        'method': 'Method to use for conversion (html2text [default], bs4, or strip_tags)',
        'separator': 'bs4: Strings will be concatenated using this separator',
        'strip': 'bs4: If True, strings will be stripped before being concatenated',
        '<any>': 'html2text: Library-specific options (see '
        'https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options)',
    }

    __default_subfilter__ = 'method'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
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

        * ``bs4``: Use Beautiful Soup Python library to extract plain text.

          * options:

            * parser: the type of markup you want to parse (currently supported are ``html``, ``xml``, and ``html5``)
              or the name of the parser library you want to use (currently supported options are ``lxml``,
              ``html5lib`` and ``html.parser``) as per
              https://www.crummy.com/software/BeautifulSoup/bs4/doc/#specifying-the-parser-to-use.  Different parsers
              are compared at https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser.
              Note: ``html5lib``requires having the ``html5lib`` Python package already installed. Defaults to 'lxml'.
            * separator: Strings will be concatenated using this separator. Defaults to `````` (empty string).
            * strip: If True, strings will be stripped before being concatenated. Defaults to False.

        * ``strip_tags``: A simple and fast regex-based HTML tag stripper.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        # extract method and options from subfilter, defaulting to method html2text
        if not isinstance(data, str):
            raise ValueError
        options = subfilter.copy()
        method = options.pop('method', 'html2text')

        if method in {'html2text', 'pyhtml2text'}:  # pythtml2text for backward compatibility
            if method == 'pyhtml2text':
                warnings.warn(
                    f"Filter html2text's method 'pyhtml2text' is deprecated: remove method as it's now the "
                    f"filter's default ({self.job.get_indexed_location()})",
                    DeprecationWarning,
                    stacklevel=1,
                )
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
            return '\n'.join(line.rstrip() for line in parser.handle(data).splitlines()), 'text/markdown'

        if method == 'bs4':
            if isinstance(bs4, str):
                self.raise_import_error('BeautifulSoup', self.__kind__, bs4)

            default_bs4_parser = 'lxml' if importlib.util.find_spec('lxml') is not None else 'html'
            bs4_parser: str = options.pop('parser', default_bs4_parser)
            try:
                soup = bs4.BeautifulSoup(data, features=bs4_parser)
            except bs4.FeatureNotFound:
                raise ValueError(  # noqa: B904
                    f"Filter html2text's method 'bs4' has been invoked with parser '{bs4_parser}', which is either not "
                    f'installed or is not supported by Beautiful Soup. Please refer to the documentation at '
                    f'https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser. '
                    f'({self.job.get_indexed_location()})'
                )
            separator: str = options.pop('separator', '')
            strip: bool = options.pop('strip', False)
            return soup.get_text(separator=separator, strip=strip), 'text/plain'

        if method in {'strip_tags', 're'}:  # re for backward compatibility
            if method == 're':
                warnings.warn(
                    f"Filter html2text's method 're' is deprecated: replace with 'strip_tags' "
                    f'({self.job.get_indexed_location()})',
                    DeprecationWarning,
                    stacklevel=1,
                )
            stripped_tags = html.unescape(re.sub(r'<[^>]*>', '', data))
            return '\n'.join((line.rstrip() for line in stripped_tags.splitlines() if line.strip() != '')), 'text/plain'

        if method == 'lynx':
            raise NotImplementedError(
                f"Filter html2text's method 'lynx' is no longer supported; for similar results, use the filter without "
                f'specifying a method. ({self.job.get_indexed_location()})'
            )

        raise ValueError(f"Unknown method {method} for filter 'html2text'. ({self.job.get_indexed_location()})")


class FormatXMLFilter(FilterBase):
    """Convert to formatted XML using lxml.etree."""

    __kind__ = 'format-xml'

    __no_subfilter__ = True

    # __supported_subfilters__: dict[str, str] = {
    #     'indentation': 'Indentation level for pretty-printing',
    # }
    #
    # __default_subfilter__ = 'indentation'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        parsed_xml = etree.XML(data)
        if not mime_type.endswith('xml'):
            mime_type = 'application/xml'
        return etree.tostring(parsed_xml, encoding='unicode', pretty_print=True), mime_type


class PrettyXMLFilter(FilterBase):
    """Pretty-print XML using xml.dom.minidom."""

    __kind__ = 'pretty-xml'

    __supported_subfilters__: dict[str, str] = {
        'indentation': 'Indentation level for pretty-printing',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        indentation = int(subfilter.get('indentation', 2))
        if not mime_type.endswith('xml'):
            mime_type = 'application/xml'
        return minidom.parseString(data).toprettyxml(indent=' ' * indentation), mime_type  # noqa: S318 use defusedxml.


class FilterBy(Enum):
    ATTRIBUTE = 1
    TAG = 2


class ElementsBy(HTMLParser, ABC):
    def __init__(self, filter_by: FilterBy, name: str, value: Any = None) -> None:  # noqa: ANN401 Dynamically typed expressions Any are disallowed
        super().__init__()

        self._filter_by = filter_by
        if self._filter_by == FilterBy.ATTRIBUTE:
            self._attributes = {name: value}
        else:
            # FilterBy.TAG
            self._name = name

        self._result: list[str] = []
        self._inside: bool = False
        self._elts: list[str] = []

    def get_html(self) -> str:
        return ''.join(self._result)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = dict(attrs)

        if (self._filter_by == FilterBy.ATTRIBUTE and all(ad.get(k) == v for k, v in self._attributes.items())) or (
            self._filter_by == FilterBy.TAG and tag == self._name
        ):
            self._inside = True

        if self._inside:
            self._result.append(f'<{tag}{" " if attrs else ""}%s>' % ' '.join(f'{k}="{v}"' for k, v in attrs))
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

    __supported_subfilters__: dict[str, str] = {
        'id': 'ID of the element to filter for (required)',
    }

    __default_subfilter__ = 'id'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'id' not in subfilter:
            raise ValueError(
                f"The 'element-by-id' filter needs an id for filtering. ({self.job.get_indexed_location()})"
            )

        element_by_id = ElementsBy(FilterBy.ATTRIBUTE, 'id', subfilter['id'])
        element_by_id.feed(data)
        return element_by_id.get_html(), mime_type


class ElementByClassFilter(FilterBase):
    """Get all HTML elements matching a class."""

    __kind__ = 'element-by-class'

    __supported_subfilters__: dict[str, str] = {
        'class': 'HTML class attribute to filter for (required)',
    }

    __default_subfilter__ = 'class'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'class' not in subfilter:
            raise ValueError(
                f"The 'element-by-class' filter needs a class for filtering. ({self.job.get_indexed_location()})"
            )

        element_by_class = ElementsBy(FilterBy.ATTRIBUTE, 'class', subfilter['class'])
        element_by_class.feed(data)
        return element_by_class.get_html(), mime_type


class ElementByStyleFilter(FilterBase):
    """Get all HTML elements matching a style."""

    __kind__ = 'element-by-style'

    __supported_subfilters__: dict[str, str] = {
        'style': 'HTML style attribute value to filter for (required)',
    }

    __default_subfilter__ = 'style'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'style' not in subfilter:
            raise ValueError(
                f"The 'element-by-style' filter needs a style for filtering. ({self.job.get_indexed_location()})"
            )

        element_by_style = ElementsBy(FilterBy.ATTRIBUTE, 'style', subfilter['style'])
        element_by_style.feed(data)
        return element_by_style.get_html(), mime_type


class ElementByTagFilter(FilterBase):
    """Get all HTML elements matching a tag."""

    __kind__ = 'element-by-tag'

    __supported_subfilters__: dict[str, str] = {
        'tag': 'HTML tag name to filter for (required)',
    }

    __default_subfilter__ = 'tag'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'tag' not in subfilter:
            raise ValueError(
                f"The 'element-by-tag' filter needs a tag for filtering. ({self.job.get_indexed_location()})"
            )

        element_by_tag = ElementsBy(FilterBy.TAG, subfilter['tag'])
        element_by_tag.feed(data)
        return element_by_tag.get_html(), mime_type


class LxmlParser:
    EXPR_NAMES: dict[str, str] = {
        'css': 'a CSS selector',
        'xpath': 'an XPath expression',
    }

    expression: str
    method: str
    namespaces: dict[str, str] | None
    parser: etree._FeedParser
    skip: int

    def __init__(
        self,
        filter_kind: str,
        subfilter: dict[str, Any],
        expr_key: str,
        job: JobBase,
    ) -> None:
        self.filter_kind = filter_kind
        self.method = subfilter.get('method', 'html')
        if self.method not in {'html', 'xml'}:
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
        self.sort_items = bool(subfilter.get('sort', False))
        self.maxitems = int(subfilter.get('maxitems', 0))
        if self.method == 'html' and self.namespaces:
            raise ValueError(
                f"The '{filter_kind}' filter's namespace prefixes are only supported with 'method: xml'. "
                f'({job.get_indexed_location()})'
            )
        self.data = ''

    def feed(self, data: str) -> None:
        self.data += data

    @staticmethod
    def _to_string(element: etree._Element | str, method: str) -> str:
        # Handle "/text()" selector, which returns lxml.etree._ElementUnicodeResult
        # (https://github.com/thp/urlwatch/issues/282)
        if isinstance(element, str):
            return element

        return etree.tostring(element, encoding='unicode', method=method, pretty_print=True, with_tail=False).strip()

    @staticmethod
    def _remove_element(element: etree._Element) -> None:
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

    def _reevaluate(self, element: etree._Element) -> etree._Element | str | None:
        if self._orphaned(element):
            return None
        if isinstance(element, etree._ElementUnicodeResult):
            parent = element.getparent()
            if parent is None:
                return element
            if element.is_tail:
                return parent.tail
            if element.is_text:
                return parent.text
            if element.is_attribute:
                return parent.attrib.get(element.attrname)
            return element
        return element

    def _orphaned(self, element: etree._Element) -> bool:
        if isinstance(element, etree._ElementUnicodeResult):
            parent = element.getparent()
            if (
                (element.is_tail and parent.tail is None)
                or (element.is_text and parent.text is None)
                or (element.is_attribute and parent.attrib.get(element.attrname) is None)
            ):
                return True
            element = parent
        try:
            tree = element.getroottree()
            path = tree.getpath(element)
            return element is not tree.xpath(path, namespaces=self.namespaces)[0]  # type: ignore[index]
        except (ValueError, IndexError):
            return True

    def _get_filtered_elements(
        self,
        job_index_number: int | None = None,
    ) -> list[etree._Element | str]:
        if self.method == 'xml' and isinstance(self.data, str):
            # see https://lxml.de/FAQ.html#why-can-t-lxml-parse-my-xml-from-unicode-strings
            data: str | bytes = self.data.encode(errors='xmlcharrefreplace')
        elif self.method == 'html' and self.data.startswith('<?xml'):
            # handle legacy https://stackoverflow.com/questions/37592045/
            data = self.data.split('>', maxsplit=1)[1]
        else:
            data = self.data
        try:
            root = etree.XML(data) if self.method == 'xml' else etree.HTML(data)
        except ValueError as e:
            args = (
                f"Filter '{self.filter_kind}' encountered the following error when parsing the data. Check that "
                f"'method: {self.method}' is the correct one.\n    {type(e).__name__}: {e}"
            )
            raise RuntimeError(args) from None
        if root is None:
            return []
        selected_elems: list[etree._Element] | None = None
        excluded_elems: list[etree._Element] | None = None
        try:
            if self.filter_kind == 'css':
                selected_elems = CSSSelector(self.expression, namespaces=self.namespaces)(root)  # type: ignore[assignment]
                excluded_elems = CSSSelector(self.exclude, namespaces=self.namespaces)(root) if self.exclude else None  # ty:ignore[invalid-assignment]

            elif self.filter_kind == 'xpath':
                selected_elems = root.xpath(self.expression, namespaces=self.namespaces)  # type: ignore[assignment]
                excluded_elems = root.xpath(self.exclude, namespaces=self.namespaces) if self.exclude else None  # ty:ignore[invalid-assignment]
        except (etree.ParserError, etree.XMLSchemaError, etree.XPathError) as e:
            raise ValueError(f'Job {job_index_number} {type(e).__name__}: {e} {self.expression}') from e
        if excluded_elems is not None:
            for el in excluded_elems:
                self._remove_element(el)
        if isinstance(selected_elems, str):
            return [selected_elems]
        if selected_elems is not None:
            return [el for el in map(self._reevaluate, selected_elems) if el is not None]
        return []

    def get_filtered_data(self, job_index_number: int | None = None) -> str:
        elements = self._get_filtered_elements(job_index_number)
        if self.skip:
            elements = elements[self.skip :]
        if self.maxitems:
            elements = elements[: self.maxitems]
        elementstrs = (self._to_string(element, self.method) for element in elements)
        return '\n'.join(sorted(elementstrs) if self.sort_items else elementstrs)


LXML_PARSER_COMMON_SUBFILTERS = {
    'method': 'The method (html or xml) used for parsing',
    'exclude': 'Elements to remove from the final result',
    'namespaces': 'Mapping of XML namespaces for matching',
    'skip': 'Number of elements to skip from the beginning (default: 0)',
    'maxitems': 'Maximum number of items to return (default: all)',
    'sort': 'Sort matched items after filtering (default: False)',
}


class CSSFilter(FilterBase):
    """Filter XML/HTML using CSS selectors."""

    __kind__ = 'css'

    __supported_subfilters__: dict[str, str] = {
        'selector': 'The CSS selector to use for filtering (required)',
        **LXML_PARSER_COMMON_SUBFILTERS,
    }

    __default_subfilter__ = 'selector'

    EXPR_NAMES: dict[str, str]
    expression: str
    exclude: str
    namespaces: dict[str, str]
    skip: int
    maxitems: int

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        lxml_parser = LxmlParser('css', subfilter, 'selector', self.job)
        lxml_parser.feed(data)
        return lxml_parser.get_filtered_data(self.job.index_number), mime_type


class XPathFilter(FilterBase):
    """Filter XML/HTML using XPath expressions."""

    __kind__ = 'xpath'

    __supported_subfilters__: dict[str, str] = {
        'path': 'The XPath to use for filtering (required)',
        **LXML_PARSER_COMMON_SUBFILTERS,
    }

    __default_subfilter__ = 'path'

    EXPR_NAMES: dict[str, str]
    expression: str
    exclude: str
    namespaces: dict[str, str]
    skip: int
    maxitems: int

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        lxml_parser = LxmlParser('xpath', subfilter, 'path', self.job)
        lxml_parser.feed(data)
        return lxml_parser.get_filtered_data(self.job.index_number), mime_type
