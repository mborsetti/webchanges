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


def test_filter_requires_bytes():
    filtercls = FilterBase.__subclasses__.get('pdf2text')
    # noinspection PyTypeChecker
    assert filtercls(FakeJob(), None).is_bytes_filter_kind('pdf2text') is True


def test_deprecated_filters():
    filtercls = FilterBase.__subclasses__.get('html2text')
    with pytest.warns(DeprecationWarning) as w:
        # noinspection PyTypeChecker
        assert filtercls(FakeJob(), None).filter('<div>a</div>', {'method': 'pyhtml2text'}) == 'a\n'
    assert len(w) == 1
    assert w[0].message.args[0] == (
        "Filter html2text's method 'pyhtml2text' is deprecated: remove method as it's now the filter's default ()"
    )

    filtercls = FilterBase.__subclasses__.get('html2text')
    with pytest.warns(DeprecationWarning) as w:
        # noinspection PyTypeChecker
        assert filtercls(FakeJob(), None).filter('<div>a</div>', {'method': 're'}) == 'a'
    assert len(w) == 1
    assert w[0].message.args[0] == ("Filter html2text's method 're' is deprecated: replace with 'strip_tags' ()")

    filtercls = FilterBase.__subclasses__.get('grep')
    with pytest.warns(DeprecationWarning) as w:
        # noinspection PyTypeChecker
        assert filtercls(FakeJob(), None).filter('a\nb', {'text': 'b'}) == 'b'
    assert len(w) == 1
    assert w[0].message.args[0] == (
        "The 'grep' filter is deprecated; replace with 'keep_lines_containing' + 're' subfilter ()"
    )

    filtercls = FilterBase.__subclasses__.get('grepi')
    with pytest.warns(DeprecationWarning) as w:
        # noinspection PyTypeChecker
        assert filtercls(FakeJob(), None).filter('a\nb', {'text': 'b'}) == 'a'
    assert len(w) == 1
    assert w[0].message.args[0] == (
        "The 'grepi' filter is deprecated; replace with 'delete_lines_containing' + 're' subfilter ()"
    )

    filtercls = FilterBase.__subclasses__.get('striplines')
    with pytest.warns(DeprecationWarning) as w:
        # noinspection PyTypeChecker
        assert filtercls(FakeJob(), None).filter('a  \nb', {}) == 'a\nb'
    assert len(w) == 1
    assert w[0].message.args[0] == (
        "The 'strip_each_line' filter is deprecated; replace with 'strip' and sub-directive 'splitlines: true' ()"
    )


def test_filter_exceptions():
    filtercls = FilterBase.__subclasses__.get('html2text')
    with pytest.raises(NotImplementedError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('<div>a</div>', {'method': 'lynx'})
    assert e.value.args[0] == (
        "Filter html2text's method 'lynx' is no longer supported; for similar results, use the filter without "
        'specifying a method ()'
    )

    filtercls = FilterBase.__subclasses__.get('html2text')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('<div>a</div>', {'method': 'blabla'})
    assert e.value.args[0] == ("Unknown method blabla for filter 'html2text' ()")

    filtercls = FilterBase.__subclasses__.get('pdf2text')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('<div>a</div>', {})
    assert e.value.args[0] == ("The 'html2text: pdf2text' filter needs bytes input (is it the first filter?) ()")

    for filter in ('keep_lines_containing', 'delete_lines_containing'):
        filtercls = FilterBase.__subclasses__.get(filter)
        with pytest.raises(TypeError) as e:
            # noinspection PyTypeChecker
            filtercls(FakeJob(), None).filter('a', {'text': 2})
        assert e.value.args[0] == (f"The '{filter}' filter requires a string but you provided a int ()")

        filtercls = FilterBase.__subclasses__.get(filter)
        with pytest.raises(TypeError) as e:
            # noinspection PyTypeChecker
            filtercls(FakeJob(), None).filter('a', {'re': 2})
        assert e.value.args[0] == (f"The '{filter}' filter requires a string but you provided a int ()")

        filtercls = FilterBase.__subclasses__.get(filter)
        with pytest.raises(ValueError) as e:
            # noinspection PyTypeChecker
            filtercls(FakeJob(), None).filter('a', {})
        assert e.value.args[0] == (f"The '{filter}' filter requires a 'text' or 're' sub-directive ()")

    filtercls = FilterBase.__subclasses__.get('strip')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {'splitlines': True, 'side': 'whatever'})
    assert e.value.args[0] == ("The 'strip' filter's 'side' sub-directive can only be 'right' or 'left' ()")

    filtercls = FilterBase.__subclasses__.get('strip')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {'side': 'whatever'})
    assert e.value.args[0] == ("The 'strip' filter's 'side' sub-directive can only be 'right' or 'left' ()")

    filtercls = FilterBase.__subclasses__.get('element-by-id')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 'element-by-id' filter needs an id for filtering ()")

    filtercls = FilterBase.__subclasses__.get('element-by-class')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 'element-by-class' filter needs a class for filtering ()")

    filtercls = FilterBase.__subclasses__.get('element-by-style')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 'element-by-style' filter needs a style for filtering ()")

    filtercls = FilterBase.__subclasses__.get('element-by-tag')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 'element-by-tag' filter needs a tag for filtering ()")

    filtercls = FilterBase.__subclasses__.get('xpath')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {'method': 'any'})
    assert e.value.args[0] == ("The 'xpath' filter's method must be 'html' or 'xml', got 'any' ()")

    filtercls = FilterBase.__subclasses__.get('xpath')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 'xpath' filter needs an XPath expression for filtering ()")

    filtercls = FilterBase.__subclasses__.get('xpath')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {'path': 'any', 'namespaces': 'whatever'})
    assert e.value.args[0] == ("The 'xpath' filter's namespace prefixes are only supported with 'method: xml' ()")

    filtercls = FilterBase.__subclasses__.get('re.sub')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 're.sub' filter needs a pattern ()")

    filtercls = FilterBase.__subclasses__.get('execute')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 'execute' filter needs a command ()")

    filtercls = FilterBase.__subclasses__.get('ocr')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 'ocr' filter needs bytes input (is it the first filter?) ()")

    filtercls = FilterBase.__subclasses__.get('jq')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('a', {})
    assert e.value.args[0] == ("The 'jq' filter needs a query ()")

    filtercls = FilterBase.__subclasses__.get('jq')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(FakeJob(), None).filter('{""""""}', {'query': 'any'})
    assert e.value.args[0] == ("The 'jq' filter needs valid JSON ()")
