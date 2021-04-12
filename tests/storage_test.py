import contextlib
import importlib.util
import os
import shutil
import sys
from typing import Optional

import pytest

from webchanges import __project_name__ as pkgname
from webchanges.config import BaseConfig
from webchanges.main import Urlwatch
from webchanges.storage import CacheSQLite3Storage, YamlConfigStorage, YamlJobsStorage

minidb_is_installed = importlib.util.find_spec('minidb') is not None

minidb_required = pytest.mark.skipif(not minidb_is_installed, reason="requires 'minidb' package to be installed")
py37_required = pytest.mark.skipif(sys.version_info < (3, 7), reason='requires Python 3.7')

root = os.path.join(os.path.dirname(__file__), f'../{pkgname}', '..')
here = os.path.dirname(__file__)


class ConfigForTest(BaseConfig):
    def __init__(self, config_file, urls_file, cache_file, hooks_file, verbose):
        super().__init__(pkgname, here, config_file, urls_file, cache_file, hooks_file, verbose)
        self.edit = False
        self.edit_hooks = False


@contextlib.contextmanager
def teardown_func():
    try:
        yield
    finally:
        'tear down test fixtures'
        cache_file = os.path.join(here, 'data', 'cache.db')
        fn_base, fn_ext = os.path.splitext(cache_file)
        minidb_cache_file = f'{fn_base}_minidb{fn_ext}'
        for filename in (cache_file, minidb_cache_file):
            if os.path.exists(filename):
                os.remove(filename)


def prepare_storage_test(config_args: Optional[dict] = None) -> (Urlwatch, CacheSQLite3Storage):
    jobs_file = os.path.join(here, 'data', 'jobs-time.yaml')
    config_file = os.path.join(here, 'data', 'config.yaml')
    cache_file = os.path.join(here, 'data', 'cache.db')
    hooks_file = ''

    config_storage = YamlConfigStorage(config_file)
    cache_storage = CacheSQLite3Storage(cache_file)
    jobs_storage = YamlJobsStorage(jobs_file)

    urlwatch_config = ConfigForTest(config_file, jobs_file, cache_file, hooks_file, True)
    if config_args:
        for k, v in config_args.items():
            setattr(urlwatch_config, k, v)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)

    return urlwatcher, cache_storage


@py37_required
def test_keep_latest():
    with teardown_func():
        urlwatcher, cache_storage = prepare_storage_test()
        try:
            # use an url that changes
            job = urlwatcher.jobs[0]
            if os.name == 'nt':
                job.command = 'echo %time%'
            guid = job.get_guid()

            # run once
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))

            # run twice
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))
            history = cache_storage.get_history_data(guid)
            assert len(history) == 2

            cache_storage.keep_latest(1)
            history = cache_storage.get_history_data(guid)
            assert len(history) == 1
        finally:
            cache_storage.close()


def test_clean():
    with teardown_func():
        urlwatcher, cache_storage = prepare_storage_test()
        try:
            # use an url that changes
            job = urlwatcher.jobs[0]
            if os.name == 'nt':
                job.command = 'echo %time%'
            guid = job.get_guid()

            # run once
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))

            # run twice
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))
            history = cache_storage.get_history_data(guid)
            assert len(history) == 2

            cache_storage.clean(guid, 1)
            history = cache_storage.get_history_data(guid)
            assert len(history) == 1
        finally:
            cache_storage.close()


def test_clean_cache():
    with teardown_func():
        urlwatcher, cache_storage = prepare_storage_test()
        try:
            # use an url that changes
            job = urlwatcher.jobs[0]
            if os.name == 'nt':
                job.command = 'echo %TIME%'
            guid = job.get_guid()

            # run once
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))

            # run twice
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))
            history = cache_storage.get_history_data(guid)
            assert len(history) == 2

            # clean cache
            cache_storage.clean_cache(guid)
            history = cache_storage.get_history_data(guid)
            assert len(history) == 1
        finally:
            cache_storage.close()


def test_clean_all_and_delete():
    with teardown_func():
        urlwatcher, cache_storage = prepare_storage_test()
        try:
            # use an url that changes
            job = urlwatcher.jobs[0]
            if os.name == 'nt':
                job.command = 'echo %TIME%'
            guid = job.get_guid()

            # run once
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))

            # run twice
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))
            history = cache_storage.get_history_data(guid)
            assert len(history) == 2

            # clean all
            cache_storage.clean_all()
            history = cache_storage.get_history_data(guid)
            assert len(history) == 1

            # delete guid
            cache_storage.delete(guid)
            history = cache_storage.get_history_data(guid)
            assert len(history) == 0
        finally:
            cache_storage.close()


def test_restore_and_backup():
    with teardown_func():
        cache_file = os.path.join(here, 'data', 'cache.db')
        cache_storage = CacheSQLite3Storage(cache_file)
        try:
            cache_storage.restore([('guid', 'data', 1618105974, 0, None)])

            entry = cache_storage.load('guid')
            assert entry == ('data', 1618105974, 0, None)

            entries = cache_storage.backup()
            entry = entries.__next__()
            assert entry == ('guid', 'data', 1618105974, 0, None)
        finally:
            cache_storage.close()


def get_empty_history_and_no_max_snapshots():
    with teardown_func():
        urlwatcher, cache_storage = prepare_storage_test({'max_snapshots': 0})
        try:
            # use an url that changes
            job = urlwatcher.jobs[0]
            if os.name == 'nt':
                job.command = 'echo %TIME%'
            guid = job.get_guid()

            # run once
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))

            # get history with zero count
            history = cache_storage.get_history_data(guid, count=0)
            assert history == {}
        finally:
            cache_storage.close()


@minidb_required
def test_migrate_urlwatch_legacy_db():
    with teardown_func():
        orig_cache_file = os.path.join(here, 'data', 'cache-urlwatch_legacy.db')
        temp_cache_file = os.path.join(here, 'data', 'cache-urlwatch_legacy-temp.db')
        shutil.copyfile(orig_cache_file, temp_cache_file)
        cache_storage = CacheSQLite3Storage(temp_cache_file)
        try:
            entries = cache_storage.backup()
            entry = entries.__next__()
            assert entry == ('547d652722e59e8894741a6382d973a89c8a7557', ' 9:52:54.74\n', 1618105974, 0, None)
        finally:
            cache_storage.close()
            os.remove(temp_cache_file)
            fn_base, fn_ext = os.path.splitext(temp_cache_file)
            minidb_file = f'{fn_base}_minidb{fn_ext}'
            os.remove(minidb_file)


# Legacy testing

@minidb_required
def prepare_storage_test_minidb(config_args={}):
    from webchanges.storage_minidb import CacheMiniDBStorage

    jobs_file = os.path.join(here, 'data', 'jobs-time.yaml')
    config_file = os.path.join(here, 'data', 'config.yaml')
    cache_file = os.path.join(here, 'data', 'cache.db')
    hooks_file = ''

    config_storage = YamlConfigStorage(config_file)
    cache_storage = CacheMiniDBStorage(cache_file)
    jobs_storage = YamlJobsStorage(jobs_file)

    urlwatch_config = ConfigForTest(config_file, jobs_file, cache_file, hooks_file, True)
    for k, v in config_args.items():
        setattr(urlwatch_config, k, v)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)

    return urlwatcher, cache_storage


@minidb_required
def test_clean_and_history_data_minidb():
    with teardown_func():
        urlwatcher, cache_storage = prepare_storage_test_minidb()
        try:
            # use an url that changes
            job = urlwatcher.jobs[0]
            if os.name == 'nt':
                job.command = 'echo %time%'
            guid = job.get_guid()

            # run once
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))

            # run twice
            urlwatcher.run_jobs()
            cache_storage.close()
            cache_storage.__init__(os.path.join(here, 'data', 'cache.db'))
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
