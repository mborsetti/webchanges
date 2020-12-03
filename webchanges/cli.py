#!/usr/bin/env python3

"""Module containing the entry point"""

import logging
import os.path
import signal
import sys
import warnings

from appdirs import AppDirs

from .command import UrlwatchCommand
from .config import CommandConfig
from .main import Urlwatch
from .storage import CacheMiniDBStorage, CacheRedisStorage, JobsYaml, YamlConfigStorage

# Check if we are installed in the system already # Legacy for apt-get type of packaging
# (prefix, bindir) = os.path.split(os.path.dirname(os.path.abspath(sys.argv[0])))
# if bindir != 'bin':
#     sys.path.insert(1, os.path.dirname(os.path.abspath(sys.argv[0])))


project_name = __package__
(prefix, bindir) = os.path.split(os.path.dirname(os.path.abspath(sys.argv[0])))

# directory where the config, jobs and hooks files are located
if os.name != 'nt':
    # typically ~/.config/{project_name}
    config_dir = AppDirs(project_name).user_config_dir
else:
    config_dir = os.path.expanduser(os.path.join('~', 'Documents', project_name))

# directory where the database is located
# typically ~/.cache/{project_name} or %LOCALAPPDATA%\{project_name}\{project_name}\Cache
cache_dir = AppDirs(project_name).user_cache_dir

# Ignore SIGPIPE for stdout (see https://github.com/thp/urlwatch/issues/77)
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except AttributeError:
    # Windows does not have signal.SIGPIPE
    ...

logger = logging.getLogger(project_name)


def setup_logger(verbose: bool) -> None:
    """Set up the logger"""
    if verbose:
        root_logger = logging.getLogger('')
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter('%(asctime)s %(module)s %(levelname)s: %(message)s'))
        root_logger.addHandler(console)
        root_logger.setLevel(logging.DEBUG)
        root_logger.info('turning on verbose logging mode')


def migrate_from_urlwatch(config_file: str, jobs_file: str, hooks_file: str, cache_file: str) -> None:
    """Migrate legacy config, jobs and hooks files from urlwatch 2.2"""
    urlwatch_config_dir = os.path.expanduser(os.path.join('~', '.' + 'urlwatch'))
    urlwatch_config_file = os.path.join(urlwatch_config_dir, 'urlwatch.yaml')
    urlwatch_urls_file = os.path.join(urlwatch_config_dir, 'urls.yaml')
    urlwatch_hooks_file = os.path.join(urlwatch_config_dir, 'hooks.py')
    urlwatch_cache_dir = AppDirs('urlwatch').user_cache_dir
    urlwatch_cache_file = os.path.join(urlwatch_cache_dir, 'cache.db')
    for old_file, new_file in zip((urlwatch_config_file, urlwatch_urls_file, urlwatch_hooks_file, urlwatch_cache_file),
                                  (config_file, jobs_file, hooks_file, cache_file)):
        if os.path.isfile(old_file) and not os.path.isfile(new_file):
            import shutil

            os.makedirs(os.path.dirname(new_file), exist_ok=True)
            shutil.copyfile(old_file, new_file)
            logger.warning(f'Copied urlwatch {old_file} to {project_name} {new_file}')

    # TODO migrate XMPP password in keyring


def main() -> None:
    """The program's entry point"""
    # make sure that DeprecationWarnings are displayed from all modules (otherwise only those in __main__ are)
    warnings.filterwarnings(action='always', category=DeprecationWarning)

    # The config, jobs, hooks and cache files
    config_file = os.path.join(config_dir, 'config.yaml')
    jobs_file = os.path.join(config_dir, 'jobs.yaml')
    hooks_file = os.path.join(config_dir, 'hooks.py')
    cache_file = os.path.join(cache_dir, 'cache.db')

    # migrate legacy urlwatch 2.21 files
    migrate_from_urlwatch(config_file, jobs_file, hooks_file, cache_file)

    # load config files
    command_config = CommandConfig(project_name, config_dir, bindir, prefix, config_file, jobs_file, hooks_file,
                                   cache_file, verbose=False)

    # set up the logger
    setup_logger(command_config.verbose)

    # check for directory of config files entered in cli
    if (not os.path.isfile(command_config.config)
            and command_config.config == os.path.basename(command_config.config)
            and os.path.isfile(os.path.join(command_config.config_dir, os.path.basename(command_config.config)))):
        command_config.config = os.path.join(command_config.config_dir, os.path.basename(command_config.config))
    if not command_config.config.endswith('.yaml'):
        if os.path.isfile(command_config.config + '.yaml'):
            command_config.config += '.yaml'
        elif (command_config.config == os.path.basename(command_config.config) and os.path.isfile(
              os.path.join(command_config.config_dir, os.path.basename(command_config.config + '.yaml')))):
            command_config.config = os.path.join(command_config.config_dir,
                                                 os.path.basename(command_config.config + '.yaml'))
    if (not os.path.isfile(command_config.jobs)
            and command_config.jobs == os.path.basename(command_config.jobs)
            and os.path.isfile(os.path.join(command_config.config_dir, os.path.basename(command_config.jobs)))):
        command_config.jobs = os.path.join(command_config.config_dir, os.path.basename(command_config.jobs))
    if not command_config.jobs.endswith('.yaml'):
        if os.path.isfile(command_config.jobs + '.yaml'):
            command_config.jobs += '.yaml'
        elif (command_config.jobs == os.path.basename(command_config.jobs) and os.path.isfile(
                os.path.join(command_config.config_dir, os.path.basename(command_config.jobs + '.yaml')))):
            command_config.jobs = os.path.join(command_config.config_dir,
                                               os.path.basename(command_config.jobs + '.yaml'))
    if (not os.path.isfile(command_config.hooks)
            and command_config.hooks == os.path.basename(command_config.hooks)
            and os.path.isfile(os.path.join(command_config.config_dir, os.path.basename(command_config.hooks)))):
        command_config.hooks = os.path.join(command_config.config_dir, os.path.basename(command_config.hooks))

    # setup storage API
    config_storage = YamlConfigStorage(command_config.config)  # storage.py

    if any(command_config.cache.startswith(prefix) for prefix in ('redis://', 'rediss://')):
        cache_storage = CacheRedisStorage(command_config.cache)  # storage.py
    else:
        cache_storage = CacheMiniDBStorage(command_config.cache)  # storage.py

    jobs_storage = JobsYaml(command_config.jobs)  # storage.py

    # setup urlwatch
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)  # main.py
    urlwatch_command = UrlwatchCommand(urlwatcher)  # command.py

    # run urlwatch
    urlwatch_command.run()


if __name__ == '__main__':
    main()
