"""Tests for cli.py helpers."""

from __future__ import annotations

import hashlib
import io
import logging
import os
import signal
import sys
import sysconfig
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from webchanges import __min_python_version__, __project_name__, __version__
from webchanges import cli as cli_module
from webchanges.cli import (
    _expand_glob_files,
    exit_on_user_error,
    first_run,
    handle_unitialized_actions,
    load_hooks,
    locate_glob_files,
    locate_jobs_and_hooks_files,
    locate_storage_file,
    migrate_from_legacy,
    python_version_warning,
    setup_logger,
    show_detailed_versions,
    sync_bundled_schemas,
    teardown_logger,
)
from webchanges.config import CommandConfig

if TYPE_CHECKING:
    from collections.abc import Generator

is_t_build = sysconfig.get_config_var('Py_GIL_DISABLED') == 1


def _make_config(config_dir: Path, jobs_dir: Path | None) -> CommandConfig:
    ns = SimpleNamespace(
        config_file=config_dir / 'config.yaml',
        jobs_files=[jobs_dir / 'jobs.yaml'] if jobs_dir is not None else [],
    )
    return cast('CommandConfig', ns)


def test_first_run_deploys_both_schemas(tmp_path: Path) -> None:
    cfg_dir = tmp_path / 'cfg'
    jobs_dir = tmp_path / 'jobs'
    cfg_dir.mkdir()
    jobs_dir.mkdir()

    sync_bundled_schemas(_make_config(cfg_dir, jobs_dir))

    assert (cfg_dir / 'config.schema.json').is_file()
    assert (cfg_dir / '.config.schema.sha256').is_file()
    assert (jobs_dir / 'jobs.schema.json').is_file()
    assert (jobs_dir / '.jobs.schema.sha256').is_file()

    deployed = (cfg_dir / 'config.schema.json').read_bytes()
    expected = (cfg_dir / '.config.schema.sha256').read_text(encoding='utf-8').strip()
    assert hashlib.sha256(deployed).hexdigest() == expected


def test_second_run_is_noop(tmp_path: Path) -> None:
    cfg_dir = tmp_path / 'cfg'
    jobs_dir = tmp_path / 'jobs'
    cfg_dir.mkdir()
    jobs_dir.mkdir()
    cmd = _make_config(cfg_dir, jobs_dir)

    sync_bundled_schemas(cmd)
    schema_path = cfg_dir / 'config.schema.json'
    mtime_before = schema_path.stat().st_mtime_ns

    sync_bundled_schemas(cmd)

    assert schema_path.stat().st_mtime_ns == mtime_before


def test_tampered_hash_triggers_redeploy(tmp_path: Path) -> None:
    cfg_dir = tmp_path / 'cfg'
    jobs_dir = tmp_path / 'jobs'
    cfg_dir.mkdir()
    jobs_dir.mkdir()
    cmd = _make_config(cfg_dir, jobs_dir)

    sync_bundled_schemas(cmd)
    (jobs_dir / '.jobs.schema.sha256').write_text('deadbeef\n', encoding='utf-8')

    sync_bundled_schemas(cmd)

    redeployed = (jobs_dir / '.jobs.schema.sha256').read_text(encoding='utf-8').strip()
    assert redeployed != 'deadbeef'
    assert len(redeployed) == 64


def test_no_jobs_files_skips_jobs_schema(tmp_path: Path) -> None:
    cfg_dir = tmp_path / 'cfg'
    cfg_dir.mkdir()

    sync_bundled_schemas(_make_config(cfg_dir, None))

    assert (cfg_dir / 'config.schema.json').is_file()
    assert not (cfg_dir / 'jobs.schema.json').exists()


def test_missing_bundled_package_is_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    cfg_dir = tmp_path / 'cfg'
    cfg_dir.mkdir()

    import importlib.resources as resources

    def fake_files(_pkg: str) -> Path:
        raise ModuleNotFoundError('no bundled files')

    monkeypatch.setattr(resources, 'files', fake_files)

    with caplog.at_level(logging.DEBUG, logger='webchanges.cli'):
        sync_bundled_schemas(_make_config(cfg_dir, None))

    assert not (cfg_dir / 'config.schema.json').exists()
    assert any('Bundled schemas package not found' in r.message for r in caplog.records)


# @pytest.mark.skipif(is_t_build, reason='Test does not work in free-threaded Python')
# @pytest.mark.skipif(sys.platform == 'win32', reason='chmod-based read-only is unreliable on Windows')
# def test_readonly_target_logs_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
#     cfg_dir = tmp_path / 'cfg'
#     cfg_dir.mkdir()
#     cfg_dir.chmod(0o500)

#     try:
#         with caplog.at_level(logging.WARNING, logger='webchanges.cli'):
#             sync_bundled_schemas(_make_config(cfg_dir, None))
#     finally:
#         cfg_dir.chmod(0o700)

#     assert any('Could not deploy' in r.message for r in caplog.records)


@pytest.fixture
def isolated_root_logger() -> Generator[None, None, None]:
    """Snapshot root logger handlers/level, clear them, restore on exit.

    Cleared inside the test (not just the fixture) so ``logging.basicConfig`` is not a no-op
    against handlers attached by pytest's logging plugin between fixture yield and test body.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    try:
        yield
    finally:
        for h in root.handlers:
            try:
                h.close()
            except Exception:  # noqa: BLE001, S110
                pass
        root.handlers.clear()
        root.handlers.extend(saved_handlers)
        root.setLevel(saved_level)


def test_setup_logger_verbose_1_sets_info_level(isolated_root_logger: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('DEBUG', raising=False)
    logging.getLogger().handlers.clear()
    setup_logger(verbose=1)
    assert logging.getLogger().level == logging.INFO
    assert 'DEBUG' not in os.environ


def test_setup_logger_verbose_2_sets_debug_env(isolated_root_logger: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('DEBUG', raising=False)
    logging.getLogger().handlers.clear()
    setup_logger(verbose=2)
    assert os.environ['DEBUG'] == 'pw:api pytest -s'
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logger_verbose_3_sets_notset_level(isolated_root_logger: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('DEBUG', raising=False)
    logging.getLogger().handlers.clear()
    setup_logger(verbose=3)
    assert os.environ['DEBUG'] == 'pw:api pytest -s'
    assert logging.getLogger().level == logging.NOTSET


def test_setup_logger_with_log_file_attaches_filehandler(
    tmp_path: Path, isolated_root_logger: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv('DEBUG', raising=False)
    log_path = tmp_path / 'wc.log'
    logging.getLogger().handlers.clear()
    setup_logger(log_file=log_path)

    file_handlers = [h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)]
    assert any(Path(h.baseFilename) == log_path for h in file_handlers)
    for h in file_handlers:
        h.flush()
    assert log_path.is_file()


def test_teardown_logger_pops_debug_env_when_verbose_high(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DEBUG', 'pw:api pytest -s')
    teardown_logger(verbose=2)
    assert 'DEBUG' not in os.environ


def test_teardown_logger_leaves_debug_env_when_verbose_low(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DEBUG', 'do-not-touch')
    teardown_logger(verbose=1)
    assert os.environ['DEBUG'] == 'do-not-touch'


def test_expand_glob_files_direct_match(tmp_path: Path) -> None:
    target = tmp_path / 'a.yaml'
    target.write_text('x', encoding='utf-8')
    result = _expand_glob_files(target, default_path=tmp_path / 'unused')
    assert target in result


def test_expand_glob_files_ext_fallback(tmp_path: Path) -> None:
    (tmp_path / 'a.yaml').write_text('x', encoding='utf-8')
    result = _expand_glob_files(tmp_path / 'a', default_path=tmp_path / 'unused', ext='.yaml')
    assert (tmp_path / 'a.yaml') in result


def test_expand_glob_files_prefix_fallback(tmp_path: Path) -> None:
    (tmp_path / 'jobs-mine').write_text('x', encoding='utf-8')
    result = _expand_glob_files(tmp_path / 'mine', default_path=tmp_path / 'unused', prefix='jobs')
    assert (tmp_path / 'jobs-mine') in result


def test_expand_glob_files_prefix_and_ext_fallback(tmp_path: Path) -> None:
    (tmp_path / 'jobs-mine.yaml').write_text('x', encoding='utf-8')
    result = _expand_glob_files(tmp_path / 'mine', default_path=tmp_path / 'unused', ext='.yaml', prefix='jobs')
    assert (tmp_path / 'jobs-mine.yaml') in result


def test_expand_glob_files_default_path_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default = tmp_path / 'default'
    default.mkdir()
    (default / 'a.yaml').write_text('x', encoding='utf-8')
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    result = _expand_glob_files(Path('a.yaml'), default_path=default)
    assert any(p.name == 'a.yaml' and p.parent == default for p in result)


def test_expand_glob_files_glob_pattern_matches_multiple(tmp_path: Path) -> None:
    (tmp_path / 'a1.yaml').write_text('x', encoding='utf-8')
    (tmp_path / 'a2.yaml').write_text('x', encoding='utf-8')
    result = _expand_glob_files(tmp_path / 'a*.yaml', default_path=tmp_path / 'unused')
    names = {p.name for p in result}
    assert {'a1.yaml', 'a2.yaml'} <= names


def test_expand_glob_files_not_found_returns_input(tmp_path: Path) -> None:
    missing = tmp_path / 'nope.yaml'
    result = _expand_glob_files(missing, default_path=tmp_path / 'unused')
    assert result == [missing]


def test_locate_storage_file_finds_existing(tmp_path: Path) -> None:
    target = tmp_path / 'config.yaml'
    target.write_text('x', encoding='utf-8')
    assert locate_storage_file(target, default_path=tmp_path / 'unused') == target


def test_locate_storage_file_ext_fallback(tmp_path: Path) -> None:
    (tmp_path / 'config.yaml').write_text('x', encoding='utf-8')
    found = locate_storage_file(Path('config'), default_path=tmp_path, ext='.yaml', prefix='config')
    assert found == tmp_path / 'config.yaml'


def test_locate_storage_file_prefix_fallback(tmp_path: Path) -> None:
    (tmp_path / 'config-mine.yaml').write_text('x', encoding='utf-8')
    found = locate_storage_file(Path('mine'), default_path=tmp_path, ext='.yaml', prefix='config')
    assert found == tmp_path / 'config-mine.yaml'


def test_locate_glob_files_expands_pattern(tmp_path: Path) -> None:
    (tmp_path / 'jobs-a.yaml').write_text('x', encoding='utf-8')
    (tmp_path / 'jobs-b.yaml').write_text('x', encoding='utf-8')
    found = locate_glob_files([tmp_path / 'jobs-*.yaml'], default_path=tmp_path / 'unused')
    assert {p.name for p in found} == {'jobs-a.yaml', 'jobs-b.yaml'}


def test_locate_glob_files_keeps_order_given_and_sorts_matches(tmp_path: Path) -> None:
    for name in ('b.yaml', 'a.yaml', 'z.yaml'):
        (tmp_path / name).write_text('x', encoding='utf-8')
    found = locate_glob_files([tmp_path / 'z.yaml', tmp_path / '*.yaml'], default_path=tmp_path / 'unused')
    assert found == [tmp_path / 'z.yaml', tmp_path / 'a.yaml', tmp_path / 'b.yaml']


def test_expand_glob_files_directory_is_recursive(tmp_path: Path) -> None:
    jobs_dir = tmp_path / 'jobs'
    (jobs_dir / 'sub' / 'subsub').mkdir(parents=True)
    for name in ('x.yaml', 'sub/y.yaml', 'sub/subsub/z.yaml', 'sub/notes.txt'):
        (jobs_dir / name).write_text('x', encoding='utf-8')
    result = _expand_glob_files(jobs_dir, default_path=tmp_path / 'unused', ext='.yaml', prefix='jobs')
    assert result == [jobs_dir / 'sub' / 'subsub' / 'z.yaml', jobs_dir / 'sub' / 'y.yaml', jobs_dir / 'x.yaml']


def test_expand_glob_files_directory_in_default_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / 'hooks').mkdir()
    (tmp_path / 'hooks' / 'h.py').write_text('x', encoding='utf-8')
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert _expand_glob_files(Path('hooks'), default_path=tmp_path, ext='.py', prefix='hooks') == [
        tmp_path / 'hooks' / 'h.py'
    ]


def test_expand_glob_files_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / 'a.yaml').write_text('x', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    assert _expand_glob_files(Path(), default_path=tmp_path / 'unused', ext='.yaml', prefix='jobs') == [Path('a.yaml')]


def test_expand_glob_files_double_star_pattern(tmp_path: Path) -> None:
    (tmp_path / 'jobs' / 'sub').mkdir(parents=True)
    (tmp_path / 'jobs' / 'a.yaml').write_text('x', encoding='utf-8')
    (tmp_path / 'jobs' / 'sub' / 'b.yaml').write_text('x', encoding='utf-8')
    result = _expand_glob_files(tmp_path / 'jobs' / '**' / '*.yaml', default_path=tmp_path / 'unused')
    assert result == [tmp_path / 'jobs' / 'a.yaml', tmp_path / 'jobs' / 'sub' / 'b.yaml']


def _make_command_config(tmp_path: Path, args: list[str] | None = None) -> CommandConfig:
    return CommandConfig(
        args=args or [],
        config_path=tmp_path,
        config_file=tmp_path / 'config.yaml',
        jobs_def_file=tmp_path / 'jobs.yaml',
        hooks_def_file=tmp_path / 'hooks.py',
        ssdb_file=tmp_path / 'snapshots.db',
    )


def test_locate_jobs_and_hooks_files_from_config_directives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The configuration file's directives apply, with relative paths taken from its directory (not the current one)."""
    (tmp_path / 'jobs' / 'sub').mkdir(parents=True)
    (tmp_path / 'jobs' / 'a.yaml').write_text('x', encoding='utf-8')
    (tmp_path / 'jobs' / 'sub' / 'b.yaml').write_text('x', encoding='utf-8')
    (tmp_path / 'my_hooks.py').write_text('x', encoding='utf-8')
    (tmp_path / 'config.yaml').write_text('jobs: jobs\nhooks:\n  - my_hooks.py\n', encoding='utf-8')
    elsewhere = tmp_path / 'elsewhere'
    (elsewhere / 'jobs').mkdir(parents=True)
    (elsewhere / 'jobs' / 'decoy.yaml').write_text('x', encoding='utf-8')
    monkeypatch.chdir(elsewhere)
    cmd = _make_command_config(tmp_path)
    locate_jobs_and_hooks_files(cmd)
    assert cmd.jobs_files == [tmp_path / 'jobs' / 'a.yaml', tmp_path / 'jobs' / 'sub' / 'b.yaml']
    assert cmd.hooks_files == [tmp_path / 'my_hooks.py']
    assert cmd.hooks_files_inputted


def test_locate_jobs_and_hooks_files_cli_overrides_config(tmp_path: Path) -> None:
    (tmp_path / 'jobs-cli.yaml').write_text('x', encoding='utf-8')
    (tmp_path / 'jobs-config.yaml').write_text('x', encoding='utf-8')
    (tmp_path / 'config.yaml').write_text('jobs: jobs-config.yaml\n', encoding='utf-8')
    cmd = _make_command_config(tmp_path, ['--jobs', str(tmp_path / 'jobs-cli.yaml')])
    locate_jobs_and_hooks_files(cmd)
    assert cmd.jobs_files == [tmp_path / 'jobs-cli.yaml']
    assert cmd.hooks_files == [tmp_path / 'hooks.py']
    assert not cmd.hooks_files_inputted


@pytest.mark.parametrize(
    'config_text',
    ['footnote: x\n', 'jobs: null\n', 'jobs: []\n', 'jobs: 3\n', '- a list\n', 'jobs: [unclosed\n'],
    ids=['absent', 'null', 'empty', 'invalid', 'not-a-mapping', 'yaml-error'],
)
def test_locate_jobs_and_hooks_files_defaults(tmp_path: Path, config_text: str) -> None:
    """Without valid directives, the defaults are used; invalid ones are reported when the configuration is loaded."""
    (tmp_path / 'jobs.yaml').write_text('x', encoding='utf-8')
    (tmp_path / 'config.yaml').write_text(config_text, encoding='utf-8')
    cmd = _make_command_config(tmp_path)
    locate_jobs_and_hooks_files(cmd)
    assert cmd.jobs_files == [tmp_path / 'jobs.yaml']
    assert cmd.hooks_files == [tmp_path / 'hooks.py']


def test_first_run_creates_jobs_file_in_empty_directory(tmp_path: Path) -> None:
    jobs_dir = tmp_path / 'jobs'
    jobs_dir.mkdir()
    cmd = _make_command_config(tmp_path, ['--jobs', str(jobs_dir)])
    cmd.edit = cmd.edit_config = False
    locate_jobs_and_hooks_files(cmd)
    assert cmd.jobs_files == [jobs_dir]
    first_run(cmd)
    assert cmd.jobs_files == [jobs_dir / 'jobs.yaml']
    assert (jobs_dir / 'jobs.yaml').is_file()


def test_migrate_from_legacy_copies_when_dest_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    legacy_dir = fake_home / '.urlwatch'
    legacy_dir.mkdir()
    legacy_config = legacy_dir / 'urlwatch.yaml'
    payload = b'legacy: yes\n'
    legacy_config.write_bytes(payload)

    monkeypatch.setattr('webchanges.cli.Path.home', lambda: fake_home)
    monkeypatch.setattr(
        'webchanges.cli.platformdirs.user_cache_path',
        lambda _pkg: tmp_path / 'no-cache',
    )
    monkeypatch.setattr('webchanges.cli.platformdirs.user_config_path', lambda _pkg: tmp_path / 'no-config')

    new_config = tmp_path / 'new' / 'config.yaml'
    with caplog.at_level(logging.WARNING, logger='webchanges.cli'):
        migrate_from_legacy('urlwatch', config_file=new_config)

    assert new_config.is_file()
    assert new_config.read_bytes() == payload
    assert any('Copied urlwatch' in r.message for r in caplog.records)


def test_migrate_from_legacy_platform_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ~/.urlwatch, files are copied from urlwatch's platform configuration directory.

    That is where urlwatch keeps them in that case (fixed in 3.39).
    """
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    platform_dir = tmp_path / 'platform-config' / 'urlwatch'
    platform_dir.mkdir(parents=True)
    (platform_dir / 'urls.yaml').write_bytes(b'url: https://example.com/\n')

    monkeypatch.setattr('webchanges.cli.Path.home', lambda: fake_home)
    monkeypatch.setattr('webchanges.cli.platformdirs.user_cache_path', lambda _pkg: tmp_path / 'no-cache')
    monkeypatch.setattr('webchanges.cli.platformdirs.user_config_path', lambda _pkg: platform_dir)

    new_jobs = tmp_path / 'new' / 'jobs.yaml'
    migrate_from_legacy('urlwatch', jobs_file=new_jobs)
    assert new_jobs.read_bytes() == b'url: https://example.com/\n'


def test_migrate_from_legacy_skips_when_dest_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake_home = tmp_path / 'home'
    (fake_home / '.urlwatch').mkdir(parents=True)
    (fake_home / '.urlwatch' / 'urlwatch.yaml').write_bytes(b'legacy\n')

    monkeypatch.setattr('webchanges.cli.Path.home', lambda: fake_home)
    monkeypatch.setattr(
        'webchanges.cli.platformdirs.user_cache_path',
        lambda _pkg: tmp_path / 'no-cache',
    )
    monkeypatch.setattr('webchanges.cli.platformdirs.user_config_path', lambda _pkg: tmp_path / 'no-config')

    new_config = tmp_path / 'new' / 'config.yaml'
    new_config.parent.mkdir()
    new_config.write_bytes(b'already here\n')

    with caplog.at_level(logging.WARNING, logger='webchanges.cli'):
        migrate_from_legacy('urlwatch', config_file=new_config)

    assert new_config.read_bytes() == b'already here\n'
    assert not any('Copied urlwatch' in r.message for r in caplog.records)


def test_migrate_from_legacy_noop_when_no_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr('webchanges.cli.Path.home', lambda: fake_home)
    monkeypatch.setattr(
        'webchanges.cli.platformdirs.user_cache_path',
        lambda _pkg: tmp_path / 'no-cache',
    )
    monkeypatch.setattr('webchanges.cli.platformdirs.user_config_path', lambda _pkg: tmp_path / 'no-config')

    new_config = tmp_path / 'new' / 'config.yaml'
    migrate_from_legacy('urlwatch', config_file=new_config)
    assert not new_config.exists()


def test_load_hooks_imports_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = Path(__file__).parent / 'data' / 'hooks_example.py'
    dest = tmp_path / 'hooks.py'
    dest.write_bytes(src.read_bytes())
    monkeypatch.setattr('webchanges.cli.file_ownership_checks', lambda _p: [])

    saved = sys.modules.pop('hooks', None)
    try:
        load_hooks(dest, is_default=False)
        assert 'hooks' in sys.modules
        assert hasattr(sys.modules['hooks'], 'CustomLoginJob')
    finally:
        sys.modules.pop('hooks', None)
        if saved is not None:
            sys.modules['hooks'] = saved


def test_load_hooks_ownership_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / 'hooks.py'
    dest.write_text('x = 1\n', encoding='utf-8')
    monkeypatch.setattr('webchanges.cli.file_ownership_checks', lambda _p: ['it is bad'])

    saved = sys.modules.pop('hooks', None)
    try:
        with pytest.warns(RuntimeWarning, match='not not imported because'):
            load_hooks(dest, is_default=False)
        assert 'hooks' not in sys.modules
    finally:
        if saved is not None:
            sys.modules['hooks'] = saved


def test_handle_unitialized_actions_noop() -> None:
    cfg = cast(
        'CommandConfig',
        SimpleNamespace(
            check_new=False,
            install_chrome=False,
            detailed_versions=False,
            edit=False,
            edit_config=False,
            edit_hooks=False,
            features=False,
        ),
    )
    assert handle_unitialized_actions(cfg) is None


def test_handle_unitialized_actions_check_new_new_release(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr('webchanges.cli.get_new_version_number', lambda timeout, force_refresh: '99.0.0')
    cfg = cast(
        'CommandConfig',
        SimpleNamespace(
            check_new=True,
            install_chrome=False,
            detailed_versions=False,
            edit=False,
            edit_config=False,
            edit_hooks=False,
        ),
    )
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(cfg)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert 'New release version 99.0.0 is available' in out


def test_handle_unitialized_actions_check_new_up_to_date(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr('webchanges.cli.get_new_version_number', lambda timeout, force_refresh: '')
    cfg = cast(
        'CommandConfig',
        SimpleNamespace(
            check_new=True,
            install_chrome=False,
            detailed_versions=False,
            edit=False,
            edit_config=False,
            edit_hooks=False,
        ),
    )
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(cfg)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert 'You are running the latest release.' in out


def test_handle_unitialized_actions_check_new_pypi_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr('webchanges.cli.get_new_version_number', lambda timeout, force_refresh: False)
    cfg = cast(
        'CommandConfig',
        SimpleNamespace(
            check_new=True,
            install_chrome=False,
            detailed_versions=False,
            edit=False,
            edit_config=False,
            edit_hooks=False,
        ),
    )
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(cfg)
    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert 'Error contacting PyPI' in out


def test_handle_unitialized_actions_check_new_prerelease(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr('webchanges.cli.get_new_version_number', lambda timeout, force_refresh: True)
    cfg = cast(
        'CommandConfig',
        SimpleNamespace(
            check_new=True,
            install_chrome=False,
            detailed_versions=False,
            edit=False,
            edit_config=False,
            edit_hooks=False,
        ),
    )
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(cfg)
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert 'You are running a pre-release.' in out


def test_show_detailed_versions(capsys: pytest.CaptureFixture[str]) -> None:
    assert show_detailed_versions() == 0
    assert f'• {__project_name__}: {__version__}\n' in capsys.readouterr().out


def test_handle_unitialized_actions_detailed_versions(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = cast(
        'CommandConfig',
        SimpleNamespace(
            check_new=False,
            install_chrome=False,
            detailed_versions=True,
            edit=False,
            edit_config=False,
            edit_hooks=False,
        ),
    )
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(cfg)
    assert excinfo.value.code == 0
    assert f'• {__project_name__}: {__version__}\n' in capsys.readouterr().out


def test_handle_unitialized_actions_features(
    command_config: CommandConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.features = True
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(command_config, command_config.config_file)
    assert excinfo.value.code == 0
    assert '* browser - Retrieve a URL using a real web browser (use_browser: true).' in capsys.readouterr().out


# --- Edit actions ---


def test_handle_unitialized_actions_edit_jobs(
    command_config: CommandConfig,
    dummy_editor: None,
) -> None:
    command_config.edit = True
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(command_config, command_config.config_file)
    assert excinfo.value.code == 0


def test_handle_unitialized_actions_edit_using_visual(
    command_config: CommandConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('VISUAL', 'rundll32' if sys.platform == 'win32' else 'true')
    monkeypatch.delenv('EDITOR', raising=False)
    command_config.edit = True
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(command_config, command_config.config_file)
    assert excinfo.value.code == 0


def test_handle_unitialized_actions_edit_jobs_fail(
    command_config: CommandConfig,
    jobs_file_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv('EDITOR', 'does_not_exist_and_should_trigger_an_error')
    monkeypatch.delenv('VISUAL', raising=False)
    command_config.edit = True
    with pytest.raises(OSError) as excinfo:
        handle_unitialized_actions(command_config, command_config.config_file)
    jobs_edit = jobs_file_path.with_stem(jobs_file_path.stem + '_edit')
    jobs_edit.unlink(missing_ok=True)
    assert excinfo.value.args[0] == ('pytest: reading from stdin while output is captured!  Consider using `-s`.')
    assert 'Errors in updating file:' in capsys.readouterr().out


def test_handle_unitialized_actions_edit_config(
    command_config: CommandConfig,
    dummy_editor: None,
) -> None:
    command_config.edit_config = True
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(command_config, command_config.config_file)
    assert excinfo.value.code == 0


def test_handle_unitialized_actions_edit_config_fail(
    command_config: CommandConfig,
    config_file_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv('EDITOR', 'does_not_exist_and_should_trigger_an_error')
    monkeypatch.delenv('VISUAL', raising=False)
    command_config.edit_config = True
    with pytest.raises(OSError) as excinfo:
        handle_unitialized_actions(command_config, command_config.config_file)
    config_edit = config_file_path.with_stem(config_file_path.stem + '_edit')
    config_edit.unlink(missing_ok=True)
    assert excinfo.value.args[0] == ('pytest: reading from stdin while output is captured!  Consider using `-s`.')
    assert 'Errors in updating file:' in capsys.readouterr().out


def test_handle_unitialized_actions_edit_hooks(
    command_config: CommandConfig,
    hooks_file_path: Path,
    dummy_editor: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command_config.edit_hooks = True
    with pytest.raises(SystemExit) as excinfo:
        handle_unitialized_actions(command_config, command_config.config_file)
    assert excinfo.value.code == 0
    assert capsys.readouterr().out == f'Saved edits in {hooks_file_path}.\n'


def test_handle_unitialized_actions_edit_hooks_fail(
    command_config: CommandConfig,
    hooks_file_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv('EDITOR', 'does_not_exist_and_should_trigger_an_error')
    monkeypatch.delenv('VISUAL', raising=False)
    command_config.edit_hooks = True
    with pytest.raises(OSError) as excinfo:
        handle_unitialized_actions(command_config, command_config.config_file)
    hooks_edit = hooks_file_path.with_stem(hooks_file_path.stem + '_edit')
    hooks_edit.unlink(missing_ok=True)
    assert excinfo.value.args[0] == ('pytest: reading from stdin while output is captured!  Consider using `-s`.')
    assert 'Parsing failed:' in capsys.readouterr().out


def test_python_version_warning(capsys: pytest.CaptureFixture[str]) -> None:
    """Issuance of deprecation warning when running on the minimum supported Python version."""
    python_version_warning()
    message = capsys.readouterr().out
    if sys.version_info[0:2] == __min_python_version__:
        current_minor_version = '.'.join(str(n) for n in sys.version_info[0:2])
        assert message.startswith(
            f'WARNING: Support for Python {current_minor_version} will be ending three years from the date Python '
        )
    else:
        assert not message


def _raise_broken_pipe() -> None:
    raise BrokenPipeError(32, 'Broken pipe')


class _BrokenStdout(io.StringIO):
    """A stdout whose reader has gone away: flushing it raises BrokenPipeError."""

    def __init__(self, fd: int) -> None:
        super().__init__()
        self._fd = fd

    def flush(self) -> None:
        raise BrokenPipeError(32, 'Broken pipe')

    def fileno(self) -> int:
        return self._fd


def test_main_exits_quietly_when_stdout_reader_goes_away(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A BrokenPipeError from stdout (e.g. `webchanges --list | head`) ends the program with exit code 1."""
    monkeypatch.setattr(cli_module, '_main', _raise_broken_pipe)
    with tmp_path.joinpath('stdout').open('w') as fake_stdout_file:
        monkeypatch.setattr(sys, 'stdout', _BrokenStdout(fake_stdout_file.fileno()))
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            cli_module.main()
    assert pytest_wrapped_e.value.code == 1


def test_main_reraises_broken_pipe_not_from_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A BrokenPipeError from elsewhere (e.g. a server closing a connection) is a real error and is not swallowed."""
    monkeypatch.setattr(cli_module, '_main', _raise_broken_pipe)
    monkeypatch.setattr(sys, 'stdout', io.StringIO())
    with pytest.raises(BrokenPipeError):
        cli_module.main()


@pytest.mark.skipif(sys.platform == 'win32', reason='SIGPIPE does not exist on Windows')
def test_importing_cli_leaves_sigpipe_ignored() -> None:
    """Importing cli must not restore SIGPIPE's default action, which would kill the process on a closed socket."""
    assert signal.getsignal(signal.SIGPIPE) == signal.SIG_IGN  # ty:ignore[unresolved-attribute]


def test_first_run_creates_default_config_and_jobs_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Default config and jobs files are created when neither exists."""
    config_file = tmp_path / 'config.yaml'
    jobs_file = tmp_path / 'jobs.yaml'
    hooks_file = tmp_path / 'hooks.py'
    cmd = CommandConfig(
        args=[],
        config_path=tmp_path,
        config_file=config_file,
        jobs_def_file=jobs_file,
        hooks_def_file=hooks_file,
        ssdb_file=':memory:',  # ty:ignore[invalid-argument-type]
    )
    cmd.edit = False
    first_run(cmd)
    out = capsys.readouterr().out
    assert 'Created default config file at ' in out
    assert 'Created default jobs file at ' in out
    assert config_file.is_file()
    assert jobs_file.is_file()


def test_load_hooks_missing_file_warns_when_inputted(tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
    """A missing hooks file emits a ``RuntimeWarning`` when not the default location."""
    missing = tmp_path / 'hooks_does_not_exist.py'
    load_hooks(missing, is_default=False)
    assert len(recwarn) == 1
    message = recwarn.pop(RuntimeWarning).message.args[0]  # ty:ignore[unresolved-attribute]
    assert message == f'Hooks file {missing} not imported because it does not exist or is not a file'


def test_load_hooks_missing_default_file_logs_info(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, recwarn: pytest.WarningsRecorder
) -> None:
    """A missing default hooks file logs INFO and does not warn."""
    missing = tmp_path / 'hooks_does_not_exist.py'
    with caplog.at_level(logging.INFO, logger='webchanges.cli'):
        load_hooks(missing, is_default=True)
    assert len(recwarn) == 0
    assert f'Hooks file {missing} does not exist or is not a file' in caplog.text


def test_exit_on_user_error_shows_only_the_message(capsys: pytest.CaptureFixture[str]) -> None:
    """A user's error (e.g. in the configuration or jobs file) exits with 1, showing its message without a traceback."""
    import yaml

    file_errors = (ValueError, yaml.YAMLError)
    with pytest.raises(SystemExit) as exc_info, exit_on_user_error(None, file_errors):
        raise ValueError("Error in directive 'suppress_errors' of job 1:\n")
    assert exc_info.value.code == 1
    assert capsys.readouterr().err == (
        "Error in directive 'suppress_errors' of job 1:\n\nRun with -v to also show the traceback.\n"
    )

    with pytest.raises(SystemExit), exit_on_user_error(0, file_errors):
        yaml.safe_load('a: [unclosed')
    assert capsys.readouterr().err.startswith('while parsing a flow sequence')


def test_exit_on_user_error_verbose_or_other_errors_propagate() -> None:
    """With -v the error keeps its traceback; exceptions other than the ones given are never caught."""
    with pytest.raises(ValueError, match='bad value'), exit_on_user_error(1, (ValueError,)):
        raise ValueError('bad value')
    with pytest.raises(KeyError), exit_on_user_error(None, (ValueError,)):
        raise KeyError('a bug')


def test_update_schema_hashes_script(tmp_path: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
    try:
        import update_schema_hashes
    finally:
        sys.path.pop(0)

    schema = tmp_path / 'demo.schema.json'
    schema.write_bytes(b'{"x": 1}')

    rc = update_schema_hashes.main([str(schema)])
    expected = hashlib.sha256(b'{"x": 1}').hexdigest()
    assert (tmp_path / '.demo.schema.sha256').read_text(encoding='utf-8').strip() == expected
    assert rc == 1

    rc_noop = update_schema_hashes.main([str(schema)])
    assert rc_noop == 0
