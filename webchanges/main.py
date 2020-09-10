# for the entrypoint, see cli.py

import logging
import os

from .handler import Report
from .util import import_module_from_source
from .worker import run_jobs

logger = logging.getLogger(__name__)


class Urlwatch(object):
    def __init__(self, urlwatch_config, config_storage, cache_storage, jobs_storage):

        self.urlwatch_config = urlwatch_config

        logger.info('Using %s as jobs file', self.urlwatch_config.jobs)
        logger.info('Using %s for hooks', self.urlwatch_config.hooks)
        logger.info('Using %s as cache database', self.urlwatch_config.cache)

        self.config_storage = config_storage
        self.cache_storage = cache_storage
        self.jobs_storage = jobs_storage

        self.report = Report(self)
        self.jobs = None

        self.check_directories()

        if not self.urlwatch_config.edit_hooks:
            self.load_hooks()

        if not self.urlwatch_config.edit:
            self.load_jobs()

    def check_directories(self):
        if not os.path.isdir(self.urlwatch_config.config_dir):
            os.makedirs(self.urlwatch_config.config_dir)
        if not os.path.exists(self.urlwatch_config.config):
            self.config_storage.write_default_config(self.urlwatch_config.config)
            print(f"""
    A default config has been written to {self.urlwatch_config.config}.
    Use "{self.urlwatch_config.project_name} --edit-config" to customize it.
        """)

    def load_hooks(self):
        if os.path.exists(self.urlwatch_config.hooks):
            import_module_from_source('hooks', self.urlwatch_config.hooks)

    def load_jobs(self):
        if os.path.isfile(self.urlwatch_config.jobs):
            jobs = self.jobs_storage.load_secure()
            logger.info(f'Found {len(jobs)} jobs')
        else:
            logger.warning(f'No jobs file found at {self.urlwatch_config.jobs}')
            jobs = []

        self.jobs = jobs

    def run_jobs(self):
        run_jobs(self)

    def close(self):
        self.report.finish()
        self.cache_storage.close()
