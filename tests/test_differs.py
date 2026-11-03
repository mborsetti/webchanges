"""Test the generation of various types of diffs.

Run individually with
> pytest -v --cov=./ --cov-report=term tests/test_differs.py

"""

from __future__ import annotations

import base64
import contextlib
import logging
import os
import random
import re
import string
import sys
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from zoneinfo import ZoneInfo

import httpx2
import pytest

from webchanges import differs
from webchanges.differs import (
    AI_GOOGLE_429_RETRY_BUFFER,
    AI_GOOGLE_503_RETRY_WAIT,
    AI_GOOGLE_MAX_TOTAL_WAIT,
    AIGoogleDiffer,
    CommandDiffer,
    DifferBase,
    UnifiedDiffer,
    WdiffDiffer,
    _ai_google_post_with_retry,
    _ai_google_retry_delay,
    _ai_google_retry_wait,
)
from webchanges.handler import JobState
from webchanges.jobs import JobBase, ShellJob
from webchanges.storage import SsdbSQLite3Storage
from webchanges.util import SettingError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

py_latest_only = cast(
    'Callable[[Callable], Callable]',
    pytest.mark.skipif(
        sys.version_info < (3, 15),
        reason='Latest python only (time consuming)',
    ),
)
# The image differ warns at every run that it is in BETA; ignore it in tests exercising it
ignore_image_beta_warning = cast(
    'Callable[[Callable], Callable]',
    pytest.mark.filterwarnings(r'ignore:Job \d+. Using differ image:RuntimeWarning'),
)
py_no_github = cast(
    'Callable[[Callable], Callable]',
    pytest.mark.skipif(
        os.getenv('GITHUB_ACTIONS') is not None,
        reason='GitHub Actions (no Google AI API calls)',
    ),
)
# py_nt_only = cast(
#     Callable[[Callable], Callable],
#     pytest.mark.skipif(
#         sys.platform == 'win32',
#         reason='Not working on Linux',
#     ),
# )

test_tz = ZoneInfo('Etc/UTC')

DIFF_TO_HTML_TEST_DATA = [
    ('+Added line', '<td style="background-color:#d1ffd1;color:#082b08;">Added line</td>'),
    (
        '-Deleted line',
        '<td style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">Deleted line</td>',
    ),
    # Changes line
    (
        '@@ -1,1 +1,1 @@',
        '<td style="font-family:monospace;background-color:#fbfbfb;">@@ -1,1 +1,1 @@</td>',
    ),
    # Horizontal ruler is manually expanded since <hr> tag is used to separate jobs
    (
        '+* * *',
        (
            '<td style="background-color:#d1ffd1;color:#082b08;">'
            '--------------------------------------------------------------------------------</td>'
        ),
    ),
    (
        '+[Link](https://example.com)',
        (
            '<td style="background-color:#d1ffd1;color:#082b08;"><a style="font-family:inherit" rel="noopener" '
            'target="_blank" href="https://example.com">Link</a></td>'
        ),
    ),
    (
        ' ![Image](https://example.com/picture.png "picture")',
        (
            '<td><img style="max-width:600px;height:auto" src="https://example.com/picture.png"'
            ' alt="Image" title="picture" /></td>'
        ),
    ),
    (
        '   Indented text (replace leading spaces)',
        '<td>&nbsp;&nbsp;Indented text (replace leading spaces)</td>',
    ),
    (' # Heading level 1', '<td><strong>Heading level 1</strong></td>'),
    (' ## Heading level 2', '<td><strong>Heading level 2</strong></td>'),
    (' ### Heading level 3', '<td><strong>Heading level 3</strong></td>'),
    (' #### Heading level 4', '<td><strong>Heading level 4</strong></td>'),
    (' ##### Heading level 5', '<td><strong>Heading level 5</strong></td>'),
    (' ###### Heading level 6', '<td><strong>Heading level 6</strong></td>'),
    ('   * Bullet point level 1', '<td>&nbsp;&nbsp;● Bullet point level 1</td>'),
    ('     * Bullet point level 2', '<td>&nbsp;&nbsp;&nbsp;&nbsp;⯀ Bullet point level 2</td>'),
    ('       * Bullet point level 3', '<td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;○ Bullet point level 3</td>'),
    (
        '         * Bullet point level 4',
        '<td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;○ Bullet point level 4</td>',
    ),
    (' *emphasis*', '<td><em>emphasis</em></td>'),
    (' _**emphasis and strong**_', '<td><em><strong>emphasis and strong</strong></em></td>'),
    (' **strong**', '<td><strong>strong</strong></td>'),
    (' **_strong and emphasis_**', '<td><strong><em>strong and emphasis</em></strong></td>'),
    (' ~~strikethrough~~', '<td><s>strikethrough</s></td>'),
    (' _emphasis_', '<td><em>emphasis</em></td>'),
    (' snake_case_name', '<td>snake_case_name</td>'),
    (' snake*case*name', '<td>snake*case*name</td>'),
]


def generate_random_string(length: int = 39) -> str:
    """Generates a random alphanumeric string of specified length."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))  # noqa: S311 not suitable for security/cryptogr.


@pytest.fixture
def job_state() -> Generator[JobState, None, None]:
    """Get a JobState object for testing."""
    ssdb_file = ':memory:'
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # ty:ignore[invalid-argument-type]
    job_state = JobState(ssdb_storage, ShellJob(command=''))
    job_state.old_timestamp = 1605147837.511478  # initial release of webchanges!
    job_state.new_timestamp = 1605147837.511478
    yield job_state
    ssdb_storage.close()


# def test_no_differ_name_raises_valueerror() -> None:
#     with pytest.raises(ValueError) as pytest_wrapped_e:
#         list(DifferBase.normalize_differ(''))
#     assert str(pytest_wrapped_e.value) == "Job None: Differ directive must have a 'name' sub-directive: {'name': ''}."


def test_invalid_differ_name_raises_valueerror() -> None:
    with pytest.raises(SettingError) as pytest_wrapped_e:
        list(DifferBase.normalize_differ({'name': 'adiffernamethatdoesnotexist'}))
    assert str(pytest_wrapped_e.value) == 'Job None: No differ named adiffernamethatdoesnotexist.'


def test_providing_subdirective_to_differ_without_differ_raises_valueerror() -> None:
    with pytest.raises(SettingError) as pytest_wrapped_e:
        list(DifferBase.normalize_differ({'name': 'deepdiff', 'asubdifferthatdoesnotexist': True}))
    err_msg = str(pytest_wrapped_e.value)
    assert err_msg == (
        'Job None: Differ deepdiff does not support sub-directive(s) asubdifferthatdoesnotexist (supported: compact, '
        'cutoff_distance_for_pairs, cutoff_intersection_for_pairs, data_type, ignore_order, ignore_string_case, '
        'significant_digits, threshold_to_diff_deeper).'
    )


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('bogus', "additions_only string value must be 'disable_safeguard'; got 'bogus'"),
        (2, 'additions_only numeric value must be in [0, 1]; got 2'),
        ([], "additions_only must be a boolean, a number in [0, 1], or 'disable_safeguard'; got list"),
    ],
)
def test_additions_only_wrong_value_is_a_setting_error(value: object, expected: str) -> None:
    """A wrong additions_only raises a SettingError, so that the report shows its message without a traceback."""
    with pytest.raises(SettingError) as pytest_wrapped_e:
        differs._resolve_additions_only(value)  # ty:ignore[invalid-argument-type]
    assert str(pytest_wrapped_e.value) == expected


def test_providing_unknown_subdirective_raises_valueerror() -> None:
    with pytest.raises(SettingError) as pytest_wrapped_e:
        list(DifferBase.normalize_differ({'name': 'image', 'data_type': 'json', 'anothersubdirective': '42'}))
    err_msg = str(pytest_wrapped_e.value)
    assert err_msg == (
        'Job None: Differ image does not support sub-directive(s) anothersubdirective (supported: ai_google, '
        'data_type, mse_threshold).'
    )


def test_process_no_valid_differ_returns_empty(job_state: JobState) -> None:
    diff = DifferBase(job_state).process(differ_kind='', directives={}, job_state=job_state)
    assert diff == {}


def test_make_timestamp() -> None:
    ts = DifferBase.make_timestamp(1605147837.511478, test_tz)
    assert ts == 'Thu, 12 Nov 2020 02:23:57 +0000 (UTC)'

    ts = DifferBase.make_timestamp(0)
    assert ts == 'NEW'


def test_html2text() -> None:
    text = DifferBase.html2text('<a href="https://example.com">link</a>')
    assert text == '[link](https://example.com)'


def test_raise_import_error(job_state: JobState) -> None:
    """The standard message for a missing package, suggesting to install the package itself when there's no extra."""
    with pytest.raises(ImportError) as pytest_wrapped_e:
        DifferBase(job_state).raise_import_error('test', 'error!')
    assert str(pytest_wrapped_e.value) == (
        "The '' differ (Job 0: ) requires the Python package 'test', which cannot be imported (error!). Install it "
        "with e.g. 'uv pip install --upgrade test'."
    )


def test_raise_import_error_with_extra(job_state: JobState) -> None:
    """With an extra, the message suggests installing webchanges with that extra."""
    with pytest.raises(ImportError) as pytest_wrapped_e:
        DifferBase(job_state).raise_import_error(
            'deepdiff', ImportError("No module named 'deepdiff'"), extra='deepdiff'
        )
    assert str(pytest_wrapped_e.value).endswith(
        "requires the Python package 'deepdiff', which cannot be imported (No module named 'deepdiff'). Install it "
        "with e.g. 'uv pip install --upgrade webchanges[deepdiff]'."
    )


def test_unified(job_state: JobState) -> None:
    """Base case."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    expected = ['@@ -1 +1 @@', '-a', '+b']
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines()[2:] == expected

    # redo as markdown
    diff = job_state.get_diff(report_kind='markdown')
    assert diff.splitlines()[2:] == expected

    # redo as html
    expected = [
        '<table style="border-collapse:collapse;">',
        '<tr><td style="font-family:monospace;color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</td></tr>',
        '<tr><td style="font-family:monospace;color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</td></tr>',
        '<tr><td style="font-family:monospace;background-color:#fbfbfb;">@@ -1 +1 @@</td></tr>',
        '<tr><td style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">a</td></tr>',
        '<tr><td style="background-color:#d1ffd1;color:#082b08;">b</td></tr>',
        '</table>',
    ]
    diff = job_state.get_diff(report_kind='html')
    assert diff.splitlines() == expected


def test_unified_no_changes(job_state: JobState) -> None:
    """Base case."""
    # set contextlines
    job_state.job.contextlines = 0
    job_state.new_data = job_state.old_data
    diff = job_state.get_diff()
    assert diff == ''


def test_unified_additions_only(job_state: JobState) -> None:
    """Changed line with "additions" comparison_filter."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.additions_only = True
    expected = ['/**Comparison type: Additions only**', '+b']
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines()[2:] == expected

    # redo as html, to use diff_text = _unfiltered_diff['text']
    expected = [
        '<table style="border-collapse:collapse;">',
        '<tr><td style="font-family:monospace;color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</td></tr>',
        '<tr><td style="font-family:monospace;color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</td></tr>',
        '<tr><td style="background-color:lightyellow;"><strong>Comparison type: Additions only</strong></td></tr>',
        '<tr><td style="background-color:#d1ffd1;color:#082b08;">b</td></tr>',
        '</table>',
    ]
    diff = job_state.get_diff(report_kind='html')
    assert diff.splitlines() == expected


def test_unified_additions_only_new_lines(job_state: JobState) -> None:
    """Change of new empty lines with "additions" comparison_filter."""
    job_state.old_data = 'a\nb'
    job_state.new_data = 'a\n\nb\n'
    job_state.job.additions_only = True
    job_state.verb = 'changed'
    diff = job_state.get_diff()
    assert not diff
    assert job_state.verb == 'changed,no_report'


def test_unified_deletions_only(job_state: JobState) -> None:
    """Changed line with "deletions" comparison_filter."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.additions_only = False
    job_state.job.deletions_only = True
    expected = ['/**Comparison type: Deletions only**', '@@ -1 +1 @@', '-a']
    diff = job_state.get_diff()
    assert diff.splitlines()[2:] == expected


def test_unified_deletions_only_only_removed_lines(job_state: JobState) -> None:
    """Changed line with "deletions" comparison_filter."""
    job_state.old_data = 'a\n\nb\n'
    job_state.new_data = 'a\nb'
    job_state.job.additions_only = False
    job_state.job.deletions_only = True
    job_state.verb = 'changed'
    diff = job_state.get_diff()
    assert not diff
    assert job_state.verb == 'changed,no_report'


def test_unified_additions_only_75pct_deleted(job_state: JobState) -> None:
    """'additions' comparison_filter with 75% or more of original content deleted."""
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = 'd\n'
    job_state.job.additions_only = True
    job_state.job.deletions_only = False
    expected = [
        '/**Comparison type: Additions only**',
        '/**Deletions are being shown as only 25% of the original content remains**',
        '@@ -1,3 +0,0 @@',
        '-a',
        '-b',
        '-c',
    ]
    diff = job_state.get_diff()
    assert diff.splitlines()[2:] == expected


def test_unified_additions_only_deletions(job_state: JobState) -> None:
    """'additions' comparison_filter and lines were only deleted."""
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = 'a\nb\nc\n'
    job_state.job.additions_only = True
    job_state.job.deletions_only = False
    diff = job_state.get_diff()
    assert not diff
    assert job_state.verb == 'changed,no_report'


def test_unified_deletions_only_additions(job_state: JobState) -> None:
    """'deletions' comparison_filter and lines were only added."""
    try:
        job_state.old_data = 'a\n'
        job_state.new_data = 'a\nb\n'
        job_state.job.additions_only = False
        job_state.job.deletions_only = True
        diff = job_state.get_diff()
        assert not diff
        assert job_state.verb == 'changed,no_report'

    finally:
        job_state.job.deletions_only = False


def test_unified_additions_only_custom_remaining_triggers_warning(job_state: JobState) -> None:
    """additions_only=0.5 with 50% remaining shows the deletion warning at 50%."""
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = 'a\nb\n'
    job_state.job.additions_only = 0.5
    job_state.job.deletions_only = False
    diff = job_state.get_diff()
    assert '/**Comparison type: Additions only**' in diff
    assert 'only 50% of the original content remains' in diff


def test_unified_additions_only_custom_remaining_above_threshold(job_state: JobState) -> None:
    """additions_only=0.5 with 75% remaining does NOT show deletions."""
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = 'a\nb\nc\n'
    job_state.job.additions_only = 0.5
    job_state.job.deletions_only = False
    job_state.verb = 'changed'
    diff = job_state.get_diff()
    assert 'remains' not in diff
    assert job_state.verb == 'changed,no_report'


def test_unified_additions_only_remaining_zero_only_warns_on_full_wipe(job_state: JobState) -> None:
    """additions_only=0 warns only when the source is completely wiped."""
    # Partial deletion: should NOT warn.
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = 'a\n'
    job_state.job.additions_only = 0
    job_state.job.deletions_only = False
    job_state.verb = 'changed'
    diff = job_state.get_diff()
    assert 'remains' not in diff
    assert job_state.verb == 'changed,no_report'

    # Full wipe: SHOULD warn. Invalidate the memoized diff before re-running.
    job_state.generated_diff = {}
    job_state.unfiltered_diff = {}
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = ''
    job_state.job.additions_only = 0
    diff = job_state.get_diff()
    assert 'only 0% of the original content remains' in diff


def test_unified_additions_only_disable_safeguard(job_state: JobState) -> None:
    """additions_only='disable_safeguard' suppresses the warning even on full wipe."""
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = ''
    job_state.job.additions_only = 'disable_safeguard'
    job_state.job.deletions_only = False
    job_state.verb = 'changed'
    diff = job_state.get_diff()
    assert 'remains' not in diff
    assert job_state.verb == 'changed,no_report'
    assert diff == ''


def test_resolve_additions_only_helper() -> None:
    """Direct unit test of the additions_only resolver helper."""
    from webchanges.differs import _resolve_additions_only

    assert _resolve_additions_only(True) == (True, 0.25)
    assert _resolve_additions_only(False) == (False, None)
    assert _resolve_additions_only(None) == (False, None)
    assert _resolve_additions_only(0) == (True, 0.0)
    assert _resolve_additions_only(0.5) == (True, 0.5)
    assert _resolve_additions_only(1) == (True, 1.0)
    assert _resolve_additions_only('disable_safeguard') == (True, None)
    with pytest.raises(ValueError, match='disable_safeguard'):
        _resolve_additions_only('nope')
    with pytest.raises(ValueError, match=r'\[0, 1\]'):
        _resolve_additions_only(1.5)
    with pytest.raises(ValueError, match=r'\[0, 1\]'):
        _resolve_additions_only(-0.1)


@pytest.mark.parametrize(('inpt', 'out'), DIFF_TO_HTML_TEST_DATA)
def test_unified_diff_to_html(inpt: str, out: str, job_state: JobState) -> None:
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n' + inpt
    job = JobBase.unserialize({'url': 'https://www.example.com', 'is_markdown': True, 'markdown_padded_tables': False})
    job_state.job = job
    result = ''.join(list(UnifiedDiffer(job_state).unified_diff_to_html(inpt)))
    assert result[197:-13] == out


def test_unified_diff_to_html_padded_table(job_state: JobState) -> None:
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n | table | row |'
    job = JobBase.unserialize(
        {
            'url': 'https://www.example.com',
            'is_markdown': True,
            'markdown_padded_tables': True,
            'markdown_tables': False,  # the table row is a line as any other
        }
    )
    job_state.job = job
    result = ''.join(list(UnifiedDiffer(job_state).unified_diff_to_html(inpt)))
    assert result[193:-8] == (
        '<tr><td><span style="font-family:monospace;white-space:pre-wrap">| table | row |</span></td></tr>'
    )


def test_unified_diff_to_html_markdown_table(job_state: JobState) -> None:
    """Markdown table rows are rendered as a nested HTML table, each row styled as its diff line."""
    inpt = '-fake head 1\n+fake head 2\n | Model | Price |\n |---|---|\n-| A | $1 |\n+| A | $3 |\n text'
    job_state.job = JobBase.unserialize({'url': 'https://www.example.com', 'is_markdown': True})
    result = ''.join(UnifiedDiffer(job_state).unified_diff_to_html(inpt))
    cell = 'border:1px solid #999;padding:2px 6px;vertical-align:top;'
    deleted = f'{cell}{UnifiedDiffer.css_deltd_style}'
    added = f'{cell}{UnifiedDiffer.css_added_style}'
    assert (
        '<tr><td><table style="border-collapse:collapse;">'
        f'<tr><th style="{cell}">Model</th><th style="{cell}">Price</th></tr>'
        f'<tr><td style="{deleted}">A</td><td style="{deleted}">$1</td></tr>'
        f'<tr><td style="{added}">A</td><td style="{added}">$3</td></tr>'
        '</table></td></tr><tr><td>text</td></tr></table>'
    ) in result


def test_unified_diff_to_html_markdown_extras(job_state: JobState) -> None:
    """The markdown_extras job directive overrides the default markdown2 extras (here, reinstating middle-word-em)."""
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n snake_case_name'
    job = JobBase.unserialize(
        {'url': 'https://www.example.com', 'is_markdown': True, 'markdown_extras': {'middle-word-em': True}}
    )
    job_state.job = job
    result = ''.join(list(UnifiedDiffer(job_state).unified_diff_to_html(inpt)))
    assert result[193:-8] == '<tr><td>snake<em>case</em>name</td></tr>'


def test_unified_diff_to_html_link(job_state: JobState) -> None:
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n [link](/test.htm)'
    job = JobBase.unserialize({'url': 'https://www.example.com', 'is_markdown': True})
    job_state.job = job
    result = ''.join(list(UnifiedDiffer(job_state).unified_diff_to_html(inpt)))
    assert result[193:-8] == (
        '<tr><td><a style="font-family:inherit" rel="noopener" target="_blank" href="/test.htm">link</a></td></tr>'
    )


def test_unified_diff_to_html_no_link_text(job_state: JobState) -> None:
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n [](/test.htm)'
    job = JobBase.unserialize({'url': 'https://www.example.com', 'is_markdown': True})
    job_state.job = job
    result = ''.join(list(UnifiedDiffer(job_state).unified_diff_to_html(inpt)))
    assert result[193:-8] == (
        '<tr><td><a style="font-family:inherit" rel="noopener" target="_blank" href="/test.htm">'
        '[<em>Link with no text</em>]</a></td></tr>'
    )


def test_unified_diff_to_html_url_no_link(job_state: JobState) -> None:
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n [](https://test.htm)'
    job = JobBase.unserialize({'url': 'https://www.example.com', 'is_markdown': True, 'differ': {'name': 'unified'}})
    job_state.job = job
    result = ''.join(list(UnifiedDiffer(job_state).unified_diff_to_html(inpt)))
    assert result[193:-8] == (
        '<tr><td><a style="font-family:inherit" rel="noopener" target="_blank" href="https://test.htm">'
        '[<em>Link with no text</em>]</a></td></tr>'
    )


def test_table_diff_normal(job_state: JobState) -> None:
    """Base case."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.differ = {'name': 'table'}
    expected = [
        '',
        '    <table class="diff" id="difflib_chg_to0__top"',
        '           cellspacing="0" cellpadding="0" rules="groups" >',
        '        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>',
        '        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>',
        (
            '        <thead><tr><th style="font-family:monospace" class="diff_next"><br '
            '/></th><th style="font-family:monospace" colspan="2" '
            'class="diff_header">Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</th><th '
            'style="font-family:monospace" class="diff_next"><br /></th><th '
            'style="font-family:monospace" colspan="2" class="diff_header">Thu, 12 Nov '
            '2020 02:23:57 +0000 (UTC)</th></tr></thead>'
        ),
        '        <tbody>',
        (
            '            <tr><td style="font-family:monospace" class="diff_next" '
            'id="difflib_chg_to0__0"><a style="font-family:monospace;color:inherit" '
            'href="#difflib_chg_to0__top">t</a></td><td style="font-family:monospace" '
            'class="diff_header" id="from0_1">1</td><td '
            'style="font-family:monospace"><span '
            'style="color:red;background-color:lightred">a</span></td><td '
            'style="font-family:monospace" class="diff_next"><a '
            'style="font-family:monospace;color:inherit" '
            'href="#difflib_chg_to0__top">t</a></td><td style="font-family:monospace" '
            'class="diff_header" id="to0_1">1</td><td style="font-family:monospace"><span '
            'style="color:green;background-color:lightgreen">b</span></td></tr>'
        ),
        '        </tbody>',
        '    </table>',
    ]
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    assert diff.splitlines() == expected

    # redo for text
    expected = [
        '',
        '| Thu, 12 Nov 2020 02:23:57 +0000 (UTC)|',
        '| Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '---|---|---|---',
        't| 1| a| t| 1| b',
    ]
    diff = job_state.get_diff(report_kind='plain')
    assert diff.splitlines() == expected


def test_command_no_change(job_state: JobState) -> None:
    """Test command differ.

    Diff tools return 0 for "nothing changed" or 1 for "files differ", anything else is an error.
    """
    job_state.old_data = 'a\n'
    job_state.new_data = 'a\n'
    if sys.platform != 'win32':
        job_state.job.differ = {'name': 'command', 'command': 'echo'}  # test with differ name
    job_state.job.is_markdown = True
    diff = job_state.get_diff(tz=test_tz)
    assert not diff
    assert job_state.verb == 'changed,no_report'

    # redo as markdown
    diff = job_state.get_diff(report_kind='markdown')
    assert not diff
    assert job_state.verb == 'changed,no_report'

    # redo as html
    diff = job_state.get_diff(report_kind='html')
    assert not diff
    assert job_state.verb == 'changed,no_report'


def test_command_change(job_state: JobState) -> None:
    """Test command differ.

    Diff tools return 0 for "nothing changed" or 1 for "files differ", anything else is an error.
    """
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    if sys.platform == 'win32':
        command = 'cmd /C exit 1 & rem'
    else:
        command = 'bash -c " echo \'This is a custom diff\'; exit 1" #'
    job_state.job.differ = {'command': command}  # test with no differ name
    expected = [
        '\x1b[91m--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)\x1b[0m',
        '\x1b[92m+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)\x1b[0m',
    ]
    job_state.job.is_markdown = True
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines()[:2] == expected

    # redo as markdown
    diff = job_state.get_diff(report_kind='markdown')
    assert diff.splitlines()[:2] == expected

    # redo as html
    expected = [
        '<span style="font-family:monospace;"><br>',
        '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span><br>',
        '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span><br>',
    ]
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    assert diff.splitlines()[:3] == expected


def test_command_error(job_state: JobState) -> None:
    """Test command differ.

    Diff tools return 0 for "nothing changed" or 1 for "files differ", anything else is an error.
    """
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    if sys.platform == 'win32':
        command = 'cmd /C exit 2 & rem'
    else:
        command = 'bash -c " echo \'This is a custom diff\'; exit 2" #'
    job_state.job.differ = {'command': command}  # test with no differ name
    job_state.get_diff()
    assert isinstance(job_state.exception, RuntimeError)
    if sys.platform != 'win32':
        command = command.replace("'", "\\'")
    assert str(job_state.exception) == (f"Job 0: External differ '{{'command': '{command}'}}' returned '' ()")


def test_command_bad_command(job_state: JobState) -> None:
    """Test command differ with bad command."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.differ = {'name': 'command', 'command': 'dfgfdgsdfg'}
    job_state.get_diff()
    assert isinstance(job_state.exception, FileNotFoundError)
    if sys.platform == 'win32':
        assert str(job_state.exception) == '[WinError 2] The system cannot find the file specified'


def test_command_command_error(job_state: JobState) -> None:
    """Test command differ with command returning an error."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.differ = {'name': 'command', 'command': 'dir /x'}
    job_state.get_diff()
    assert isinstance(job_state.exception, (RuntimeError, FileNotFoundError))
    if sys.platform == 'win32':
        assert str(job_state.exception) in (
            '[WinError 2] The system cannot find the file specified',
            (
                "Job 0: External differ '{'command': 'dir /x'}' returned 'dir: cannot access "
                "'/x': No such file or directory' ()"
            ),
        )


def test_command_wdiff_to_html(job_state: JobState) -> None:
    """Test wdiff colorizer."""
    diff = '## This is [-not-] what I [-want.-] {+want!+}'
    expected = (
        '## This is <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">not</span> '
        'what I <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">want.</span> '
        '<span style="background-color:#d1ffd1;color:#082b08;">want!</span>'
    )
    htm = CommandDiffer(job_state).wdiff_to_html(diff)
    assert htm == expected


def test_command_wdiff_to_html_markdown(job_state: JobState) -> None:
    """Test wdiff colorizer with monospace markdown text."""
    diff = '## This is [-not-] what I [-want\nfor you-] {+want\n for me+}'
    job_state.job.set_to_monospace()
    job_state.job.is_markdown = True
    expected = [
        (
            '<span style="font-family:monospace;white-space:pre-wrap">## This is '
            '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">not</span> '
            'what I <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">want</span><br>'
        ),
        (
            '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">for you</span> '
            '<span style="background-color:#d1ffd1;color:#082b08;">want</span><br>'
        ),
        '<span style="background-color:#d1ffd1;color:#082b08;"> for me</span></span>',
    ]
    htm = CommandDiffer(job_state).wdiff_to_html(diff)
    assert htm.splitlines() == expected


def test_deepdiff_json(job_state: JobState) -> None:
    """Test deepdiff json differ."""
    job_state.old_data = '{"test": 1}'
    job_state.new_data = '{"test": 2}'
    job_state.job.differ = {'name': 'deepdiff', 'data_type': 'json'}
    expected = [
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '• Value of root[\'test\'] changed from "1" to "2".',
    ]
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines() == expected

    # retest as html
    expected = [
        (
            '<span style="font-family:monospace;white-space:pre-wrap;">'
            '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>'
        ),
        '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
        (
            "• Value of root['test'] changed from <span "
            'style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">"1"</span> '
            'to <span style="background-color:#d1ffd1;color:#082b08;">"2"</span>.</span>'
        ),
    ]
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    assert diff.splitlines() == expected


def test_deepdiff_json_list(job_state: JobState) -> None:
    """Test deepdiff json differ when the new data is a list."""
    job_state.old_data = ''
    job_state.new_data = '[{"test": 2, "second_test": 3}, "morestuff", 323]'
    job_state.job.differ = {'name': 'deepdiff', 'data_type': 'json'}
    expected = [
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '• Type of root changed from str to list and value changed from "" to [',
        '  {',
        '    "test": 2,',
        '    "second_test": 3',
        '  },',
        '  "morestuff",',
        '  323',
        '].',
    ]
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines() == expected

    # retest as html
    expected = [
        (
            '<span style="font-family:monospace;white-space:pre-wrap;">'
            '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>'
        ),
        '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
        (
            '• Type of root changed from str to list and value changed from <span '
            'style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">""</span> '
            'to <span style="background-color:#d1ffd1;color:#082b08;">['
        ),
        '  {',
        '    "test": 2,',
        '    "second_test": 3',
        '  },',
        '  "morestuff",',
        '  323',
        ']</span>.</span>',
    ]
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    assert diff.splitlines() == expected

    # retest as compact
    job_state.unfiltered_diff = {}
    job_state.generated_diff = {}
    job_state.job.differ.update({'compact': True})
    expected = [
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        "• ⊤: '' → ",  # noqa: RUF001
        '    - test: 2',
        '      second_test: 3',
        '    - morestuff',
        '    - 323',
    ]
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines() == expected

    # retest as compact html
    expected = [
        (
            '<span style="font-family:monospace;white-space:pre-wrap;">'
            '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>'
        ),
        '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
        (
            '• ⊤: <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">\'\''  # noqa: RUF001
            '</span> ⮕ <span style="background-color:#d1ffd1;color:#082b08;">'
        ),
        '    - test: 2',
        '      second_test: 3',
        '    - morestuff',
        '    - 323</span></span>',
    ]
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    assert diff.splitlines() == expected


def test_deepdiff_json_ignore_order_compares_changed_items_in_depth(job_state: JobState) -> None:
    """With ignore_order, the changed items in a list are compared in depth.

    Only the nested values that changed are reported, not each item's entire before-and-after contents (webchanges'
    cutoff defaults; the deepdiff library's own defaults report the items in their entirety, as tested in
    test_deepdiff_json_ignore_order_cutoff_directives).
    """
    job_state.old_data = '[{"id": "A", "status": "open"}, {"id": "B", "status": "open"}]'
    job_state.new_data = '[{"id": "A", "status": "flown"}, {"id": "B", "status": "flown"}]'
    job_state.job.differ = {'name': 'deepdiff', 'data_type': 'json', 'ignore_order': True}
    expected = [
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '• Value of root[0][\'status\'] changed from "open" to "flown".',
        '• Value of root[1][\'status\'] changed from "open" to "flown".',
    ]
    diff = job_state.get_diff(tz=test_tz)
    assert sorted(diff.splitlines()) == sorted(expected)


def test_deepdiff_json_ignore_order_cutoff_directives(job_state: JobState) -> None:
    """The cutoff_* and threshold_to_diff_deeper sub-directives are passed through to DeepDiff.

    At the deepdiff library's own defaults, the changed items of two iterables with no item in common are not paired and
    are therefore reported in their entirety instead of in depth.
    """
    job_state.old_data = '[{"id": "A", "status": "open"}, {"id": "B", "status": "open"}]'
    job_state.new_data = '[{"id": "A", "status": "flown"}, {"id": "B", "status": "flown"}]'
    job_state.job.differ = {
        'name': 'deepdiff',
        'data_type': 'json',
        'ignore_order': True,
        'cutoff_distance_for_pairs': 0.3,
        'cutoff_intersection_for_pairs': 0.7,
        'threshold_to_diff_deeper': 0.33,
    }
    expected = [
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '• Value of root[0] changed from {',
        '  "id": "A",',
        '  "status": "open"',
        '} to {',
        '  "id": "A",',
        '  "status": "flown"',
        '}.',
        '• Value of root[1] changed from {',
        '  "id": "B",',
        '  "status": "open"',
        '} to {',
        '  "id": "B",',
        '  "status": "flown"',
        '}.',
    ]
    diff = job_state.get_diff(tz=test_tz)
    assert sorted(diff.splitlines()) == sorted(expected)


def test_deepdiff_json_no_change(job_state: JobState) -> None:
    """Test deepdiff json differ with bad data."""
    job_state.old_data = '{"test": 1}'
    job_state.old_mime_type = 'application/json'
    job_state.new_data = '{"test": 1}'
    job_state.new_mime_type = 'application/json'
    job_state.job.differ = {'name': 'deepdiff'}
    diff = job_state.get_diff()
    assert diff == ''


def test_deepdiff_json_bad_data(job_state: JobState) -> None:
    """Test deepdiff json differ with bad data."""
    job_state.old_data = '{"test": 1'
    job_state.new_data = '{"test": 2'
    job_state.job.differ = {'name': 'deepdiff', 'data_type': 'json'}
    expected = [
        'Differ deepdiff ERROR: Old data is invalid JSON',
        "Expecting ',' delimiter: line 1 column 11 (char 10)",
    ]
    diff = job_state.get_diff()
    assert diff.splitlines() == expected


def test_deepdiff_xml(job_state: JobState) -> None:
    """Test deepdiff xml differ."""
    job_state.old_data = '<test>1</test>'
    job_state.new_data = '<test>2</test>'
    job_state.job.differ = {'name': 'deepdiff', 'data_type': 'xml'}
    expected = [
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '• Value of root[\'test\'] changed from "1" to "2".',
    ]
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines() == expected


def test_deepdiff_xml_and_yaml(job_state: JobState) -> None:
    """Test deepdiff differ with xml and yaml."""
    job_state.old_data = '<test>1</test>'
    job_state.old_mime_type = 'application/xml'
    job_state.new_data = 'test: 2'
    job_state.new_mime_type = 'application/yaml'
    job_state.job.differ = {'name': 'deepdiff'}
    expected = [
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '• Type of root[\'test\'] changed from str to int and value changed from "1" to "2".',
    ]
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines() == expected


def test_deepdiff_yaml_and_json(job_state: JobState) -> None:
    """Test deepdiff json differ with bad data."""
    job_state.old_data = 'test: 1'
    job_state.old_mime_type = 'application/yaml'
    job_state.new_data = '{"test": 1}'
    job_state.new_mime_type = 'application/json'
    job_state.job.differ = {'name': 'deepdiff'}
    diff = job_state.get_diff()
    assert diff == ''


# @py_nt_only
@py_latest_only
@ignore_image_beta_warning
def test_image_url(job_state: JobState) -> None:
    """Test image differ with urls."""
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display logging
    #     logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
    job_state.old_data = 'https://aviationweather.gov/data/products/progs/F006_wpc_prog.gif'
    job_state.new_data = 'https://aviationweather.gov/data/products/progs/F012_wpc_prog.gif'
    job_state.job.differ = {'name': 'image', 'data_type': 'url', 'mse_threshold': 5}
    expected = '<br>\n'.join(
        [
            (
                '<span style="font-family:monospace">'
                '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC) '
                f'(<a href="{job_state.old_data}" target="_blank">Old image</a>)</span>'
            ),
            (
                '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC) '
                f'(<a href="{job_state.new_data}" target="_blank">New image</a>)</span>'
            ),
            '</span>',
            'New image:',
            f'<img src="{job_state.new_data}" style="max-width: 100%; display: block;">',
            'Differences from old (in yellow):',
            '<img src="data:image/gif;base64,',
        ]
    )
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display the result
    #     import tempfile
    #     import time
    #     import webbrowser
    #
    #     f = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
    #     f.write(f'<span style="font-family: Roboto, Arial, Helvetica, sans-serif; font-size: 13px;">{diff}</span>')
    #     f.close()
    #     webbrowser.open(f.name)
    #     time.sleep(1)
    #     os.remove(f.name)
    assert diff[: len(expected)] == expected


@py_latest_only
@ignore_image_beta_warning
def test_image_filenames(job_state: JobState) -> None:
    """Test image differ with filenames."""
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display logging
    #     logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
    current_dir = Path(__file__).parent
    old_file = current_dir.joinpath('data', 'pic_1.png')
    new_file = current_dir.joinpath('data', 'pic_2.png')
    job_state.old_data = str(old_file)
    job_state.new_data = str(new_file)
    job_state.job.differ = {'name': 'image', 'data_type': 'filename'}
    expected = '<br>\n'.join(
        [
            (
                '<span style="font-family:monospace">'
                '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC) '
                f'(<a href="file://{job_state.old_data}" target="_blank">Old image</a>)</span>'
            ),
            (
                '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC) '
                f'(<a href="file://{job_state.new_data}" target="_blank">New image</a>)</span>'
            ),
            '</span>',
            'New image:',
            '<img src="data:image/png;base64,',
        ]
    )
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display the result
    #     import os
    #     import tempfile
    #     import time
    #     import webbrowser
    #
    #     f = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
    #     f.write(diff)
    #     f.close()
    #     webbrowser.open(f.name)
    #     time.sleep(1)
    #     os.remove(f.name)
    assert diff[: len(expected)] == expected
    # from src.webchanges.mailer import Mailer
    #
    # email = Mailer().msg('', '', '', '', diff)


@py_latest_only
@ignore_image_beta_warning
def test_image_ascii85(job_state: JobState) -> None:
    """Test image differ with ascii85 encoded images."""
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display logging
    #     logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
    current_dir = Path(__file__).parent
    old_file = current_dir.joinpath('data', 'pic_1.png')
    new_file = current_dir.joinpath('data', 'pic_2.png')
    job_state.old_data = base64.a85encode(old_file.read_bytes()).decode()
    job_state.new_data = base64.a85encode(new_file.read_bytes()).decode()
    job_state.job.differ = {'name': 'image', 'data_type': 'ascii85'}
    expected = '<br>\n'.join(  # noqa: FLY002 one line per item reads better than one long literal
        [
            (
                '<span style="font-family:monospace">'
                '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>'
            ),
            '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
            '</span>',
            'New image:',
            '<img src="data:image/png;base64,',
        ]
    )
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display the result
    #     import tempfile
    #     import time
    #     import webbrowser
    #
    #     f = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
    #     f.write(f'<span style="font-family: Roboto, Arial, Helvetica, sans-serif; font-size: 13px;">{diff}</span>')
    #     f.close()
    #     webbrowser.open(f.name)
    #     time.sleep(1)
    #     os.remove(f.name)
    assert diff[: len(expected)] == expected


@py_latest_only
@ignore_image_beta_warning
def test_image_base64_and_resize(job_state: JobState) -> None:
    """Test image differ with base64 encoded images."""
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display logging
    #     logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
    from PIL import Image

    current_dir = Path(__file__).parent
    old_file = current_dir.joinpath('data', 'pic_1.png')
    new_file = current_dir.joinpath('data', 'pic_2.png')
    job_state.old_data = base64.b64encode(old_file.read_bytes()).decode()
    # blow up the second image to trigger resizing
    new_img = Image.open(new_file)
    img_format = new_img.format
    new_img = new_img.resize((new_img.width * 2, new_img.height * 2), Image.Resampling.NEAREST)
    output_stream = BytesIO()
    new_img.save(output_stream, format=img_format)
    job_state.new_data = base64.b64encode(output_stream.getvalue()).decode()
    job_state.job.differ = {'name': 'image', 'data_type': 'base64'}
    expected = '<br>\n'.join(  # noqa: FLY002 one line per item reads better than one long literal
        [
            (
                '<span style="font-family:monospace">'
                '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>'
            ),
            '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
            '</span>',
            'New image:',
            '<img src="data:image/png;base64,',
        ]
    )
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display the result
    #     import tempfile
    #     import time
    #     import webbrowser
    #
    #     f = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
    #     f.write(f'<span style="font-family: Roboto, Arial, Helvetica, sans-serif; font-size: 13px;">{diff}</span>')
    #     f.close()
    #     webbrowser.open(f.name)
    #     time.sleep(1)
    #     os.remove(f.name)
    assert diff[: len(expected)] == expected


@py_latest_only
@ignore_image_beta_warning
def test_image_resize(job_state: JobState) -> None:
    """Test identical image but old is bigger."""
    # if not os.getenv('GITHUB_ACTIONS'):
    #     # we are doing interactive debugging and want to display logging
    #     logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
    from PIL import Image

    current_dir = Path(__file__).parent
    img_file = current_dir.joinpath('data', 'pic_1.png')
    # blow up the old image to trigger resizing
    old_img = Image.open(img_file)
    img_format = old_img.format
    old_img = old_img.resize((old_img.width + 1, old_img.height), Image.Resampling.NEAREST)
    output_stream = BytesIO()
    old_img.save(output_stream, format=img_format)
    job_state.old_data = base64.b64encode(output_stream.getvalue()).decode()
    job_state.new_data = base64.b64encode(img_file.read_bytes()).decode()
    job_state.job.differ = {'name': 'image', 'data_type': 'base64'}
    diff = job_state.get_diff(report_kind='html')
    # if not os.getenv('GITHUB_ACTIONS') and diff:
    #     # we are doing interactive debugging and want to display the result
    #     import tempfile
    #     import time
    #     import webbrowser
    #
    #     f = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
    #     f.write(f'<span style="font-family: Roboto, Arial, Helvetica, sans-serif; font-size: 13px;">{diff}</span>')
    #     f.close()
    #     webbrowser.open(f.name)
    #     time.sleep(1)
    #     os.remove(f.name)
    assert not diff
    assert job_state.verb == 'changed,no_report'


@py_latest_only
@ignore_image_beta_warning
def test_image_identical(job_state: JobState) -> None:
    current_dir = Path(__file__).parent
    img_file = current_dir.joinpath('data', 'pic_1.png')
    job_state.old_data = str(img_file)
    job_state.new_data = str(img_file)
    job_state.job.differ = {'name': 'image', 'data_type': 'filename'}
    diff = job_state.get_diff(report_kind='html')
    assert not diff
    assert job_state.verb == 'unchanged'


def test_ai_google_unchanged(job_state: JobState) -> None:
    """Test ai_google but with unchanged data as not to trigger API charges."""
    existing_key = os.environ.get('GEMINI_API_KEY')
    try:
        os.environ['GEMINI_API_KEY'] = generate_random_string(39)
        job_state.new_data = job_state.old_data
        job_state.job.differ = {'name': 'ai_google', 'model': 'gemini-pro', 'timeout': 1e-9}
        diff = job_state.get_diff()
        assert diff == ''
    finally:
        if existing_key:
            os.environ['GEMINI_API_KEY'] = existing_key


def test_ai_google_no_key(job_state: JobState) -> None:
    """Test ai_google with no key."""
    existing_key = os.environ.get('GEMINI_API_KEY')
    try:
        os.environ['GEMINI_API_KEY'] = ''
        job_state.job.differ = {'name': 'ai_google'}
        diff = job_state.get_diff()
        expected = (
            '## ERROR in summarizing changes using Google AI:\n'
            'Environment variable GEMINI_API_KEY not found or is of the incorrect length 0.\n'
            '\n'
            '\n'
        )
        assert diff[: len(expected)] == expected
    finally:
        if existing_key:
            os.environ['GEMINI_API_KEY'] = existing_key


@pytest.fixture
def ai_google_no_key_state(job_state: JobState, monkeypatch: pytest.MonkeyPatch) -> JobState:
    """Get a JobState with changed data for ai_google, whose missing API key keeps the model from being called."""
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GOOGLE_AI_API_KEY', raising=False)
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    return job_state


def test_ai_google_diff_dict(ai_google_no_key_state: JobState) -> None:
    """Test ai_google with the diff following the summary set by a differ name and its sub-directives."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'diff': {'name': 'wdiff', 'color': False}}
    assert '\n[-a-] {+b+}\n' in job_state.get_diff(tz=test_tz)
    assert '<span style="background-color:#d1ffd1;color:#082b08;">b</span>' in job_state.get_diff('html', tz=test_tz)


def test_ai_google_diff_name(ai_google_no_key_state: JobState) -> None:
    """Test ai_google with the diff following the summary set by a differ name only."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'diff': 'table'}
    assert '<table' in job_state.get_diff('html', tz=test_tz)
    assert '@@ -1 +1 @@' not in job_state.get_diff(tz=test_tz)


def test_ai_google_diff_default_unified(ai_google_no_key_state: JobState) -> None:
    """Test ai_google with the default unified diff following the summary, in every report kind."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google'}
    assert job_state.get_diff(tz=test_tz).endswith('\n@@ -1 +1 @@\n-a\n+b')  # no footer without model or directives
    assert job_state.get_diff('markdown', tz=test_tz).endswith('\n@@ -1 +1 @@\n-a\n+b')
    assert '<table' in job_state.get_diff('html', tz=test_tz)


def test_ai_google_unified_deprecated(ai_google_no_key_state: JobState) -> None:
    """Test that ai_google's sub-directive 'unified' still works, with a deprecation warning."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'unified': {'range_info': False}}
    with pytest.warns(DeprecationWarning, match="sub-directive 'unified' is deprecated"):
        diff = job_state.get_diff(tz=test_tz)
    assert '\n-a\n+b\n' in diff
    assert '@@' not in diff


def test_ai_google_unified_deprecated_diff_wins(ai_google_no_key_state: JobState) -> None:
    """Test that ai_google's sub-directive 'diff' takes precedence over the deprecated 'unified'."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'unified': {}, 'diff': {'name': 'wdiff', 'color': False}}
    with pytest.warns(DeprecationWarning):
        assert '\n[-a-] {+b+}\n' in job_state.get_diff(tz=test_tz)


@pytest.mark.parametrize(
    ('diff', 'message'),
    [
        ('image', "Differ 'ai_google' sub-directive 'diff' cannot be 'image'"),
        ('ai_google', "Differ 'ai_google' sub-directive 'diff' cannot be 'ai_google'"),
        ('nodiffer', 'No differ named nodiffer.'),
        ({'name': 'wdiff', 'nodirective': True}, 'Differ wdiff does not support sub-directive(s) nodirective'),
    ],
)
def test_ai_google_diff_invalid(ai_google_no_key_state: JobState, diff: str | dict[str, Any], message: str) -> None:
    """Test ai_google with a diff following the summary that cannot be generated: a settings error, like any other."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'diff': diff}
    with pytest.raises(SettingError, match=re.escape(message)):
        job_state.get_diff(tz=test_tz)


def test_ai_google_diff_invalid_not_normalized(ai_google_no_key_state: JobState) -> None:
    """Test that ai_google rejects a diff following the summary that cannot be generated even if called directly."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'diff': 'image'}
    diff = DifferBase.process('ai_google', {'diff': 'image'}, job_state, 'plain', test_tz)
    assert "Differ 'ai_google' sub-directive 'diff' cannot be 'image'" in diff['plain']
    assert isinstance(job_state.exception, SettingError)


def test_ai_google_diff_differ_defaults(ai_google_no_key_state: JobState) -> None:
    """Test that the configuration's differ_defaults apply to the differ following the summary."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'diff': 'wdiff'}
    diff = job_state.get_diff(tz=test_tz, differ_defaults={'wdiff': {'color': False}})
    assert '\n[-a-] {+b+}\n' in diff
    assert "diff={'name': 'wdiff', 'color': False}" in diff  # listed in the footer


def test_ai_google_diff_differ_defaults_job_wins(ai_google_no_key_state: JobState) -> None:
    """Test that the sub-directives of the differ following the summary take precedence over differ_defaults."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'diff': {'name': 'wdiff', 'color': True}}
    diff = job_state.get_diff(tz=test_tz, differ_defaults={'wdiff': {'color': False}})
    assert '[-a-]' not in diff
    assert '\033[91ma\033[0m' in diff


def test_ai_google_diff_differ_defaults_default_unified(ai_google_no_key_state: JobState) -> None:
    """Test that differ_defaults for unified apply to the default diff following the summary."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google'}
    diff = job_state.get_diff(tz=test_tz, differ_defaults={'unified': {'range_info': False}})
    assert '\n-a\n+b\n------------\n' in diff
    assert '@@' not in diff


def test_ai_google_no_diff_not_in_footer(ai_google_no_key_state: JobState) -> None:
    """Test that the default diff following the summary is not listed in the footer."""
    job_state = ai_google_no_key_state
    job_state.job.differ = {'name': 'ai_google', 'timeout': 1}
    diff = job_state.get_diff(tz=test_tz, differ_defaults={'unified': {}})
    assert diff.endswith('(differ directive(s): timeout=1).')


@py_no_github
def test_ai_google_bad_api_key(job_state: JobState) -> None:
    """Test ai_google but with unchanged data as not to trigger API charges."""
    existing_key = os.environ.get('GEMINI_API_KEY')
    try:
        os.environ['GEMINI_API_KEY'] = generate_random_string(39)
        job_state.old_data = 'a\n'
        job_state.new_data = 'b\n'
        job_state.job.differ = {'name': 'ai_google'}
        subdiffers = job_state.job.differ.copy()
        subdiffers.pop('name')
        expected = [
            '## ERROR in summarizing changes using Google AI:',
            'Received error from generativelanguage.googleapis.com: API key not valid. Please pass a valid API key.',
            '',
            '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
            '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
            '@@ -1 +1 @@',
            '-a',
            '+b',
            '------------',
        ]
        diff = job_state.get_diff(tz=test_tz)
        assert diff.splitlines()[:9] == expected
    finally:
        if existing_key:
            os.environ['GEMINI_API_KEY'] = existing_key


@py_no_github
def test_ai_google_timeout_and_unified_diff_medium_long(job_state: JobState, caplog: pytest.LogCaptureFixture) -> None:
    """Test ai_google with a unified_diff that is too long for the full diff."""
    existing_key = os.environ.get('GEMINI_API_KEY')
    try:
        job_state.old_data = 'aaaaaaaaaa\nb\nc\nd\nnew\ne\nf\ng\nhhhhhhhhhh\n'
        job_state.new_data = 'aaaaaaaaaa\nb\nc\nd\nold\ne\nf\ng\nhhhhhhhhhh\n'
        prompt = (
            'Describe the differences between the two versions of text as summarized in this unified diff, '
            'highlighting the most significant modifications:\n\n{unified_diff}'
        )
        job_state.job.differ = {
            'name': 'ai_google',
            'model': 'gemini-pro',
            'prompt': prompt,
            'timeout': 1e-9,
        }
        subdiffers = job_state.job.differ.copy()
        subdiffers.pop('name')
        # prompt_text = prompt.replace('\n', '\\n')
        expected = [
            '',
            '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
            '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
            '@@ -2,7 +2,7 @@',
            ' b',
            ' c',
            ' d',
            '-new',
            '+old',
            ' e',
            ' f',
            ' g',
            '------------',
            "Summary by Google Generative AI's model gemini-pro (differ directive(s): prompt=«custom», timeout=1e-09).",
        ]
        logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
        diff = job_state.get_diff(tz=test_tz)
        assert diff.splitlines()[2:] == expected
        expected_second_line = {
            (
                'HTTP client error: The read operation timed out when requesting data from '
                'generativelanguage.googleapis.com'
            ),
            'HTTP client error: timed out when requesting data from generativelanguage.googleapis.com',
            'The handshake operation timed out when requesting data from generativelanguage.googleapis.com',
        }  # not sure why error flips flops
        assert diff.splitlines()[0] == '## ERROR in summarizing changes using Google AI:'
        try:
            assert any(exp_str in diff.splitlines()[1] for exp_str in expected_second_line) is True
        except AssertionError:
            print(f'{diff.splitlines()[1]=}')
            raise
    finally:
        if existing_key:
            os.environ['GEMINI_API_KEY'] = existing_key
        logging.getLogger('webchanges.differs').setLevel(level=logging.WARNING)


@py_no_github
def test_ai_google_timeout_no_unified_diff(job_state: JobState, caplog: pytest.LogCaptureFixture) -> None:
    """Test ai_google timeout error with no unified diff."""
    existing_key = os.environ.get('GEMINI_API_KEY')
    try:
        os.environ['GEMINI_API_KEY'] = generate_random_string(39)
        job_state.old_data = 'a\n'
        job_state.new_data = 'b\n'
        job_state.job.differ = {
            'name': 'ai_google',
            'model': 'gemini-pro',
            'prompt': ('Identify and summarize the changes:\n\n<old>\n{old_text}\n</old>\n\n<new>\n{new_text}\n</new>'),
            'timeout': 1e-9,
            'temperature': 1,
            'top_k': 1,
            'top_p': 1,
        }
        expected_second_line = {
            (
                'HTTP client error: The read operation timed out when requesting data from '
                'generativelanguage.googleapis.com'
            ),
            'HTTP client error: timed out when requesting data from generativelanguage.googleapis.com',
            'The handshake operation timed out when requesting data from generativelanguage.googleapis.com',
        }  # not sure why error flips flops
        logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
        diff = job_state.get_diff()
        assert diff.splitlines()[0] == '## ERROR in summarizing changes using Google AI:'
        try:
            assert any(exp_str in diff.splitlines()[1] for exp_str in expected_second_line) is True
        except AssertionError:
            print(f'{diff.splitlines()[1]=}')
            raise
    finally:
        if existing_key:
            os.environ['GEMINI_API_KEY'] = existing_key
        logging.getLogger('webchanges.differs').setLevel(level=logging.WARNING)


WDIFF_TEST_DATA = [
    (
        'text/plain',
        'This is very old text\nThis is medium old text\n',
        'This is new text\nThis is newish text\n',
        [
            'This is [-very old-] {+new+} text',
            'This is [-medium old-] {+newish+} text',
        ],
        [
            'This is \x1b[91mvery old\x1b[0m \x1b[92mnew\x1b[0m text',
            'This is \x1b[91mmedium old\x1b[0m \x1b[92mnewish\x1b[0m text',
        ],
        [
            (
                'This is <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">very old'
                '</span> <span style="background-color:#d1ffd1;color:#082b08;">new</span> text<br>'
            ),
            (
                'This is <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">medium old'
                '</span> <span style="background-color:#d1ffd1;color:#082b08;">newish</span> text<br>'
            ),
        ],
    ),
    (
        'text/plain',
        'a',
        'b',
        ['[-a-] {+b+}'],
        ['\x1b[91ma\x1b[0m \x1b[92mb\x1b[0m'],
        [
            (
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">a</span> '
                '<span style="background-color:#d1ffd1;color:#082b08;">b</span>'
            )
        ],
    ),
    (
        'text/plain',
        'a',
        '',
        ['[-a-]'],
        ['\x1b[91ma\x1b[0m'],
        ['<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">a</span>'],
    ),
    (
        'text/plain',
        '',
        'b',
        ['{+b+}'],
        ['\x1b[92mb\x1b[0m'],
        ['<span style="background-color:#d1ffd1;color:#082b08;">b</span>'],
    ),
    (
        'text/plain',
        'a b',
        'a  b',
        ['a[- -] {+  +}b'],
        ['a\x1b[91m \x1b[0m \x1b[92m  \x1b[0mb'],
        [
            (
                'a<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"> </span> '
                '<span style="background-color:#d1ffd1;color:#082b08;">  </span>b'
            )
        ],
    ),
    (
        'text/markdown',
        '[link](https://www.a.com)\n',
        '[link](https://www.b.com)\n',
        ['[-[link](https://www.a.com)-] {+[link](https://www.b.com)+}'],
        ['\x1b[91m[link](https://www.a.com)\x1b[0m \x1b[92m[link](https://www.b.com)\x1b[0m'],
        [
            (
                '<span '
                'style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"><a '
                'style="font-family:inherit" rel="noopener" target="_blank" '
                'href="https://www.a.com">link</a></span> <span style="background-color:#d1ffd1;color:#082b08;"><a '
                'style="font-family:inherit" rel="noopener" target="_blank" href="https://www.b.com">link</a></span>'
            )
        ],
    ),
    (
        'text/markdown',
        '**one flower**\n',
        '**two flowers**\n',
        ['**[-one-] {+two+} [-flower-] {+flowers+}**'],
        ['**\x1b[91mone\x1b[0m \x1b[92mtwo\x1b[0m \x1b[91mflower\x1b[0m \x1b[92mflowers\x1b[0m**'],
        [
            (
                '<strong><span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">one</span> '
                '<span style="background-color:#d1ffd1;color:#082b08;">two</span> '
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">flower</span> '
                '<span style="background-color:#d1ffd1;color:#082b08;">flowers</span></strong>'
            )
        ],
    ),
    (
        'text/markdown',
        '~~one flower~~\n',
        '~~two flowers~~\n',
        ['~~[-one-] {+two+} [-flower-] {+flowers+}~~'],
        ['~~\x1b[91mone\x1b[0m \x1b[92mtwo\x1b[0m \x1b[91mflower\x1b[0m \x1b[92mflowers\x1b[0m~~'],
        [
            (
                '<s><span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">one</span> '
                '<span style="background-color:#d1ffd1;color:#082b08;">two</span> '
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">flower</span> '
                '<span style="background-color:#d1ffd1;color:#082b08;">flowers</span></s>'
            )
        ],
    ),
    (
        'text/markdown',
        '[**bold** text](https://www.a.com)\n',
        '[**bold** text](https://www.b.com)\n',
        ['[-[**bold** text](https://www.a.com)-] {+[**bold** text](https://www.b.com)+}'],
        ['\x1b[91m[**bold** text](https://www.a.com)\x1b[0m \x1b[92m[**bold** text](https://www.b.com)\x1b[0m'],
        [
            (
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"><a '
                'style="font-family:inherit" rel="noopener" target="_blank" '
                'href="https://www.a.com"><strong>bold</strong> text</a></span> '
                '<span style="background-color:#d1ffd1;color:#082b08;"><a style="font-family:inherit" rel="noopener" '
                'target="_blank" href="https://www.b.com"><strong>bold</strong> text</a></span>'
            )
        ],
    ),
    (
        'text/markdown',
        '**one flower**\n',
        'one flower\n',
        ['[-**-] one flower[-**-] '],
        ['\x1b[91m**\x1b[0m one flower\x1b[91m**\x1b[0m '],
        [
            (
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">**</span> '
                'one flower<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">'
                '**</span> '
            )
        ],
    ),
    (
        'text/html',
        'Text',
        '<b>Text</b>',
        ['{+<b>+}Text{+</b>+}'],
        ['\x1b[92m<b>\x1b[0mText\x1b[92m</b>\x1b[0m'],
        [
            (
                '<span style="background-color:#d1ffd1;color:#082b08;"><b></span>Text'
                '<span style="background-color:#d1ffd1;color:#082b08;"></b></span>'
            )
        ],
    ),
    (
        'text/html',
        '<div>',
        '<span>',
        ['[-<div>-] {+<span>+}'],
        ['\x1b[91m<div>\x1b[0m \x1b[92m<span>\x1b[0m'],
        [
            (
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"><div></span> '
                '<span style="background-color:#d1ffd1;color:#082b08;"><span></span>'
            )
        ],
    ),
    (
        'text/html',
        '<div id="a">',
        '<div id="b">',
        ['[-<div id="a">-] {+<div id="b">+}'],
        ['\x1b[91m<div id="a">\x1b[0m \x1b[92m<div id="b">\x1b[0m'],
        [
            (
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"><div id="a">'
                '</span> <span style="background-color:#d1ffd1;color:#082b08;"><div id="b"></span>'
            )
        ],
    ),
    (
        'text/html',
        '&copy;',
        '©',
        ['[-&copy;-] {+©+}'],
        ['\x1b[91m&copy;\x1b[0m \x1b[92m©\x1b[0m'],
        [
            (
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">&copy;</span> '
                '<span style="background-color:#d1ffd1;color:#082b08;">©</span>'
            )
        ],
    ),
    (
        'text/html',
        '<br>',
        '<br/>',
        ['[-<br>-] {+<br/>+}'],
        ['\x1b[91m<br>\x1b[0m \x1b[92m<br/>\x1b[0m'],
        [
            (
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"><br></span> '
                '<span style="background-color:#d1ffd1;color:#082b08;"><br/></span>'
            )
        ],
    ),
    (
        'text/html',
        '<!-- old -->',
        '<!-- new -->',
        ['[-<!-- old -->-] {+<!-- new -->+}'],
        ['\x1b[91m<!-- old -->\x1b[0m \x1b[92m<!-- new -->\x1b[0m'],
        [
            (
                '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"><!-- old -->'
                '</span> <span style="background-color:#d1ffd1;color:#082b08;"><!-- new --></span>'
            )
        ],
    ),
]


@pytest.mark.parametrize(
    ('mime_type', 'old_data', 'new_data', 'expected_text', 'expected_color', 'expected_html'), WDIFF_TEST_DATA
)
def test_wdiff(
    mime_type: str,
    old_data: str,
    new_data: str,
    expected_text: str,
    expected_color: str,
    expected_html: str,
    job_state: JobState,
) -> None:
    job_state.old_data = old_data
    job_state.old_mime_type = mime_type
    job_state.new_data = new_data
    job_state.new_mime_type = mime_type

    job_state.job.differ = {'name': 'wdiff', 'color': False}
    diff = job_state.get_diff()
    assert diff.splitlines()[2:] == expected_text

    job_state.job.differ = {'name': 'wdiff', 'color': True}
    job_state.generated_diff = {}
    job_state.unfiltered_diff = {}
    diff = job_state.get_diff()
    assert diff.splitlines()[2:] == expected_color

    diff = job_state.get_diff(report_kind='html')
    assert diff.splitlines()[2:] == expected_html


@pytest.mark.parametrize(
    ('color', 'changed_line'), [(True, 'line \033[91m5\033[0m \033[92mfive\033[0m'), (False, 'line [-5-] {+five+}')]
)
def test_wdiff_context_lines(color: bool, changed_line: str, job_state: JobState) -> None:
    """Test that wdiff keeps the changed line and its context lines, with or without color."""
    job_state.old_data = ''.join(f'line {i}\n' for i in range(10))
    job_state.new_data = job_state.old_data.replace('line 5', 'line five')
    job_state.job.differ = {'name': 'wdiff', 'color': color, 'context_lines': 1}
    assert job_state.get_diff().splitlines()[2:] == ['@@ 1...4 @@', 'line 4', changed_line, 'line 6', '@@ 8...10 @@']


@pytest.mark.parametrize('mime_type', ['text/plain', 'text/markdown'])
def test_wdiff_context_lines_html(mime_type: str, job_state: JobState) -> None:
    """Test that the range information lines of the HTML diff are styled as those of the unified differ."""
    job_state.old_data = ''.join(f'line {i}\n' for i in range(10))
    job_state.new_data = job_state.old_data.replace('line 5', 'line five')
    job_state.old_mime_type = job_state.new_mime_type = mime_type
    job_state.job.differ = {'name': 'wdiff', 'context_lines': 1}
    lines = job_state.get_diff(report_kind='html').splitlines()[2:]
    assert lines[0] == f'<span style="{WdiffDiffer.css_range_style}">@@ 1...4 @@</span><br>'
    assert lines[-1] == f'<span style="{WdiffDiffer.css_range_style}">@@ 8...10 @@</span>'


def test_wdiff_markdown_table(job_state: JobState) -> None:
    """Markdown table rows are rendered as an HTML table, a change spanning cells being split at their boundaries."""
    job_state.old_data = 'Prices\n| Model | Price |\n| A | $1 |\nEnd'
    job_state.new_data = 'Prices\n| Model | Price |\n| A | $3 |\n| B | $4 |\nEnd'
    job_state.old_mime_type = job_state.new_mime_type = 'text/markdown'
    job_state.job.differ = {'name': 'wdiff'}
    cell = 'border:1px solid #999;padding:2px 6px;vertical-align:top;'
    deleted = f'<span style="{WdiffDiffer.css_deltd_style}">'
    added = f'<span style="{WdiffDiffer.css_added_style}">'
    assert job_state.get_diff(report_kind='html').splitlines()[2:] == [
        'Prices<br>',
        (
            '<table style="border-collapse:collapse;">'
            f'<tr><td style="{cell}">Model</td><td style="{cell}">Price</td></tr>'
            f'<tr><td style="{cell}">A</td><td style="{cell}">{deleted}$1</span> {added}$3</span></td></tr>'
            f'<tr><td style="{cell}">{added}B</span></td><td style="{cell}">{added}$4</span></td></tr>'
            '</table>'
        ),
        'End',
    ]


def test_wdiff_markdown_table_cells() -> None:
    """A change span open at a cell boundary is closed in its cell and reopened in the next one."""
    add, rem = '<span a>', '<span r>'
    assert WdiffDiffer.markdown_table_cells(f'{add}| x | y |</span>', add, rem) == [
        f'{add}x</span>',
        f'{add}y</span>',
    ]
    assert WdiffDiffer.markdown_table_cells(f'| {rem}a</span> {add}b</span> | c \\| d |', add, rem) == [
        f'{rem}a</span> {add}b</span>',
        'c \\| d',
    ]


def test_wdiff_markdown_html_line_by_line(job_state: JobState) -> None:
    """Test that wdiff renders multi-line Markdown to HTML line by line, as the unified differ does.

    In html2text output each line is a block of its own; converted as one text, list items stayed as literal '* ',
    indentation was lost, headings became <h2> and '* * *' an <hr>.
    """
    job_state.old_data = '## Title\n  * item one\n    * nested two\n    indented\n* * *\nLast'
    job_state.new_data = job_state.old_data.replace('two', '2')
    job_state.old_mime_type = job_state.new_mime_type = 'text/markdown'
    job_state.job.differ = {'name': 'wdiff'}
    assert job_state.get_diff(report_kind='html').splitlines()[2:] == [
        '<strong>Title</strong><br>',
        '&nbsp;&nbsp;● item one<br>',
        (
            '&nbsp;&nbsp;&nbsp;&nbsp;⯀ nested <span style="background-color:#fff0f0;color:#9c1c1c;'
            'text-decoration:line-through;">two</span> <span style="background-color:#d1ffd1;color:#082b08;">2</span>'
            '<br>'
        ),
        '&nbsp;&nbsp;&nbsp;&nbsp;indented<br>',
        f'{"-" * 80}<br>',
        'Last',
    ]


# ---------------------------------------------------------------------------------------------------------------------
# Google AI (Gemini) transient-error retry logic
# ---------------------------------------------------------------------------------------------------------------------

_AI_GOOGLE_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'


def _make_response(status_code: int, *, json_data: object | None = None, text: str | None = None) -> httpx2.Response:
    """Build an httpx2.Response with an attached request (so ``response.url`` works)."""
    request = httpx2.Request('POST', _AI_GOOGLE_URL)
    if json_data is not None:
        return httpx2.Response(status_code, json=json_data, request=request)
    return httpx2.Response(status_code, text=text or '', request=request)


class _FakeJob:
    """Minimal stand-in for a JobBase, providing only what the retry helper logs."""

    index_number = 1


class _FakeClient:
    """Minimal stand-in for httpx2.Client that returns queued responses in order."""

    def __init__(self, responses: list[httpx2.Response]) -> None:
        self._responses = responses
        self.calls = 0

    def post(self, url: str, **kwargs: object) -> httpx2.Response:
        self.calls += 1
        return self._responses.pop(0)


def test_ai_google_retry_delay_structured() -> None:
    """The structured RetryInfo retryDelay is parsed."""
    response = _make_response(
        429,
        json_data={
            'error': {
                'code': 429,
                'status': 'RESOURCE_EXHAUSTED',
                'details': [
                    {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '15s'},
                ],
            }
        },
    )
    assert _ai_google_retry_delay(response) == 15.0


def test_ai_google_retry_delay_message_text() -> None:
    """The retry delay is parsed from the human-readable message as a fallback."""
    response = _make_response(
        429,
        json_data={'error': {'message': 'Resource exhausted. Please retry in 15.606408828s.'}},
    )
    delay = _ai_google_retry_delay(response)
    assert delay is not None
    assert round(delay, 3) == 15.606


def test_ai_google_retry_delay_from_plain_text() -> None:
    """The retry delay is parsed even when the body is not valid JSON."""
    response = _make_response(429, text='Too many requests; please retry in 7s')
    assert _ai_google_retry_delay(response) == 7.0


def test_ai_google_retry_delay_none() -> None:
    """No delay is returned when none is present."""
    assert _ai_google_retry_delay(_make_response(429, json_data={'error': {'message': 'rate limited'}})) is None
    assert _ai_google_retry_delay(_make_response(429, text='garbage')) is None


def test_ai_google_retry_wait() -> None:
    """Retry waits: 429 the parsed delay plus a buffer, 503 a fixed wait, others (or a bad 429) none."""
    parseable = _make_response(429, json_data={'error': {'details': [{'@type': '.../RetryInfo', 'retryDelay': '10s'}]}})
    assert _ai_google_retry_wait(parseable) == 10.0 + AI_GOOGLE_429_RETRY_BUFFER

    # Even a large delay is returned (the cumulative ceiling, not a per-call cap, governs whether it is honored).
    large = _make_response(429, json_data={'error': {'details': [{'@type': '.../RetryInfo', 'retryDelay': '300s'}]}})
    assert _ai_google_retry_wait(large) == 300.0 + AI_GOOGLE_429_RETRY_BUFFER

    unparseable = _make_response(429, json_data={'error': {'message': 'rate limited'}})
    assert _ai_google_retry_wait(unparseable) is None

    assert _ai_google_retry_wait(_make_response(503)) == AI_GOOGLE_503_RETRY_WAIT
    assert _ai_google_retry_wait(_make_response(200, json_data={})) is None
    assert _ai_google_retry_wait(_make_response(400, json_data={})) is None


def test_ai_google_post_with_retry_429_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 is retried once (honoring the parsed delay plus the buffer), then the success response is returned."""
    sleeps: list[float] = []
    monkeypatch.setattr(differs.time, 'sleep', lambda secs: sleeps.append(secs))
    responses = [
        _make_response(429, json_data={'error': {'details': [{'@type': '.../RetryInfo', 'retryDelay': '3s'}]}}),
        _make_response(200, json_data={'candidates': []}),
    ]
    client = _FakeClient(responses)
    result = _ai_google_post_with_retry(client, _AI_GOOGLE_URL, job=_FakeJob())  # ty:ignore[invalid-argument-type]
    assert result.status_code == 200
    assert client.calls == 2
    assert sleeps == [3.0 + AI_GOOGLE_429_RETRY_BUFFER]


def test_ai_google_post_with_retry_503_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 503 is retried after the fixed wait, then the success response is returned."""
    sleeps: list[float] = []
    monkeypatch.setattr(differs.time, 'sleep', lambda secs: sleeps.append(secs))
    responses = [_make_response(503), _make_response(200, json_data={'candidates': []})]
    client = _FakeClient(responses)
    result = _ai_google_post_with_retry(client, _AI_GOOGLE_URL, job=_FakeJob())  # ty:ignore[invalid-argument-type]
    assert result.status_code == 200
    assert sleeps == [AI_GOOGLE_503_RETRY_WAIT]


def test_ai_google_post_with_retry_exceeds_ceiling_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 whose requested delay alone exceeds the cumulative ceiling is not retried."""
    sleeps: list[float] = []
    monkeypatch.setattr(differs.time, 'sleep', lambda secs: sleeps.append(secs))
    too_long = AI_GOOGLE_MAX_TOTAL_WAIT + 1
    json_data = {'error': {'details': [{'@type': '.../RetryInfo', 'retryDelay': f'{too_long}s'}]}}
    client = _FakeClient([_make_response(429, json_data=json_data)])
    result = _ai_google_post_with_retry(client, _AI_GOOGLE_URL, job=_FakeJob())  # ty:ignore[invalid-argument-type]
    assert result.status_code == 429
    assert client.calls == 1
    assert sleeps == []
    assert result.extensions['webchanges_requested_delay'] == too_long


def test_ai_google_post_with_retry_unparseable_429_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 with no parseable retry delay is not retried."""
    sleeps: list[float] = []
    monkeypatch.setattr(differs.time, 'sleep', lambda secs: sleeps.append(secs))
    client = _FakeClient([_make_response(429, json_data={'error': {'message': 'rate limited'}})])
    result = _ai_google_post_with_retry(client, _AI_GOOGLE_URL, job=_FakeJob())  # ty:ignore[invalid-argument-type]
    assert result.status_code == 429
    assert client.calls == 1
    assert sleeps == []


def test_ai_google_post_with_retry_stops_at_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retrying stops once the next wait would push the cumulative wait past the ceiling."""
    sleeps: list[float] = []
    monkeypatch.setattr(differs.time, 'sleep', lambda secs: sleeps.append(secs))
    # 503 waits a fixed AI_GOOGLE_503_RETRY_WAIT each time; keep returning 503 forever.
    client = _FakeClient([_make_response(503) for _ in range(20)])
    result = _ai_google_post_with_retry(client, _AI_GOOGLE_URL, job=_FakeJob())  # ty:ignore[invalid-argument-type]
    assert result.status_code == 503
    # Sleeps continue while cumulative + next <= ceiling, then stop.
    expected_sleeps = int(AI_GOOGLE_MAX_TOTAL_WAIT // AI_GOOGLE_503_RETRY_WAIT)
    assert sleeps == [AI_GOOGLE_503_RETRY_WAIT] * expected_sleeps
    assert sum(sleeps) <= AI_GOOGLE_MAX_TOTAL_WAIT
    assert client.calls == expected_sleeps + 1


def test_ai_google_post_with_retry_records_retry_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    """The returned response carries the number of retries made and the cumulative wait in its extensions."""
    monkeypatch.setattr(differs.time, 'sleep', lambda secs: None)
    # A 100s delay fits twice under the cumulative ceiling, so the third 429 is returned after two retries.
    json_data = {'error': {'details': [{'@type': '.../RetryInfo', 'retryDelay': '100s'}]}}
    client = _FakeClient([_make_response(429, json_data=json_data) for _ in range(3)])
    result = _ai_google_post_with_retry(client, _AI_GOOGLE_URL, job=_FakeJob())  # ty:ignore[invalid-argument-type]
    assert result.status_code == 429
    assert client.calls == 3
    assert result.extensions['webchanges_retries'] == 2
    assert result.extensions['webchanges_total_wait'] == pytest.approx(2 * (100.0 + AI_GOOGLE_429_RETRY_BUFFER))

    # Not retried at all: stats are still present and zero.
    client = _FakeClient([_make_response(429, json_data={'error': {'message': 'rate limited'}})])
    result = _ai_google_post_with_retry(client, _AI_GOOGLE_URL, job=_FakeJob())  # ty:ignore[invalid-argument-type]
    assert result.extensions['webchanges_retries'] == 0
    assert result.extensions['webchanges_total_wait'] == 0.0


def test_ai_google_send_to_model_429_summary_reports_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """The error summary for a persistent 429 states the retries made, or that none were made."""
    monkeypatch.setenv('GEMINI_API_KEY', 'A' * 39)
    monkeypatch.setattr(differs.time, 'sleep', lambda secs: None)
    job = JobBase.unserialize({'url': 'https://example.com', 'differ': {'name': 'ai_google'}})

    def run(responses: list[httpx2.Response]) -> str:
        client = _FakeClient(responses)
        monkeypatch.setattr(differs.httpx2, 'Client', lambda **kwargs: contextlib.nullcontext(client))
        summary, _ = AIGoogleDiffer._send_to_model(job, 'system', 'prompt')
        return summary

    # A 100s delay fits twice under the cumulative ceiling, so the third 429 is reported after two retries.
    json_data = {'error': {'details': [{'@type': '.../RetryInfo', 'retryDelay': '100s'}]}}
    summary = run([_make_response(429, json_data=json_data) for _ in range(3)])
    assert 'Received error 429' in summary
    assert 'Still failing after 2 automatic retries and 202 seconds of waiting' in summary

    summary = run([_make_response(429, json_data={'error': {'message': 'rate limited'}})])
    assert 'Received error 429' in summary
    assert 'Not retried automatically as the response carried no usable retry delay.' in summary

    json_data = {'error': {'details': [{'@type': '.../RetryInfo', 'retryDelay': '600s'}]}}
    summary = run([_make_response(429, json_data=json_data)])
    assert 'Received error 429' in summary
    assert (
        f'Not retried automatically as the requested delay of 600 seconds exceeded the '
        f'{AI_GOOGLE_MAX_TOTAL_WAIT}-second limit.'
    ) in summary
