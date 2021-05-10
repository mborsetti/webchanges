"""Command-line configuration."""

import argparse
from os import PathLike
from pathlib import Path
from typing import List, Optional, Union

from . import __doc__, __project_name__, __version__


class BaseConfig(object):
    """Base configuration class."""

    def __init__(self, project_name: str, config_dir: Union[str, bytes, PathLike],
                 config: Union[str, bytes, PathLike], jobs: Union[str, bytes, PathLike],
                 cache: Union[str, bytes, PathLike], hooks: Union[str, bytes, PathLike],
                 verbose: bool) -> None:
        self.project_name = project_name
        self.config_dir = Path(config_dir)
        self.config = Path(config)
        self.jobs = Path(jobs)
        self.cache = Path(cache)
        self.hooks = Path(hooks)
        self.verbose = verbose


class CommandConfig(BaseConfig):
    """Command line arguments configuration."""

    def __init__(self, project_name: str, config_dir: PathLike, config: PathLike, jobs: PathLike,
                 hooks: PathLike, cache: PathLike, verbose: bool) -> None:
        super().__init__(project_name, config_dir, config, jobs, cache, hooks, verbose)
        self.joblist: Optional[List[int]] = None
        self.list: bool = False
        self.errors: bool = False
        self.test_job: Optional[str] = None
        self.test_diff: Optional[str] = None
        self.add: Optional[str] = None
        self.delete: Optional[str] = None
        self.test_reporter: Optional[str] = None
        self.smtp_login: bool = False
        self.telegram_chats: bool = False
        self.xmpp_login: bool = False
        self.edit: bool = False
        self.edit_config: bool = False
        self.edit_hooks: bool = False
        self.gc_cache: bool = False
        self.clean_cache: bool = False
        self.rollback_cache: Optional[int] = None
        self.delete_snapshot: Optional[str] = None
        self.database_engine: str = 'sqlite3'
        self.max_snapshots: int = 4
        self.features: bool = False
        self.log_level: str = 'DEBUG'

        self.parse_args()

    def parse_args(self) -> argparse.ArgumentParser:
        """Python arguments parser."""
        parser = argparse.ArgumentParser(description=__doc__.replace('\n\n', '--par--').replace('\n', ' ')
                                         .replace('--par--', '\n\n'),
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument('joblist', nargs='*', type=int,
                            help='job(s) to run (by index as per --list) (default: run all jobs)', metavar='JOB')
        parser.add_argument('-V', '--version', action='version', version=f'{__project_name__} {__version__}')
        parser.add_argument('-v', '--verbose', action='store_true', help='show logging output')

        group = parser.add_argument_group('override file defaults')
        group.add_argument('--jobs', '--urls', default=self.jobs, help='read job list (URLs) from FILE',
                           metavar='FILE', dest='jobs')
        group.add_argument('--config', default=self.config, help='read configuration from FILE', metavar='FILE')
        group.add_argument('--hooks', default=self.hooks, help='use FILE as hooks.py module', metavar='FILE')
        group.add_argument('--cache', default=self.cache,
                           help='use FILE as cache (snapshots database) or directory, alternatively a redis URI',
                           metavar='FILE')
        group.add_argument('--list', action='store_true', help='list jobs and their index number')
        group.add_argument('--errors', action='store_true', help='list jobs with errors or no data captured')
        group.add_argument('--test', '--test-filter',
                           help='test a job (by index or URL/command) and show filtered output', metavar='JOB',
                           dest='test_job')
        group.add_argument('--test-diff', '--test-diff-filter',
                           help='test and show diff using existing saved snapshots of a job (by index or URL/command)',
                           metavar='JOB', dest='test_diff')
        group.add_argument('--add', help='add job (key1=value1,key2=value2,...). WARNING: all remarks are deleted from '
                                         'jobs file; use --edit instead!', metavar='JOB')
        group.add_argument('--delete', help='delete job by URL/command or index number. WARNING: all remarks are '
                                            'deleted from jobs file; use --edit instead!', metavar='JOB')
        group = parser.add_argument_group('reporters')
        group.add_argument('--test-reporter', help='send a test notification', metavar='REPORTER')
        group.add_argument('--smtp-login', action='store_true',
                           help='verify SMTP login credentials with server and, if stored in keyring, enter or check '
                                'password')
        group.add_argument('--telegram-chats', action='store_true', help='list telegram chats program is joined to')
        group.add_argument('--xmpp-login', action='store_true',
                           help='enter or check password for XMPP (stored in keyring)')

        group = parser.add_argument_group('launch editor ($EDITOR/$VISUAL)')
        group.add_argument('--edit', action='store_true', help='edit job (URL/command) list')
        group.add_argument('--edit-config', action='store_true', help='edit configuration file')
        group.add_argument('--edit-hooks', action='store_true', help='edit hooks script')

        group = parser.add_argument_group('database')
        group.add_argument('--gc-cache', action='store_true',
                           help='garbage collect the cache database by removing old snapshots plus all data of jobs'
                                ' not in the jobs file')
        group.add_argument('--clean-cache', action='store_true', help='remove old snapshots from the cache database')
        group.add_argument('--rollback-cache', type=int,
                           help='delete recent snapshots > timestamp; backup the database before using!',
                           metavar='TIMESTAMP')
        group.add_argument('--delete-snapshot', help='delete the last saved snapshot of job (URL/command)',
                           metavar='JOB')
        group.add_argument('--database-engine', default='sqlite3', choices=['sqlite3', 'redis', 'minidb', 'textfiles'],
                           help='database engine to use (default: %(default)s unless redis URI in --cache)')
        group.add_argument('--max-snapshots', default=4, type=int,
                           help='maximum number of snapshots to retain in sqlite3 database (default: %(default)s) '
                                '(Python 3.7 or higher)', metavar='NUM_SNAPSHOTS')

        group = parser.add_argument_group('miscellaneous')
        group.add_argument('--features', action='store_true', help='list supported job types, filters and reporters')
        group.add_argument('--log-level', default='DEBUG', choices=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
                           help='level of logging output if -v is selected (default: %(default)s)')

        # workaround for avoiding triggering error when invoked by pytest
        if parser.prog != '_jb_pytest_runner.py':
            args = parser.parse_args()

            for arg in vars(args):
                argval = getattr(args, arg)
                setattr(self, arg, argval)

        return parser
