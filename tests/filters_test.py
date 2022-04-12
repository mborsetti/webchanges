"""Test filters based on a set of patterns."""

import importlib.util
import logging
import os
import sys
from pathlib import Path

import pytest
import yaml

from webchanges.filters import FilterBase
from webchanges.jobs import JobBase, UrlJob

logger = logging.getLogger(__name__)

bs4_is_installed = importlib.util.find_spec('bs4') is not None

# https://stackoverflow.com/questions/31469707/
if sys.version_info[0:2] == (3, 6) and sys.platform == 'win32':
    import _locale

    _locale._getdefaultlocale = lambda *args: ['en_US', 'utf8']


TESTDATA = [
    # New dict-style filter definition to test normalization/mapping but nothing more
    ([{'keep_lines_containing': None}], [('keep_lines_containing', {})]),
    ([{'keep_lines_containing': {'re': 'bla'}}], [('keep_lines_containing', {'re': 'bla'})]),
    ([{'reverse': '\n\n'}], [('reverse', {'separator': '\n\n'})]),
    (
        ['html2text', {'keep_lines_containing': 'Current.version'}, 'strip'],
        [
            ('html2text', {}),
            ('keep_lines_containing', {'text': 'Current.version'}),
            ('strip', {}),
        ],
    ),
    ([{'css': 'body'}], [('css', {'selector': 'body'})]),
    (
        [{'html2text': {'method': 'bs4', 'parser': 'html5lib'}}],
        [
            ('html2text', {'method': 'bs4', 'parser': 'html5lib'}),
        ],
    ),
]


@pytest.mark.parametrize('input, output', TESTDATA, ids=(str(d[0]) for d in TESTDATA))
def test_normalize_filter_list(input, output):
    assert list(FilterBase.normalize_filter_list(input)) == output


FILTER_TESTS = list(yaml.safe_load(Path(__file__).parent.joinpath('data/filters_test.yaml').read_text()).items())


class FakeJob(JobBase):
    def get_indexed_location(self):
        return ''


@pytest.mark.parametrize('test_name, test_data', FILTER_TESTS, ids=(d[0] for d in FILTER_TESTS))
def test_filters(test_name, test_data):
    filter = test_data['filter']
    data = test_data['data']
    expected_result = test_data['expected_result']

    result = data
    for filter_kind, subfilter in FilterBase.normalize_filter_list(filter):
        logger.info(f'filter kind: {filter_kind}, subfilter: {subfilter}')
        if filter_kind == 'html2text' and subfilter.get('method') == 'bs4' and not bs4_is_installed:
            logger.warning(f"Skipping {test_name} since 'beautifulsoup4' package is not installed")
            return
        filtercls = FilterBase.__subclasses__.get(filter_kind)
        if filtercls is None:
            raise ValueError('Unknown filter kind: {filter_kind}:{subfilter}')
        # noinspection PyTypeChecker
        result = filtercls(FakeJob(), None).filter(result, subfilter)

    logger.debug(f'Expected result:\n{expected_result}')
    logger.debug(f'Actual result:\n{result}')
    assert result == expected_result.rstrip()


def test_invalid_filter_name_raises_valueerror():
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(FilterBase.normalize_filter_list(['afilternamethatdoesnotexist']))
    assert str(pytest_wrapped_e.value) == 'Unknown filter kind: afilternamethatdoesnotexist (subfilter: {})'


def test_providing_subfilter_to_filter_without_subfilter_raises_valueerror():
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(FilterBase.normalize_filter_list([{'beautify': {'asubfilterthatdoesnotexist': True}}]))
    assert str(pytest_wrapped_e.value) == (
        "Filter beautify does not support subfilter(s): {'asubfilterthatdoesnotexist'} (supported: {'indent'})"
    )


def test_providing_unknown_subfilter_raises_valueerror():
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(
            FilterBase.normalize_filter_list([{'keep_lines_containing': {'re': 'Price: .*', 'anothersubfilter': '42'}}])
        )
    assert "Filter keep_lines_containing does not support subfilter(s): {'anothersubfilter'} (supported:" in str(
        pytest_wrapped_e.value
    )


def test_execute_inherits_environment_but_does_not_modify_it():
    # https://github.com/thp/urlwatch/issues/541

    # Set a specific value to check it doesn't overwrite the current env
    os.environ['URLWATCH_JOB_NAME'] = 'should-not-be-overwritten'

    # See if the execute process can use a variable from the outside
    os.environ['INHERITED_FROM'] = 'parent-process'
    job = UrlJob(url='test')
    if sys.platform != 'win32':
        command = 'bash -c "echo $INHERITED_FROM/$URLWATCH_JOB_NAME"'
    else:
        command = 'cmd /c echo %INHERITED_FROM%/%URLWATCH_JOB_NAME%'
    filtercls = FilterBase.__subclasses__.get('execute')
    # noinspection PyTypeChecker
    result = filtercls(job, None).filter('input-string', {'command': command})

    # Check that the inherited value and the job name are set properly
    assert result.rstrip('"') == 'parent-process/test\n'

    # Check that the outside variable wasn't overwritten by the filter
    assert os.environ['URLWATCH_JOB_NAME'] == 'should-not-be-overwritten'


def test_shellpipe_inherits_environment_but_does_not_modify_it():
    # https://github.com/thp/urlwatch/issues/541
    # if os.getenv('GITHUB_ACTIONS') and sys.version_info[0:2] == (3, 6) and sys.platform == 'linux':
    #     pytest.skip('Triggers exit code 141 in Python 3.8 on Ubuntu in GitHub Actions')
    #     return

    # Set a specific value to check it doesn't overwrite the current env
    os.environ['URLWATCH_JOB_NAME'] = 'should-not-be-overwritten'

    # See if the shellpipe process can use a variable from the outside
    os.environ['INHERITED_FROM'] = 'parent-process'
    job = UrlJob(url='test')
    if sys.platform != 'win32':
        command = 'echo $INHERITED_FROM/$URLWATCH_JOB_NAME'
    else:
        command = 'echo %INHERITED_FROM%/%URLWATCH_JOB_NAME%'
    filtercls = FilterBase.__subclasses__.get('shellpipe')
    # noinspection PyTypeChecker
    result = filtercls(job, None).filter('input-string', {'command': command})

    # Check that the inherited value and the job name are set properly
    assert result.rstrip('"') == 'parent-process/test\n'

    # Check that the outside variable wasn't overwritten by the filter
    assert os.environ['URLWATCH_JOB_NAME'] == 'should-not-be-overwritten'


def test_deprecated_filters():
    filtercls = FilterBase.__subclasses__.get('grep')
    # noinspection PyTypeChecker
    assert filtercls(FakeJob(), None).filter('a\nb', {'text': 'b'}) == 'b'

    filtercls = FilterBase.__subclasses__.get('grepi')
    # noinspection PyTypeChecker
    assert filtercls(FakeJob(), None).filter('a\nb', {'text': 'b'}) == 'a'


def test_filter_requires_bytes():
    filtercls = FilterBase.__subclasses__.get('pdf2text')
    # noinspection PyTypeChecker
    assert filtercls(FakeJob(), None).is_bytes_filter_kind('pdf2text') is True
