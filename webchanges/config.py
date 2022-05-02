"""Command-line configuration."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from . import __doc__, __docs_url__, __project_name__, __version__
from .util import get_new_version_number


@dataclass
class BaseConfig(object):
    """Base configuration class.

    :param project_name: The name of the project.
    :param config_path: The path of the configuration directory.
    :param config: The path of the configuration file.
    :param jobs: The path of the jobs file.
    :param hooks: The path of the Python hooks file.
    :param cache: The path of the database file (or directory if using the textfiles database-engine) where
       snapshots are stored.
    """

    project_name: str
    config_path: Path
    config: Path
    jobs: Path
    hooks: Path
    cache: Union[str, Path]


class CommandConfig(BaseConfig):
    """Command line arguments configuration; the arguments are stored as class attributes."""

    joblist: Optional[List[int]] = None
    verbose: bool = False
    list: bool = False
    errors: bool = False
    test_job: Optional[str] = None
    no_headless: bool = False
    test_diff: Optional[str] = None
    dump_history: Optional[str] = None
    add: Optional[str] = None
    delete: Optional[str] = None
    test_reporter: Optional[str] = None
    smtp_login: bool = False
    telegram_chats: bool = False
    xmpp_login: bool = False
    edit: bool = False
    edit_config: bool = False
    edit_hooks: bool = False
    gc_cache: bool = False
    clean_cache: bool = False
    rollback_cache: Optional[int] = None
    delete_snapshot: Optional[str] = None
    database_engine: str = 'sqlite3'
    max_snapshots: int = 4
    features: bool = False
    install_chrome: bool = False
    log_level: str = 'DEBUG'

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
        # self.joblist: Optional[List[int]] = None
        # self.verbose: bool = False
        # self.list: bool = False
        # self.errors: bool = False
        # self.test_job: Optional[str] = None
        # self.no_headless: bool = False
        # self.test_diff: Optional[str] = None
        # self.dump_history: Optional[str] = None
        # self.add: Optional[str] = None
        # self.delete: Optional[str] = None
        # self.test_reporter: Optional[str] = None
        # self.smtp_login: bool = False
        # self.telegram_chats: bool = False
        # self.xmpp_login: bool = False
        # self.edit: bool = False
        # self.edit_config: bool = False
        # self.edit_hooks: bool = False
        # self.gc_cache: bool = False
        # self.clean_cache: bool = False
        # self.rollback_cache: Optional[int] = None
        # self.delete_snapshot: Optional[str] = None
        # self.database_engine: str = 'sqlite3'
        # self.max_snapshots: int = 4
        # self.features: bool = False
        # self.install_chrome: bool = False
        # self.log_level: str = 'DEBUG'
        self.parse_args(args)

    def parse_args(self, cmdline_args: List[str]) -> argparse.ArgumentParser:
        """Set up the Python arguments parser and stores the arguments in the class's variables.

        :returns: The Python arguments parser.
        """

        new_version = get_new_version_number(timeout=0.5)
        new_version_text = (
            f'\nNew release version {new_version} is available; we recommend updating.' if new_version else ''
        )
        parser = argparse.ArgumentParser(
            description=__doc__.replace('\n\n', '--par--').replace('\n', ' ').replace('--par--', '\n\n'),
            epilog=f'Full documentation is at {__docs_url__}{new_version_text}\n',
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            'joblist',
            nargs='*',
            type=int,
            help='job(s) to run (by index as per --list) (default: run all jobs)',
            metavar='JOB',
        )
        parser.add_argument('-V', '--version', action='version', version=f'{__project_name__} {__version__}')
        parser.add_argument('-v', '--verbose', action='store_true', help='show logging output')

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
            help='test a job (by index or URL/command) and show filtered output',
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
        group.add_argument(
            '--add',
            help='add job (key1=value1,key2=value2,...). WARNING: all remarks are deleted from '
            'jobs file; use --edit instead!',
            metavar='JOB',
        )
        group.add_argument(
            '--delete',
            help='delete job by URL/command or index number. WARNING: all remarks are '
            'deleted from jobs file; use --edit instead!',
            metavar='JOB',
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
            '--delete-snapshot', help='delete the last saved snapshot of job (URL/command)', metavar='JOB'
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
            help='maximum number of snapshots to retain in sqlite3 database (default: %(default)s)',
            metavar='NUM_SNAPSHOTS',
        )

        group = parser.add_argument_group('miscellaneous')
        group.add_argument(
            '--install-chrome',
            action='store_true',
            help="install or update Google Chrome browser for use with 'use_browser: true' jobs",
        )
        group.add_argument('--features', action='store_true', help='list supported job types, filters and reporters')
        group.add_argument(
            '--log-level',
            default='DEBUG',
            choices=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
            help='level of logging output when -v is selected (default: %(default)s)',
        )

        # workaround for avoiding triggering error when invoked by pytest
        if parser.prog != '_jb_pytest_runner.py' and not os.getenv('CI'):
            args = parser.parse_args(cmdline_args)

            for arg in vars(args):
                argval = getattr(args, arg)
                setattr(self, arg, argval)

        return parser
