"""Differs."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import base64
import difflib
import html
import logging
import math
import os
import re
import shlex
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.
import tempfile
import traceback
import urllib.parse
import warnings
from base64 import b64encode
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator, Literal, Optional, TYPE_CHECKING
from zoneinfo import ZoneInfo

import html2text

from webchanges.util import linkify, mark_to_html, TrackSubClasses

try:
    from deepdiff import DeepDiff
    from deepdiff.model import DiffLevel
except ImportError as e:  # pragma: no cover
    DeepDiff = e.msg  # type: ignore[no-redef]

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
    import numpy as np
except ImportError as e:  # pragma: no cover
    np = e.msg  # type: ignore[assignment]

try:
    from PIL import Image, ImageChops, ImageEnhance, ImageStat
except ImportError as e:  # pragma: no cover
    Image = e.msg  # type: ignore[no-redef]

# https://stackoverflow.com/questions/712791
try:
    import simplejson as jsonlib
except ImportError:  # pragma: no cover
    import json as jsonlib  # type: ignore[no-redef]

try:
    import xmltodict
except ImportError as e:  # pragma: no cover
    xmltodict = e.msg  # type: ignore[no-redef]

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.handler import JobState


logger = logging.getLogger(__name__)


class DifferBase(metaclass=TrackSubClasses):
    """The base class for differs."""

    __subclasses__: dict[str, type[DifferBase]] = {}
    __anonymous_subclasses__: list[type[DifferBase]] = []

    __kind__: str = ''

    __supported_directives__: dict[str, str] = {}  # this must be present, even if empty

    css_added_style = 'background-color:#d1ffd1;color:#082b08;'
    css_deltd_style = 'background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;'

    def __init__(self, state: JobState) -> None:
        """

        :param state: the JobState.
        """
        self.job = state.job
        self.state = state

    @classmethod
    def differ_documentation(cls) -> str:
        """Generates simple differ documentation for use in the --features command line argument.

        :returns: A string to display.
        """
        result: list[str] = []
        for sc in TrackSubClasses.sorted_by_kind(cls):
            # default_subdirective = getattr(sc, '__default_subdirective__', None)
            result.extend((f'  * {sc.__kind__} - {sc.__doc__}',))
            if hasattr(sc, '__supported_directives__'):
                for key, doc in sc.__supported_directives__.items():
                    result.append(f'      {key} ... {doc}')
        result.append('\n[] ... Parameter can be supplied as unnamed value\n')
        return '\n'.join(result)

    @classmethod
    def normalize_differ(
        cls,
        differ_spec: Optional[dict[str, Any]],
        job_index_number: Optional[int] = None,
    ) -> tuple[str, dict[str, Any]]:
        """Checks the differ_spec for its validity and applies default values.

        :param differ_spec: The differ as entered by the user; use "unified" if empty.
        :param job_index_number: The job index number.
        :returns: A validated differ_kind, subdirectives (where subdirectives is a dict).
        """
        differ_spec = differ_spec or {'name': 'unified'}
        subdirectives = differ_spec.copy()
        differ_kind = subdirectives.pop('name', '')
        if not differ_kind:
            if list(subdirectives.keys()) == ['command']:
                differ_kind = 'command'
            else:
                raise ValueError(
                    f"Job {job_index_number}: Differ directive must have a 'name' sub-directive: {differ_spec}."
                )

        differcls = cls.__subclasses__.get(differ_kind, None)
        if not differcls:
            raise ValueError(f'Job {job_index_number}: No differ named {differ_kind}.')

        if hasattr(differcls, '__supported_directives__'):
            provided_keys = set(subdirectives.keys())
            allowed_keys = set(differcls.__supported_directives__.keys())
            unknown_keys = provided_keys.difference(allowed_keys)
            if unknown_keys and '<any>' not in allowed_keys:
                raise ValueError(
                    f'Job {job_index_number}: Differ {differ_kind} does not support sub-directive(s) '
                    f"{', '.join(unknown_keys)} (supported: {', '.join(sorted(allowed_keys))})."
                )

        return differ_kind, subdirectives

    @classmethod
    def process(
        cls,
        differ_kind: str,
        directives: dict[str, Any],
        job_state: JobState,
        report_kind: Literal['text', 'markdown', 'html'] = 'text',
        tz: Optional[str] = None,
        _unfiltered_diff: Optional[dict[Literal['text', 'markdown', 'html'], str]] = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        """Process the differ.

        :param differ_kind: The name of the differ.
        :param directives: The directives.
        :param job_state: The JobState.
        :param report_kind: The report kind required.
        :param tz: The timezone of the report.
        :param _unfiltered_diff: Any previous diffs generated by the same filter, who can be used to generate a diff
           for a different report_kind.
        :returns: The output of the differ.
        """
        logger.info(f'Job {job_state.job.index_number}: Applying differ {differ_kind}, directives {directives}')
        differcls: Optional[type[DifferBase]] = cls.__subclasses__.get(differ_kind)  # type: ignore[assignment]
        if differcls:
            return differcls(job_state).differ(directives, report_kind, _unfiltered_diff, tz)
        else:
            return {}

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: Optional[dict[Literal['text', 'markdown', 'html'], str]] = None,
        tz: Optional[str] = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        """Create a diff from the data. Since this function could be called by different reporters of multiple report
        types ('text', 'markdown', 'html'), the differ outputs a dict with data for the report_kind it generated so
        that it can be reused.

        :param directives: The directives.
        :param report_kind: The report_kind for which a diff must be generated (at a minimum).
        :param _unfiltered_diff: Any previous diffs generated by the same filter, who can be used to generate a diff
           for a different report_kind.
        :param tz: The timezone of the report.
        :returns: An empty dict if there is no change, otherwise a dict with report_kind as key and diff as value
           (as a minimum for the report_kind requested).
        :raises RuntimeError: If the external diff tool returns an error.
        """
        raise NotImplementedError()

    @staticmethod
    def make_timestamp(
        timestamp: float,
        tz: Optional[str] = None,
    ) -> str:
        """Creates a datetime string in RFC 5322 (email) format with the time zone name (if available) in the
        Comments and Folding White Space (CFWS) section.

        :param timestamp: The timestamp.
        :param tz: The IANA timezone of the report.
        :returns: A datetime string in RFC 5322 (email) format.
        """
        if timestamp:
            if tz:
                tz_info: Optional[ZoneInfo] = ZoneInfo(tz)
            else:
                tz_info = None
            dt = datetime.fromtimestamp(timestamp).astimezone(tz=tz_info)
            # add timezone name if known
            if dt.strftime('%Z') != dt.strftime('%z')[:3]:
                cfws = f" ({dt.strftime('%Z')})"
            else:
                cfws = ''
            return dt.strftime('%a, %d %b %Y %H:%M:%S %z') + cfws
        else:
            return 'NEW'

    @staticmethod
    def html2text(data: str) -> str:
        """Converts html to text.

        :param data: the string in html format.
        :returns: the string in text format.
        """
        parser = html2text.HTML2Text()
        parser.unicode_snob = True
        parser.body_width = 0
        parser.ignore_images = True
        parser.single_line_break = True
        parser.wrap_links = False
        return '\n'.join(line.rstrip() for line in parser.handle(data).splitlines())

    def raise_import_error(self, package_name: str, error_message: str) -> None:
        """Raise ImportError for missing package.

        :param package_name: The name of the module/package that could not be imported.
        :param error_message: The error message from ImportError.

        :raises: ImportError.
        """
        raise ImportError(
            f"Job {self.job.index_number}: Python package '{package_name}' is not installed; cannot use "
            f"'differ: {self.__kind__}' ({self.job.get_location()})\n{error_message}"
        )


class UnifiedDiffer(DifferBase):
    """(Default) Generates a unified diff."""

    __kind__ = 'unified'

    __supported_directives__ = {
        'context_lines': 'the number of context lines (default: 3)',
        'range_info': 'include range information lines (default: true)',
    }

    def unified_diff_to_html(self, diff: str) -> Iterator[str]:
        """
        Generates a colorized HTML table from unified diff, applying styles and processing based on job values.

        :param diff: the unified diff
        """

        def process_line(line: str, line_num: int, monospace_style: str) -> str:
            """
            Processes each line for HTML output, handling special cases and styles.

            :param line: The line to analyze.
            :param line_num: The line number in the document.
            :param monospace_style: Additional style string for monospace text.

            :returns: The line processed into an HTML table row string.
            """
            # The style= string (or empty string) to add to an HTML tag.
            if line_num == 0:
                style = 'font-family:monospace;color:darkred;'
            elif line_num == 1:
                style = 'font-family:monospace;color:darkgreen;'
            elif line[0] == '+':  # addition
                style = f'{monospace_style}{self.css_added_style}'
            elif line[0] == '-':  # deletion
                style = f'{monospace_style}{self.css_deltd_style}'
            elif line[0] == ' ':  # context line
                style = monospace_style
            elif line[0] == '@':  # range information
                style = 'font-family:monospace;background-color:#fbfbfb;'
            elif line[0] == '/':  # informational header added by additions_only or deletions_only filters
                style = 'background-color:lightyellow;'
            else:
                raise RuntimeError('Unified Diff does not comform to standard!')
            style = f' style="{style}"' if style else ''

            if line_num > 1 and line[0] != '@':  # don't apply to headers or range information
                if self.job.is_markdown or line[0] == '/':  # our informational header
                    line = mark_to_html(line[1:], self.job.markdown_padded_tables)
                else:
                    line = linkify(line[1:])
            return f'<tr><td{style}>{line}</td></tr>'

        table_style = (
            ' style="border-collapse:collapse;font-family:monospace;white-space:pre-wrap;"'
            if self.job.monospace
            else ' style="border-collapse:collapse;"'
        )
        yield f'<table{table_style}>'
        monospace_style = 'font-family:monospace;' if self.job.monospace else ''
        for i, line in enumerate(diff.splitlines()):
            yield process_line(line, i, monospace_style)
        yield '</table>'

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: Optional[dict[Literal['text', 'markdown', 'html'], str]] = None,
        tz: Optional[str] = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        out_diff: dict[Literal['text', 'markdown', 'html'], str] = {}
        if report_kind == 'html' and _unfiltered_diff is not None and 'text' in _unfiltered_diff:
            diff_text = _unfiltered_diff['text']
        else:
            empty_return: dict[Literal['text', 'markdown', 'html'], str] = {'text': '', 'markdown': '', 'html': ''}
            contextlines = directives.get('context_lines') or self.job.contextlines
            if not contextlines:
                if self.job.additions_only or self.job.deletions_only:
                    contextlines = 0
                else:
                    contextlines = 3
            diff = list(
                difflib.unified_diff(
                    str(self.state.old_data).splitlines(),
                    str(self.state.new_data).splitlines(),
                    '@',
                    '@',
                    self.make_timestamp(self.state.old_timestamp, tz),
                    self.make_timestamp(self.state.new_timestamp, tz),
                    contextlines,
                    lineterm='',
                )
            )
            if not diff:
                self.state.verb = 'changed,no_report'
                return empty_return
            # replace tabs in header lines
            diff[0] = diff[0].replace('\t', ' ')
            diff[1] = diff[1].replace('\t', ' ')

            if self.job.additions_only:
                if len(self.state.old_data) and len(self.state.new_data) / len(self.state.old_data) <= 0.25:
                    diff = (
                        diff[:2]
                        + ['/**Comparison type: Additions only**']
                        + ['/**Deletions are being shown as 75% or more of the content has been deleted**']
                        + diff[2:]
                    )
                else:
                    head = '---' + diff[0][3:]
                    diff = [line for line in diff if line.startswith('+') or line.startswith('@')]
                    diff = [
                        line1
                        for line1, line2 in zip([''] + diff, diff + [''])
                        if not (line1.startswith('@') and line2.startswith('@'))
                    ][1:]
                    diff = diff[:-1] if diff[-1].startswith('@') else diff
                    if len(diff) == 1 or len([line for line in diff if line.lstrip('+').rstrip()]) == 2:
                        self.state.verb = 'changed,no_report'
                        return empty_return
                    diff = [head, diff[0], '/**Comparison type: Additions only**'] + diff[1:]
            elif self.job.deletions_only:
                head = '---' + diff[1][3:]
                diff = [line for line in diff if line.startswith('-') or line.startswith('@')]
                diff = [
                    line1
                    for line1, line2 in zip([''] + diff, diff + [''])
                    if not (line1.startswith('@') and line2.startswith('@'))
                ][1:]
                diff = diff[:-1] if diff[-1].startswith('@') else diff
                if len(diff) == 1 or len([line for line in diff if line.lstrip('-').rstrip()]) == 2:
                    self.state.verb = 'changed,no_report'
                    return empty_return
                diff = [diff[0], head, '/**Comparison type: Deletions only**'] + diff[1:]

            # remove range info lines if needed
            if directives.get('range_info') is False or (
                directives.get('range_info') is None
                and self.job.additions_only
                and (len(diff) < 4 or diff[3][0] != '/')
            ):
                diff = [line for line in diff if not line.startswith('@@ ')]

            diff_text = '\n'.join(diff)

            out_diff.update(
                {
                    'text': diff_text,
                    'markdown': diff_text,
                }
            )

        if report_kind == 'html':
            out_diff['html'] = '\n'.join(self.unified_diff_to_html(diff_text))

        return out_diff


class TableDiffer(DifferBase):
    """Generates a Python HTML table diff."""

    __kind__ = 'table'

    __supported_directives__ = {
        'tabsize': 'tab stop spacing (default: 8)',
    }

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: Optional[dict[Literal['text', 'markdown', 'html'], str]] = None,
        tz: Optional[str] = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        out_diff: dict[Literal['text', 'markdown', 'html'], str] = {}
        if report_kind in {'text', 'markdown'} and _unfiltered_diff is not None and 'html' in _unfiltered_diff:
            table = _unfiltered_diff['html']
        else:
            tabsize = int(directives.get('tabsize', 8))
            html_diff = difflib.HtmlDiff(tabsize=tabsize)
            table = html_diff.make_table(
                str(self.state.old_data).splitlines(keepends=True),
                str(self.state.new_data).splitlines(keepends=True),
                self.make_timestamp(self.state.old_timestamp, tz),
                self.make_timestamp(self.state.new_timestamp, tz),
                True,
                3,
            )
            # fix table formatting
            table = table.replace('<th ', '<th style="font-family:monospace" ')
            table = table.replace('<td ', '<td style="font-family:monospace" ')
            table = table.replace(' nowrap="nowrap"', '')
            table = table.replace('<a ', '<a style="font-family:monospace;color:inherit" ')
            table = table.replace('<span class="diff_add"', '<span style="color:green;background-color:lightgreen"')
            table = table.replace('<span class="diff_sub"', '<span style="color:red;background-color:lightred"')
            table = table.replace('<span class="diff_chg"', '<span style="color:orange;background-color:lightyellow"')
            out_diff['html'] = table

        if report_kind in {'text', 'markdown'}:
            diff_text = self.html2text(table)
            out_diff.update(
                {
                    'text': diff_text,
                    'markdown': diff_text,
                }
            )

        return out_diff


class CommandDiffer(DifferBase):
    """Runs an external command to generate the diff."""

    __kind__ = 'command'

    __supported_directives__ = {
        'command': 'The command to execute',
    }

    re_ptags = re.compile(r'^<p>|</p>$')
    re_htags = re.compile(r'<(/?)h\d>')
    re_tagend = re.compile(r'<(?!.*<).*>+$')

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: Optional[dict[Literal['text', 'markdown', 'html'], str]] = None,
        tz: Optional[str] = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        out_diff: dict[Literal['text', 'markdown', 'html'], str] = {}
        command = directives['command']
        if (
            report_kind == 'html'
            and not command.startswith('wdiff')
            and _unfiltered_diff is not None
            and 'text' in _unfiltered_diff
        ):
            diff = _unfiltered_diff['text']
        else:
            old_data = self.state.old_data
            new_data = self.state.new_data
            if self.job.is_markdown:
                # protect the link anchor from being split (won't work)
                markdown_links_re = re.compile(r'\[(.*?)][(](.*?)[)]')
                old_data = markdown_links_re.sub(
                    lambda x: f'[{urllib.parse.quote(x.group(1))}]({x.group(2)})', old_data
                )
                new_data = markdown_links_re.sub(
                    lambda x: f'[{urllib.parse.quote(x.group(1))}]({x.group(2)})', new_data
                )

            # External diff tool
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                old_file_path = tmp_path.joinpath('old_file')
                new_file_path = tmp_path.joinpath('new_file')
                old_file_path.write_text(old_data)
                new_file_path.write_text(new_data)
                cmdline = shlex.split(command) + [str(old_file_path), str(new_file_path)]
                proc = subprocess.run(cmdline, capture_output=True, text=True)  # noqa: S603 subprocess call
            if proc.stderr or proc.returncode > 1:
                raise RuntimeError(
                    f"Job {self.job.index_number}: External differ '{directives}' returned '{proc.stderr.strip()}' "
                    f'({self.job.get_location()})'
                ) from subprocess.CalledProcessError(proc.returncode, cmdline)
            if proc.returncode == 0:
                self.state.verb = 'changed,no_report'
                return {'text': '', 'markdown': '', 'html': ''}
            head = '\n'.join(
                [
                    f'Using differ "{directives}"',
                    f'Old: {self.make_timestamp(self.state.old_timestamp, tz)}',
                    f'New: {self.make_timestamp(self.state.new_timestamp, tz)}',
                    '-' * 36,
                ]
            )
            diff = proc.stdout
            if self.job.is_markdown:
                # undo the protection of the link anchor from being split
                diff = markdown_links_re.sub(lambda x: f'[{urllib.parse.unquote(x.group(1))}]({x.group(2)})', diff)
            if command.startswith('wdiff') and self.job.contextlines == 0:
                # remove lines that don't have any changes
                keeplines = []
                for line in diff.splitlines(keepends=True):
                    if any(x in line for x in {'{+', '+}', '[-', '-]'}):
                        keeplines.append(line)
                diff = ''.join(keeplines)
            diff = head + diff
            out_diff.update(
                {
                    'text': diff,
                    'markdown': diff,
                }
            )

        if report_kind == 'html':
            if command.startswith('wdiff'):
                # colorize output of wdiff
                out_diff['html'] = self.wdiff_to_html(diff)
            else:
                out_diff['html'] = html.escape(diff)

        return out_diff

    def wdiff_to_html(self, diff: str) -> str:
        """
        Colorize output of wdiff.

        :param diff: The output of the wdiff command.
        :returns: The colorized HTML output.
        """
        html_diff = html.escape(diff)
        if self.job.is_markdown:
            # detect and fix multiline additions or deletions
            is_add = False
            is_del = False
            new_diff = []
            for line in html_diff.splitlines():
                if is_add:
                    line = '{+' + line
                    is_add = False
                elif is_del:
                    line = '[-' + line
                    is_del = False
                for match in re.findall(r'\[-|-]|{\+|\+}', line):
                    if match == '[-':
                        is_del = True
                    if match == '-]':
                        is_del = False
                    if match == '{+':
                        is_add = True
                    if match == '+}':
                        is_add = False
                if is_add:
                    line += '+}'
                elif is_del:
                    line += '-]'
                new_diff.append(line)
            html_diff = '<br>\n'.join(new_diff)

        # wdiff colorization (cannot be done with global CSS class as Gmail overrides it)
        html_diff = re.sub(
            r'\{\+(.*?)\+}',
            lambda x: f'<span style="{self.css_added_style}">{x.group(1)}</span>',
            html_diff,
            flags=re.DOTALL,
        )
        html_diff = re.sub(
            r'\[-(.*?)-]',
            lambda x: f'<span style="{self.css_deltd_style}">{x.group(1)}</span>',
            html_diff,
            flags=re.DOTALL,
        )
        if self.job.monospace:
            return f'<span style="font-family:monospace;white-space:pre-wrap">{html_diff}</span>'
        else:
            return html_diff


class DeepdiffDiffer(DifferBase):

    __kind__ = 'deepdiff'

    __supported_directives__ = {
        'data_type': "either 'json' (default) or 'xml'",
        'ignore_order': 'Whether to ignore the order in which the items have appeared (default: false)',
        'ignore_string_case': 'Whether to be case-sensitive or not when comparing strings (default: false)',
        'significant_digits': (
            'The number of digits AFTER the decimal point to be used in the comparison (default: ' 'no limit)'
        ),
    }

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: Optional[dict[Literal['text', 'markdown', 'html'], str]] = None,
        tz: Optional[str] = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        if isinstance(DeepDiff, str):  # pragma: no cover
            self.raise_import_error('deepdiff', DeepDiff)

        span_added = f'<span style="{self.css_added_style}">'
        span_deltd = f'<span style="{self.css_deltd_style}">'

        def _pretty_deepdiff(ddiff: DeepDiff, report_kind: Literal['text', 'markdown', 'html']) -> str:
            """
            Customized version of deepdiff.serialization.SerializationMixin.pretty method, edited to include the
            values deleted or added and an option for colorized HTML output. The pretty human-readable string
            output for the diff object regardless of what view was used to generate the diff.
            """
            if report_kind == 'html':
                PRETTY_FORM_TEXTS = {
                    'type_changes': (
                        'Type of {diff_path} changed from {type_t1} to {type_t2} and value changed '
                        f'from {span_deltd}{{val_t1}}</span> to {span_added}{{val_t2}}</span>.'
                    ),
                    'values_changed': (
                        f'Value of {{diff_path}} changed from {span_deltd}{{val_t1}}</span> to {span_added}{{val_t2}}'
                        '</span>.'
                    ),
                    'dictionary_item_added': (
                        f'Item {{diff_path}} added to dictionary as {span_added}{{val_t2}}</span>.'
                    ),
                    'dictionary_item_removed': (
                        f'Item {{diff_path}} removed from dictionary (was {span_deltd}{{val_t1}}</span>).'
                    ),
                    'iterable_item_added': f'Item {{diff_path}} added to iterable as {span_added}{{val_t2}}</span>.',
                    'iterable_item_removed': (
                        f'Item {{diff_path}} removed from iterable (was {span_deltd}{{val_t1}}</span>).'
                    ),
                    'attribute_added': f'Attribute {{diff_path}} added as {span_added}{{val_t2}}</span>.',
                    'attribute_removed': f'Attribute {{diff_path}} removed (was {span_deltd}{{val_t1}}</span>).',
                    'set_item_added': f'Item root[{{val_t2}}] added to set as {span_added}{{val_t1}}</span>.',
                    'set_item_removed': (
                        f'Item root[{{val_t1}}] removed from set (was {span_deltd}{{val_t2}}</span>).'
                    ),
                    'repetition_change': 'Repetition change for item {diff_path} ({val_t2}).',
                }
            else:
                PRETTY_FORM_TEXTS = {
                    'type_changes': (
                        'Type of {diff_path} changed from {type_t1} to {type_t2} and value changed '
                        'from {val_t1} to {val_t2}.'
                    ),
                    'values_changed': 'Value of {diff_path} changed from {val_t1} to {val_t2}.',
                    'dictionary_item_added': 'Item {diff_path} added to dictionary as {val_t2}.',
                    'dictionary_item_removed': 'Item {diff_path} removed from dictionary (was {val_t1}).',
                    'iterable_item_added': 'Item {diff_path} added to iterable as {val_t2}.',
                    'iterable_item_removed': 'Item {diff_path} removed from iterable (was {val_t1}).',
                    'attribute_added': 'Attribute {diff_path} added as {val_t2}.',
                    'attribute_removed': 'Attribute {diff_path} removed (was {val_t1}).',
                    'set_item_added': 'Item root[{val_t2}] added to set as {val_t1}.',
                    'set_item_removed': 'Item root[{val_t1}] removed from set (was {val_t2}).',
                    'repetition_change': 'Repetition change for item {diff_path} ({val_t2}).',
                }

            def _pretty_print_diff(ddiff: DiffLevel) -> str:
                """
                Customized version of deepdiff.serialization.pretty_print_diff() function, edited to include the
                values deleted or added.
                """
                type_t1 = type(ddiff.t1).__name__
                type_t2 = type(ddiff.t2).__name__

                val_t1 = (
                    f'"{ddiff.t1}"'
                    if type_t1 in {'str', 'int', 'float'}
                    else (jsonlib.dumps(ddiff.t1, ensure_ascii=False, indent=2) if type_t1 == 'dict' else str(ddiff.t1))
                )
                val_t2 = (
                    f'"{ddiff.t2}"'
                    if type_t2 in {'str', 'int', 'float'}
                    else (jsonlib.dumps(ddiff.t2, ensure_ascii=False, indent=2) if type_t2 == 'dict' else str(ddiff.t2))
                )

                diff_path = ddiff.path(root='')
                return PRETTY_FORM_TEXTS.get(ddiff.report_type, '').format(
                    diff_path=diff_path,
                    type_t1=type_t1,
                    type_t2=type_t2,
                    val_t1=val_t1,
                    val_t2=val_t2,
                )

            result = []
            for key in ddiff.tree.keys():
                for item_key in ddiff.tree[key]:
                    result.append(_pretty_print_diff(item_key))

            return '\n'.join(result)

        data_type = directives.get('data_type', 'json')
        old_data = ''
        new_data = ''
        if data_type == 'json':
            try:
                old_data = jsonlib.loads(self.state.old_data)
            except jsonlib.JSONDecodeError:
                old_data = ''
            try:
                new_data = jsonlib.loads(self.state.new_data)
            except jsonlib.JSONDecodeError as e:
                self.state.exception = e
                self.state.traceback = self.job.format_error(e, traceback.format_exc())
                logger.error(f'{self.job.index_number}: Invalid JSON data: {e.msg} ({self.job.get_location()})')
                return {
                    'text': f'Differ {self.__kind__} ERROR: New data is invalid JSON\n{e.msg}',
                    'markdown': f'Differ {self.__kind__} **ERROR: New data is invalid JSON**\n{e.msg}',
                    'html': f'Differ {self.__kind__} <b>ERROR: New data is invalid JSON</b>\n{e.msg}',
                }
        elif data_type == 'xml':
            if isinstance(xmltodict, str):  # pragma: no cover
                self.raise_import_error('xmltodict', xmltodict)

            old_data = xmltodict.parse(self.state.old_data)
            new_data = xmltodict.parse(self.state.new_data)

        ignore_order = directives.get('ignore_order')
        ignore_string_case = directives.get('ignore_string_case')
        significant_digits = directives.get('significant_digits')
        ddiff = DeepDiff(
            old_data,
            new_data,
            cache_size=500,
            cache_purge_level=0,
            cache_tuning_sample_size=500,
            ignore_order=ignore_order,
            ignore_string_type_changes=True,
            ignore_numeric_type_changes=True,
            ignore_string_case=ignore_string_case,
            significant_digits=significant_digits,
            verbose_level=min(2, max(0, math.ceil(3 - logger.getEffectiveLevel() / 10))),
        )
        diff_text = _pretty_deepdiff(ddiff, report_kind)
        if not diff_text:
            self.state.verb = 'changed,no_report'
            return {'text': '', 'markdown': '', 'html': ''}

        self.job.set_to_monospace()

        if report_kind == 'html':
            html_diff = (
                f'<span style="font-family:monospace;white-space:pre-wrap;">\n'
                f'Differ: {self.__kind__} for {data_type}\n'
                f'<span style="color:darkred;">Old {self.make_timestamp(self.state.old_timestamp, tz)}</span>\n'
                f'<span style="color:darkgreen;">New {self.make_timestamp(self.state.new_timestamp, tz)}</span>\n'
                + '-' * 36
                + '\n'
                + diff_text[:-1]
                + '</span>'
            )
            return {'html': html_diff}
        else:
            text_diff = (
                f'Differ: {self.__kind__} for {data_type}\n'
                f'Old {self.make_timestamp(self.state.old_timestamp, tz)}\n'
                f'New {self.make_timestamp(self.state.new_timestamp, tz)}\n' + '-' * 36 + '\n' + diff_text
            )
            return {'text': text_diff, 'markdown': text_diff}


class ImageDiffer(DifferBase):
    """Compares two images providing an image outlining areas that have changed."""

    __kind__ = 'image'

    __supported_directives__ = {
        'data_type': (
            "'url' (to retrieve an image), 'base_64' (Base 64 data) or 'filename' (the path to an image file) "
            "(default: 'url')"
        ),
        'mse_treshold': (
            'the minimum mean squared error (MSE) between two images to consider them changed if numpy in installed '
            '(default: 2.5)'
        ),
    }

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: Optional[dict[Literal['text', 'markdown', 'html'], str]] = None,
        tz: Optional[str] = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        warnings.warn(
            f'Job {self.job.index_number}: Using differ {self.__kind__}, which is BETA, may have bugs, and may '
            f'change in the future. Please report any problems or suggestions at '
            f'https://github.com/mborsetti/webchanges/discussions.',
            RuntimeWarning,
        )
        if isinstance(Image, str):  # pragma: no cover
            self.raise_import_error('pillow', Image)
        if isinstance(httpx, str):  # pragma: no cover
            self.raise_import_error('httpx', httpx)

        span_added = f'<span style="{self.css_added_style}">'
        span_deltd = f'<span style="{self.css_deltd_style}">'

        def load_image_from_web(url: str) -> Image:
            """Fetches the image from an url."""
            logging.debug(f'Retrieving image from {url}')
            with httpx.stream('GET', url, timeout=10) as response:
                response.raise_for_status()
                return Image.open(BytesIO(b''.join(response.iter_bytes())))

        def load_image_from_file(filename: str) -> Image:
            """Load an image from a file."""
            logging.debug(f'Reading image from {filename}')
            return Image.open(filename)

        def load_image_from_base_64(base_64: str) -> Image:
            """Load an image from an encoded bytes object."""
            logging.debug('Retrieving image from a bytes object')
            return Image.open(BytesIO(base64.b64decode(base_64)))

        def compute_diff_image(img1: Image, img2: Image) -> tuple[Image, Optional[np.float64]]:
            """Compute the difference between two images."""
            # Compute the absolute value of the pixel-by-pixel difference between the two images.
            diff_image = ImageChops.difference(img1, img2)

            # Compute the mean squared error between the images
            if not isinstance(np, str):
                diff_array = np.array(diff_image)
                mse_value = np.mean(np.square(diff_array))
            else:  # pragma: no cover
                mse_value = None

            # Create the diff image by overlaying this difference on a darkened greyscale background
            back_image = img1.convert('L')
            back_image_brightness = ImageStat.Stat(back_image).rms[0]
            back_image = ImageEnhance.Brightness(back_image).enhance(back_image_brightness / 225)

            # Convert the 'L' image to 'RGB' using a matrix that applies to yellow tint
            # The matrix has 12 elements: 4 for Red, 4 for Green, and 4 for Blue.
            # For yellow, we want Red and Green to copy the L values (1.0) and Blue to be zero.
            # The matrix is: [R, G, B, A] for each of the three output channels
            yellow_tint_matrix = (
                1.0,
                0.0,
                0.0,
                0.0,  # Red = 100% of the grayscale value
                1.0,
                0.0,
                0.0,
                0.0,  # Green = 100% of the grayscale value
                0.0,
                0.0,
                0.0,
                0.0,  # Blue = 0% of the grayscale value
            )

            # Apply the conversion
            diff_colored = diff_image.convert('RGB').convert('RGB', matrix=yellow_tint_matrix)

            final_img = ImageChops.add(back_image.convert('RGB'), diff_colored)

            return final_img, mse_value

        data_type = directives.get('data_type', 'url')
        mse_threshold = directives.get('mse_threshold', 2.5)
        if data_type == 'url':
            old_image = load_image_from_web(self.state.old_data)
            new_image = load_image_from_web(self.state.new_data)
            old_data = f' (<a href="{self.state.old_data}">Old image</a>)'
            new_data = f' (<a href="{self.state.new_data}">New image</a>)'
        elif data_type == 'base_64':
            old_image = load_image_from_base_64(self.state.old_data)
            new_image = load_image_from_base_64(self.state.new_data)
            old_data = ''
            new_data = ''
        else:  # 'filename'
            old_image = load_image_from_file(self.state.old_data)
            new_image = load_image_from_file(self.state.new_data)
            old_data = f' (<a href="file://{self.state.old_data}">Old image</a>)'
            new_data = f' (<a href="file://{self.state.new_data}">New image</a>)'

        # Check formats  TODO: is it needed? under which circumstances?
        # if new_image.format != old_image.format:
        #     logger.info(f'Image formats do not match: {old_image.format} vs {new_image.format}')
        # else:
        #     logger.debug(f'image format is {old_image.format}')

        # If needed, shrink the larger image
        if new_image.size != old_image.size:
            if new_image.size > old_image.size:
                logging.debug(f'Job {self.job.index_number}: Shrinking the new image')
                img_format = new_image.format
                new_image = new_image.resize(old_image.size, Image.LANCZOS)
                new_image.format = img_format

            else:
                logging.debug(f'Job {self.job.index_number}: Shrinking the old image')
                img_format = old_image.format
                old_image = old_image.resize(new_image.size, Image.LANCZOS)
                old_image.format = img_format

        if old_image == new_image:
            logger.info(f'Job {self.job.index_number}: New image is identical to the old one')
            self.state.verb = 'unchanged'
            return {'text': '', 'markdown': '', 'html': ''}

        diff_image, mse_value = compute_diff_image(old_image, new_image)

        if mse_value and mse_value < mse_threshold:
            logger.info(
                f'Job {self.job.index_number}: MSE value {mse_value:.2f} below the threshold of {mse_threshold}; '
                f'considering changes not worthy of a report'
            )
            self.state.verb = 'changed,no_report'
            return {'text': '', 'markdown': '', 'html': ''}

        # Convert the difference image to a base64 object
        output_stream = BytesIO()
        diff_image.save(output_stream, format=new_image.format)
        encoded_diff = b64encode(output_stream.getvalue()).decode()

        # Convert the new image to a base64 object
        output_stream = BytesIO()
        new_image.save(output_stream, format=new_image.format)
        encoded_new = b64encode(output_stream.getvalue()).decode()

        # Prepare HTML output
        htm = [
            f'Differ: {self.__kind__} for {data_type}<br>',
            f'{span_deltd}Old</span> {self.make_timestamp(self.state.old_timestamp, tz)}{old_data}<br>',
            f'{span_added}New</span> {self.make_timestamp(self.state.new_timestamp, tz)}{new_data}<br>',
            '-' * 36 + '<br>',
            f'{span_added}New:</span><br>',
            f'<img src="data:image/{new_image.format.lower()};base64,{encoded_new}">',
            '<br>',
            'Differences from old (in yellow):<br>',
            f'<img src="data:image/{old_image.format.lower()};base64,{encoded_diff}">',
            '<br>',
        ]

        return {
            'text': 'The image has changed; please see an HTML report for the visualization.',
            'markdown': 'The image has changed; please see an HTML report for the visualization.',
            'html': '\n'.join(htm),
        }


class AIGoogleDiffer(DifferBase):
    """(Default) Generates a summary using Google Generative AI (Gemini models).

    Calls Google Gemini APIs; documentation at https://ai.google.dev/api/rest and tutorial at
    https://ai.google.dev/tutorials/rest_quickstart

    """

    __kind__ = 'ai_google'

    __supported_directives__ = {
        'model': 'model name from https://ai.google.dev/models/gemini (default: gemini-1.5-pro-latest)',
        'prompt': 'a custom prompt - {unified_diff}, {old_data} and {new_data} will be replaced; ask for markdown',
        'prompt_ud_context_lines': 'the number of context lines for {unified_diff} (default: 9999)',
        'timeout': 'the number of seconds before timing out the API call (default: 300)',
        'max_output_tokens': "the maximum number of tokens returned by the model (default: None, i.e. model's default)",
        'temperature': "the model's Temperature parameter (default: None, i.e. model's default)",
        'top_p': "the model's TopP parameter (default: None, i.e. model's default",
        'top_k': "the model's TopK parameter (default: None, i.e. model's default",
        'token_limit': (
            "the maximum number of tokens, if different from model's default (default: None, i.e. model's default)"
        ),
    }
    __default_subdirective__ = 'model'

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: str | None = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        logger.info(f'Job {self.job.index_number}: Running the {self.__kind__} differ from hooks.py')
        warnings.warn(
            f'Job {self.job.index_number}: Using differ {self.__kind__}, which is BETA, may have bugs, and may '
            f'change in the future. Please report any problems or suggestions at '
            f'https://github.com/mborsetti/webchanges/discussions.',
            RuntimeWarning,
        )

        def get_ai_summary(prompt: str) -> str:
            """Generate AI summary from unified diff, or an error message"""
            GOOGLE_AI_API_KEY = os.environ.get('GOOGLE_AI_API_KEY', '').rstrip()
            if len(GOOGLE_AI_API_KEY) != 39:
                raise ValueError(
                    f'Job {self.job.index_number}: Environment variable GOOGLE_AI_API_KEY not found or is of the '
                    f'incorrect length {len(GOOGLE_AI_API_KEY)} ({self.job.get_location()})'
                )

            api_version = '1beta'
            _models_token_limits = {  # from https://ai.google.dev/models/gemini
                'gemini-1.5-pro-latest': 1048576,
                'gemini-pro': 30720,
                'gemini-1.0-pro-latest': 30720,
                'gemini-pro-latest': 30720,
                'gemini-1.0-pro-001': 30720,
            }

            if 'model' not in directives:
                directives['model'] = 'gemini-1.5-pro-latest'  # also for footer
            model = directives['model']
            token_limit = directives.get('token_limit')
            if not token_limit:
                if model not in _models_token_limits:
                    raise NotImplementedError(
                        f"Job {self.job.index_number}: Differ '{self.__kind__}' does not know `model: {model}` "
                        f"(supported: {', '.join(sorted(list(_models_token_limits.keys())))}) "
                        f'({self.job.get_location()})'
                    )
                token_limit = _models_token_limits[model]

            if '{unified_diff}' in prompt:
                context_lines = directives.get('prompt_ud_context_lines', 9999)
                unified_diff = '\n'.join(
                    difflib.unified_diff(
                        str(self.state.old_data).splitlines(),
                        str(self.state.new_data).splitlines(),
                        # '@',
                        # '@',
                        # self.make_timestamp(self.state.old_timestamp, tz),
                        # self.make_timestamp(self.state.new_timestamp, tz),
                        n=context_lines,
                    )
                )
                if not unified_diff:
                    # no changes
                    return ''
            else:
                unified_diff = ''

            def _send_to_model(model_prompt: str) -> str:
                """Creates the summary request to the model"""
                max_output_tokens = directives.get('max_output_tokens')
                temperature = directives.get('temperature', 0.0)
                top_p = directives.get('top_p')
                top_k = directives.get('top_k')
                data = {
                    'system_instruction': {'parts': [{'text': 'Respond in Markdown'}]},
                    'contents': [{'parts': [{'text': model_prompt}]}],
                    'generation_config': {
                        'max_output_tokens': max_output_tokens,
                        'temperature': temperature,
                        'top_p': top_p,
                        'top_k': top_k,
                    },
                }
                logger.info(f'Job {self.job.index_number}: Making summary request to Google model {model}')
                try:
                    timeout = directives.get('timeout', 300)
                    r = httpx.Client(http2=True).post(
                        f'https://generativelanguage.googleapis.com/v{api_version}/models/{model}:generateContent?'
                        f'key={GOOGLE_AI_API_KEY}',
                        json=data,
                        headers={'Content-Type': 'application/json'},
                        timeout=timeout,
                    )
                    if r.is_success:
                        result = r.json()
                        candidate = result['candidates'][0]
                        logger.info(
                            f"Job {self.job.index_number}: AI generation finished by {candidate['finishReason']}"
                        )
                        summary = candidate['content']['parts'][0]['text']
                    elif r.status_code == 400:
                        summary = (
                            f'AI summary unavailable: Received error from {r.url.host}: '
                            f"{r.json().get('error', {}).get('message') or ''}"
                        )
                    else:
                        summary = (
                            f'AI summary unavailable: Received error {r.status_code} {r.reason_phrase} from '
                            f'{r.url.host}'
                        )
                        if r.content:
                            summary += f": {r.json().get('error', {}).get('message') or ''}"

                except httpx.HTTPError as e:
                    summary = (
                        f'AI summary unavailable: HTTP client error: {e.args[0]} when requesting data from '
                        f'{e.request.url.host}'
                    )

                return summary

            model_prompt = prompt.format(
                unified_diff=unified_diff, old_data=self.state.old_data, new_data=self.state.new_data
            )

            if len(model_prompt) / 4 < token_limit:
                summary = _send_to_model(model_prompt)
            elif '{unified_diff}' in prompt:
                logger.info(
                    f'Job {self.job.index_number}: Model prompt with full diff is too long: '
                    f'({len(model_prompt) / 4:,.0f} est. tokens exceeds limit of {token_limit:,.0f} tokens); '
                    f'recomputing with default contextlines'
                )
                unified_diff = '\n'.join(
                    difflib.unified_diff(
                        str(self.state.old_data).splitlines(),
                        str(self.state.new_data).splitlines(),
                        # '@',
                        # '@',
                        # self.make_timestamp(self.state.old_timestamp, tz),
                        # self.make_timestamp(self.state.new_timestamp, tz),
                    )
                )
                model_prompt = prompt.format(
                    unified_diff=unified_diff, old_data=self.state.old_data, new_data=self.state.new_data
                )
                if len(model_prompt) / 4 < token_limit:
                    summary = _send_to_model(model_prompt)
                else:
                    summary = (
                        f'AI summary unavailable (model prompt with unified diff is too long: '
                        f'{len(model_prompt) / 4:,.0f} est. tokens exceeds maximum of {token_limit:,.0f})'
                    )
            else:
                logger.info(
                    f'The model prompt may be too long: {len(model_prompt) / 4:,.0f} est. tokens exceeds '
                    f'limit of {token_limit:,.0f} tokens'
                )
                summary = _send_to_model(model_prompt)
            return summary

        prompt = directives.get(
            'prompt',
            'Summarize this unified diff:\n\n{unified_diff}',
        )
        summary = get_ai_summary(prompt)
        if not summary:
            self.state.verb = 'changed,no_report'
            return {'text': '', 'markdown': '', 'html': ''}
        subdirectives_text = ', '.join(f'{key}={value}' for key, value in directives.items())
        footer = f'Summary generated by Google Generative AI (differ directives: {subdirectives_text})'
        temp_unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] = {}
        for rep_kind in {'text', 'html'}:  # markdown is same as text
            unified_report = DifferBase.process(
                'unified',
                directives.get('unified'),  # type: ignore[arg-type]
                self.state,
                rep_kind,  # type: ignore[arg-type]
                tz,
                temp_unfiltered_diff,
            )
        return {
            'text': summary + '\n\n' + unified_report['text'] + '\n------------\n' + footer,
            'markdown': summary + '\n\n' + unified_report['markdown'] + '\n* * *\n' + footer,
            'html': (
                mark_to_html(summary, extras={'tables'}).replace('<h2>', '<h3>').replace('</h2>', '</h3>')
                + '<br>'
                + unified_report['html']
                + f'---<i><small>{footer}</small></i>'
            ),
        }
