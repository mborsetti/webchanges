"""Test the jobs embedded in the documentation's filters.rst file by running them against the data in the
data/doc_filer_testadata.yaml file."""

import importlib.util
import logging
import os

import docutils.frontend
import docutils.nodes
import docutils.parsers.rst
import docutils.utils
import html2text
import pytest
import yaml

from webchanges.filters import FilterBase
from webchanges.jobs import UrlJob

logger = logging.getLogger(__name__)

root = os.path.join(os.path.dirname(__file__), '../webchanges', '..')
here = os.path.dirname(__file__)

beautifulsoup_is_installed = importlib.util.find_spec('beautifulsoup') is not None
jq_is_installed = importlib.util.find_spec('jq') is not None
pdftotext_is_installed = importlib.util.find_spec('pdftotext') is not None
pytesseract_is_installed = importlib.util.find_spec('pytesseract') is not None
vobject_is_installed = importlib.util.find_spec('vobject') is not None


# https://stackoverflow.com/a/48719723/1047040
def parse_rst(text):
    """Parse the rst document"""
    parser = docutils.parsers.rst.Parser()
    components = (docutils.parsers.rst.Parser,)
    settings = docutils.frontend.OptionParser(components=components).get_default_values()
    document = docutils.utils.new_document('<rst-doc>', settings=settings)
    parser.parse(text, document)
    return document


# https://stackoverflow.com/a/48719723/1047040
class YAMLCodeBlockVisitor(docutils.nodes.NodeVisitor):
    """Used in loading yaml code block from rst file"""
    def __init__(self, doc):
        super().__init__(doc)
        self.jobs = []

    def visit_literal_block(self, node):
        if 'yaml' in node.attributes['classes']:
            self.jobs.append(yaml.safe_load(node.astext()))

    def unknown_visit(self, node: docutils.nodes.Node) -> None:
        ...


def load_filter_doc_urls():
    """Load YAML code blocks from rst file"""
    doc = parse_rst(open(os.path.join(root, 'docs/filters.rst')).read())
    visitor = YAMLCodeBlockVisitor(doc)
    doc.walk(visitor)

    # collect job URLs (ignore commands for now)
    jobs = {job['url']: job for job in visitor.jobs if 'url' in job}

    # Make sure all URLs are unique
    assert len(jobs) == len([job for job in visitor.jobs if 'url' in job])

    return jobs


def load_filter_testdata():
    with open(os.path.join(here, 'data/doc_filter_testdata.yaml')) as f:
        yaml_data = f.read()
    return yaml.safe_load(yaml_data)


FILTER_DOC_URLS = load_filter_doc_urls()
testdata = load_filter_testdata()


@pytest.mark.parametrize('url, job', FILTER_DOC_URLS.items())
def test_url(url, job):
    """Test the yaml code in docs/filters.rst against the source and expected results contained
    in tests/data/doc_filter_testdata.yaml using 'url' as the key)"""
    # only tests shellpipe in linux; test pdf2text and ocr only if packages are installed (they require
    # OS-specific installations beyond pip)
    if url != 'https://example.com/html2text.html' or html2text.__version__ <= (2020, 1, 16):
        # TODO update output and remove this when html2text > 2020.1.16 (https://github.com/Alir3z4/html2text/pull/339)
        d = testdata[url]
        if 'filename' in d:
            input_data = open(os.path.join(here, 'data', d['filename']), 'rb').read()
        else:
            input_data = d['input']

        for filter_kind, subfilter in FilterBase.normalize_filter_list(job['filter']):
            # skip if package is not installed
            if (filter_kind == 'beautify' or (filter_kind == 'html2text' and subfilter.get('method') == 'bs4')
                    and not beautifulsoup_is_installed):
                logger.warning(f"Skipping {url} since 'beautifulsoup' package is not installed")
                return
            if filter_kind == 'ical2text' and not vobject_is_installed:
                logger.warning(f"Skipping {url} since 'vobject' package is not installed")
                return
            elif filter_kind == 'ocr' and not pytesseract_is_installed:
                logger.warning(f"Skipping {url} since 'pytesseract' package is not installed")
                return
            elif filter_kind == 'jq' and not jq_is_installed:
                logger.warning(f"Skipping {url} since 'jq' package is not installed")
                return
            elif filter_kind == 'pdf2text' and not pdftotext_is_installed:
                logger.warning(f"Skipping {url} since 'pdftotext' package is not installed")
                return
            filtercls = FilterBase.__subclasses__[filter_kind]
            input_data = filtercls(UrlJob(url=url), None).filter(input_data, subfilter)
            if filter_kind in ('pdf2text', 'shellpipe'):  # fix for macOS or OS-specific end of line
                input_data = input_data.rstrip()
            # TODO: FilterBase.process(cls, filter_kind, subfilter, state, data):

        expected_output_data = d['output']
        assert input_data == expected_output_data
