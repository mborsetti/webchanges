"""Test utility functions."""

import pytest

from webchanges.util import chunk_string, linkify

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


def test_linkify():
    assert linkify('Test www.example.com') == 'Test <a href="http://www.example.com">www.example.com</a>'
    assert (
        linkify('Test www.example.com/thisisalonglink', shorten=True)
        == 'Test <a href="http://www.example.com/thisisalonglink" '
        'title=http://www.example.com/thisisalonglink>www.example.com/thisisal...</a>'
    )
