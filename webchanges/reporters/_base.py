"""Base classes for reporters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import html
import itertools
import logging
import re
from typing import TYPE_CHECKING, Any, Iterable, TypeAlias
from zoneinfo import ZoneInfo

from webchanges import __project_name__, __url__, __version__
from webchanges.jobs import UrlJob
from webchanges.util import TrackSubClasses, chunk_string, dur_text, mark_to_html

if TYPE_CHECKING:
    from pathlib import Path

    from webchanges.handler import JobState, Report
    from webchanges.storage import (
        _ConfigDifferDefaults,
        _ConfigReportBrowser,
        _ConfigReportDiscord,
        _ConfigReportEmail,
        _ConfigReportIfttt,
        _ConfigReportMailgun,
        _ConfigReportMatrix,
        _ConfigReportNtfy,
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
        | _ConfigReportNtfy
        | _ConfigReportProwl
        | _ConfigReportPushbullet
        | _ConfigReportPushover
        | _ConfigReportRunCommand
        | _ConfigReportStdout
        | _ConfigReportTelegram
        | _ConfigReportWebhook
        | _ConfigReportXmpp
    )

# https://stackoverflow.com/questions/712791
try:
    import httpx
    from httpx import Response
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]
    try:
        import requests
        from requests import Response
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            f"A Python HTTP client package (either 'httpx' or 'requests' is required to run {__project_name__}; "
            'neither can be imported.'
        ) from e
if httpx is not None:
    from httpx import Headers

    try:
        import h2
    except ImportError:  # pragma: no cover
        h2 = None  # type: ignore[assignment]
else:
    from webchanges._vendored.headers import Headers

logger = logging.getLogger(__name__)

# Re-export for sub-modules
__all__ = [
    'Headers',
    'HtmlReporter',
    'MarkdownReporter',
    'ReporterBase',
    'Response',
    'TextReporter',
    'chunk_string',
    'httpx',
]


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
        """:param report: The Report object containing information about the report.
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
            self.footer_job_file = f' ({", ".join(f.stem for f in jobs_files)})'
        else:
            self.footer_job_file = ''
        if httpx:
            self.http_client = httpx.Client(http2=h2 is not None, follow_redirects=True)
        else:
            self.http_client = requests.Session()

    def convert(self, othercls: type[ReporterBase]) -> ReporterBase:
        """Convert self to a different ReporterBase class (object typecasting).

        :param othercls: The ReporterBase class to be cast into.
        :returns: The typecasted object.
        """
        if hasattr(othercls, '__kind__'):
            config: _ConfigReportersList = self.report.config['report'][othercls.__kind__]  # ty:ignore[invalid-key]
        else:
            config = {}

        return othercls(self.report, config, self.job_states, self.duration, self.jobs_files, self.differ_defaults)

    @classmethod
    def get_base_config(cls, report: Report) -> dict[str, Any]:
        """Gets the configuration of the base of the report (e.g. for stdout, it will be text)"""
        report_class: ReporterBase = cls.mro()[-3]  # type: ignore[assignment]
        base_config: dict[str, Any] = report.config['report'][report_class.__kind__]  # ty:ignore[invalid-key]
        return base_config

    def subject_with_args(self, filtered_job_states: list[JobState], subject: str = '') -> str:
        if not subject:
            subject = self.config.get('subject', '')
        subject_args = {
            'count': len(filtered_job_states),
            'jobs': ', '.join(job_state.job.pretty_name() for job_state in filtered_job_states),
        }
        if '{jobs_files}' in subject:
            if self.jobs_files and (len(self.jobs_files) > 1 or self.jobs_files[0].stem != 'jobs'):
                jobs_files = f' ({", ".join(f.stem.removeprefix("jobs-") for f in self.jobs_files)})'
            else:
                jobs_files = ''
            subject_args['jobs_files'] = jobs_files
        return subject.format(**subject_args)

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
        jobs_files: list[Path],
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
        cfg = report.config['report'][name]  # ty:ignore[invalid-key]
        differ_config = report.config['differ_defaults']

        if cfg.get('enabled', False) or not check_enabled:
            logger.info(f'Submitting with {name} ({subclass})')
            base_config = subclass.get_base_config(report)
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
        jobs_files: list[Path],
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
            cfg: _ConfigReportersList = report.config['report'].get(name, {})
            if cfg.get('enabled', False):
                any_enabled = True
                logger.info(f'Submitting with {name} ({subclass})')
                base_config = subclass.get_base_config(report)
                if base_config.get('separate', False):
                    for job_state in job_states:
                        subclass(report, cfg, [job_state], duration, jobs_files, differ_config=differ_config).submit()
                else:
                    subclass(report, cfg, job_states, duration, jobs_files, differ_config=differ_config).submit()

        if not any_enabled:
            logger.warning('No reporters enabled.')

    def submit(self, **kwargs: Any) -> Iterable[str]:
        """For the ReporterBase subclass, submit a job to generate the report.

        :returns: The content of the report.
        """
        raise NotImplementedError

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

    def submit(self, **kwargs: Any) -> Iterable[str]:
        """Submit a job to generate the report.

        :returns: The content of the HTML report.
        """
        yield from self._parts()

    def _parts(self) -> Iterable[str]:
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
            yield f'{self.report.config["footnote"]}\n'
        if cfg['footer']:
            if self.report.config['footnote']:
                yield '\n<hr>'
            yield (
                f'Checked {len(self.job_states)} source{"s" if len(self.job_states) > 1 else ""} in '
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

        def _format_for_return(data: str) -> str:
            if job_state.is_markdown():
                data = self.markdown_to_html(data, job_state.job.markdown_padded_tables)
            elif job_state.new_mime_type == 'text/html':
                pass
            elif not job_state.job.monospace:
                data = f'<pre style="white-space:pre-wrap">{html.escape(data)}</pre>'

            if job_state.job.monospace:
                return '<span style="font-family:monospace;white-space:pre-wrap">{0}</span>'.format(
                    data.replace('<br>\n', '\n')
                )
            return data

        if job_state.verb in ('new', 'test'):
            return _format_for_return(str(job_state.new_data))

        if job_state.verb in ('error', 'error,repeated'):
            htm = f'<pre style="white-space:pre-wrap;color:red;">{html.escape(job_state.traceback)}</pre>'
            if job_state.job.suppress_repeated_errors:
                htm += (
                    '<div style="color:maroon;"><i>Reminder: No further alerts until the error is resolved or changes.'
                    '</i></div>'
                )
            return htm

        if job_state.verb == 'unchanged,error_ended':
            return (
                f'<div style="color:green;"><i>{job_state.old_error_data.get("type")} fixed; '
                'content unchanged.</i></div>'
            )

        if job_state.verb == 'unchanged':
            return _format_for_return(str(job_state.old_data))

        if job_state.old_data is None or job_state.old_data == job_state.new_data:
            return '...'

        return job_state.get_diff('html', differ=differ, differ_defaults=self.differ_defaults, tz=self.tz)


class TextReporter(ReporterBase):
    """The base class for all reports using plain text."""

    __kind__ = 'text'

    def submit(self, **kwargs: Any) -> Iterable[str]:
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
                yield f'--\n{self.report.config["footnote"]}'
            yield (
                f'--\nChecked {len(self.job_states)} source{"s" if len(self.job_states) > 1 else ""} in '
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
        """Returns the plain text of the report for a job; called by _format_output.

        :param job_state: The JobState object with the job information.
        :param differ: The type of differ to use.
        :returns: HTML for a single job.
        """
        if job_state.verb == 'error' or job_state.verb == 'error,repeated':
            text = self._red(job_state.traceback) if hasattr(self, '_red') else job_state.traceback  # ty:ignore[call-non-callable]
            if job_state.job.suppress_repeated_errors:
                text += 'Reminder: No further alerts until the error is resolved or changes.'
            return text

        if job_state.verb == 'unchanged':
            return str(job_state.old_data)

        if job_state.verb == 'unchanged,error_ended':
            return f'{job_state.old_error_data.get("type")} fixed; content unchanged.'

        if job_state.verb in ('new', 'test'):
            return str(job_state.new_data)

        if job_state.old_data in {None, job_state.new_data}:
            return None

        return job_state.get_diff('plain', differ=differ, differ_defaults=self.differ_defaults, tz=self.tz)

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

    def submit(self, max_length: int | None = None, **kwargs: Any) -> Iterable[str]:
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
                yield f'* {": ".join((job_state.verb.replace("_", " ").upper(), location))}'
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
            footer = f'--\n{self.report.config["footnote"]}' if self.report.config['footnote'] else ''
            footer += (
                f'--\n_Checked {len(self.job_states)} source{"s" if len(self.job_states) > 1 else ""} in '
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
        if summary_len > max_length:
            return True, [], [], ''
        if footer_len > max_length - summary_len:
            return True, summary, [], footer[: max_length - summary_len]
        if not details:
            return False, summary, [], footer
        # Determine the space remaining after taking into account summary and footer.
        remaining_len = max_length - summary_len - footer_len
        headers_len = sum(len(header) for header, _ in details)

        details_trimmed = False

        # First ensure we can show all the headers.
        if headers_len > remaining_len:
            return True, summary, [], footer
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
        target_max_length = max_length - trim_message_length
        pos = s.rfind('\n', 0, target_max_length)

        # Cut short if a single long line, else (multiple lines) cut off extra lines.
        s = s[0:target_max_length] if pos == -1 else s[0:pos]

        return True, f'{trim_message}{s}'

    def _format_content(self, job_state: JobState, differ: dict[str, Any]) -> str | None:
        """Returns the Markdown of the report for a job; called by _format_output.

        :param job_state: The JobState object with the job information.
        :param differ: The type of differ to use.
        :returns: HTML for a single job.
        """
        if job_state.verb == 'error' or job_state.verb == 'error,repeated':
            mark = job_state.traceback
            if job_state.job.suppress_repeated_errors:
                mark += '_Reminder: No further alerts until the error is resolved or changes._'
            return mark

        if job_state.verb == 'unchanged':
            return str(job_state.old_data)

        if job_state.verb == 'unchanged,error_ended':
            return f'_{job_state.old_error_data.get("type")} fixed; content unchanged._'

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
