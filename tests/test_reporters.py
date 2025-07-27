"""Test reporting, primarily handling of diffs."""

from __future__ import annotations

import importlib.util
import os
import sys
import traceback
from smtplib import SMTPAuthenticationError

import pytest

try:
    from httpx import UnsupportedProtocol
except ImportError:
    from requests.exceptions import MissingSchema as UnsupportedProtocol  # type: ignore[assignment]

from webchanges.handler import JobState, Report
from webchanges.jobs import JobBase
from webchanges.mailer import smtp_have_password, smtp_set_password, SMTPMailer
from webchanges.storage import DEFAULT_CONFIG

try:
    from keyring.errors import NoKeyringError
except ImportError:
    NoKeyringError = None  # type: ignore[misc,assignment]

try:
    from matrix_client.errors import MatrixError
except ImportError:
    MatrixError = Exception


matrix_client_is_installed = importlib.util.find_spec('matrix_client') is not None
aioxmpp_is_installed = importlib.util.find_spec('aioxmpp') is not None
pushbullet_testing_broken = sys.version_info >= (3, 13)


ALL_REPORTERS = [
    reporter for reporter in DEFAULT_CONFIG['report'] if reporter not in {'tz', 'html', 'text', 'markdown'}
]


class UrlwatchTest:
    """A mock Urlwatch class for testing."""

    class config_storage:
        """A mock config_storage class for testing."""

        config = DEFAULT_CONFIG


def build_test_report() -> Report:
    """Builds a report with mock data for testing.

    :return: The test report.
    """

    def build_job(name: str, url: str, old: str, new: str) -> JobState:
        """Builds a job state with mock data for testing.

        :param name: The name of the job.
        :param url: The URL of the job.
        :param old: The old data of the job.
        :param new: The new data of the job.
        :return: The job state.
        """
        job = JobBase.unserialize({'name': name, 'url': url})

        # Can pass in None for ssdb_storage as we are not going to load or save the job state for testing; also no
        # need to use it as context manager, since no processing is called on the job
        job_state = JobState(None, job)  # type: ignore[arg-type]

        job_state.old_data = old
        job_state.old_timestamp = 1605147837.511478  # initial release of webchanges!
        job_state.new_data = new
        job_state.new_timestamp = 1605147837.511478

        return job_state

    def set_error(job_state: JobState, message: str) -> JobState:
        """Sets an error on the job state.

        :param job_state: The job state to set the error on.
        :param message: The error message.
        :return: The job state with the error set.
        """
        try:
            raise ValueError(message)
        except ValueError as e:
            job_state.exception = e
            job_state.traceback = job_state.job.format_error(e, traceback.format_exc())

        return job_state

    test_report = Report(UrlwatchTest())  # type: ignore[arg-type]
    test_report.job_states = []
    test_report.new(build_job('Newly Added', 'https://example.com/new', '', ''))
    test_report.changed(
        build_job(
            'Something Changed',
            'https://example.com/changed',
            """
    Unchanged Line
    Previous Content
    Another Unchanged Line
    """,
            """
    Unchanged Line
    Updated Content
    Another Unchanged Line
    """,
        )
    )
    test_report.changed_no_report(build_job('Newly Added', 'https://example.com/changed_no_report', '', ''))
    test_report.unchanged(
        build_job('Same As Before', 'https://example.com/unchanged', 'Same Old, Same Old\n', 'Same Old, Same Old\n')
    )
    test_report.error(
        set_error(
            build_job(
                'Error Reporting',
                'https://example.com/error',
                '',
                '',
            ),
            'Sample error text',
        )
    )

    return test_report


def test_smtp_password() -> None:
    if NoKeyringError is not None:
        try:
            assert smtp_have_password('fdsfdsfdsafdsf', '') is False
        except NoKeyringError:
            pass
        with pytest.raises((OSError, ImportError, NoKeyringError)):
            smtp_set_password('', '')
    else:
        assert smtp_have_password('fdsfdsfdsafdsf', '') is False


@pytest.mark.parametrize('reporter', ALL_REPORTERS)  # type: ignore[misc]
def test_reporters(reporter: str, capsys: pytest.CaptureFixture) -> None:
    test_report = build_test_report()
    match reporter:
        case 'email':
            if NoKeyringError is not None:
                with pytest.raises((ValueError, NoKeyringError)) as pytest_wrapped_e:
                    test_report.finish_one(reporter, check_enabled=False)
            else:
                with pytest.raises(ValueError) as pytest_wrapped_e:
                    test_report.finish_one(reporter, check_enabled=False)
            assert sum(
                list(
                    x in str(pytest_wrapped_e.value)
                    for x in {
                        'No password available in keyring for localhost ',
                        'No password available for localhost ',
                        'No recommended backend was available.',
                    }
                )
            )
        case 'xmpp':
            if not aioxmpp_is_installed:
                pytest.skip(f"Skipping {reporter} since 'aioxmpp' package is not installed")
            else:
                if NoKeyringError is not None:
                    with pytest.raises((ValueError, NoKeyringError)) as pytest_wrapped_e:
                        test_report.finish_one(reporter, check_enabled=False)
                    assert sum(
                        list(
                            x in str(pytest_wrapped_e.value)
                            for x in {
                                'No password available in keyring for ',
                                'No recommended backend was available.',
                            }
                        )
                    )
        case 'ifttt' | 'mailgun' | 'prowl' | 'pushover' | 'telegram':
            with pytest.raises(RuntimeError) as pytest_wrapped_e:
                test_report.finish_one(reporter, check_enabled=False)
            assert reporter in str(pytest_wrapped_e.value).lower()
        case 'pushbullet':
            if not pushbullet_testing_broken:
                with pytest.raises(RuntimeError) as pytest_wrapped_e:
                    test_report.finish_one(reporter, check_enabled=False)
                assert reporter in str(pytest_wrapped_e.value).lower()
        case 'matrix':
            if not matrix_client_is_installed:
                pytest.skip(f"Skipping {reporter} since 'matrix' package is not installed")
            with pytest.raises(MatrixError) as pytest_wrapped_e:
                test_report.finish_one(reporter, check_enabled=False)
            assert str(pytest_wrapped_e.value) == 'No scheme in homeserver url '
        case 'discord' | 'gotify' | 'webhook':
            with pytest.raises(UnsupportedProtocol) as pytest_wrapped_e:
                test_report.finish_one(reporter, check_enabled=False)
            err_msg = str(pytest_wrapped_e.value)
            assert (
                err_msg == "Request URL is missing an 'http://' or 'https://' protocol."
                or err_msg == "Invalid URL '': No scheme supplied. Perhaps you meant https://?"
            )
        case 'run_command':
            if os.getenv('GITHUB_ACTIONS'):
                pytest.skip('Test triggers exit code 141 in GitHub Actions')
            with pytest.raises(ValueError) as pytest_wrapped_e:
                test_report.finish_one(reporter, check_enabled=False)
            assert str(pytest_wrapped_e.value) == 'Reporter "run_command" needs a command'
            if sys.platform == 'win32':
                test_report.config['report']['run_command']['command'] = 'cmd /C echo TEST'
            else:
                test_report.config['report']['run_command']['command'] = 'echo TEST'
            test_report.finish_one(reporter, check_enabled=False)
            assert capsys.readouterr().out == 'TEST\n'
        case _:
            if reporter != 'browser':
                test_report.config['footnote'] = 'Footnote'
                test_report.finish_one(reporter, check_enabled=False)
            elif 'PYCHARM_HOSTED' in os.environ:  # browser
                test_report.config['report']['html']['separate'] = True
                test_report.config['footnote'] = 'Footnote'
                test_report.finish_one(reporter, check_enabled=False)


def test_mailer_send() -> None:
    mailer = SMTPMailer(  # noqa: S106 Possible hardcoded password: 'password'.
        smtp_user='test@gmail.com',
        smtp_server='smtp.gmail.com',
        smtp_port=587,
        tls=True,
        auth=True,
        insecure_password='password',
    )
    with pytest.raises(SMTPAuthenticationError) as pytest_wrapped_e:
        mailer.send(msg=None)
    assert pytest_wrapped_e.value.smtp_code == 535
