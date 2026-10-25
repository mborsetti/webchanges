"""Test reporting, primarily handling of diffs."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import smtplib
import socket
import sys
import traceback
from smtplib import SMTPAuthenticationError
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

try:
    from httpx import UnsupportedProtocol
except ImportError:
    from requests.exceptions import MissingSchema as UnsupportedProtocol

from webchanges import mailer as mailer_module
from webchanges.handler import JobState, Report
from webchanges.jobs import JobBase
from webchanges.mailer import SMTP_TIMEOUT, SMTPMailer, smtp_have_password, smtp_set_password
from webchanges.reporters import TelegramReporter
from webchanges.storage import DEFAULT_CONFIG

if TYPE_CHECKING:
    from typing import Self

    from webchanges.storage import _ConfigReportStdout

try:
    from keyring.errors import NoKeyringError
except ImportError:
    NoKeyringError = None

try:
    from matrix_client.errors import MatrixError
except ImportError:
    MatrixError = Exception


matrix_client_is_installed = importlib.util.find_spec('matrix_client') is not None
aioxmpp_is_installed = importlib.util.find_spec('aioxmpp') is not None
# pushbullet.py not maintained, breaks at Python 3.12 or 3.13. See https://pypi.org/project/pushbullet.py/
pushbullet_broken = sys.version_info >= (3, 13) or sys.platform == 'win32'


ALL_REPORTERS = [
    reporter for reporter in DEFAULT_CONFIG['report'] if reporter not in {'tz', 'html', 'text', 'markdown'}
]


class UrlwatchTest:
    """A mock Urlwatch class for testing.

    Each instance carries its own deep copy of the default configuration, so that a test mutating a report's config
    can corrupt neither the shared DEFAULT_CONFIG nor the other tests.
    """

    def __init__(self) -> None:
        self.config_storage = SimpleNamespace(config=copy.deepcopy(DEFAULT_CONFIG))


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
        job_state = JobState(None, job)  # ty:ignore[invalid-argument-type]

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

    test_report = Report(UrlwatchTest())  # ty:ignore[invalid-argument-type]
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


@pytest.mark.filterwarnings('ignore::getpass.GetPassWarning')  # headless runs cannot control terminal echo
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


@pytest.mark.parametrize('reporter', ALL_REPORTERS)
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
                [
                    x in str(pytest_wrapped_e.value)
                    for x in (
                        'No password available in keyring for localhost ',
                        'No password available for localhost ',
                        'No recommended backend was available.',
                    )
                ]
            )
        case 'xmpp':
            if not aioxmpp_is_installed:
                pytest.skip("'aioxmpp' not installed")
            elif NoKeyringError is not None:
                with pytest.raises((ValueError, NoKeyringError)) as pytest_wrapped_e:
                    test_report.finish_one(reporter, check_enabled=False)
                assert sum(
                    [
                        x in str(pytest_wrapped_e.value)
                        for x in (
                            'No password available in keyring for ',
                            'No recommended backend was available.',
                        )
                    ]
                )
        case 'ifttt' | 'mailgun' | 'prowl' | 'pushover' | 'telegram':
            with pytest.raises(RuntimeError) as pytest_wrapped_e:
                test_report.finish_one(reporter, check_enabled=False)
            assert reporter in str(pytest_wrapped_e.value).lower()
        case 'pushbullet':
            if not pushbullet_broken:
                with pytest.raises(RuntimeError) as pytest_wrapped_e:
                    test_report.finish_one(reporter, check_enabled=False)
                assert reporter in str(pytest_wrapped_e.value).lower()
        case 'matrix':
            if not matrix_client_is_installed:
                pytest.skip("'matrix' not installed")
            with pytest.raises(MatrixError) as pytest_wrapped_e:
                test_report.finish_one(reporter, check_enabled=False)
            assert str(pytest_wrapped_e.value) == 'No scheme in homeserver url '
        case 'discord' | 'gotify' | 'ntfy' | 'webhook':
            with pytest.raises(UnsupportedProtocol) as pytest_wrapped_e:
                test_report.finish_one(reporter, check_enabled=False)
            err_msg = str(pytest_wrapped_e.value)
            assert (
                err_msg == "Request URL is missing an 'http://' or 'https://' protocol."
                or err_msg == "Invalid URL '': No scheme supplied. Perhaps you meant https://?"
            )
        case 'run_command':
            # if os.getenv('GITHUB_ACTIONS'):
            #     pytest.skip('GitHub Actions Test triggers exit code 141 in ')
            with pytest.raises(ValueError) as pytest_wrapped_e:
                test_report.finish_one(reporter, check_enabled=False)
            assert str(pytest_wrapped_e.value) == 'Reporter "run_command" needs a command'
            if sys.platform == 'win32':
                test_report.config['report']['run_command']['command'] = 'cmd /C echo TEST'  # ty:ignore[invalid-assignment]
            else:
                test_report.config['report']['run_command']['command'] = 'echo TEST'
            test_report.finish_one(reporter, check_enabled=False)
            assert capsys.readouterr().out == 'TEST\n'
        case 'github_issue':
            pytest.skip('We cannot create GitHub issues')
        case _:
            if reporter != 'browser':
                test_report.config['footnote'] = 'Footnote'
                test_report.finish_one(reporter, check_enabled=False)
            elif sys.breakpointhook.__module__ != 'sys':  # debug, browser
                test_report.config['report']['html']['separate'] = True
                test_report.config['footnote'] = 'Footnote'
                test_report.finish_one(reporter, check_enabled=False)


def build_tagged_report() -> Report:
    """Builds a report of three changed jobs tagged 'personal', ['team', 'ops'] and nothing at all.

    :return: The test report.
    """

    def build_job_state(name: str, tags: str | list[str] | None) -> JobState:
        job = JobBase.unserialize({'name': name, 'url': f'https://example.com/{name}', 'tags': tags})
        job_state = JobState(None, job)  # ty:ignore[invalid-argument-type]
        job_state.old_data = 'old\n'
        job_state.old_timestamp = 1605147837.511478
        job_state.new_data = 'new\n'
        job_state.new_timestamp = 1605147837.511478
        return job_state

    test_report = Report(UrlwatchTest())  # ty:ignore[invalid-argument-type]
    test_report.job_states = []
    test_report.changed(build_job_state('personal', 'personal'))
    test_report.changed(build_job_state('team', ['team', 'ops']))
    test_report.changed(build_job_state('untagged', None))
    return test_report


def stdout_config(**directives: object) -> _ConfigReportStdout:
    """Returns a configuration of the (enabled, uncolored) stdout reporter with the directives given."""
    defaults = cast('dict[str, Any]', copy.deepcopy(DEFAULT_CONFIG['report']['stdout']))
    return {**defaults, 'enabled': True, 'color': False, **directives}


def test_reporter_configured_multiple_times(capsys: pytest.CaptureFixture[str]) -> None:
    """A reporter configured with a list of configurations runs once per configuration, each on its own tags."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = [
        stdout_config(tags=['personal']),
        stdout_config(tags='team'),  # a single tag needs no list
    ]
    test_report.finish(jobs_file=[])

    out = capsys.readouterr().out
    assert out.count('CHANGED: personal') == 2  # once in the summary and once in the details
    assert out.count('CHANGED: team') == 2
    assert 'CHANGED: untagged' not in out
    assert test_report.reporters_enabled is True
    assert [(state.job.pretty_name(), state.reported_count) for state in test_report.job_states] == [
        ('personal', 1),
        ('team', 1),
        ('untagged', 0),
    ]


def test_reporter_without_tags_reports_on_every_job(capsys: pytest.CaptureFixture[str]) -> None:
    """A reporter with no 'tags' directive reports on every job, tagged or not, and its footer is unchanged."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = stdout_config()
    test_report.finish(jobs_file=[])

    out = capsys.readouterr().out
    assert out.count('CHANGED: personal') == 2
    assert out.count('CHANGED: untagged') == 2
    assert 'Checked 3 sources in ' in out
    assert 'this report covers' not in out
    assert all(state.reported_count == 1 for state in test_report.job_states)


def test_reporter_tags_add_coverage_to_footer(capsys: pytest.CaptureFixture[str]) -> None:
    """A reporter restricted by tags states in its footer how many of the jobs run it covers."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = stdout_config(tags=['personal', 'team'])
    test_report.finish(jobs_file=[])

    out = capsys.readouterr().out
    assert 'Checked 3 sources in ' in out
    assert '; this report covers 2.' in out


def test_reporter_tags_matching_no_job(capsys: pytest.CaptureFixture[str]) -> None:
    """A reporter whose tags match no job reports nothing, but still counts as enabled."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = stdout_config(tags=['nonexistent'])
    test_report.finish(jobs_file=[])

    assert capsys.readouterr().out == ''
    assert test_report.reporters_enabled is True
    assert all(state.reported_count == 0 for state in test_report.job_states)


def test_no_reporters_enabled(caplog: pytest.LogCaptureFixture) -> None:
    """With every reporter disabled, submit_all warns and reports that none was enabled."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = stdout_config(enabled=False)
    test_report.finish(jobs_file=[])

    assert test_report.reporters_enabled is False
    assert 'No reporters enabled.' in caplog.text


def test_disabled_reporter_in_list_is_skipped(capsys: pytest.CaptureFixture[str]) -> None:
    """Only the enabled configurations of a reporter configured multiple times are run."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = [
        stdout_config(enabled=False, tags=['personal']),
        stdout_config(tags=['team']),
    ]
    test_report.finish(jobs_file=[])

    out = capsys.readouterr().out
    assert 'CHANGED: personal' not in out
    assert out.count('CHANGED: team') == 2


def test_finish_one_of_reporter_configured_multiple_times(capsys: pytest.CaptureFixture[str]) -> None:
    """finish_one runs every configuration of the named reporter."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = [stdout_config(tags=['personal']), stdout_config(tags=['team'])]
    test_report.finish_one('stdout')

    out = capsys.readouterr().out
    assert out.count('CHANGED: personal') == 2
    assert out.count('CHANGED: team') == 2


def test_finish_one_can_ignore_tags(capsys: pytest.CaptureFixture[str]) -> None:
    """apply_tags=False (used by --test-reporter and --errors) reports on every job regardless of the tags."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = stdout_config(tags=['nonexistent'])
    test_report.finish_one('stdout', apply_tags=False)

    out = capsys.readouterr().out
    assert out.count('CHANGED: personal') == 2
    assert out.count('CHANGED: untagged') == 2


def test_finish_one_of_disabled_reporter_raises() -> None:
    """finish_one of a reporter with no enabled configuration raises, as before."""
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = [stdout_config(enabled=False), stdout_config(enabled=False)]
    with pytest.raises(ValueError, match=r'^Reporter not enabled: stdout$'):
        test_report.finish_one('stdout')


@pytest.mark.parametrize(('color', 'intensity'), [(True, '9'), ('bright', '9'), ('normal', '3')])
def test_stdout_reporter_colors(
    color: bool | str, intensity: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stdout reporter emits ANSI escape sequences when stdout is a console that supports them."""
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    monkeypatch.setattr('webchanges.reporters._stdout._enable_windows_ansi', lambda: True)
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = stdout_config(color=color)
    test_report.finish_one('stdout')

    out = capsys.readouterr().out
    assert f'CHANGED: [{intensity}4mpersonal (' in out  # blue status line
    assert f'[{intensity}1m-old[0m' in out  # red deletion
    assert f'[{intensity}2m+new[0m' in out  # green addition


def test_stdout_reporter_no_colors_without_console_support(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stdout reporter emits no ANSI escape sequences when the console cannot process them (e.g. old Windows)."""
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    monkeypatch.setattr('webchanges.reporters._stdout._enable_windows_ansi', lambda: False)
    test_report = build_tagged_report()
    test_report.config['report']['stdout'] = stdout_config(color=True)
    test_report.finish_one('stdout')

    out = capsys.readouterr().out
    assert 'CHANGED: personal' in out
    assert '[' not in out


def test_html_markdown_to_html_extras() -> None:
    """Emphasis within words is off by default; the job's markdown_extras can reinstate it."""
    from webchanges.reporters import HtmlReporter

    assert HtmlReporter.markdown_to_html('snake_case_name\n_word_') == 'snake_case_name<br>\n<em>word</em>'
    assert HtmlReporter.markdown_to_html('snake_case_name', None, {'middle-word-em': True}) == 'snake<em>case</em>name'


def _smtp_handshake_transcript(host: str, port: int) -> str:
    """Return a transcript of a fresh EHLO exchange with an SMTP server, to explain an unexpected mailer failure."""
    transcript = io.StringIO()
    try:
        with contextlib.redirect_stderr(transcript), smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT) as server:
            server.set_debuglevel(1)
            code, reply = server.ehlo()
            transcript.write(
                f'\nlocal_hostname sent in EHLO: {server.local_hostname!r} (socket.getfqdn(): {socket.getfqdn()!r})\n'
                f'EHLO reply: {code} {reply!r}\nextensions: {sorted(server.esmtp_features)}\n'
            )
    except (OSError, smtplib.SMTPException) as e:
        transcript.write(f'\nhandshake failed: {type(e).__name__}: {e}\n')
    return transcript.getvalue()


def test_mailer_send() -> None:
    # Amazon SES answers each failed AUTH mechanism with 535 and keeps the connection open, so smtplib raises
    # SMTPAuthenticationError. Gmail (used until 3.38) now drops the connection after the first failed mechanism,
    # which smtplib surfaces as SMTPServerDisconnected.
    host, port = 'email-smtp.us-east-1.amazonaws.com', 587
    mailer = SMTPMailer(
        smtp_user='test@example.com',
        smtp_server=host,
        smtp_port=port,
        tls=True,
        auth=True,
        insecure_password='password',  # noqa: S106 possible hardcoded password
    )
    try:
        with pytest.raises(SMTPAuthenticationError) as pytest_wrapped_e:
            mailer.send(msg=None)
    except smtplib.SMTPException as e:
        # Any other SMTP error (e.g. 'STARTTLS extension not supported by server') usually means the server rejected
        # the EHLO greeting; include what it said so that the cause is visible in the CI log
        pytest.fail(f'{type(e).__name__}: {e}\n{_smtp_handshake_transcript(host, port)}')
    assert pytest_wrapped_e.value.smtp_code == 535


def _fake_smtp(calls: list[tuple]) -> type:
    """A stand-in for smtplib.SMTP that records the calls made to it, in order."""

    class FakeSMTP:
        def __init__(self, host: str, port: int, local_hostname: str | None, timeout: float) -> None:
            calls.append(('connect', host, port, local_hostname, timeout))  # the real one connects here

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def ehlo(self) -> None:
            calls.append(('ehlo',))

        def starttls(self) -> None:
            calls.append(('starttls',))

        def login(self, user: str, password: str) -> None:
            calls.append(('login', user))

    return FakeSMTP


def test_mailer_send_timeout_and_hostname_before_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SMTP connection has a timeout (an unresponsive server cannot block the run forever), and the local hostname
    sent in EHLO is looked up before connecting (a slow lookup after connecting can make the server time out).
    """
    calls: list[tuple] = []
    monkeypatch.setattr('webchanges.mailer.socket.getfqdn', lambda: calls.append(('getfqdn',)) or 'host.example.com')
    monkeypatch.setattr('webchanges.mailer.smtplib.SMTP', _fake_smtp(calls))
    SMTPMailer(
        smtp_user='test@example.com',
        smtp_server='smtp.example.com',
        smtp_port=587,
        tls=True,
        auth=True,
        insecure_password='password',  # noqa: S106 possible hardcoded password
    ).send(msg=None)
    assert calls == [
        ('getfqdn',),
        ('connect', 'smtp.example.com', 587, 'host.example.com', SMTP_TIMEOUT),
        ('ehlo',),
        ('starttls',),
        ('login', 'test@example.com'),
    ]


def test_ehlo_hostname_falls_back_to_address_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a fully qualified domain name, EHLO uses the IP address as a domain literal, as smtplib does."""
    monkeypatch.setattr('webchanges.mailer.socket.getfqdn', lambda: 'localhostname')
    monkeypatch.setattr('webchanges.mailer.socket.gethostbyname', lambda _name: '192.0.2.1')
    assert mailer_module._ehlo_hostname() == '[192.0.2.1]'


# ---------------------------------------------------------------- Telegram MarkdownV2 escaping and chunking

# Telegram rejects a message longer than 4096 characters or whose MarkdownV2 doesn't parse (e.g. an unescaped
# character or an unclosed code block), so a broken chunk means a report that is never delivered.


def _telegram_chunks(text: str, max_length: int) -> list[str]:
    reporter = TelegramReporter.__new__(TelegramReporter)  # the chunking needs neither a report nor a config
    return reporter.telegram_chunk_by_line(text, max_length)


def test_telegram_escaping() -> None:
    """Text is escaped, except for the inline code (only ` and \\ escaped), links and bolding."""
    assert _telegram_chunks('Go to [the site](https://ex.com/a_b) and run `x.y`! **New**', 4096) == [
        r'Go to [the site](https://ex.com/a_b) and run `x.y`\! *New*'
    ]


def test_telegram_code_block() -> None:
    """A code block keeps its fences (and language), and only ` and \\ are escaped inside it, as is a differ error's
    traceback."""
    text = 'Error:\n```python\nprint("a_b") # `x` \\ y\n```\nDone.'
    assert _telegram_chunks(text, 4096) == ['Error:\n```python\nprint("a_b") # \\`x\\` \\\\ y\n```\nDone\\.']


def test_telegram_code_block_across_chunks() -> None:
    """A code block too long for one chunk is closed at the end of each chunk and reopened with its opening fence at the
    start of the next one; no chunk is longer than the maximum or holds an empty code block."""
    code = [f'line {i:02} = a.b(c)\n' for i in range(30)]
    text = 'Start\n```diff\n' + ''.join(code) + '```\nEnd\n'
    chunks = _telegram_chunks(text, 80)
    assert len(chunks) > 2
    assert all(len(chunk) <= 80 for chunk in chunks)
    assert all(chunk.count('```') == 2 for chunk in chunks)
    assert all(chunk.startswith('```diff\n') for chunk in chunks[1:])
    assert '```diff\n```' not in ''.join(chunks)
    received = [line for chunk in chunks for line in chunk.splitlines(keepends=True) if not line.startswith('```')]
    assert received == ['Start\n', *code, 'End\n']


def test_telegram_long_line() -> None:
    """A line longer than a chunk is split across chunks without losing or adding anything, never between an escaping
    backslash and the character it escapes, and the next line is not merged into it."""
    text = 'a.b ' * 30 + '\nNext line.'
    chunks = _telegram_chunks(text, 25)
    assert all(len(chunk) <= 25 for chunk in chunks)
    assert ''.join(chunks) == 'a\\.b ' * 30 + '\nNext line\\.'
    assert not any(chunk.endswith('\\') for chunk in chunks)
    assert chunks[-1].endswith('\nNext line\\.')
