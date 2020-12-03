import traceback

import pytest

from webchanges.handler import JobState, Report
from webchanges.jobs import JobBase
from webchanges.reporters import HtmlReporter
from webchanges.storage import DEFAULT_CONFIG

DIFFTOHTMLTESTDATA = [
    ('+Added line', '<tr style="background-color:#e6ffed"><td>Added line</td></tr>'),
    ('-Deleted line', '<tr style="background-color:#ffeef0;color:#cb2431;text-decoration:line-through">'
                      '<td>Deleted line</td></tr>'),
    # Changes line
    ('@@ -1,1 +1,1 @@', '<tr style="background-color:#fafbfc;font-family:monospace">'
                        '<td style="font-family:monospace">@@ -1,1 +1,1 @@</td></tr>'),
    # Horizontal ruler is manually expanded since <hr> tag is used to separate jobs
    ('+* * *', '<tr style="background-color:#e6ffed"><td>'
               '--------------------------------------------------------------------------------</td></tr>'),
    ('+[Link](https://example.com)',
        '<tr style="background-color:#e6ffed"><td><a style="font-family:inherit" rel="noopener" target="_blank" '
        'href="https://example.com">Link</a></td></tr>'),
    (' ![Image](https://example.com/picture.png "picture")',
     '<tr><td><img style="max-width:100%;height:auto;max-height:100%" src="https://example.com/picture.png" alt="Image"'
     ' title="picture" /></td></tr>'),
    ('   Indented text (replace leading spaces)',
     '<tr><td>&nbsp;&nbsp;Indented text (replace leading spaces)</td></tr>'),
    (' # Heading level 1', '<tr><td><strong>Heading level 1</strong></td></tr>'),
    (' ## Heading level 2', '<tr><td><strong>Heading level 2</strong></td></tr>'),
    (' ### Heading level 3', '<tr><td><strong>Heading level 3</strong></td></tr>'),
    (' #### Heading level 4', '<tr><td><strong>Heading level 4</strong></td></tr>'),
    (' ##### Heading level 5', '<tr><td><strong>Heading level 5</strong></td></tr>'),
    (' ###### Heading level 6', '<tr><td><strong>Heading level 6</strong></td></tr>'),
    ('   * Bullet point level 1', '<tr><td>&nbsp;&nbsp;● Bullet point level 1</td></tr>'),
    ('     * Bullet point level 2', '<tr><td>&nbsp;&nbsp;&nbsp;&nbsp;⯀ Bullet point level 2</td></tr>'),
    ('       * Bullet point level 3', '<tr><td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;○ Bullet point level 3</td></tr>'),
    ('         * Bullet point level 4',
     '<tr><td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;○ Bullet point level 4</td></tr>'),
    (' *emphasis*', '<tr><td><em>emphasis</em></td></tr>'),
    (' _**emphasis and strong**_', '<tr><td><em><strong>emphasis and strong</strong></em></td></tr>'),
    (' **strong**', '<tr><td><strong>strong</strong></td></tr>'),
    (' **_strong and emphasis_**', '<tr><td><strong><em>strong and emphasis</em></strong></td></tr>'),
    (' ~~strikethrough~~', '<tr><td><strike>strikethrough</strike></td></tr>'),
    (' | table | row |', '<tr><td>| table | row |</td></tr>'),
]


REPORTER = [report for report, v in DEFAULT_CONFIG['report'].items() if v.get('enabled', False)]


@pytest.mark.parametrize('inpt, out', DIFFTOHTMLTESTDATA)
def test_diff_to_html(inpt, out):
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n' + inpt
    job = JobBase.unserialize({'url': '', 'is_markdown': True, 'markdown_padded_tables': False, 'diff_tool': ''})
    result = ''.join(list(HtmlReporter('', '', '', '')._diff_to_html(inpt, job)))
    assert result[202:-8] == out


def test_diff_to_htm_padded_table():
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n | table | row |'
    job = JobBase.unserialize({'url': '', 'is_markdown': True, 'markdown_padded_tables': True, 'diff_tool': ''})
    result = ''.join(list(HtmlReporter('', '', '', '')._diff_to_html(inpt, job)))
    assert result[202:-8] == ('<tr><td><span style="font-family:monospace;white-space:pre-wrap">| table | '
                              'row |</span></td></tr>')


def test_diff_to_htm_wdiff():
    # must add to fake headers to get what we want:
    inpt = '[-old-] {+new+}'
    job = JobBase.unserialize({'url': '', 'is_markdown': False, 'markdown_padded_tables': False, 'diff_tool': 'wdiff'})
    result = ''.join(list(HtmlReporter('', '', '', '')._diff_to_html(inpt, job)))
    assert result == '<span style="color:#cb2431;">[-old-]</span> <span style="color:green;">{+new+}</span>'


@pytest.mark.parametrize('reporter', REPORTER)
def test_reporters(reporter):
    # command_config = CommandConfig('', '', '', '', '', '', '', '', verbose=False)
    # urlwatcher = Urlwatch('', '', '', '')

    class urlwatch_config:
        class config_storage:
            config = DEFAULT_CONFIG

    report = Report(urlwatch_config)

    def build_job(name, url, old, new):
        job = JobBase.unserialize({'name': name, 'url': url})

        # Can pass in None as cache_storage, as we are not
        # going to load or save the job state for testing;
        # also no need to use it as context manager, since
        # no processing is called on the job
        job_state = JobState(None, job)

        job_state.old_data = old
        job_state.new_data = new

        return job_state

    def set_error(job_state, message):
        try:
            raise ValueError(message)
        except ValueError as e:
            job_state.exception = e
            job_state.traceback = job_state.job.format_error(e, traceback.format_exc())

        return job_state

    report.new(build_job('Newly Added', 'https://example.com/new', '', ''))
    report.changed(build_job('Something Changed', 'https://example.com/changed', """
    Unchanged Line
    Previous Content
    Another Unchanged Line
    """, """
    Unchanged Line
    Updated Content
    Another Unchanged Line
    """))
    report.unchanged(build_job('Same As Before', 'https://example.com/unchanged',
                               'Same Old, Same Old\n',
                               'Same Old, Same Old\n'))
    report.error(set_error(build_job('Error Reporting', 'https://example.com/error', '', ''), 'Oh Noes!'))

    report.finish_one(reporter)
