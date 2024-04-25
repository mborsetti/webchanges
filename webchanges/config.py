"""Command-line configuration."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import argparse
import textwrap

# import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from webchanges import __doc__ as doc
from webchanges import __docs_url__, __project_name__, __version__


@dataclass
class BaseConfig:
    """Base configuration class."""

    config_path: Path
    config_file: Path
    jobs_def_file: Path
    hooks_file: Path
    ssdb_file: Path
    jobs_files: list[Path] = field(default_factory=list)


class CommandConfig(BaseConfig):
    """Command line arguments configuration; the arguments are stored as class attributes."""

    add: Optional[str]
    change_location: tuple[Union[int, str], str]
    check_new: bool
    clean_database: int
    database_engine: str
    delete: Optional[str]
    delete_snapshot: Optional[str]
    detailed_versions: bool
    dump_history: Optional[str]
    edit: bool
    edit_config: bool
    edit_hooks: bool
    errors: str
    features: bool
    footnote: Optional[str]
    gc_database: int
    install_chrome: bool
    joblist: list[str]
    list_jobs: bool
    max_snapshots: int
    max_workers: Optional[int]
    no_headless: bool
    rollback_database: Optional[int]
    smtp_login: bool
    telegram_chats: bool
    test_differ: Optional[list[str]]
    test_job: Union[bool, Optional[str]]
    test_reporter: Optional[str]
    verbose: Optional[int]
    xmpp_login: bool

    def __init__(
        self,
        args: list[str],
        config_path: Path,
        config_file: Path,
        jobs_def_file: Path,
        hooks_file: Path,
        ssdb_file: Path,
    ) -> None:
        """Command line arguments configuration; the arguments are stored as class attributes.

        :param config_path: The path of the configuration directory.
        :param config_file: The path of the configuration file.
        :param jobs_def_file: The glob of the jobs file(s).
        :param hooks_file: The path of the Python hooks file.
        :param ssdb_file: The path of the database file (or directory if using the textfiles database-engine) where
           snapshots are stored.
        """
        super().__init__(config_path, config_file, jobs_def_file, hooks_file, ssdb_file)
        self.jobs_files = [jobs_def_file]
        self.parse_args(args)

    def parse_args(self, cmdline_args: list[str]) -> argparse.ArgumentParser:
        """Set up the Python arguments parser and stores the arguments in the class's variables.

        :returns: The Python arguments parser.
        """
        description = '\n'.join(
            textwrap.wrap(doc.replace('\n\n', '--par--').replace('\n', ' ').replace('--par--(', '\n\n'), 79)
        )

        parser = argparse.ArgumentParser(
            prog=__project_name__,
            description=description,
            epilog=f'Full documentation is at {__docs_url__}\n',
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            'joblist',
            nargs='*',
            help=(
                'JOB(S) to run (if one, index as per --list or URL/command, if multiple, by index) (default: run all '
                'jobs)'
            ),
            metavar='JOB(S)',
        )
        parser.add_argument(
            '-V',
            '--version',
            action='version',
            version=f'{__project_name__} {__version__}\n'
            f"Run '{__project_name__} --check-new' to check if a new release is available.",
        )
        parser.add_argument(
            '-v', '--verbose', action='count', help='show logging output; use -vv for maximum verbosity'
        )

        group = parser.add_argument_group('override file defaults')
        group.add_argument(
            '--jobs',
            '--urls',
            default=self.jobs_def_file,
            type=Path,
            help='read job list (URLs/commands) from FILE or files matching a glob pattern',
            metavar='FILE',
            dest='jobs_def_file',
        )
        group.add_argument(
            '--config',
            default=self.config_file,
            type=Path,
            help='read configuration from FILE',
            metavar='FILE',
            dest='config_file',
        )
        group.add_argument(
            '--hooks',
            default=self.hooks_file,
            type=Path,
            help='use FILE as hooks.py module to import',
            metavar='FILE',
            dest='hooks_file',
        )
        group.add_argument(
            '--database',
            '--cache',
            default=self.ssdb_file,
            type=Path,
            help='use FILE as snapshots database; FILE can be a redis URI',
            metavar='FILE',
            dest='ssdb_file',
        )

        group = parser.add_argument_group('job management')
        group.add_argument(
            '--list-jobs',
            action='store_true',
            help='list jobs and their index number',
        )
        group.add_argument(
            '--errors',
            nargs='?',
            const='stdout',
            help='test run all jobs and list those with errors or no data captured; optionally send output to REPORTER',
            metavar='REPORTER',
        )
        group.add_argument(
            '--test',
            '--test-filter',
            nargs='?',
            const=True,
            help='test a JOB (by index or URL/command) and show filtered output; if no JOB, check syntax of config and '
            'jobs file(s)',
            metavar='JOB',
            dest='test_job',
        )
        group.add_argument(
            '--no-headless',
            action='store_true',
            help='turn off browser headless mode (for jobs using a browser)',
        )
        group.add_argument(
            '--test-differ',
            '--test-diff',
            '--test-diff-filter',
            nargs='+',
            help='show diff(s) using existing saved snapshots of a JOB (by index or URL/command)',
            metavar='JOB',
            dest='test_differ',
        )
        group.add_argument(
            '--dump-history',
            help='print all saved changed snapshots for a JOB (by index or URL/command)',
            metavar='JOB',
        )
        group.add_argument(
            '--max-workers',
            type=int,
            help='maximum number of parallel threads (WORKERS)',
            metavar='WORKERS',
        )

        group = parser.add_argument_group('reporters')
        group.add_argument(
            '--test-reporter',
            help='test the REPORTER or redirect output of --test-differ',
            metavar='REPORTER',
        )
        group.add_argument(
            '--smtp-login',
            action='store_true',
            help='verify SMTP login credentials with server (and enter or check password if using keyring)',
        )
        group.add_argument(
            '--telegram-chats',
            action='store_true',
            help=f'list telegram chats {__project_name__} is joined to',
        )
        group.add_argument(
            '--xmpp-login',
            action='store_true',
            help='enter or check password for XMPP (stored in keyring)',
        )
        group.add_argument(
            '--footnote',
            help='FOOTNOTE text (quoted text)',
        )

        group = parser.add_argument_group('launch editor ($EDITOR/$VISUAL)')
        group.add_argument(
            '--edit',
            action='store_true',
            help='edit job (URL/command) list',
        )
        group.add_argument(
            '--edit-config',
            action='store_true',
            help='edit configuration file',
        )
        group.add_argument(
            '--edit-hooks',
            action='store_true',
            help='edit hooks script',
        )

        group = parser.add_argument_group('database')
        group.add_argument(
            '--gc-database',
            '--gc-cache',
            nargs='?',
            const=1,
            type=int,
            help='garbage collect the database: remove all snapshots of jobs not listed in the jobs file and keep only '
            'the latest RETAIN_LIMIT snapshots for remaining jobs (default: 1)',
            metavar='RETAIN_LIMIT',
        )
        group.add_argument(
            '--clean-database',
            '--clean-cache',
            nargs='?',
            const=1,
            type=int,
            help='clean up the database by keeping only the latest RETAIN_LIMIT snapshots (default: 1)',
            metavar='RETAIN_LIMIT',
        )
        group.add_argument(
            '--rollback-database',
            '--rollback-cache',
            type=int,
            help='delete changed snapshots added since TIMESTAMP (backup the database before using!)',
            metavar='TIMESTAMP',
        )
        group.add_argument(
            '--delete-snapshot',
            help='delete the last saved changed snapshot of JOB (index or URL/command)',
            metavar='JOB',
        )
        group.add_argument(
            '--change-location',
            nargs=2,
            help='change the location of an existing JOB (index or URL/command)',
            metavar=('JOB', 'NEW_LOCATION'),
        )

        group = parser.add_argument_group('miscellaneous')
        group.add_argument(
            '--check-new',
            action='store_true',
            help='check if a new release is available',
        )
        group.add_argument(
            '--install-chrome',
            action='store_true',
            help='install or update Google Chrome browser',
        )
        group.add_argument(
            '--features',
            action='store_true',
            help='list supported job kinds, filters and reporters (including those loaded from hooks.py)',
        )
        group.add_argument(
            '--detailed-versions',
            action='store_true',
            help='list detailed versions including those of installed dependencies',
        )

        group = parser.add_argument_group('override configuration file')
        group.add_argument(
            '--database-engine',
            # choices=['sqlite3', 'redis', 'minidb', 'textfiles'],
            help='override database engine to use',
        )
        group.add_argument(
            '--max-snapshots',
            # default=4,
            type=int,
            help='override maximum number of changed snapshots to retain in database (sqlite3 only)',
            metavar='NUM_SNAPSHOTS',
        )

        group = parser.add_argument_group('deprecated')
        group.add_argument(
            '--add',
            help='add a job (key1=value1,key2=value2,...) [use --edit instead]',
            metavar='JOB',
        )
        group.add_argument(
            '--delete',
            help='delete a job (by index or URL/command) [use --edit instead]',
            metavar='JOB',
        )

        # # workaround for avoiding triggering error when invoked by pytest
        # if parser.prog != '_jb_pytest_runner.py' and not os.getenv('CI'):
        args = parser.parse_args(cmdline_args)

        for arg in vars(args):
            argval = getattr(args, arg)
            setattr(self, arg, argval)

        return parser
