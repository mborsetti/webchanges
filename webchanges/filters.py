"""Filters."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import base64
import csv
import hashlib
import html
import importlib.util
import io
import itertools
import logging
import os
import re
import shlex
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.
import warnings
from abc import ABC
from enum import Enum
from html.parser import HTMLParser
from typing import Any, Iterator, Literal, TYPE_CHECKING
from urllib.parse import urljoin
from xml.dom import minidom  # noqa: S408 Replace minidom with the equivalent defusedxml package. TODO

import html2text
import yaml
from lxml import etree  # noqa: S410 insecure use of XML modules, prefer "defusedxml". TODO
from lxml.cssselect import CSSSelector  # noqa: S410 insecure use of XML ... "defusedxml". TODO

from webchanges import __project_name__
from webchanges.util import TrackSubClasses

# https://stackoverflow.com/questions/712791
try:
    import simplejson as jsonlib
except ImportError:  # pragma: no cover
    import json as jsonlib  # type: ignore[no-redef]

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.handler import JobState
    from webchanges.jobs import JobBase

try:
    import bs4
except ImportError as e:  # pragma: has-bs4
    bs4 = str(e)  # type: ignore[assignment]

try:
    import cssbeautifier
except ImportError as e:  # pragma: no cover
    cssbeautifier = str(e)  # type: ignore[assignment]

try:
    import jq
except ImportError as e:  # pragma: has-jq
    jq = str(e)

try:
    import jsbeautifier
except ImportError as e:  # pragma: no cover
    jsbeautifier = str(e)  # type: ignore[assignment]

try:
    from pypdf import PdfReader
except ImportError as e:  # pragma: no cover
    PdfReader = str(e)  # type: ignore[assignment,misc]

try:
    import pdftotext
except ImportError as e:  # pragma: has-pdftotext
    pdftotext = str(e)  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError as e:  # pragma: no cover
    Image = str(e)  # type: ignore[assignment]

try:
    import pytesseract
except ImportError as e:  # pragma: has-pytesseract
    pytesseract = str(e)  # type: ignore[assignment]

try:
    import vobject.base
except ImportError as e:  # pragma: no cover
    vobject = str(e)  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class FilterBase(metaclass=TrackSubClasses):
    """The base class for filters."""

    __subclasses__: dict[str, type[FilterBase]] = {}
    __anonymous_subclasses__: list[type[FilterBase]] = []

    __kind__: str = ''

    # Typing
    __supported_subfilters__: dict[str, str]
    __default_subfilter__: str
    __no_subfilter__: bool
    __uses_bytes__: bool
    method: str

    def __init__(self, state: JobState) -> None:
        """

        :param state: the JobState.
        """
        self.job = state.job
        self.state = state

    @classmethod
    def filter_documentation(cls) -> str:
        """Generates simple filter documentation for use in the --features command line argument.

        :returns: A string to display.
        """
        result: list[str] = []
        for sc in TrackSubClasses.sorted_by_kind(cls):
            default_subfilter = getattr(sc, '__default_subfilter__', None)
            result.extend((f'  * {sc.__kind__} - {sc.__doc__}',))
            if hasattr(sc, '__supported_subfilters__'):
                for key, doc in sc.__supported_subfilters__.items():
                    result.append(
                        f"      {'[' if key == default_subfilter else ''}{key}{']' if key == default_subfilter else ''}"
                        f' ... {doc}'
                    )
        result.append('\n[] ... Parameter can be supplied as unnamed value\n')
        return '\n'.join(result)

    @classmethod
    def auto_process(cls, state: JobState, data: str | bytes, mime_type: str) -> tuple[str | bytes, str]:
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
            filter_instance = filtercls(state)
            if filter_instance.match():
                logger.info(f'Job {state.job.index_number}: Auto-applying filter {filter_instance}')
                data, mime_type = filter_instance.filter(data, mime_type, {})  # All filters take a subfilter

        return data, mime_type

    @classmethod
    def normalize_filter_list(
        cls,
        filter_spec: str | list[str | dict[str, Any]] | None,
        job_index_number: int | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Generates a list of filters that has been checked for its validity.

        :param filter_spec: A list of either filter_kind, subfilter (where subfilter is a dict) or a legacy
           string-based filter list specification.
        :param job_index_number: The job index number.
        :returns: Iterator of filter_kind, subfilter (where subfilter is a dict).
        """
        for filter_kind, subfilter in cls._internal_normalize_filter_list(filter_spec, job_index_number):
            filtercls = cls.__subclasses__.get(filter_kind, None)

            if filtercls is None:
                raise ValueError(
                    f'Job {job_index_number}: Unknown filter kind: {filter_kind} (subfilter or filter directive(s): '
                    f'{subfilter}).'
                )

            if getattr(filtercls, '__no_subfilter__', False) and subfilter:
                raise ValueError(
                    f'Job {job_index_number}: No subfilters or filter directives supported for {filter_kind}.'
                )

            if hasattr(filtercls, '__supported_subfilters__'):
                provided_keys = set(subfilter.keys())
                allowed_keys = set(filtercls.__supported_subfilters__.keys())
                unknown_keys = provided_keys.difference(allowed_keys)
                if unknown_keys and '<any>' not in allowed_keys:
                    if allowed_keys:
                        raise ValueError(
                            f'Job {job_index_number}: Filter {filter_kind} does not support subfilter or filter '
                            f"directive(s) {', '.join(unknown_keys)}. Only {', '.join(allowed_keys)} are supported."
                        )
                    else:
                        raise ValueError(
                            f'Job {job_index_number}: Filter {filter_kind} does not support any subfilters or filter '
                            f"directives, but {', '.join(unknown_keys)} was supplied."
                        )

            yield filter_kind, subfilter

    @classmethod
    def _internal_normalize_filter_list(
        cls,
        filter_spec: str | list[str | dict[str, Any]] | None,
        job_index_number: int | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
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
                (
                    {filter_kind.split(':', maxsplit=1)[0]: filter_kind.split(':', maxsplit=1)[1]}
                    if ':' in filter_kind
                    else {filter_kind: ''}
                )
                for filter_kind in old_filter_spec.split(',')
            ]
            warnings.warn(
                f'String-based filter definitions ({old_filter_spec}) are deprecated, please convert to dict-style:\n\n'
                f'{yaml.safe_dump(filter_spec, default_flow_style=False, allow_unicode=True, sort_keys=False,)}',
                DeprecationWarning,
            )

        if isinstance(filter_spec, list):
            for item in filter_spec:
                if isinstance(item, str):
                    filter_kind, subfilter = item, None
                elif isinstance(item, dict):
                    filter_kind, subfilter = next(iter(item.items()))
                else:
                    raise ValueError(
                        f'Job {job_index_number}: Subfilter or filter directive(s) must be a string or a dictionary.'
                    )

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
    def process(
        cls, filter_kind: str, subfilter: dict[str, Any], job_state: JobState, data: str | bytes, mime_type: str
    ) -> tuple[str | bytes, str]:
        """Process the filter.

        :param filter_kind: The name of the filter.
        :param subfilter: The subfilter information.
        :param job_state: The JobState object (containing the Job).
        :param data: The data upon which to apply the filter.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        logger.info(f'Job {job_state.job.index_number}: Applying filter {filter_kind}, subfilter(s) {subfilter}')
        filtercls: type[FilterBase] | None = cls.__subclasses__.get(filter_kind)  # type: ignore[assignment]
        if filtercls:
            return filtercls(job_state).filter(data, mime_type, subfilter)
        else:
            return data, mime_type

    @classmethod
    def filter_chain_needs_bytes(cls, filter_name: str | list[str | dict[str, Any]] | None) -> bool:
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

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Method used by the filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        raise NotImplementedError()

    def raise_import_error(self, package_name: str, filter_name: str, error_message: str) -> None:
        """Raise ImportError for missing package.

        :param package_name: The name of the module/package that could not be imported.
        :param filter_name: The name of the filter that needs the package.
        :param error_message: The error message from ImportError.

        :raises: ImportError.
        """
        raise ImportError(
            f"Filter {filter_name} requires package '{package_name}', which has the following error: {error_message}"
        )


class AutoMatchFilter(FilterBase):
    """Base class for filters that automatically exactly match one or more directives.

    MATCH is a dict of {directive: text to match}.
    """

    MATCH: dict[str, str] | None = None

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

    def filter(  # type: ignore[empty-body]
        self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]
    ) -> tuple[str | bytes, str]:
        """Method used by filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        ...


class RegexMatchFilter(FilterBase):
    """Base class for filters that automatically match one or more directives.

    Same as AutoMatchFilter but MATCH is a dict of {directive: Regular Expression Object}, where a Regular
    Expression Object is a compiled regex."""

    MATCH: dict[str, re.Pattern] | None = None

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

    def filter(  # type: ignore[empty-body]
        self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]
    ) -> tuple[str | bytes, str]:
        """Method used by filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        ...


class BeautifyFilter(FilterBase):
    """Beautify HTML (requires Python package ``BeautifulSoup`` and optionally ``jsbeautifier`` and/or
    ``cssbeautifier``)."""

    __kind__ = 'beautify'

    __supported_subfilters__ = {
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
            elem.attrib['action'] = urljoin(self.job.url, elem.attrib['action'])  # type: ignore[type-var,assignment]
        for elem in tree.xpath('//object[@data]'):  # type: ignore[assignment,union-attr]
            elem.attrib['data'] = urljoin(self.job.url, elem.attrib['data'])  # type: ignore[type-var,assignment]
        for elem in tree.xpath('//*[@href]'):  # type: ignore[assignment,union-attr]
            elem.attrib['href'] = urljoin(self.job.url, elem.attrib['href'])  # type: ignore[type-var,assignment]
        for elem in tree.xpath('//*[@src]'):  # type: ignore[assignment,union-attr]
            elem.attrib['src'] = urljoin(self.job.url, elem.attrib['src'])  # type: ignore[type-var,assignment]
        return etree.tostring(tree, encoding='unicode', method='html'), mime_type


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

        elif method == 'bs4':
            if isinstance(bs4, str):
                self.raise_import_error('BeautifulSoup', self.__kind__, bs4)

            default_bs4_parser = 'lxml' if importlib.util.find_spec('lxml') is not None else 'html'
            bs4_parser: str = options.pop('parser', default_bs4_parser)
            try:
                soup = bs4.BeautifulSoup(data, bs4_parser)
            except bs4.FeatureNotFound:
                raise ValueError(
                    f"Filter html2text's method 'bs4' has been invoked with parser '{bs4_parser}', which is either not "
                    f'installed or is not supported by Beautiful Soup. Please refer to the documentation at '
                    f'https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser. '
                    f'({self.job.get_indexed_location()})'
                )
            separator: str = options.pop('separator', '')
            strip: bool = options.pop('strip', False)
            return soup.get_text(separator=separator, strip=strip), 'text/plain'

        elif method in {'strip_tags', 're'}:  # re for backward compatibility
            if method == 're':
                warnings.warn(
                    f"Filter html2text's method 're' is deprecated: replace with 'strip_tags' "
                    f'({self.job.get_indexed_location()})',
                    DeprecationWarning,
                )
            stripped_tags = html.unescape(re.sub(r'<[^>]*>', '', data))
            return '\n'.join((line.rstrip() for line in stripped_tags.splitlines() if line.strip() != '')), 'text/plain'

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

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
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

        return '\n'.join(lines), 'text/plain'


class PypdfFilter(FilterBase):
    """Convert PDF to plaintext (requires Python package ``pypdf``)."""

    # Dependency: pdftotext (https://github.com/jalan/pdftotext), itself based
    # on poppler (https://poppler.freedesktop.org/)
    # Note: check pdftotext website for OS-specific dependencies for install

    __kind__ = 'pypdf'
    __uses_bytes__ = True

    __supported_subfilters__ = {
        'password': 'PDF password for decryption',
        'extraction_mode': '"layout" for experimental layout mode functionality',
    }

    __default_subfilter__ = 'password'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        # data must be bytes
        if not isinstance(data, bytes):
            raise ValueError(
                f"The '{self.__kind__}' filter needs bytes input (is it the first filter?). "
                f'({self.job.get_indexed_location()})'
            )

        if isinstance(PdfReader, str):
            self.raise_import_error('pypdf', self.__kind__, PdfReader)

        password = subfilter.get('password', None)
        extraction_mode: Literal['plain', 'layout'] = subfilter.get('extraction_mode', 'plain')

        if password:
            try:
                import cryptography  # noqa: F401 imported but unused
            except ImportError:  # pragma: no cover
                self.raise_import_error(
                    'cryptography',
                    f'password sub-directive of {self.__kind__}',
                    "Please install with 'pip install --upgrade webchanges[pypdf_crypto]'",
                )

        text = []
        reader = PdfReader(io.BytesIO(data), password=password)
        logger.info(f'Job {self.job.index_number}: Found {reader.pdf_header} file')
        for page in reader.pages:
            text.append(page.extract_text(extraction_mode=extraction_mode))

        return '\n'.join(text), 'text/plain'


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

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        # data must be bytes
        if not isinstance(data, bytes):
            raise ValueError(
                f"The '{self.__kind__}' filter needs bytes input (is it the first filter?). "
                f'({self.job.get_indexed_location()})'
            )

        if isinstance(pdftotext, str):
            self.raise_import_error('pdftotext', self.__kind__, pdftotext)

        return (
            '\n'.join(
                pdftotext.PDF(
                    io.BytesIO(data),
                    password=subfilter.get('password', ''),
                    raw=subfilter.get('method', False),
                    physical=subfilter.get('physical', True),
                ),
            ),
            'text/plain',
        )


class Ical2TextFilter(FilterBase):
    """Convert iCalendar to plaintext (requires Python package ``vobject``)."""

    __kind__ = 'ical2text'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if isinstance(vobject, str):
            self.raise_import_error('vobject', self.__kind__, vobject)

        result = []
        if isinstance(data, str):
            parsedCal = vobject.base.readOne(data)
        else:
            try:
                parsedCal = vobject.base.readOne(data)
            except vobject.base.ParseError:
                parsedCal = vobject.base.readOne(data.decode(errors='ignore'))
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

        return '\n'.join(result), 'text/plain'


class FormatJsonFilter(FilterBase):
    """Convert to formatted JSON."""

    __kind__ = 'format-json'

    __supported_subfilters__ = {
        'indentation': 'Indentation level for pretty-printing',
        'sort_keys': 'Sort the output of dictionaries by key',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        self.job.set_to_monospace()
        sort_keys = subfilter.get('sort_keys', False)
        indentation = int(subfilter.get('indentation', 4))
        try:
            parsed_json = jsonlib.loads(data)
        except jsonlib.JSONDecodeError as e:
            return (
                jsonlib.dumps(
                    f"ERROR: Filter '{self.__kind__}' returned 'JSONDecodeError: {e}' on the following data:\n\n"
                    f'{data!s}',
                    ensure_ascii=False,
                ),
                'application/json',
            )
        if not mime_type.endswith('json'):
            mime_type = 'application/json'
        return jsonlib.dumps(parsed_json, ensure_ascii=False, sort_keys=sort_keys, indent=indentation), mime_type


class FormatXMLFilter(FilterBase):
    """Convert to formatted XML using lxml.etree."""

    __kind__ = 'format-xml'

    __no_subfilter__ = True

    # __supported_subfilters__ = {
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

    __supported_subfilters__ = {
        'indentation': 'Indentation level for pretty-printing',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        indentation = int(subfilter.get('indentation', 2))
        if not mime_type.endswith('xml'):
            mime_type = 'application/xml'
        return minidom.parseString(data).toprettyxml(indent=' ' * indentation), mime_type  # noqa: S318 use defusedxml.


class KeepLinesContainingFilter(FilterBase):
    """Filter only lines matching a regular expression."""

    __kind__ = 'keep_lines_containing'

    __supported_subfilters__ = {
        'text': 'Lines matching this text are kept (default)',
        're': 'Lines matching this expression are kept',
    }

    __default_subfilter__ = 'text'

    def filter(
        self: KeepLinesContainingFilter | GrepFilter,
        data: str | bytes,
        mime_type: str,
        subfilter: dict[str, Any],
    ) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'text' in subfilter:
            if isinstance(subfilter['text'], str):
                return (
                    ''.join(line for line in data.splitlines(keepends=True) if subfilter['text'] in line).rstrip(),
                    mime_type,
                )
            else:
                raise TypeError(
                    f"The '{self.__kind__}' filter requires a string but you provided a "
                    f"{type(subfilter['text']).__name__}. ({self.job.get_indexed_location()})"
                )
        if 're' in subfilter:
            if isinstance(subfilter['re'], str):
                return (
                    ''.join(
                        line for line in data.splitlines(keepends=True) if re.search(subfilter['re'], line)
                    ).rstrip(),
                    mime_type,
                )
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

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        warnings.warn(
            f"The 'grep' filter is deprecated; replace with 'keep_lines_containing' + 're' subfilter"
            f' ({self.job.get_indexed_location()})',
            DeprecationWarning,
        )
        return KeepLinesContainingFilter.filter(self, data, mime_type, subfilter)


class DeleteLinesContainingFilter(FilterBase):
    """Remove lines matching a regular expression."""

    __kind__ = 'delete_lines_containing'

    __supported_subfilters__ = {
        'text': 'Lines matching this text are deleted (default)',
        're': 'Lines matching this expression deleted kept',
    }

    __default_subfilter__ = 'text'

    def filter(
        self: DeleteLinesContainingFilter | GrepIFilter,
        data: str | bytes,
        mime_type: str,
        subfilter: dict[str, Any],
    ) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'text' in subfilter:
            if isinstance(subfilter['text'], str):
                return (
                    ''.join(line for line in data.splitlines(keepends=True) if subfilter['text'] not in line).rstrip(),
                    mime_type,
                )
            else:
                raise TypeError(
                    f"The '{self.__kind__}' filter requires a string but you provided a "
                    f"{type(subfilter['text']).__name__}. ({self.job.get_indexed_location()})"
                )
        if 're' in subfilter:
            if isinstance(subfilter['re'], str):
                return (
                    ''.join(
                        line for line in data.splitlines(keepends=True) if re.search(subfilter['re'], line) is None
                    ).rstrip(),
                    mime_type,
                )
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

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        warnings.warn(
            f"The 'grepi' filter is deprecated; replace with 'delete_lines_containing' + 're' subfilter"
            f' ({self.job.get_indexed_location()})',
            DeprecationWarning,
        )
        return DeleteLinesContainingFilter.filter(self, data, mime_type, subfilter)


class StripFilter(FilterBase):
    """Strip leading and trailing whitespace."""

    __kind__ = 'strip'

    __supported_subfilters__ = {
        'splitlines': 'Apply the filter on each line of text (default: false, apply to the entire data)',
        'chars': 'String specifying the set of characters to be removed. If omitted, defaults to removing whitespace',
        'side': "One-sided removal: either 'left' (leading characters) or 'right' (trailing characters)",
    }

    __default_subfilter__ = 'chars'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if subfilter.get('splitlines'):
            lines = data.splitlines()

            if 'side' in subfilter:
                if subfilter['side'] == 'right':
                    return '\n'.join([line.rstrip(subfilter.get('chars')) for line in lines]), mime_type
                if subfilter['side'] == 'left':
                    return '\n'.join([line.lstrip(subfilter.get('chars')) for line in lines]), mime_type

                raise ValueError(
                    f"The 'strip' filter's 'side' sub-directive can only be 'right' or 'left'. "
                    f'({self.job.get_indexed_location()})'
                )

            return '\n'.join([line.strip(subfilter.get('chars')) for line in lines]), mime_type

        else:
            if 'side' in subfilter:
                if subfilter['side'] == 'right':
                    return data.rstrip(subfilter.get('chars')), mime_type
                if subfilter['side'] == 'left':
                    return data.lstrip(subfilter.get('chars')), mime_type

                raise ValueError(
                    f"The 'strip' filter's 'side' sub-directive can only be 'right' or 'left'. "
                    f'({self.job.get_indexed_location()})'
                )

            return data.strip(subfilter.get('chars')), mime_type


class StripLinesFilter(FilterBase):
    """Deprecated; use ``strip`` with subfilter ``splitlines`` instead."""

    __kind__ = 'striplines'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        warnings.warn(
            f"The 'strip_each_line' filter is deprecated; replace with 'strip' and sub-directive 'splitlines: "
            f"true' ({self.job.get_indexed_location()})",
            DeprecationWarning,
        )
        if not isinstance(data, str):
            raise ValueError
        return '\n'.join([line.strip() for line in data.splitlines()]), mime_type


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

        self._result: list[str] = []
        self._inside: bool = False
        self._elts: list[str] = []

    def get_html(self) -> str:
        return ''.join(self._result)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
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

    __supported_subfilters__ = {
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

    __supported_subfilters__ = {
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

    __supported_subfilters__ = {
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


class Sha1SumFilter(FilterBase):
    """Calculate the SHA-1 checksum of the content."""

    __kind__ = 'sha1sum'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        return hashlib.sha1(data, usedforsecurity=False).hexdigest(), 'text/plain'


class Sha256SumFilter(FilterBase):
    """Calculate the SHA-256 checksum of the content."""

    __kind__ = 'sha256sum'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        return hashlib.sha256(data, usedforsecurity=False).hexdigest(), 'text/plain'


class HexDumpFilter(FilterBase):
    """Convert string to hex dump format."""

    __kind__ = 'hexdump'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        arr = bytearray(data)
        blocks = [arr[i * 16 : (i + 1) * 16] for i in range(int((len(arr) + (16 - 1)) / 16))]
        return (
            '\n'.join(
                f"{' '.join(f'{c:02x}' for c in block):49}{''.join((chr(c) if (31 < c < 127) else '.') for c in block)}"
                for block in blocks
            ),
            'text/plain',
        )


class LxmlParser:
    EXPR_NAMES = {
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

        return (  # type: ignore[no-any-return]
            etree.tostring(element, encoding='unicode', method=method, pretty_print=True, with_tail=False).strip()
        )

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
            elif element.is_text:
                return parent.text
            elif element.is_attribute:
                return parent.attrib.get(element.attrname)
            else:
                return element
        else:
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
            else:
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
            if self.method == 'xml':
                root = etree.XML(data)
            else:  # html
                root = etree.HTML(data)
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
                selected_elems = CSSSelector(self.expression, namespaces=self.namespaces)(
                    root
                )  # type: ignore[assignment]
                excluded_elems = (
                    CSSSelector(self.exclude, namespaces=self.namespaces)(root)  # type: ignore[assignment]
                    if self.exclude
                    else None
                )

            elif self.filter_kind == 'xpath':
                selected_elems = root.xpath(self.expression, namespaces=self.namespaces)  # type: ignore[assignment]
                excluded_elems = (
                    root.xpath(self.exclude, namespaces=self.namespaces)  # type: ignore[assignment]
                    if self.exclude
                    else None
                )
        except (etree.ParserError, etree.XMLSchemaError, etree.XPathError) as e:
            raise ValueError(f'Job {job_index_number} {type(e).__name__}: {e} {self.expression}') from e
        if excluded_elems is not None:
            for el in excluded_elems:
                self._remove_element(el)
        if selected_elems is not None:
            return [el for el in map(self._reevaluate, selected_elems) if el is not None]
        else:
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

    __supported_subfilters__ = {
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

    __supported_subfilters__ = {
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


class ReSubFilter(FilterBase):
    """Replace text with regular expressions using Python's re.sub."""

    __kind__ = 're.sub'

    __supported_subfilters__ = {
        'pattern': 'Regular expression to search for (required)',
        'repl': 'Replacement string (default: empty string)',
    }

    __default_subfilter__ = 'pattern'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if 'pattern' not in subfilter:
            raise ValueError(f"The '{self.__kind__}' filter needs a pattern. ({self.job.get_indexed_location()})")

        # Default: Replace with empty string if no "repl" value is set
        return re.sub(subfilter['pattern'], subfilter.get('repl', ''), data), mime_type


class RegexFindall(FilterBase):
    """Extract text using regular expressions using Python's re.findall"""

    __kind__ = 're.findall'

    __supported_subfilters__ = {
        'pattern': 'Regular expression to search for (required)',
        'repl': "Replacement string applied iteratively to each match (default: '\\g<0>', or extract all matches)",
    }

    __default_subfilter__ = 'pattern'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'pattern' not in subfilter:
            raise ValueError(f"The '{self.__kind__}' filter needs a pattern. ({self.job.get_indexed_location()})")

        # Default: Replace with full match if no "repl" value is set
        return (
            '\n'.join(
                [match.expand(subfilter.get('repl', r'\g<0>')) for match in re.finditer(subfilter['pattern'], data)]
            ),
            mime_type,
        )


class SortFilter(FilterBase):
    """Sort input items."""

    __kind__ = 'sort'

    __supported_subfilters__ = {
        'reverse': 'Set to true to reverse sorting order',
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        if not isinstance(data, str):
            raise ValueError
        reverse = isinstance(subfilter, dict) and subfilter.get('reverse', False) is True
        separator = subfilter.get('separator', '\n')
        return separator.join(sorted(data.split(separator), key=str.casefold, reverse=reverse)), mime_type


class RemoveRepeatedFilter(FilterBase):
    """Remove repeated lines (uniq)."""

    __kind__ = 'remove_repeated'

    __supported_subfilters__ = {
        'separator': 'Item separator (default: newline)',
        'ignore_case': 'Ignore differences in case when comparing',
        'adjacent': 'Remove only adjacent lines or items (default: true)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        separator = subfilter.get('separator', '\n')
        ignore_case = subfilter.get('ignore_case', False)
        consecutive = subfilter.get('adjacent', True)
        data_lines = data.split(separator)
        uniq_lines = [data_lines[0]]
        if not ignore_case:
            for line in data_lines[1:]:
                if consecutive and line not in uniq_lines[-1]:
                    uniq_lines.append(line)
                elif line not in uniq_lines:
                    uniq_lines.append(line)
        else:
            past_lines = [data_lines[0].strip().lower()]
            for line in data_lines[1:]:
                if consecutive and line.strip().lower() not in past_lines[-1]:
                    past_lines.append(line.strip().lower())
                    uniq_lines.append(line)
                elif line.strip().lower() not in past_lines:
                    past_lines.append(line.strip().lower())
                    uniq_lines.append(line)

        return separator.join(uniq_lines), mime_type


class RemoveDuplicateLinesFilter(FilterBase):
    """Remove duplicate lines (case sensitive)."""

    __kind__ = 'remove-duplicate-lines'

    __supported_subfilters__ = {
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        separator = subfilter.get('separator', '\n')
        data_lines = data.split(separator)

        def get_unique_lines(lines: list[str]) -> Iterator[str]:
            seen = set()
            for line in lines:
                if line not in seen:
                    yield line
                    seen.add(line)

        return separator.join(get_unique_lines(data_lines)), mime_type


class ReverseFilter(FilterBase):
    """Reverse sort input items."""

    __kind__ = 'reverse'

    __supported_subfilters__ = {
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        separator = subfilter.get('separator', '\n')
        return separator.join(reversed(data.split(separator))), mime_type


def _pipe_filter(f_cls: FilterBase, data: str | bytes, subfilter: dict[str, Any]) -> str:
    if 'command' not in subfilter:
        raise ValueError(f"The '{f_cls.__kind__}' filter needs a command. ({f_cls.job.get_indexed_location()})")

    # Work on a copy of the environment as not to modify the outside environment
    env = os.environ.copy()
    env.update(
        {
            f'{__project_name__.upper()}_JOB_JSON': jsonlib.dumps(f_cls.job.to_dict()),
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
        return subprocess.run(  # type: ignore[no-any-return]
            command,
            input=data,
            capture_output=True,
            shell=shell,  # noqa: S602 subprocess call with shell=True identified, security issue.
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

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not mime_type.startswith('text'):
            mime_type = 'text/plain'
        return _pipe_filter(self, data, subfilter), mime_type


class ShellPipeFilter(FilterBase):
    """Filter using a shell command."""

    __kind__ = 'shellpipe'

    __supported_subfilters__ = {
        'command': 'Shell command to execute for filtering (required)',
    }

    __default_subfilter__ = 'command'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not mime_type.startswith('text'):
            mime_type = 'text/plain'
        return _pipe_filter(self, data, subfilter), mime_type


class OCRFilter(FilterBase):  # pragma: has-pytesseract
    """Convert text in images to plaintext (requires Python packages ``pytesseract`` and ``Pillow``)."""

    __kind__ = 'ocr'
    __uses_bytes__ = True

    __supported_subfilters__ = {
        'language': 'Language of the text (e.g. "fra" or "eng+fra")',
        'timeout': 'Timeout (in seconds) for OCR (default 10 seconds)',
    }

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, bytes):
            raise ValueError(
                f"The '{self.__kind__}' filter needs bytes input (is it the first filter?). "
                f'({self.job.get_indexed_location()})'
            )

        language = subfilter.get('language', None)
        timeout = int(subfilter.get('timeout', 10))

        if isinstance(Image, str):
            self.raise_import_error('PIL', self.__kind__, Image)

        if isinstance(pytesseract, str):
            self.raise_import_error('pytesseract', self.__kind__, pytesseract)

        return (
            pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=language, timeout=timeout).strip(),
            'text/plain',
        )


class JQFilter(FilterBase):  # pragma: has-jq
    """Parse, transform, and extract data from json as text using `jq`."""

    # contributed by robgmills https://github.com/thp/urlwatch/pull/626

    __kind__ = 'jq'

    __supported_subfilters__ = {
        'query': 'jq query function to execute on data',
    }

    __default_subfilter__ = 'query'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if 'query' not in subfilter:
            raise ValueError(f"The 'jq' filter needs a query. ({self.job.get_indexed_location()})")
        try:
            jsondata = jsonlib.loads(data)
        except ValueError:
            raise ValueError(f"The 'jq' filter needs valid JSON. ({self.job.get_indexed_location()})")

        if isinstance(jq, str):
            self.raise_import_error('jq', self.__kind__, jq)

        return jq.text(subfilter['query'], jsondata), 'text/plain'
        # Unicode solution is below https://github.com/mwilliamson/jq.py/issues/59
        # however it aborts execution(!) during testing
        # return '\n'.join(json.dumps(v, ensure_ascii=False) for v in (jq.compile(subfilter['query'], jsondata)))


class Ascii85(FilterBase):
    """Convert bytes data (e.g. images) into an ascii85 string.

    Ascii85 encoding is much more efficient than Base64.
    """

    __kind__ = 'ascii85'

    __no_subfilter__ = True

    __uses_bytes__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        data_to_encode = data.encode() if isinstance(data, str) else data
        return base64.a85encode(data_to_encode).decode(), 'text/plain'


class Base64(FilterBase):
    """Convert bytes data (e.g. images) into a base64 string.

    Base64 encoding causes an overhead of 33–37% relative to the size of the original binary data.
    """

    __kind__ = 'base64'

    __no_subfilter__ = True

    __uses_bytes__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        data_to_encode = data.encode() if isinstance(data, str) else data
        return base64.b64encode(data_to_encode).decode(), 'text/plain'


class JsontoYamlFilter(FilterBase):
    """Convert JSON to formatted YAML.  An alternative to format-json."""

    __kind__ = 'jsontoyaml'

    __supported_subfilters__ = {
        'indentation': 'Indentation level for pretty-printing',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        self.job.set_to_monospace()
        indentation = int(subfilter.get('indentation', 2))
        try:
            parsed_json = jsonlib.loads(data)
        except jsonlib.JSONDecodeError as e:
            return f"Filter '{self.__kind__}' returned JSONDecodeError: {e}\n\n{data!s}", mime_type
        if isinstance(parsed_json, list):
            yaml_data = yaml.safe_dump_all(
                parsed_json,
                indent=indentation,
                width=999,
                allow_unicode=True,
                line_break='\n',
                sort_keys=False,
            )
        else:
            yaml_data = yaml.safe_dump(
                parsed_json,
                indent=indentation,
                width=999,
                allow_unicode=True,
                line_break='\n',
                sort_keys=False,
            )
        return yaml_data, 'application/yaml'
