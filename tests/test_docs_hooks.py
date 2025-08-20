"""Test the jobs embedded in the documentation's hooks.rst file by running them against the data in the
data/docs_hooks_testadata.yaml file."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import docutils.core
import docutils.nodes
import docutils.parsers.rst
import pytest
import yaml
from flake8.api import legacy as flake8

from webchanges.cli import load_hooks
from webchanges.filters import FilterBase
from webchanges.handler import JobState
from webchanges.jobs import JobBase
from webchanges.storage import YamlJobsStorage

here = Path(__file__).parent
data_path = here.joinpath('data')
docs_path = here.parent.joinpath('docs')

if sys.version_info < (3, 12):
    pytest.skip('hooks.py is written for Python 3.13', allow_module_level=True)


# # https://stackoverflow.com/a/48719723/1047040
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
    """
    Parse the rst document.

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

    document = docutils.core.publish_doctree(
        source=text,
        parser=docutils.parsers.rst.Parser(),
        settings_overrides=settings_overrides,
    )
    return document  # type: ignore[no-any-return]


# https://stackoverflow.com/a/48719723/1047040
class YAMLCodeBlockVisitor(docutils.nodes.NodeVisitor):
    """Used in loading yaml code block from rst file."""

    def __init__(self, document: docutils.nodes.document) -> None:
        """Initialise the visitor."""
        super().__init__(document)
        self.code: list[str] = []

    def visit_literal_block(self, node: docutils.nodes.literal_block) -> None:
        """Extract python code blocks."""
        if 'python' in node.attributes['classes']:
            self.code.append(node.astext())
        elif node.rawsource.startswith('.. code-block:: python'):
            self.code.append(node.rawsource[22:].strip())

    def unknown_visit(self, node: docutils.nodes.Node) -> None:
        """Pass."""
        pass


def load_hooks_from_doc() -> str:
    """Load YAML code blocks from rst file."""
    doc = parse_rst(docs_path.joinpath('hooks.rst').read_text())
    visitor = YAMLCodeBlockVisitor(doc)
    doc.walk(visitor)
    return visitor.code[0]


def load_hooks_testdata() -> dict[str, Any]:
    yaml_data = Path(data_path.joinpath('docs_hooks_testdata.yaml')).read_text()
    return yaml.safe_load(yaml_data)  # type: ignore[no-any-return]


def load_hooks_jobs() -> list[JobBase]:
    jobs_file = data_path.joinpath('docs_hooks_jobs.yaml')
    jobs_storage = YamlJobsStorage([jobs_file])
    return jobs_storage.load()


HOOKS_DOC_JOBS = load_hooks_jobs()
testdata = load_hooks_testdata()

HOOKS = load_hooks_from_doc()
spec = importlib.util.spec_from_loader('hooks', loader=None)
if spec:
    hooks = importlib.util.module_from_spec(spec)
    sys.modules['hooks'] = hooks
    exec(HOOKS, hooks.__dict__)  # noqa: S102 Use of exec detected.
else:
    raise ImportError('hooks not loaded')
# TODO Ensure that this is the version loaded during testing.


def test_load_hooks(caplog: pytest.LogCaptureFixture) -> None:
    """Check the cli.py load of hooks.com"""
    load_hooks(data_path.joinpath('hooks.does_not_exist.py'))
    assert caplog.text == '' or 'not imported because' in caplog.text


def test_flake8_on_hooks_rst(tmp_path: Path) -> None:
    """Check that the hooks.py example code in hooks.rst passes flake8."""
    hooks_path = tmp_path.joinpath('hooks.py')
    hooks_path.write_text(HOOKS)

    # https://flake8.pycqa.org/en/latest/user/python-api.html
    style_guide = flake8.get_style_guide(
        extend_ignore=[
            'W292',  # No newline at end of file
            'W503',  # Line break before binary operator [conflicts with W504]
        ],
        max_line_length=120,
    )
    report = style_guide.input_file(str(hooks_path))
    assert report.get_statistics('') == [], 'Flake8 found violations in hooks.py'


@pytest.mark.parametrize('job', HOOKS_DOC_JOBS, ids=(v.url for v in HOOKS_DOC_JOBS))  # type: ignore[misc]
def test_url(job: JobBase) -> None:
    d = testdata[job.url]
    data = d['input']
    # noinspection PyTypeChecker
    with JobState(None, job) as job_state:  # type: ignore[arg-type]
        data, mime_type = FilterBase.auto_process(job_state, data, '')
        for filter_kind, subfilter in FilterBase.normalize_filter_list(job_state.job.filters):
            data, mime_type = FilterBase.process(filter_kind, subfilter, job_state, data, '')

        expected_output_data = d['output']
        assert data == expected_output_data
