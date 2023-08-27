"""Test storage.

To test Redis, set an environment variable REDIS_URI with the URI to the Redis server.  E.g.:
$ export REDIS_URI=redis://localhost:6379
"""
from __future__ import annotations

import copy
import importlib.util
import os
import shutil
import sys
import tempfile
import time
from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pytest

from webchanges import __docs_url__, __project_name__
from webchanges.config import CommandConfig
from webchanges.main import Urlwatch
from webchanges.storage import (
    BaseTextualFileStorage,
    CacheDirStorage,
    CacheRedisStorage,
    CacheSQLite3Storage,
    CacheStorage,
    Snapshot,
    YamlConfigStorage,
    YamlJobsStorage,
)
from webchanges.util import import_module_from_source

minidb_is_installed = importlib.util.find_spec('minidb') is not None
minidb_required = pytest.mark.skipif(not minidb_is_installed, reason="requires 'minidb' package to be installed")

tmp_path = Path(tempfile.mkdtemp())

here = Path(__file__).parent
data_path = here.joinpath('data')
config_file = data_path.joinpath('config.yaml')
hooks_file = Path('')
config_storage = YamlConfigStorage(config_file)


DATABASE_ENGINES: Tuple[CacheStorage, ...] = (
    CacheDirStorage(tmp_path),
    CacheSQLite3Storage(':memory:'),
)

if os.getenv('REDIS_URI') and importlib.util.find_spec('redis') is not None:
    DATABASE_ENGINES += (CacheRedisStorage(os.getenv('REDIS_URI', '')),)

if importlib.util.find_spec('minidb') is not None:
    from webchanges.storage_minidb import CacheMiniDBStorage

    cache_file = ':memory:'
    DATABASE_ENGINES += (CacheMiniDBStorage(cache_file),)
else:
    CacheMiniDBStorage = type(None)  # type: ignore[misc,assignment]


def test_all_database_engines() -> None:
    if not os.getenv('REDIS_URI') or importlib.util.find_spec('redis') is None:
        pytest.mark.xfail(
            'Cannot test the CacheRedisStorage class. The REDIS_URI environment variable is not set or '
            "the 'redis' package is not installed"
        )
    if importlib.util.find_spec('minidb') is None:
        pytest.mark.xfail("Cannot test the CacheMiniDBStorage class. The 'minidb' package is not installed")


def prepare_storage_test(
    cache_storage: CacheStorage, config_args: Optional[dict] = None, jobs_file: Optional[Path] = None
) -> Tuple[Urlwatch, CacheStorage, CommandConfig]:
    """Set up storage."""
    cache_file = cache_storage.filename

    if hasattr(cache_storage, 'flushdb'):
        cache_storage.flushdb()

    if jobs_file is None:
        jobs_file = data_path.joinpath('jobs-time.yaml')

    command_config = CommandConfig([], __project_name__, here, config_file, jobs_file, hooks_file, cache_file)
    if config_args:
        for k, v in config_args.items():
            setattr(command_config, k, v)

    jobs_storage = YamlJobsStorage([jobs_file])
    urlwatcher = Urlwatch(command_config, config_storage, cache_storage, jobs_storage)

    if os.name == 'nt':
        urlwatcher.jobs[0].command = 'echo %time% %random%'

    return urlwatcher, cache_storage, command_config


def test_check_for_unrecognized_keys() -> None:
    """Test if config has keys not in DEFAULT_CONFIG (i.e. typos)."""
    config_storage = YamlConfigStorage(config_file)
    config = config_storage.parse(config_file)
    config['this_is_a_typo'] = True
    with pytest.warns(RuntimeWarning) as pytest_wrapped_e:
        config_storage.check_for_unrecognized_keys(config)
    if isinstance(pytest_wrapped_e.list[0].message, Warning):
        message = pytest_wrapped_e.list[0].message.args[0]
    else:
        message = pytest_wrapped_e.list[0].message
    assert message == (
        f'Found unrecognized directive(s) in the configuration file {config_file}:\n'
        f'this_is_a_typo: true\nCheck for typos (documentation at {__docs_url__})\n'
    )


def test_check_for_unrecognized_keys_hooks() -> None:
    """Test config with keys that are in hooks."""
    config_storage = YamlConfigStorage(config_file)
    config = config_storage.parse(config_file)
    config['report']['made_up_key'] = True
    with pytest.warns(RuntimeWarning) as pytest_wrapped_e:
        config_storage.check_for_unrecognized_keys(config)
    if isinstance(pytest_wrapped_e.list[0].message, Warning):
        message = pytest_wrapped_e.list[0].message.args[0]
    else:
        message = pytest_wrapped_e.list[0].message
    assert message == (
        f'Found unrecognized directive(s) in the configuration file {config_file}:\n'
        f'report:\n  made_up_key: true\nCheck for typos (documentation at {__docs_url__})\n'
    )
    import_module_from_source('hooks', data_path.joinpath('hooks_example.py'))
    config_storage.check_for_unrecognized_keys(config)


def test_empty_config_file() -> None:
    """Test if config is empyty and DEFAULT_CONFIG is used."""
    config_storage = YamlConfigStorage('')
    config_storage.load()
    assert config_storage.config['report']


def test_jobs_parse() -> None:
    """Test if a job is a shell job."""
    jobs_file = data_path.joinpath('jobs-time.yaml')
    jobs_storage = YamlJobsStorage([jobs_file])
    jobs = jobs_storage.parse(jobs_file)
    assert len(jobs) == 1
    assert jobs[0].command == "perl -MTime::HiRes -e 'printf \"%f\n\",Time::HiRes::time()'"


def test_check_for_shell_job() -> None:
    """Test if a job is a shell job."""
    jobs_file = data_path.joinpath('jobs-is_shell_job.yaml')
    # TODO the below generates PermissionError: [Errno 1] Operation not permitted when run by GitHub Actions in macOS
    # if os.name != 'nt':
    #     os.chown(jobs_file, 65534, 65534)
    jobs_storage = YamlJobsStorage([jobs_file])
    jobs_storage.load_secure()
    # jobs = jobs_storage.load_secure()
    # if os.name != 'nt':
    #     assert len(jobs) == 1


def test_legacy_slack_keys() -> None:
    """Test if legacy report 'slack' keys don't trigger a ValueError even if not in DEFAULT_CONFIG."""
    config_storage = YamlConfigStorage(config_file)
    config = config_storage.parse(config_file)
    config['report']['slack'] = {'enabled': False}
    config_storage.check_for_unrecognized_keys(config)


# @py37_required
# CacheSQLite3Storage.keep_latest() requires Python 3.7 to work (returns 0 otherwise).
@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_keep_latest(database_engine: CacheStorage) -> None:
    if not hasattr(database_engine, 'keep_latest'):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} has no keep_latest method')
    else:
        urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

        # run twice
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        assert timestamps[1] < timestamps[0]

        # check that history matches load
        snapshot = cache_storage.load(guid)
        assert snapshot.data == list(history.keys())[0]
        assert snapshot.timestamp == list(history.values())[0]

        # only keep last one
        if isinstance(cache_storage, CacheSQLite3Storage):
            cache_storage.keep_latest(1)
            history = cache_storage.get_history_data(guid)
            assert len(history) == 1
            timestamp = list(history.values())[0]
            # is it the most recent?
            assert timestamp == timestamps[0]


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean(database_engine: CacheStorage) -> None:
    if isinstance(database_engine, CacheDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

        # run twice
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        if not isinstance(database_engine, CacheMiniDBStorage):  # rounds to the closest second
            assert timestamps[1] < timestamps[0]

        # check that history matches load
        snapshot = cache_storage.load(guid)
        assert snapshot.data == list(history.keys())[0]
        assert snapshot.timestamp == list(history.values())[0]

        cache_storage.clean(guid, 1)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1
        timestamp = list(history.values())[0]
        # is it the most recent?
        assert timestamp == timestamps[0]


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_gc(database_engine: CacheStorage) -> None:
    urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

    # run once
    urlwatcher.run_jobs()
    if hasattr(cache_storage, '_copy_temp_to_permanent'):
        cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

    cache_storage.gc([])
    guid = urlwatcher.jobs[0].get_guid()
    history = cache_storage.get_history_data(guid)
    assert history == {}


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_gc_delete_1_of_2(database_engine: CacheStorage) -> None:
    urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

    # add second job
    new_job = copy.deepcopy(urlwatcher.jobs[0])
    new_job.set_base_location(new_job.get_location() + ' #')
    urlwatcher.jobs.append(new_job)

    # run twice
    for i in range(3):
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
    if hasattr(cache_storage, '_copy_temp_to_permanent'):
        cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

    guid = urlwatcher.jobs[0].get_guid()
    cache_storage.gc([guid])
    history = cache_storage.get_history_data(guid)
    assert len(history) == 1

    guid_2 = urlwatcher.jobs[1].get_guid()
    history = cache_storage.get_history_data(guid_2)
    assert history == {}


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_gc_delete_2_of_4(database_engine: CacheStorage) -> None:
    if isinstance(database_engine, CacheDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    if isinstance(database_engine, CacheRedisStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} does not support this')
    if isinstance(database_engine, CacheMiniDBStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} not implemented')

    urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

    # add second job
    new_job = copy.deepcopy(urlwatcher.jobs[0])
    new_job.set_base_location(new_job.get_location() + ' #')
    urlwatcher.jobs.append(new_job)

    # run four times
    for i in range(5):
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
    if hasattr(cache_storage, '_copy_temp_to_permanent'):
        cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

    guid = urlwatcher.jobs[0].get_guid()
    cache_storage.gc([guid], 2)
    history = cache_storage.get_history_data(guid)
    assert len(history) == 2

    guid_2 = urlwatcher.jobs[1].get_guid()
    history = cache_storage.get_history_data(guid_2)
    assert history == {}


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_cache(database_engine: CacheStorage) -> None:
    if isinstance(database_engine, CacheDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

        # run five times
        for i in range(5):
            if isinstance(database_engine, CacheSQLite3Storage):
                time.sleep(0.0001)
            urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 5
        timestamps = list(history.values())
        # returned in reverse order
        if not isinstance(database_engine, CacheMiniDBStorage):  # rounds to the closest second
            assert timestamps[1] < timestamps[0]

        # clean cache, leaving 3
        if isinstance(database_engine, (CacheSQLite3Storage, CacheMiniDBStorage)):
            cache_storage.clean_cache([guid], 3)
            history = cache_storage.get_history_data(guid)
            assert len(history) == 3
        else:
            with pytest.raises(NotImplementedError):
                cache_storage.clean_cache([guid], 3)

        # clean cache, leaving 1
        cache_storage.clean_cache([guid])
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1

        timestamp = list(history.values())[0]
        # is it the most recent?
        assert timestamp == timestamps[0]


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_and_delete(database_engine: CacheStorage) -> None:
    urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

    # run once
    urlwatcher.run_jobs()
    if hasattr(cache_storage, '_copy_temp_to_permanent'):
        cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

    # clean guid
    guid = urlwatcher.jobs[0].get_guid()
    deleted = cache_storage.clean(guid)
    assert deleted == 0
    history = cache_storage.get_history_data(guid)
    assert len(history) == 1

    # delete guid
    cache_storage.delete(guid)
    history = cache_storage.get_history_data(guid)
    assert len(history) == 0

    # clean too much
    try:
        cache_storage.clean(guid, 10)
    except NotImplementedError:
        pass


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_all(database_engine: CacheStorage) -> None:
    if not hasattr(database_engine, 'clean_all'):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} has no clean_all method')
    else:
        urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

        # run twice
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        if not isinstance(database_engine, CacheMiniDBStorage):  # rounds to the closest second
            assert timestamps[1] <= timestamps[0]

        # clean all
        if isinstance(cache_storage, CacheSQLite3Storage):
            cache_storage.clean_all()
            history = cache_storage.get_history_data(guid)
            assert len(history) == 1
            timestamp = list(history.values())[0]
            # is it the most recent?
            assert timestamp == timestamps[0]


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_cache_no_clean_all(database_engine: CacheStorage) -> None:
    if isinstance(database_engine, CacheDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

        # run twice
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        if not isinstance(database_engine, CacheMiniDBStorage):  # rounds to the closest second
            assert timestamps[1] < timestamps[0]

        # clean cache without using clean_all
        # delattr(CacheSQLite3Storage, 'clean_all')
        cache_storage.clean_cache([guid])
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1
        timestamp = list(history.values())[0]
        # is it the most recent?
        assert timestamp == timestamps[0]


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_delete_latest(database_engine: CacheStorage) -> None:
    if isinstance(database_engine, CacheDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

        # run twice
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2

        # rollback
        try:
            num_del = cache_storage.delete_latest(guid)
        except NotImplementedError:
            pytest.skip(f'database_engine {database_engine.__class__.__name__} does not implement delete_latest')

        assert num_del == 1
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_rollback_cache(database_engine: CacheStorage) -> None:
    if isinstance(database_engine, CacheDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        run_time = time.time()

        # run twice
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2

        # rollback
        try:
            num_del = cache_storage.rollback(run_time)
        except NotImplementedError:
            pytest.skip(f'database_engine {database_engine.__class__.__name__} does not implement rollback')

        assert num_del == 1
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_restore_and_backup(database_engine: CacheStorage) -> None:
    urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

    cache_storage.restore([('myguid', 'mydata', 1618105974, 0, '')])
    if hasattr(cache_storage, '_copy_temp_to_permanent'):
        cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

    entry = cache_storage.load('myguid')
    assert entry == Snapshot('mydata', 1618105974, 0, '')

    entries = cache_storage.backup()
    backup_entry = entries.__next__()
    assert backup_entry == ('myguid', 'mydata', 1618105974, 0, '')


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_get_empty_history_and_no_max_snapshots(database_engine: CacheStorage) -> None:
    urlwatcher, cache_storage, _ = prepare_storage_test(database_engine, {'max_snapshots': 0})

    # run once
    urlwatcher.run_jobs()
    if hasattr(cache_storage, '_copy_temp_to_permanent'):
        cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

    # get rich_history
    guid = urlwatcher.jobs[0].get_guid()
    rich_history = cache_storage.get_history_snapshots(guid)
    assert len(rich_history) == 1

    # get history with zero count
    history = cache_storage.get_history_data(guid, count=0)
    assert history == {}

    # get rich_history with zero count
    rich_history = cache_storage.get_history_snapshots(guid, count=0)
    assert rich_history == []


@pytest.mark.parametrize(  # type: ignore[misc]
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_and_history_data(database_engine: CacheStorage) -> None:
    if isinstance(database_engine, CacheDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, cache_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]

        # run twice
        if isinstance(database_engine, CacheSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(cache_storage, '_copy_temp_to_permanent'):
            cache_storage._copy_temp_to_permanent(delete=True)  # type: ignore[attr-defined]
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2

        # clean
        cache_storage.clean(guid)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1

        # get history with zero count
        history = cache_storage.get_history_data(guid, count=0)
        assert history == {}

        # delete
        cache_storage.delete(guid)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 0


def test_migrate_urlwatch_legacy_db(tmp_path: Path) -> None:
    orig_cache_file = data_path.joinpath('cache-urlwatch_legacy.db')
    temp_cache_file = tmp_path.joinpath(f'cache-urlwatch_legacy-temp_{sys.version_info.minor}.db')
    shutil.copyfile(orig_cache_file, temp_cache_file)
    if minidb_is_installed:
        cache_storage = CacheSQLite3Storage(temp_cache_file)
        try:
            entries = cache_storage.backup()
            entry = entries.__next__()
            assert entry == ('547d652722e59e8894741a6382d973a89c8a7557', ' 9:52:54.74\n', 1618105974, 0, None)
        finally:
            cache_storage.close()
            temp_cache_file.unlink()
            # Pyton 3.9: minidb_temp_cache_file = temp_cache_file.with_stem(temp_cache_file.stem + '_minidb')
            minidb_temp_cache_file = temp_cache_file.parent.joinpath(
                temp_cache_file.stem + '_minidb' + ''.join(temp_cache_file.suffixes)
            )
            minidb_temp_cache_file.unlink()
    else:
        with pytest.raises(ImportError) as pytest_wrapped_e:
            CacheSQLite3Storage(temp_cache_file)
        assert str(pytest_wrapped_e.value) == (
            "Python package 'minidb' is not installed; cannot upgrade the legacy 'minidb' database"
        )


def test_max_snapshots() -> None:
    cache_file = ':memory:'
    cache_storage = CacheSQLite3Storage(cache_file)
    cache_storage.max_snapshots = 0
    cache_storage.close()


def test_abstractmethods() -> None:
    BaseTextualFileStorage.__abstractmethods__ = frozenset()

    @dataclass
    class DummyBaseTextualFileStorage(BaseTextualFileStorage, ABC):
        filename: Path

    filename = Path('test')
    d = DummyBaseTextualFileStorage(filename)  # type: ignore[abstract]
    assert d.load() is None
    assert d.save() is None
    assert d.parse(Path()) is None

    CacheStorage.__abstractmethods__ = frozenset()

    @dataclass
    class DummyCacheStorage(CacheStorage, ABC):
        filename: Path

    filename = Path('test')
    dummy_cache = DummyCacheStorage(filename)  # type: ignore[abstract]
    assert dummy_cache.close() is None
    assert dummy_cache.get_guids() is None
    assert dummy_cache.load('guid') is None
    assert dummy_cache.get_history_data('guid') is None
    assert dummy_cache.save(guid='guid', data='data', timestamp=0, tries=0, etag='etag') is None
    assert dummy_cache.delete('guid') is None
    assert dummy_cache.delete_latest('guid') is None
    assert dummy_cache.clean('guid') is None
    assert dummy_cache.rollback(0) is None
