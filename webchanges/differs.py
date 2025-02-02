"""Differs."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import base64
import difflib
import html
import io
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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator, Literal, TYPE_CHECKING, TypedDict
from zoneinfo import ZoneInfo

import html2text

from webchanges.jobs import JobBase
from webchanges.util import linkify, mark_to_html, TrackSubClasses

try:
    from deepdiff import DeepDiff
    from deepdiff.model import DiffLevel
except ImportError as e:  # pragma: no cover
    DeepDiff = str(e)  # type: ignore[assignment,misc]

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
    np = str(e)  # type: ignore[assignment]

try:
    from PIL import Image, ImageChops, ImageEnhance, ImageStat
except ImportError as e:  # pragma: no cover
    Image = str(e)  # type: ignore[assignment]

# https://stackoverflow.com/questions/712791
try:
    import simplejson as jsonlib
except ImportError:  # pragma: no cover
    import json as jsonlib  # type: ignore[no-redef]

try:
    import xmltodict
except ImportError as e:  # pragma: no cover
    xmltodict = str(e)  # type: ignore[no-redef]

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.handler import JobState


logger = logging.getLogger(__name__)

AiGoogleDirectives = TypedDict(
    'AiGoogleDirectives',
    {
        'model': str,
        'additions_only': str,
        'system_instructions': str,
        'prompt': str,
        'prompt_ud_context_lines': int,
        'timeout': int,
        'max_output_tokens': int | None,
        'temperature': float | None,
        'top_p': float | None,
        'top_k': float | None,
        'tools': list[Any],
    },
    total=False,
)


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
        differ_spec: dict[str, Any] | None,
        job_index_number: int | None = None,
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
        tz: ZoneInfo | None = None,
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        """Process the differ.

        :param differ_kind: The name of the differ.
        :param directives: The directives.
        :param job_state: The JobState.
        :param report_kind: The report kind required.
        :param tz: The timezone of the report.
        :param _unfiltered_diff: Any previous diffs generated by the same filter, who can be used to generate a diff
           for a different report_kind.
        :returns: The output of the differ or an error message with traceback if it fails.
        """
        logger.info(f'Job {job_state.job.index_number}: Applying differ {differ_kind}, directives {directives}')
        differcls: type[DifferBase] | None = cls.__subclasses__.get(differ_kind)  # type: ignore[assignment]
        if differcls:
            try:
                return differcls(job_state).differ(directives, report_kind, _unfiltered_diff, tz)
            except Exception as e:
                # Differ failed
                logger.info(
                    f'Job {job_state.job.index_number}: Differ {differ_kind} with {directives=} encountered '
                    f'error {e}'
                )
                # Undo saving of new data since user won't see the diff
                job_state.delete_latest()

                job_state.exception = e
                job_state.traceback = job_state.job.format_error(e, traceback.format_exc())
                directives_text = ', '.join(f'{key}={value}' for key, value in directives.items()) or 'None'
                return {
                    'text': (
                        f'Differ {differ_kind} with directive(s) {directives_text} encountered an '
                        f'error:\n\n{job_state.traceback}'
                    ),
                    'markdown': (
                        f'## Differ {differ_kind} with directive(s) {directives_text} '
                        f'encountered an error:\n```\n{job_state.traceback}\n```\n'
                    ),
                    'html': (
                        f'<span style="color:red;font-weight:bold">Differ {differ_kind} with directive(s) '
                        f'{directives_text} encountered an error:<br>\n<br>\n'
                        f'<span style="font-family:monospace;white-space:pre-wrap;">{job_state.traceback}'
                        f'</span></span>'
                    ),
                }
        else:
            return {}

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: ZoneInfo | None = None,
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
        tz: ZoneInfo | None = None,
    ) -> str:
        """Creates a datetime string in RFC 5322 (email) format with the time zone name (if available) in the
        Comments and Folding White Space (CFWS) section.

        :param timestamp: The timestamp.
        :param tz: The IANA timezone of the report.
        :returns: A datetime string in RFC 5322 (email) format.
        """
        if timestamp:
            dt = datetime.fromtimestamp(timestamp).astimezone(tz=tz)
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
        'additions_only': 'keep only addition lines (default: false)',
        'deletions_only': 'keep only deletion lines (default: false)',
    }

    def unified_diff_to_html(self, diff: str) -> Iterator[str]:
        """
        Generates a colorized HTML table from unified diff, applying styles and processing based on job values.

        :param diff: the unified diff
        """

        def process_line(line: str, line_num: int, is_markdown: bool, monospace_style: str) -> str:
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
                if is_markdown or line[0] == '/':  # our informational header
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
        is_markdown = self.state.is_markdown()
        monospace_style = 'font-family:monospace;' if self.job.monospace else ''
        for i, line in enumerate(diff.splitlines()):
            yield process_line(line, i, is_markdown, monospace_style)
        yield '</table>'

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: ZoneInfo | None = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        additions_only = directives.get('additions_only') or self.job.additions_only
        deletions_only = directives.get('deletions_only') or self.job.deletions_only
        out_diff: dict[Literal['text', 'markdown', 'html'], str] = {}
        if report_kind == 'html' and _unfiltered_diff is not None and 'text' in _unfiltered_diff:
            diff_text = _unfiltered_diff['text']
        else:
            empty_return: dict[Literal['text', 'markdown', 'html'], str] = {'text': '', 'markdown': '', 'html': ''}
            contextlines = directives.get('context_lines', self.job.contextlines)
            if contextlines is None:
                if additions_only or deletions_only:
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

            if additions_only:
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
            elif deletions_only:
                head = '--- @' + diff[1][3:]
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
                directives.get('range_info') is None and additions_only and (len(diff) < 4 or diff[3][0] != '/')
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
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: ZoneInfo | None = None,
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
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: ZoneInfo | None = None,
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
            if self.state.is_markdown():
                # protect the link anchor from being split (won't work)
                markdown_links_re = re.compile(r'\[(.*?)][(](.*?)[)]')
                old_data = markdown_links_re.sub(
                    lambda x: f'[{urllib.parse.quote(x.group(1))}]({x.group(2)})', str(old_data)
                )
                new_data = markdown_links_re.sub(
                    lambda x: f'[{urllib.parse.quote(x.group(1))}]({x.group(2)})', str(new_data)
                )

            # External diff tool
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                old_file_path = tmp_path.joinpath('old_file')
                new_file_path = tmp_path.joinpath('new_file')
                if isinstance(old_data, str):
                    old_file_path.write_text(old_data)
                else:
                    old_file_path.write_bytes(old_data)
                if isinstance(new_data, str):
                    new_file_path.write_text(new_data)
                else:
                    new_file_path.write_bytes(new_data)
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
                    f'--- @ {self.make_timestamp(self.state.old_timestamp, tz)}',
                    f'+++ @ {self.make_timestamp(self.state.new_timestamp, tz)}',
                ]
            )
            diff = proc.stdout
            if self.state.is_markdown():
                # undo the protection of the link anchor from being split
                diff = markdown_links_re.sub(lambda x: f'[{urllib.parse.unquote(x.group(1))}]({x.group(2)})', diff)
            if command.startswith('wdiff') and self.job.contextlines == 0:
                # remove lines that don't have any changes
                keeplines = []
                for line in diff.splitlines(keepends=True):
                    if any(x in line for x in {'{+', '+}', '[-', '-]'}):
                        keeplines.append(line)
                diff = ''.join(keeplines)
            diff = f'{head}\n{diff}'
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
        if self.state.is_markdown():
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
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: ZoneInfo | None = None,
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
                    else (
                        jsonlib.dumps(ddiff.t1, ensure_ascii=False, indent=2)
                        if type_t1 in {'dict', 'list'}
                        else str(ddiff.t1)
                    )
                )
                val_t2 = (
                    f'"{ddiff.t2}"'
                    if type_t2 in {'str', 'int', 'float'}
                    else (
                        jsonlib.dumps(ddiff.t2, ensure_ascii=False, indent=2)
                        if type_t2 in {'dict', 'list'}
                        else str(ddiff.t2)
                    )
                )

                diff_path = ddiff.path()  # type: ignore[no-untyped-call]
                return '• ' + PRETTY_FORM_TEXTS.get(ddiff.report_type, '').format(
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
                logger.error(f'Job {self.job.index_number}: New data is invalid JSON: {e} ({self.job.get_location()})')
                logger.info(f'Job {self.job.index_number}: {self.state.new_data!r}')
                return {
                    'text': f'Differ {self.__kind__} ERROR: New data is invalid JSON\n{e}',
                    'markdown': f'Differ {self.__kind__} **ERROR: New data is invalid JSON**\n{e}',
                    'html': f'Differ {self.__kind__} <b>ERROR: New data is invalid JSON</b>\n{e}',
                }
        elif data_type == 'xml':
            if isinstance(xmltodict, str):  # pragma: no cover
                self.raise_import_error('xmltodict', xmltodict)

            old_data = xmltodict.parse(self.state.old_data)
            new_data = xmltodict.parse(self.state.new_data)

        ignore_order: bool = directives.get('ignore_order')  # type: ignore[assignment]
        ignore_string_case: bool = directives.get('ignore_string_case')  # type: ignore[assignment]
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
                f'<span style="font-family:monospace;white-space:pre-wrap;">'
                # f'Differ: {self.__kind__} for {data_type}\n'
                f'<span style="color:darkred;">--- @ {self.make_timestamp(self.state.old_timestamp, tz)}</span>\n'
                f'<span style="color:darkgreen;">+++ @ {self.make_timestamp(self.state.new_timestamp, tz)}</span>\n'
                + diff_text[:-1].replace('][', ']<wbr>[')
                + '</span>'
            )
            return {'html': html_diff}
        else:
            text_diff = (
                # f'Differ: {self.__kind__} for {data_type}\n'
                f'--- @ {self.make_timestamp(self.state.old_timestamp, tz)}\n'
                f'+++ @ {self.make_timestamp(self.state.new_timestamp, tz)}\n'
                f'{diff_text}'
            )
            return {'text': text_diff, 'markdown': text_diff}


class ImageDiffer(DifferBase):
    """Compares two images providing an image outlining areas that have changed."""

    __kind__ = 'image'

    __supported_directives__ = {
        'data_type': (
            "'url' (to retrieve an image), 'ascii85' (Ascii85 data), 'base64' (Base64 data) or 'filename' (the path "
            "to an image file) (default: 'url')"
        ),
        'mse_threshold': (
            'the minimum mean squared error (MSE) between two images to consider them changed, if numpy in installed '
            '(default: 2.5)'
        ),
        'ai_google': 'Generative AI summary of changes (BETA)',
    }

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: ZoneInfo | None = None,
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

        def load_image_from_web(url: str) -> Image.Image:
            """Fetches the image from an url."""
            logging.debug(f'Retrieving image from {url}')
            with httpx.stream('GET', url, timeout=10) as response:
                response.raise_for_status()
                return Image.open(BytesIO(b''.join(response.iter_bytes())))

        def load_image_from_file(filename: str) -> Image.Image:
            """Load an image from a file."""
            logging.debug(f'Reading image from {filename}')
            return Image.open(filename)

        def load_image_from_base64(base_64: str) -> Image.Image:
            """Load an image from an encoded bytes object."""
            logging.debug('Retrieving image from a base64 string')
            return Image.open(BytesIO(base64.b64decode(base_64)))

        def load_image_from_ascii85(ascii85: str) -> Image.Image:
            """Load an image from an encoded bytes object."""
            logging.debug('Retrieving image from an ascii85 string')
            return Image.open(BytesIO(base64.a85decode(ascii85)))

        def compute_diff_image(img1: Image.Image, img2: Image.Image) -> tuple[Image.Image, np.float64]:
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
            final_img.format = img2.format

            return final_img, mse_value

        def ai_google(
            old_image: Image.Image,
            new_image: Image.Image,
            directives: AiGoogleDirectives,
        ) -> str:
            """Summarize changes in image using Generative AI (ALPHA)."""
            logger.info(f'Job {self.job.index_number}: Running ai_google for {self.__kind__} differ')
            warnings.warn(
                f'Job {self.job.index_number}: Using ai_google in differ {self.__kind__}, which is ALPHA, '
                f'may have bugs, and may change in the future. Please report any problems or suggestions at '
                f'https://github.com/mborsetti/webchanges/discussions.',
                RuntimeWarning,
            )

            api_version = '1beta'
            GOOGLE_AI_API_KEY = os.environ.get('GOOGLE_AI_API_KEY', '').rstrip()
            if len(GOOGLE_AI_API_KEY) != 39:
                logger.error(
                    f'Job {self.job.index_number}: Environment variable GOOGLE_AI_API_KEY not found or is of the '
                    f'incorrect length {len(GOOGLE_AI_API_KEY)} ({self.job.get_location()})'
                )
                return (
                    f'## ERROR in summarizing changes using {self.__kind__}:\n'
                    f'Environment variable GOOGLE_AI_API_KEY not found or is of the incorrect length '
                    f'{len(GOOGLE_AI_API_KEY)}.\n'
                )
            client = httpx.Client(http2=True, timeout=self.job.timeout)

            def _load_image(img_data: tuple[str, Image.Image]) -> dict[str, dict[str, str] | Exception | str]:
                img_name, image = img_data
                # Convert image to bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format=image.format)
                image_data = img_byte_arr.getvalue()
                mime_type = f'image/{image.format.lower()}'  # type: ignore[union-attr]

                logger.info(
                    f'Job {self.job.index_number}: Loading {img_name} ({image.format}) to Google AI '
                    f'({len(image_data) / 1024:,.0f} kbytes)'
                )

                # Initial resumable upload request
                headers = {
                    'X-Goog-Upload-Protocol': 'resumable',
                    'X-Goog-Upload-Command': 'start',
                    'X-Goog-Upload-Header-Content-Length': str(len(image_data)),
                    'X-Goog-Upload-Header-Content-Type': mime_type,
                    'Content-Type': 'application/json',
                }
                data = {'file': {'display_name': 'TEXT'}}

                try:
                    response = client.post(
                        f'https://generativelanguage.googleapis.com/upload/v{api_version}/files?'
                        f'key={GOOGLE_AI_API_KEY}',
                        headers=headers,
                        json=data,
                    )
                except httpx.HTTPError as e:
                    return {'error': e, 'img_name': img_name}
                upload_url = response.headers['X-Goog-Upload-Url']

                # Upload the image data
                headers = {
                    'Content-Length': str(len(image_data)),
                    'X-Goog-Upload-Offset': '0',
                    'X-Goog-Upload-Command': 'upload, finalize',
                }
                try:
                    response = client.post(upload_url, headers=headers, content=image_data)
                except httpx.HTTPError as e:
                    return {'error': e, 'img_name': img_name}

                # Extract file URI from response
                file_info = response.json()
                file_uri = file_info['file']['uri']
                logger.info(f'Job {self.job.index_number}: {img_name.capitalize()} loaded to {file_uri}')

                return {
                    'file_data': {
                        'mime_type': mime_type,
                        'file_uri': file_uri,
                    }
                }

            # Create a diff image
            # diff_image = ImageChops.difference(old_image, new_image)
            # diff_image.format = new_image.format

            # upload to Google
            additional_parts: list[dict[str, dict[str, str]]] = []
            executor = ThreadPoolExecutor()
            for additional_part in executor.map(
                _load_image,
                (
                    ('old image', old_image),
                    ('new image', new_image),
                    # ('differences image', diff_image),
                ),
            ):
                if 'error' not in additional_part:
                    additional_parts.append(additional_part)  # type: ignore[arg-type]
                else:
                    logger.error(
                        f'Job {self.job.index_number}: ai_google for {self.__kind__} HTTP Client error '
                        f"{type(additional_part['error'])} when loading {additional_part['img_name']} to Google AI: "
                        f"{additional_part['error']}"
                    )
                    return (
                        f"HTTP Client error {type(additional_part['error'])} when loading "
                        f"{additional_part['img_name']} to Google AI: {additional_part['error']}"
                    )

            system_instructions = (
                'You are a skilled journalist tasked with summarizing the key differences between two versions '
                'of the same image. The audience for your summary is already familiar with the image, so you can'
                'focus on the most significant changes.'
            )
            model_prompt = (
                '**Instructions:**\n\n'
                f"1. Compare the new image {additional_parts[1]['file_data']['file_uri']} to the old image "
                f"{additional_parts[0]['file_data']['file_uri']}, focusing only on major changes.\n"
                '2. Summarize the meaning of the changes in a clear and concise manner. Be specific.\n'
                '3. Use Markdown formatting to structure your summary effectively. Use headings, bullet points, and '
                'other Markdown elements as needed to enhance readability.\n'
                '4. Restrict your analysis and summary to these two specific images. Do not introduce external '
                'information or assumptions. Do not introduce knowledge from images you may have already seen.\n'
            )
            summary = AIGoogleDiffer._send_to_model(
                self.job,
                system_instructions,
                model_prompt,
                additional_parts=additional_parts,  # type: ignore[arg-type]
                directives=directives,
            )
            return summary

        data_type = directives.get('data_type', 'url')
        mse_threshold = directives.get('mse_threshold', 2.5)
        if not isinstance(self.state.old_data, str):
            raise ValueError('old_data is not a string')
        if not isinstance(self.state.new_data, str):
            raise ValueError('new_data is not a string')
        if data_type == 'url':
            old_image = load_image_from_web(self.state.old_data)
            new_image = load_image_from_web(self.state.new_data)
            old_data = f' (<a href="{self.state.old_data}">Old image</a>)'
            new_data = f' (<a href="{self.state.new_data}">New image</a>)'
        elif data_type == 'ascii85':
            old_image = load_image_from_ascii85(self.state.old_data)
            new_image = load_image_from_ascii85(self.state.new_data)
            old_data = ''
            new_data = ''
        elif data_type == 'base64':
            old_image = load_image_from_base64(self.state.old_data)
            new_image = load_image_from_base64(self.state.new_data)
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
                new_image = new_image.resize(old_image.size, Image.Resampling.LANCZOS)
                new_image.format = img_format

            else:
                logging.debug(f'Job {self.job.index_number}: Shrinking the old image')
                img_format = old_image.format
                old_image = old_image.resize(new_image.size, Image.Resampling.LANCZOS)
                old_image.format = img_format

        if old_image == new_image:
            logger.info(f'Job {self.job.index_number}: New image is identical to the old one')
            self.state.verb = 'unchanged'
            return {'text': '', 'markdown': '', 'html': ''}

        diff_image, mse_value = compute_diff_image(old_image, new_image)
        if mse_value:
            logger.debug(f'Job {self.job.index_number}: MSE value {mse_value:.2f}')

        if mse_value and mse_value < mse_threshold:
            logger.info(
                f'Job {self.job.index_number}: MSE value {mse_value:.2f} below the threshold of {mse_threshold}; '
                f'considering changes not worthy of a report'
            )
            self.state.verb = 'changed,no_report'
            return {'text': '', 'markdown': '', 'html': ''}

        # Convert the difference image to a base64 object
        output_stream = BytesIO()
        diff_image.save(output_stream, format=diff_image.format)
        encoded_diff = b64encode(output_stream.getvalue()).decode()

        # Convert the new image to a base64 object
        output_stream = BytesIO()
        new_image.save(output_stream, format=new_image.format)
        encoded_new = b64encode(output_stream.getvalue()).decode()

        # prepare AI summary
        summary = ''
        if 'ai_google' in directives:
            summary = ai_google(old_image, new_image, directives.get('ai_google', {}))

        # Prepare HTML output
        htm = [
            f'<span style="font-family:monospace">'
            # f'Differ: {self.__kind__} for {data_type}',
            f'<span style="color:darkred;">--- @ {self.make_timestamp(self.state.old_timestamp, tz)}{old_data}</span>',
            f'<span style="color:darkgreen;">+++ @ {self.make_timestamp(self.state.new_timestamp, tz)}{new_data}'
            '</span>',
            '</span>',
            'New image:',
        ]
        if data_type == 'url':
            htm.append(f'<img src="{self.state.old_data}" style="max-width: 100%; display: block;">')
        else:
            htm.append(
                f'<img src="data:image/{(new_image.format or "").lower()};base64,{encoded_new}" '
                'style="max-width: 100%; display: block;">'
            )
        htm.extend(
            [
                'Differences from old (in yellow):',
                f'<img src="data:image/{(diff_image.format or "").lower()};base64,{encoded_diff}" '
                'style="max-width: 100%; display: block;">',
            ]
        )
        changed_text = 'The image has changed; please see an HTML report for the visualization.'
        if not summary:
            return {
                'text': changed_text,
                'markdown': changed_text,
                'html': '<br>\n'.join(htm),
            }

        newline = '\n'  # For Python < 3.12 f-string {} compatibility
        back_n = '\\n'  # For Python < 3.12 f-string {} compatibility
        directives_text = (
            ', '.join(
                f'{key}={str(value).replace(newline, back_n)}' for key, value in directives.get('ai_google', {}).items()
            )
            or 'None'
        )
        footer = f'Summary generated by Google Generative AI (ai_google directive(s): {directives_text})'
        return {
            'text': f'{summary}\n\n\nA visualization is available in HTML reports.\n------------\n{footer}',
            'markdown': f'{summary}\n\n\nA visualization is available in HTML reports.\n* * *\n{footer}',
            'html': '<br>\n'.join(
                [
                    mark_to_html(summary, extras={'tables'}).replace('<h2>', '<h3>').replace('</h2>', '</h3>'),
                    '',
                ]
                + htm
                + [
                    '-----',
                    f'<i><small>{footer}</small></i>',
                ]
            ),
        }


class AIGoogleDiffer(DifferBase):
    """(Default) Generates a summary using Google Generative AI (Gemini models).

    Calls Google Gemini APIs; documentation at https://ai.google.dev/api/rest and tutorial at
    https://ai.google.dev/tutorials/rest_quickstart

    """

    __kind__ = 'ai_google'

    __supported_directives__ = {
        'model': (
            'model name from https://ai.google.dev/gemini-api/docs/models/gemini (default: gemini-1.5-flash-latest)'
        ),
        'system_instructions': (
            'Optional tone and style instructions for the model (default: see documentation at'
            'https://webchanges.readthedocs.io/en/stable/differs.html#ai-google-diff)'
        ),
        'prompt': 'a custom prompt - {unified_diff}, {unified_diff_new}, {old_text} and {new_text} will be replaced',
        'additions_only': 'summarizes only added lines (including as a result of a change)',
        'prompt_ud_context_lines': 'the number of context lines for {unified_diff} (default: 9999)',
        'timeout': 'the number of seconds before timing out the API call (default: 300)',
        'max_output_tokens': "the maximum number of tokens returned by the model (default: None, i.e. model's default)",
        'temperature': "the model's Temperature parameter (default: 0.0)",
        'top_p': "the model's TopP parameter (default: None, i.e. model's default",
        'top_k': "the model's TopK parameter (default: None, i.e. model's default",
        'tools': "data passed on to the API's 'tools' field (default: None)",
        'unified': 'directives passed to the unified differ (default: None)',
    }
    __default_subdirective__ = 'model'

    @staticmethod
    def _send_to_model(
        job: JobBase,
        system_instructions: str,
        model_prompt: str,
        additional_parts: list[dict[str, str | dict[str, str]]] | None = None,
        directives: AiGoogleDirectives | None = None,
    ) -> str:
        """Creates the summary request to the model"""
        api_version = '1beta'
        if directives is None:
            directives = {}
        if 'model' not in directives:
            directives['model'] = 'gemini-1.5-pro'  # also for footer
        model = directives.get('model')
        timeout = directives.get('timeout', 300)
        max_output_tokens = directives.get('max_output_tokens')
        temperature = directives.get('temperature', 0.0)
        top_p = directives.get('top_p')
        top_k = directives.get('top_k')

        GOOGLE_AI_API_KEY = os.environ.get('GOOGLE_AI_API_KEY', '').rstrip()
        if len(GOOGLE_AI_API_KEY) != 39:
            logger.error(
                f'Job {job.index_number}: Environment variable GOOGLE_AI_API_KEY not found or is of the '
                f'incorrect length {len(GOOGLE_AI_API_KEY)} ({job.get_location()})'
            )
            return (
                f'## ERROR in summarizing changes using Google AI:\n'
                f'Environment variable GOOGLE_AI_API_KEY not found or is of the incorrect length '
                f'{len(GOOGLE_AI_API_KEY)}.\n'
            )

        data: dict[str, Any] = {
            'system_instruction': {'parts': [{'text': system_instructions}]},
            'contents': [{'parts': [{'text': model_prompt}]}],
            'generation_config': {
                'max_output_tokens': max_output_tokens,
                'temperature': temperature,
                'top_p': top_p,
                'top_k': top_k,
            },
        }
        if additional_parts:
            data['contents'][0]['parts'].extend(additional_parts)
        if directives.get('tools'):
            data['tools'] = directives['tools']
        logger.info(f'Job {job.index_number}: Making the content generation request to Google AI model {model}')
        try:
            r = httpx.Client(http2=True).post(  # noqa: S113 Call to httpx without timeout
                f'https://generativelanguage.googleapis.com/v{api_version}/models/{model}:generateContent?'
                f'key={GOOGLE_AI_API_KEY}',
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=timeout,
            )
            if r.is_success:
                result = r.json()
                candidate = result['candidates'][0]
                logger.info(f"Job {job.index_number}: AI generation finished by {candidate['finishReason']}")
                if 'content' in candidate:
                    summary: str = candidate['content']['parts'][0]['text'].rstrip()
                else:
                    summary = (
                        f'AI summary unavailable: Model did not return any candidate output:\n'
                        f'{jsonlib.dumps(result, ensure_ascii=True, indent=2)}'
                    )
            elif r.status_code == 400:
                summary = (
                    f'AI summary unavailable: Received error from {r.url.host}: '
                    f"{r.json().get('error', {}).get('message') or ''}"
                )
            else:
                summary = (
                    f'AI summary unavailable: Received error {r.status_code} {r.reason_phrase} from ' f'{r.url.host}'
                )
                if r.content:
                    summary += f": {r.json().get('error', {}).get('message') or ''}"

        except httpx.HTTPError as e:
            summary = (
                f'AI summary unavailable: HTTP client error: {e} when requesting data from ' f'{e.request.url.host}'
            )

        return summary

    def differ(
        self,
        directives: AiGoogleDirectives,  # type: ignore[override]
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: ZoneInfo | None = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        logger.info(f'Job {self.job.index_number}: Running the {self.__kind__} differ from hooks.py')
        warnings.warn(
            f'Job {self.job.index_number}: Using differ {self.__kind__}, which is BETA, may have bugs, and may '
            f'change in the future. Please report any problems or suggestions at '
            f'https://github.com/mborsetti/webchanges/discussions.',
            RuntimeWarning,
        )

        def get_ai_summary(prompt: str, system_instructions: str) -> str:
            """Generate AI summary from unified diff, or an error message"""
            GOOGLE_AI_API_KEY = os.environ.get('GOOGLE_AI_API_KEY', '').rstrip()
            if len(GOOGLE_AI_API_KEY) != 39:
                logger.error(
                    f'Job {self.job.index_number}: Environment variable GOOGLE_AI_API_KEY not found or is of the '
                    f'incorrect length {len(GOOGLE_AI_API_KEY)} ({self.job.get_location()})'
                )
                return (
                    f'## ERROR in summarizing changes using {self.__kind__}:\n'
                    f'Environment variable GOOGLE_AI_API_KEY not found or is of the incorrect length '
                    f'{len(GOOGLE_AI_API_KEY)}.\n'
                )

            if 'model' not in directives:
                directives['model'] = 'gemini-1.5-flash-latest'  # also for footer

            if '{unified_diff' in prompt:  # matches unified_diff or unified_diff_new
                default_context_lines = 9999 if '{unified_diff}' in prompt else 0  # none if only unified_diff_new
                context_lines = directives.get('prompt_ud_context_lines', default_context_lines)
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

            if '{unified_diff_new}' in prompt:
                unified_diff_new_lines = []
                for line in unified_diff.splitlines():
                    if line.startswith('+'):
                        unified_diff_new_lines.append(line[1:])
                unified_diff_new = '\n'.join(unified_diff_new_lines)
            else:
                unified_diff_new = ''

            # check if data is different (same data is sent during testing)
            if '{old_text}' in prompt and '{new_text}' in prompt and self.state.old_data == self.state.new_data:
                return ''

            model_prompt = prompt.format(
                unified_diff=unified_diff,
                unified_diff_new=unified_diff_new,
                old_text=self.state.old_data,
                new_text=self.state.new_data,
            )

            summary = self._send_to_model(
                self.job,
                system_instructions,
                model_prompt,
                directives=directives,
            )

            return summary

        if directives.get('additions_only') or self.job.additions_only:
            default_system_instructions = (
                'You are a skilled journalist. Your task is to summarize the provided text in a clear and concise '
                'manner. Restrict your analysis and summary *only* to the text provided. Do not introduce any '
                'external information or assumptions.\n\n'
                'Format your summary using Markdown. Use headings, bullet points, and other Markdown elements where '
                'appropriate to create a well-structured and easily readable summary.'
            )
            default_prompt = '{unified_diff_new}'
        else:
            default_system_instructions = (
                'You are a skilled journalist tasked with analyzing two versions of a text and summarizing the key '
                'differences in meaning between them. The audience for your summary is already familiar with the '
                "text's content, so you can focus on the most significant changes.\n\n"
                "**Instructions:**\n\n'"
                '1. Carefully examine the old version of the text, provided within the `<old_version>` and '
                '`</old_version>` tags.\n'
                '2. Carefully examine the new version of the text, provided within the `<new_version>` and '
                '`</new_version>` tags.\n'
                '3. Compare the two versions, identifying areas where the meaning differs. This includes additions, '
                'removals, or alterations that change the intended message or interpretation.\n'
                '4. Ignore changes that do not affect the overall meaning, even if the wording has been modified.\n'
                '5. Summarize the identified differences, except those ignored, in a clear and concise manner, '
                'explaining how the meaning has shifted or evolved in the new version compared to the old version only '
                'when necessary. Be specific and provide examples to illustrate your points when needed.\n'
                '6. If ther are only additions to the text, then summarize the additions.\n'
                '7. Use Markdown formatting to structure your summary effectively. Use headings, bullet points, '
                'and other Markdown elements as needed to enhance readability.\n'
                '8. Restrict your analysis and summary to the information provided within the `<old_version>` and '
                '`<new_version> tags. Do not introduce external information or assumptions.\n'
            )
            default_prompt = '<old_version>\n{old_text}\n</old_version>\n\n<new_version>\n{new_text}\n</new_version>'
        system_instructions = directives.get('system_instructions', default_system_instructions)
        prompt = directives.get('prompt', default_prompt).replace('\\n', '\n')
        summary = get_ai_summary(prompt, system_instructions)
        if not summary:
            self.state.verb = 'changed,no_report'
            return {'text': '', 'markdown': '', 'html': ''}
        newline = '\n'  # For Python < 3.12 f-string {} compatibility
        back_n = '\\n'  # For Python < 3.12 f-string {} compatibility
        directives_text = (
            ', '.join(f'{key}={str(value).replace(newline, back_n)}' for key, value in directives.items()) or 'None'
        )
        footer = f'Summary generated by Google Generative AI (differ directive(s): {directives_text})'
        temp_unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] = {}
        for rep_kind in ['text', 'html']:  # markdown is same as text
            unified_report = DifferBase.process(
                'unified',
                directives.get('unified') or {},  # type: ignore[arg-type]
                self.state,
                rep_kind,  # type: ignore[arg-type]
                tz,
                temp_unfiltered_diff,
            )
        return {
            'text': f"{summary}\n\n{unified_report['text']}\n------------\n{footer}",
            'markdown': f"{summary}\n\n{unified_report['markdown']}\n* * *\n{footer}",
            'html': '\n'.join(
                [
                    mark_to_html(summary, extras={'tables'}).replace('<h2>', '<h3>').replace('</h2>', '</h3>'),
                    '<br>',
                    '<br>',
                    unified_report['html'],
                    '-----<br>',
                    f'<i><small>{footer}</small></i>',
                ]
            ),
        }


class WdiffDiffer(DifferBase):
    __kind__ = 'wdiff'

    __supported_directives__: dict[str, str] = {
        'context_lines': 'the number of context lines (default: 3)',
        'range_info': 'include range information lines (default: true)',
    }

    def differ(
        self,
        directives: dict[str, Any],
        report_kind: Literal['text', 'markdown', 'html'],
        _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
        tz: ZoneInfo | None = None,
    ) -> dict[Literal['text', 'markdown', 'html'], str]:
        warnings.warn(
            f'Job {self.job.index_number}: Differ {self.__kind__} is WORK IN PROGRESS and has KNOWN bugs which '
            "are being worked on. DO NOT USE AS THE RESULTS WON'T BE CORRECT.",
            RuntimeWarning,
        )
        if not isinstance(self.state.old_data, str):
            raise ValueError
        if not isinstance(self.state.new_data, str):
            raise ValueError

        # Split the texts into words tokenizing newline
        if self.state.is_markdown():
            # Don't split spaces in link text, tokenize space as </s>
            old_data = re.sub(r'\[(.*?)\]', lambda x: '[' + x.group(1).replace(' ', '</s>') + ']', self.state.old_data)
            words1 = old_data.replace('\n', ' <\\n> ').split(' ')
            new_data = re.sub(r'\[(.*?)\]', lambda x: '[' + x.group(1).replace(' ', '</s>') + ']', self.state.new_data)
            words2 = new_data.replace('\n', ' <\\n> ').split(' ')
        else:
            words1 = self.state.old_data.replace('\n', ' <\\n> ').split(' ')
            words2 = self.state.new_data.replace('\n', ' <\\n> ').split(' ')

        # Create a Differ object
        import difflib

        d = difflib.Differ()

        # Generate a difference list
        diff = list(d.compare(words1, words2))

        add_html = '<span style="background-color:#d1ffd1;color:#082b08;">'
        rem_html = '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">'

        head_text = (
            # f'Differ: wdiff\n'
            f'\033[91m--- @ {self.make_timestamp(self.state.old_timestamp, tz)}\033[0m\n'
            f'\033[92m+++ @ {self.make_timestamp(self.state.new_timestamp, tz)}\033[0m\n'
        )
        head_html = '<br>\n'.join(
            [
                '<span style="font-family:monospace;">'
                # 'Differ: wdiff',
                f'<span style="color:darkred;">--- @ {self.make_timestamp(self.state.old_timestamp, tz)}</span>',
                f'<span style="color:darkgreen;">+++ @ {self.make_timestamp(self.state.new_timestamp, tz)}</span>'
                f'</span>',
                '',
            ]
        )
        # Process the diff output to make it more wdiff-like
        result_text = []
        result_html = []
        prev_word_text = ''
        prev_word_html = ''
        next_text = ''
        next_html = ''
        add = False
        rem = False

        for word_text in diff + ['  ']:
            if word_text[0] == '?':  # additional context line
                continue
            word_html = word_text
            pre_text = [next_text] if next_text else []
            pre_html = [next_html] if next_html else []
            next_text = ''
            next_html = ''

            if word_text[0] == '+' and not add:  # Beginning of additions
                if rem:
                    prev_word_html += '</span>'
                    rem = False
                if word_text[2:] == '<\\n>':
                    next_text = '\033[92m'
                    next_html = add_html
                else:
                    pre_text.append('\033[92m')
                    pre_html.append(add_html)
                add = True
            elif word_text[0] == '-' and not rem:  # Beginning of deletions
                if add:
                    prev_word_html += '</span>'
                    add = False
                if word_text[2:] == '<\\n>':
                    next_text = '\033[91m'
                    next_html = rem_html
                else:
                    pre_text.append('\033[91m')
                    pre_html.append(rem_html)
                rem = True
            elif word_text[0] == ' ' and (add or rem):  # Unchanged word
                if prev_word_text == '<\\n>':
                    prev_word_text = '\033[0m<\\n>'
                    prev_word_html = '</span><\\n>'
                else:
                    prev_word_text += '\033[0m'
                    prev_word_html += '</span>'
                add = False
                rem = False
            elif word_text[2:] == '<\\n>':  # New line
                if add:
                    word_text = '  \033[0m<\\n>'
                    word_html = '  </span><\\n>'
                    add = False
                elif rem:
                    word_text = '  \033[0m<\\n>'
                    word_html = '  </span><\\n>'
                    rem = False

            result_text.append(prev_word_text)
            result_html.append(prev_word_html)
            pre_text.append(word_text[2:])
            pre_html.append(word_html[2:])
            prev_word_text = ''.join(pre_text)
            prev_word_html = ''.join(pre_html)
        if add or rem:
            result_text[-1] += '\033[0m'
            result_html[-1] += '</span>'

        # rebuild the text from words, replacing the newline token
        diff_text = ' '.join(result_text[1:]).replace('<\\n> ', '\n').replace('<\\n>', '\n')
        diff_html = ' '.join(result_html[1:]).replace('<\\n> ', '\n').replace('<\\n>', '\n')

        # build contextlines
        contextlines = directives.get('context_lines', self.job.contextlines)
        # contextlines = 999
        if contextlines is None:
            contextlines = 3
        range_info = directives.get('range_info', True)
        if contextlines < len(diff_text.splitlines()):
            lines_with_changes = []
            for i, line in enumerate(diff_text.splitlines()):
                if '\033[9' in line:
                    lines_with_changes.append(i)
            if contextlines:
                lines_to_keep: set[int] = set()
                for i in lines_with_changes:
                    lines_to_keep.update(r for r in range(i - contextlines, i + contextlines + 1))
            else:
                lines_to_keep = set(lines_with_changes)
            new_diff_text = []
            new_diff_html = []
            last_line = 0
            skip = False
            i = 0
            for i, (line_text, line_html) in enumerate(zip(diff_text.splitlines(), diff_html.splitlines())):
                if i in lines_to_keep:
                    if range_info and skip:
                        new_diff_text.append(f'@@ {last_line + 1}...{i} @@')
                        new_diff_html.append(f'@@ {last_line + 1}...{i} @@')
                        skip = False
                    new_diff_text.append(line_text)
                    new_diff_html.append(line_html)
                    last_line = i + 1
                else:
                    skip = True
            if (i + 1) != last_line:
                if range_info and skip:
                    new_diff_text.append(f'@@ {last_line + 1}...{i + 1} @@')
                    new_diff_html.append(f'@@ {last_line + 1}...{i + 1} @@')
            diff_text = '\n'.join(new_diff_text)
            diff_html = '\n'.join(new_diff_html)

        if self.state.is_markdown():
            diff_text = diff_text.replace('</s>', ' ')
            diff_html = diff_html.replace('</s>', ' ')
            diff_html = mark_to_html(diff_html, self.job.markdown_padded_tables).replace('<p>', '').replace('</p>', '')

        if self.job.monospace:
            diff_html = f'<span style="font-family:monospace;white-space:pre-wrap">{diff_html}</span>'
        else:
            diff_html = diff_html.replace('\n', '<br>\n')

        return {
            'text': head_text + diff_text,
            'markdown': head_text + diff_text,
            'html': head_html + diff_html,
        }
