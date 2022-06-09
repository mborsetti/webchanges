"""Command-line configuration."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import argparse

# import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from . import __doc__, __docs_url__, __project_name__, __version__


@dataclass
class BaseConfig:
    """Base configuration class."""

    project_name: str
    config_path: Path
    config: Path
    jobs: Path
    hooks: Path
    cache: Union[str, Path]


class CommandConfig(BaseConfig):
    """Command line arguments configuration; the arguments are stored as class attributes."""

    add: Optional[str]
    check_new: bool
    clean_cache: bool
    database_engine: str
    delete: Optional[str]
    delete_snapshot: Optional[str]
    dump_history: Optional[str]
    edit: bool
    edit_config: bool
    edit_hooks: bool
    errors: bool
    features: bool
    gc_cache: bool
    install_chrome: bool
    joblist: List[int]
    list: bool
    max_snapshots: int
    no_headless: bool
    rollback_cache: Optional[int]
    smtp_login: bool
    telegram_chats: bool
    test_diff: Optional[str]
    test_job: Union[bool, Optional[str]]
    test_reporter: Optional[str]
    verbose: Optional[int]
    xmpp_login: bool

    def __init__(
        self,
        args: List[str],
        project_name: str,
        config_path: Path,
        config: Path,
        jobs: Path,
        hooks: Path,
        cache: Union[str, Path],
    ) -> None:
        """Command line arguments configuration; the arguments are stored as class attributes.

        :param project_name: The name of the project.
        :param config_path: The path of the configuration directory.
        :param config: The path of the configuration file.
        :param jobs: The path of the jobs file.
        :param hooks: The path of the Python hooks file.
        :param cache: The path of the database file (or directory if using the textfiles database-engine) where
           snapshots are stored.
        """
        super().__init__(project_name, config_path, config, jobs, hooks, cache)
        self.parse_args(args)

    def parse_args(self, cmdline_args: List[str]) -> argparse.ArgumentParser:
        """Set up the Python arguments parser and stores the arguments in the class's variables.

        :returns: The Python arguments parser.
        """

        parser = argparse.ArgumentParser(
            description=__doc__.replace('\n\n', '--par--').replace('\n', ' ').replace('--par--', '\n\n'),
            epilog=f'Full documentation is at {__docs_url__}\n',
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            'joblist',
            nargs='*',
            type=int,
            help='job(s) to run (by index as per --list) (default: run all jobs)',
            metavar='JOB',
        )
        parser.add_argument(
            '-V',
            '--version',
            action='version',
            version=f'{__project_name__} {__version__}\n\n'
            f"Run '{__project_name__} --check-new' to check if a new release is available.",
        )
        parser.add_argument(
            '-v', '--verbose', action='count', help='show logging output; use -vv for maximum verbosity'
        )

        group = parser.add_argument_group('override file defaults')
        group.add_argument(
            '--jobs',
            '--urls',
            default=self.jobs,
            type=Path,
            help='read job list (URLs) from FILE',
            metavar='FILE',
            dest='jobs',
        )
        group.add_argument(
            '--config', default=self.config, type=Path, help='read configuration from FILE', metavar='FILE'
        )
        group.add_argument(
            '--hooks', default=self.hooks, type=Path, help='use FILE as imported hooks.py module', metavar='FILE'
        )
        group.add_argument(
            '--cache',
            default=self.cache,
            type=Path,
            help='use FILE as cache (snapshots database), alternatively a redis URI',
            metavar='FILE',
        )

        group = parser.add_argument_group('job management')
        group.add_argument('--list', action='store_true', help='list jobs and their index number')
        group.add_argument('--errors', action='store_true', help='list jobs with errors or no data captured')
        group.add_argument(
            '--test',
            '--test-filter',
            nargs='?',
            const=True,
            help='test a job (by index or URL/command) and show filtered output; if no JOB, check config and job files',
            metavar='JOB',
            dest='test_job',
        )
        group.add_argument(
            '--no-headless',
            action='store_true',
            help='turn off browser headless mode (for jobs using a browser)',
        )
        group.add_argument(
            '--test-diff',
            '--test-diff-filter',
            help='test and show diff using existing saved snapshots of a job (by index or URL/command)',
            metavar='JOB',
            dest='test_diff',
        )
        group.add_argument(
            '--dump-history',
            help='print all saved snapshot history for a job (by index or URL/command)',
            metavar='JOB',
        )

        group = parser.add_argument_group(
            'backward compatibility (WARNING: all remarks are deleted from jobs file; use --edit instead)'
        )
        group.add_argument('--add', help='add a job (key1=value1,key2=value2,...) [use --edit instead]', metavar='JOB')
        group.add_argument(
            '--delete', help='delete a job (by index or URL/command) [use --edit instead]', metavar='JOB'
        )

        group = parser.add_argument_group('reporters')
        group.add_argument(
            '--test-reporter',
            help='test a reporter or redirect output of --test-diff',
            metavar='REPORTER',
        )
        group.add_argument(
            '--smtp-login',
            action='store_true',
            help='verify SMTP login credentials with server (and enter or check password if using keyring)',
        )
        group.add_argument('--telegram-chats', action='store_true', help='list telegram chats program is joined to')
        group.add_argument(
            '--xmpp-login', action='store_true', help='enter or check password for XMPP (stored in keyring)'
        )

        group = parser.add_argument_group('launch editor ($EDITOR/$VISUAL)')
        group.add_argument('--edit', action='store_true', help='edit job (URL/command) list')
        group.add_argument('--edit-config', action='store_true', help='edit configuration file')
        group.add_argument('--edit-hooks', action='store_true', help='edit hooks script')

        group = parser.add_argument_group('database')
        group.add_argument(
            '--gc-cache',
            action='store_true',
            help='garbage collect the cache database by removing old snapshots plus all data of jobs'
            ' not in the jobs file',
        )
        group.add_argument('--clean-cache', action='store_true', help='remove old snapshots from the cache database')
        group.add_argument(
            '--rollback-cache',
            type=int,
            help='delete recent snapshots since TIMESTAMP (backup the database before using!)',
            metavar='TIMESTAMP',
        )
        group.add_argument(
            '--delete-snapshot', help='delete the last saved snapshot of job (index or URL/command)', metavar='JOB'
        )
        group.add_argument(
            '--database-engine',
            default='sqlite3',
            choices=['sqlite3', 'redis', 'minidb', 'textfiles'],
            help='database engine to use (default: %(default)s, unless redis URI in --cache)',
        )
        group.add_argument(
            '--max-snapshots',
            default=4,
            type=int,
            help='sqlite3 only: maximum number of snapshots to retain in database (default: %(default)s)',
            metavar='NUM_SNAPSHOTS',
        )

        group = parser.add_argument_group('miscellaneous')
        group.add_argument('--check-new', action='store_true', help='check if new release is available')
        group.add_argument(
            '--install-chrome',
            action='store_true',
            help='install or update Google Chrome browser (for jobs using a browser)',
        )
        group.add_argument(
            '--features',
            action='store_true',
            help='list supported job types, filters and reporters (including those loaded by hooks)',
        )

        # # workaround for avoiding triggering error when invoked by pytest
        # if parser.prog != '_jb_pytest_runner.py' and not os.getenv('CI'):
        args = parser.parse_args(cmdline_args)

        for arg in vars(args):
            argval = getattr(args, arg)
            setattr(self, arg, argval)

        return parser
