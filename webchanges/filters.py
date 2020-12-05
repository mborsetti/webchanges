import hashlib
import html.parser
import io
import itertools
import json
import logging
import os
import re
import subprocess
import sys
from enum import Enum

import html2text
import yaml
from appdirs import AppDirs
from lxml import etree  # noqa:DUO107 insecure use of XML modules, prefer "defusedxml"
from lxml.cssselect import CSSSelector  # noqa:DUO107 insecure use of XML modules, prefer "defusedxml"

from .util import TrackSubClasses, import_module_from_source

logger = logging.getLogger(__name__)


class FilterBase(object, metaclass=TrackSubClasses):
    __subclasses__ = {}
    __anonymous_subclasses__ = []

    def __init__(self, job, state):
        self.job = job
        self.state = state

    @classmethod
    def filter_documentation(cls):
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
    def auto_process(cls, state, data):
        filters = itertools.chain((filtercls for _, filtercls in
                                   sorted(cls.__subclasses__.items(), key=lambda k_v: k_v[0])),
                                  cls.__anonymous_subclasses__)

        for filtercls in filters:
            filter_instance = filtercls(state.job, state)
            if filter_instance.match():
                logger.info('Auto-applying filter %r to %s', filter_instance, state.job.get_location())
                data = filter_instance.filter(data, None)  # all filters take a subfilter

        return data

    @classmethod
    def normalize_filter_list(cls, filter_spec):
        for filter_kind, subfilter in cls._internal_normalize_filter_list(filter_spec):
            filtercls = cls.__subclasses__.get(filter_kind, None)

            if filtercls is None:
                raise ValueError(f'Unknown filter kind: {filter_kind} (subfilter {subfilter})')

            if getattr(filtercls, '__no_subfilter__', False) and subfilter:
                raise ValueError(f'No subfilters supported for {filter_kind}')

            if isinstance(subfilter, dict) and hasattr(filtercls, '__supported_subfilters__'):
                provided_keys = set(subfilter.keys())
                allowed_keys = set(filtercls.__supported_subfilters__.keys())
                unknown_keys = provided_keys.difference(allowed_keys)
                if unknown_keys and '<any>' not in allowed_keys:
                    raise ValueError(f'Filter "{filter_kind}" does not support subfilter(s): {unknown_keys} '
                                     f'(supported: {allowed_keys})')

            yield filter_kind, subfilter

    @classmethod
    def _internal_normalize_filter_list(cls, filter_spec):
        if isinstance(filter_spec, str):
            old_filter_spec = filter_spec

            # Legacy string-based filter list specification:
            # "filter1:param1,filter2,filter3,filter4:param4"
            filter_spec = [dict([filter_kind.split(':', 1)]) if ':' in filter_kind else filter_kind
                           for filter_kind in filter_spec.split(',')]

            logger.warning('String-based filter definitions (%s) are deprecated, please convert to dict-style:\n\n%s',
                           old_filter_spec, yaml.safe_dump(filter_spec, default_flow_style=False))

        if isinstance(filter_spec, list):
            for item in filter_spec:
                if isinstance(item, str):
                    filter_kind, subfilter = item, None
                elif isinstance(item, dict):
                    filter_kind, subfilter = next(iter(item.items()))

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
    def process(cls, filter_kind, subfilter, state, data):
        logger.info('Applying filter %r, subfilter %r to %s', filter_kind, subfilter, state.job.get_location())
        filtercls = cls.__subclasses__.get(filter_kind, None)
        return filtercls(state.job, state).filter(data, subfilter)

    @classmethod
    def filter_chain_needs_bytes(cls, filter):
        # If the first filter is a bytes filter, return content in bytes instead of
        # in unicode as that's what's required by the library used by that filter
        first_filter = next(cls.normalize_filter_list(filter), None)
        if first_filter is not None:
            filter_kind, subfilter = first_filter
            return cls.is_bytes_filter_kind(filter_kind)

        return False

    @classmethod
    def is_bytes_filter_kind(cls, filter_kind):
        return (filter_kind in [name for name, class_ in cls.__subclasses__.items()
                                if getattr(class_, '__uses_bytes__', False)])

    def match(self):
        return False

    def filter(self, data, subfilter):
        raise NotImplementedError()


class AutoMatchFilter(FilterBase):
    """Automatically matches subclass filters with a given location"""
    MATCH = None

    def match(self):
        if self.MATCH is None:
            return False

        d = self.job.to_dict()
        result = all(d.get(k, None) == v for k, v in self.MATCH.items())
        logger.debug('Matching %r with %r result: %r', self, self.job, result)
        return result


class RegexMatchFilter(FilterBase):
    """Same as AutoMatchFilter but matching is done with regexes"""
    MATCH = None

    def match(self):
        if self.MATCH is None:
            return False

        d = self.job.to_dict()

        # It's a match if we have at least one key/value pair that matches,
        # and no key/value pairs that do not match
        matches = [v.match(d[k]) for k, v in self.MATCH.items() if k in d]
        result = len(matches) > 0 and all(matches)
        logger.debug('Matching %r with %r result: %r', self, self.job, result)
        return result


class LegacyHooksPyFilter(FilterBase):
    """Loads custom filters (classes) in lib/hooks.py file"""
    def __init__(self, job, state):
        super().__init__(job, state)

        self.hooks = None
        # TODO urlwatch_dir should not be recreated here (code from cli.py)
        pkgname = 'urlwatch'
        if os.name != 'nt':
            urlwatch_dir = os.path.expanduser(os.path.join('~', '.' + pkgname))
        else:
            urlwatch_dir = os.path.expanduser(os.path.join('~', 'Documents', pkgname))
        if not os.path.exists(urlwatch_dir):
            urlwatch_dir = AppDirs(pkgname).user_config_dir
        FILENAME = os.path.join(urlwatch_dir, 'lib', 'hooks.py')
        if os.path.exists(FILENAME):
            try:
                self.hooks = import_module_from_source('legacy_hooks', FILENAME)
            except Exception as e:
                logger.error('Could not load legacy hooks file: %s', e)

    def match(self):
        return self.hooks is not None

    def filter(self, data):
        try:
            result = self.hooks.filter(self.job.get_location(), data)
            if result is None:
                result = data
            return result
        except Exception as e:
            logger.warning('Could not apply legacy hooks filter: %s', e)
            return data


class BeautifyFilter(FilterBase):
    """Beautify HTML (requires Python package 'BeautifulSoup' and optionally 'jsbeautifier' and/or 'cssbeautifier')"""

    __kind__ = 'beautify'

    __no_subfilter__ = True

    def filter(self, data, subfilter):
        try:
            from bs4 import BeautifulSoup as bs
        except ImportError:
            raise ImportError(f'Python package "BeautifulSoup" is not installed; cannot use the "beautify" filter'
                              f' ( {self.job.get_location()} )')

        soup = bs(data, features="lxml")

        try:
            import jsbeautifier
        except ImportError:
            logger.info(f'Python package "jsbeautifier" is not installed; will not beautify <script> tags'
                        f' ( {self.job.get_location()} )')
            jsbeautifier = None

        if jsbeautifier:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    beautified_js = jsbeautifier.beautify(script.string)
                    script.string = beautified_js

        try:
            import cssbeautifier
        except ImportError:
            logger.info('Python package "cssbeautifier" is not installed; will not beautify <style> tags')
            cssbeautifier = None

        if cssbeautifier:
            styles = soup.find_all('style')
            for style in styles:
                if style.string:
                    beautified_css = cssbeautifier.beautify(style.string)
                    style.string = beautified_css

        return soup.prettify()


class Html2TextFilter(FilterBase):
    """Convert HTML to Markdown text"""

    __kind__ = 'html2text'

    __supported_subfilters__ = {
        'method': 'Method to use for conversion (html2text [default], bs4, or strip_tags)',
        '<any>': 'Method-specific options passed to html2text',
    }

    __default_subfilter__ = 'method'

    def filter(self, data, subfilter):
        """
        Convert a string consisting of HTML to plain text
        for easy difference checking.

        Method may be one of:
         'html2text'      - (DEFAULT): Use html2text library to extract text (in Markdown) from html.
                            options: https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options
                            default options optimized as follows: parser.unicode_snob = True,
                            parser.body_width = 0, parser.single_line_break = True, parser.ignore_images = True
         'bs4'            - Use Beautiful Soup library to prettify the HTML
                            options: "parser" only, bs4 supports "lxml", "html5lib", and "html.parser"
                            https://www.crummy.com/software/BeautifulSoup/bs4/doc/#specifying-the-parser-to-use
         'strip_tags'     - A simple regex-based HTML tag stripper
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
                logger.warning(f"filter html2text's method 'pyhtml2text' is deprecated: replace with 'html2text'"
                               f"(or remove method as it's now the filter's default) ( {self.job.get_location()} )")
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

            d = parser.handle(data)

            return d

        elif method == 'bs4':
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                raise ImportError(f'Python package "BeautifulSoup" is not installed; cannot use the "html2text: bs4"'
                                  f' filter ( {self.job.get_location()} )')
            parser = options.pop('parser', 'lxml')
            soup = BeautifulSoup(data, parser)
            d = soup.get_text(strip=True)
            return d

        elif method in ('strip_tags', 're'):  # re for backward compatibility
            if method == 're':
                logger.warning(f"filter html2text's method 're' is deprecated: replace with 'strip_tags'"
                               f"( {self.job.get_location()} )")
            stripped_tags = re.sub(r'<[^>]*>', '', data)
            d = '\n'.join((line.rstrip() for line in stripped_tags.splitlines() if line.strip() != ''))
            return d

        elif method == 'lynx':
            logger.error(f"'filter html2text's method 'lynx' is no longer supported."
                         f" ( {self.job.get_location()} )")

        else:
            raise ValueError(f'Unknown filter html2text method: {method!r} ( {self.job.get_location()} )')


class Pdf2TextFilter(FilterBase):
    """Convert PDF to plaintext (requires Python package 'pdftotext' and its dependencies)"""
    # Dependency: pdftotext (https://github.com/jalan/pdftotext), itself based
    # on poppler (https://poppler.freedesktop.org/)
    # Note: check pdftotext website for OS-specific dependencies for install

    __kind__ = 'pdf2text'
    __uses_bytes__ = True  # Requires data to be in bytes (not unicode)

    __supported_subfilters__ = {
        'password': 'PDF password for decryption',
    }

    def filter(self, data, subfilter):
        # data must be bytes
        if not isinstance(data, bytes):
            raise ValueError(f'The "html2text: pdf2text" filter needs bytes input (is it the first filter?)'
                             f' ( {self.job.get_location()} )')

        try:
            import pdftotext
        except ImportError:
            raise ImportError(f'Python package "pdftotext" (and OS-specific dependencies) is not installed; cannot use'
                              f' "html2text: pdf2text" filter ( {self.job.get_location()} )')
        return '\n\n'.join(pdftotext.PDF(io.BytesIO(data), password=subfilter.get('password', '')))


class Ical2TextFilter(FilterBase):
    """Convert iCalendar to plaintext (requires Python package 'vobject')"""

    __kind__ = 'ical2text'

    __no_subfilter__ = True

    def filter(self, data, subfilter):
        try:
            import vobject
        except ImportError:
            raise ImportError(f'Python package "vobject" is not installed; cannot use "html2text: ical2text" filter'
                              f' ( {self.job.get_location()} )')
        result = []
        if isinstance(data, str):
            parsedCal = vobject.readOne(data)
        else:
            try:
                parsedCal = vobject.readOne(data)
            except Exception:
                parsedCal = vobject.readOne(data.decode('utf-8', 'ignore'))

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
    """Convert to formatted JSON"""

    __kind__ = 'format-json'

    __supported_subfilters__ = {
        'indentation': 'Indentation level for pretty-printing',
        'sort_keys': 'Sort the output of dictionaries by key',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data, subfilter):
        indentation = int(subfilter.get('indentation', 4))
        sort_keys = int(subfilter.get('sort_keys', False))
        parsed_json = json.loads(data)
        return json.dumps(parsed_json, ensure_ascii=False, sort_keys=sort_keys, indent=indentation,
                          separators=(',', ': '))


class XMLFormatFilter(FilterBase):
    """Convert to formatted XML"""

    __kind__ = 'format-xml'

    __no_subfilter__ = True

    # __supported_subfilters__ = {
    #     'indentation': 'Indentation level for pretty-printing',
    # }
    #
    # __default_subfilter__ = 'indentation'

    def filter(self, data, subfilter):
        parsed_xml = etree.XML(data)
        return etree.tostring(parsed_xml, encoding='unicode', pretty_print=True)


class KeepLinesFilter(FilterBase):
    """Filter only lines matching a regular expression"""

    __kind__ = 'keep_lines_containing'

    __supported_subfilters__ = {
        'text': 'Lines matching this text are kept (default)',
        're': 'Lines matching this expression are kept',
    }

    __default_subfilter__ = 'text'

    def filter(self, data, subfilter):
        if 'text' in subfilter:
            return '\n'.join(line for line in data.splitlines() if subfilter['text'] in line)
        if 're' in subfilter:
            return '\n'.join(line for line in data.splitlines() if re.search(subfilter['re'], line))
        else:
            raise ValueError(f'The keep_lines_containing filter needs a text or re expression'
                             f' ( {self.job.get_location()} )')


class GrepFilter(FilterBase):
    """Deprecated; use keep_lines_containing instead"""

    __kind__ = 'grep'

    __supported_subfilters__ = {
        're': 'Lines matching this expression are kept (required)',
    }

    __default_subfilter__ = 're'

    def filter(self, data, subfilter):
        from warnings import warn
        warn(f"'grep' filter is deprecated; replace with 'keep_lines_containing' (+ 're' subfilter)"
             f" ( {self.job.get_location()} )", DeprecationWarning)
        return KeepLinesFilter.filter(self, data, subfilter)


class DeleteLinesFilter(FilterBase):
    """Remove lines matching a regular expression"""

    __kind__ = 'delete_lines_containing'

    __supported_subfilters__ = {
        'text': 'Lines matching this text are deleted (default)',
        're': 'Lines matching this expression deleted kept',
    }

    __default_subfilter__ = 'text'

    def filter(self, data, subfilter):
        if 'text' in subfilter:
            return '\n'.join(line for line in data.splitlines() if subfilter['text'] not in line)
        if 're' in subfilter:
            return '\n'.join(line for line in data.splitlines() if re.search(subfilter['re'], line) is None)
        else:
            raise ValueError(f'The delete_lines_containing filter needs a text or re expression'
                             f' ( {self.job.get_location()} )')


class InverseGrepFilter(FilterBase):
    """Deprecated; use delete_lines_containing instead"""

    __kind__ = 'grepi'

    __supported_subfilters__ = {
        're': 'Lines matching this expression are removed (required)',
    }

    __default_subfilter__ = 're'

    def filter(self, data, subfilter):
        from warnings import warn
        warn(f"'grepi' filter is deprecated; replace with 'delete_lines_containing (+ 're' subfilter')"
             f" ( {self.job.get_location()} )", DeprecationWarning)
        return DeleteLinesFilter.filter(self, data, subfilter)


class StripFilter(FilterBase):
    """Strip leading and trailing whitespace"""

    __kind__ = 'strip'

    __no_subfilter__ = True

    def filter(self, data, subfilter):
        return data.strip()


class StripEmptyLines(FilterBase):
    """Strip leading and trailing whitespace"""

    __kind__ = 'strip_empty_lines'

    __no_subfilter__ = True

    def filter(self, data, subfilter):
        return '\n'.join([line for line in data.splitlines() if line.strip()])


class FilterBy(Enum):
    ATTRIBUTE = 1
    TAG = 2


class ElementsBy(html.parser.HTMLParser):
    def __init__(self, filter_by, name, value=None):
        super().__init__()

        self._filter_by = filter_by
        if self._filter_by == FilterBy.ATTRIBUTE:
            self._attributes = {name: value}
        else:
            self._name = name

        self._result = []
        self._inside = False
        self._elts = []

    def get_html(self):
        return ''.join(self._result)

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)

        if self._filter_by == FilterBy.ATTRIBUTE and all(ad.get(k, None) == v for k, v in self._attributes.items()):
            self._inside = True
        elif self._filter_by == FilterBy.TAG and tag == self._name:
            self._inside = True

        if self._inside:
            self._result.append('<%s%s%s>' % (tag, ' ' if attrs else '', ' '.join(f'{k}="{v}"' for k, v in attrs)))
            self._elts.append(tag)

    def handle_endtag(self, tag):
        if self._inside:
            self._result.append(f'</{tag}>')
            if tag in self._elts:
                t = self._elts.pop()
                while t != tag and self._elts:
                    t = self._elts.pop()
            if not self._elts:
                self._inside = False

    def handle_data(self, data):
        if self._inside:
            self._result.append(data)


class GetElementById(FilterBase):
    """Get an HTML element by its ID"""

    __kind__ = 'element-by-id'

    __supported_subfilters__ = {
        'id': 'ID of the element to filter for (required)',
    }

    __default_subfilter__ = 'id'

    def filter(self, data, subfilter):
        if 'id' not in subfilter:
            raise ValueError(f'Need an element ID for filtering ( {self.job.get_location()} )')

        element_by_id = ElementsBy(FilterBy.ATTRIBUTE, 'id', subfilter['id'])
        element_by_id.feed(data)
        return element_by_id.get_html()


class GetElementByClass(FilterBase):
    """Get all HTML elements by class"""

    __kind__ = 'element-by-class'

    __supported_subfilters__ = {
        'class': 'HTML class attribute to filter for (required)',
    }

    __default_subfilter__ = 'class'

    def filter(self, data, subfilter):
        if 'class' not in subfilter:
            raise ValueError(f'Need an element class for filtering ( {self.job.get_location()} )')

        element_by_class = ElementsBy(FilterBy.ATTRIBUTE, 'class', subfilter['class'])
        element_by_class.feed(data)
        return element_by_class.get_html()


class GetElementByStyle(FilterBase):
    """Get all HTML elements by style"""

    __kind__ = 'element-by-style'

    __supported_subfilters__ = {
        'style': 'HTML style attribute value to filter for (required)',
    }

    __default_subfilter__ = 'style'

    def filter(self, data, subfilter):
        if 'style' not in subfilter:
            raise ValueError(f'Need an element style for filtering ( {self.job.get_location()} )')

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

    def filter(self, data, subfilter):
        if 'tag' not in subfilter:
            raise ValueError(f'Need a tag for filtering ( {self.job.get_location()} )')

        element_by_tag = ElementsBy(FilterBy.TAG, subfilter['tag'])
        element_by_tag.feed(data)
        return element_by_tag.get_html()


class Sha1Filter(FilterBase):
    """Calculate the SHA-1 checksum of the content"""

    __kind__ = 'sha1sum'

    __no_subfilter__ = True

    def filter(self, data, subfilter):
        sha = hashlib.sha1()  # noqa:DUO130 insecure use of "hashlib" module
        sha.update(data.encode('utf-8', 'ignore'))
        return sha.hexdigest()


class HexdumpFilter(FilterBase):
    """Convert binary data to hex dump format"""

    __kind__ = 'hexdump'

    __no_subfilter__ = True

    def filter(self, data, subfilter):
        data = bytearray(data.encode('utf-8', 'ignore'))
        blocks = [data[i * 16:(i + 1) * 16] for i in range(int((len(data) + (16 - 1)) / 16))]
        return '\n'.join('%s  %s' % (' '.join('%02x' % c for c in block),
                                     ''.join((chr(c) if (c > 31 and c < 127) else '.')
                                             for c in block)) for block in blocks)


class LxmlParser:
    EXPR_NAMES = {'css': 'a CSS selector',
                  'xpath': 'an XPath expression'}

    def __init__(self, filter_kind, subfilter, expr_key):
        self.filter_kind = filter_kind
        if expr_key not in subfilter:
            raise ValueError(f'Need {self.EXPR_NAMES[filter_kind]} for filtering ( {self.job.get_location()} )')
        self.expression = subfilter[expr_key]
        self.method = subfilter.get('method', 'html')
        self.exclude = subfilter.get('exclude')
        self.namespaces = subfilter.get('namespaces')
        self.skip = int(subfilter.get('skip', 0))
        self.maxitems = int(subfilter.get('maxitems', 0))
        if self.method not in ('html', 'xml'):
            raise ValueError(f'{filter_kind} method must be "html" or "xml", got {self.method!r}'
                             f' ( {self.job.get_location()} )')
        if self.method == 'html' and self.namespaces:
            raise ValueError(f'Namespace prefixes only supported with "xml" method'
                             f' ( {self.job.get_location()} )')
        self.parser = (etree.HTMLParser if self.method == 'html' else etree.XMLParser)()
        self.data = ''

    def feed(self, data):
        self.data += data

    def _to_string(self, element):
        # Handle "/text()" selector, which returns lxml.etree._ElementUnicodeResult (Issue #282)
        if isinstance(element, str):
            return element

        return etree.tostring(element, pretty_print=True, encoding='unicode', with_tail=False).strip()

    @staticmethod
    def _remove_element(element):
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

    def _reevaluate(self, element):
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

    def _orphaned(self, element):
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

    def _get_filtered_elements(self):
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

    def get_filtered_data(self):
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
    """Filter XML/HTML using CSS selectors"""

    __kind__ = 'css'

    __supported_subfilters__ = {
        'selector': 'The CSS selector to use for filtering (required)',
        **LXML_PARSER_COMMON_SUBFILTERS,
    }

    __default_subfilter__ = 'selector'

    def filter(self, data, subfilter):
        lxml_parser = LxmlParser('css', subfilter, 'selector')
        lxml_parser.feed(data)
        return lxml_parser.get_filtered_data()


class XPathFilter(FilterBase):
    """Filter XML/HTML using XPath expressions"""

    __kind__ = 'xpath'

    __supported_subfilters__ = {
        'path': 'The XPath to use for filtering (required)',
        **LXML_PARSER_COMMON_SUBFILTERS,
    }

    __default_subfilter__ = 'path'

    def filter(self, data, subfilter):
        lxml_parser = LxmlParser('xpath', subfilter, 'path')
        lxml_parser.feed(data)
        return lxml_parser.get_filtered_data()


class RegexSub(FilterBase):
    """Replace text with regular expressions using Python's re.sub"""

    __kind__ = 're.sub'

    __supported_subfilters__ = {
        'pattern': 'Regular expression to search for (required)',
        'repl': 'Replacement string (default: empty string)',
    }

    __default_subfilter__ = 'pattern'

    def filter(self, data, subfilter):
        if 'pattern' not in subfilter:
            raise ValueError(f'{self.__kind__} needs a pattern ( {self.job.get_location()} )')

        # Default: Replace with empty string if no "repl" value is set
        return re.sub(subfilter['pattern'], subfilter.get('repl', ''), data)


class SortFilter(FilterBase):
    """Sort input items"""

    __kind__ = 'sort'

    __supported_subfilters__ = {
        'reverse': 'Set to true to reverse sorting order',
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data, subfilter):
        reverse = (isinstance(subfilter, dict) and subfilter.get('reverse', False) is True)
        separator = subfilter.get('separator', '\n')
        return separator.join(sorted(data.split(separator), key=str.casefold, reverse=reverse))


class ReverseFilter(FilterBase):
    """Reverse input items"""

    __kind__ = 'reverse'

    __supported_subfilters__ = {
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data, subfilter):
        separator = subfilter.get('separator', '\n')
        return separator.join(reversed(data.split(separator)))


class ShellPipeFilter(FilterBase):
    """Filter using a shell command"""

    __kind__ = 'shellpipe'

    __supported_subfilters__ = {
        'command': 'Shell command to execute for filtering (required)',
    }

    __default_subfilter__ = 'command'

    def filter(self, data, subfilter):
        if 'command' not in subfilter:
            raise ValueError(f'{self.__kind__} filter needs a command ( {self.job.get_location()} )')

        encoding = sys.getdefaultencoding()

        # Work on a copy to not modify the outside environment
        env = dict(os.environ)
        env.update({
            'URLWATCH_JOB_NAME': self.job.pretty_name() if self.job else '',
            'URLWATCH_JOB_LOCATION': self.job.get_location() if self.job else '',
        })

        return subprocess.check_output(subfilter['command'], shell=True,  # noqa:DUO116 use of "shell=True" is insecure
                                       input=data.encode(encoding), env=env).decode(encoding)


class OCRFilter(FilterBase):
    """Convert text in images to plaintext (requires Python packages 'pytesseract' and 'Pillow")"""

    __kind__ = 'ocr'
    __uses_bytes__ = True

    __supported_subfilters__ = {
        'language': 'Language of the text (e.g. "fra" or "eng+fra")',
        'timeout': 'Timeout (in seconds) for OCR (default 10 seconds)',
    }

    def filter(self, data, subfilter):
        if not isinstance(data, bytes):
            raise ValueError(f'The ocr filter needs bytes input (is it the first filter?)'
                             f' ( {self.job.get_location()} )')

        language = subfilter.get('language', None)
        timeout = int(subfilter.get('timeout', 10))

        try:
            import pytesseract
        except ImportError:
            raise ImportError(f'Python package "pytesseract" is not installed; cannot use the "ocr" filter'
                              f' ( {self.job.get_location()} )')
        try:
            from PIL import Image
        except ImportError:
            raise ImportError(f'Python package "Pillow" is not installed; cannot use the "ocr" filter'
                              f' ( {self.job.get_location()} )')
        return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=language, timeout=timeout)
