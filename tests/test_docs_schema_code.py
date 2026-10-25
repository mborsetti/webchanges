"""Check that the code, the JSON Schemas in webchanges/_resources/ (used by editors to validate and autocomplete the
jobs and configuration files) and the documentation in docs/ describe the same filters, job directives and
configuration directives.

A name in the schema but not in the code must be marked ``"deprecated": true`` in the schema (a renamed directive that
the code maps to its new name); a deprecated filter or job directive needs no documentation.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from webchanges.filters import FilterBase
from webchanges.jobs import JobBase
from webchanges.reporters import ReporterBase
from webchanges.storage import DEFAULT_CONFIG

root_path = Path(__file__).resolve().parent.parent
resources_path = root_path.joinpath('webchanges', '_resources')
docs_path = root_path.joinpath('docs')

JOBS_SCHEMA: dict[str, Any] = json.loads(resources_path.joinpath('jobs.schema.json').read_text(encoding='utf-8'))
CONFIG_SCHEMA: dict[str, Any] = json.loads(resources_path.joinpath('config.schema.json').read_text(encoding='utf-8'))
SCHEMA_FILTERS: dict[str, Any] = JOBS_SCHEMA['definitions']['filterItemObject']['properties']

# Job directives set by webchanges itself, not by the user
INTERNAL_JOB_DIRECTIVES = {'index_number'}

# Filter sub-directives that are documented differently from the '* ``name``' bullet of the others, by filter
FILTER_DOCS_EXCEPTIONS: dict[str, set[str]] = {
    'html2text': {'parser'},  # a sub-directive of the 'bs4' method, documented under it
    'shellpipe': {'sudo'},  # a bullet of a warning about running commands with sudo, not a sub-directive
}


def schema_alternatives(node: dict[str, Any]) -> list[dict[str, Any]]:
    """The alternative forms of a schema node (e.g. a filter's shorthand and its object form)."""
    return node.get('oneOf') or node.get('anyOf') or [node]


def schema_properties(node: dict[str, Any]) -> set[str]:
    """The names of the properties of the object form(s) of a schema node."""
    return {name for alt in schema_alternatives(node) for name in alt.get('properties', {})}


def rst_sections(text: str) -> dict[str, str]:
    """Maps each '.. _label:' of an rst document to its text, up to the next label; consecutive labels (e.g. those of
    the filters sharing a section) all map to the text that follows the last one."""
    parts = re.split(r'^\.\. _([\w.…-]+):\s*$', text, flags=re.MULTILINE)
    sections: dict[str, str] = {}
    stacked: list[str] = []
    for i in range(1, len(parts) - 1, 2):
        stacked.append(parts[i])
        if parts[i + 1].strip():
            sections.update(dict.fromkeys(stacked, parts[i + 1]))
            stacked.clear()
    return sections


def rst_bullets(section: str) -> set[str]:
    """The names documented in a section as '* ``name``' bullets (the format of the sub-directives' lists)."""
    return set(re.findall(r'^\s*\* ``([\w.-]+)``', section, flags=re.MULTILINE))


@cache
def docs_sections(name: str) -> dict[str, str]:
    return rst_sections(docs_path.joinpath(name).read_text(encoding='utf-8'))


@cache
def docs_labels() -> set[str]:
    return {label for file in docs_path.glob('*.rst') for label in docs_sections(file.name)}


def code_filters() -> dict[str, type]:
    """The built-in filters (excluding any defined by a hooks file loaded by another test)."""
    return {
        kind: cls
        for kind, cls in FilterBase.__subclasses__.items()
        if kind and cls.__module__.startswith('webchanges.')
    }


def code_subfilters(cls: type) -> set[str]:
    return set(getattr(cls, '__supported_subfilters__', None) or {})


def code_job_directives() -> set[str]:
    """The directives of the built-in job classes (excluding any defined by a hooks file loaded by another test)."""
    return {
        directive
        for cls in JobBase.__subclasses__.values()
        if cls.__module__.startswith('webchanges.')
        for directive in (*cls.__required__, *cls.__optional__)
    } - INTERNAL_JOB_DIRECTIVES


def flatten_config(config: dict[str, Any], prefix: str = '') -> set[str]:
    """The dotted paths of all the keys of the configuration, excluding '_'-prefixed remarks."""
    paths: set[str] = set()
    for key, value in config.items():
        if key.startswith('_'):
            continue
        paths.add(f'{prefix}{key}')
        if isinstance(value, dict):
            paths |= flatten_config(value, f'{prefix}{key}.')
    return paths


def flatten_config_schema(node: dict[str, Any], prefix: str = '') -> tuple[set[str], set[str]]:
    """The dotted paths of all the properties of the configuration schema, and the subset marked deprecated."""
    paths: set[str] = set()
    deprecated: set[str] = set()
    for alt in [node, *node.get('oneOf', []), *node.get('anyOf', [])]:
        if '$ref' in alt:
            alt = CONFIG_SCHEMA['$defs'][alt['$ref'].rsplit('/', 1)[-1]]
        if isinstance(items := alt.get('items'), dict):  # a reporter configured with a list of configurations
            sub_paths, sub_deprecated = flatten_config_schema(items, prefix)
            paths |= sub_paths
            deprecated |= sub_deprecated
        for key, value in alt.get('properties', {}).items():
            if key == 'tags' or key.startswith('_'):
                # 'tags' is accepted by every reporter but, having no default, is absent from DEFAULT_CONFIG; a
                # '_'-prefixed key is a remark
                continue
            paths.add(f'{prefix}{key}')
            if value.get('deprecated'):
                deprecated.add(f'{prefix}{key}')
            sub_paths, sub_deprecated = flatten_config_schema(value, f'{prefix}{key}.')
            paths |= sub_paths
            deprecated |= sub_deprecated
    return paths, deprecated


# ---------------------------------------------------------------- filters


def test_filters_in_schema() -> None:
    """Every filter has a schema definition, and every schema definition is a filter."""
    assert set(code_filters()) == set(SCHEMA_FILTERS)


def test_filter_names_in_schema_enum_exist() -> None:
    """The filters that the schema accepts as a plain name exist."""
    enum = next(alt['enum'] for alt in JOBS_SCHEMA['definitions']['filterItem']['oneOf'] if 'enum' in alt)
    assert set(enum) - set(code_filters()) == set()


@pytest.mark.parametrize('kind', sorted(code_filters()))
def test_filter_subdirectives_in_schema(kind: str) -> None:
    """The schema lists the same sub-directives as the code ('<any>' in the code allows any sub-directive)."""
    code = code_subfilters(code_filters()[kind])
    schema = schema_properties(SCHEMA_FILTERS.get(kind, {}))
    if '<any>' in code:
        assert code - {'<any>'} - schema == set()
    else:
        assert code == schema


@pytest.mark.parametrize('kind', sorted(code_filters()))
def test_filter_documented(kind: str) -> None:
    """A filter not deprecated in the schema has a section in filters.rst, listing its sub-directives (a section shared
    by several filters lists those of all of them)."""
    if SCHEMA_FILTERS.get(kind, {}).get('deprecated'):
        pytest.skip('deprecated filter')
    sections = docs_sections('filters.rst')
    assert kind in sections, f"No '.. _{kind}:' section in docs/filters.rst"
    filters = code_filters()
    code = code_subfilters(filters[kind]) - {'<any>'}
    sharing = {other for other in filters if sections.get(other) == sections[kind]}
    allowed = set().union(*(code_subfilters(filters[other]) for other in sharing))
    docs = rst_bullets(sections[kind]) - FILTER_DOCS_EXCEPTIONS.get(kind, set())
    assert code - docs == set(), 'not documented'
    assert docs - allowed == set(), 'documented, but not in the code'


# ---------------------------------------------------------------- job directives


def test_job_directives_in_schema() -> None:
    """Every job directive is in the schema; the schema's other ones are deprecated names mapped by the code."""
    code = code_job_directives()
    schema = JOBS_SCHEMA['properties']
    assert code - set(schema) == set()
    assert {name for name in set(schema) - code if not schema[name].get('deprecated')} == set()


@pytest.mark.parametrize('directive', sorted(code_job_directives()))
def test_job_directive_documented(directive: str) -> None:
    """A job directive not deprecated in the schema has a '.. _<directive>:' label in the documentation."""
    if JOBS_SCHEMA['properties'].get(directive, {}).get('deprecated'):
        pytest.skip('deprecated directive')
    assert directive in docs_labels()


# ---------------------------------------------------------------- configuration


def test_config_directives_in_schema() -> None:
    """Every configuration directive is in the schema; the schema's other ones are deprecated."""
    code = flatten_config(DEFAULT_CONFIG)  # ty:ignore[invalid-argument-type]
    schema, deprecated = flatten_config_schema(CONFIG_SCHEMA)
    assert code - schema == set()
    assert schema - code - deprecated == set()


@pytest.mark.parametrize('kind', sorted(k for k, v in DEFAULT_CONFIG['report'].items() if isinstance(v, dict)))
def test_reporter_documented(kind: str) -> None:
    """Each sub-directive of a reporter appears in its section of reporters.rst (or, for a report type,
    reports.rst)."""
    assert kind in ReporterBase.__subclasses__
    sections = {**docs_sections('reports.rst'), **docs_sections('reporters.rst')}
    assert kind in sections, f"No '.. _{kind}:' section in docs/reporters.rst or docs/reports.rst"
    section = sections[kind]
    undocumented = {
        key
        for key in DEFAULT_CONFIG['report'][kind]  # ty:ignore[invalid-key]
        if key != 'enabled' and f'``{key}``' not in section and not re.search(rf'^\s*{key}:', section, re.MULTILINE)
    }
    assert undocumented == set()
