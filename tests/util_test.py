"""Test utility functions."""

import pytest

from webchanges.util import chunk_string, get_new_version_number, linkify

CHUNK_TEST_DATA = [
    # Numbering for just one item doesn't add the numbers
    ('Hello World', 100, True, ['Hello World']),
    ('This Is A Long Message', 5, False, ['This', 'Is A', 'Long ', 'Messa', 'ge']),
    (
        (
            'This Is A Very Long Message That Should Be Numbered',
            20,
            True,
            # 12345678901234567890
            ['This Is A Very (1/4)', 'Long Message (2/4)', 'That Should Be (3/4)', 'Numbered (4/4)'],
        )
    ),
    (
        (
            'Averylongwordthathas\nnewlineseparationgoingon',
            15,
            True,
            # 123456789012345
            ['Averylong (1/5)', 'wordthath (2/5)', 'as\nnewlin (3/5)', 'eseparati (4/5)', 'ongoingon (5/5)'],
        )
    ),
]


@pytest.mark.parametrize('string, length, numbering, output', CHUNK_TEST_DATA)
def test_chunkstring(string, length, numbering, output):
    assert list(chunk_string(string, length, numbering=numbering)) == output


def test_chunk_tooshort_1(caplog):
    chunk_string(
        'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore '
        'magna aliqua.',
        9,
        numbering=True,
    )
    message = caplog.text
    assert 'Not enough space to chunkify string with line numbering (1)' in message


def test_linkify():
    assert linkify('Test www.example.com') == 'Test <a href="https://www.example.com">www.example.com</a>'
    assert (
        linkify(
            'Test https://www.example.com/thisisalonglink',
            shorten=True,
            require_protocol=True,
            extra_params='rel="nofollow"',
        )
        == 'Test <a href="https://www.example.com/thisisalonglink" rel="nofollow" '
        'title=https://www.example.com/thisisalonglink>https://www.example.com/thisisal...</a>'
    )
    assert linkify('ftp://test', require_protocol=True) == 'ftp://test'
    assert (
        linkify('ftp://test', require_protocol=True, permitted_protocols=('ftp',))
        == '<a href="ftp://test">ftp://test</a>'
    )

    def extra_p(x):
        return ' rel="nofollow"'

    assert (
        linkify('www.test.com', extra_params=extra_p)
        == '<a href="https://www.test.com" rel="nofollow">www.test.com</a>'
    )
    assert (
        linkify('www.5678901234567890123.com/&amp;', shorten=True)
        == '<a href="https://www.5678901234567890123.com/">www.5678901234567890123.com/</a>&amp;amp;'
    )
    assert (
        linkify('www.56789012345678901234567.com/&amp;&copy;', shorten=True)
        == '<a href="https://www.56789012345678901234567.com/">www.56789012345678901234567.com/</a>&amp;amp;&amp;copy;'
    )


def test_get_new_version_number():
    version = get_new_version_number(timeout=1)
    assert not version  # this version should be higher than the one in PyPi!
