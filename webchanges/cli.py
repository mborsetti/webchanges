#!/usr/bin/env python3

"""Module containing the entry point: the function main()."""

# See config module for the command line arguments.

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import warnings
from pathlib import Path, PurePath

import platformdirs

from webchanges import __copyright__, __docs_url__, __min_python_version__, __project_name__, __version__
from webchanges.config import CommandConfig
from webchanges.util import edit_file, file_ownership_checks, get_new_version_number, import_module_from_source

# Restore the default system behavior for the SIGPIPE signal, which is ignored by Python by default.
# This prevents a BrokenPipeError when piping output to a command like `less` that may close the pipe before reading all
# of the output.
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # not defined in Windows  # ty:ignore[unresolved-attribute]
except AttributeError:
    pass


logger = logging.getLogger(__name__)


def python_version_warning() -> None:
    """Check if we're running on the minimum Python version supported and if so print and issue a pending deprecation
    warning.
    """
    if sys.version_info[0:2] == __min_python_version__:
        current_minor_version = '.'.join(str(n) for n in sys.version_info[0:2])
        next_minor_version = f'{__min_python_version__[0]}.{__min_python_version__[1] + 1}'
        warning = (
            f'Support for Python {current_minor_version} will be ending three years from the date Python '
            f'{next_minor_version} was released'
        )
        print(f'WARNING: {warning}\n')
        PendingDeprecationWarning(warning)


def migrate_from_legacy(
    legacy_package: str,
    config_file: Path | None = None,
    jobs_file: Path | None = None,
    hooks_file: Path | None = None,
    ssdb_file: Path | None = None,
) -> None:
    """Check for existence of legacy files for configuration, jobs and Python hooks and migrate them (i.e. make a copy
    to new folder and/or name). Original files are not deleted.

    :param legacy_package: The name of the legacy package to migrate (e.g. urlwatch).
    :param config_file: The new Path to the configuration file.
    :param jobs_file: The new Path to the jobs file.
    :param hooks_file: The new Path to the hooks file.
    :param ssdb_file: The new Path to the snapshot database file.
    """
    legacy_project_path = Path.home().joinpath(f'.{legacy_package}')
    leagacy_config_file = legacy_project_path.joinpath(f'{legacy_package}.yaml')
    legacy_urls_file = legacy_project_path.joinpath('urls.yaml')
    legacy_hooks_file = legacy_project_path.joinpath('hooks.py')
    legacy_cache_path = platformdirs.user_cache_path(legacy_package)
    legacy_cache_file = legacy_cache_path.joinpath('cache.db')
    for old_file, new_file in zip(
        (leagacy_config_file, legacy_urls_file, legacy_hooks_file, legacy_cache_file),
        (config_file, jobs_file, hooks_file, ssdb_file),
        strict=False,
    ):
        if new_file and old_file.is_file() and not new_file.is_file():
            new_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(old_file, new_file)
            logger.warning(f"Copied {legacy_package} '{old_file}' file to {__project_name__} '{new_file}'.")
            logger.warning(f"You can safely delete '{old_file}'.")


def setup_logger(verbose: int | None = None, log_file: Path | None = None) -> None:
    """Set up the logger.

    :param verbose: the verbosity level (1 = INFO, 2 = ERROR, 3 = NOTSET).
    """
    if log_file:
        handlers: tuple[logging.Handler, ...] | None = (logging.FileHandler(log_file),)
        if not verbose:
            verbose = 1
    else:
        handlers = None

    log_level = None

    if verbose is not None:
        if verbose >= 3:
            log_level = 'NOTSET'
            # https://playwright.dev/python/docs/debug#verbose-api-logs
            os.environ['DEBUG'] = 'pw:api pytest -s'
        elif verbose >= 2:
            log_level = 'DEBUG'
            # https://playwright.dev/python/docs/debug#verbose-api-logs
            os.environ['DEBUG'] = 'pw:api pytest -s'
        elif verbose == 1:
            log_level = 'INFO'

    # if not verbose:
    #     sys.tracebacklimit = 0

    logging.basicConfig(
        format='%(asctime)s %(module)s[%(thread)s] %(levelname)s: %(message)s',
        level=log_level,
        handlers=handlers,
    )
    logger.info(f'{__project_name__}: {__version__} {__copyright__}')
    logger.info(
        f'{platform.python_implementation()}: {platform.python_version()} '
        f'{platform.python_build()} {platform.python_compiler()}'
    )
    logger.info(f'System: {platform.platform()}')


def teardown_logger(verbose: int | None = None) -> None:
    """Clean up logging.

    :param verbose: the verbosity level (1 = INFO, 2 = ERROR).
    """
    if verbose is not None and verbose >= 2:
        # https://playwright.dev/python/docs/debug#verbose-api-logs
        os.environ.pop('DEBUG', None)


def _expand_glob_files(
    filename: Path,
    default_path: Path,
    ext: str | None = None,
    prefix: str | None = None,
) -> list[Path]:
    """Searches for file both as specified and in the default directory, then retries with 'ext' extension if defined.

    :param filename: The filename.
    :param default_path: The default directory.
    :param ext: The extension, e.g. '.yaml', to add for searching if first scan fails.
    :param prefix: The prefix, e.g. 'config', to add with a hypen (e.g. 'config-') for searching if first scan fails.

    :returns: The filename, either original or one with path where found and/or extension.
    """
    search_filenames = [filename]

    # if ext is given, iterate both on raw filename and the filename with ext if different
    if ext and filename.suffix != ext:
        search_filenames.append(filename.with_suffix(ext))

    # if prefix is given, iterate both on raw filename and the filename with prefix if different
    if prefix and not filename.name.startswith(prefix):
        search_filenames.append(filename.with_stem(f'{prefix}-{filename.stem}'))
        if ext and filename.suffix != ext:
            search_filenames.append(filename.with_stem(f'{prefix}-{filename.stem}').with_suffix(ext))

    # try as given
    for file in search_filenames:
        # https://stackoverflow.com/questions/56311703/globbing-absolute-paths-with-pathlib
        file_list = list(Path(file.anchor).glob(str(file.relative_to(file.anchor))))
        if any(f.is_file() for f in file_list):
            return file_list

        # no directory specified (and not in current one): add default one
        if not file.is_absolute() and Path(file).parent != Path.cwd():
            file_list = list(default_path.glob(str(file)))
            if any(f.is_file() for f in file_list):
                return file_list

    # no matches found
    return [filename]


def locate_glob_files(
    filenames: list[Path],
    default_path: Path,
    ext: str | None = None,
    prefix: str | None = None,
) -> list[Path]:
    job_files = set()
    for filename in filenames:
        for file in _expand_glob_files(filename, default_path, ext, prefix):
            job_files.add(file)
    return list(job_files)


def locate_storage_file(
    filename: Path,
    default_path: Path,
    ext: str | None = None,
    prefix: str | None = None,
) -> Path:
    """Searches for file both as specified and in the default directory, then retries with 'ext' extension if defined.

    :param filename: The filename.
    :param default_path: The default directory.
    :param ext: The extension, e.g. '.yaml', to add for searching if first scan fails.
    :param prefix: The prefix, e.g. 'config', to add with a hypen (e.g. 'config-') for searching if first scan fails.

    :returns: The filename, either original or one with path where found and/or extension.
    """
    search_filenames = [filename]

    # if ext is given, iterate both on raw filename and the filename with ext if different
    if ext and filename.suffix != ext:
        search_filenames.append(filename.with_suffix(ext))

    # if prefix is given, iterate both on raw filename and the filename with prefix if different
    if prefix and not filename.name.startswith(prefix):
        search_filenames.append(filename.with_stem(f'{prefix}-{filename.stem}'))
        if ext and filename.suffix != ext:
            search_filenames.append(filename.with_stem(f'{prefix}-{filename.stem}').with_suffix(ext))

    for file in search_filenames:
        # return if found
        if file.is_file():
            return file

        # no directory specified (and not in current one): add default one
        if file.parent == PurePath():
            new_file = default_path.joinpath(file)
            if new_file.is_file():
                return new_file

    # no matches found
    return filename


def locate_storage_files(
    filename_list: list[Path],
    default_path: Path,
    ext: str | None = None,
    prefix: str | None = None,
) -> set[Path]:
    """Searches for file both as specified and in the default directory, then retries with 'ext' extension if defined.

    :param filename_list: The list of filenames.
    :param default_path: The default directory.
    :param ext: The extension, e.g. '.yaml', to add for searching if first scan fails.
    :param prefix: The prefix, e.g. 'config', to add with a hypen (e.g. 'config-') for searching if first scan fails.

    :returns: The list filenames, either originals or ones with path where found and/or extension.
    """
    filenames = set()
    for filename in filename_list:
        filenames.add(locate_storage_file(filename, default_path, ext, prefix))
    return filenames


def first_run(command_config: CommandConfig) -> None:
    """Create configuration and jobs files.

    :param command_config: the CommandConfig containing the command line arguments selected.
    """
    if not command_config.config_file.is_file():
        command_config.config_file.parent.mkdir(parents=True, exist_ok=True)
        from webchanges.storage import YamlConfigStorage

        YamlConfigStorage.write_default_config(command_config.config_file)
        print(f'Created default config file at {command_config.config_file}')
        if not command_config.edit_config:
            print(f'> Edit it with {__project_name__} --edit-config')
    if not any(f.is_file() for f in command_config.jobs_files):
        command_config.jobs_files[0].parent.mkdir(parents=True, exist_ok=True)
        command_config.jobs_files[0].write_text(
            f'# {__project_name__} jobs file. See {__docs_url__}en/stable/jobs.html\n'
        )
        print(f'Created default jobs file at {command_config.jobs_files[0]}')
        if not command_config.edit:
            print(f'> Edit it with {__project_name__} --edit-jobs')


def load_hooks(hooks_file: Path, is_default: bool = False) -> None:
    """Load hooks file."""
    if not hooks_file.is_file():
        if is_default:
            logger.info(f'Hooks file {hooks_file} does not exist or is not a file')
        else:
            # do not use ImportWarning as it could be suppressed
            warnings.warn(
                f'Hooks file {hooks_file} not imported because it does not exist or is not a file',
                RuntimeWarning,
                stacklevel=1,
            )
        return

    hooks_file_errors = file_ownership_checks(hooks_file)
    if hooks_file_errors:
        logger.debug('Here should come the warning')
        # do not use ImportWarning as it could be suppressed
        warnings.warn(
            f'Hooks file {hooks_file} not not imported because{" and ".join(hooks_file_errors)}.\n'
            f'(see {__docs_url__}en/stable/hooks.html#important-note-for-hooks-file)',
            RuntimeWarning,
            stacklevel=1,
        )
    else:
        logger.info(f'Importing into hooks module from {hooks_file}')
        import_module_from_source('hooks', hooks_file)
        logger.info('Finished importing into hooks module')


def sync_bundled_schemas(command_config: CommandConfig) -> None:
    """Deploy bundled JSON schemas next to the user's ``config.yaml`` and ``jobs.yaml``.

    ``config.schema.json`` is written next to the ``--config`` file; ``jobs.schema.json`` next to the first
    ``--jobs`` file. A sibling ``.*.sha256`` file records the deployed hash so subsequent runs can detect when the
    bundled schema has changed without re-hashing on every invocation.
    """
    from importlib.resources import files as resource_files

    try:
        schema_root = resource_files('webchanges._resources')
    except (ModuleNotFoundError, FileNotFoundError):
        logger.debug('Bundled schemas package not found; skipping schema sync.')
        return

    targets = [('config.schema', command_config.config_file.parent)]
    if command_config.jobs_files:
        targets.append(('jobs.schema', command_config.jobs_files[0].parent))

    for stem, target_dir in targets:
        bundled_hash_resource = schema_root / f'.{stem}.sha256'
        try:
            bundled_hash = bundled_hash_resource.read_text(encoding='utf-8').strip()
        except (FileNotFoundError, OSError):
            logger.debug(f'Bundled hash .{stem}.sha256 not available; skipping.')
            continue
        if not bundled_hash:
            logger.debug(f'Bundled hash .{stem}.sha256 is empty; skipping.')
            continue

        deployed_hash_file = target_dir / f'.{stem}.sha256'
        try:
            deployed_hash = deployed_hash_file.read_text(encoding='utf-8').strip() or None
        except (FileNotFoundError, OSError):
            deployed_hash = None
        if deployed_hash == bundled_hash:
            continue

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            schema_dest = target_dir / f'{stem}.json'
            tmp_schema = schema_dest.parent / (schema_dest.name + '.tmp')
            tmp_schema.write_bytes((schema_root / f'{stem}.json').read_bytes())
            tmp_schema.replace(schema_dest)
            tmp_hash = deployed_hash_file.parent / (deployed_hash_file.name + '.tmp')
            tmp_hash.write_text(f'{bundled_hash}\n', encoding='utf-8')
            tmp_hash.replace(deployed_hash_file)
        except OSError as e:
            logger.info(f'Could not deploy {stem}.json to {target_dir}: {e}')
            continue
        logger.info(f'Updated {schema_dest} (sha256 {bundled_hash[:12]}…).')


def handle_unitialized_actions(urlwatch_config: CommandConfig, default_config_file: Path | None = None) -> None:
    """Handles CLI actions that do not require all classes etc. to be initialized (and command.py loaded). For speed
    purposes.

    The editor commands (``--edit-jobs``, ``--edit-config``, ``--edit-hooks``) are dispatched here too so that a
    malformed user file does not block the user from opening it. ``default_config_file`` is the platform default so
    we can mirror ``main()``'s ``first_run`` gate.
    """

    def _exit(arg: str | int | None) -> None:
        logger.info(f'Exiting with exit code {arg}')
        sys.exit(arg)

    def print_new_version() -> int:
        """Will print alert message if a newer version is found on PyPi."""
        print(f'{__project_name__} {__version__}.', end='')
        new_release = get_new_version_number(timeout=2)
        if new_release:
            print(
                f'\nNew release version {new_release} is available; we recommend updating using e.g. '
                f"'pip install -U {__project_name__}'."
            )
            return 0
        if new_release == '':
            print(' You are running the latest release.')
            return 0
        print(' Error contacting PyPI to determine the latest release.')
        return 1

    def playwright_install_chrome() -> int:  # pragma: no cover
        """Replicates playwright.___main__.main() function, which is called by the playwright executable, in order to
        install the browser executable.

        :return: Playwright's executable return code.
        """
        try:
            from playwright._impl._driver import compute_driver_executable
        except ImportError:  # pragma: no cover
            raise ImportError('Python package playwright is not installed; cannot install the Chrome browser') from None

        driver_executable = compute_driver_executable()
        env = os.environ.copy()
        env['PW_CLI_TARGET_LANG'] = 'python'
        cmd = [str(driver_executable), 'install', 'chrome']
        logger.info(f'Running playwright CLI: {" ".join(cmd)}')
        completed_process = subprocess.run(cmd, check=False, env=env, capture_output=True, text=True)  # noqa: S603
        if completed_process.returncode:
            print(completed_process.stderr)
            return completed_process.returncode
        if completed_process.stdout:
            logger.info(f'Success! Output of Playwright CLI: {completed_process.stdout}')
        return 0

    if urlwatch_config.check_new:
        _exit(print_new_version())

    if urlwatch_config.install_chrome:  # pragma: no cover
        _exit(playwright_install_chrome())

    if urlwatch_config.detailed_versions:
        _exit(show_detailed_versions())

    if urlwatch_config.edit or urlwatch_config.edit_config or urlwatch_config.edit_hooks:
        # Resolve paths and run the same first-run / schema-sync setup that main() does, so editing works
        # identically regardless of which dispatch path runs the command.
        urlwatch_config.config_file = locate_storage_file(
            filename=urlwatch_config.config_file,
            default_path=urlwatch_config.config_path,
            ext='.yaml',
            prefix='config',
        )
        urlwatch_config.jobs_files = locate_glob_files(
            filenames=urlwatch_config.jobs_files,
            default_path=urlwatch_config.config_path,
            ext='.yaml',
            prefix='jobs',
        )
        urlwatch_config.hooks_files = locate_glob_files(
            filenames=urlwatch_config.hooks_files,
            default_path=urlwatch_config.config_path,
            ext='.py',
            prefix='hooks',
        )
        sync_bundled_schemas(urlwatch_config)
        if (
            default_config_file is not None
            and urlwatch_config.config_file == default_config_file
            and not Path(urlwatch_config.config_file).is_file()
        ):
            first_run(urlwatch_config)
        if urlwatch_config.edit_hooks:
            _exit(_edit_hooks_files(urlwatch_config.hooks_files))
        if urlwatch_config.edit_config:
            _exit(_edit_config_file(urlwatch_config.config_file))
        if urlwatch_config.edit:
            _exit(_edit_jobs_files(urlwatch_config.jobs_files))


def _edit_jobs_files(jobs_files: list[Path]) -> int:
    """Open the jobs file in the user's editor and validate it on save."""
    from webchanges.storage import YamlJobsStorage

    return YamlJobsStorage(jobs_files).edit()


def _edit_config_file(config_file: Path) -> int:
    """Open the configuration file in the user's editor and validate it on save."""
    from webchanges.storage import YamlConfigStorage

    return YamlConfigStorage(config_file).edit()


def _edit_hooks_files(hooks_files: list[Path]) -> int:
    """Open each hooks file in the user's editor and validate it on save."""
    # Mirrors the original logic from UrlwatchCommand.edit_hooks.
    for hooks_file in hooks_files:
        logger.debug(f'Edit file {hooks_file}')
        hooks_edit = hooks_file.with_stem(hooks_file.stem + '_edit')
        if hooks_file.exists():
            shutil.copy(hooks_file, hooks_edit)

        while True:
            try:
                edit_file(hooks_edit)
                import_module_from_source('hooks', hooks_edit)
                break
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001 Do not catch blind exception: `Exception`
                print('Parsing failed:')
                print('======')
                print(e)
                print('======')
                print()
                print(f'The file {hooks_file} was NOT updated.')
                user_input = input('Do you want to retry the same edit? (Y/n)')
                if not user_input or user_input.lower()[0] == 'y':
                    continue
                hooks_edit.unlink()
                print('No changes have been saved.')
                return 1

        if hooks_file.is_symlink():
            hooks_file.write_text(hooks_edit.read_text())
        else:
            hooks_edit.replace(hooks_file)
        hooks_edit.unlink(missing_ok=True)
        print(f'Saved edits in {hooks_file}.')

    return 0


def _print_dist_sub_deps(name: str, raw: list[str]) -> None:
    """Print sub-dependencies of distribution ``name`` from its PEP 508 requirement strings ``raw``.

    Uses ``packaging.requirements.Requirement`` to honour markers (``python_version``, ``sys_platform``, ``extra``, ...)
    when available. Falls back to a regex that strips version specifiers but cannot evaluate markers.
    """
    import importlib.metadata
    import re

    try:
        from packaging.requirements import InvalidRequirement, Requirement
    except ImportError:
        # Fallback: requirements without whitespace before the operator (e.g. ``httpx>=0.20``) would otherwise be
        # treated as invalid distribution names; this regex strips the specifier so the lookup succeeds.
        for req_name in sorted({re.split('[ <>=;#^[]', i)[0] for i in raw}):
            try:
                installed = importlib.metadata.distribution(req_name)
            except ModuleNotFoundError:
                continue
            print(f'  - {req_name}: {installed.version}')
        return

    # Try every extra the package declares so that, e.g., an ``extra == "crypto"`` dep shows up if the user installed
    # ``package[crypto]``.
    try:
        extras = set(importlib.metadata.metadata(name).get_all('Provides-Extra') or [])
    except importlib.metadata.PackageNotFoundError:
        extras = set()
    envs = [{'extra': e} for e in ('', *extras)]
    seen: set[str] = set()
    for line in sorted(raw):
        try:
            req = Requirement(line)
        except InvalidRequirement:
            continue
        if req.marker is not None and not any(req.marker.evaluate(env) for env in envs):
            continue
        if req.name in seen:
            continue
        seen.add(req.name)
        try:
            installed = importlib.metadata.distribution(req.name)
        except ModuleNotFoundError:
            continue
        print(f'  - {req.name}: {installed.version}')


def show_detailed_versions() -> int:
    """Prints the detailed versions, including of dependencies.

    :return: 0.
    """
    import importlib.metadata
    import re
    import sqlite3
    from concurrent.futures import ThreadPoolExecutor

    def dependencies() -> list[str]:
        try:
            from pip._internal.metadata import get_default_environment

            env = get_default_environment()
            dist = None
            for dist in env.iter_all_distributions():
                if dist.canonical_name == __project_name__:
                    break
            if dist and dist.canonical_name == __project_name__:
                requires_dist = dist.metadata_dict.get('requires_dist', [])
                dependencies = {re.split('[ <>=;#^[]', d)[0] for d in requires_dist}
                dependencies.update(('httpx', 'packaging', 'simplejson', 'typeguard'))
                return sorted(dependencies, key=str.lower)
        except ImportError:
            pass

        # default list of all possible dependencies
        logger.info(f'Found no pip distribution for {__project_name__}; returning all possible dependencies.')
        deps = [
            'aioxmpp',
            'beautifulsoup4',
            'chump',
            'colorama',
            'cryptography',
            'cssbeautifier',
            'cssselect',
            'curl_cffi',
            'deepdiff',
            'h2',
            'html2text',
            'html5lib',
            'httpx',
            'jq',
            'jsbeautifier',
            'keyring',
            'lxml',
            'markdown2',
            'matrix_client',
            'msgpack',
            'packaging',
            'pdftotext',
            'Pillow',
            'platformdirs',
            'playwright',
            'psutil',
            'pushbullet.py',
            'pypdf',
            'pytesseract',
            'pyyaml',
            'redis',
            'requests',
            'simplejson',
            'typeguard',
            'typing-extensions',
            'tzdata',
            'vobject',
            'xmltodict',
        ]
        if sys.version_info < (3, 14):
            deps.append('zstandard')
        return sorted(deps)

    print('Software:')
    print(f'• {__project_name__}: {__version__}')
    print(
        f'• {platform.python_implementation()}: {platform.python_version()} '
        f'{platform.python_build()} {platform.python_compiler()}'
    )
    print(f'• SQLite: {sqlite3.sqlite_version}')

    try:
        import psutil
        from psutil._common import bytes2human

        print()
        print('System:')
        print(f'• Platform: {platform.platform()}, {platform.machine()}')
        print(f'• Processor: {platform.processor()}')
        print(f'• CPUs (logical): {psutil.cpu_count()}')
        try:
            virt_mem = psutil.virtual_memory().available
            print(
                f'• Free memory: {bytes2human(virt_mem)} physical plus {bytes2human(psutil.swap_memory().free)} swap.'
            )
        except psutil.Error as e:  # pragma: no cover
            print(f'• Free memory: Could not read information: {e}')
        print(
            f"• Free disk '/': {bytes2human(psutil.disk_usage('/').free)} ({100 - psutil.disk_usage('/').percent:.1f}%)"
        )
        executor = ThreadPoolExecutor()
        print(f'• --max-threads default value: {executor._max_workers}')
    except ImportError:
        pass

    print()
    print('Relevant PyPi packages:')
    for dist_name in dependencies():
        if dist_name == __project_name__:
            continue
        try:
            mod = importlib.metadata.distribution(dist_name)
        except ModuleNotFoundError:
            continue
        print(f'• {dist_name}: {mod.version}')
        if mod.requires:
            _print_dist_sub_deps(dist_name, mod.requires)

    # playwright
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        if psutil:
            try:
                virt_mem_before = psutil.virtual_memory().available
                swap_mem_before = psutil.swap_memory().free
            except psutil.Error:
                pass

        with sync_playwright() as p:
            try:
                print()
                print('Playwright browser:')
                browser = p.chromium.launch(channel='chrome')
                print(f'• Name: {browser.browser_type.name}')
                print(f'• Version: {browser.version}')
                if psutil:
                    try:
                        print(
                            f'• Free memory before launching browser: '
                            f'{bytes2human(virt_mem_before)} physical plus '
                            f'{bytes2human(swap_mem_before)} swap'
                        )
                    except NameError:
                        pass
                if psutil:
                    browser.new_page()
                    try:
                        virt_mem_loaded = psutil.virtual_memory().available
                        swap_mem_loaded = psutil.swap_memory().free
                        print(
                            f'• Free memory with browser running    : '
                            f'{bytes2human(virt_mem_loaded)} physical plus '
                            f'{bytes2human(swap_mem_loaded)} swap'
                        )
                    except psutil.Error:
                        pass
                    try:
                        virt_mem = virt_mem_before - virt_mem_loaded
                        swap_mem = swap_mem_before - swap_mem_loaded
                        print(
                            f'• Memory used by launching browser    : '
                            f'{bytes2human(virt_mem)} physical plus '
                            f'{bytes2human(swap_mem)} swap'
                        )
                    except NameError:
                        pass
                print(f'• Executable: {browser.browser_type.executable_path}')
            except PlaywrightError as e:
                print()
                print('Playwright browser:')
                print(f'• Error: {e}')
    except ImportError:
        pass

    if os.name == 'posix':
        print()
        print('Installed dpkg dependencies:')
        try:
            import apt

            apt_cache = apt.Cache()

            def print_version(libs: list[str]) -> None:
                for lib in libs:
                    if lib in apt_cache and apt_cache[lib].versions:
                        ver = apt_cache[lib].versions
                        print(f'   - {ver[0].package}: {ver[0].version}')

            installed_packages = {dist.metadata['Name'] for dist in importlib.metadata.distributions()}
            for module, apt_dists in (
                ('jq', ['jq']),
                # https://github.com/jalan/pdftotext#os-dependencies
                ('pdftotext', ['libpoppler-cpp-dev']),
                # https://pillow.readthedocs.io/en/latest/installation.html#external-libraries
                (
                    'Pillow',
                    [
                        'libjpeg-dev',
                        'zlib-dev',
                        'zlib1g-dev',
                        'libtiff-dev',
                        'libfreetype-dev',
                        'littlecms-dev',
                        'libwebp-dev',
                        'tcl/tk-dev',
                        'openjpeg-dev',
                        'libimagequant-dev',
                        'libraqm-dev',
                        'libxcb-dev',
                        'libxcb1-dev',
                    ],
                ),
                ('playwright', ['google-chrome-stable']),
                # https://tesseract-ocr.github.io/tessdoc/Installation.html
                ('pytesseract', ['tesseract-ocr']),
            ):
                if module in installed_packages:
                    importlib.metadata.distribution(module)
                    print(f'• {module}')
                    print_version(apt_dists)
        except ImportError:
            print('Dependencies cannot be printed as python3-apt is not installed.')
            print("Run 'sudo apt-get install python3-apt' to install.")
    print()
    return 0


def main() -> None:  # pragma: no cover
    """The entry point run when __name__ == '__main__'.

    Contains all the high-level logic to instantiate all classes that run the program.

    :raises NotImplementedError: If a `--database-engine` is specified that is not supported.
    :raises RuntimeError: If `--database-engine redis` is selected but `--cache` with a redis URI is not provided.
    """
    # Make sure that PendingDeprecationWarning are displayed from all modules (otherwise only those in __main__ are)
    warnings.filterwarnings('default', category=PendingDeprecationWarning)

    # Issue deprecation warning if running on minimum version supported
    python_version_warning()

    # Path where the config, jobs and hooks files are located
    if sys.platform != 'win32':
        config_path = platformdirs.user_config_path(__project_name__)  # typically ~/.config/{__project_name__}
    else:
        config_path = platformdirs.user_documents_path().joinpath(__project_name__)

    # Path where the snapshot database is located; typically ~/.local/share/{__project_name__} or
    # $XDG_DATA_HOME/{__project_name__} # in linux, ~/Library/Application Support/webchanges in macOS  and
    # or %LOCALAPPDATA%\{__project_name__}\{__project_name__} in Windows
    data_path = platformdirs.user_data_path(__project_name__, __project_name__.capitalize())

    # Default config, jobs, hooks and ssdb (database) files
    default_config_file = config_path.joinpath('config.yaml')
    default_jobs_file = config_path.joinpath('jobs.yaml')
    default_hooks_file = config_path.joinpath('hooks.py')
    default_ssdb_file = data_path.joinpath('snapshots.db')

    # Check for and if found migrate snapshot database file from version <= 3.21, which was called cache.db and located
    # in user_cache_path
    migrate_from_legacy('webchanges', ssdb_file=default_ssdb_file)

    # Check for and if found migrate legacy (urlwatch) files
    migrate_from_legacy('urlwatch', default_config_file, default_jobs_file, default_hooks_file, default_ssdb_file)

    # Parse command line arguments
    command_config = CommandConfig(
        sys.argv[1:],
        config_path,
        default_config_file,
        default_jobs_file,
        default_hooks_file,
        default_ssdb_file,
    )

    # Set up the logger to verbose if needed
    setup_logger(command_config.verbose, command_config.log_file)

    # log defaults
    logger.debug(f'Default config path is {config_path}')
    logger.debug(f'Default data path is {data_path}')

    # For speed, run these here
    handle_unitialized_actions(command_config, default_config_file)

    # Only now, after configuring logging, we can load other modules
    from webchanges.command import UrlwatchCommand
    from webchanges.main import Urlwatch
    from webchanges.storage import (
        SsdbDirStorage,
        SsdbRedisStorage,
        SsdbSQLite3Storage,
        SsdbStorage,
        YamlConfigStorage,
        YamlJobsStorage,
    )

    # Locate config, jobs, hooks and database files
    command_config.config_file = locate_storage_file(
        filename=command_config.config_file,
        default_path=command_config.config_path,
        ext='.yaml',
        prefix='config',
    )
    command_config.jobs_files = locate_glob_files(
        filenames=command_config.jobs_files,
        default_path=command_config.config_path,
        ext='.yaml',
        prefix='jobs',
    )
    command_config.hooks_files = locate_glob_files(
        filenames=command_config.hooks_files,
        default_path=command_config.config_path,
        ext='.py',
        prefix='hooks',
    )
    command_config.ssdb_file = locate_storage_file(
        filename=command_config.ssdb_file,
        default_path=data_path,
        ext='.db',
    )

    # Deploy bundled JSON schemas next to the user's config.yaml / jobs.yaml so editors can autocomplete and
    # validate.
    sync_bundled_schemas(command_config)

    # Check for first run
    if command_config.config_file == default_config_file and not Path(command_config.config_file).is_file():
        first_run(command_config)

    # Setup config file API
    config_storage = YamlConfigStorage(command_config.config_file)  # storage.py

    # load config (which for syntax checking requires hooks to be loaded too)
    if command_config.hooks_files:
        logger.debug(f'Hooks files to be loaded: {command_config.hooks_files}')
        for hooks_file in command_config.hooks_files:
            load_hooks(hooks_file, is_default=not command_config.hooks_files_inputted)
    config_storage.load()

    # Setup database API
    database_engine = command_config.database_engine or config_storage.config.get('database', {}).get('engine')
    max_snapshots = command_config.max_snapshots or config_storage.config.get('database', {}).get('max_snapshots')
    if database_engine == 'sqlite3':
        ssdb_storage: SsdbStorage = SsdbSQLite3Storage(command_config.ssdb_file, max_snapshots)  # storage.py
    elif any(str(command_config.ssdb_file).startswith(prefix) for prefix in ('redis://', 'rediss://')):
        ssdb_storage = SsdbRedisStorage(command_config.ssdb_file)  # storage.py
    elif database_engine.startswith('redis'):
        ssdb_storage = SsdbRedisStorage(database_engine)
    elif database_engine == 'textfiles':
        ssdb_storage = SsdbDirStorage(command_config.ssdb_file)  # storage.py
    elif database_engine == 'minidb':
        # legacy code imported only if needed (requires minidb, which is not a dependency)
        from webchanges.storage_minidb import SsdbMiniDBStorage

        ssdb_storage = SsdbMiniDBStorage(command_config.ssdb_file)  # storage.py
    else:
        raise NotImplementedError(f'Database engine {database_engine} not implemented')

    # Setup jobs file API
    jobs_storage = YamlJobsStorage(command_config.jobs_files)  # storage.py

    # Setup 'webchanges'
    urlwatcher = Urlwatch(command_config, config_storage, ssdb_storage, jobs_storage)  # main.py
    urlwatch_command = UrlwatchCommand(urlwatcher)  # command.py

    # Run 'webchanges', starting with processing command line arguments
    urlwatch_command.run()

    # Remove Playwright debug mode if there
    teardown_logger(command_config.verbose)


if __name__ == '__main__':
    main()
