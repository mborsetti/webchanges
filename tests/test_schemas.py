"""Validate the jobs and configurations of the docs and of the test data against the bundled JSON Schemas.

The JSON Schemas in webchanges/_resources/ are used by editors to validate and autocomplete the jobs and configuration
files, so they must accept every valid example and reject invalid ones. test_docs_schema_code.py checks instead that the
schemas, the code and the docs list the same names.

A YAML block in the docs is validated as a job if all its keys are job directives (a fragment without ``url`` or
``command`` gets a dummy ``url``), as a configuration if they are configuration directives, or as the ``report`` section
of one if they are reporters. A block containing the word INCORRECT is an example of a mistake and must be rejected.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

from webchanges.storage import DEFAULT_CONFIG  # also registers the !env YAML tag on the SafeLoader

jsonschema = pytest.importorskip('jsonschema')

root_path = Path(__file__).resolve().parent.parent
data_path = root_path.joinpath('tests', 'data')
docs_path = root_path.joinpath('docs')
resources_path = root_path.joinpath('webchanges', '_resources')

JOBS_SCHEMA: dict[str, Any] = json.loads(resources_path.joinpath('jobs.schema.json').read_text(encoding='utf-8'))
CONFIG_SCHEMA: dict[str, Any] = json.loads(resources_path.joinpath('config.schema.json').read_text(encoding='utf-8'))
JOBS_VALIDATOR = jsonschema.validators.validator_for(JOBS_SCHEMA)(JOBS_SCHEMA)
CONFIG_VALIDATOR = jsonschema.validators.validator_for(CONFIG_SCHEMA)(CONFIG_SCHEMA)

JOB_DIRECTIVES = set(JOBS_SCHEMA['properties'])
CONFIG_DIRECTIVES = set(CONFIG_SCHEMA['properties'])
REPORTERS = set(CONFIG_SCHEMA['$defs']['_ConfigReport']['properties'])

# Docs files whose YAML blocks are not jobs or configurations
DOCS_NOT_VALIDATED = {'yaml_syntax.rst'}  # a YAML tutorial

# YAML blocks in the docs that are neither jobs nor configurations, by file and first key
DOCS_BLOCKS_NOT_VALIDATED = {
    ('jobs.rst', 'accept'),  # the default headers of url jobs
}

YAML_BLOCK_RE = re.compile(
    r'^( *)\.\. code(?:-block)?:: yaml *\n((?:\1 +:.*\n)*)\n((?:\1 +\S.*\n|[ \t]*\n)+)', re.MULTILINE
)


def docs_yaml_blocks() -> list[Any]:
    """The YAML code blocks of the docs, as pytest params of (docs file, text) with id '<file>:<line>'."""
    params = []
    for file in sorted(docs_path.glob('*.rst')):
        if file.name in DOCS_NOT_VALIDATED:
            continue
        rst = file.read_text(encoding='utf-8')
        for match in YAML_BLOCK_RE.finditer(rst):
            line = rst.count('\n', 0, match.start()) + 1
            params.append(pytest.param(file.name, textwrap.dedent(match[3]), id=f'{file.name}:{line}'))
    return params


def schema_errors(validator: Any, instance: Any) -> list[str]:
    """The validation errors, each as '<path>: <message>'."""
    return [
        f'{"/".join(map(str, error.absolute_path)) or "<root>"}: {error.message}'
        for error in validator.iter_errors(instance)
    ]


def classify(document: dict[str, Any]) -> tuple[Any, dict[str, Any]] | None:
    """The validator for a YAML document of the docs and the instance to validate, or None if it is neither."""
    keys = {key for key in document if not key.startswith('_')}  # keys starting with '_' are remarks
    if keys and keys <= JOB_DIRECTIVES:
        if not keys & {'url', 'command'}:
            document = {'url': 'https://example.com/', **document}
        return JOBS_VALIDATOR, document
    if keys <= CONFIG_DIRECTIVES:
        return CONFIG_VALIDATOR, document
    if keys <= REPORTERS:
        return CONFIG_VALIDATOR, {'report': document}
    return None


@pytest.mark.parametrize('schema', [JOBS_SCHEMA, CONFIG_SCHEMA], ids=['jobs', 'config'])
def test_schema_is_valid(schema: dict[str, Any]) -> None:
    """The schema is itself a valid JSON Schema of the draft it declares."""
    jsonschema.validators.validator_for(schema).check_schema(schema)


def test_default_config_is_valid() -> None:
    assert schema_errors(CONFIG_VALIDATOR, DEFAULT_CONFIG) == []


def test_config_data_is_valid() -> None:
    """A configuration file missing directives (here, one written by an older version) is valid: defaults fill them."""
    config = yaml.safe_load(data_path.joinpath('config.yaml').read_text(encoding='utf-8'))
    assert DEFAULT_CONFIG.keys() - config.keys()  # make sure it is still a partial configuration
    assert schema_errors(CONFIG_VALIDATOR, config) == []


@pytest.mark.parametrize(
    'file', [*sorted(data_path.glob('jobs*.yaml')), data_path.joinpath('docs_hooks_jobs.yaml')], ids=lambda f: f.name
)
def test_jobs_data_is_valid(file: Path) -> None:
    jobs = [job for job in yaml.safe_load_all(file.read_text(encoding='utf-8')) if job]
    assert jobs
    for i, job in enumerate(jobs):
        assert schema_errors(JOBS_VALIDATOR, job) == [], f'job {i}'


def test_filters_data_is_valid() -> None:
    """The filters of tests/data/filters_testdata.yaml are valid."""
    cases = yaml.safe_load(data_path.joinpath('filters_testdata.yaml').read_text(encoding='utf-8'))
    errors = {
        name: errors
        for name, case in cases.items()
        if (errors := schema_errors(JOBS_VALIDATOR, {'url': 'https://example.com/', 'filters': case['filters']}))
    }
    assert errors == {}


@pytest.mark.parametrize(('file', 'text'), docs_yaml_blocks())
def test_docs_yaml_block(file: str, text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each job or configuration in a YAML block of the docs is valid, unless the block says it is INCORRECT."""
    for name in re.findall(r'\$\{(\w+)', text):  # the environment variables of !env tags
        monkeypatch.setenv(name, 'dummy')
    documents = [document for document in yaml.safe_load_all(text) if document is not None]
    assert documents, 'empty YAML block'
    incorrect = 'INCORRECT' in text
    for document in documents:
        assert isinstance(document, dict), f'not a mapping: {document!r}'
        if (file, next(iter(document))) in DOCS_BLOCKS_NOT_VALIDATED:
            continue
        classified = classify(document)
        assert classified, (
            f'neither a job nor a configuration (if intended, add it to DOCS_BLOCKS_NOT_VALIDATED): {text}'
        )
        errors = schema_errors(*classified)
        if incorrect:
            assert errors, 'an INCORRECT example is accepted by the schema'
        else:
            assert errors == []


@pytest.mark.parametrize(
    'job',
    [
        {'url': 'https://example.com/', 'filters': [{'html2text': {'strip_tags': True}}]},  # a method as sub-directive
        {'url': 'https://example.com/', 'filters': [{'html2text': {'pad_table': True}}]},  # misspelled sub-directive
        {'url': 'https://example.com/', 'filters': ['html2txt']},  # misspelled filter
        {'url': 'https://example.com/', 'max_try': 2},  # misspelled directive
        {'url': 'https://example.com/', 'max_tries': '2'},  # wrong type
        {'name': 'no url or command'},
        {'url': 'https://example.com/', 'command': 'echo both'},
        {'url': 'https://example.com/', 'differ': {'command': 'diff', 'is_html': True}},  # 'name' omitted wrongly
    ],
    ids=[
        'method-as-key',
        'filter-subdirective-typo',
        'filter-typo',
        'directive-typo',
        'wrong-type',
        'no-url-or-command',
        'url-and-command',
        'differ-without-name',
    ],
)
def test_invalid_job_rejected(job: dict[str, Any]) -> None:
    assert schema_errors(JOBS_VALIDATOR, job)


@pytest.mark.parametrize(
    'config',
    [
        {'_note': 'a remark', 'report': {'stdout': {'_note': 'a remark', 'enabled': True}}},
        {'display': {'new': False}},  # a section missing directives
        {'display': {'empty-diff': True}},  # deprecated but still accepted
        {'report': {'github_issue': {'milestone': 1}}},
        {'report': {'stdout': [{'enabled': True, 'tags': 'a'}, {'enabled': True, 'tags': ['b', 'c']}]}},
        {'report': {'my_hooks_reporter': {'anything': True}}},  # a reporter defined in hooks.py
    ],
    ids=['remarks', 'partial-section', 'deprecated-empty-diff', 'integer-milestone', 'reporter-list', 'hooks-reporter'],
)
def test_valid_config_accepted(config: dict[str, Any]) -> None:
    assert schema_errors(CONFIG_VALIDATOR, config) == []


@pytest.mark.parametrize(
    'config',
    [
        {'dispaly': {'new': True}},  # misspelled section
        {'display': {'new': 'yes'}},  # wrong type
        {'report': {'stdout': {'colour': True}}},  # misspelled reporter sub-directive
        {'report': {'telegram': {'enabled': 'true'}}},  # wrong type of a reporter sub-directive
    ],
    ids=['section-typo', 'wrong-type', 'reporter-subdirective-typo', 'reporter-wrong-type'],
)
def test_invalid_config_rejected(config: dict[str, Any]) -> None:
    assert schema_errors(CONFIG_VALIDATOR, config)
