"""Chat/messaging reporters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import asyncio
import getpass
import logging
import os
import re
import warnings
from typing import TYPE_CHECKING, Any, Iterable

from markdown2 import Markdown

from webchanges.reporters._base import MarkdownReporter, TextReporter, chunk_string

if TYPE_CHECKING:
    from webchanges.reporters._base import Response
    from webchanges.storage import (
        _ConfigReportGithubIssue,
        _ConfigReportGotify,
        _ConfigReportMatrix,
        _ConfigReportTelegram,
        _ConfigReportXmpp,
    )

import json

try:
    import aioxmpp  # ty:ignore[unresolved-import]
except ImportError as e:  # pragma: no cover
    aioxmpp = str(e)

try:
    import keyring
except ImportError as e:  # pragma: no cover
    keyring = str(e)  # ty:ignore[invalid-assignment]

try:
    import matrix_client.api
except ImportError as e:  # pragma: no cover
    matrix_client = str(e)  # ty:ignore[invalid-assignment]

logger = logging.getLogger(__name__)


class TelegramReporter(MarkdownReporter):
    """Send a Markdown message using Telegram."""

    # See https://core.telegram.org/bots/api#formatting-options

    __kind__ = 'telegram'

    config: _ConfigReportTelegram

    def submit(self, max_length: int = 4096, **kwargs: Any) -> None:  # ty:ignore[invalid-method-override]
        """Submit report."""
        bot_token = self.config['bot_token'] or os.environ.get('TELEGRAM_BOT_TOKEN')
        if bot_token is None:
            raise RuntimeError('Telegram bot token not found')
        chat_ids = self.config['chat_id']
        chat_ids_list = [chat_ids] if not isinstance(chat_ids, list) else chat_ids

        text = '\n'.join(super().submit())  # no max_length here as we will chunk later

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        chunks = self.telegram_chunk_by_line(text, max_length)

        for chat_id in chat_ids_list:
            for chunk in chunks:
                self.submit_to_telegram(bot_token, chat_id, chunk)

    def submit_to_telegram(self, bot_token: str, chat_id: int | str, text: str) -> Response:
        """Submit to Telegram."""
        logger.info(f"Sending telegram message to chat id: '{chat_id}'")

        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'MarkdownV2',
            'disable_web_page_preview': True,
            'disable_notification': self.config['silent'],
        }
        with self.http_client as http_client:
            result = http_client.post(f'https://api.telegram.org/bot{bot_token}/sendMessage', data=data, timeout=60)

        try:
            json_res = result.json()

            if result.status_code == 200:
                logger.info(f"Telegram response: ok '{json_res['ok']}'. {json_res['result']}")
            else:
                raise RuntimeError(f'Telegram error: {json_res["description"]}')
        except ValueError:
            logger.error(
                f'Failed to parse telegram response. HTTP status code: {result.status_code}, '
                f'content: {result.content!s}'
            )

        return result

    @staticmethod
    def telegram_escape_markdown(text: str, version: int = 2, entity_type: str | None = None) -> str:
        """Helper function to escape telegram markup symbols. See https://core.telegram.org/bots/api#formatting-options

        Inspired by https://github.com/python-telegram-bot/python-telegram-bot/blob/master/telegram/utils/helpers.py
        v13.5 30-Apr-21

        :param text: The text.
        :param version: Use to specify the version of telegrams Markdown. Either ``1`` or ``2``. Defaults to ``2``.
        :param entity_type: For the entity types ``pre``, ``code`` and the link part of ``text_links``, only certain
            characters need to be escaped in ``MarkdownV2``. See the official API documentation for details. Only valid
            in combination with ``version=2``, will be ignored otherwise.

        :returns: The escaped text.
        """
        if version == 1:
            escape_chars = r'_*`['
        elif version == 2:
            if entity_type is None:
                escape_chars = r'\_*[]()~`>#+-=|{}.!'
            elif entity_type in {'pre', 'code'}:
                escape_chars = r'\`'
            elif entity_type == 'text_link':
                escape_chars = r'\)[]'
            else:
                raise ValueError("entity_type must be None, 'pre', 'code' or 'text_link'!")
        else:
            raise ValueError('Markdown version must be either 1 or 2!')

        text = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
        lines = text.splitlines(keepends=True)
        for i in range(len(lines)):
            if lines[i].count('\\*\\*') and not lines[i].count('\\*\\*') % 2:
                lines[i] = lines[i].replace('\\*\\*', '*')  # rebuild bolding from html2text
            if lines[i].count('\\~\\~') and not lines[i].count('\\~\\~') % 2:
                lines[i] = lines[i].replace('\\~\\~', '~')  # rebuild strikethrough from html2text

        return ''.join(lines)

    def telegram_chunk_by_line(self, text: str, max_length: int) -> list[str]:
        """Chunk-ify by line while escaping markdown as required by Telegram."""
        chunks = []

        # Escape Markdown by type
        lines = re.split(r'(`)(.*?)(`)', text)
        for i in range(len(lines)):
            if i % 4 in {1, 3}:
                continue
            base_entity = 'code' if i % 4 == 2 else None
            # subtext = re.split(r'(\[[^\][]*]\((?:https?|tel|mailto):[^()]*\))', text[i])
            subtext = re.split(r'(\[.*?]\((?:https?|tel|mailto):[^()]*\))', lines[i])
            for j in range(len(subtext)):
                if (j + 1) % 2:
                    subtext[j] = self.telegram_escape_markdown(subtext[j], entity_type=base_entity)
                else:
                    subtext[j] = ''.join(
                        [
                            '[',
                            self.telegram_escape_markdown(subtext[j][1:].split(']')[0]),
                            '](',
                            self.telegram_escape_markdown(
                                subtext[j].split('(')[-1].split(')')[0], entity_type='text_link'
                            ),
                            ')',
                        ]
                    )
            lines[i] = ''.join(subtext)

        new_text = ''.join(lines).splitlines(keepends=True)

        # check if any individual line is too long and chunk it
        if any(len(line) > max_length for line in new_text):
            new_lines: list[str] = []
            for line in new_text:
                if len(line) > max_length:
                    new_lines.extend(chunk_string(line, max_length))
                else:
                    new_lines.append(line)
            new_text = new_lines

        it_lines = iter(new_text)
        chunk_lines: list[str] = []
        pre_status = False  # keep track of whether you're in the middle of a PreCode entity to close and reopen
        try:
            while True:
                next_line = next(it_lines)
                if sum(len(line) for line in chunk_lines) + len(next_line) > max_length - pre_status * 3:
                    if pre_status:
                        chunk_lines[-1] += '```'
                    chunks.append(''.join(chunk_lines))
                    chunk_lines = [pre_status * '```' + next_line]
                else:
                    chunk_lines.append(next_line)
                if next_line.count('```') % 2:
                    pre_status = not pre_status
        except StopIteration:
            chunks.append(''.join(chunk_lines))

        return chunks


class MatrixReporter(MarkdownReporter):
    """Send a message to a room using the Matrix protocol."""

    __kind__ = 'matrix'

    config: _ConfigReportMatrix
    MAX_LENGTH = 16384

    def submit(self, max_length: int | None = None, **kwargs: Any) -> None:  # ty:ignore[invalid-method-override]
        if isinstance(matrix_client, str):
            self.raise_import_error('matrix_client', self.__kind__, matrix_client)

        homeserver_url = self.config['homeserver']
        access_token = self.config['access_token']
        room_id = self.config['room_id']

        body_markdown = '\n'.join(super().submit(self.MAX_LENGTH))

        if not body_markdown:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        client_api = matrix_client.api.MatrixHttpApi(homeserver_url, access_token)

        body_html = Markdown(extras=['fenced-code-blocks', 'highlightjs-lang']).convert(body_markdown)

        try:
            client_api.send_message_event(
                room_id,
                'm.room.message',
                content={
                    'msgtype': 'm.text',
                    'format': 'org.matrix.custom.html',
                    'body': body_markdown,
                    'formatted_body': body_html,
                },
            )
        except matrix_client.api.MatrixError as e:
            raise RuntimeError(f'Matrix error: {e}')  # noqa: B904


class XMPP:
    # TODO: aioxmpp unmaintained, breaks at Python 3.13; move to https://pypi.org/project/slixmpp/
    def __init__(self, sender: str, recipient: str, insecure_password: str | None = None) -> None:
        if isinstance(aioxmpp, str):
            raise ImportError(
                f"Python package 'aioxmpp' cannot be imported; cannot use the 'xmpp' reporter.\n{aioxmpp}"
            )
        self.sender = sender
        self.recipient = recipient
        self.insecure_password = insecure_password

    async def send(self, chunk: str) -> None:
        if self.insecure_password:
            password = self.insecure_password
        elif keyring is not None:
            passw = keyring.get_password('urlwatch_xmpp', self.sender)
            if passw is None:
                raise ValueError(f'No password available in keyring for {self.sender}')
            password = passw
        else:
            raise ValueError(f'No password available for {self.sender}')

        jid = aioxmpp.JID.fromstr(self.sender)  # ty:ignore[unresolved-attribute]
        client = aioxmpp.PresenceManagedClient(jid, aioxmpp.make_security_layer(password))  # ty:ignore[unresolved-attribute]
        recipient_jid = aioxmpp.JID.fromstr(self.recipient)  # ty:ignore[unresolved-attribute]

        async with client.connected() as stream:
            msg = aioxmpp.Message(  # ty:ignore[unresolved-attribute]
                to=recipient_jid,
                type_=aioxmpp.MessageType.CHAT,  # ty:ignore[unresolved-attribute]
            )
            msg.body[None] = chunk

            await stream.send_and_wait_for_sent(msg)


def xmpp_have_password(sender: str) -> bool:
    if isinstance(keyring, str):
        raise ImportError(f'Python package "keyring" is non installed - service unsupported.\n{keyring}')

    return keyring.get_password('urlwatch_xmpp', sender) is not None


def xmpp_set_password(sender: str) -> None:
    """Set the keyring password for the XMPP connection. Interactive."""
    if isinstance(keyring, str):
        raise ImportError(f'Python package "keyring" is non installed - service unsupported.\n{keyring}')

    password = getpass.getpass(prompt=f'Enter password for {sender}: ')
    keyring.set_password('urlwatch_xmpp', sender, password)


class XMPPReporter(TextReporter):
    """Send a message using the XMPP Protocol."""

    __kind__ = 'xmpp'

    config: _ConfigReportXmpp
    MAX_LENGTH = 262144

    def submit(self) -> None:  # ty:ignore[invalid-method-override]
        sender = self.config['sender']
        recipient = self.config['recipient']

        text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        xmpp = XMPP(sender, recipient, self.config['insecure_password'])

        for chunk in chunk_string(text, self.MAX_LENGTH, numbering=True):
            asyncio.run(xmpp.send(chunk))


class GotifyReporter(MarkdownReporter):
    """Send a message to a gotify server (https://gotify.net/)"""

    MAX_LENGTH = 16 * 1024

    __kind__ = 'gotify'

    config: _ConfigReportGotify

    def submit(self, max_length: int | None = None, **kwargs: Any) -> None:  # ty:ignore[invalid-method-override]
        body_markdown = '\n'.join(super().submit(self.MAX_LENGTH))
        if not body_markdown:
            logger.debug('Not sending message to gotify server (no changes)')
            return

        server_url = self.config['server_url']
        url = f'{server_url}/message'

        token = self.config['token']
        headers = {'Authorization': f'Bearer {token}'}
        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        # 'subject' used in the config file, but the API uses what might be called the subject as the 'title'
        title = self.subject_with_args(filtered_job_states)
        data = {
            'extras': {
                'client::display': {
                    'contentType': 'text/markdown',
                },
            },
            'message': body_markdown,
            'priority': self.config['priority'],
            'title': title,
        }
        with self.http_client as http_client:
            http_client.post(url, headers=headers, json=data)


class GitHubIssueReporter(MarkdownReporter):
    """Reporter that submits reports as issues to a GitHub repository."""

    # Contributed by Dmitry Vasiliev (https://github.com/swimmwatch) in
    # https://github.com/mborsetti/webchanges/issues/105

    __kind__ = 'github_issue'

    config: _ConfigReportGithubIssue

    _API_URL = 'https://api.github.com/repos/{owner}/{repo}/issues'
    _CONTENT_LIMIT = 65536  # GitHub issue body limit

    def _format_title(self) -> str:
        """Format the title of the issue."""
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC)
        format_dt = self.config['format_dt'] or '%Y-%m-%d %H:%M:%S'

        title = self.config['title']
        if not title:
            title = 'Webchanges report'
        else:
            dt = now.strftime(format_dt)
            title = title.format(dt=dt)

        return title

    def _format_text(self, content: str) -> str:
        """Format the content of the issue."""
        format_content = self.config['format_content']
        content = content[: self._CONTENT_LIMIT]
        if format_content:
            placeholder = '{content}'
            max_content_length = self._CONTENT_LIMIT - (len(format_content) - len(placeholder))
            content = content[:max_content_length]
            content = format_content.format(content=content)

        return content

    def _create_issue(self, content: str) -> None:
        """Create an issue on GitHub."""
        from http import HTTPStatus

        url = self._API_URL.format(owner=self.config['owner'], repo=self.config['repo'])
        headers = {'Authorization': f'Bearer {self.config["token"]}', 'Accept': 'application/json'}

        title = self._format_title()
        content = self._format_text(content)
        issue_data = {'title': title, 'body': content, 'labels': self.config['labels']}

        assignees = self.config['assignees']
        if assignees:
            issue_data['assignees'] = assignees

        type_ = self.config['type']
        if type_:
            issue_data['type'] = type_

        milestone = self.config['milestone']
        if milestone:
            issue_data['milestone'] = milestone

        with self.http_client as http_client:
            response = http_client.post(url, headers=headers, json=issue_data)

        if response.status_code == HTTPStatus.CREATED:
            logger.info('Issue created successfully.')
        else:
            json_object = json.loads(response.text)
            json_formatted_str = json.dumps(json_object, indent=2)
            raise RuntimeError(f'Failed to create issue: {json_formatted_str}')

    def submit(
        self,
        max_length: int | None = None,
        **kwargs: Any,
    ) -> Iterable[str]:
        """Submit the report to GitHub as an issue."""
        warnings.warn(
            f'Reporter {self.__kind__} is ALPHA, is undocumented, may have bugs, and may change in the future. '
            'Please report any problems or suggestions in https://github.com/mborsetti/webchanges/issues/105.',
            RuntimeWarning,
            stacklevel=1,
        )

        lines = super().submit(max_length, **kwargs)
        content = '\n'.join(lines)
        if not content:
            logger.info('No content to submit.')
            return []

        logger.info('Submitting issue to GitHub...')
        self._create_issue(content)

        return lines
