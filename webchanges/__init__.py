"""Check web (or commands) for changes since last run and notify

`webchanges` checks web content (or the output of local commands) for changes and shows or notifies you via e-mail or
one of many other supported services if any change is detected. The notification includes the changed URL (or command)
and a 'diff' summary of the changes. You can fine-tune what to track by using filters.
"""

# The docstring above (__doc__) and the variables below are used in the program and for builds, including
# documentation (Sphynx autodoc)

__project_name__ = __package__
# Release numbering largely follows Semantic Versioning https://semver.org/spec/v2.0.0.html#semantic-versioning-200
# * MAJOR version when you make incompatible API changes,
# * MINOR version when you add functionality in a backwards compatible manner, and
# * PATCH version when you make backwards compatible bug fixes
# If unsure on increments, use pkg_resources.parse_version to parse
__version__ = '3.2.5.rc1'
__min_python_version__ = (3, 6)  # minimum version of Python required to run
__author__ = 'Mike Borsetti <mike@borsetti.com>'
__copyright__ = 'Copyright 2020- Mike Borsetti'
__license__ = 'MIT, BSD 3-Clause License'
__url__ = f'https://pypi.org/project/{__project_name__}/'
__user_agent__ = f'{__project_name__}/{__version__} (+{__url__})'

from typing import Any, Dict


def init_data() -> Dict[str, Any]:
    """Returns dict of globals, including __version__ (used in testing)

    :return: dict of globals()
    """
    return {k: v for k, v in globals().items()}
