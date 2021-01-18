import os
import subprocess
import sys


def test_build_docs():
    """Test that Sphinx build does not have any warnings or errors"""
    # readthedocs.io uses Python 3.8 so only run continuous integration in 3.8
    if not os.environ.get('CI'):
        run = subprocess.run('sphinx-build -M html ../docs ../docs/_build'.split(), capture_output=True, text=True)
    elif sys.version_info[:2] == (3, 8):
        run = subprocess.run('sphinx-build -M html docs docs/_build'.split(), capture_output=True, text=True)
    else:
        return

    assert not run.stderr
    assert not any(x in run.stdout for x in ('WARNING', 'ERROR'))
