#!/usr/bin/env python3

"""Run by setuptools to build and distribute as a Python package wheel."""

import re
import sys

from setuptools import find_packages, setup

import webchanges as project

if sys.version_info < project.__min_python_version__:
    sys.exit(
        f'{project.__project_name__} requires Python version '
        f'{".".join(str(v) for v in project.__min_python_version__)} or newer.\n'
        f'You are running {sys.version}'
    )

with open('requirements.txt') as f:
    requirements = map(str.strip, f.readlines())

with open('README.rst') as f:
    README_rst = f.read()

SETUP = {
    'name': project.__project_name__,
    'version': project.__version__,
    'description': project.__description__.replace('\n', ' '),
    'long_description': README_rst,
    'long_description_content_type': 'text/x-rst',
    'keywords': 'webmonitoring monitoring',
    'author': re.match(r'(.*) <(.*)>', project.__author__).groups()[0],
    'author_email': re.match(r'(.*) <(.*)>', project.__author__).groups()[1],
    'url': project.__url__,
    'packages': find_packages(),
    'classifiers': [
        'Environment :: Console',
        'Topic :: Internet',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Utilities',
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: Implementation :: CPython',
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Developers',
    ],
    'license': project.__license__,
    # Below to include in sdist the files read above (see https://stackoverflow.com/questions/37753833)
    # data_files is deprecated. It does not work with wheels, so it should be avoided.
    'zip_safe': True,
    'install_requires': list(requirements),
    'entry_points': {'console_scripts': [f'{project.__project_name__}={project.__package__}.cli:main']},
    'extras_require': {
        'use_browser': ['playwright', 'psutil'],
        'beautify': ['beautifulsoup4', 'jsbeautifier', 'cssbeautifier'],
        'bs4': ['beautifulsoup4'],
        'deepdiff': ['deepdiff'],
        'jq': ['jq;os_name!="nt"'],
        'ical2text': ['vobject'],
        'matrix': ['matrix_client'],
        'ocr': ['pytesseract', 'Pillow'],
        'pdf2text': ['pdftotext'],
        'pushbullet': ['pushbullet.py'],
        'pushover': ['chump'],
        'redis': ['redis'],
        'safe_password': ['keyring'],
        'xmpp': ['aioxmpp'],
    },
    'python_requires': f'>={".".join(str(v) for v in project.__min_python_version__)}',
    'project_urls': {
        'Source Code': project.__code_url__,
        'CI': f'{project.__code_url__}actions',
        'Issues': f'{project.__code_url__}issues',
        'Changelog': f'{project.__docs_url__}en/stable/changelog.html',
        'Documentation': project.__docs_url__,
    },
}
SETUP['extras_require']['all'] = sorted(list(set(pkg for extra in SETUP['extras_require'].values() for pkg in extra)))
setup(**SETUP)

# to build manually (https://packaging.python.org/tutorials/packaging-projects/):
# $ python setup.py sdist bdist_wheel
# $ python -m twine upload --repository testpypi dist/*
