"""Test the vendored fallback modules in webchanges._vendored.

These modules are only imported by webchanges when the corresponding optional dependency (typeguard, httpx,
packaging) is not installed, so the regular test suite never exercises them; they are tested directly here.
"""

from __future__ import annotations

from typing import Literal, TypedDict

import pytest
from typing_extensions import NotRequired

from webchanges._vendored.headers import Headers
from webchanges._vendored.packaging_version import parse
from webchanges._vendored.typeguard import TypeCheckError, check_type


class _Inner(TypedDict):
    color: bool | Literal['normal', 'bright']


class _Outer(TypedDict):
    display: _Inner
    footnote: NotRequired[str | None]


def test_typeguard_typed_dict_valid() -> None:
    """Nested TypedDicts with Literal unions (the shapes used by validate_config) pass."""
    check_type({'display': {'color': 'normal'}, 'footnote': None}, _Outer)
    check_type({'display': {'color': True}}, _Outer)


def test_typeguard_typed_dict_invalid() -> None:
    """Wrong value types, missing keys, and extra keys are rejected with TypeCheckError."""
    with pytest.raises(TypeCheckError):
        check_type({'display': {'color': 'dim'}}, _Outer)
    with pytest.raises(TypeCheckError):
        check_type({}, _Outer)
    with pytest.raises(TypeCheckError):
        check_type({'display': {'color': True}, 'surprise': 1}, _Outer)


def test_typeguard_literal_bool_int() -> None:
    """typeguard 4.6.0 fix: bool and int Literal members are matched by type first (1 == True in Python)."""
    check_type(1, Literal[True, 1])
    with pytest.raises(TypeCheckError):
        check_type(True, Literal[1, 2])
    with pytest.raises(TypeCheckError):
        check_type(1, Literal[True, False])


def test_headers() -> None:
    """The vendored httpx.Headers is case-insensitive and joins repeated keys."""
    headers = Headers({'User-Agent': 'webchanges'})
    assert headers['user-agent'] == 'webchanges'
    headers = Headers([('x-a', '1'), ('X-A', '2')])
    assert headers['x-a'] == '1, 2'


def test_packaging_version_parse() -> None:
    """The vendored packaging.version.parse orders release candidates before finals."""
    assert parse('3.37.0rc2') < parse('3.37.0')
    assert parse('3.36.1').release == (3, 36, 1)
