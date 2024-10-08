"""The main class.

For the entry point, see main() in the cli module."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import logging

from webchanges import __project_name__
from webchanges.config import CommandConfig
from webchanges.handler import Report
from webchanges.jobs import JobBase
from webchanges.storage import SsdbStorage, YamlConfigStorage, YamlJobsStorage
from webchanges.util import get_new_version_number
from webchanges.worker import run_jobs

logger = logging.getLogger(__name__)


class Urlwatch:
    """The main class."""

    def __init__(
        self,
        urlwatch_config: CommandConfig,
        config_storage: YamlConfigStorage,
        ssdb_storage: SsdbStorage,
        jobs_storage: YamlJobsStorage,
    ) -> None:
        """

        :param urlwatch_config: The CommandConfig object containing the program run information.
        :param config_storage: The YamlConfigStorage object containing the configuration information.
        :param ssdb_storage: The CacheStorage object containing snapshot database information
        :param jobs_storage: The YamlJobsStorage object containing information about the jobs.
        """

        self.urlwatch_config = urlwatch_config

        self.config_storage = config_storage
        self.ssdb_storage = ssdb_storage
        self.jobs_storage = jobs_storage

        self.report = Report(self)
        self.jobs: list[JobBase] = []

        self._latest_release: str | bool | None = None

        self.check_directories()

        if not self.urlwatch_config.edit:
            self.load_jobs()

    def check_directories(self) -> None:
        """Check whether the configuration and jobs files directories exist. Create them and write default configuration
        files if one not found.
        """
        if (
            not (self.urlwatch_config.config_file and self.urlwatch_config.jobs_files)
            and not self.urlwatch_config.config_path.is_dir()
        ):
            self.urlwatch_config.config_path.mkdir(parents=True)
            if not self.urlwatch_config.config_file.is_file():
                self.config_storage.write_default_config(self.urlwatch_config.config_file)
                print(
                    f'A default config has been written to {self.urlwatch_config.config_file}.'
                    f'Use "{__project_name__} --edit-config" to customize it.'
                )

    def load_jobs(self) -> None:
        """Load jobs from the file(s) into self.jobs.

        :raises SystemExit: If job is not found, setting argument to 1.
        """
        if any(f.is_file() for f in self.urlwatch_config.jobs_files):
            jobs = self.jobs_storage.load_secure()
        else:
            print(f"Jobs file not found: {' ,'.join((str(file) for file in self.urlwatch_config.jobs_files))}")
            raise SystemExit(1)

        self.jobs = jobs

    def get_new_release_version(self, timeout: float | None = None) -> str | bool:
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
        self.ssdb_storage.close()
