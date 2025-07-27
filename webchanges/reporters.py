"""Runs reports."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import asyncio
import functools
import getpass
import html
import itertools
import logging
import os
import re
import shlex
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.s
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, TYPE_CHECKING, TypeAlias
from warnings import warn
from zoneinfo import ZoneInfo

from markdown2 import Markdown

from webchanges import __project_name__, __url__, __version__
from webchanges.jobs import UrlJob
from webchanges.mailer import Mailer, SendmailMailer, SMTPMailer
from webchanges.util import chunk_string, dur_text, mark_to_html, TrackSubClasses

# https://stackoverflow.com/questions/712791
try:
    import simplejson as jsonlib
except ImportError:  # pragma: no cover
    import json as jsonlib  # type: ignore[no-redef]

try:
    import httpx
    from httpx import Response
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]
    try:
        import requests
        from requests import Response  # type: ignore[assignment]
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            f"A Python HTTP client package (either 'httpx' or 'requests' is required to run {__project_name__}; "
            'neither can be imported.'
        ) from e
if httpx is not None:
    try:
        import h2
    except ImportError:  # pragma: no cover
        h2 = None  # type: ignore[assignment]


# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    from webchanges.handler import JobState, Report
    from webchanges.storage import (
        _ConfigDifferDefaults,
        _ConfigReportBrowser,
        _ConfigReportDiscord,
        _ConfigReportEmail,
        _ConfigReportGotify,
        _ConfigReportIfttt,
        _ConfigReportMailgun,
        _ConfigReportMatrix,
        _ConfigReportProwl,
        _ConfigReportPushbullet,
        _ConfigReportPushover,
        _ConfigReportRunCommand,
        _ConfigReportStdout,
        _ConfigReportTelegram,
        _ConfigReportWebhook,
        _ConfigReportXmpp,
    )

    _ConfigReportersList: TypeAlias = (
        _ConfigReportBrowser
        | _ConfigReportDiscord
        | _ConfigReportEmail
        | _ConfigReportIfttt
        | _ConfigReportMailgun
        | _ConfigReportMatrix
        | _ConfigReportProwl
        | _ConfigReportPushbullet
        | _ConfigReportPushover
        | _ConfigReportRunCommand
        | _ConfigReportStdout
        | _ConfigReportTelegram
        | _ConfigReportWebhook
        | _ConfigReportXmpp
    )

try:
    import aioxmpp
except ImportError as e:  # pragma: no cover
    aioxmpp = str(e)  # type: ignore[assignment]

try:
    import chump
except ImportError as e:  # pragma: no cover
    chump = str(e)  # type: ignore[assignment]

try:
    import keyring
except ImportError as e:  # pragma: no cover
    keyring = str(e)  # type: ignore[assignment]

try:
    import matrix_client.api
except ImportError as e:  # pragma: no cover
    matrix_client = str(e)  # type: ignore[assignment]

if sys.platform == 'win32':
    try:
        from colorama import AnsiToWin32
    except ImportError as e:  # pragma: no cover
        AnsiToWin32 = str(e)  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class ReporterBase(metaclass=TrackSubClasses):
    """Base class for reporting."""

    __subclasses__: dict[str, type[ReporterBase]] = {}
    __anonymous_subclasses__: list[type[ReporterBase]] = []
    __kind__: str = ''

    def __init__(
        self,
        report: Report,
        config: _ConfigReportersList,
        job_states: list[JobState],
        duration: float,
        jobs_files: list[Path],
        differ_config: _ConfigDifferDefaults,
    ) -> None:
        """
        :param report: The Report object containing information about the report.
        :param config: The configuration of the run (typically from config.yaml).
        :param job_states: The list of JobState objects containing the information about the jobs that were retrieved.
        :param duration: The duration of the retrieval of jobs.
        :param jobs_files: The list of paths to the files containing the list of jobs (optional, used in footers).
        :param differ_config: The default configuration of differs (typically from config.yaml).
        """
        self.report = report
        self.config = config
        self.job_states = job_states
        self.duration = duration
        self.jobs_files = jobs_files
        self.tz = ZoneInfo(self.report.config['report']['tz']) if self.report.config['report']['tz'] else None
        self.differ_defaults = differ_config
        if jobs_files and (len(jobs_files) > 1 or jobs_files[0].stem != 'jobs'):
            self.footer_job_file = f" ({', '.join(f.stem for f in jobs_files)})"
        else:
            self.footer_job_file = ''
        if httpx:
            self.post_client = httpx.Client(http2=h2 is not None, follow_redirects=True).post  # noqa: S113 no timeout
        else:
            self.post_client = requests.post  # type: ignore[assignment]

    def convert(self, othercls: type[ReporterBase]) -> ReporterBase:
        """Convert self to a different ReporterBase class (object typecasting).

        :param othercls: The ReporterBase class to be cast into.
        :returns: The typecasted object.
        """
        if hasattr(othercls, '__kind__'):
            config: _ConfigReportersList = self.report.config['report'][
                othercls.__kind__  # type: ignore[literal-required]
            ]
        else:
            config = {}  # type: ignore[assignment]

        return othercls(self.report, config, self.job_states, self.duration, self.jobs_files, self.differ_defaults)

    @classmethod
    def get_base_config(cls, report: Report) -> dict[str, Any]:
        """Gets the configuration of the base of the report (e.g. for stdout, it will be text)"""
        report_class: ReporterBase = cls.mro()[-3]  # type: ignore[assignment]
        base_config: dict[str, Any] = report.config['report'][report_class.__kind__]  # type: ignore[literal-required]
        return base_config

    def subject_with_args(self, filtered_job_states: list[JobState], subject: str = '') -> str:
        if not subject:
            subject = self.config.get('subject', '')  # type: ignore[assignment]
        subject_args = {
            'count': len(filtered_job_states),
            'jobs': ', '.join(job_state.job.pretty_name() for job_state in filtered_job_states),
        }
        if '{jobs_files}' in subject:
            if self.jobs_files and (len(self.jobs_files) > 1 or self.jobs_files[0].stem != 'jobs'):
                jobs_files = f" ({', '.join(f.stem.removeprefix('jobs-') for f in self.jobs_files)})"
            else:
                jobs_files = ''
            subject_args['jobs_files'] = jobs_files
        subject = subject.format(**subject_args)
        return subject

    @classmethod
    def reporter_documentation(cls) -> str:
        """Generates simple reporter documentation for use in the --features command line argument.

        :returns: A string to display.
        """
        result: list[str] = []
        for sc in TrackSubClasses.sorted_by_kind(cls):
            result.extend((f'  * {sc.__kind__} - {sc.__doc__}',))
        return '\n'.join(result)

    @classmethod
    def submit_one(
        cls,
        name: str,
        report: Report,
        job_states: list[JobState],
        duration: float,
        jobs_files: list[Path] | None = None,
        check_enabled: bool | None = True,
    ) -> None:
        """Run a single named report.

        :param name: The name of report to run.
        :param report: The Report object with the information of all the reports.
        :param job_states: The list of JobState objects containing the information about each job retrieved.
        :param duration: The duration of the retrieval of jobs.
        :param jobs_files: The path(s) to the file(s) containing the list of jobs (optional, used in footers).
        :param check_enabled: Whether to check if the report is marked "enabled" in the configuration (used for
           testing)
        """
        subclass = cls.__subclasses__[name]
        cfg = report.config['report'][name]  # type: ignore[literal-required]
        differ_config = report.config['differ_defaults']

        if cfg.get('enabled', False) or not check_enabled:
            logger.info(f'Submitting with {name} ({subclass})')
            base_config = subclass.get_base_config(report)  # type: ignore[attr-defined]
            if base_config.get('separate', False):
                for job_state in job_states:
                    subclass(report, cfg, [job_state], duration, jobs_files, differ_config=differ_config).submit()
            else:
                subclass(report, cfg, job_states, duration, jobs_files, differ_config=differ_config).submit()
        else:
            raise ValueError(f'Reporter not enabled: {name}')

    @classmethod
    def submit_all(
        cls,
        report: Report,
        job_states: list[JobState],
        duration: float,
        jobs_files: list[Path] | None = None,
    ) -> None:
        """Run all (enabled) reports.

        :param report: The Report object with the information of all the reports.
        :param job_states: The list of JobState objects containing the information about each job retrieved.
        :param duration: The duration of the retrieval of jobs.
        :param jobs_files: The path(s) to the file(s) containing the list of jobs (optional, used in footers).
        """

        # sort job_states
        job_states = sorted(job_states, key=lambda x: x.job.pretty_name().lower())
        differ_config = report.config['differ_defaults']

        any_enabled = False
        for name, subclass in cls.__subclasses__.items():
            cfg: _ConfigReportersList = report.config['report'].get(name, {})  # type: ignore[assignment]
            if cfg.get('enabled', False):
                any_enabled = True
                logger.info(f'Submitting with {name} ({subclass})')
                base_config = subclass.get_base_config(report)  # type: ignore[attr-defined]
                if base_config.get('separate', False):
                    for job_state in job_states:
                        subclass(report, cfg, [job_state], duration, jobs_files, differ_config=differ_config).submit()
                else:
                    subclass(report, cfg, job_states, duration, jobs_files, differ_config=differ_config).submit()

        if not any_enabled:
            logger.warning('No reporters enabled.')

    def submit(self, **kwargs: Any) -> Iterator[str]:
        """For the ReporterBase subclass, submit a job to generate the report.

        :returns: The content of the report.
        """
        raise NotImplementedError()

    def raise_import_error(self, package_name: str, reporter_name: str, error_message: str) -> None:
        """Raise ImportError for missing package.

        :param package_name: The name of the module/package that could not be imported.
        :param reporter_name: The name of the reporter that needs the package.
        :param error_message: The error message from ImportError.

        :raises: ImportError.
        """
        raise ImportError(
            f"Python package '{package_name}' cannot be imported; cannot use the '{reporter_name}' reporter.\n"
            f'{error_message}'
        )


class HtmlReporter(ReporterBase):
    """The base class for all reports using HTML."""

    __kind__ = 'html'

    re_ptags = re.compile(r'^<p>|</p>$')
    re_htags = re.compile(r'<(/?)h\d>')
    re_tagend = re.compile(r'<(?!.*<).*>+$')

    def submit(self, **kwargs: Any) -> Iterator[str]:
        """Submit a job to generate the report.

        :returns: The content of the HTML report.
        """
        yield from self._parts()

    def _parts(self) -> Iterator[str]:
        """Generator yielding the HTML; called by submit. Calls _format_content.

        :returns: The content of the report.
        """
        cfg = self.get_base_config(self.report)

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        if not filtered_job_states:
            return
        title = self.subject_with_args(filtered_job_states, self.report.config['report']['html']['title'])

        yield (
            '<!DOCTYPE html>\n'
            '<html>\n'
            '<head>\n'
            f'<title>{title}</title>\n'
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '<meta name="color-scheme" content="light dark">\n'
            '<meta name="supported-color-schemes" content="light dark only">\n'
            '</head>\n'
            '<style>\n'
            '  :root {\n'
            '    color-scheme: light dark;\n'
            '    supported-color-schemes: light dark;\n'
            '  }\n'
            '</style>\n'
            '<body style="font-family: Roboto, Arial, Helvetica, sans-serif; font-size: 13px;">\n'
        )

        for job_state in filtered_job_states:
            differ = job_state.job.differ or {'name': cfg['diff']}
            content = self._format_content(job_state, differ)
            if content is not None and job_state.verb != 'changed,no_report':
                if hasattr(job_state.job, 'url'):
                    yield (
                        f'<h3>{job_state.verb.title()}: <a href="{html.escape(job_state.job.get_location())}">'
                        f'{html.escape(job_state.job.pretty_name())}</a></h3>'
                    )
                elif job_state.job.pretty_name() != job_state.job.get_location():
                    yield (
                        f'<h3>{job_state.verb.title()}: <span title="{html.escape(job_state.job.get_location())}">'
                        f'{html.escape(job_state.job.pretty_name())}</span></h3>'
                    )
                else:
                    yield f'<h3>{job_state.verb.title()}: {html.escape(job_state.job.get_location())}</h3>'
                if hasattr(job_state.job, 'note') and job_state.job.note:
                    yield f'<h4>{self.markdown_to_html(job_state.job.note)}</h4>'
                yield content

                yield '<hr>'

        # HTML footer
        yield '<span style="font-style:italic">'
        if self.report.config['footnote']:
            yield f"{self.report.config['footnote']}\n"
        if cfg['footer']:
            if self.report.config['footnote']:
                yield '\n<hr>'
            yield (
                f"Checked {len(self.job_states)} source{'s' if len(self.job_states) > 1 else ''} in "
                f'{dur_text(self.duration)} with <a href="{html.escape(__url__)}">{html.escape(__project_name__)}</a> '
                f'{html.escape(__version__)}{self.footer_job_file}.<br>\n'
            )
        if (
            self.report.new_release_future is not None
            and self.report.new_release_future.done()
            and self.report.new_release_future.result()
        ):
            yield (
                f'<b>New release version {self.report.new_release_future.result()} is available; we recommend '
                f'updating.</b>'
            )
        yield '</span>\n</body>\n</html>\n'

    @staticmethod
    def markdown_to_html(text: str, markdown_padded_tables: bool | None = None) -> str:
        """Return an html representation of a markdown string."""
        return '<br>\n'.join([mark_to_html(line, markdown_padded_tables) for line in text.splitlines()])

    def _format_content(self, job_state: JobState, differ: dict[str, Any]) -> str | None:
        """Returns the HTML of the report for a job; called by _parts.

        :param job_state: The JobState object with the job information.
        :param differ: The type of differ to use.
        :returns: HTML for a single job.
        """

        if job_state.verb == 'error' or job_state.verb == 'repeated_error':
            htm = f'<pre style="white-space:pre-wrap;color:red;">{html.escape(job_state.traceback)}</pre>'
            if job_state.job.suppress_repeated_errors:
                htm += (
                    '<div style="color:maroon;"><i>Reminder: No further alerts until the error is resolved or changes.'
                    '</i></div>'
                )
            return htm

        if job_state.verb == 'unchanged':
            if job_state.is_markdown():
                return self.markdown_to_html(str(job_state.old_data), job_state.job.markdown_padded_tables)
            elif job_state.new_mime_type == 'text/html':
                return str(job_state.old_data)
            else:
                return f'<pre style="white-space:pre-wrap">{html.escape(str(job_state.old_data))}</pre>'

        if job_state.verb == 'error_ended':
            return (
                f"<div style=\"color:green;\"><i>{job_state.old_error_data.get('type')} fixed; "
                'content unchanged.</i></div>'
            )

        if job_state.verb == 'new':
            if job_state.is_markdown():
                return self.markdown_to_html(str(job_state.new_data), job_state.job.markdown_padded_tables)
            elif job_state.new_mime_type == 'text/html':
                return str(job_state.new_data)
            else:
                return f'<pre style="white-space:pre-wrap">{html.escape(str(job_state.new_data))}</pre>'

        if job_state.verb == 'test':
            if job_state.is_markdown():
                data = self.markdown_to_html(str(job_state.new_data), job_state.job.markdown_padded_tables)
            elif job_state.new_mime_type == 'text/html':
                data = str(job_state.new_data)
            else:
                data = f'<pre style="white-space:pre-wrap">{html.escape(str(job_state.new_data))}</pre>'
            if job_state.job.monospace:
                return '<span style="font-family:monospace;white-space:pre-wrap">{0}</span>'.format(
                    data.replace('<br>\n', '\n')
                )
            else:
                return data

        if job_state.old_data is None or job_state.old_data == job_state.new_data:
            return '...'

        return job_state.get_diff('html', differ=differ, differ_defaults=self.differ_defaults, tz=self.tz)


class TextReporter(ReporterBase):
    """The base class for all reports using plain text."""

    __kind__ = 'text'

    def submit(self, **kwargs: Any) -> Iterator[str]:
        """Submit a job to generate the report.

        :returns: The content of the plain text report.
        """
        cfg = self.get_base_config(self.report)
        line_length = cfg['line_length']
        show_details = cfg['details']
        show_footer = cfg['footer']

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        if not filtered_job_states:
            return

        if cfg['minimal']:
            for job_state in filtered_job_states:
                pretty_name = job_state.job.pretty_name()
                location = job_state.job.get_location()
                if pretty_name != location:
                    location = f'{pretty_name} ({location})'
                yield ': '.join((job_state.verb.replace('_', ' ').upper(), location))
                if hasattr(job_state.job, 'note') and job_state.job.note:
                    yield job_state.job.note
            return

        summary = []
        details = []
        for job_state in filtered_job_states:
            summary_part, details_part = self._format_output(job_state, line_length)
            summary.extend(summary_part)
            details.extend(details_part)

        if summary:
            sep = (line_length * '=') or None
            if len(summary) == 1:
                yield from (
                    part
                    for part in itertools.chain(
                        (sep,),
                        (line for line in summary),
                        (sep, ''),
                    )
                    if part is not None
                )
            else:
                yield from (
                    part
                    for part in itertools.chain(
                        (sep,),
                        (f'{idx + 1:02}. {line}' for idx, line in enumerate(summary)),
                        (sep, ''),
                    )
                    if part is not None
                )

        if show_details:
            yield from details

        if summary and show_footer:
            # Text footer
            if self.report.config['footnote']:
                yield f"--\n{self.report.config['footnote']}"
            yield (
                f"--\nChecked {len(self.job_states)} source{'s' if len(self.job_states) > 1 else ''} in "
                f'{dur_text(self.duration)} with {__project_name__} {__version__}{self.footer_job_file}.\n'
            )
            if (
                self.report.new_release_future is not None
                and self.report.new_release_future.done()
                and self.report.new_release_future.result()
            ):
                yield (
                    f'New release version {self.report.new_release_future.result()} is available; we recommend '
                    f'updating.'
                )

    def _format_content(self, job_state: JobState, differ: dict[str, Any]) -> str | None:
        """Returns the text of the report for a job; called by _format_output.

        :param job_state: The JobState object with the job information.
        :param differ: The type of differ to use.
        :returns: HTML for a single job.
        """
        if job_state.verb == 'error' or job_state.verb == 'repeated_error':
            if isinstance(self, StdoutReporter):
                text = self._red(job_state.traceback)
            else:
                text = job_state.traceback
            if job_state.job.suppress_repeated_errors:
                text += 'Reminder: No further alerts until the error is resolved or changes.'
            return text

        if job_state.verb == 'unchanged':
            return str(job_state.old_data)

        if job_state.verb == 'error_ended':
            return f"{job_state.old_error_data.get('type')} fixed; content unchanged."

        if job_state.verb in ('new', 'test'):
            return str(job_state.new_data)

        if job_state.old_data in {None, job_state.new_data}:
            return None

        return job_state.get_diff('text', differ=differ, differ_defaults=self.differ_defaults, tz=self.tz)

    def _format_output(self, job_state: JobState, line_length: int) -> tuple[list[str], list[str]]:
        summary_part: list[str] = []
        details_part: list[str | None] = []

        pretty_name = job_state.job.pretty_name()
        location = job_state.job.get_location()
        if pretty_name != location:
            location = f'{pretty_name} ({location})'
        pretty_summary = ': '.join((job_state.verb.replace('_', ' ').upper(), pretty_name))
        summary = ': '.join((job_state.verb.replace('_', ' ').upper(), location))
        differ = job_state.job.differ or {}
        content = self._format_content(job_state, differ)
        # self._format_content may update verb to 'changed,no_report'
        if job_state.verb == 'changed,no_report':
            return [], []

        summary_part.append(pretty_summary)

        sep = (line_length * '-') or None
        details_part.extend((sep, summary, sep))
        if hasattr(job_state.job, 'note'):
            details_part.extend((job_state.job.note, ''))
        if isinstance(content, str):
            details_part.extend((content, sep))
        details_part.extend(['', ''] if sep else [''])

        return summary_part, [part for part in details_part if part is not None]


class MarkdownReporter(ReporterBase):
    """The base class for all reports using Markdown."""

    __kind__ = 'markdown'

    def submit(self, max_length: int | None = None, **kwargs: Any) -> Iterator[str]:
        """Submit a job to generate the report in Markdown format.
        We use the CommonMark spec: https://spec.commonmark.org/

        :param max_length: The maximum length of the report. Unlimited if not specified.
        :param kwargs:
        :returns: The content of the Markdown report.
        """
        cfg = self.get_base_config(self.report)
        show_details = cfg['details']
        show_footer = cfg['footer']

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        if not filtered_job_states:
            return

        if cfg['minimal']:
            for job_state in filtered_job_states:
                pretty_name = job_state.job.pretty_name()
                location = job_state.job.get_location()
                if pretty_name != location:
                    location = f'{pretty_name} ({location})'
                yield f"* {': '.join((job_state.verb.replace('_', ' ').upper(), location))}"
                if hasattr(job_state.job, 'note') and job_state.job.note:
                    yield job_state.job.note
            return

        summary: list[str] = []
        details: list[tuple[str, str]] = []
        for job_state in filtered_job_states:
            summary_part, details_part = self._format_output(job_state)
            summary.extend(summary_part)
            details.extend(details_part)

        if summary and show_footer:
            # Markdown footer
            if self.report.config['footnote']:
                footer = f"--\n{self.report.config['footnote']}"
            else:
                footer = ''

            footer += (
                f"--\n_Checked {len(self.job_states)} source{'s' if len(self.job_states) > 1 else ''} in "
                f'{dur_text(self.duration)} with {__project_name__} {__version__}{self.footer_job_file}_.\n'
            )
            if (
                self.report.new_release_future is not None
                and self.report.new_release_future.done()
                and self.report.new_release_future.result()
            ):
                footer += (
                    f'**New release version {self.report.new_release_future.result()} is available; we recommend '
                    f'updating.**\n'
                )
        else:
            footer = ''

        trimmed_msg = '**Parts of the report were omitted due to message length.**\n'
        if max_length:
            max_length -= len(trimmed_msg)

        trimmed, summary, details, footer = self._render(max_length, summary, details, footer)

        if summary:
            yield from summary
            yield ''

        if show_details:
            for header, body in details:
                yield header
                yield body
                yield ''

        if trimmed:
            yield trimmed_msg

        if summary and show_footer:
            yield footer

    @classmethod
    def _render(
        cls, max_length: int | None, summary: list[str], details: list[tuple[str, str]], footer: str
    ) -> tuple[bool, list[str], list[tuple[str, str]], str]:
        """Render the report components, trimming them if the available length is insufficient.

        :param max_length: The maximum length of the report.
        :param summary: The summary block of the report.
        :param details: The details block of the report.
        :param footer: The footer of the report.
        :returns: a tuple (trimmed, summary, details, footer).

        The first element of the tuple (trimmed) indicates whether any part of the report  was omitted due to
        maximum length. The other elements are the potentially trimmed report components (summary, details, and footer).
        """

        # The footer/summary lengths are the sum of the length of their parts
        # plus the space taken up by newlines.
        if summary:
            summary = [f'{idx + 1}. {line}' for idx, line in enumerate(summary)]
            summary_len = sum(len(part) for part in summary) + len(summary) - 1
        else:
            summary_len = 0

        footer_len = sum(len(part) for part in footer) + len(footer) - 1

        if max_length is None:
            processed_details: list[tuple[str, str]] = []
            for header, body in details:
                _, body = cls._format_details_body(body)
                processed_details.append((header, body))
            return False, summary, processed_details, footer
        else:
            if summary_len > max_length:
                return True, [], [], ''
            elif footer_len > max_length - summary_len:
                return True, summary, [], footer[: max_length - summary_len]
            elif not details:
                return False, summary, [], footer
            else:
                # Determine the space remaining after taking into account summary and footer.
                remaining_len = max_length - summary_len - footer_len
                headers_len = sum(len(header) for header, _ in details)

                details_trimmed = False

                # First ensure we can show all the headers.
                if headers_len > remaining_len:
                    return True, summary, [], footer
                else:
                    remaining_len -= headers_len

                    # Calculate approximate available length per item, shared equally between all details components.
                    body_len_per_details = remaining_len // len(details)

                    trimmed_details: list[tuple[str, str]] = []
                    unprocessed = len(details)

                    for header, body in details:
                        # Calculate the available length for the body and render it
                        avail_length = body_len_per_details - 1

                        body_trimmed, body = cls._format_details_body(body, avail_length)

                        if body_trimmed:
                            details_trimmed = True

                        if len(body) <= body_len_per_details:
                            trimmed_details.append((header, body))
                        else:
                            trimmed_details.append((header, ''))

                        # If the current item's body did not use all of its allocated space, distribute the unused space
                        # into subsequent items, unless we're at the last item already.
                        unused = body_len_per_details - len(body)
                        remaining_len -= body_len_per_details
                        remaining_len += unused
                        unprocessed -= 1

                        if unprocessed > 0:
                            body_len_per_details = remaining_len // unprocessed

                    return details_trimmed, summary, trimmed_details, footer

    @staticmethod
    def _format_details_body(s: str, max_length: int | None = None) -> tuple[bool, str]:
        """Trim the details to fit the maximum length available; add a message when so done.

        :param s: The details text to fit into the maximum length.
        :param max_length: The maximum length.
        :returns: The fitted string.
        """

        if s[:3] in {'+++', '---', '...'}:  # is a unified diff (with our '...' modification)
            lines = s.splitlines(keepends=True)
            for i in range(len(lines)):
                if i <= 1 or lines[i][:3] == '@@ ':
                    lines[i] = f'`{lines[i]}`'
            s = ''.join(lines)

        # Message to print when the diff is too long.
        trim_message = '*diff trimmed*\n'
        trim_message_length = len(trim_message)

        if max_length is None or len(s) <= max_length:
            return False, s
        else:
            target_max_length = max_length - trim_message_length
            pos = s.rfind('\n', 0, target_max_length)

            if pos == -1:
                # Just a single long line, so cut it short.
                s = s[0:target_max_length]
            else:
                # Multiple lines, cut off extra lines.
                s = s[0:pos]

            return True, f'{trim_message}{s}'

    def _format_content(self, job_state: JobState, differ: dict[str, Any]) -> str | None:
        """Returns the Markdown of the report for a job; called by _format_output.

        :param job_state: The JobState object with the job information.
        :param differ: The type of differ to use.
        :returns: HTML for a single job.
        """
        if job_state.verb == 'error' or job_state.verb == 'repeated_error':
            mark = job_state.traceback
            if job_state.job.suppress_repeated_errors:
                mark += '_Reminder: No further alerts until the error is resolved or changes._'
            return mark

        if job_state.verb == 'unchanged':
            return str(job_state.old_data)

        if job_state.verb == 'error_ended':
            return f"_{job_state.old_error_data.get('type')} fixed; content unchanged._"

        if job_state.verb == 'unchanged':
            return str(job_state.new_data)

        if job_state.old_data in {None, job_state.new_data}:
            return None

        return job_state.get_diff('markdown', differ=differ, differ_defaults=self.differ_defaults, tz=self.tz)

    def _format_output(self, job_state: JobState) -> tuple[list[str], list[tuple[str, str]]]:
        summary_part: list[str] = []
        details_part: list[tuple[str, str]] = []

        pretty_name = job_state.job.pretty_name()
        location = job_state.job.get_location()
        if pretty_name != location:
            if isinstance(job_state.job, UrlJob):
                location = f'[{pretty_name}]({location})'
            else:
                location = f'{pretty_name} ({location})'

        pretty_summary = ': '.join((job_state.verb.replace('_', ' ').upper(), pretty_name))
        summary = ': '.join((job_state.verb.replace('_', ' ').upper(), location))
        differ = job_state.job.differ or {}
        content = self._format_content(job_state, differ)  # may update verb to 'changed,no_report'
        if job_state.verb == 'changed,no_report':
            return [], []

        summary_part.append(pretty_summary)

        if content is not None:
            details_part.append((f'### {summary}', content))

        return summary_part, details_part


class StdoutReporter(TextReporter):
    """Print summary on stdout (the console)."""

    __kind__ = 'stdout'

    config: _ConfigReportStdout

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._has_color = sys.stdout.isatty() and self.config['color']

    def _incolor(self, color_id: int, s: str) -> str:
        if self._has_color:
            return f'\033[9{color_id}m{s}\033[0m'
        return s

    def _red(self, s: str) -> str:
        return self._incolor(1, s)

    def _green(self, s: str) -> str:
        return self._incolor(2, s)

    def _yellow(self, s: str) -> str:
        return self._incolor(3, s)

    def _blue(self, s: str) -> str:
        return self._incolor(4, s)

    def _get_print(self) -> Callable:
        if sys.platform == 'win32' and self._has_color and not isinstance(AnsiToWin32, str):
            return functools.partial(print, file=AnsiToWin32(sys.stdout).stream)
        return print

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        print_color = self._get_print()

        cfg = self.get_base_config(self.report)
        line_length = cfg['line_length']

        separators = (line_length * '=', line_length * '-', '--') if line_length else ()
        body = '\n'.join(super().submit())

        if any(
            differ.get('command', '').startswith('wdiff')
            for differ in (job_state.job.differ for job_state in self.job_states if job_state.job.differ)
        ):
            # wdiff colorization
            body = re.sub(r'\{\+.*?\+}', lambda x: self._green(x.group(0)), body, flags=re.DOTALL)
            body = re.sub(r'\[-.*?-]', lambda x: self._red(x.group(0)), body, flags=re.DOTALL)
            separators = (*separators, '-' * 36)

        class LineType(Enum):
            """Defines the differ line types"""

            SEPARATOR = 1
            ADDITION = 2
            DELETION = 3
            STATUS = 4
            OTHER = 5

        def get_line_type(line: str, separators: Iterable[str]) -> LineType:
            """Classifies each line"""
            if line in separators:
                return LineType.SEPARATOR
            elif line.startswith('+'):
                return LineType.ADDITION
            elif line.startswith('-'):
                return LineType.DELETION
            elif any(line.startswith(prefix) for prefix in {'NEW: ', 'CHANGED: ', 'UNCHANGED: ', 'ERROR: '}):
                return LineType.STATUS
            else:
                return LineType.OTHER

        def print_status_line(line: str, print_color: Callable, red_color: Callable, blue_color: Callable) -> None:
            """Prints a status line"""
            first, second = line.split(' ', 1)
            if line.startswith('ERROR: '):
                print_color(first, red_color(second))
            else:
                print_color(first, blue_color(second))

        def process_lines(
            body: str,
            separators: Iterable[str],
            print_color: Callable,
            green_color: Callable,
            red_color: Callable,
            blue_color: Callable,
        ) -> None:
            """Processes the lines"""
            for line in body.splitlines():
                line_type = get_line_type(line, separators)

                match line_type:
                    case LineType.SEPARATOR:
                        print_color(line)
                    case LineType.ADDITION:
                        print_color(green_color(line))
                    case LineType.DELETION:
                        print_color(red_color(line))
                    case LineType.STATUS:
                        print_status_line(line, print_color, red_color, blue_color)
                    case LineType.OTHER:
                        print_color(line)

        process_lines(body, separators, print_color, self._green, self._red, self._blue)


class EMailReporter(TextReporter):
    """Send summary via email (including SMTP)."""

    __kind__ = 'email'

    config: _ConfigReportEmail

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        body_text = '\n'.join(super().submit())

        if not body_text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        subject = self.subject_with_args(filtered_job_states)

        if self.config['method'] == 'smtp':
            smtp_config = self.config['smtp']
            smtp_user = smtp_config['user'] or self.config['from']
            use_auth = smtp_config['auth']
            mailer: Mailer = SMTPMailer(
                smtp_user,
                smtp_config['host'],
                smtp_config['port'],
                smtp_config['starttls'],
                use_auth,
                smtp_config['insecure_password'],
            )
        elif self.config['method'] == 'sendmail':
            mailer = SendmailMailer(self.config['sendmail']['path'])
        else:
            raise ValueError(f"Unknown email reporter method: {self.config['method']}")

        if self.config['html']:
            html_reporter = HtmlReporter(
                self.report, self.config, self.job_states, self.duration, self.jobs_files, self.differ_defaults
            )
            body_html = '\n'.join(html_reporter.submit())
            msg = mailer.msg(self.config['from'], self.config['to'], subject, body_text, body_html)
        else:
            msg = mailer.msg(self.config['from'], self.config['to'], subject, body_text)

        mailer.send(msg)


class IFTTTReport(TextReporter):
    """Send summary via IFTTT."""

    __kind__ = 'ifttt'

    config: _ConfigReportIfttt

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        webhook_url = 'https://maker.ifttt.com/trigger/{event}/with/key/{key}'.format(**self.config)
        for job_state in self.report.get_filtered_job_states(self.job_states):
            pretty_name = job_state.job.pretty_name()
            location = job_state.job.get_location()
            print(f'submitting {job_state}')
            result = self.post_client(
                webhook_url,
                json={
                    'value1': job_state.verb,
                    'value2': pretty_name,
                    'value3': location,
                },
                timeout=60,
            )
            if result.status_code != 200:
                raise RuntimeError(f'IFTTT error: {result.text}')


class WebServiceReporter(TextReporter):
    """Base class for other reporters, such as Pushover and Pushbullet."""

    __kind__ = 'webservice (no settings)'

    MAX_LENGTH = 1024

    def web_service_get(self) -> str:
        raise NotImplementedError

    def web_service_submit(self, service: str, title: str, body: str) -> None:
        raise NotImplementedError

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Not sending {self.__kind__} (no changes)')
            return

        if len(text) > self.MAX_LENGTH:
            text = text[: self.MAX_LENGTH]

        try:
            service = self.web_service_get()
        except Exception as e:
            raise RuntimeError(
                f'Failed to load or connect to {self.__kind__} - are the dependencies installed and configured?'
            ) from e

        self.web_service_submit(service, 'Website Change Detected', text)


class PushoverReport(WebServiceReporter):
    """Send summary via pushover.net."""

    __kind__ = 'pushover'

    config: _ConfigReportPushover

    def web_service_get(self) -> 'chump.User':
        if isinstance(chump, str):
            self.raise_import_error('chump', self.__kind__, chump)

        app = chump.Application(self.config['app'])
        return app.get_user(self.config['user'])

    def web_service_submit(self, service: 'chump.User', title: str, body: str) -> None:
        sound = self.config['sound']
        # If device is the empty string or not specified at all, use None to send to all devices
        # (see https://github.com/thp/urlwatch/issues/372)
        device = self.config['device']
        priority = {
            'lowest': chump.LOWEST,
            'low': chump.LOW,
            'normal': chump.NORMAL,
            'high': chump.HIGH,
            'emergency': chump.EMERGENCY,
        }.get(self.config['priority'], chump.NORMAL)
        msg = service.create_message(
            title=title, message=body, html=True, sound=sound, device=device, priority=priority
        )
        msg.send()


class PushbulletReport(WebServiceReporter):
    """Send summary via pushbullet.com."""

    __kind__ = 'pushbullet'

    config: _ConfigReportPushbullet

    def web_service_get(self) -> Any:
        # def web_service_get(self) -> Pushbullet:
        # Moved here as loading breaks Pytest in Python 3.13 on Windows
        # Is stuck in collecting due to File Windows fatal exception: access violation
        try:
            from pushbullet import Pushbullet
        except ImportError as e:  # pragma: no cover
            Pushbullet = str(e)  # type: ignore[assignment]

        if isinstance(Pushbullet, str):
            self.raise_import_error('pushbullet', self.__kind__, Pushbullet)

        return Pushbullet(self.config['api_key'])

    def web_service_submit(self, service: Any, title: str, body: str) -> None:
        # def web_service_submit(self, service: Pushbullet, title: str, body: str) -> None:
        service.push_note(title, body)


class MailgunReporter(TextReporter):
    """Send email via the Mailgun service."""

    __kind__ = 'mailgun'

    config: _ConfigReportMailgun

    def submit(self) -> str | None:  # type: ignore[override]
        region = self.config['region']
        domain = self.config['domain']
        api_key = self.config['api_key']
        from_name = self.config['from_name']
        from_mail = self.config['from_mail']
        to = self.config['to']

        if region == 'us':
            region = ''
        elif region != '':
            region = f'.{region}'

        body_text = '\n'.join(super().submit())
        body_html = '\n'.join(self.convert(HtmlReporter).submit())

        if not body_text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return None

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        subject = self.subject_with_args(filtered_job_states)

        logger.info(f"Sending Mailgun request for domain: '{domain}'")
        result = self.post_client(
            f'https://api{region}.mailgun.net/v3/{domain}/messages',
            auth=('api', api_key),
            data={
                'from': f'{from_name} <{from_mail}>',
                'to': to,
                'subject': subject,
                'text': body_text,
                'html': body_html,
            },
            timeout=60,
        )

        try:
            json_res = result.json()

            if result.status_code == 200:
                logger.info(f"Mailgun response: id '{json_res['id']}'. {json_res['message']}")
            else:
                raise RuntimeError(f"Mailgun error: {json_res['message']}")
        except ValueError:
            raise RuntimeError(
                f'Failed to parse Mailgun response. HTTP status code: {result.status_code}, content: {result.text}'
            ) from None
        return None


class TelegramReporter(MarkdownReporter):
    """Send a Markdown message using Telegram."""

    # See https://core.telegram.org/bots/api#formatting-options

    __kind__ = 'telegram'

    config: _ConfigReportTelegram

    def submit(self, max_length: int = 4096, **kwargs: Any) -> None:  # type: ignore[override]
        """Submit report."""
        bot_token = self.config['bot_token']
        chat_ids = self.config['chat_id']
        chat_ids_list = [chat_ids] if not isinstance(chat_ids, list) else chat_ids

        text = '\n'.join(super().submit())  # no max_length here as we will chunk later

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return None

        chunks = self.telegram_chunk_by_line(text, max_length)

        for chat_id in chat_ids_list:
            for chunk in chunks:
                self.submit_to_telegram(bot_token, chat_id, chunk)

    def submit_to_telegram(self, bot_token: str, chat_id: int | str, text: str) -> Response:
        """Submit to Telegram."""
        logger.info(f"Sending telegram message to chat id: '{chat_id}'")

        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'MarkdownV2',
            'disable_web_page_preview': True,
            'disable_notification': self.config['silent'],
        }
        result = self.post_client(f'https://api.telegram.org/bot{bot_token}/sendMessage', data=data, timeout=60)

        try:
            json_res = result.json()

            if result.status_code == 200:
                logger.info(f"Telegram response: ok '{json_res['ok']}'. {json_res['result']}")
            else:
                raise RuntimeError(f"Telegram error: {json_res['description']}")
        except ValueError:
            logger.error(
                f'Failed to parse telegram response. HTTP status code: {result.status_code}, '
                f'content: {result.content!s}'
            )

        return result

    @staticmethod
    def telegram_escape_markdown(text: str, version: int = 2, entity_type: str | None = None) -> str:
        """
        Helper function to escape telegram markup symbols. See https://core.telegram.org/bots/api#formatting-options

        Inspired by https://github.com/python-telegram-bot/python-telegram-bot/blob/master/telegram/utils/helpers.py
        v13.5 30-Apr-21

        :param text: The text.
        :param version: Use to specify the version of telegrams Markdown. Either ``1`` or ``2``. Defaults to ``2``.
        :param entity_type: For the entity types ``pre``, ``code`` and the link part of ``text_links``, only certain
            characters need to be escaped in ``MarkdownV2``. See the official API documentation for details. Only valid
            in combination with ``version=2``, will be ignored otherwise.

        :returns: The escaped text.
        """
        if version == 1:
            escape_chars = r'_*`['
        elif version == 2:
            if entity_type is None:
                escape_chars = r'\_*[]()~`>#+-=|{}.!'
            elif entity_type in {'pre', 'code'}:
                escape_chars = r'\`'
            elif entity_type == 'text_link':
                escape_chars = r'\)[]'
            else:
                raise ValueError("entity_type must be None, 'pre', 'code' or 'text_link'!")
        else:
            raise ValueError('Markdown version must be either 1 or 2!')

        text = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
        lines = text.splitlines(keepends=True)
        for i in range(len(lines)):
            if lines[i].count('\\*\\*') and not lines[i].count('\\*\\*') % 2:
                lines[i] = lines[i].replace('\\*\\*', '*')  # rebuild bolding from html2text
            if lines[i].count('\\~\\~') and not lines[i].count('\\~\\~') % 2:
                lines[i] = lines[i].replace('\\~\\~', '~')  # rebuild strikethrough from html2text

        return ''.join(lines)

    def telegram_chunk_by_line(self, text: str, max_length: int) -> list[str]:
        """Chunk-ify by line while escaping markdown as required by Telegram."""
        chunks = []

        # Escape Markdown by type
        lines = re.split(r'(`)(.*?)(`)', text)
        for i in range(len(lines)):
            if i % 4 in {1, 3}:
                continue
            base_entity = 'code' if i % 4 == 2 else None
            # subtext = re.split(r'(\[[^\][]*]\((?:https?|tel|mailto):[^()]*\))', text[i])
            subtext = re.split(r'(\[.*?]\((?:https?|tel|mailto):[^()]*\))', lines[i])
            for j in range(len(subtext)):
                if (j + 1) % 2:
                    subtext[j] = self.telegram_escape_markdown(subtext[j], entity_type=base_entity)
                else:
                    subtext[j] = ''.join(
                        [
                            '[',
                            self.telegram_escape_markdown(subtext[j][1:].split(']')[0]),
                            '](',
                            self.telegram_escape_markdown(
                                subtext[j].split('(')[-1].split(')')[0], entity_type='text_link'
                            ),
                            ')',
                        ]
                    )
            lines[i] = ''.join(subtext)

        new_text = ''.join(lines).splitlines(keepends=True)

        # check if any individual line is too long and chunk it
        if any(len(line) > max_length for line in new_text):
            new_lines: list[str] = []
            for line in new_text:
                if len(line) > max_length:
                    new_lines.extend(chunk_string(line, max_length))
                else:
                    new_lines.append(line)
            new_text = new_lines

        it_lines = iter(new_text)
        chunk_lines: list[str] = []
        pre_status = False  # keep track of whether you're in the middle of a PreCode entity to close and reopen
        try:
            while True:
                next_line = next(it_lines)
                if sum(len(line) for line in chunk_lines) + len(next_line) > max_length - pre_status * 3:
                    if pre_status:
                        chunk_lines[-1] += '```'
                    chunks.append(''.join(chunk_lines))
                    chunk_lines = [pre_status * '```' + next_line]
                else:
                    chunk_lines.append(next_line)
                if next_line.count('```') % 2:
                    pre_status = not pre_status
        except StopIteration:
            chunks.append(''.join(chunk_lines))

        return chunks


class DiscordReporter(TextReporter):
    """Send a message to a Discord channel using a discord webhook."""

    __kind__ = 'discord'

    config: _ConfigReportDiscord

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        default_max_length = 2000 if not self.config['embed'] else 4096
        if isinstance(self.config['max_message_length'], int):
            self.max_length = int(self.config['max_message_length'])
        else:
            self.max_length = default_max_length
        if self.config['colored']:
            self.max_length -= 11

    def submit(self) -> Response | None:  # type: ignore[override]
        webhook_url = self.config['webhook_url']
        text = '\n'.join(super().submit())

        if not text:
            logger.info('Not calling Discord API (no changes)')
            return None

        result = None
        for chunk in chunk_string(text, self.max_length, numbering=True):
            res = self.submit_to_discord(webhook_url, chunk)
            if res.status_code != 200 or res is None:
                result = res

        return result

    def submit_to_discord(self, webhook_url: str, text: str) -> Response:
        if self.config['colored']:
            text = '```diff\n' + text + '```'

        if self.config['embed']:
            filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
            subject = self.subject_with_args(filtered_job_states)

            # Content has a maximum length of 2000 characters, but the combined sum of characters in all title,
            # description, field.name, field.value, footer.text, and author.name fields across all embeds attached to
            # a message must not exceed 6000 characters.
            max_subject_length = min(2000, 6000 - len(text))
            subject = subject[:max_subject_length]

            post_data = {
                'content': subject,
                'embeds': [
                    {
                        'type': 'rich',
                        'description': text,
                    }
                ],
            }
        else:
            post_data = {'content': text}

        logger.info(f'Sending Discord request with post_data: {post_data}')

        result = self.post_client(webhook_url, json=post_data, timeout=60)
        try:
            if result.status_code in {200, 204}:
                logger.info('Discord response: ok')
            else:
                logger.error(f'Discord error: {result.text}')
        except ValueError:
            logger.error(
                f'Failed to parse Discord response. HTTP status code: {result.status_code}, content: {result.content!r}'
            )
        return result


class WebhookReporter(TextReporter):
    """Send a text message to a webhook such as Slack or Mattermost.  For Mattermost, set 'markdown' to true."""

    __kind__ = 'webhook'

    config: _ConfigReportWebhook

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        default_max_length = 40000
        if isinstance(self.config['max_message_length'], int):
            self.max_length = int(self.config['max_message_length'])
        else:
            self.max_length = default_max_length

    def submit(self) -> Response | None:  # type: ignore[override]
        webhook_url = self.config['webhook_url']

        if self.config['markdown']:
            markdown_reporter = MarkdownReporter(
                self.report, self.config, self.job_states, self.duration, self.jobs_files, self.differ_defaults
            )
            text = '\n'.join(markdown_reporter.submit())
        else:
            text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return None

        result = None
        for chunk in chunk_string(text, self.max_length, numbering=True):
            res = self.submit_to_webhook(webhook_url, chunk)
            if res.status_code != 200 or res is None:
                result = res

        return result

    def submit_to_webhook(self, webhook_url: str, text: str) -> Response:
        logger.debug(f'Sending request to webhook with text: {text}')
        post_data = self.prepare_post_data(text)
        result = self.post_client(webhook_url, json=post_data, timeout=60)
        try:
            if result.status_code in {200, 204}:
                logger.info('Webhook server response: ok')
            else:
                raise RuntimeError(f'Webhook server error: {result.text}')
        except ValueError:
            logger.error(
                f'Failed to parse webhook server response. HTTP status code: {result.status_code}, '
                f'content: {result.content!s}'
            )
        return result

    def prepare_post_data(
        self, text: str
    ) -> dict[str, str | list[dict[str, str | list[dict[str, str | list[dict[str, str]]]]]]]:
        if self.config.get('rich_text', False):
            return {
                'blocks': [
                    {
                        'type': 'rich_text',
                        'elements': [
                            {
                                'type': 'rich_text_preformatted',
                                'elements': [
                                    {
                                        'type': 'text',
                                        'text': text,
                                    },
                                ],
                            },
                        ],
                    }
                ]
            }
        else:
            return {'text': text}


class SlackReporter(WebhookReporter):
    """Deprecated; use webhook instead."""

    __kind__ = 'slack'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        warn("'slack' reporter is deprecated; replace with 'webhook' (same exact keys)", DeprecationWarning)
        super().__init__(*args, **kwargs)


class MatrixReporter(MarkdownReporter):
    """Send a message to a room using the Matrix protocol."""

    __kind__ = 'matrix'

    config: _ConfigReportMatrix
    MAX_LENGTH = 16384

    def submit(self, max_length: int | None = None, **kwargs: Any) -> None:  # type: ignore[override]
        if isinstance(matrix_client, str):
            self.raise_import_error('matrix_client', self.__kind__, matrix_client)

        homeserver_url = self.config['homeserver']
        access_token = self.config['access_token']
        room_id = self.config['room_id']

        body_markdown = '\n'.join(super().submit(self.MAX_LENGTH))

        if not body_markdown:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        client_api = matrix_client.api.MatrixHttpApi(homeserver_url, access_token)

        body_html = Markdown(extras=['fenced-code-blocks', 'highlightjs-lang']).convert(body_markdown)

        try:
            client_api.send_message_event(
                room_id,
                'm.room.message',
                content={
                    'msgtype': 'm.text',
                    'format': 'org.matrix.custom.html',
                    'body': body_markdown,
                    'formatted_body': body_html,
                },
            )
        except Exception as e:
            raise RuntimeError(f'Matrix error: {e}')


class XMPPReporter(TextReporter):
    """Send a message using the XMPP Protocol."""

    __kind__ = 'xmpp'

    config: _ConfigReportXmpp
    MAX_LENGTH = 262144

    def submit(self) -> None:  # type: ignore[override]
        sender = self.config['sender']
        recipient = self.config['recipient']

        text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        xmpp = XMPP(sender, recipient, self.config['insecure_password'])

        for chunk in chunk_string(text, self.MAX_LENGTH, numbering=True):
            asyncio.run(xmpp.send(chunk))


class BrowserReporter(HtmlReporter):
    """Display HTML summary using the default web browser."""

    __kind__ = 'browser'

    config: _ConfigReportBrowser

    def submit(self) -> None:  # type: ignore[override]
        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        if not filtered_job_states:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        html_reporter = HtmlReporter(
            self.report, self.config, self.job_states, self.duration, self.jobs_files, self.differ_defaults
        )
        body_html = '\n'.join(html_reporter.submit())

        # recheck after running as diff_filters can modify job_states.verb
        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        if not filtered_job_states:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        import tempfile
        import webbrowser

        f = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
        f.write(body_html)
        f.close()
        webbrowser.open(f.name)
        time.sleep(2)
        os.remove(f.name)


class XMPP:
    def __init__(self, sender: str, recipient: str, insecure_password: str | None = None) -> None:
        if isinstance(aioxmpp, str):
            raise ImportError(
                f"Python package 'aioxmpp' cannot be imported; cannot use the 'xmpp' reporter.\n" f'{aioxmpp}'
            )
        self.sender = sender
        self.recipient = recipient
        self.insecure_password = insecure_password

    async def send(self, chunk: str) -> None:
        if self.insecure_password:
            password = self.insecure_password
        elif keyring is not None:
            passw = keyring.get_password('urlwatch_xmpp', self.sender)
            if passw is None:
                raise ValueError(f'No password available in keyring for {self.sender}')
            else:
                password = passw
        else:
            raise ValueError(f'No password available for {self.sender}')

        jid = aioxmpp.JID.fromstr(self.sender)
        client = aioxmpp.PresenceManagedClient(jid, aioxmpp.make_security_layer(password))
        recipient_jid = aioxmpp.JID.fromstr(self.recipient)

        async with client.connected() as stream:
            msg = aioxmpp.Message(
                to=recipient_jid,
                type_=aioxmpp.MessageType.CHAT,
            )
            msg.body[None] = chunk

            await stream.send_and_wait_for_sent(msg)


def xmpp_have_password(sender: str) -> bool:
    if isinstance(keyring, str):
        raise ImportError(f'Python package "keyring" is non installed - service unsupported.\n{keyring}')

    return keyring.get_password('urlwatch_xmpp', sender) is not None


def xmpp_set_password(sender: str) -> None:
    """Set the keyring password for the XMPP connection. Interactive."""
    if isinstance(keyring, str):
        raise ImportError(f'Python package "keyring" is non installed - service unsupported.\n{keyring}')

    password = getpass.getpass(prompt=f'Enter password for {sender}: ')
    keyring.set_password('urlwatch_xmpp', sender, password)


class ProwlReporter(TextReporter):
    """Send a detailed notification via prowlapp.com."""

    # contributed by nitz https://github.com/thp/urlwatch/pull/633

    __kind__ = 'prowl'

    config: _ConfigReportProwl

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def submit(self) -> None:  # type: ignore[override]
        api_add = 'https://api.prowlapp.com/publicapi/add'

        text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return None

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))

        # 'subject' used in the config file, but the API uses what might be called the subject as the 'event'
        event = self.subject_with_args(filtered_job_states)

        # 'application' is prepended to the message in prowl, to show the source of the notification. this too,
        # is user configurable, and may reference subject args
        application = self.config['application']
        if application is not None:
            application = self.subject_with_args(filtered_job_states, application)
        else:
            application = f'{__project_name__} v{__version__}'

        # build the data to post
        post_data = {
            'event': event[:1024],
            'description': text[:10000],
            'application': application[:256],
            'apikey': self.config['api_key'],
            'priority': self.config['priority'],
        }

        # all set up, add the notification!
        result = self.post_client(api_add, data=post_data, timeout=60)

        try:
            if result.status_code in {200, 204}:
                logger.info('Prowl response: ok')
            else:
                raise RuntimeError(f'Prowl error: {result.text}')
        except ValueError:
            logger.error(
                f'Failed to parse Prowl response. HTTP status code: {result.status_code}, content: {result.content!s}'
            )


class RunCommandReporter(TextReporter):
    """Run a command."""

    __kind__ = 'run_command'

    config: _ConfigReportRunCommand

    def submit(self) -> None:  # type: ignore[override]
        if not self.config['command']:
            raise ValueError('Reporter "run_command" needs a command')

        text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))

        # Work on a copy to not modify the outside environment
        env = dict(os.environ)
        env.update({f'{__project_name__.upper()}_REPORT_CONFIG_JSON': jsonlib.dumps(self.report.config)})
        env.update({f'{__project_name__.upper()}_REPORT_REPORTED_JOBS_JSON': jsonlib.dumps(self.report.config)})

        subject_args = {
            'text': text,
            'count': len(filtered_job_states),
            'jobs': ', '.join(job_state.job.pretty_name() for job_state in filtered_job_states),
        }
        command = shlex.split(self.config['command'].format(**subject_args))

        try:
            result = subprocess.run(  # noqa: S603 subprocess call - check for execution of untrusted input.
                command,
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"The '{self.__kind__}' filter with command {command} returned error:\n{e.stderr}")
            raise e
        except FileNotFoundError as e:
            logger.error(f"The '{self.__kind__}' filter with command {command} returned error:\n{e}")
            raise FileNotFoundError(e, f'with command {command}')
        print(result.stdout, end='')


class ShellReporter(WebhookReporter):
    """Deprecated; use run_command instead."""

    __kind__ = 'shell'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        warn("'shell' reporter is deprecated; use 'run_command' instead", DeprecationWarning)
        super().__init__(*args, **kwargs)


class GotifyReporter(MarkdownReporter):
    """Send a message to a gotify server (https://gotify.net/)"""

    MAX_LENGTH = 16 * 1024

    __kind__ = 'gotify'

    config: _ConfigReportGotify

    def submit(self, max_length: int | None = None, **kwargs: Any) -> None:  # type: ignore[override]
        body_markdown = '\n'.join(super().submit(self.MAX_LENGTH))
        if not body_markdown:
            logger.debug('Not sending message to gotify server (no changes)')
            return

        server_url = self.config['server_url']
        url = f'{server_url}/message'

        token = self.config['token']
        headers = {'Authorization': f'Bearer {token}'}
        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        # 'subject' used in the config file, but the API uses what might be called the subject as the 'title'
        title = self.subject_with_args(filtered_job_states)
        data = {
            'extras': {
                'client::display': {
                    'contentType': 'text/markdown',
                },
            },
            'message': body_markdown,
            'priority': self.config['priority'],
            'title': title,
        }
        self.post_client(url, headers=headers, json=data)
