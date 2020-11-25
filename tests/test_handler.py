import contextlib
import os
import sys
import tempfile
import warnings

import pytest

from webchanges.config import BaseConfig
from webchanges.jobs import JobBase, ShellJob, UrlJob
from webchanges.main import Urlwatch
from webchanges.storage import CacheMiniDBStorage, DEFAULT_CONFIG, JobsYaml, YamlConfigStorage
from webchanges.util import import_module_from_source

pkgname = 'webchanges'
root = os.path.join(os.path.dirname(__file__), '../webchanges', '..')
here = os.path.dirname(__file__)


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
    JobsYaml(name).save(jobs)
    jobs2 = JobsYaml(name).load()
    os.chmod(name, 0o777)
    jobs3 = JobsYaml(name).load_secure()
    os.close(fd)
    os.remove(name)

    assert len(jobs2) == len(jobs)
    # Assert that the shell jobs have been removed due to secure loading
    # TODO why not working in Windows?
    if os.name != 'nt':
        assert len(jobs3) == 1


def test_load_config_yaml():
    config_file = os.path.join(here, 'data', 'config.yaml')
    if os.path.exists(config_file):
        config = YamlConfigStorage(config_file)
        assert config is not None
        assert config.config is not None
        assert config.config == DEFAULT_CONFIG
    else:
        print(f'{config_file} not found')


def test_load_jobs_yaml():
    jobs_yaml = os.path.join(here, 'data', 'jobs.yaml')
    if os.path.exists(jobs_yaml):
        assert len(JobsYaml(jobs_yaml).load_secure()) > 0
    else:
        warnings.warn(f'{jobs_yaml} not found', UserWarning)


def test_load_hooks_py():
    hooks_py = os.path.join(here, 'data', 'hooks.py')
    if os.path.exists(hooks_py):
        import_module_from_source('hooks', hooks_py)
    else:
        warnings.warn(f'{hooks_py} not found', UserWarning)


class ConfigForTest(BaseConfig):
    def __init__(self, config, urls, cache, hooks, verbose):
        (_, _) = os.path.split(os.path.dirname(os.path.abspath(sys.argv[0])))
        super().__init__(pkgname, os.path.dirname(__file__), config, urls, cache, hooks, verbose)
        self.edit = False
        self.edit_hooks = False


@contextlib.contextmanager
def teardown_func():
    try:
        yield
    finally:
        "tear down test fixtures"
        cache = os.path.join(here, 'data', 'cache.db')
        if os.path.exists(cache):
            os.remove(cache)
        if os.path.exists(cache + '.bak'):
            os.remove(cache + '.bak')


def test_run_watcher():
    with teardown_func():
        urls = os.path.join(root, 'share', 'examples', 'jobs-example.yaml')
        config = os.path.join(here, 'data', 'config.yaml')
        cache = os.path.join(here, 'data', 'cache.db')
        hooks = ''

        config_storage = YamlConfigStorage(config)
        jobs_storage = JobsYaml(urls)
        cache_storage = CacheMiniDBStorage(cache)
        try:
            urlwatch_config = ConfigForTest(config, urls, cache, hooks, True)

            urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)
            urlwatcher.run_jobs()
        finally:
            cache_storage.close()


def test_unserialize_shell_job_without_kind():
    job = JobBase.unserialize({
        'name': 'hoho',
        'command': 'ls',
    })
    assert isinstance(job, ShellJob)


def test_unserialize_with_unknown_key():
    with pytest.raises(ValueError):
        JobBase.unserialize({
            'unknown_key': 123,
            'name': 'hoho',
        })


def prepare_retry_test():
    urls = os.path.join(here, 'data', 'invalid-url.yaml')
    config = os.path.join(here, 'data', 'config.yaml')
    cache = os.path.join(here, 'data', 'cache.db')
    hooks = ''

    config_storage = YamlConfigStorage(config)
    cache_storage = CacheMiniDBStorage(cache)
    jobs_storage = JobsYaml(urls)

    urlwatch_config = ConfigForTest(config, urls, cache, hooks, True)
    urlwatcher = Urlwatch(urlwatch_config, config_storage, cache_storage, jobs_storage)

    return urlwatcher, cache_storage


def test_number_of_tries_in_cache_is_increased():
    with teardown_func():
        urlwatcher, cache_storage = prepare_retry_test()
        try:
            job = urlwatcher.jobs[0]
            old_data, timestamp, tries, etag = cache_storage.load(job, job.get_guid())
            assert tries == 0

            urlwatcher.run_jobs()
            urlwatcher.run_jobs()

            job = urlwatcher.jobs[0]
            old_data, timestamp, tries, etag = cache_storage.load(job, job.get_guid())

            assert tries == 2
            assert urlwatcher.report.job_states[-1].verb == 'error'
        finally:
            cache_storage.close()


def test_report_error_when_out_of_tries():
    with teardown_func():
        urlwatcher, cache_storage = prepare_retry_test()
        try:
            job = urlwatcher.jobs[0]
            old_data, timestamp, tries, etag = cache_storage.load(job, job.get_guid())
            assert tries == 0

            urlwatcher.run_jobs()
            urlwatcher.run_jobs()

            report = urlwatcher.report
            assert report.job_states[-1].verb == 'error'
        finally:
            cache_storage.close()


def test_reset_tries_to_zero_when_successful():
    with teardown_func():
        urlwatcher, cache_storage = prepare_retry_test()
        try:
            job = urlwatcher.jobs[0]
            old_data, timestamp, tries, etag = cache_storage.load(job, job.get_guid())
            assert tries == 0

            urlwatcher.run_jobs()

            job = urlwatcher.jobs[0]
            old_data, timestamp, tries, etag = cache_storage.load(job, job.get_guid())
            assert tries == 1

            # use an url that definitely exists
            job = urlwatcher.jobs[0]
            job.url = 'file://' + os.path.join(here, 'data', 'jobs.yaml')

            urlwatcher.run_jobs()

            job = urlwatcher.jobs[0]
            old_data, timestamp, tries, etag = cache_storage.load(job, job.get_guid())
            assert tries == 0
        finally:
            cache_storage.close()
