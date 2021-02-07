import pytest

from webchanges.util import chunk_string, linkify

TESTDATA = [
    # Numbering for just one item doesn't add the numbers
    (('Hello World', 100, True, ['Hello World'])),
    (('This Is A Long Message', 5, False, ['This', 'Is A', 'Long', 'Messa', 'ge'])),
    (('This Is A Very Long Message That Should Be Numbered', 20, True,
     # 12345678901234567890
      ['This Is A Very (1/4)',
       'Long Message (2/4)',
       'That Should Be (3/4)',
       'Numbered (4/4)'])),
    (('Averylongwordthathas\nnewlineseparationgoingon', 15, True,
      # 123456789012345
      ['Averylong (1/6)',
       'wordthath (2/6)',
       'as (3/6)',
       'newlinese (4/6)',
       'parationg (5/6)',
       'oingon (6/6)'])),
]


@pytest.mark.parametrize('string, length, numbering, output', TESTDATA)
def test_chunkstring(string, length, numbering, output):
    assert list(chunk_string(string, length, numbering=numbering)) == output


def test_linkify():
    assert linkify('Test www.example.com') == 'Test <a href="http://www.example.com">www.example.com</a>'
