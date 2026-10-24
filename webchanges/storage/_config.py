"""Configuration TypedDicts and DEFAULT_CONFIG."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import warnings
from typing import Any, Literal, Mapping, NotRequired, TypedDict

from webchanges import __project_name__

try:
    from typeguard import check_type  # ty:ignore[unresolved-import]
except ImportError:
    from webchanges._vendored.typeguard import check_type

# _ConfigDisplay uses functional syntax because 'empty-diff' is not a valid identifier
_ConfigDisplay = TypedDict(
    '_ConfigDisplay',
    {
        'new': bool,
        'error': bool,
        'unchanged': bool,
        'empty-diff': bool,
    },
)


class _ConfigReporter(TypedDict, total=False):
    """Directives accepted by every reporter, in addition to its own ones. Reporters inherit from this (the report
    formats -- text, html and markdown -- do not, as they are not reporters)."""

    # Restricts the reporter to the jobs having at least one of these tags in their own 'tags' directive.
    tags: str | list[str]


class _ConfigReportText(TypedDict):
    line_length: int
    details: bool
    footer: bool
    minimal: bool
    separate: bool


class _ConfigReportHtml(TypedDict):
    diff: Literal['unified', 'table']
    footer: bool
    separate: bool
    title: str


class _ConfigReportMarkdown(TypedDict):
    details: bool
    footer: bool
    minimal: bool
    separate: bool


class _ConfigReportStdout(_ConfigReporter):
    enabled: bool
    color: bool | Literal['normal', 'bright']


class _ConfigReportBrowser(_ConfigReporter):
    enabled: bool


class _ConfigReportDiscord(_ConfigReporter):
    enabled: bool
    webhook_url: str
    embed: bool
    subject: str
    colored: bool
    max_message_length: int | None


class _ConfigReportEmailSmtp(TypedDict):
    host: str
    user: str
    port: int
    starttls: bool
    auth: bool
    insecure_password: str
    utf_8: bool


class _ConfigReportEmailSendmail(TypedDict):
    path: str


# _ConfigReportEmail uses functional syntax because 'from' is not a valid identifier
_ConfigReportEmail = TypedDict(
    '_ConfigReportEmail',
    {
        'enabled': bool,
        'html': bool,
        'to': str,
        'from': str,
        'subject': str,
        'method': Literal['sendmail', 'smtp'],
        'smtp': _ConfigReportEmailSmtp,
        'sendmail': _ConfigReportEmailSendmail,
        # Same as _ConfigReporter.tags; repeated here as the functional syntax does not allow inheritance.
        'tags': NotRequired[str | list[str]],
    },
)


class _ConfigReportGithubIssue(_ConfigReporter):
    enabled: bool
    token: str
    owner: str
    repo: str
    title: str
    labels: list[str]
    format_dt: str
    format_content: str
    assignees: list[str]
    type: str
    milestone: str


class _ConfigReportGotify(_ConfigReporter):
    enabled: bool
    priority: int
    server_url: str
    title: str
    token: str


class _ConfigReportIfttt(_ConfigReporter):
    enabled: bool
    key: str
    event: str


class _ConfigReportMailgun(_ConfigReporter):
    enabled: bool
    region: str
    api_key: str
    domain: str
    from_mail: str
    from_name: str
    to: str
    subject: str


class _ConfigReportMatrix(_ConfigReporter):
    enabled: bool
    homeserver: str
    access_token: str
    room_id: str


class _ConfigReportNtfyPriorities(TypedDict):
    default: int | str
    new: int | str
    changed: int | str
    error: int | str


class _ConfigReportNtfy(_ConfigReporter):
    enabled: bool
    topic_url: str
    authorization: str | None
    priorities: _ConfigReportNtfyPriorities


class _ConfigReportProwl(_ConfigReporter):
    enabled: bool
    api_key: str
    priority: int
    application: str
    subject: str


class _ConfigReportPushbullet(_ConfigReporter):
    enabled: bool
    api_key: str


class _ConfigReportPushover(_ConfigReporter):
    enabled: bool
    app: str
    device: str | None
    sound: str
    user: str
    priority: str


class _ConfigReportRunCommand(_ConfigReporter):
    enabled: bool
    command: str


class _ConfigReportTelegram(_ConfigReporter):
    enabled: bool
    bot_token: str
    chat_id: str | int | list[str | int]
    silent: bool


class _ConfigReportWebhook(_ConfigReporter):
    enabled: bool
    markdown: bool
    webhook_url: str
    rich_text: bool
    max_message_length: int | None


class _ConfigReportXmpp(_ConfigReporter):
    enabled: bool
    sender: str
    recipient: str
    insecure_password: str | None


class _ConfigReport(TypedDict):
    # Every reporter (i.e. all but 'tz' and the report formats text, html and markdown) may be configured either once,
    # with a single configuration, or multiple times, with a list of configurations (see ReporterBase.submit_one).
    tz: str | None
    text: _ConfigReportText
    html: _ConfigReportHtml
    markdown: _ConfigReportMarkdown
    stdout: _ConfigReportStdout | list[_ConfigReportStdout]
    browser: _ConfigReportBrowser | list[_ConfigReportBrowser]
    discord: _ConfigReportDiscord | list[_ConfigReportDiscord]
    email: _ConfigReportEmail | list[_ConfigReportEmail]
    github_issue: _ConfigReportGithubIssue | list[_ConfigReportGithubIssue]
    gotify: _ConfigReportGotify | list[_ConfigReportGotify]
    ifttt: _ConfigReportIfttt | list[_ConfigReportIfttt]
    mailgun: _ConfigReportMailgun | list[_ConfigReportMailgun]
    matrix: _ConfigReportMatrix | list[_ConfigReportMatrix]
    ntfy: _ConfigReportNtfy | list[_ConfigReportNtfy]
    prowl: _ConfigReportProwl | list[_ConfigReportProwl]
    pushbullet: _ConfigReportPushbullet | list[_ConfigReportPushbullet]
    pushover: _ConfigReportPushover | list[_ConfigReportPushover]
    run_command: _ConfigReportRunCommand | list[_ConfigReportRunCommand]
    telegram: _ConfigReportTelegram | list[_ConfigReportTelegram]
    webhook: _ConfigReportWebhook | list[_ConfigReportWebhook]
    xmpp: _ConfigReportXmpp | list[_ConfigReportXmpp]


class _ConfigJobDefaults(TypedDict, total=False):
    _note: str
    all: dict[str, Any]
    url: dict[str, Any]
    browser: dict[str, Any]
    command: dict[str, Any]


class _ConfigDifferDefaults(TypedDict, total=False):
    _note: str
    unified: dict[str, Any]
    ai_google: dict[str, Any]
    command: dict[str, Any]
    deepdiff: dict[str, Any]
    image: dict[str, Any]
    table: dict[str, Any]
    wdiff: dict[str, Any]


class _ConfigDatabase(TypedDict):
    engine: Literal['sqlite3', 'redis', 'minidb', 'textfiles']
    max_snapshots: int


class _ConfigVersionCheck(TypedDict):
    enabled: bool


class _Config(TypedDict):
    display: _ConfigDisplay
    report: _ConfigReport
    job_defaults: _ConfigJobDefaults
    differ_defaults: _ConfigDifferDefaults
    database: _ConfigDatabase
    footnote: str | None
    version_check: _ConfigVersionCheck


def validate_config(config: Mapping[str, Any]) -> None:
    """Validate ``config`` against the ``_Config`` TypedDict structure; alert for deprecations.

    Defined in this module so that, with ``from __future__ import annotations`` in effect, typeguard resolves the
    nested TypedDict forward references (``_ConfigDisplay``, ``_ConfigReport``, …) against this module's globals where
    they are defined.
    """
    check_type(config, _Config)

    # Deprecations
    if config['display']['empty-diff'] is True:
        warnings.warn(
            "The configuration setting 'display > empty-diff' is deprecated; please set to false and use "
            "the 'additions_only' job directive instead.",
            DeprecationWarning,
            stacklevel=1,
        )


DEFAULT_CONFIG: _Config = {
    'display': {  # select whether the report include the categories below
        'new': True,
        'error': True,
        'unchanged': False,
        'empty-diff': False,
    },
    'report': {
        'tz': None,  # the timezone as a IANA time zone name, e.g. 'America/Los_Angeles', or null for machine's
        # the directives below are for the report content types (text, html or markdown)
        'text': {
            'details': True,  # whether the diff is sent
            'footer': True,
            'line_length': 75,
            'minimal': False,
            'separate': False,
        },
        'html': {
            'diff': 'unified',  # 'unified' or 'table'
            'footer': True,
            'separate': False,
            'title': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
        },
        'markdown': {
            'details': True,  # whether the diff is sent
            'footer': True,
            'minimal': False,
            'separate': False,
        },
        # the directives below control 'reporters', i.e. where a report is displayed and/or sent
        'stdout': {  # the console / command line display; uses text
            'enabled': True,
            'color': True,
        },
        'browser': {  # the system's default browser; uses html
            'enabled': False,
        },
        'discord': {
            'enabled': False,
            'webhook_url': '',
            'embed': True,
            'subject': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
            'colored': True,
            'max_message_length': None,
        },
        'email': {  # email (except mailgun); uses text or both html and text if 'html' is set to true
            'enabled': False,
            'html': True,
            'from': '',
            'to': '',
            'subject': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
            'method': 'smtp',  # either 'smtp' or 'sendmail'
            'smtp': {
                'host': 'localhost',
                'port': 587,
                'starttls': True,
                'auth': True,
                'user': '',
                'insecure_password': '',
                'utf_8': True,
            },
            'sendmail': {
                'path': 'sendmail',
            },
        },
        'github_issue': {
            'enabled': False,
            'token': '',
            'owner': '',
            'repo': '',
            'title': '',
            'labels': [],
            'format_dt': '',
            'format_content': '',
            'assignees': [],
            'type': '',
            'milestone': '',
        },
        'gotify': {  # uses markdown
            'enabled': False,
            'priority': 0,
            'server_url': '',
            'title': '',
            'token': '',
        },
        'ifttt': {  # uses text
            'enabled': False,
            'key': '',
            'event': '',
        },
        'mailgun': {  # uses text
            'enabled': False,
            'region': 'us',
            'api_key': '',
            'domain': '',
            'from_mail': '',
            'from_name': '',
            'to': '',
            'subject': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
        },
        'matrix': {  # uses text
            'enabled': False,
            'homeserver': '',
            'access_token': '',
            'room_id': '',
        },
        'ntfy': {  # uses text
            'enabled': False,
            'topic_url': '',
            'authorization': None,
            'priorities': {
                'default': 'default',
                'new': 'low',
                'changed': 'max',
                'error': 'high',
            },
        },
        'prowl': {  # uses text
            'enabled': False,
            'api_key': '',
            'priority': 0,
            'application': '',
            'subject': f'[{__project_name__}] {{count}} changes{{jobs_files}}: {{jobs}}',
        },
        'pushbullet': {  # uses text
            'enabled': False,
            'api_key': '',
        },
        'pushover': {  # uses text
            'enabled': False,
            'app': '',
            'user': '',
            'device': None,
            'sound': 'spacealarm',
            'priority': 'normal',
        },
        'run_command': {  # uses text
            'enabled': False,
            'command': '',
        },
        'telegram': {  # uses markdown (from version 3.7)
            'enabled': False,
            'bot_token': '',
            'chat_id': '',
            'silent': False,
        },
        'webhook': {
            'enabled': False,
            'webhook_url': '',
            'markdown': False,
            'rich_text': False,
            'max_message_length': None,
        },
        'xmpp': {  # uses text
            'enabled': False,
            'sender': '',
            'recipient': '',
            'insecure_password': '',
        },
    },
    'job_defaults': {
        '_note': 'Default directives that are applied to jobs.',
        'all': {'_note': 'These are used for all type of jobs, including those in hooks.py.'},
        'url': {'_note': "These are used for 'url' jobs without 'use_browser'."},
        'browser': {'_note': "These are used for 'url' jobs with 'use_browser: true'."},
        'command': {'_note': "These are used for 'command' jobs."},
    },
    'differ_defaults': {
        '_note': 'Default directives that are applied to individual differs.',
        'unified': {},
        'ai_google': {},
        'command': {},
        'deepdiff': {},
        'image': {},
        'table': {},
        'wdiff': {},
    },
    'database': {
        'engine': 'sqlite3',
        'max_snapshots': 4,
    },
    'footnote': None,
    'version_check': {
        'enabled': True,  # whether to check PyPi once a day for a newer release of webchanges
    },
}
