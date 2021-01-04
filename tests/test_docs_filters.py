"""Reads code in the filters.rst (help) documents and runs tests against the data in the data/doc_filer_testadata.yaml
file"""

import os

import docutils.frontend
import docutils.nodes
import docutils.parsers.rst
import docutils.utils
import pkg_resources
import pytest
import yaml

from webchanges.filters import FilterBase
from webchanges.jobs import UrlJob

root = os.path.join(os.path.dirname(__file__), '../webchanges', '..')
here = os.path.dirname(__file__)

installed_packages = [pkg.key for pkg in pkg_resources.working_set]


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
    if ((os.name != 'nt' or 'shellpipe' not in job['filter'][0])
            and ('pdftotext' in installed_packages or 'pdf2text' not in job['filter'][0])
            and ('pytesseract' in installed_packages or 'ocr' not in job['filter'][0])):
        d = testdata[url]
        if 'filename' in d:
            input_data = open(os.path.join(here, 'data', d['filename']), 'rb').read()
        else:
            input_data = d['input']

        for filter_kind, subfilter in FilterBase.normalize_filter_list(job['filter']):
            filtercls = FilterBase.__subclasses__[filter_kind]
            input_data = filtercls(UrlJob(url=url), None).filter(input_data, subfilter)
            # TODO: FilterBase.process(cls, filter_kind, subfilter, state, data):

        expected_output_data = d['output']
        assert input_data == expected_output_data
