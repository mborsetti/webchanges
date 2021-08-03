"""The main class.

For the entrypoint, see cli.py.
"""

import logging
from typing import List

from . import __project_name__, __version__
from .config import CommandConfig
from .handler import Report
from .jobs import JobBase
from .storage import CacheStorage, YamlConfigStorage, YamlJobsStorage
from .util import import_module_from_source
from .worker import run_jobs
from ._vendored.packaging_version import parse as parse_version


import requests

logger = logging.getLogger(__name__)


class Urlwatch(object):
    """The main class."""

    def __init__(
        self,
        urlwatch_config: CommandConfig,
        config_storage: YamlConfigStorage,
        cache_storage: CacheStorage,
        jobs_storage: YamlJobsStorage,
    ) -> None:
        """

        :param urlwatch_config: The CommandConfig object containing the program run information.
        :param config_storage: The YamlConfigStorage object containing the configuration information.
        :param cache_storage: The CacheStorage object containing snapshot database information
        :param jobs_storage: The YamlJobsStorage object containing the jobs information.
        """

        self.urlwatch_config = urlwatch_config

        logger.info(f'Config file is {self.urlwatch_config.config}')
        logger.info(f'Jobs file is {self.urlwatch_config.jobs}')
        logger.info(f'Hooks file is {self.urlwatch_config.hooks}')
        logger.info(f'Database file is {self.urlwatch_config.cache}')

        self.config_storage = config_storage
        self.cache_storage = cache_storage
        self.jobs_storage = jobs_storage

        self.report = Report(self)
        self.jobs: List[JobBase] = []

        self._latest_release: str = None  # type: ignore[assignment]

        self.check_directories()

        if not self.urlwatch_config.edit_hooks:
            self.load_hooks()

        if not self.urlwatch_config.edit:
            self.load_jobs()

    def check_directories(self) -> None:
        """Check whether the configuration and jobs files directories exist. Create them and write default configuration
        files if one not found.
        """
        if (
            not (self.urlwatch_config.config and self.urlwatch_config.jobs)
            and not self.urlwatch_config.config_path.is_dir()
        ):
            self.urlwatch_config.config_path.mkdir(parents=True)
            if not self.urlwatch_config.config.is_file():
                self.config_storage.write_default_config(self.urlwatch_config.config)
                print(
                    f'A default config has been written to {self.urlwatch_config.config}.'
                    f'Use "{self.urlwatch_config.project_name} --edit-config" to customize it.'
                )

    def load_hooks(self) -> None:
        """Load hooks.py file."""
        if self.urlwatch_config.hooks.is_file():
            import_module_from_source('hooks', self.urlwatch_config.hooks)

    def load_jobs(self) -> None:
        """Load jobs from the file."""
        if self.urlwatch_config.jobs.is_file():
            jobs = self.jobs_storage.load_secure()
            logger.info(f'Found {len(jobs)} jobs')
        else:
            logger.warning(f'No jobs file found at {self.urlwatch_config.jobs}')
            jobs = []

        self.jobs = jobs

    def get_new_release_version(self) -> str:
        """Check PyPi to see if we're running the latest version.  Memoized.

        :returns: Empty string if no higher version is available, otherwise the new version number.
        """
        if self._latest_release is not None:
            return self._latest_release

        r = requests.get(f'https://pypi.org/pypi/{__project_name__}/json', timeout=1)
        if r.ok:
            latest_release: str = list(r.json()['releases'].keys())[-1]
            if parse_version(latest_release) > parse_version(__version__):
                self._latest_release = latest_release
            else:
                self._latest_release = ''

        return self._latest_release

    def run_jobs(self) -> None:
        """Run all jobs."""
        run_jobs(self)

    def close(self) -> None:
        """Finalizer. Create reports ands close snapshots database."""
        self.report.finish()
        self.cache_storage.close()
