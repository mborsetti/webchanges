"""Check web content (or the output of local commands) for changes and show, and/or notify via e-mail or one of many
other supported services, if any change is detected since its prior run; the notification includes the changed URL
(or command) and a 'diff' summary. See documentation at https://webchanges.readthedocs.io/
"""

# The docstring above (__doc__) and the variables below are used in the program and for builds, including in building
# documentation with Sphinx.

__min_python_version__ = (3, 6)  # minimum version of Python required to run

__project_name__ = __package__
# Release numbering largely follows Semantic Versioning https://semver.org/spec/v2.0.0.html#semantic-versioning-200
# * MAJOR version when you make incompatible API changes,
# * MINOR version when you add functionality in a backwards compatible manner, and
# * PATCH version when you make backwards compatible bug fixes
# If unsure on increments, use pkg_resources.parse_version to parse
__version__ = '3.6.1'
__description__ = 'Check web (or commands) for changes since last run and notify'
__author__ = 'Mike Borsetti <mike@borsetti.com>'
__copyright__ = 'Copyright 2020- Mike Borsetti'
__license__ = 'MIT, BSD 3-Clause License'
__url__ = f'https://pypi.org/project/{__project_name__}/'
__docs_url__ = f'https://{__project_name__}.readthedocs.io/en/stable/'
__user_agent__ = f'{__project_name__}/{__version__} (+{__url__})'

from typing import Dict, Union


def init_data() -> Dict[str, Union[str, tuple]]:
    """Returns dict of globals, including __version__ (used in testing)

    :return: dict of globals()
    """
    return {k: v for k, v in globals().items()}
