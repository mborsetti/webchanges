"""Command-line configuration."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import argparse
import os
import textwrap

# import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Collection

from webchanges import __doc__ as doc
from webchanges import __docs_url__, __project_name__, __version__


@dataclass
class BaseConfig:
    """Base configuration class."""

    config_path: Path
    config_file: Path
    jobs_def_file: Path
    hooks_def_file: Path
    ssdb_file: Path
    jobs_files: list[Path] = field(default_factory=list)
    hooks_files: list[Path] = field(default_factory=list)


class CommandConfig(BaseConfig):
    """Command line arguments configuration; the arguments are stored as class attributes."""

    add: str | None
    change_location: tuple[int | str, str] | None
    check_new: bool
    clean_database: int | None
    database_engine: str | None
    delete: str | None
    delete_snapshot: str | None
    detailed_versions: bool
    dump_history: str | None
    edit: bool
    edit_config: bool
    edit_hooks: bool
    errors: str | None
    features: bool
    footnote: str | None
    gc_database: int | None
    hooks_files: list[Path]
    hooks_files_inputted: bool
    install_chrome: bool
    joblist: Collection[str | int]
    jobs_files: list[Path]
    list_jobs: bool | str | None
    log_file: Path
    max_snapshots: int | None
    max_workers: int | None
    no_headless: bool
    prepare_jobs: bool
    rollback_database: str | None
    smtp_login: bool
    telegram_chats: bool
    test_differ: list[str] | None
    test_job: bool | str | None
    test_reporter: str | None
    verbose: int | None
    xmpp_login: bool

    def __init__(
        self,
        args: list[str],
        config_path: Path,
        config_file: Path,
        jobs_def_file: Path,
        hooks_def_file: Path,
        ssdb_file: Path,
    ) -> None:
        """Command line arguments configuration; the arguments are stored as class attributes.

        :param config_path: The path of the configuration directory.
        :param config_file: The path of the configuration file.
        :param jobs_def_file: The glob of the jobs file(s).
        :param hooks_def_file: The path of the Python hooks file.
        :param ssdb_file: The path of the database file (or directory if using the textfiles database-engine) where
           snapshots are stored.
        """
        super().__init__(config_path, config_file, jobs_def_file, hooks_def_file, ssdb_file)
        self.parse_args(args)
        self.jobs_files = self.jobs_files or [jobs_def_file]
        self.hooks_files_inputted = bool(self.hooks_files)
        self.hooks_files = self.hooks_files or [hooks_def_file]

    class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
        def __init__(self, prog: str) -> None:
            """Initialize the help formatter.

            :param prog: The program name.
            """
            if os.getenv('WEBCHANGES_BUILD_CLI_HELP.RST'):  # called by pre-commit
                super().__init__(prog, width=104)
            else:
                super().__init__(prog)

    def parse_args(self, cmdline_args: list[str]) -> argparse.ArgumentParser:
        """Set up the Python arguments parser and stores the arguments in the class's variables.

        :returns: The Python arguments parser.
        """
        description = '\n'.join(
            textwrap.wrap(str(doc).replace('\n\n', '--par--').replace('\n', ' ').replace('--par--(', '\n\n'), 79)
        )

        parser = argparse.ArgumentParser(
            prog=__project_name__,
            description=description,
            epilog=f'Full documentation is at {__docs_url__}\n',
            formatter_class=self.CustomHelpFormatter,
        )
        parser.add_argument(
            'joblist',
            nargs='*',
            help=('JOB(S) to run (index number(s) as per --list; if one also URL/command) (default: run all jobs)'),
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
        parser.add_argument(
            '--log-file',
            type=Path,
            help='send log to FILE',
            metavar='FILE',
        )

        group = parser.add_argument_group('override file defaults')
        group.add_argument(
            '--jobs',
            '--urls',
            action='append',
            type=Path,
            help='read job list (URLs/commands) from FILE or files matching a glob pattern',
            metavar='FILE',
            dest='jobs_files',
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
            action='append',
            # default=self.hooks_file,
            type=Path,
            help='use FILE or files matching a glob pattern as hooks.py module to import',
            metavar='FILE',
            dest='hooks_files',
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
            nargs='?',
            const=True,
            help='list jobs and their index number (optional: only those who match REGEX)',
            metavar='REGEX',
            dest='list_jobs',
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
            type=str,
            help='delete changed snapshots added since TIMESTAMP (backup the database before using!)',
            metavar='TIMESTAMP',
        )
        group.add_argument(
            '--delete-snapshot',
            help='delete the last saved changed snapshot of JOB (index or URL/command)',
            metavar='JOB',
        )
        group.add_argument(
            '--prepare-jobs',
            action='store_true',
            help='run only newly added jobs (without history)',
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
