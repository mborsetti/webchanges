"""tests filters based on a set of patterns"""

import logging
import os
import sys

import pytest

from webchanges.handler import JobState
from webchanges.jobs import BrowserJob, JobBase
from webchanges.storage import CacheDirStorage

logger = logging.getLogger(__name__)

here = os.path.dirname(__file__)

TESTDATA = [
    ({'url': 'https://www.google.com/',
      'timeout': 15,
      'method': 'GET',
      'ssl_no_verify': False,
      'ignore_cached': True,
      'no_redirects': True,
      'encoding': 'ascii',  # required for testing Python 3.6 in Windows as it has a tendency of erroring on cp1252
      'ignore_connection_errors': False,
      'ignore_http_error_codes': 200,
      'ignore_timeout_errors': False,
      'ignore_too_many_redirects': False,
      },
     'Google'),
    ({'url': 'https://www.google.com/',
      'use_browser': True,
      'timeout': 15,
      'ignore_https_errors': False,
      'switches': ['--window-size=1298,1406'],
      'wait_until': 'load',
      'wait_for': 1,
      'wait_for_navigation': 'https://www.google.com/'
      },
     'Google'),
    ({'command': 'echo test',
      },
     'test'),
]

cache_storage = CacheDirStorage(os.path.join(here, 'data'))


@pytest.mark.parametrize('input_job, output', TESTDATA)
def test_job(input_job, output):
    job = JobBase.unserialize(input_job)
    if not os.getenv('GITHUB_ACTIONS') or not isinstance(job, BrowserJob) or sys.version_info >= (3, 7):
        # legacy code for Pyppeteer does not pass testing in GitHub Actions as it fails with error
        # pyppeteer.errors.BrowserError: Browser closed unexpectedly
        job_state = JobState(cache_storage, job)
        job.main_thread_enter()
        assert output in job.retrieve(job_state)
        job.main_thread_exit()
