import os
import subprocess
import sys


def test_build_docs():
    """Test that Sphinx does not have any warnings or errors"""
    # readthedocs.io uses Python 3.8 so only run continuous integration in 3.8
    if not os.environ.get('CI') or (sys.version_info.major == 3 and sys.version_info.minor == 8):
        run = subprocess.run('sphinx-build -M html ../docs ../docs/build'.split(), capture_output=True)
        stderr = run.stderr.decode()
        assert not stderr
        stdout=run.stdout.decode()
        assert not any(x in stdout for x in ('WARNING', 'ERROR'))
