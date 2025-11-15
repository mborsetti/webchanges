"""Test filters based on a set of patterns."""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from webchanges.filters import FilterBase, Html2TextFilter
from webchanges.handler import JobState
from webchanges.jobs import JobBase, UrlJob
from webchanges.storage import SsdbDirStorage
from webchanges.util import mark_to_html

logger = logging.getLogger(__name__)

bs4_is_installed = importlib.util.find_spec('bs4') is not None
# skip_mac_issue = pytest.mark.skipif(
#     sys.platform == 'darwin' and sys.version_info == (3, 12),
#     reason='Crashing',
# )

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


@pytest.mark.parametrize(('in_spec', 'out_spec'), TESTDATA, ids=(str(d[0]) for d in TESTDATA))  # type: ignore[misc]
def test_normalize_filter_list(
    in_spec: str | list[str | dict[str, Any]],
    out_spec: list[tuple[str, dict[str, Any]]],
) -> None:
    assert list(FilterBase.normalize_filter_list(in_spec)) == out_spec


FILTER_TESTS = list(yaml.safe_load(Path(__file__).parent.joinpath('data/filters_testdata.yaml').read_text()).items())
job_state = JobState(SsdbDirStorage(''), JobBase.unserialize({'url': 'https://testfakejob.com/'}))


class FakeJob(JobBase):
    url = 'https://testfakejob.com/'

    def get_indexed_location(self) -> str:
        return ''


@pytest.mark.parametrize(('test_name', 'test_data'), FILTER_TESTS, ids=(d[0] for d in FILTER_TESTS))  # type: ignore[misc]
def test_filters(test_name: str, test_data: dict[str, str]) -> None:
    """Runs the tests defined in data/filters_testdata.yaml."""
    filter_spec = test_data['filter']
    data = test_data['data']
    expected_result = test_data['expected_result']
    filter_result = ''

    result = data
    for filter_kind, subfilter in FilterBase.normalize_filter_list(filter_spec):
        logger.info(f'filter kind: {filter_kind}, subfilter: {subfilter}')
        if filter_kind == 'html2text' and subfilter.get('method') == 'bs4' and not bs4_is_installed:
            pytest.skip("'beautifulsoup4' not installed")
        filtercls = FilterBase.__subclasses__.get(filter_kind)
        if filtercls is None:
            raise ValueError('Unknown filter kind: {filter_kind}:{subfilter}')
        # noinspection PyTypeChecker
        filter_result = filtercls(job_state).filter(result, '', subfilter)

    logger.debug(f'Expected result:\n{expected_result}')
    logger.debug(f'Actual result:\n{filter_result}')
    assert filter_result[0] == expected_result


def test_invalid_filter_name_raises_valueerror() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(FilterBase.normalize_filter_list(['afilternamethatdoesnotexist']))
    assert str(pytest_wrapped_e.value) == (
        'Job None: Unknown filter kind: afilternamethatdoesnotexist (subfilter or filter directive(s): {}).'
    )


def test_providing_subfilter_to_filter_without_subfilter_raises_valueerror() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(FilterBase.normalize_filter_list([{'beautify': {'asubfilterthatdoesnotexist': True}}]))
    err_msg = str(pytest_wrapped_e.value)
    assert err_msg.startswith(
        'Job None: Filter beautify does not support subfilter or filter directive(s) asubfilterthatdoesnotexist. Only '
    )
    assert err_msg.endswith(('indent, absolute_links are supported.', 'absolute_links, indent are supported.'))


def test_providing_unknown_subfilter_raises_valueerror() -> None:
    with pytest.raises(ValueError) as pytest_wrapped_e:
        list(
            FilterBase.normalize_filter_list([{'keep_lines_containing': {'re': 'Price: .*', 'anothersubfilter': '42'}}])
        )
    err_msg = str(pytest_wrapped_e.value)
    assert err_msg.startswith(
        'Job None: Filter keep_lines_containing does not support subfilter or filter directive(s) anothersubfilter. '
        'Only '
    )
    assert err_msg.endswith(('re, text are supported.', 'text, re are supported.'))


# @pytest.mark.skipif(sys.platform == 'darwin', reason='Often leads to Process completed with exit code 141 on macOS')
#   # type: ignore[misc]
def test_execute_inherits_environment_but_does_not_modify_it() -> None:
    # https://github.com/thp/urlwatch/issues/541

    # Set a specific value to check it doesn't overwrite the current env
    os.environ['URLWATCH_JOB_NAME'] = 'should-not-be-overwritten'

    # See if the execute process can use a variable from the outside
    os.environ['INHERITED_FROM'] = 'parent-process'
    job_state.job = UrlJob(url='test')
    if os.name != 'nt':
        command = 'bash -c "cat; echo $INHERITED_FROM/$URLWATCH_JOB_NAME"'
    else:
        command = 'cmd /c echo %INHERITED_FROM%/%URLWATCH_JOB_NAME%'
    filtercls = FilterBase.__subclasses__.get('execute')
    # noinspection PyTypeChecker
    data, _ = filtercls(job_state).filter(  # type: ignore[misc]
        'input-string',
        'text/plain',
        {'command': command},
    )

    # Check that the inherited value and the job name are set properly
    if os.name != 'nt':
        assert str(data).rstrip('"') == 'input-stringparent-process/test\n'
    else:
        assert str(data).rstrip('"') == 'parent-process/test'

    # Check that the outside variable wasn't overwritten by the filter
    assert os.environ['URLWATCH_JOB_NAME'] == 'should-not-be-overwritten'


# @pytest.mark.skipif(sys.platform == 'darwin', reason='Often leads to Process completed with exit code 141 on macOS')
#   # type: ignore[misc]
def test_shellpipe_inherits_environment_but_does_not_modify_it() -> None:
    # https://github.com/thp/urlwatch/issues/541
    # if os.getenv('GITHUB_ACTIONS') and sys.version_info[0:2] == (3, 6) and sys.platform == 'linux':
    #     pytest.skip('Triggers exit code 141 in Python 3.8 on Ubuntu in GitHub Actions')
    #     return

    # Set a specific value to check it doesn't overwrite the current env
    os.environ['URLWATCH_JOB_NAME'] = 'should-not-be-overwritten'

    # See if the shellpipe process can use a variable from the outside
    os.environ['INHERITED_FROM'] = 'parent-process'
    job_state.job = UrlJob(url='test')
    if os.name != 'nt':
        command = 'cat; echo $INHERITED_FROM/$URLWATCH_JOB_NAME'
    else:
        command = 'echo %INHERITED_FROM%/%URLWATCH_JOB_NAME%'
    filtercls = FilterBase.__subclasses__.get('shellpipe')
    # noinspection PyTypeChecker
    data, _ = filtercls(job_state).filter(  # type: ignore[misc]
        'input-string',
        'text/plain',
        {'command': command},
    )

    # Check that the inherited value and the job name are set properly
    if os.name != 'nt':
        assert str(data).rstrip('"') == 'input-stringparent-process/test\n'
    else:
        assert str(data).rstrip('"') == 'parent-process/test'

    # Check that the outside variable wasn't overwritten by the filter
    assert os.environ['URLWATCH_JOB_NAME'] == 'should-not-be-overwritten'


def test_filter_requires_bytes() -> None:
    filtercls = FilterBase.__subclasses__.get('pdf2text')
    # noinspection PyTypeChecker
    assert filtercls(job_state).is_bytes_filter_kind('pdf2text') is True  # type: ignore[misc]


def test_deprecated_filters() -> None:
    def _warning_message(warning: Warning | str) -> str:
        if isinstance(warning, Warning):
            return warning.args[0]  # type: ignore[no-any-return]
        return warning

    filtercls = FilterBase.__subclasses__.get('html2text')
    with pytest.warns(DeprecationWarning) as w:
        data, _ = filtercls(job_state).filter(  # type: ignore[misc]
            '<div>a</div>',
            'text/plain',
            {'method': 'pyhtml2text'},
        )
    assert data == 'a'
    assert len(w) == 1
    expected = (
        "Filter html2text's method 'pyhtml2text' is deprecated: remove method as it's now the filter's default (Job 0: "
    )
    assert _warning_message(w[0].message)[: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('html2text')
    with pytest.warns(DeprecationWarning) as w:
        data, _ = filtercls(job_state).filter('<div>a</div>', 'text/plain', {'method': 're'})  # type: ignore[misc]
    assert data == 'a'
    assert len(w) == 1
    expected = "Filter html2text's method 're' is deprecated: replace with 'strip_tags' (Job 0: "
    assert _warning_message(w[0].message)[: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('grep')
    with pytest.warns(DeprecationWarning) as w:
        data, _ = filtercls(job_state).filter('a\nb', 'text/plain', {'text': 'b'})  # type: ignore[misc]
    assert data == 'b'
    assert len(w) == 1
    expected = "The 'grep' filter is deprecated; replace with 'keep_lines_containing' + 're' subfilter (Job 0: "
    assert _warning_message(w[0].message)[: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('grepi')
    with pytest.warns(DeprecationWarning) as w:
        # noinspection PyTypeChecker
        data, _ = filtercls(job_state).filter('a\nb', 'text/plain', {'text': 'b'})  # type: ignore[misc]
    assert data == 'a'
    assert len(w) == 1
    expected = "The 'grepi' filter is deprecated; replace with 'delete_lines_containing' + 're' subfilter (Job 0: "
    assert _warning_message(w[0].message)[: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('striplines')
    with pytest.warns(DeprecationWarning) as w:
        data, _ = filtercls(job_state).filter('a  \nb', 'text/plain', {})  # type: ignore[misc]
    assert data == 'a\nb'
    assert len(w) == 1
    expected = (
        "The 'strip_each_line' filter is deprecated; replace with 'strip' and sub-directive 'splitlines: true' (Job "
    )
    assert _warning_message(w[0].message)[: len(expected)] == expected


def test_filter_exceptions() -> None:
    filtercls = FilterBase.__subclasses__.get('html2text')
    e: pytest.ExceptionInfo  # mypy
    with pytest.raises(NotImplementedError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('<div>a</div>', 'text/plain', {'method': 'lynx'})  # type: ignore[misc]
    expected = (
        "Filter html2text's method 'lynx' is no longer supported; for similar results, use the filter without "
        'specifying a method. (Job 0:'
    )
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('html2text')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('<div>a</div>', 'text/plain', {'method': 'blabla'})  # type: ignore[misc]
    expected = "Unknown method blabla for filter 'html2text'. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('pdf2text')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('<div>a</div>', 'text/plain', {})  # type: ignore[misc]
    expected = "The 'pdf2text' filter needs bytes input (is it the first filter?). (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    for filter_kind in ('keep_lines_containing', 'delete_lines_containing'):
        filtercls = FilterBase.__subclasses__.get(filter_kind)
        with pytest.raises(TypeError) as e:
            # noinspection PyTypeChecker
            filtercls(job_state).filter('a', 'text/plain', {'text': 2})  # type: ignore[misc]
        expected = f"The '{filter_kind}' filter requires a string but you provided a int. (Job 0: "
        assert e.value.args[0][: len(expected)] == expected

        filtercls = FilterBase.__subclasses__.get(filter_kind)
        with pytest.raises(TypeError) as e:
            # noinspection PyTypeChecker
            filtercls(job_state).filter('a', 'text/plain', {'re': 2})  # type: ignore[misc]
        expected = f"The '{filter_kind}' filter requires a string but you provided a int. (Job 0: "
        assert e.value.args[0][: len(expected)] == expected

        filtercls = FilterBase.__subclasses__.get(filter_kind)
        with pytest.raises(ValueError) as e:
            # noinspection PyTypeChecker
            filtercls(job_state).filter('a', 'text/plain', {})  # type: ignore[misc]
        expected = f"The '{filter_kind}' filter requires a 'text' or 're' sub-directive. (Job 0: "
        assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('strip')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/plain', {'splitlines': True, 'side': 'whatever'})  # type: ignore[misc]
    expected = "The 'strip' filter's 'side' sub-directive can only be 'right' or 'left'. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('strip')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/plain', {'side': 'whatever'})  # type: ignore[misc]
    expected = "The 'strip' filter's 'side' sub-directive can only be 'right' or 'left'. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('element-by-id')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/html', {})  # type: ignore[misc]
    expected = "The 'element-by-id' filter needs an id for filtering. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('element-by-class')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/html', {})  # type: ignore[misc]
    expected = "The 'element-by-class' filter needs a class for filtering. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('element-by-style')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/html', {})  # type: ignore[misc]
    expected = "The 'element-by-style' filter needs a style for filtering. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('element-by-tag')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/html', {})  # type: ignore[misc]
    expected = "The 'element-by-tag' filter needs a tag for filtering. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('xpath')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/html', {'method': 'any'})  # type: ignore[misc]
    expected = "The 'xpath' filter's method must be 'html' or 'xml', got 'any'. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('xpath')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/html', {})  # type: ignore[misc]
    expected = "The 'xpath' filter needs an XPath expression for filtering. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('xpath')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/html', {'path': 'any', 'namespaces': 'whatever'})  # type: ignore[misc]
    expected = "The 'xpath' filter's namespace prefixes are only supported with 'method: xml'. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('re.sub')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/plain', {})  # type: ignore[misc]
    expected = "The 're.sub' filter needs a pattern. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('execute')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/plain', {})  # type: ignore[misc]
    expected = "The 'execute' filter needs a command. (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    filtercls = FilterBase.__subclasses__.get('ocr')
    with pytest.raises(ValueError) as e:
        # noinspection PyTypeChecker
        filtercls(job_state).filter('a', 'text/plain', {})  # type: ignore[misc]
    expected = "The 'ocr' filter needs bytes input (is it the first filter?). (Job 0: "
    assert e.value.args[0][: len(expected)] == expected

    if importlib.util.find_spec('jq') is not None:
        filtercls = FilterBase.__subclasses__.get('jq')
        with pytest.raises(ValueError) as e:
            # noinspection PyTypeChecker
            filtercls(job_state).filter('a', 'text/json', {})  # type: ignore[misc]
        expected = "The 'jq' filter needs a query. (Job 0: "
        assert e.value.args[0][: len(expected)] == expected

        filtercls = FilterBase.__subclasses__.get('jq')
        with pytest.raises(ValueError) as e:
            # noinspection PyTypeChecker
            filtercls(job_state).filter('{""""""}', 'text/json', {'query': 'any'})  # type: ignore[misc]
        expected = "The 'jq' filter needs valid JSON. (Job 0: "
        assert e.value.args[0][: len(expected)] == expected
    else:
        pytest.xfail('jq not installed')


# @pytest.mark.xfail('Not working due to an html2text bug')
def test_html2text_roundtrip() -> None:
    html = '1 | <a href="https://www.example.com">1</a><br><strong>2 |<a href="https://www.example.com">2</a></strong>'
    data, _ = Html2TextFilter(job_state).filter(html, 'text/plain', {})  # type: ignore[arg-type]
    html2_lines = [
        mark_to_html(line).replace('style="font-family:inherit" rel="noopener" target="_blank" ', '')
        for line in str(data).splitlines()
    ]
    html2 = '<br>'.join(html2_lines)
    assert html2 == html
