"""Test storage."""

import importlib.util
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import pytest

from webchanges import __project_name__ as project_name
from webchanges.config import CommandConfig
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, YamlConfigStorage, YamlJobsStorage

minidb_is_installed = importlib.util.find_spec('minidb') is not None

minidb_required = pytest.mark.skipif(not minidb_is_installed, reason="requires 'minidb' package to be installed")
py37_required = pytest.mark.skipif(sys.version_info < (3, 7), reason='requires Python 3.7')

here = Path(__file__).parent
data_dir = here.joinpath('data')
config_file = data_dir.joinpath('config.yaml')
cache_file = ':memory:'
hooks_file = ''


def prepare_storage_test(config_args: Optional[dict] = None) -> (Urlwatch, CacheSQLite3Storage, str):
    jobs_file = data_dir.joinpath('jobs-time.yaml')

    config_storage = YamlConfigStorage(config_file)
    cache_storage = CacheSQLite3Storage(cache_file)
    jobs_storage = YamlJobsStorage(jobs_file)

    urlwatch_config = CommandConfig(project_name, here, config_file, jobs_file, hooks_file, cache_file, True)
    if config_args:
        for k, v in config_args.items():
            setattr(urlwatch_config, k, v)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)

    if os.name == 'nt':
        urlwatcher.jobs[0].command = 'echo %time% %random%'

    return urlwatcher, cache_storage, cache_file


@py37_required
# CacheSQLite3Storage.keep_latest() requires Python 3.7 to work (returns 0 otherwise).
def test_keep_latest():
    urlwatcher, cache_storage, cache_file = prepare_storage_test()
    try:
        # run once
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        # run twice
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        assert timestamps[1] < timestamps[0]

        # check that history matches load
        data, timestamp, tries, etag = cache_storage.load(guid)
        assert data == list(history.keys())[0]
        assert timestamp == list(history.values())[0]

        # only keep last one
        cache_storage.keep_latest(1)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1
        timestamp = list(history.values())[0]
        # is it the most recent?
        assert timestamp == timestamps[0]
    finally:
        cache_storage.close()


def test_clean():
    urlwatcher, cache_storage, cache_file = prepare_storage_test()
    try:
        # run once
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        # run twice
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        assert timestamps[1] < timestamps[0]

        # check that history matches load
        data, timestamp, tries, etag = cache_storage.load(guid)
        assert data == list(history.keys())[0]
        assert timestamp == list(history.values())[0]

        cache_storage.clean(guid, 1)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1
        timestamp = list(history.values())[0]
        # is it the most recent?
        assert timestamp == timestamps[0]
    finally:
        cache_storage.close()


def test_clean_cache():
    urlwatcher, cache_storage, cache_file = prepare_storage_test()
    try:
        # run once
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        # run twice
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        assert timestamps[1] < timestamps[0]

        # clean cache
        cache_storage.clean_cache(guid)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1
        timestamp = list(history.values())[0]
        # is it the most recent?
        assert timestamp == timestamps[0]
    finally:
        cache_storage.close()


def test_clean_all_and_delete():
    urlwatcher, cache_storage, cache_file = prepare_storage_test()
    try:
        # run once
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        # run twice
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        assert timestamps[1] <= timestamps[0]

        # clean all
        cache_storage.clean_all()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1
        timestamp = list(history.values())[0]
        # is it the most recent?
        assert timestamp == timestamps[0]

        # delete guid
        cache_storage.delete(guid)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 0
    finally:
        cache_storage.close()


def test_rollback_cache():
    urlwatcher, cache_storage, cache_file = prepare_storage_test()
    try:
        # run once
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        run_time = time.time()

        # run twice
        time.sleep(.0001)
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid)
        assert len(history) == 2

        # rollback
        num_del = cache_storage.rollback(run_time)
        assert num_del == 1
        cache_storage._copy_temp_to_permanent(delete=True)
        history = cache_storage.get_history_data(guid)
        assert len(history) == 1
    finally:
        cache_storage.close()


def test_restore_and_backup():
    urlwatcher, cache_storage, cache_file = prepare_storage_test()
    try:
        cache_storage.restore([('guid', 'data', 1618105974, 0, None)])
        cache_storage._copy_temp_to_permanent(delete=True)

        entry = cache_storage.load('guid')
        assert entry == ('data', 1618105974, 0, None)

        entries = cache_storage.backup()
        entry = entries.__next__()
        assert entry == ('guid', 'data', 1618105974, 0, None)
    finally:
        cache_storage.close()


def get_empty_history_and_no_max_snapshots():
    urlwatcher, cache_storage, cache_file = prepare_storage_test({'max_snapshots': 0})
    try:
        # run once
        urlwatcher.run_jobs()
        cache_storage._copy_temp_to_permanent(delete=True)

        # get history with zero count
        guid = urlwatcher.jobs[0].get_guid()
        history = cache_storage.get_history_data(guid, count=0)
        assert history == {}
    finally:
        cache_storage.close()


def test_migrate_urlwatch_legacy_db():
    orig_cache_file = data_dir.joinpath('cache-urlwatch_legacy.db')
    temp_cache_file = data_dir.joinpath('cache-urlwatch_legacy-temp.db')
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
            minidb_temp_cache_file = temp_cache_file.parent.joinpath(temp_cache_file.stem + '_minidb'
                                                                     + ''.join(temp_cache_file.suffixes))
            minidb_temp_cache_file.unlink()
    else:
        with pytest.raises(ImportError) as pytest_wrapped_e:
            CacheSQLite3Storage(temp_cache_file)
        assert str(pytest_wrapped_e.value) == (
            "Python package 'minidb' is not installed; cannot upgrade the legacy 'minidb' database"
        )


# Legacy testing
@minidb_required
def prepare_storage_test_minidb(config_args={}):
    from webchanges.storage_minidb import CacheMiniDBStorage

    jobs_file = data_dir.joinpath('jobs-time.yaml')

    config_storage = YamlConfigStorage(config_file)
    cache_storage = CacheMiniDBStorage(cache_file)
    jobs_storage = YamlJobsStorage(jobs_file)

    urlwatch_config = CommandConfig(project_name, here, config_file, jobs_file, hooks_file, cache_file, True)
    for k, v in config_args.items():
        setattr(urlwatch_config, k, v)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)

    if os.name == 'nt':
        urlwatcher.jobs[0].command = 'echo %time%'

    return urlwatcher, cache_storage, cache_file


@minidb_required
def test_clean_and_history_data_minidb():
    urlwatcher, cache_storage, cache_file = prepare_storage_test_minidb()
    try:
        # run once
        urlwatcher.run_jobs()

        # run twice
        urlwatcher.run_jobs()
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
    finally:
        cache_storage.close()
