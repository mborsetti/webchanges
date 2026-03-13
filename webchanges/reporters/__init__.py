"""Reporters."""

# The code below is subject to the license contained in the LICENSE file, with the exception of the
# the SOURCE CODE REDISTRIBUTION NOTICE since this code does not include any redistributed code.

from __future__ import annotations

from webchanges.reporters._base import HtmlReporter, MarkdownReporter, ReporterBase, TextReporter
from webchanges.reporters._browser import BrowserReporter
from webchanges.reporters._chat import (
    XMPP,
    GitHubIssueReporter,
    GotifyReporter,
    MatrixReporter,
    TelegramReporter,
    XMPPReporter,
    xmpp_have_password,
    xmpp_set_password,
)
from webchanges.reporters._email import EMailReporter, MailgunReporter
from webchanges.reporters._filter import BetweenLinesFilter, get_lines_between
from webchanges.reporters._stdout import StdoutReporter
from webchanges.reporters._system import RunCommandReporter
from webchanges.reporters._web import (
    DiscordReporter,
    IFTTTReport,
    NtfyReporter,
    ProwlReporter,
    PushbulletReport,
    PushoverReport,
    ShellReporter,
    SlackReporter,
    WebhookReporter,
    WebServiceReporter,
)

__all__ = [
    'XMPP',
    'BetweenLinesFilter',
    'BrowserReporter',
    'DiscordReporter',
    'EMailReporter',
    'GitHubIssueReporter',
    'GotifyReporter',
    'HtmlReporter',
    'IFTTTReport',
    'MailgunReporter',
    'MarkdownReporter',
    'MatrixReporter',
    'NtfyReporter',
    'ProwlReporter',
    'PushbulletReport',
    'PushoverReport',
    'ReporterBase',
    'RunCommandReporter',
    'ShellReporter',
    'SlackReporter',
    'StdoutReporter',
    'TelegramReporter',
    'TextReporter',
    'WebServiceReporter',
    'WebhookReporter',
    'XMPPReporter',
    'get_lines_between',
    'xmpp_have_password',
    'xmpp_set_password',
]
