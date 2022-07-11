"""Test the handling of jobs."""

import importlib.util
import os
import tempfile
import warnings
from pathlib import Path

import pytest

from webchanges import __project_name__ as project_name
from webchanges.config import CommandConfig
from webchanges.jobs import JobBase, ShellJob, UrlJob
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, DEFAULT_CONFIG, YamlConfigStorage, YamlJobsStorage
from webchanges.util import import_module_from_source

minidb_is_installed = importlib.util.find_spec('minidb') is not None

if minidb_is_installed:
    from webchanges.storage_minidb import CacheMiniDBStorage

minidb_required = pytest.mark.skipif(not minidb_is_installed, reason="requires 'minidb' package to be installed")

here = Path(__file__).parent
data_path = here.joinpath('data')

config_file = data_path.joinpath('config.yaml')
cache_file = ':memory:'
hooks_file = Path('')


def test_required_classattrs_in_subclasses():
    for kind, subclass in JobBase.__subclasses__.items():
        assert hasattr(subclass, '__kind__')
        assert hasattr(subclass, '__required__')
        assert hasattr(subclass, '__optional__')


def test_save_load_jobs():
    jobs = [
        UrlJob(name='news', url='https://news.orf.at/'),
        ShellJob(name='list homedir', command='ls ~'),
        ShellJob(name='list proc', command='ls /proc'),
    ]

    # tempfile.NamedTemporaryFile() doesn't work on Windows
    # because the returned file object cannot be opened again
    fd, name = tempfile.mkstemp()
    name = Path(name)
    YamlJobsStorage([name]).save(jobs)
    jobs2 = YamlJobsStorage([name]).load()
    os.chmod(name, 0o777)  # nosec: B103 Chmod setting a permissive mask 0o777 on file (name).
    jobs3 = YamlJobsStorage([name]).load_secure()
    os.close(fd)
    os.remove(name)

    assert len(jobs2) == len(jobs)
    # Assert that the shell jobs have been removed due to secure loading in Linux
    if os.name == 'linux':
        assert len(jobs3) == 1


def test_load_config_yaml():
    if config_file.is_file():
        config = YamlConfigStorage(config_file)
        config.load()
        assert config is not None
        assert config.config is not None
        assert config.config == DEFAULT_CONFIG
    else:
        warnings.warn(f'{config_file} not found', UserWarning)


def test_load_jobs_yaml():
    jobs_file = data_path.joinpath('jobs.yaml')
    if jobs_file.is_file():
        assert len(YamlJobsStorage([jobs_file]).load_secure()) > 0
    else:
        warnings.warn(f'{jobs_file} not found', UserWarning)


def test_duplicates_in_jobs_yaml():
    jobs_file = data_path.joinpath('jobs-duplicate_url.broken_yaml')
    if jobs_file.is_file():
        with pytest.raises(ValueError) as pytest_wrapped_e:
            YamlJobsStorage([jobs_file]).load_secure()
        assert str(pytest_wrapped_e.value).startswith(
            'Each job must have a unique URL/command (for URLs, append #1, #2, etc. to make them unique):'
            '\n   • https://dupe_1\n   • https://dupe_2\n   in jobs file '
        )
    else:
        warnings.warn(f'{jobs_file} not found', UserWarning)


def test_load_hooks_py():
    hooks_file = data_path.joinpath('hooks_test.py')
    if hooks_file.is_file():
        import_module_from_source('hooks', hooks_file)
    else:
        warnings.warn(f'{hooks_file} not found', UserWarning)


def test_run_watcher_sqlite3():
    jobs_file = data_path.joinpath('jobs.yaml')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    cache_storage = CacheSQLite3Storage(cache_file)
    try:
        urlwatch_config = CommandConfig([], project_name, here, config_file, jobs_file, hooks_file, cache_file)
        urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)
        urlwatcher.run_jobs()
    finally:
        cache_storage.close()


@minidb_required
def test_run_watcher_minidb():
    jobs_file = data_path.joinpath('jobs.yaml')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    cache_storage = CacheMiniDBStorage(cache_file)
    try:
        urlwatch_config = CommandConfig([], project_name, here, config_file, jobs_file, hooks_file, cache_file)
        urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)
        urlwatcher.run_jobs()
    finally:
        cache_storage.close()


def prepare_retry_test_sqlite3():
    jobs_file = data_path.joinpath('jobs-invalid_url.yaml')

    config_storage = YamlConfigStorage(config_file)
    cache_storage = CacheSQLite3Storage(cache_file)
    jobs_storage = YamlJobsStorage([jobs_file])

    urlwatch_config = CommandConfig([], project_name, here, config_file, jobs_file, hooks_file, cache_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)

    return urlwatcher, cache_storage


def test_number_of_tries_in_cache_is_increased_sqlite3():
    urlwatcher, cache_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        old_data, timestamp, tries, etag = cache_storage.load(guid)

        assert tries == 0

        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        old_data, timestamp, tries, etag = cache_storage.load(guid)

        assert tries == 2
        assert urlwatcher.report.job_states[-1].verb == 'error'
    finally:
        cache_storage.close()


def test_report_error_when_out_of_tries_sqlite3():
    urlwatcher, cache_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        old_data, timestamp, tries, etag = cache_storage.load(guid)
        assert tries == 0

        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        report = urlwatcher.report
        assert report.job_states[-1].verb == 'error'
    finally:
        cache_storage.close()


def test_reset_tries_to_zero_when_successful_sqlite3():
    urlwatcher, cache_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        old_data, timestamp, tries, etag = cache_storage.load(guid)
        assert tries == 0

        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        old_data, timestamp, tries, etag = cache_storage.load(guid)
        assert tries == 1

        # use an uri that definitely exists
        job = urlwatcher.jobs[0]
        job.url = Path(__file__).as_uri()
        guid = job.get_guid()

        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        old_data, timestamp, tries, etag = cache_storage.load(guid)
        assert tries == 0
    finally:
        cache_storage.close()


@minidb_required
def prepare_retry_test_minidb():
    jobs_file = data_path.joinpath('jobs-invalid_url.yaml')
    config_storage = YamlConfigStorage(config_file)
    cache_storage = CacheMiniDBStorage(cache_file)
    jobs_storage = YamlJobsStorage([jobs_file])

    urlwatch_config = CommandConfig([], project_name, here, config_file, jobs_file, hooks_file, cache_file)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)

    return urlwatcher, cache_storage


@minidb_required
def test_number_of_tries_in_cache_is_increased_minidb():
    urlwatcher, cache_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        old_data, timestamp, tries, etag = cache_storage.load(job.get_guid())
        assert tries == 0

        urlwatcher.run_jobs()
        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        old_data, timestamp, tries, etag = cache_storage.load(job.get_guid())

        assert tries == 2
        assert urlwatcher.report.job_states[-1].verb == 'error'
    finally:
        cache_storage.close()


@minidb_required
def test_report_error_when_out_of_tries_minidb():
    urlwatcher, cache_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        old_data, timestamp, tries, etag = cache_storage.load(job.get_guid())
        assert tries == 0

        urlwatcher.run_jobs()
        urlwatcher.run_jobs()

        report = urlwatcher.report
        assert report.job_states[-1].verb == 'error'
    finally:
        cache_storage.close()


@minidb_required
def test_reset_tries_to_zero_when_successful_minidb():
    urlwatcher, cache_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        old_data, timestamp, tries, etag = cache_storage.load(job.get_guid())
        assert tries == 0

        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        old_data, timestamp, tries, etag = cache_storage.load(job.get_guid())
        assert tries == 1

        # use an url that definitely exists
        job = urlwatcher.jobs[0]
        job.url = data_path.joinpath('jobs.yaml').as_uri()

        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        old_data, timestamp, tries, etag = cache_storage.load(job.get_guid())
        assert tries == 0
    finally:
        cache_storage.close()
