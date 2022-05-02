"""The main class.

For the entrypoint, see cli.py.
"""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import logging
from typing import List, Optional, Tuple, Union

from .config import CommandConfig
from .handler import Report
from .jobs import JobBase
from .storage import CacheStorage, YamlConfigStorage, YamlJobsStorage
from .util import get_new_version_number, import_module_from_source
from .worker import run_jobs

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
        """Load hooks file."""
        logger.info('Loading hooks file')
        if self.urlwatch_config.hooks.is_file():
            import_module_from_source('hooks', self.urlwatch_config.hooks)

    def load_jobs(self) -> None:
        """Load jobs from the file into self.jobs.

        :raises SystemExit: If job is not found, setting argument to 1.
        """
        if self.urlwatch_config.jobs.is_file():
            jobs = self.jobs_storage.load_secure()
            logger.info(f'Loaded {len(jobs)} jobs')
        else:
            print(f'Jobs file not found: {self.urlwatch_config.jobs}')
            raise SystemExit(1)

        self.jobs = jobs

    def get_new_release_version(self, timeout: Optional[Union[float, Tuple[float, float]]] = None) -> str:
        """Check PyPi to see if we're running the latest version. Memoized.

        :returns: Empty string if no higher version is available, otherwise the new version number.
        """
        if self._latest_release is not None:
            return self._latest_release

        self._latest_release = get_new_version_number(timeout)
        return self._latest_release

    def run_jobs(self) -> None:
        """Run all jobs."""
        run_jobs(self)

    def close(self) -> None:
        """Finalizer. Create reports ands close snapshots database."""
        self.report.finish(jobs_file=self.jobs_storage.filename)
        self.cache_storage.close()
