"""Test that all __init__ variables have been defined."""

from __future__ import annotations

import sys

from webchanges import init_data

INITDATAKEYS = {
    '__name__',
    '__doc__',
    '__package__',
    '__loader__',
    '__spec__',
    '__path__',
    '__file__',
    # '__init__',
    '__builtins__',
    '__min_python_version__',
    '__project_name__',
    '__version__',
    '__description__',
    '__author__',
    '__copyright__',
    '__license__',
    '__url__',
    '__code_url__',
    '__docs_url__',
    '__user_agent__',
}
if sys.version_info < (3, 15):
    # Python 3.15 no longer sets a module's __cached__ (deprecated since 3.13)
    INITDATAKEYS.add('__cached__')


def test_init_data() -> None:
    assert {key for key in init_data() if key[:2] == '__'}.issuperset(INITDATAKEYS)
    assert sorted([key for key in init_data() if key[:2] == '__']) == sorted(INITDATAKEYS)
