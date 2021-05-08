#!/usr/bin/env python3

"""Module containing the entry point."""

# See config module for the command line arguments

import logging
import os.path
import shutil
import signal
import sys
import warnings
from typing import Optional, Union

from appdirs import AppDirs

from . import __copyright__, __docs_url__, __min_python_version__, __project_name__, __version__
from .command import UrlwatchCommand
from .config import CommandConfig
from .main import Urlwatch
from .storage import CacheDirStorage, CacheRedisStorage, CacheSQLite3Storage, YamlConfigStorage, YamlJobsStorage

# directory where the config, jobs and hooks files are located
if os.name != 'nt':
    # typically ~/.config/{__project_name__}
    config_dir = AppDirs(__project_name__).user_config_dir
else:
    config_dir = os.path.expanduser(os.path.join('~', 'Documents', __project_name__))

# directory where the database is located
# typically ~/.cache/{__project_name__} or %LOCALAPPDATA%\{__project_name__}\{__project_name__}\Cache
cache_dir = AppDirs(__project_name__).user_cache_dir

# Ignore SIGPIPE for stdout (see https://github.com/thp/urlwatch/issues/77)
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except AttributeError:
    # Windows does not have signal.SIGPIPE
    pass

logger = logging.getLogger(__name__)


def setup_logger_verbose(log_level: Union[str, int] = logging.DEBUG) -> None:
    """Set up the loggers for verbosity."""
    import platform

    # logging.basicConfig(format='%(asctime)s %(module)s %(levelname)s: %(message)s', level=log_level)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter('%(asctime)s %(module)s %(levelname)s: %(message)s'))
    logger.addHandler(console)
    logger.setLevel(log_level)
    logger.debug(f'{__project_name__}: {__version__} {__copyright__}')
    logger.debug(f'Python: {platform.python_build()}')
    logger.debug(f'System: {platform.platform()}')


def locate_storage_file(filename: Union[str, bytes, os.PathLike], default_dir: Union[str, bytes, os.PathLike],
                        ext: Optional[str] = None) -> str:
    """Searches for file as specified and in default directory; retry with 'ext' extension.

    :param filename: The filename
    :param default_dir: Default storage directory
    :param ext: The extension, e.g. '.yaml', to add for searching if first scan fails

    :returns: The filename, either original or with path where found
    """
    search_filenames = [filename]

    # if exp is given, iterate both on raw filename and the filename with ext if different
    if ext and os.path.splitext(filename)[1] != ext:
        search_filenames.append(filename + ext)

    for file in search_filenames:
        # return if found
        if os.path.isfile(file):
            return file

        # no directory specified: add default one
        if file == os.path.basename(file):
            new_file = os.path.join(default_dir, file)
            if os.path.isfile(new_file):
                return new_file

    return filename


def migrate_from_urlwatch(config_file: Union[str, bytes, os.PathLike], jobs_file: Union[str, bytes, os.PathLike],
                          hooks_file: Union[str, bytes, os.PathLike], cache_file: Union[str, bytes, os.PathLike]
                          ) -> None:
    """Check for existence of legacy (urlwatch 2.23) config, jobs and hooks files and migrate them (i.e. make a copy to
    new folder and or naming).  Original files are not deleted."""
    uw_urlwatch_dir = os.path.expanduser(os.path.join('~', '.' + 'urlwatch'))
    uw_config_file = os.path.join(uw_urlwatch_dir, 'urlwatch.yaml')
    uw_urls_file = os.path.join(uw_urlwatch_dir, 'urls.yaml')
    uw_hooks_file = os.path.join(uw_urlwatch_dir, 'hooks.py')
    uw_cache_dir = AppDirs('urlwatch').user_cache_dir
    uw_cache_file = os.path.join(uw_cache_dir, 'cache.db')
    for old_file, new_file in zip((uw_config_file, uw_urls_file, uw_hooks_file, uw_cache_file),
                                  (config_file, jobs_file, hooks_file, cache_file)):
        if os.path.isfile(old_file) and not os.path.isfile(new_file):
            os.makedirs(os.path.dirname(new_file), exist_ok=True)
            shutil.copyfile(old_file, new_file)
            logger.warning(f"Copied urlwatch '{old_file}' file to {__project_name__} '{new_file}'")


def first_run(command_config: CommandConfig) -> None:
    """Create jobs and configuration files."""
    os.makedirs(config_dir, exist_ok=True)
    if not os.path.isfile(command_config.config):
        YamlConfigStorage.write_default_config(command_config.config)
        print(f'Created default config file at {command_config.config}\n> Edit it with {__project_name__} '
              f'--edit-config')
    if not os.path.isfile(command_config.jobs):
        with open(command_config.jobs, 'w') as fp:
            fp.write(f'# {__project_name__} jobs file. See {__docs_url__}jobs.html\n')
        command_config.edit = True
        print(f'Created default jobs file at {command_config.jobs}\n> Edit it with {__project_name__} --edit-config '
              f'(trying to launch it automatically)')


def main() -> None:  # pragma: no cover
    """The entry point."""
    # make sure that PendingDeprecationWarning are displayed from all modules (otherwise only those in __main__ are)
    warnings.filterwarnings('default', category=PendingDeprecationWarning)

    # Issue deprecation warning if running on minimum version supported
    if sys.version_info[0:2] == __min_python_version__:
        current_minor_version = '.'.join(str(n) for n in sys.version_info[0:2])
        next_minor_version = f'{__min_python_version__[0]}.{__min_python_version__[1] + 1}'
        warning = (f'Support for Python {current_minor_version} will be ending three years from the date Python '
                   f'{next_minor_version} was released')
        print(f'WARNING: {warning}\n')
        PendingDeprecationWarning(warning)

    # The config, jobs, hooks and cache files
    default_config_file = os.path.join(config_dir, 'config.yaml')
    default_jobs_file = os.path.join(config_dir, 'jobs.yaml')
    default_hooks_file = os.path.join(config_dir, 'hooks.py')
    default_cache_file = os.path.join(cache_dir, 'cache.db')

    # migrate legacy urlwatch 2.23 files
    migrate_from_urlwatch(default_config_file, default_jobs_file, default_hooks_file, default_cache_file)

    # load config files
    command_config = CommandConfig(__project_name__, config_dir, default_config_file, default_jobs_file,
                                   default_hooks_file, default_cache_file, verbose=False)

    # set up the logger to verbose if needed
    if command_config.verbose:
        setup_logger_verbose(command_config.log_level)

    # check for location of config files entered in cli
    command_config.config = locate_storage_file(command_config.config, command_config.config_dir, '.yaml')
    command_config.jobs = locate_storage_file(command_config.jobs, command_config.config_dir, '.yaml')
    command_config.hooks = locate_storage_file(command_config.hooks, command_config.config_dir, '.py')

    # check for first run
    if command_config.config == default_config_file and not os.path.isfile(command_config.config):
        first_run(command_config)

    # setup config file API
    config_storage = YamlConfigStorage(command_config.config)  # storage.py

    # setup database API
    if command_config.database_engine == 'sqlite3':
        cache_storage = CacheSQLite3Storage(command_config.cache, command_config.max_snapshots)  # storage.py
    elif any(command_config.cache.startswith(prefix) for prefix in ('redis://', 'rediss://')):
        cache_storage = CacheRedisStorage(command_config.cache)  # storage.py
    elif command_config.database_engine == 'redis':
        raise RuntimeError("A redis URI (starting with 'redis://' or 'rediss://' needs to be specified with --cache")
    elif command_config.database_engine == 'textfiles':
        cache_storage = CacheDirStorage(command_config.cache)  # storage.py
    elif command_config.database_engine == 'minidb':
        from .storage_minidb import CacheMiniDBStorage  # legacy code imported only if needed (requires minidb)

        cache_storage = CacheMiniDBStorage(command_config.cache)  # storage.py
    else:
        raise NotImplementedError(f'Database engine {command_config.database_engine} not implemented')

    # setup jobs file API
    jobs_storage = YamlJobsStorage(command_config.jobs)  # storage.py

    # setup urlwatch
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    urlwatch_command = UrlwatchCommand(urlwatcher)  # command.py

    # run urlwatch
    urlwatch_command.run()


if __name__ == '__main__':

    main()
