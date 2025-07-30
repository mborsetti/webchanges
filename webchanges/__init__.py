"""Checks web content, including images, to detect any changes since the prior run. If any are found,
it summarizes (including with Gen AI) what changed ('diff') and displays it and/or sends it via email and/or other
supported services. Can check the output of local commands as well.
"""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

# The docstring above (__doc__) and the variables below are used in the program and for builds, including in building
# documentation with Sphinx.

# Older Python versions are supported for 3 years after being obsoleted by a new major release.

from __future__ import annotations

__min_python_version__ = (3, 10)  # minimum version of Python required to run; supported until fall 2025


__project_name__ = str(__package__)
# Version numbering is PEP440-compliant https://www.python.org/dev/peps/pep-0440/
# Release numbering largely follows Semantic Versioning https://semver.org/spec/v2.0.0.html#semantic-versioning-200
# * MAJOR version when you make incompatible API changes,
# * MINOR version when you add functionality in a backwards compatible manner, and
# * MICRO or PATCH version when you make backwards compatible bug fixes. We no longer use '0'
# If unsure on increments, use pkg_resources.parse_version to parse
__version__ = '3.31.0'
__description__ = (
    'Check web (or command output) for changes since last run and notify.\n'
    '\n'
    'Anonymously alerts you of web changes.'
)
__author__ = 'Mike Borsetti <mike@borsetti.com>'
__copyright__ = 'Copyright 2020- Mike Borsetti'
__license__ = 'MIT, BSD 3-Clause License'
__url__ = f'https://pypi.org/project/{__project_name__}/'
__code_url__ = f'https://github.com/mborsetti/{__project_name__}/'
__docs_url__ = f'https://{__project_name__}.readthedocs.io/'
__user_agent__ = f'{__project_name__}/{__version__} (+{__url__})'


def init_data() -> dict[str, str | tuple]:
    """Returns dict of globals (used in testing).

    :returns: dict of globals()
    """
    return {k: v for k, v in globals().items()}


if __name__ == '__main__':
    # allow running from __init__.py
    from webchanges.cli import main

    main()
