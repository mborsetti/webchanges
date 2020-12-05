"""webchanges checks webpages for changes

webchanges checks web content (or the output of local commands) for changes and shows or notifies you via e-mail or
one of many other supported services if any change is detected; the notification includes the changed URL (or command)
and a 'diff' summary of the changes.
"""

# The docstring above (__doc__) and the variables below are used in the program and for builds, including
# documentation (Sphynx autodoc)

__project_name__ = __package__
# Release numbering largely follows Semantic Versioning https://semver.org/spec/v2.0.0.html#semantic-versioning-200
# If unsure on increments, use pkg_resources.parse_version to parse
__version__ = '3.0.1'
__min_python_version__ = (3, 6)
__author__ = 'Mike Borsetti <mike@borsetti.com>'
__copyright__ = 'Copyright 2020- Mike Borsetti'
__license__ = 'MIT, BSD 3-Clause License'
__url__ = f'https://github.com/mborsetti/{__project_name__}'
__user_agent__ = f'{__project_name__}/{__version__} (+{__url__})'


def init_data():
    return {k: v for k, v in globals().items()}
