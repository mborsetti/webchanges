"""Test the handling of jobs."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import warnings
from pathlib import Path
from typing import Callable, cast

import pytest

from webchanges.config import CommandConfig
from webchanges.jobs import JobBase, ShellJob, UrlJob
from webchanges.main import Urlwatch
from webchanges.storage import DEFAULT_CONFIG, SsdbSQLite3Storage, YamlConfigStorage, YamlJobsStorage
from webchanges.util import import_module_from_source

minidb_is_installed = importlib.util.find_spec('minidb') is not None

if minidb_is_installed:
    from webchanges.storage_minidb import SsdbMiniDBStorage

minidb_required = cast(
    Callable[[Callable], Callable],
    pytest.mark.skipif(not minidb_is_installed, reason="requires 'minidb' package to be installed"),
)

here = Path(__file__).parent
data_path = here.joinpath('data')

config_file = data_path.joinpath('config.yaml')
ssdb_file = ':memory:'
hooks_file = Path('')
ssdb_storage: SsdbSQLite3Storage


def cleanup(request: pytest.FixtureRequest) -> None:
    """Cleanup once we are finished."""

    def finalizer() -> None:
        """Cleanup once we are finished."""
        ssdb_storage.delete_all()

    request.addfinalizer(finalizer)


def test_required_classattrs_in_subclasses() -> None:
    for kind, subclass in JobBase.__subclasses__.items():
        assert hasattr(subclass, '__kind__')
        assert hasattr(subclass, '__required__')
        assert hasattr(subclass, '__optional__')


def test_save_load_jobs() -> None:
    jobs = [
        UrlJob(name='news', url='https://news.orf.at/'),
        ShellJob(name='list homedir', command='ls ~'),
        ShellJob(name='list proc', command='ls /proc'),
    ]

    # tempfile.NamedTemporaryFile() doesn't work on Windows
    # because the returned file object cannot be opened again
    fd, tmpfile = tempfile.mkstemp()
    name = Path(tmpfile)
    YamlJobsStorage([name]).save(jobs)
    jobs2 = YamlJobsStorage([name]).load()
    os.chmod(name, 0o777)  # noqa: S103 Chmod setting a permissive mask 0o777 on file (name).
    jobs3 = YamlJobsStorage([name]).load_secure()
    os.close(fd)
    os.remove(name)

    assert len(jobs2) == len(jobs)
    # Assert that the shell jobs have been removed due to secure loading in Linux
    if os.name == 'linux':
        assert len(jobs3) == 1


def test_load_config_yaml() -> None:
    if config_file.is_file():
        config = YamlConfigStorage(config_file)
        config.load()
        assert config is not None
        assert config.config is not None
        assert config.config == DEFAULT_CONFIG
    else:
        warnings.warn(f'{config_file} not found', UserWarning)


def test_load_jobs_yaml() -> None:
    jobs_file = data_path.joinpath('jobs.yaml')
    if jobs_file.is_file():
        assert len(YamlJobsStorage([jobs_file]).load_secure()) > 0
    else:
        warnings.warn(f'{jobs_file} not found', UserWarning)


def test_duplicates_in_jobs_yaml() -> None:
    jobs_file = data_path.joinpath('jobs-duplicate_url.broken_yaml')
    if jobs_file.is_file():
        with pytest.raises(ValueError) as pytest_wrapped_e:
            YamlJobsStorage([jobs_file]).load_secure()
        expected = '\n'.join(
            [
                'Each job must have a unique URL/command (for URLs, append #1, #2, etc. to make them unique):',
                '   • https://dupe_1',
                '   • https://dupe_2',
                '   ',
                '   in jobs file ',
            ]
        )
        assert str(pytest_wrapped_e.value)[: len(expected)] == expected
    else:
        warnings.warn(f'{jobs_file} not found', UserWarning)


def test_disabled_job() -> None:
    jobs_file = data_path.joinpath('jobs-disabled.yaml')

    urlwatch_config = CommandConfig(
        [],
        here,
        config_file,
        jobs_file,
        hooks_file,
        ssdb_file,  # type: ignore[arg-type]
    )
    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # type: ignore[arg-type]
    ssdb_storage.delete_all()
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
    urlwatcher.report.job_states = []
    try:
        urlwatcher.run_jobs()

        assert len(urlwatcher.report.job_states) == 1
        assert urlwatcher.report.job_states[0].new_data == 'enabled job\n'
    finally:
        ssdb_storage.delete_all()


def test_load_hooks_py() -> None:
    hooks_file = data_path.joinpath('hooks_example.py')
    if hooks_file.is_file():
        import_module_from_source('hooks', hooks_file)
    else:
        warnings.warn(f'{hooks_file} not found', UserWarning)


def test_run_watcher_sqlite3() -> None:
    jobs_file = data_path.joinpath('jobs.yaml')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # type: ignore[arg-type]
    try:
        urlwatch_config = CommandConfig(
            [],
            here,
            config_file,
            jobs_file,
            hooks_file,
            ssdb_file,  # type: ignore[arg-type]
        )
        urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
        urlwatcher.run_jobs()
    finally:
        ssdb_storage.delete_all()


@minidb_required  # type: ignore[misc]
def test_run_watcher_minidb() -> None:
    jobs_file = data_path.joinpath('jobs.yaml')

    config_storage = YamlConfigStorage(config_file)
    jobs_storage = YamlJobsStorage([jobs_file])
    ssdb_storage = SsdbMiniDBStorage(ssdb_file)  # type: ignore[arg-type]
    try:
        urlwatch_config = CommandConfig(
            [],
            here,
            config_file,
            jobs_file,
            hooks_file,
            ssdb_file,  # type: ignore[arg-type]
        )
        urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)
        urlwatcher.run_jobs()
    finally:
        ssdb_storage.close()


def prepare_retry_test_sqlite3() -> tuple[Urlwatch, SsdbSQLite3Storage]:
    jobs_file = data_path.joinpath('jobs-invalid_url.yaml')

    config_storage = YamlConfigStorage(config_file)
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # type: ignore[arg-type]
    jobs_storage = YamlJobsStorage([jobs_file])

    urlwatch_config = CommandConfig(
        [],
        here,
        config_file,
        jobs_file,
        hooks_file,
        ssdb_file,  # type: ignore[arg-type]
    )
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)

    return urlwatcher, ssdb_storage


def test_number_of_tries_in_cache_is_increased_sqlite3() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        snapshot = ssdb_storage.load(guid)

        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)

        snapshot = ssdb_storage.load(guid)

        assert snapshot.tries == 2
        assert urlwatcher.report.job_states[-1].verb == 'error'
    finally:
        ssdb_storage.delete_all()


def test_report_error_when_out_of_tries_sqlite3() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        snapshot = ssdb_storage.load(guid)
        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)
        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)

        report = urlwatcher.report
        assert report.job_states[-1].verb == 'error'
    finally:
        ssdb_storage.delete_all()


def test_reset_tries_to_zero_when_successful_sqlite3() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_sqlite3()
    try:
        guid = urlwatcher.jobs[0].get_guid()
        snapshot = ssdb_storage.load(guid)
        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)

        snapshot = ssdb_storage.load(guid)
        assert snapshot.tries == 1

        # use an uri that definitely exists
        job = urlwatcher.jobs[0]
        job.url = Path(__file__).as_uri()
        guid = job.get_guid()

        urlwatcher.run_jobs()
        ssdb_storage._copy_temp_to_permanent(delete=True)

        snapshot = ssdb_storage.load(guid)
        assert snapshot.tries == 0
    finally:
        ssdb_storage.delete_all()


@minidb_required  # type: ignore[misc]
def prepare_retry_test_minidb() -> tuple[Urlwatch, SsdbMiniDBStorage]:
    jobs_file = data_path.joinpath('jobs-invalid_url.yaml')
    config_storage = YamlConfigStorage(config_file)
    ssdb_storage = SsdbMiniDBStorage(ssdb_file)  # type: ignore[arg-type]
    jobs_storage = YamlJobsStorage([jobs_file])

    urlwatch_config = CommandConfig(
        [],
        here,
        config_file,
        jobs_file,
        hooks_file,
        ssdb_file,  # type: ignore[arg-type]
    )
    urlwatcher = Urlwatch(urlwatch_config, config_storage, ssdb_storage, jobs_storage)

    return urlwatcher, ssdb_storage


@minidb_required  # type: ignore[misc]
def test_number_of_tries_in_cache_is_increased_minidb() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())
        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())

        assert snapshot.tries == 2
        assert urlwatcher.report.job_states[-1].verb == 'error'
    finally:
        ssdb_storage.close()


@minidb_required  # type: ignore[misc]
def test_report_error_when_out_of_tries_minidb() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())
        assert snapshot.tries == 0

        urlwatcher.run_jobs()
        urlwatcher.run_jobs()

        report = urlwatcher.report
        assert report.job_states[-1].verb == 'error'
    finally:
        ssdb_storage.close()


@minidb_required  # type: ignore[misc]
def test_reset_tries_to_zero_when_successful_minidb() -> None:
    urlwatcher, ssdb_storage = prepare_retry_test_minidb()
    try:
        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())
        assert snapshot.tries == 0

        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())
        assert snapshot.tries == 1

        # use an url that definitely exists
        job = urlwatcher.jobs[0]
        job.url = data_path.joinpath('jobs.yaml').as_uri()

        urlwatcher.run_jobs()

        job = urlwatcher.jobs[0]
        snapshot = ssdb_storage.load(job.get_guid())
        assert snapshot.tries == 0
    finally:
        ssdb_storage.close()
