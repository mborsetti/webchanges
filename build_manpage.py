#!/usr/bin/env python3

# Build manpages
# Legacy for apt-get type of packaging

import os
from textwrap import wrap

from build_manpages.manpage import Manpage

import webchanges as project
from webchanges.config import CommandConfig

MANPAGE_ADD_TEXT = (f"""
.TP
.B $XDG_CONFIG_HOME/{project.__project_name__}/jobs.yaml
A list of URLs, commands and other jobs to watch

.TP
.B $XDG_CONFIG_HOME/{project.__project_name__}/config.py
Options for the program, including methods of notification

.TP
.B $XDG_CONFIG_HOME/{project.__project_name__}/hooks.py
A Python module that can implement new job types, filters and reporters

.TP
.B $XDG_CACHE_HOME/{project.__project_name__}/cache.db
A SQLite 3 database that contains the state history of jobs (for diffing)

.SH AUTHOR
{project.__author__}

.SH WEBSITE
{project.__url__}
""")


def build_manpage():
    parser = CommandConfig('', '', '', '', '', '', '', '', verbose=False).parse_args()
    parser.prog = f"{project.__project_name__} {project.__version__}"
    parser.usage = parser.description.strip().split('\n\n', 1)[0]
    parser.description = '\n'.join(wrap(parser.description.strip().split('\n\n', 1)[1]))
    manpage = str(Manpage(parser))
    manpage += MANPAGE_ADD_TEXT
    dirpath = os.path.relpath(os.path.join('share', 'man', 'man1'))
    os.makedirs(dirpath, exist_ok=True)
    with open(os.path.join(dirpath, f'{project.__project_name__}.1'), 'w') as f:
        f.write(manpage)

if __name__ == '__main__':
    build_manpage()