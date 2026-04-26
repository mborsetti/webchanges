"""Test storage.

To test Redis, set an environment variable REDIS_URI with the URI to the Redis server.  E.g.:
$ export REDIS_URI=redis://localhost:6379
or if using https://cloud.redis.io/#/databases
$ export REDIS_URI=redis://default:password@redis-1234.c123.us-west1-1.gce.redns.redis-cloud.com:12345
"""

from __future__ import annotations

import atexit
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

import pytest
import yaml

from tests.conftest import prepare_storage_test
from webchanges import __docs_url__
from webchanges.handler import Snapshot
from webchanges.storage import (
    BaseTextualFileStorage,
    SsdbDirStorage,
    SsdbRedisStorage,
    SsdbSQLite3Storage,
    SsdbStorage,
    YamlConfigStorage,
    YamlJobsStorage,
)
from webchanges.util import import_module_from_source

minidb_is_installed = importlib.util.find_spec('minidb') is not None
minidb_required = pytest.mark.skipif(not minidb_is_installed, reason="requires 'minidb' package to be installed")

# A real on-disk dir is needed at import time because ``DATABASE_ENGINES`` (used by ``@pytest.mark.parametrize``)
# constructs ``SsdbDirStorage`` against a path. ``atexit`` cleans it up at session end so it doesn't leak.
_storage_tmp = Path(tempfile.mkdtemp(prefix='wc-storage-tests-'))
atexit.register(shutil.rmtree, str(_storage_tmp), True)
tmp_path = _storage_tmp  # back-compat alias for ``test_migrate_urlwatch_legacy_db`` below

here = Path(__file__).parent
data_path = here.joinpath('data')
config_file = data_path.joinpath('config.yaml')


DATABASE_ENGINES: tuple[SsdbStorage, ...] = (
    SsdbDirStorage(_storage_tmp),
    SsdbSQLite3Storage(':memory:'),  # ty:ignore[invalid-argument-type]
)

if os.getenv('REDIS_URI') and importlib.util.find_spec('redis') is not None:
    DATABASE_ENGINES += (SsdbRedisStorage(os.getenv('REDIS_URI', '')),)

if importlib.util.find_spec('minidb') is not None:
    from webchanges.storage_minidb import SsdbMiniDBStorage

    DATABASE_ENGINES += (SsdbMiniDBStorage(':memory:'),)
else:
    SsdbMiniDBStorage = type(None)


def test_all_database_engines() -> None:
    if not os.getenv('REDIS_URI') or importlib.util.find_spec('redis') is None:
        pytest.mark.skip(
            'Cannot test the SsdbRedisStorage class. The REDIS_URI environment variable is not set or '
            "the 'redis' package is not installed"
        )
    if importlib.util.find_spec('minidb') is None:
        pytest.mark.skip("Cannot test the SsdbMiniDBStorage class. The 'minidb' package is not installed")


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
        f'this_is_a_typo: true\nCheck for typos or the hooks.py file (if any); documentation is at {__docs_url__}\n'
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
        f'Found unrecognized directive(s) in the configuration file {config_file}:\nreport:\n  made_up_key: true\n'
        f'Check for typos or the hooks.py file (if any); documentation is at {__docs_url__}\n'
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
    assert jobs[0].command == 'perl -MTime::HiRes -e \'printf "%f\n",Time::HiRes::time()\''


def test_check_for_shell_job() -> None:
    """Test if a job is a shell job."""
    jobs_file = data_path.joinpath('jobs-is_shell_job.yaml')
    # TODO: The below generates PermissionError: [Errno 1] Operation not permitted when run by GitHub Actions in macOS
    # if sys.platform != 'win32':
    #     os.chown(jobs_file, 65534, 65534)
    jobs_storage = YamlJobsStorage([jobs_file])
    jobs_storage.load_secure()
    # jobs = jobs_storage.load_secure()
    # if sys.platform != 'win32':
    #     assert len(jobs) == 1


def test_legacy_slack_keys() -> None:
    """Test if legacy report 'slack' keys don't trigger a ValueError even if not in DEFAULT_CONFIG."""
    config_storage = YamlConfigStorage(config_file)
    config = config_storage.parse(config_file)
    config['report']['slack'] = {'enabled': False}
    config_storage.check_for_unrecognized_keys(config)


def _write_config(tmp_path: Path, overrides: dict) -> Path:
    """Deep-merge overrides onto the test config.yaml baseline and write to tmp_path/config.yaml."""
    base = YamlConfigStorage(config_file).parse(config_file)
    merged = YamlConfigStorage.dict_deep_merge(overrides, copy.deepcopy(base))  # ty:ignore[invalid-argument-type]
    out = tmp_path / 'config.yaml'
    out.write_text(yaml.safe_dump(merged), encoding='utf-8')
    return out


_TYPE_ERROR_MATCH = r'^Found invalid data in configuration file .* entry:\n'


def test_load_valid_config_passes_type_check(tmp_path: Path) -> None:
    """A valid config.yaml loads without raising."""
    cfg = _write_config(tmp_path, {})
    YamlConfigStorage(cfg).load()


def test_load_invalid_bool_raises_value_error(tmp_path: Path) -> None:
    """A non-bool where bool is expected raises ValueError."""
    cfg = _write_config(tmp_path, {'display': {'new': 'yes'}})
    with pytest.raises(ValueError, match=_TYPE_ERROR_MATCH):
        YamlConfigStorage(cfg).load()


def test_load_invalid_literal_raises_value_error(tmp_path: Path) -> None:
    """A value outside an allowed Literal raises ValueError."""
    cfg = _write_config(tmp_path, {'database': {'engine': 'postgres'}})
    with pytest.raises(ValueError, match=_TYPE_ERROR_MATCH):
        YamlConfigStorage(cfg).load()


def test_load_invalid_int_raises_value_error(tmp_path: Path) -> None:
    """A non-int where int is expected raises ValueError."""
    cfg = _write_config(tmp_path, {'report': {'text': {'line_length': 'wide'}}})
    with pytest.raises(ValueError, match=_TYPE_ERROR_MATCH):
        YamlConfigStorage(cfg).load()


def test_load_invalid_nested_dict_raises_value_error(tmp_path: Path) -> None:
    """A scalar where a nested TypedDict is expected raises ValueError."""
    base = YamlConfigStorage(config_file).parse(config_file)
    merged = copy.deepcopy(base)
    merged['report']['email']['smtp'] = 'localhost'
    out = tmp_path / 'config.yaml'
    out.write_text(yaml.safe_dump(merged), encoding='utf-8')
    with pytest.raises(ValueError, match=_TYPE_ERROR_MATCH):
        YamlConfigStorage(out).load()


def test_remove_remark_keys_strips_underscore_keys() -> None:
    """remove_remark_keys recursively drops keys starting with '_'."""
    storage = YamlConfigStorage(config_file)
    nested = {
        '_note': 'top level remark',
        'kept': 1,
        'inner': {
            '_note': 'inner remark',
            'also_kept': [1, 2, 3],
            'deeper': {'_skip': True, 'real': 'value'},
        },
    }
    cleaned = storage.remove_remark_keys(nested)
    assert cleaned == {'kept': 1, 'inner': {'also_kept': [1, 2, 3], 'deeper': {'real': 'value'}}}


def test_load_remark_keys_do_not_break_type_check(tmp_path: Path) -> None:
    """User-added '_'-prefixed remark keys must not trigger a type-check failure."""
    cfg = _write_config(tmp_path, {'job_defaults': {'all': {'_note': 'a remark'}}})
    YamlConfigStorage(cfg).load()


def test_remove_deprecated_keys_strips_slack() -> None:
    """remove_deprecated_keys drops the legacy 'slack' reporter key."""
    config = YamlConfigStorage(config_file).parse(config_file)
    config['report']['slack'] = {'enabled': False}
    cleaned = YamlConfigStorage.remove_deprecated_keys(config)
    assert 'slack' not in cleaned['report']


# @py37_required
# SsdbSQLite3Storage.keep_latest() requires Python 3.7 to work (returns 0 otherwise).
@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_keep_latest(database_engine: SsdbStorage) -> None:
    if not hasattr(database_engine, 'keep_latest'):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} has no keep_latest method')
    else:
        urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

        # run twice
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0003)
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        guid = urlwatcher.jobs[0].get_guid()
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        assert timestamps[1] < timestamps[0]

        # check that history matches load
        snapshot = ssdb_storage.load(guid)
        assert snapshot.data == next(iter(history.keys()))
        assert snapshot.timestamp == next(iter(history.values()))

        # only keep last one
        if isinstance(ssdb_storage, SsdbSQLite3Storage):
            ssdb_storage.keep_latest(1)
            history = ssdb_storage.get_history_data(guid)
            assert len(history) == 1
            timestamp = next(iter(history.values()))
            # is it the most recent?
            assert timestamp == timestamps[0]


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean(database_engine: SsdbStorage) -> None:
    if isinstance(database_engine, SsdbDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

        # run twice
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        guid = urlwatcher.jobs[0].get_guid()
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        if not isinstance(database_engine, SsdbMiniDBStorage):  # rounds to the closest second
            assert timestamps[1] < timestamps[0]

        # check that history matches load
        snapshot = ssdb_storage.load(guid)
        assert snapshot.data == next(iter(history.keys()))
        assert snapshot.timestamp == next(iter(history.values()))

        ssdb_storage.clean(guid, 1)
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 1
        timestamp = next(iter(history.values()))
        # is it the most recent?
        assert timestamp == timestamps[0]


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_gc(database_engine: SsdbStorage) -> None:
    urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

    # run once
    urlwatcher.run_jobs()
    if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
        ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

    ssdb_storage.gc([])
    guid = urlwatcher.jobs[0].get_guid()
    history = ssdb_storage.get_history_data(guid)
    assert history == {}


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_gc_delete_1_of_2(database_engine: SsdbStorage) -> None:
    urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

    # add second job
    new_job = copy.deepcopy(urlwatcher.jobs[0])
    new_job.set_base_location(new_job.get_location() + ' #')
    urlwatcher.jobs.append(new_job)

    # run twice
    for _ in range(3):
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
    if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
        ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

    guid = urlwatcher.jobs[0].get_guid()
    ssdb_storage.gc([guid])
    history = ssdb_storage.get_history_data(guid)
    assert len(history) == 1

    guid_2 = urlwatcher.jobs[1].get_guid()
    history = ssdb_storage.get_history_data(guid_2)
    assert history == {}


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_gc_delete_2_of_4(database_engine: SsdbStorage) -> None:
    if isinstance(database_engine, SsdbDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    if isinstance(database_engine, SsdbRedisStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} does not support this')
    if isinstance(database_engine, SsdbMiniDBStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} not implemented')

    urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

    # add second job
    new_job = copy.deepcopy(urlwatcher.jobs[0])
    new_job.set_base_location(new_job.get_location() + ' #')
    urlwatcher.jobs.append(new_job)

    # run four times
    for _ in range(5):
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
    if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
        ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

    guid = urlwatcher.jobs[0].get_guid()
    ssdb_storage.gc([guid], 2)
    history = ssdb_storage.get_history_data(guid)
    assert len(history) == 2

    guid_2 = urlwatcher.jobs[1].get_guid()
    history = ssdb_storage.get_history_data(guid_2)
    assert history == {}


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_ssdb(database_engine: SsdbStorage) -> None:
    if isinstance(database_engine, SsdbDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

        # run five times
        for _ in range(5):
            if isinstance(database_engine, SsdbSQLite3Storage):
                time.sleep(0.0001)
            urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

        guid = urlwatcher.jobs[0].get_guid()
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 5
        timestamps = list(history.values())
        # returned in reverse order
        if not isinstance(database_engine, SsdbMiniDBStorage):  # rounds to the closest second
            assert timestamps[1] < timestamps[0]

        # clean ssdb, leaving 3
        if isinstance(database_engine, (SsdbSQLite3Storage, SsdbMiniDBStorage)):
            ssdb_storage.clean_ssdb([guid], 3)
            history = ssdb_storage.get_history_data(guid)
            assert len(history) == 3
        else:
            with pytest.raises(NotImplementedError):
                ssdb_storage.clean_ssdb([guid], 3)

        # clean ssdb, leaving 1
        ssdb_storage.clean_ssdb([guid])
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 1

        timestamp = next(iter(history.values()))
        # is it the most recent?
        assert timestamp == timestamps[0]


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_and_delete(database_engine: SsdbStorage) -> None:
    urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

    # run once
    urlwatcher.run_jobs()
    if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
        ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

    # clean guid
    guid = urlwatcher.jobs[0].get_guid()
    deleted = ssdb_storage.clean(guid)
    assert deleted == 0
    history = ssdb_storage.get_history_data(guid)
    assert len(history) == 1

    # delete guid
    ssdb_storage.delete(guid)
    history = ssdb_storage.get_history_data(guid)
    assert len(history) == 0

    # clean too much
    try:
        ssdb_storage.clean(guid, 10)
    except NotImplementedError:
        pass


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_all(database_engine: SsdbStorage) -> None:
    if not hasattr(database_engine, 'clean_all'):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} has no clean_all method')
    else:
        urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

        # run twice
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        guid = urlwatcher.jobs[0].get_guid()
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        if not isinstance(database_engine, SsdbMiniDBStorage):  # rounds to the closest second
            assert timestamps[1] <= timestamps[0]

        # clean all
        if isinstance(ssdb_storage, SsdbSQLite3Storage):
            ssdb_storage.clean_all()
            history = ssdb_storage.get_history_data(guid)
            assert len(history) == 1
            timestamp = next(iter(history.values()))
            # is it the most recent?
            assert timestamp == timestamps[0]


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_ssdb_no_clean_all(database_engine: SsdbStorage) -> None:
    if isinstance(database_engine, SsdbDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

        # run twice
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        guid = urlwatcher.jobs[0].get_guid()
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 2
        timestamps = list(history.values())
        # returned in reverse order
        if not isinstance(database_engine, SsdbMiniDBStorage):  # rounds to the closest second
            assert timestamps[1] < timestamps[0]

        # clean ssdb without using clean_all
        # delattr(SsdbSQLite3Storage, 'clean_all')
        ssdb_storage.clean_ssdb([guid])
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 1
        timestamp = next(iter(history.values()))
        # is it the most recent?
        assert timestamp == timestamps[0]


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_delete_latest(database_engine: SsdbStorage) -> None:
    if isinstance(database_engine, SsdbDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

        # run twice
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        guid = urlwatcher.jobs[0].get_guid()
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 2

        # rollback
        try:
            num_del = ssdb_storage.delete_latest(guid)
        except NotImplementedError:
            pytest.skip(f'database_engine {database_engine.__class__.__name__} does not implement delete_latest')

        assert num_del == 1
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 1


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_rollback_ssdb(database_engine: SsdbStorage) -> None:
    if isinstance(database_engine, SsdbDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        run_time = time.time()

        # run twice
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        guid = urlwatcher.jobs[0].get_guid()
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 2

        # rollback
        try:
            num_del = ssdb_storage.rollback(run_time)
        except NotImplementedError:
            pytest.skip(f'database_engine {database_engine.__class__.__name__} does not implement rollback')

        assert num_del == 1
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 1


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_restore_and_backup(database_engine: SsdbStorage) -> None:
    _, ssdb_storage, _ = prepare_storage_test(database_engine)

    mime_type = 'text/plain' if isinstance(database_engine, (SsdbSQLite3Storage, SsdbRedisStorage)) else ''

    ssdb_storage.restore((('myguid', 'mydata', 1618105974, 0, '', mime_type, {}),))  # ty:ignore[invalid-argument-type]
    if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
        ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

    entry = ssdb_storage.load('myguid')
    assert entry == Snapshot('mydata', 1618105974, 0, '', mime_type, {})

    entries = ssdb_storage.backup()
    backup_entry = entries.__next__()
    assert backup_entry == ('myguid', 'mydata', 1618105974, 0, '', mime_type, {})


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_get_empty_history_and_no_max_snapshots(database_engine: SsdbStorage) -> None:
    urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine, {'max_snapshots': 0})

    # run once
    urlwatcher.run_jobs()
    if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
        ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

    # get rich_history
    guid = urlwatcher.jobs[0].get_guid()
    rich_history = ssdb_storage.get_history_snapshots(guid)
    assert len(rich_history) == 1

    # get history with zero count
    history = ssdb_storage.get_history_data(guid, count=0)
    assert history == {}

    # get rich_history with zero count
    rich_history = ssdb_storage.get_history_snapshots(guid, count=0)
    assert rich_history == []


@pytest.mark.parametrize(
    'database_engine',
    DATABASE_ENGINES,
    ids=(type(v).__name__ for v in DATABASE_ENGINES),
)
def test_clean_and_history_data(database_engine: SsdbStorage) -> None:
    if isinstance(database_engine, SsdbDirStorage):
        pytest.skip(f'database_engine {database_engine.__class__.__name__} can only save one snapshot at a time')
    else:
        urlwatcher, ssdb_storage, _ = prepare_storage_test(database_engine)

        # run once
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]

        # run twice
        if isinstance(database_engine, SsdbSQLite3Storage):
            time.sleep(0.0001)
        urlwatcher.run_jobs()
        if hasattr(ssdb_storage, '_copy_temp_to_permanent'):
            ssdb_storage._copy_temp_to_permanent(delete=True)  # ty:ignore[call-non-callable]
        guid = urlwatcher.jobs[0].get_guid()
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 2

        # clean
        ssdb_storage.clean(guid)
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 1

        # get history with zero count
        history = ssdb_storage.get_history_data(guid, count=0)
        assert history == {}

        # delete
        ssdb_storage.delete(guid)
        history = ssdb_storage.get_history_data(guid)
        assert len(history) == 0


def test_migrate_urlwatch_legacy_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    orig_ssdb_file = data_path.joinpath('cache-urlwatch_legacy.db')
    temp_ssdb_file = tmp_path.joinpath(f'cache-urlwatch_legacy-temp_{sys.version_info.minor}.db')
    shutil.copyfile(orig_ssdb_file, temp_ssdb_file)
    if minidb_is_installed:
        ssdb_storage = SsdbSQLite3Storage(temp_ssdb_file)
        try:
            entries = ssdb_storage.backup()
            entry = entries.__next__()
            assert entry == ('547d652722e59e8894741a6382d973a89c8a7557', ' 9:52:54.74\n', 1618105974.0, 0, None, '', {})
        finally:
            ssdb_storage.close()
            temp_ssdb_file.unlink()
            minidb_temp_ssdb_file = temp_ssdb_file.with_stem(temp_ssdb_file.stem + '_minidb')
            minidb_temp_ssdb_file.unlink()
    else:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            SsdbSQLite3Storage(temp_ssdb_file)
        assert pytest_wrapped_e.value.code == 1
        message = capsys.readouterr().out
        assert message.splitlines() == (
            [
                'You have an old snapshot database format that needs to be converted to a current one.',
                "Please install the Python package 'minidb' for this one-time conversion and rerun webchanges.",
                'Use e.g. `pip install -U minidb`.',
                '',
                "After the conversion, you can uninstall 'minidb' with e.g. `pip uninstall minidb`.",
            ]
        )


def test_max_snapshots() -> None:
    ssdb_file = ':memory:'
    ssdb_storage = SsdbSQLite3Storage(ssdb_file)  # ty:ignore[invalid-argument-type]
    ssdb_storage.max_snapshots = 0
    ssdb_storage.close()


def test_abstractmethods() -> None:
    BaseTextualFileStorage.__abstractmethods__ = frozenset()

    @dataclass
    class DummyBaseTextualFileStorage(BaseTextualFileStorage, ABC):
        filename: Path

    filename = Path('test')
    d = DummyBaseTextualFileStorage(filename)
    assert d.load() is None
    assert d.save() is None
    assert d.parse(Path()) is None

    SsdbStorage.__abstractmethods__ = frozenset()

    @dataclass
    class DummySsdbStorage(SsdbStorage, ABC):
        filename: Path

    filename = Path('test')
    dummy_ssdb = DummySsdbStorage(filename)
    assert dummy_ssdb.close() is None
    assert dummy_ssdb.get_guids() is None
    assert dummy_ssdb.load('guid') is None
    assert dummy_ssdb.get_history_data('guid') is None
    assert (
        dummy_ssdb.save(
            guid='guid',
            snapshot=Snapshot(
                data='data',
                timestamp=0,
                tries=0,
                etag='etag',
                mime_type='text/plain',
                error_data={},
            ),
        )
        is None
    )
    assert dummy_ssdb.delete('guid') is None
    assert dummy_ssdb.delete_latest('guid') is None
    assert dummy_ssdb.clean('guid') is None
    assert dummy_ssdb.rollback(0) is None
