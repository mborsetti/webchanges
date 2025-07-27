"""Example hooks file for webchanges (used by test_command.py, test_handler.py, and test_storage.py)."""

import re
from pathlib import Path
from typing import Any

from webchanges.filters import AutoMatchFilter, FilterBase, RegexMatchFilter
from webchanges.handler import JobState
from webchanges.jobs import UrlJob
from webchanges.reporters import HtmlReporter, TextReporter


class CustomLoginJob(UrlJob):
    """Custom login for my webpage."""

    __kind__ = 'custom-login'
    __required__ = ('username', 'password')

    username: str
    password: str

    def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str, str]:
        ...  # custom code here
        return f'Would log in to {self.url} with {self.username} and {self.password}\n', '', ''


class CaseFilter(FilterBase):
    """Custom filter for changing case, needs to be selected manually."""

    __kind__ = 'case'

    __supported_subfilters__ = {'upper': 'Upper case (default)', 'lower': 'Lower case'}

    __default_subfilter__ = 'upper'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:

        if not subfilter or subfilter.get('upper'):
            return data.upper(), mime_type
        elif subfilter.get('lower'):
            return data.lower(), mime_type
        else:
            raise ValueError(f'Unknown case subfilter {subfilter}')


class IndentFilter(FilterBase):
    """Custom filter for indenting, needs to be selected manually."""

    __kind__ = 'indent'

    __supported_subfilters__ = {'indent': 'Number of spaces to indent (default 8)'}

    __default_subfilter__ = 'indent'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        indent = int(subfilter.get('indent', 8))

        return '\n'.join((' ' * indent) + line for line in str(data).splitlines()), mime_type


class CustomMatchUrlFilter(AutoMatchFilter):
    # The AutoMatchFilter will apply automatically to all filters
    # that have the given properties set
    MATCH = {'url': 'https://example.org/'}

    # An auto-match filter does not have any subfilters
    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError

        return data.replace('foo', 'bar'), mime_type


class CustomRegexMatchUrlFilter(RegexMatchFilter):
    # Similar to AutoMatchFilter
    MATCH = {'url': re.compile('https://example.org/.*')}

    # An auto-match filter does not have any subfilters
    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        return data.replace('foo', 'bar'), mime_type


class CustomTextFileReporter(TextReporter):
    """Custom reporter that writes the text-only report to a file."""

    __kind__ = 'custom_file'

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        Path(self.config['filename']).write_text('\n'.join(super().submit()))  # type: ignore[typeddict-item]


class CustomHtmlFileReporter(HtmlReporter):
    """Custom reporter that writes the HTML report to a file."""

    __kind__ = 'custom_html'

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        Path(self.config['filename']).write_text('\n'.join(super().submit()))  # type: ignore[typeddict-item]
