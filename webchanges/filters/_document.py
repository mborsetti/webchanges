"""Document/data format conversion filters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any, Literal

import yaml

from webchanges.filters._base import FilterBase

try:
    from pypdf import PdfReader
except ImportError as e:  # pragma: no cover
    PdfReader = str(e)  # ty:ignore[invalid-assignment]

try:
    import pdftotext  # ty:ignore[unresolved-import]
except ImportError as e:  # pragma: has-pdftotext
    pdftotext = str(e)

try:
    from PIL import Image
except ImportError as e:  # pragma: no cover
    Image = str(e)  # ty:ignore[invalid-assignment]

try:
    import pytesseract  # ty:ignore[unresolved-import]
except ImportError as e:  # pragma: has-pytesseract
    pytesseract = str(e)

try:
    import vobject.base
except ImportError as e:  # pragma: no cover
    vobject = str(e)  # ty:ignore[invalid-assignment]

try:
    import jq  # ty:ignore[unresolved-import]
except ImportError as e:  # pragma: has-jq
    jq = str(e)

logger = logging.getLogger(__name__)


class Csv2TextFilter(FilterBase):
    """Convert CSV to plaintext."""

    __kind__ = 'csv2text'

    __supported_subfilters__: dict[str, str] = {
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

        has_header = csv.Sniffer().has_header(data) if has_header_config is None else has_header_config

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
                legend = dict(zip(header, i, strict=False))
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

    __supported_subfilters__: dict[str, str] = {
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

        class RenamePypdfFilter(logging.Filter):
            """Function to rename logging name from '_.utils' to 'pypdf_utils'"""

            def filter(self, record: logging.LogRecord) -> bool:
                if record.name == 'pypdf._utils':
                    record.name = 'pypdf_utils'  # Change the displayed name
                return True

        # Rename logging name from '_.utils' to 'pypdf_utils'
        logger = logging.getLogger('pypdf._utils')
        logger.addFilter(RenamePypdfFilter())

        password = subfilter.get('password')
        extraction_mode: Literal['plain', 'layout'] = subfilter.get('extraction_mode', 'plain')

        if password:
            try:
                import cryptography  # noqa: F401 imported but unused
            except ImportError:  # pragma: no cover
                self.raise_import_error(
                    'cryptography',
                    f'password sub-directive of {self.__kind__}',
                    "Please install with 'uv pip install --upgrade webchanges[pypdf_crypto]'",
                )

        reader = PdfReader(io.BytesIO(data), password=password)
        logger.info(f'Job {self.job.index_number}: Found {reader.pdf_header} file')
        text = [page.extract_text(extraction_mode=extraction_mode) for page in reader.pages]

        return '\n'.join(text), 'text/plain'


class Pdf2TextFilter(FilterBase):  # pragma: has-pdftotext
    """Convert PDF to plaintext (requires Python package ``pdftotext`` and its dependencies)."""

    # Dependency: pdftotext (https://github.com/jalan/pdftotext), itself based
    # on poppler (https://poppler.freedesktop.org/)
    # Note: check pdftotext website for OS-specific dependencies for install

    __kind__ = 'pdf2text'
    __uses_bytes__ = True

    __supported_subfilters__: dict[str, str] = {
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
                pdftotext.PDF(  # ty:ignore[unresolved-attribute]
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
            parsed_cal = vobject.base.readOne(data)
        else:
            try:
                parsed_cal = vobject.base.readOne(data)
            except vobject.base.ParseError:
                parsed_cal = vobject.base.readOne(data.decode(errors='ignore'))
                logger.warning('Found and ignored Unicode-related errors when reading iCal entry.')

        for event in parsed_cal.getChildren():
            if event.name == 'VEVENT':
                if hasattr(event, 'dtstart'):
                    start_date = event.dtstart.value.strftime('%F %H:%M')
                else:
                    start_date = 'unknown start date'

                end_date = event.dtend.value.strftime('%F %H:%M') if hasattr(event, 'dtend') else start_date
                date_str = start_date if start_date == end_date else f'{start_date} -- {end_date}'

                result.append(f'{date_str}: {event.summary.value}')

        return '\n'.join(result), 'text/plain'


class OCRFilter(FilterBase):  # pragma: has-pytesseract
    """Convert text in images to plaintext (requires Python packages ``pytesseract`` and ``Pillow``)."""

    __kind__ = 'ocr'
    __uses_bytes__ = True

    __supported_subfilters__: dict[str, str] = {
        'language': 'Language of the text (e.g. "fra" or "eng+fra")',
        'timeout': 'Timeout (in seconds) for OCR (default 10 seconds)',
    }

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, bytes):
            raise ValueError(
                f"The '{self.__kind__}' filter needs bytes input (is it the first filter?). "
                f'({self.job.get_indexed_location()})'
            )

        language = subfilter.get('language')
        timeout = int(subfilter.get('timeout', 10))

        if isinstance(Image, str):
            self.raise_import_error('PIL', self.__kind__, Image)

        if isinstance(pytesseract, str):
            self.raise_import_error('pytesseract', self.__kind__, pytesseract)

        return (
            pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=language, timeout=timeout).strip(),  # ty:ignore[unresolved-attribute]
            'text/plain',
        )


class JQFilter(FilterBase):  # pragma: has-jq
    """Parse, transform, and extract data from json as text using `jq`."""

    # contributed by robgmills https://github.com/thp/urlwatch/pull/626

    __kind__ = 'jq'

    __supported_subfilters__: dict[str, str] = {
        'query': 'jq query function to execute on data',
    }

    __default_subfilter__ = 'query'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if 'query' not in subfilter:
            raise ValueError(f"The 'jq' filter needs a query. ({self.job.get_indexed_location()})")
        try:
            jsondata = json.loads(data)
        except ValueError:
            raise ValueError(f"The 'jq' filter needs valid JSON. ({self.job.get_indexed_location()})")  # noqa: B904

        if isinstance(jq, str):
            self.raise_import_error('jq', self.__kind__, jq)

        return jq.text(subfilter['query'], jsondata), 'text/plain'  # ty:ignore[unresolved-attribute]
        # Unicode solution is below https://github.com/mwilliamson/jq.py/issues/59
        # however it aborts execution(!) during testing
        # return '\n'.join(json.dumps(v, ensure_ascii=False) for v in (jq.compile(subfilter['query'], jsondata)))


class FormatJsonFilter(FilterBase):
    """Convert to formatted JSON."""

    __kind__ = 'format-json'

    __supported_subfilters__: dict[str, str] = {
        'indentation': 'Indentation level for pretty-printing',
        'sort_keys': 'Sort the output of dictionaries by key',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        self.job.set_to_monospace()
        sort_keys = subfilter.get('sort_keys', False)
        indentation = int(subfilter.get('indentation', 4))
        try:
            parsed_json = json.loads(data)
        except json.JSONDecodeError as e:
            return (
                json.dumps(
                    f"ERROR: Filter '{self.__kind__}' returned 'JSONDecodeError: {e}' on the following data:\n\n"
                    f'{data!s}',
                    ensure_ascii=False,
                ),
                'application/json',
            )
        if not mime_type.endswith('json'):
            mime_type = 'application/json'
        return json.dumps(parsed_json, ensure_ascii=False, sort_keys=sort_keys, indent=indentation), mime_type


class JsontoYamlFilter(FilterBase):
    """Convert JSON to formatted YAML.  An alternative to format-json."""

    __kind__ = 'jsontoyaml'

    __supported_subfilters__: dict[str, str] = {
        'indentation': 'Indentation level for pretty-printing',
    }

    __default_subfilter__ = 'indentation'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        self.job.set_to_monospace()
        indentation = int(subfilter.get('indentation', 2))
        try:
            parsed_json = json.loads(data)
        except json.JSONDecodeError as e:
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
