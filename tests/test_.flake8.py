import os
from glob import glob

from flake8.api import legacy as flake8


def test_flake8():
    """Test that we conform to PEP-8."""
    style_guide = flake8.get_style_guide(ignore=['A', 'W503'])
    py_files = [y for x in os.walk(os.path.abspath('../webchanges')) for y in glob(os.path.join(x[0], '*.py'))]
    report = style_guide.check_files(py_files)
    assert report.get_statistics('E') == [], 'Flake8 found violations'
