"""Test that all __init__ variables have been defined."""

from webchanges import init_data

INITDATAKEYS = (
    '__name__',
    '__doc__',
    '__package__',
    '__loader__',
    '__spec__',
    '__path__',
    '__file__',
    '__cached__',
    '__builtins__',
    '__min_python_version__',
    '__project_name__',
    '__version__',
    '__description__',
    '__author__',
    '__copyright__',
    '__license__',
    '__code_url__',
    '__docs_url__',
    '__url__',
    '__user_agent__',
)


def test_init_data():
    assert set(init_data().keys()).issuperset(INITDATAKEYS)
    assert sorted([key for key in init_data().keys() if key[:2] == '__']) == sorted(INITDATAKEYS)
