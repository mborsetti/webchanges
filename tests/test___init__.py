from webchanges.__init__ import init_data

INITDATAKEYS = (
    '__name__', '__doc__', '__package__', '__loader__', '__spec__', '__file__', '__cached__', '__builtins__',
    '__project_name__', '__version__', '__min_python_version__', '__author__', '__copyright__', '__license__',
    '__url__', '__user_agent__', 'init_data')


def test_init_data():
    assert set(init_data().keys()).issuperset(INITDATAKEYS)
