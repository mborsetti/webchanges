"""Chat/messaging reporters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

__lazy_modules__ = ['asyncio', 'getpass', 'json', 'markdown2', 're', 'warnings']

import asyncio
import getpass
import logging
import os
import re
import warnings
from typing import TYPE_CHECKING, Any

from markdown2 import Markdown

from webchanges.mailer import import_keyring
from webchanges.reporters._base import MarkdownReporter, TextReporter, chunk_string
from webchanges.util import SettingError, missing_dependency

if TYPE_CHECKING:
    from collections.abc import Iterable

    from webchanges.reporters._base import Response
    from webchanges.storage import (
        _ConfigReportGithubIssue,
        _ConfigReportGotify,
        _ConfigReportMatrix,
        _ConfigReportTelegram,
        _ConfigReportXmpp,
    )

import json

# Optional dependencies (keyring, matrix_client, slixmpp) are imported inside the functions that use them, so that only
# the runs that need them pay for importing them (see missing_dependency() in webchanges/util.py).

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
            raise SettingError('Telegram bot token not found')
        chat_ids = self.config['chat_id']
        chat_ids_list = [chat_ids] if not isinstance(chat_ids, list) else chat_ids

        text = '\n'.join(super().submit())  # no max_length here as we will chunk later

        if not text:
            logger.info('Reporter %s has nothing to report; execution aborted', self.__kind__)
            return

        chunks = self.telegram_chunk_by_line(text, max_length)

        for chat_id in chat_ids_list:
            for chunk in chunks:
                self.submit_to_telegram(bot_token, chat_id, chunk)

    def submit_to_telegram(self, bot_token: str, chat_id: int | str, text: str) -> Response:
        """Submit to Telegram."""
        logger.info("Sending telegram message to chat id: '%s'", chat_id)

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
                logger.info("Telegram response: ok '%s'. %s", json_res['ok'], json_res['result'])
            else:
                raise RuntimeError(f'Telegram error: {json_res["description"]}')
        except ValueError:
            logger.error(
                'Failed to parse telegram response. HTTP status code: %s, content: %s',
                result.status_code,
                result.content,
            )

        return result

    @staticmethod
    def telegram_escape_markdown(text: str, version: int = 2, entity_type: str | None = None) -> str:
        """Helper function to escape Telegram markup symbols.

        See https://core.telegram.org/bots/api#formatting-options

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

    def telegram_escape_line(self, line: str) -> str:
        """Escape a line outside a code block, escaping inline code and the URL of links as their entities require."""
        parts = re.split(r'(`)(.*?)(`)', line)
        for i in range(len(parts)):
            if i % 4 in {1, 3}:
                continue
            base_entity = 'code' if i % 4 == 2 else None
            subtext = re.split(r'(\[.*?]\((?:https?|tel|mailto):[^()]*\))', parts[i])
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
            parts[i] = ''.join(subtext)
        return ''.join(parts)

    @staticmethod
    def telegram_split_line(line: str, width: int) -> list[str]:
        """Split an escaped line into pieces of at most width characters.

        Preferably after a space and never between a backslash and the character it escapes. Joined, the pieces are the
        line.
        """
        pieces = []
        while len(line) > width:
            cut = line.rfind(' ', 1, width) + 1 or width
            while cut > 1 and (cut - len(line[:cut].rstrip('\\'))) % 2:  # odd number of trailing backslashes
                cut -= 1
            pieces.append(line[:cut])
            line = line[cut:]
        pieces.append(line)
        return pieces

    def telegram_chunk_by_line(self, text: str, max_length: int) -> list[str]:
        """Chunk-ify by line while escaping markdown as required by Telegram.

        No chunk is longer than max_length. A code block split across chunks is closed at the end of a chunk and
        reopened (with its opening fence) at the start of the next, and a line too long for a chunk is split.
        """
        # Escape each line as its context requires; a fence line (```) is kept as is, as is the code block's content
        # except for the characters a 'pre' entity requires to be escaped.
        escaped: list[tuple[str, bool, bool]] = []  # (line, is a fence, whether a code block is open after it)
        in_pre = False
        for line in text.splitlines(keepends=True):
            is_fence = line.lstrip().startswith('```') and bool(line.count('```') % 2)
            if is_fence:
                in_pre = not in_pre
                if not in_pre:  # a closing fence fits in the room kept to close a code block
                    line = '```\n' if line.endswith('\n') else '```'
            elif in_pre:
                line = self.telegram_escape_markdown(line, entity_type='pre')
            else:
                line = self.telegram_escape_line(line)
            escaped.append((line, is_fence, in_pre))

        # Room is kept in each chunk to close a code block ('\n```') and, in the next chunk, to reopen it
        reopen_length = max((len(line) for line, is_fence, _ in escaped if is_fence), default=0)
        width = max(max_length - 4 - reopen_length, 1)

        chunks: list[str] = []
        chunk: list[str] = []
        size = 0
        pre_open = False  # whether a code block is open at the end of the chunk
        opening_fence = ''
        for line, is_fence, pre_after in escaped:
            for piece in [line] if is_fence else self.telegram_split_line(line, width):
                if chunk and size + len(piece) + 4 * pre_after > max_length:
                    if pre_open and chunk[-1] is opening_fence:
                        chunk.pop()  # rather than leaving an empty code block, move its opening fence to the next chunk
                    elif pre_open:
                        chunk[-1] += '```' if chunk[-1].endswith('\n') else '\n```'
                    if chunk:
                        chunks.append(''.join(chunk))
                    chunk = [opening_fence] if pre_open else []
                    size = sum(len(c) for c in chunk)
                if is_fence and pre_after:
                    opening_fence = piece
                chunk.append(piece)
                size += len(piece)
                pre_open = pre_after
        if chunk or not chunks:
            chunks.append(''.join(chunk))

        return chunks


class MatrixReporter(MarkdownReporter):
    """Send a message to a room using the Matrix protocol."""

    __kind__ = 'matrix'

    config: _ConfigReportMatrix
    MAX_LENGTH = 16384

    def submit(self, max_length: int | None = None, **kwargs: Any) -> None:  # ty:ignore[invalid-method-override]
        try:
            import matrix_client.api
        except ImportError as e:  # pragma: no cover
            self.raise_import_error('matrix_client', self.__kind__, e, extra='matrix')

        homeserver_url = self.config['homeserver']
        access_token = self.config['access_token']
        room_id = self.config['room_id']

        body_markdown = '\n'.join(super().submit(self.MAX_LENGTH))

        if not body_markdown:
            logger.info('Reporter %s has nothing to report; execution aborted', self.__kind__)
            return

        client_api = matrix_client.api.MatrixHttpApi(homeserver_url, access_token)

        body_html = Markdown(
            extras={'fenced-code-blocks': None, 'highlightjs-lang': None, 'middle-word-em': False}
        ).convert(body_markdown)

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
    """Sends chat messages using the slixmpp library."""

    # Seconds to wait for a session: slixmpp retries a failed connection forever, so this bounds a run
    SESSION_TIMEOUT = 60

    def __init__(self, sender: str, recipient: str, insecure_password: str | None = None) -> None:
        # slixmpp warns on import when installed without its optional (Rust) JID extension, as on Windows
        logging.getLogger('slixmpp.stringprep').setLevel(logging.ERROR)
        try:
            import slixmpp  # noqa: F401 imported but unused (checks that it loads)
        except ImportError as e:  # pragma: no cover
            raise missing_dependency(e, 'slixmpp', used_by="the 'xmpp' reporter", extra='xmpp') from e
        self.sender = sender
        self.recipient = recipient
        self.insecure_password = insecure_password

    def _password(self) -> str:
        if self.insecure_password:
            return self.insecure_password
        keyring = import_keyring(used_by="the 'xmpp' reporter's password (as no 'insecure_password' is set)")
        password = keyring.get_password('urlwatch_xmpp', self.sender)
        if password is None:
            raise SettingError(f'No password available in keyring for {self.sender}')
        return password

    async def send(self, chunks: Iterable[str]) -> None:
        """Connects to the sender's server, sends each chunk as a chat message to the recipient, and disconnects.

        :param chunks: The messages to send.
        :raises RuntimeError: If authentication fails or no session is established within SESSION_TIMEOUT seconds.
        """
        import slixmpp  # availability already checked by __init__()

        client = slixmpp.ClientXMPP(self.sender, self._password())
        session: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        connection_errors: list[object] = []

        def session_started(_event: object) -> None:
            if not session.done():
                session.set_result(None)

        def authentication_failed(_event: object) -> None:
            if not session.done():
                session.set_exception(RuntimeError(f'XMPP authentication of {self.sender} failed'))

        client.add_event_handler('session_start', session_started)
        client.add_event_handler('failed_all_auth', authentication_failed)
        # a failed attempt is not final: slixmpp tries the next transport (direct TLS, STARTTLS), then reschedules
        client.add_event_handler('connection_failed', connection_errors.append)
        client.connect()
        try:
            try:
                await asyncio.wait_for(session, self.SESSION_TIMEOUT)
            except TimeoutError:
                reason = f' ({connection_errors[-1]})' if connection_errors else ''
                raise RuntimeError(
                    f'No XMPP session established for {self.sender} within {self.SESSION_TIMEOUT} seconds{reason}'
                ) from None
            recipient = slixmpp.JID(self.recipient)
            for chunk in chunks:
                client.send_message(mto=recipient, mbody=chunk, mtype='chat')
        finally:
            client.cancel_connection_attempt()
            await client.disconnect()  # sends what is queued first


def xmpp_have_password(sender: str) -> bool:
    keyring = import_keyring(used_by="the 'xmpp' reporter's password in the keyring")
    return keyring.get_password('urlwatch_xmpp', sender) is not None


def xmpp_set_password(sender: str) -> None:
    """Set the keyring password for the XMPP connection. Interactive."""
    keyring = import_keyring(used_by="storing the 'xmpp' reporter's password in the keyring")
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
            logger.info('Reporter %s has nothing to report; execution aborted', self.__kind__)
            return

        xmpp = XMPP(sender, recipient, self.config['insecure_password'])
        asyncio.run(xmpp.send(chunk_string(text, self.MAX_LENGTH, numbering=True)))


class GotifyReporter(MarkdownReporter):
    """Send a message to a gotify server (https://gotify.net/)."""

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
