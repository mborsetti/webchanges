"""Test the jobs embedded in the documentation's filters.rst file by running them against the data in the
data/docs_filter_testadata.yaml file.
"""

from __future__ import annotations

import importlib.util
from collections import defaultdict
from pathlib import Path

import docutils.core
import docutils.nodes
import docutils.parsers.rst
import pytest
import yaml

from webchanges.filters import FilterBase
from webchanges.handler import JobState
from webchanges.jobs import JobBase

# import sys


# if sys.platform == 'win32':
#     sys.path.insert(1, str(Path(__file__).parent.parent))


# https://stackoverflow.com/questions/712791
# try:
#     import simplejson as jsonlib
# except ImportError:
#     import json as jsonlib  # type: ignore[no-redef]

here = Path(__file__).parent
data_path = here.joinpath('data')
docs_path = here.parent.joinpath('docs')

bs4_is_installed = importlib.util.find_spec('bs4') is not None
cssbeautifier_is_installed = importlib.util.find_spec('cssbeautifier') is not None
html5lib_is_installed = importlib.util.find_spec('html5lib') is not None
jq_is_installed = importlib.util.find_spec('jq') is not None
pdftotext_is_installed = importlib.util.find_spec('pdftotext') is not None
pytesseract_is_installed = importlib.util.find_spec('pytesseract') is not None
vobject_is_installed = importlib.util.find_spec('vobject') is not None


# # https://stackoverflow.com/a/48719723/1047040
# # https://stackoverflow.com/a/75996218/1047040
# def _old_parse_rst(text: str) -> docutils.nodes.document:
#     """Parse the rst document"""
#     parser = docutils.parsers.rst.Parser()
#     settings = docutils.frontend.get_default_settings(docutils.parsers.rst.Parser)
#     # suppress messages of unknown directive types etc. from sphinx (e.g. "versionchanged")
#     settings.update(
#         {'report_level': 4}, docutils.frontend.OptionParser(components=(docutils.parsers.rst.Parser,))
#     )  # (critical): Only show critical messages, which indicate a fatal error that prevents completing processing.
#     document = docutils.utils.new_document('<rst-doc>', settings=settings)
#     parser.parse(text, document)
#     return document


def parse_rst(text: str) -> docutils.nodes.document:
    """Parse the rst document.

    This function uses docutils.core.publish_doctree to parse the text, which handles the setup of the parser,
    settings, and document internally, avoiding deprecated components.
    """
    # Settings overrides are passed directly to the publish_doctree function.
    # 'report_level': 4 corresponds to 'critical'.
    settings_overrides = {
        'report_level': 4,
        'halt_level': 4,  # Prevents exiting on errors
        'warning_stream': None,  # Suppress warnings from being printed to stderr
    }

    return docutils.core.publish_doctree(  # type: ignore[no-any-return]
        source=text,
        parser=docutils.parsers.rst.Parser(),
        settings_overrides=settings_overrides,
    )


# https://stackoverflow.com/a/48719723/1047040
class YAMLCodeBlockVisitor(docutils.nodes.NodeVisitor):
    """Used in loading yaml code block from rst file."""

    def visit_literal_block(self, node: docutils.nodes.literal_block) -> None:
        self.jobs = []
        if 'yaml' in node.attributes['classes']:
            self.jobs.append(yaml.safe_load(node.astext()))
        elif node.rawsource.startswith('.. code-block:: yaml'):
            yaml_block = node.rawsource[20:].strip()
            self.jobs.append(yaml.safe_load(yaml_block))

    def unknown_visit(self, node: docutils.nodes.Node) -> None:
        pass


def load_filter_doc_jobs() -> list[JobBase]:
    """Load YAML code blocks from rst file."""
    filter_file = docs_path.joinpath('filters.rst')
    doc = parse_rst(filter_file.read_text())
    visitor = YAMLCodeBlockVisitor(doc)
    doc.walk(visitor)

    jobs = []
    jobs_by_url = defaultdict(list)
    for i, job_data in enumerate(job for job in visitor.jobs if 'url' in job):
        if job_data is not None:
            job_data['index_number'] = i + 1
            job = JobBase.unserialize(job_data)
            jobs.append(job)
            jobs_by_url[job.url].append(job)

    conflicting_jobs = [url_jobs[0].get_location() for url_jobs in jobs_by_url.values() if len(url_jobs) != 1]

    # Make sure all URLs are unique
    assert not conflicting_jobs, f'Found conflicting job name in {filter_file}'

    return jobs


def load_filter_testdata() -> dict[str, dict[str, str]]:
    yaml_data = data_path.joinpath('docs_filters_testdata.yaml').read_text()
    return yaml.safe_load(yaml_data)  # type: ignore[no-any-return]


FILTER_DOC_JOBS = load_filter_doc_jobs()
testdata = load_filter_testdata()


@pytest.mark.parametrize('job', FILTER_DOC_JOBS, ids=(v.url for v in FILTER_DOC_JOBS))  # type: ignore[misc]
def test_jobs(job: JobBase) -> None:
    """Test the yaml code in docs/filters.rst against the source and expected results contained
    in tests/data/docs_filters_testdata.yaml using 'url' as the key.
    """
    # Skips certain filters if packages are not installed (e.g. pdf2text and ocr as they require OS-specific
    # installations beyond pip)
    d = testdata[job.url]
    if 'filename' in d:
        data: bytes | str = data_path.joinpath(d['filename']).read_bytes()
    else:
        data = d['input']
    expected_output_data = d['output']

    # noinspection PyTypeChecker
    with JobState(None, job) as job_state:  # type: ignore[arg-type]
        for filter_kind, subfilter in FilterBase.normalize_filter_list(job_state.job.filters):
            if (
                filter_kind == 'beautify' or (filter_kind == 'html2text' and subfilter.get('method') == 'bs4')
            ) and not bs4_is_installed:
                pytest.skip("'beautifulsoup4' not installed")
            if (
                subfilter.get('method') == 'bs4' and subfilter.get('parser') == 'html5lib'
            ) and not html5lib_is_installed:
                pytest.skip("'html5lib' not installed")
            if filter_kind == 'ascii85':
                data = b'\xc9\x89\xa3'
            elif filter_kind == 'base64':
                data = b'i\xb7\x1d'
            elif filter_kind == 'ical2text' and not vobject_is_installed:
                pytest.skip("'vobject' not installed")
            elif filter_kind == 'ocr' and not pytesseract_is_installed:
                pytest.skip("'pytesseract' not installed")
            elif filter_kind == 'jq' and not jq_is_installed:
                pytest.skip("'jq' not installed")
            elif filter_kind == 'pdf2text' and not pdftotext_is_installed:
                pytest.skip("'pdftotext' not installed")
            elif filter_kind == 'beautify' and not cssbeautifier_is_installed:
                pytest.skip("'cssbeautifier' not installed")

            data, _ = FilterBase.process(filter_kind, subfilter, job_state, data, '')
            if filter_kind in {'pdf2text', 'shellpipe'}:  # fix for macOS or OS-specific end of line
                data = data.rstrip()

        if job.url == 'https://example.net/execute.html':
            assert data.splitlines()[:-1] == expected_output_data.splitlines()[:-1]
            # assert jsonlib.loads(data.splitlines()[-1][17:-1]) == jsonlib.loads(
            #     expected_output_data.splitlines()[-1][17:-1]
            # )
        else:
            assert data == expected_output_data
