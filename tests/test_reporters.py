import pytest

from webchanges.reporters import HtmlReporter

htmlreporter = HtmlReporter('', '', '', '')

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
    ('+[Link](https://example.com)', '<tr style="background-color:#e6ffed"><td>'
                                     '<a style="font-family:inherit" target="_blank" href="https://example.com">'
                                     'Link</a></td></tr>'),
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
    ('       * Bullet point level 3',
     '<tr><td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;○ Bullet point level 3</td></tr>'),
    ('         * Bullet point level 4',
     '<tr><td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;○ Bullet point level 4</td></tr>'),
    (' *emphasis*', '<tr><td><em>emphasis</em></td></tr>'),
    (' _**emphasis and strong**_', '<tr><td><em><strong>emphasis and strong</strong></em></td></tr>'),
    (' **strong**', '<tr><td><strong>strong</strong></td></tr>'),
    (' **_strong and emphasis_**', '<tr><td><strong><em>strong and emphasis</em></strong></td></tr>'),
    (' ~~strikethrough~~', '<tr><td><strike>strikethrough</strike></td></tr>'),
    (' | table | row |', '<tr><td><span style="font-family: monospace">| table | row |</td></tr>'),
]


@pytest.mark.parametrize('inpt, out', DIFFTOHTMLTESTDATA)
def test_diff_to_html(inpt, out):
    # must add to fake headers to get what we want:
    inpt = '-fake head 1\n+fake head 2\n' + inpt
    result = ''.join(list(htmlreporter._diff_to_html(inpt, is_markdown=True)))
    assert result[202:-8] == out
