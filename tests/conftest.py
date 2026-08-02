"""Shared pytest fixtures for the webchanges test suite."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from webchanges.command import UrlwatchCommand
from webchanges.config import CommandConfig
from webchanges.main import Urlwatch
from webchanges.storage import SsdbSQLite3Storage, SsdbStorage, YamlConfigStorage, YamlJobsStorage

if TYPE_CHECKING:
    from typing import Iterator

_TESTS_DIR = Path(__file__).parent
_DATA_DIR = _TESTS_DIR / 'data'
# High-resolution changing-output command for Windows test jobs. cmd's `echo %time% %random%` has only centisecond
# resolution (and %random% repeats when two cmd spawns share the same seed second), so on a fast machine two
# consecutive runs can emit identical data, collapsing into a single snapshot; time_ns() cannot collide. It mirrors
# the perl Time::HiRes command that jobs-time.yaml uses on other platforms.
WINDOWS_TIME_COMMAND = f'"{sys.executable}" -c "import time; print(time.time_ns())"'

# Captured at import time, before test_command.py's autouse ``_silence_db_close`` fixture can monkeypatch it to a
# no-op (the patch is still active while other fixtures tear down), so teardowns can always really close the DB.
_REAL_SSDB_SQLITE3_CLOSE = SsdbSQLite3Storage.close


def close_ssdb_storage(storage: SsdbStorage) -> None:
    """Close ``storage`` for real, bypassing any monkeypatched ``close`` and tolerating already-closed storages."""
    try:
        if isinstance(storage, SsdbSQLite3Storage):
            _REAL_SSDB_SQLITE3_CLOSE(storage)
        else:
            storage.close()
    except AttributeError:
        pass  # already closed: close() deletes or None-s its connection attributes


_WORKSPACE_FILES = (
    'config.yaml',
    'jobs-echo_test.yaml',
    'jobs-time.yaml',
    'hooks_example.py',
)


@pytest.fixture(scope='session')
def data_dir() -> Path:
    """Path to ``tests/data``."""
    return _DATA_DIR


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Per-test temp workspace seeded with copies of the standard test config / jobs / hooks files.

    Function-scoped so any test that mutates files (writes ``_edit`` siblings, adds extra jobs files,
    etc.) cannot leak into another test.
    """
    for name in _WORKSPACE_FILES:
        shutil.copyfile(_DATA_DIR / name, tmp_path / name)
    return tmp_path


@pytest.fixture
def config_file_path(workspace: Path) -> Path:
    return workspace / 'config.yaml'


@pytest.fixture
def jobs_file_path(workspace: Path) -> Path:
    return workspace / 'jobs-echo_test.yaml'


@pytest.fixture
def hooks_file_path(workspace: Path) -> Path:
    return workspace / 'hooks_example.py'


@pytest.fixture
def command_config(
    workspace: Path, config_file_path: Path, jobs_file_path: Path, hooks_file_path: Path
) -> CommandConfig:
    """Fresh ``CommandConfig`` per test, pointing at the per-test workspace and an in-memory ssdb."""
    return CommandConfig(
        args=[],
        config_path=workspace,
        config_file=config_file_path,
        jobs_def_file=jobs_file_path,
        hooks_def_file=hooks_file_path,
        ssdb_file=':memory:',  # ty:ignore[invalid-argument-type]
    )


@pytest.fixture
def loaded_config_storage(config_file_path: Path) -> YamlConfigStorage:
    storage = YamlConfigStorage(config_file_path)
    storage.load()
    return storage


@pytest.fixture
def ssdb_storage() -> Iterator[SsdbSQLite3Storage]:
    storage = SsdbSQLite3Storage(':memory:')  # ty:ignore[invalid-argument-type]
    yield storage
    close_ssdb_storage(storage)


@pytest.fixture(scope='session', autouse=True)
def _close_database_engines() -> Iterator[None]:
    """Close tests.test_storage's module-level ``DATABASE_ENGINES`` (when imported) at session end so that their
    database connections don't survive to interpreter shutdown and emit ResourceWarnings.
    """
    yield
    test_storage_module = sys.modules.get('tests.test_storage')
    if test_storage_module is not None:
        for engine in test_storage_module.DATABASE_ENGINES:
            close_ssdb_storage(engine)


@pytest.fixture
def jobs_storage(jobs_file_path: Path) -> YamlJobsStorage:
    return YamlJobsStorage([jobs_file_path])


@pytest.fixture
def urlwatcher(
    command_config: CommandConfig,
    loaded_config_storage: YamlConfigStorage,
    ssdb_storage: SsdbSQLite3Storage,
    jobs_storage: YamlJobsStorage,
) -> Urlwatch:
    """Fresh ``Urlwatch`` per test with in-memory snapshot DB.

    No teardown ``close()`` — that triggers ``report.finish()`` which can fire reporters configured by
    the test under test. The in-memory SQLite DB cleans itself when garbage-collected.
    """
    return Urlwatch(command_config, loaded_config_storage, ssdb_storage, jobs_storage)


@pytest.fixture
def urlwatch_command(urlwatcher: Urlwatch) -> UrlwatchCommand:
    """``UrlwatchCommand`` wrapping the per-test ``urlwatcher``."""
    return UrlwatchCommand(urlwatcher)


def prepare_storage_test(
    ssdb_storage: SsdbStorage,
    config_args: dict | None = None,
    jobs_file: Path | None = None,
) -> tuple[Urlwatch, SsdbStorage, CommandConfig]:
    """Build an ``Urlwatch`` around the given storage engine and ``jobs-time.yaml`` (default).

    Used by storage/command tests that need to drive a full ``Urlwatch`` against each available DB engine.
    ``config_args`` is a dict of attributes to assign on the resulting ``CommandConfig`` (e.g. ``max_snapshots``).
    """
    if hasattr(ssdb_storage, 'flushdb'):
        ssdb_storage.flushdb()
    if jobs_file is None:
        jobs_file = _DATA_DIR / 'jobs-time.yaml'
    config_file = _DATA_DIR / 'config.yaml'
    command_config = CommandConfig(
        args=[],
        config_path=_TESTS_DIR,
        config_file=config_file,
        jobs_def_file=jobs_file,
        hooks_def_file=Path(),
        ssdb_file=ssdb_storage.filename,
    )
    if config_args:
        for k, v in config_args.items():
            setattr(command_config, k, v)
    config_storage = YamlConfigStorage(config_file)
    config_storage.load()
    urlwatcher = Urlwatch(command_config, config_storage, ssdb_storage, YamlJobsStorage([jobs_file]))
    if sys.platform == 'win32':
        urlwatcher.jobs[0].command = WINDOWS_TIME_COMMAND
        urlwatcher.jobs[0].guid = urlwatcher.jobs[0].get_guid()
    return urlwatcher, ssdb_storage, command_config


@pytest.fixture
def dummy_editor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set ``EDITOR`` to a no-op (``rundll32`` on Windows, ``true`` elsewhere); clear ``VISUAL``.

    Tests that exercise an edit action — but don't actually want to launch one — request this fixture.
    Tests that want a *broken* editor can additionally call ``monkeypatch.setenv('EDITOR', '<bad>')``
    after this fixture; pytest's monkeypatch restores the original value at teardown.
    """
    monkeypatch.setenv('EDITOR', 'rundll32' if sys.platform == 'win32' else 'true')
    monkeypatch.delenv('VISUAL', raising=False)
