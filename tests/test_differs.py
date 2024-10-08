"""Test the generation of various types of diffs.

Run individually with
> pytest -v --cov=./ --cov-report=term --cov-report=html --cov-config=.coveragerc tests/test_differs.py

"""

from __future__ import annotations

import base64
import logging
import os
import random
import string
import sys
from io import BytesIO
from pathlib import Path
from typing import Callable, cast
from zoneinfo import ZoneInfo

import pytest

from webchanges.differs import CommandDiffer, DifferBase, UnifiedDiffer
from webchanges.handler import JobState
from webchanges.jobs import JobBase, ShellJob
from webchanges.storage import SsdbSQLite3Storage

py_latest_only = cast(
    Callable[[Callable], Callable],
    pytest.mark.skipif(
        sys.version_info < (3, 12),
        reason='Time consuming; testing latest version only',
    ),
)
py_no_github = cast(
    Callable[[Callable], Callable],
    pytest.mark.skipif(
        os.getenv('GITHUB_ACTIONS') is not None,
        reason='Google AI API call not placed from GitHub Actions',
    ),
)
# py_nt_only = cast(
#     Callable[[Callable], Callable],
#     pytest.mark.skipif(
#         os.name == 'nt',
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
        '<td style="background-color:#d1ffd1;color:#082b08;">'
        '--------------------------------------------------------------------------------</td>',
    ),
    (
        '+[Link](https://example.com)',
        '<td style="background-color:#d1ffd1;color:#082b08;"><a style="font-family:inherit" rel="noopener" '
        'target="_blank" href="https://example.com">Link</a></td>',
    ),
    (
        ' ![Image](https://example.com/picture.png "picture")',
        '<td><img style="max-width:100%;height:auto;max-height:100%" src="https://example.com/picture.png"'
        ' alt="Image" title="picture" /></td>',
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
    (' | table | row |', '<td>| table | row |</td>'),
]


def generate_random_string(length: int = 39) -> str:
    """
    Generates a random alphanumeric string of specified length.
    """
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))  # noqa: S311 not suitable for security/cryptogr.


@pytest.fixture()  # type: ignore[misc]
def job_state() -> JobState:
    """Get a JobState object for testing."""
    ssdb_file = ':memory:'
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # type: ignore[arg-type]
    job_state = JobState(ssdb_storage, ShellJob(command=''))
    job_state.old_timestamp = 1605147837.511478  # initial release of webchanges!
    job_state.new_timestamp = 1605147837.511478
    return job_state


# def test_no_differ_name_raises_valueerror() -> None:
#     with pytest.raises(ValueError) as pytest_wrapped_e:
#         list(DifferBase.normalize_differ(''))
#     assert str(pytest_wrapped_e.value) == "Job None: Differ directive must have a 'name' sub-directive: {'name': ''}."


def test_invalid_differ_name_raises_valueerror() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(DifferBase.normalize_differ({'name': 'adiffernamethatdoesnotexist'}))
    assert str(pytest_wrapped_e.value) == 'Job None: No differ named adiffernamethatdoesnotexist.'


def test_providing_subdirective_to_differ_without_differ_raises_valueerror() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(DifferBase.normalize_differ({'name': 'deepdiff', 'asubdifferthatdoesnotexist': True}))
    err_msg = str(pytest_wrapped_e.value)
    assert err_msg == (
        'Job None: Differ deepdiff does not support sub-directive(s) asubdifferthatdoesnotexist (supported: data_type, '
        'ignore_order, ignore_string_case, significant_digits).'
    )


def test_providing_unknown_subdirective_raises_valueerror() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(DifferBase.normalize_differ({'name': 'image', 'data_type': 'json', 'anothersubdirective': '42'}))
    err_msg = str(pytest_wrapped_e.value)
    assert err_msg == (
        'Job None: Differ image does not support sub-directive(s) anothersubdirective (supported: data_type, '
        'mse_threshold).'
    )


def test_process_no_valid_differ_returns_empty(job_state: JobState) -> None:
    diff = DifferBase(job_state).process(differ_kind='', directives={}, job_state=job_state)
    assert {} == diff


def test_make_timestamp() -> None:
    ts = DifferBase.make_timestamp(1605147837.511478, test_tz)
    assert ts == 'Thu, 12 Nov 2020 02:23:57 +0000 (UTC)'

    ts = DifferBase.make_timestamp(0)
    assert ts == 'NEW'


def test_html2text() -> None:
    text = DifferBase.html2text('<a href="https://example.com">link</a>')
    assert text == '[link](https://example.com)'


def test_raise_import_error(job_state: JobState) -> None:
    """Test ai_google with no key."""

    with pytest.raises(ImportError) as pytest_wrapped_e:
        DifferBase(job_state).raise_import_error('test', 'error!')
    assert str(pytest_wrapped_e.value) == (
        "Job 0: Python package 'test' is not installed; cannot use 'differ: ' ()\nerror!"
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
        '<tr><td style="font-family:monospace;color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 '
        '+0000 (UTC)</td></tr>',
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
        '<tr><td style="font-family:monospace;color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 '
        '+0000 (UTC)</td></tr>',
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
        '/**Deletions are being shown as 75% or more of the content has been deleted**',
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


@pytest.mark.parametrize('inpt, out', DIFF_TO_HTML_TEST_DATA)  # type: ignore[misc]
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
    job = JobBase.unserialize({'url': 'https://www.example.com', 'is_markdown': True, 'markdown_padded_tables': True})
    job_state.job = job
    result = ''.join(list(UnifiedDiffer(job_state).unified_diff_to_html(inpt)))
    assert result[193:-8] == (
        '<tr><td><span style="font-family:monospace;white-space:pre-wrap">| table | row |</span></td></tr>'
    )


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
        '        <thead><tr><th style="font-family:monospace" class="diff_next"><br '
        '/></th><th style="font-family:monospace" colspan="2" '
        'class="diff_header">Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</th><th '
        'style="font-family:monospace" class="diff_next"><br /></th><th '
        'style="font-family:monospace" colspan="2" class="diff_header">Thu, 12 Nov '
        '2020 02:23:57 +0000 (UTC)</th></tr></thead>',
        '        <tbody>',
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
        'style="color:green;background-color:lightgreen">b</span></td></tr>',
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
    diff = job_state.get_diff(report_kind='text')
    assert diff.splitlines() == expected


def test_command_no_change(job_state: JobState) -> None:
    """Test command differ.

    Diff tools return 0 for "nothing changed" or 1 for "files differ", anything else is an error.
    """
    job_state.old_data = 'a\n'
    job_state.new_data = 'a\n'
    job_state.job.differ = {'name': 'command', 'command': 'echo'}  # test with differ name
    job_state.job.is_markdown = True
    diff = job_state.get_diff(tz=test_tz)
    assert not diff
    assert 'changed,no_report' == job_state.verb

    # redo as markdown
    diff = job_state.get_diff(report_kind='markdown')
    assert not diff
    assert 'changed,no_report' == job_state.verb

    # redo as html
    diff = job_state.get_diff(report_kind='html')
    assert not diff
    assert 'changed,no_report' == job_state.verb


def test_command_change(job_state: JobState) -> None:
    """Test command differ.

    Diff tools return 0 for "nothing changed" or 1 for "files differ", anything else is an error.
    """
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    if os.name == 'nt':
        command = 'cmd /C exit 1 & rem'
    else:
        command = 'bash -c " echo \'This is a custom diff\'; exit 1" #'
    job_state.job.differ = {'command': command}  # test with no differ name
    expected = [
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
    ]
    job_state.job.is_markdown = True
    diff = job_state.get_diff(tz=test_tz)
    assert diff.splitlines()[1:3] == expected

    # redo as markdown
    diff = job_state.get_diff(report_kind='markdown')
    assert diff.splitlines()[1:3] == expected

    # redo as html
    expected = [
        # f'Using differ &quot;{{&#x27;command&#x27;: &#x27;{html.escape(command)}&#x27;}}&quot;',
        '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
        '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
    ]
    diff = job_state.get_diff(report_kind='html')
    assert diff.splitlines()[1:3] == expected


def test_command_error(job_state: JobState) -> None:
    """Test command differ.

    Diff tools return 0 for "nothing changed" or 1 for "files differ", anything else is an error.
    """
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    if os.name == 'nt':
        command = 'cmd /C exit 2 & rem'
    else:
        command = 'bash -c " echo \'This is a custom diff\'; exit 2" #'
    job_state.job.differ = {'command': command}  # test with no differ name
    job_state.get_diff()
    assert isinstance(job_state.exception, RuntimeError)
    if os.name != 'nt':
        command = command.replace("'", "\\'")
    assert str(job_state.exception) == (f"Job 0: External differ '{{'command': '{command}'}}' returned '' ()")


def test_command_bad_command(job_state: JobState) -> None:
    """Test command differ with bad command."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.differ = {'name': 'command', 'command': 'dfgfdgsdfg'}
    job_state.get_diff()
    assert isinstance(job_state.exception, FileNotFoundError)
    if os.name == 'nt':
        assert str(job_state.exception) == '[WinError 2] The system cannot find the file specified'


def test_command_command_error(job_state: JobState) -> None:
    """Test command differ with command returning an error."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.differ = {'name': 'command', 'command': 'dir /x'}
    job_state.get_diff()
    assert isinstance(job_state.exception, (RuntimeError, FileNotFoundError))
    if os.name == 'nt':
        assert str(job_state.exception) == (
            "Job 0: External differ '{'command': 'dir /x'}' returned 'dir: cannot access "
            "'/x': No such file or directory' ()"
        )
    # else:
    # assert str(pytest_wrapped_e.value) == ("[Errno 2] No such file or directory: 'dir'")


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
    job_state.job.monospace = True
    job_state.job.is_markdown = True
    expected = [
        '<span style="font-family:monospace;white-space:pre-wrap">## This is '
        '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">not</span> '
        'what I <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">want</span><br>',
        '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">for you</span> '
        '<span style="background-color:#d1ffd1;color:#082b08;">want</span><br>',
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
        '<span style="font-family:monospace;white-space:pre-wrap;">'
        '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
        '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
        "• Value of root['test'] changed from <span "
        'style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">"1"</span> '
        'to <span style="background-color:#d1ffd1;color:#082b08;">"2"</span></span>',
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
        '<span style="font-family:monospace;white-space:pre-wrap;">'
        '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
        '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
        '• Type of root changed from str to list and value changed from <span '
        'style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">""</span> '
        'to <span style="background-color:#d1ffd1;color:#082b08;">[',
        '  {',
        '    "test": 2,',
        '    "second_test": 3',
        '  },',
        '  "morestuff",',
        '  323',
        ']</span></span>',
    ]
    diff = job_state.get_diff(report_kind='html', tz=test_tz)
    assert diff.splitlines() == expected


def test_deepdiff_json_no_change(job_state: JobState) -> None:
    """Test deepdiff json differ with bad data."""
    job_state.old_data = '{"test": 1}'
    job_state.new_data = '{"test": 1}'
    job_state.job.differ = {'name': 'deepdiff'}
    diff = job_state.get_diff()
    assert diff == ''


def test_deepdiff_json_bad_data(job_state: JobState) -> None:
    """Test deepdiff json differ with bad data."""
    job_state.old_data = '{"test": 1'
    job_state.new_data = '{"test": 2'
    job_state.job.differ = {'name': 'deepdiff', 'data_type': 'json'}
    expected = [
        'Differ deepdiff ERROR: New data is invalid JSON',
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


# @py_nt_only
@py_latest_only
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
            '<span style="font-family:monospace">'
            '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC) '
            f'(<a href="{job_state.old_data}">Old image</a>)</span>',
            '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC) '
            f'(<a href="{job_state.new_data}">New image</a>)</span>',
            '</span>',
            'New image:',
            f'<img src="{job_state.old_data}" style="max-width: 100%; display: block;">',
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
            '<span style="font-family:monospace">'
            '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC) '
            f'(<a href="file://{job_state.old_data}">Old image</a>)</span>',
            '<span style="color:darkgreen;">+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC) '
            f'(<a href="file://{job_state.new_data}">New image</a>)</span>',
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
    # from webchanges.mailer import Mailer
    #
    # email = Mailer().msg('', '', '', '', diff)


@py_latest_only
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
    expected = '<br>\n'.join(
        [
            '<span style="font-family:monospace">'
            '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
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
    expected = '<br>\n'.join(
        [
            '<span style="font-family:monospace">'
            '<span style="color:darkred;">--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)</span>',
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

    existing_key = os.environ.get('GOOGLE_AI_API_KEY')
    try:
        os.environ['GOOGLE_AI_API_KEY'] = generate_random_string(39)
        job_state.new_data = job_state.old_data
        job_state.job.differ = {'name': 'ai_google', 'model': 'gemini-pro', 'timeout': 1e-9}
        diff = job_state.get_diff()
        assert diff == ''
    finally:
        if existing_key:
            os.environ['GOOGLE_AI_API_KEY'] = existing_key


def test_ai_google_no_key(job_state: JobState) -> None:
    """Test ai_google with no key."""

    existing_key = os.environ.get('GOOGLE_AI_API_KEY')
    try:
        os.environ['GOOGLE_AI_API_KEY'] = ''
        job_state.job.differ = {'name': 'ai_google'}
        diff = job_state.get_diff()
        expected = (
            '## ERROR in summarizing changes using ai_google:\n'
            'Environment variable GOOGLE_AI_API_KEY not found or is of the incorrect length 0.\n'
            '\n'
            '\n'
            'Differ unified with directive(s) None encountered an error:\n'
            '\n'
        )
        assert diff[: len(expected)] == expected
    finally:
        if existing_key:
            os.environ['GOOGLE_AI_API_KEY'] = existing_key


@py_no_github
def test_ai_google_bad_api_key(job_state: JobState) -> None:
    """Test ai_google but with unchanged data as not to trigger API charges."""
    existing_key = os.environ.get('GOOGLE_AI_API_KEY')
    try:
        os.environ['GOOGLE_AI_API_KEY'] = generate_random_string(39)
        job_state.old_data = 'a\n'
        job_state.new_data = 'b\n'
        job_state.job.differ = {'name': 'ai_google'}
        subdiffers = job_state.job.differ.copy()
        subdiffers.pop('name')
        expected = [
            'AI summary unavailable: Received error from generativelanguage.googleapis.com: API key not valid. '
            'Please pass a valid API key.',
            '',
            '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
            '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
            '@@ -1 +1 @@',
            '-a',
            '+b',
            '------------',
            'Summary generated by Google Generative AI (differ directive(s): model=gemini-1.5-flash-latest)',
        ]
        diff = job_state.get_diff(tz=test_tz)
        assert diff.splitlines() == expected
    finally:
        if existing_key:
            os.environ['GOOGLE_AI_API_KEY'] = existing_key


@py_no_github
def test_ai_google_timeout_and_unified_diff_medium_long(job_state: JobState, caplog: pytest.LogCaptureFixture) -> None:
    """Test ai_google with a unified_diff that is too long for the full diff."""
    existing_key = os.environ.get('GOOGLE_AI_API_KEY')
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
            'token_limit': 53,
        }
        subdiffers = job_state.job.differ.copy()
        subdiffers.pop('name')
        prompt_text = prompt.replace('\n', '\\n')
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
            'Summary generated by Google Generative AI (differ directive(s): model=gemini-pro, '
            f'prompt={prompt_text}, timeout=1e-09, token_limit=53)',
        ]
        logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
        diff = job_state.get_diff(tz=test_tz)
        assert diff.splitlines()[1:] == expected
        expected_in_first_line = {
            'AI summary unavailable: HTTP client error: The read operation timed out when requesting data from '
            'generativelanguage.googleapis.com',
            'AI summary unavailable: HTTP client error: timed out when requesting data from '
            'generativelanguage.googleapis.com',
            'AI summary unavailable: HTTP client error: _ssl.c:983: The handshake operation timed out when requesting '
            'data from generativelanguage.googleapis.com',
        }  # not sure why error flips flops
        try:
            assert any(exp_str in diff.splitlines()[0] for exp_str in expected_in_first_line) is True
        except AssertionError:
            print(f'{diff=}')
            raise
        expected_in_logs = (
            'Model prompt with full diff is too long: (56 est. tokens exceeds limit of 53 tokens); recomputing with '
            'default contextlines'
        )
        assert expected_in_logs in caplog.text
    finally:
        if existing_key:
            os.environ['GOOGLE_AI_API_KEY'] = existing_key
        logging.getLogger('webchanges.differs').setLevel(level=logging.WARNING)


def test_ai_google_unified_diff_too_long(job_state: JobState, caplog: pytest.LogCaptureFixture) -> None:
    """Test ai_google with a unified_diff that is too long."""
    existing_key = os.environ.get('GOOGLE_AI_API_KEY')
    try:
        job_state.old_data = 'a\n'
        job_state.new_data = 'b\n'
        prompt = (
            'Describe the differences between the two versions of text as summarized in this unified diff, '
            'highlighting the most significant modifications:\n\n{unified_diff}'
        )

        job_state.job.differ = {
            'name': 'ai_google',
            'model': 'gemini-pro',
            'prompt': prompt,
            'token_limit': 1,
        }
        subdiffers = job_state.job.differ.copy()
        subdiffers.pop('name')
        prompt_text = prompt.replace('\n', '\\n')
        expected = [
            'AI summary unavailable (model prompt with unified diff is too long: 44 est. tokens exceeds maximum of 1)',
            '',
            '--- @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
            '+++ @ Thu, 12 Nov 2020 02:23:57 +0000 (UTC)',
            '@@ -1 +1 @@',
            '-a',
            '+b',
            '------------',
            'Summary generated by Google Generative AI (differ directive(s): model=gemini-pro, '
            f'prompt={prompt_text}, token_limit=1)',
        ]
        logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
        diff = job_state.get_diff(tz=test_tz)
        assert diff.splitlines() == expected
        expected_in_logs = (
            'Model prompt with full diff is too long: (44 est. tokens exceeds limit of 1 tokens); recomputing with '
            'default contextlines'
        )
        assert expected_in_logs in caplog.text
    finally:
        if existing_key:
            os.environ['GOOGLE_AI_API_KEY'] = existing_key
        logging.getLogger('webchanges.differs').setLevel(level=logging.WARNING)


@py_no_github
def test_ai_google_timeout_no_unified_diff(job_state: JobState, caplog: pytest.LogCaptureFixture) -> None:
    """Test ai_google timeout error with no unified diff."""
    existing_key = os.environ.get('GOOGLE_AI_API_KEY')
    try:
        os.environ['GOOGLE_AI_API_KEY'] = generate_random_string(39)
        job_state.old_data = 'a\n'
        job_state.new_data = 'b\n'
        job_state.job.differ = {
            'name': 'ai_google',
            'model': 'gemini-pro',
            'prompt': (
                'Identify and summarize the changes:\n\n<old>\n{old_text}\n</old>\n\n<new>\n{' 'new_text}\n</new>'
            ),
            'timeout': 1e-9,
            'temperature': 1,
            'top_k': 1,
            'top_p': 1,
            'token_limit': 1,
        }
        expected = {
            'AI summary unavailable: HTTP client error: The read operation timed out when requesting data from '
            'generativelanguage.googleapis.com',
            'AI summary unavailable: HTTP client error: timed out when requesting data from '
            'generativelanguage.googleapis.com',
            'AI summary unavailable: HTTP client error: _ssl.c:983: The handshake operation timed out when requesting '
            'data from generativelanguage.googleapis.com',
        }  # not sure why error flips flops
        logging.getLogger('webchanges.differs').setLevel(level=logging.DEBUG)
        diff = job_state.get_diff()
        try:
            assert any(exp_str in diff for exp_str in expected) is True
        except AssertionError:
            print(f'{diff=}')
            raise
        expected_in_logs = 'The model prompt may be too long: 17 est. tokens exceeds limit of 1 tokens'
        assert expected_in_logs in caplog.text
    finally:
        if existing_key:
            os.environ['GOOGLE_AI_API_KEY'] = existing_key
        logging.getLogger('webchanges.differs').setLevel(level=logging.WARNING)


WDIFF_TEST_DATA = [
    (
        'a',
        'b',
        ['\x1b[91ma \x1b[92mb\x1b[0m'],
        [
            '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">a</span> '
            '<span style="background-color:#d1ffd1;color:#082b08;">b</span>'
        ],
    ),
    (
        'a',
        '',
        ['\x1b[91ma \x1b[92m\x1b[0m'],
        [
            '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">a</span> '
            '<span style="background-color:#d1ffd1;color:#082b08;"></span>'
        ],
    ),
    (
        '',
        'b',
        ['\x1b[91m \x1b[92mb\x1b[0m'],
        [
            '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"></span> '
            '<span style="background-color:#d1ffd1;color:#082b08;">b</span>'
        ],
    ),
    (
        'This is very old text\nThis is medium old text\n',
        'This is new text\nThis is newish text\n',
        [
            'This is \x1b[92mnew \x1b[91mvery old\x1b[0m text ',
            'This is \x1b[92mnewish \x1b[91mmedium old\x1b[0m text ',
        ],
        [
            'This is <span style="background-color:#d1ffd1;color:#082b08;">new</span> '
            '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">'
            'very old</span> text <br>',
            'This is <span style="background-color:#d1ffd1;color:#082b08;">newish</span> '
            '<span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;">medium old</span> '
            'text ',
        ],
    ),
    (
        '[link](https://www.a.com)\n',
        '[link](https://www.b.com)\n',
        ['\x1b[91m[link](https://www.a.com) \x1b[92m[link](https://www.b.com)\x1b[0m '],
        [
            '<span '
            'style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through;"><a '
            'style="font-family:inherit" rel="noopener" target="_blank" '
            'href="https://www.a.com">link</a></span> <span '
            'style="background-color:#d1ffd1;color:#082b08;"><a '
            'style="font-family:inherit" rel="noopener" target="_blank" '
            'href="https://www.b.com">link</a></span> '
        ],
    ),
]


@pytest.mark.parametrize('old_data, new_data, expected_text, expected_html', WDIFF_TEST_DATA)  # type: ignore[misc]
def test_worddiff(old_data: str, new_data: str, expected_text: str, expected_html: str, job_state: JobState) -> None:
    job_state.job.differ = {'name': 'wdiff'}
    job_state.old_data = old_data
    job_state.new_data = new_data
    job_state.new_mime_type = 'text/markdown'
    diff = job_state.get_diff()
    assert diff.splitlines()[2:] == expected_text
    diff = job_state.get_diff(report_kind='html')
    assert diff.splitlines()[2:] == expected_html
