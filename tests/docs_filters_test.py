"""Test the jobs embedded in the documentation's filters.rst file by running them against the data in the
data/doc_filter_testadata.yaml file."""

import importlib.util
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import docutils.frontend
import docutils.nodes
import docutils.parsers.rst
import docutils.utils
import html2text
import pytest
import yaml

from webchanges.filters import FilterBase
from webchanges.handler import JobState
from webchanges.jobs import JobBase

logger = logging.getLogger(__name__)

here = Path(__file__).parent
docs_path = here.joinpath('..').resolve().joinpath('docs')

bs4_is_installed = importlib.util.find_spec('bs4') is not None
cssbeautifier_is_installed = importlib.util.find_spec('cssbeautifier') is not None
jq_is_installed = importlib.util.find_spec('jq') is not None
pdftotext_is_installed = importlib.util.find_spec('pdftotext') is not None
pytesseract_is_installed = importlib.util.find_spec('pytesseract') is not None
vobject_is_installed = importlib.util.find_spec('vobject') is not None


# https://stackoverflow.com/a/48719723/1047040
def parse_rst(text: str) -> docutils.nodes.document:
    """Parse the rst document"""
    parser = docutils.parsers.rst.Parser()
    components = (docutils.parsers.rst.Parser,)
    settings = docutils.frontend.OptionParser(components=components).get_default_values()
    document = docutils.utils.new_document('<rst-doc>', settings=settings)
    parser.parse(text, document)
    return document


# https://stackoverflow.com/a/48719723/1047040
class YAMLCodeBlockVisitor(docutils.nodes.NodeVisitor):
    """Used in loading yaml code block from rst file."""

    jobs: List[dict] = []

    def visit_literal_block(self, node: docutils.nodes.reference) -> None:
        if 'yaml' in node.attributes['classes']:
            self.jobs.append(yaml.safe_load(node.astext()))
        elif node.rawsource.startswith('.. code-block:: yaml'):
            yaml_block = node.rawsource[20:].strip()
            self.jobs.append(yaml.safe_load(yaml_block))

    def unknown_visit(self, node: docutils.nodes.Node) -> None:
        ...


def load_filter_doc_jobs() -> List[JobBase]:
    """Load YAML code blocks from rst file."""
    doc = parse_rst(open(docs_path.joinpath('filters.rst')).read())
    visitor = YAMLCodeBlockVisitor(doc)
    doc.walk(visitor)

    jobs = []
    jobs_by_guid = defaultdict(list)
    for i, job_data in enumerate(job for job in visitor.jobs if 'url' in job):
        if job_data is not None:
            job_data['index_number'] = i + 1
            job = JobBase.unserialize(job_data)
            jobs.append(job)
            jobs_by_guid[job.get_guid()].append(job)

    conflicting_jobs = []
    for guid, guid_jobs in jobs_by_guid.items():
        if len(guid_jobs) != 1:
            conflicting_jobs.append(guid_jobs[0].get_location())

    # Make sure all URLs are unique
    assert not conflicting_jobs

    return jobs


def load_filter_testdata() -> Dict[str, Any]:
    yaml_data = Path(here.joinpath('data').joinpath('docs_filters_testdata.yaml')).read_text()
    return yaml.safe_load(yaml_data)


FILTER_DOC_JOBS = load_filter_doc_jobs()
testdata = load_filter_testdata()


@pytest.mark.parametrize('job', FILTER_DOC_JOBS, ids=(v.url for v in FILTER_DOC_JOBS))
def test_filter_doc_jobs(job):
    """Test the yaml code in docs/filters.rst against the source and expected results contained
    in tests/data/docs_filters_testdata.yaml using 'url' as the key."""
    # Skips certain filters if packages are not installed (e.g. pdf2text and ocr as they require OS-specific
    # installations beyond pip)
    if job.url != 'https://example.com/html2text.html' or html2text.__version__ <= (2020, 1, 16):
        # TODO when html2text > 2020.1.16 update output and remove if (https://github.com/Alir3z4/html2text/pull/339)
        d = testdata[job.url]
        if 'filename' in d:
            data = here.joinpath('data').joinpath(d['filename']).read_bytes()
        else:
            data = d['input']
        # noinspection PyTypeChecker
        with JobState(None, job) as job_state:
            for filter_kind, subfilter in FilterBase.normalize_filter_list(job_state.job.filter):
                # skip if package is not installed
                if (
                    filter_kind == 'beautify' or filter_kind == 'html2text' and subfilter.get('method') == 'bs4'
                ) and not bs4_is_installed:
                    logger.warning(f"Skipping {job.url} since 'beautifulsoup4' package is not installed")
                    return
                if filter_kind == 'ical2text' and not vobject_is_installed:
                    logger.warning(f"Skipping {job.url} since 'vobject' package is not installed")
                    return
                elif filter_kind == 'ocr' and not pytesseract_is_installed:
                    logger.warning(f"Skipping {job.url} since 'pytesseract' package is not installed")
                    return
                elif filter_kind == 'jq' and not jq_is_installed:
                    logger.warning(f"Skipping {job.url} since 'jq' package is not installed")
                    return
                elif filter_kind == 'pdf2text' and not pdftotext_is_installed:
                    logger.warning(f"Skipping {job.url} since 'pdftotext' package is not installed")
                    return
                elif filter_kind == 'beautify' and not cssbeautifier_is_installed:
                    logger.warning(f"Skipping {job.url} since 'cssbeautifier' package is not installed")
                    return
                data = FilterBase.process(filter_kind, subfilter, job_state, data)
                if filter_kind in ('pdf2text', 'shellpipe'):  # fix for macOS or OS-specific end of line
                    data = data.rstrip()

            expected_output_data = d['output']
            assert data == expected_output_data

    else:
        logger.warning("Skipping https://example.com/html2text.html since 'html2text' > (2020, 1, 16)")
