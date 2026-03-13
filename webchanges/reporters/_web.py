"""Web/HTTP-based reporters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from warnings import warn

from webchanges.reporters._base import Headers, MarkdownReporter, TextReporter, chunk_string, httpx

if TYPE_CHECKING:
    from webchanges.reporters._base import Response
    from webchanges.storage import (
        _ConfigReportDiscord,
        _ConfigReportIfttt,
        _ConfigReportNtfy,
        _ConfigReportProwl,
        _ConfigReportPushbullet,
        _ConfigReportPushover,
        _ConfigReportWebhook,
    )

try:
    import chump
except ImportError as e:  # pragma: no cover
    chump = str(e)  # ty:ignore[invalid-assignment]

logger = logging.getLogger(__name__)


class IFTTTReport(TextReporter):
    """Send summary via IFTTT."""

    __kind__ = 'ifttt'

    config: _ConfigReportIfttt

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        webhook_url = 'https://maker.ifttt.com/trigger/{event}/with/key/{key}'.format(**self.config)
        for job_state in self.report.get_filtered_job_states(self.job_states):
            pretty_name = job_state.job.pretty_name()
            location = job_state.job.get_location()
            print(f'submitting {job_state}')
            with self.http_client as http_client:
                result = http_client.post(
                    webhook_url,
                    json={
                        'value1': job_state.verb,
                        'value2': pretty_name,
                        'value3': location,
                    },
                    timeout=60,
                )
            if result.status_code != 200:
                raise RuntimeError(f'IFTTT error: {result.text}')


class WebServiceReporter(TextReporter):
    """Base class for other reporters, such as Pushover and Pushbullet."""

    __kind__ = 'webservice (no settings)'

    MAX_LENGTH = 1024

    def web_service_get(self) -> str | chump.User:
        raise NotImplementedError

    def web_service_submit(self, service: str | chump.User, title: str, body: str) -> None:
        raise NotImplementedError

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Not sending {self.__kind__} (no changes)')
            return

        if len(text) > self.MAX_LENGTH:
            text = text[: self.MAX_LENGTH]

        try:
            service = self.web_service_get()
        except Exception as e:
            raise RuntimeError(
                f'Failed to load or connect to {self.__kind__} - are the dependencies installed and configured?'
            ) from e

        self.web_service_submit(service, 'Website Change Detected', text)


class PushoverReport(WebServiceReporter):
    """Send summary via pushover.net."""

    __kind__ = 'pushover'

    config: _ConfigReportPushover

    def web_service_get(self) -> chump.User:
        if isinstance(chump, str):
            self.raise_import_error('chump', self.__kind__, chump)

        app = chump.Application(self.config['app'])
        return app.get_user(self.config['user'])

    def web_service_submit(self, service: chump.User, title: str, body: str) -> None:  # ty:ignore[invalid-method-override]
        sound = self.config['sound']
        # If device is the empty string or not specified at all, use None to send to all devices
        # (see https://github.com/thp/urlwatch/issues/372)
        device = self.config['device']
        priority = {
            'lowest': chump.LOWEST,
            'low': chump.LOW,
            'normal': chump.NORMAL,
            'high': chump.HIGH,
            'emergency': chump.EMERGENCY,
        }.get(self.config['priority'], chump.NORMAL)
        msg = service.create_message(
            message=body, html=True, title=title, device=device, priority=priority, sound=sound
        )
        msg.send()


class PushbulletReport(WebServiceReporter):
    """Send summary via pushbullet.com."""

    __kind__ = 'pushbullet'

    config: _ConfigReportPushbullet

    def web_service_get(self) -> Any:  # noqa: ANN401 Dynamically typed expressions Any are disallowed
        # def web_service_get(self) -> Pushbullet:
        # Moved here as loading breaks Pytest in Python 3.13 on Windows
        # Is stuck in collecting due to File Windows fatal exception: access violation
        try:
            from pushbullet import Pushbullet
        except ImportError as e:  # pragma: no cover
            Pushbullet = str(e)  # noqa: N806 variable should be lowercase  # ty:ignore[invalid-assignment]

        if isinstance(Pushbullet, str):
            self.raise_import_error('pushbullet', self.__kind__, Pushbullet)

        return Pushbullet(self.config['api_key'])

    def web_service_submit(self, service: Any, title: str, body: str) -> None:  # noqa: ANN401 Dynamically typed expressions Any are disallowed
        # def web_service_submit(self, service: Pushbullet, title: str, body: str) -> None:
        service.push_note(title, body)


class WebhookReporter(TextReporter):
    """Send a text message to a webhook such as Slack or Mattermost.  For Mattermost, set 'markdown' to true."""

    __kind__ = 'webhook'

    config: _ConfigReportWebhook

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        default_max_length = 40000
        if isinstance(self.config['max_message_length'], int):
            self.max_length = int(self.config['max_message_length'])
        else:
            self.max_length = default_max_length

    def submit(self) -> Response | None:  # type: ignore[override]
        webhook_url = self.config['webhook_url']

        if self.config['markdown']:
            markdown_reporter = MarkdownReporter(
                self.report, self.config, self.job_states, self.duration, self.jobs_files, self.differ_defaults
            )
            text = '\n'.join(markdown_reporter.submit())
        else:
            text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return None

        result = None
        for chunk in chunk_string(text, self.max_length, numbering=True):
            res = self.submit_to_webhook(webhook_url, chunk)
            if res.status_code != 200 or res is None:
                result = res

        return result

    def submit_to_webhook(self, webhook_url: str, text: str) -> Response:
        logger.debug(f'Sending request to webhook with text: {text}')
        post_data = self.prepare_post_data(text)
        with self.http_client as http_client:
            result = http_client.post(webhook_url, json=post_data, timeout=60)
        try:
            if result.status_code in {200, 204}:
                logger.info('Webhook server response: ok')
            else:
                raise RuntimeError(f'Webhook server error: {result.text}')
        except ValueError:
            logger.error(
                f'Failed to parse webhook server response. HTTP status code: {result.status_code}, '
                f'content: {result.content!s}'
            )
        return result

    def prepare_post_data(
        self, text: str
    ) -> dict[str, str | list[dict[str, str | list[dict[str, str | list[dict[str, str]]]]]]]:
        if self.config.get('rich_text', False):
            return {
                'blocks': [
                    {
                        'type': 'rich_text',
                        'elements': [
                            {
                                'type': 'rich_text_preformatted',
                                'elements': [
                                    {
                                        'type': 'text',
                                        'text': text,
                                    },
                                ],
                            },
                        ],
                    }
                ]
            }
        return {'text': text}


class SlackReporter(WebhookReporter):
    """Deprecated; use webhook instead."""

    __kind__ = 'slack'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        warn(
            "'slack' reporter is deprecated; replace with 'webhook' (same exact keys)", DeprecationWarning, stacklevel=1
        )
        super().__init__(*args, **kwargs)


class ShellReporter(WebhookReporter):
    """Deprecated; use run_command instead."""

    __kind__ = 'shell'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        warn("'shell' reporter is deprecated; use 'run_command' instead", DeprecationWarning, stacklevel=1)
        super().__init__(*args, **kwargs)


class DiscordReporter(TextReporter):
    """Send a message to a Discord channel using a discord webhook."""

    __kind__ = 'discord'

    config: _ConfigReportDiscord

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        default_max_length = 2000 if not self.config['embed'] else 4096
        if isinstance(self.config['max_message_length'], int):
            self.max_length = int(self.config['max_message_length'])
        else:
            self.max_length = default_max_length
        if self.config['colored']:
            self.max_length -= 11

    def submit(self) -> Response | None:  # type: ignore[override]
        webhook_url = self.config['webhook_url']
        text = '\n'.join(super().submit())

        if not text:
            logger.info('Not calling Discord API (no changes)')
            return None

        result = None
        for chunk in chunk_string(text, self.max_length, numbering=True):
            res = self.submit_to_discord(webhook_url, chunk)
            if res.status_code != 200 or res is None:
                result = res

        return result

    def submit_to_discord(self, webhook_url: str, text: str) -> Response:
        if self.config['colored']:
            text = '```diff\n' + text + '```'

        if self.config['embed']:
            filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
            subject = self.subject_with_args(filtered_job_states)

            # Content has a maximum length of 2000 characters, but the combined sum of characters in all title,
            # description, field.name, field.value, footer.text, and author.name fields across all embeds attached to
            # a message must not exceed 6000 characters.
            max_subject_length = min(2000, 6000 - len(text))
            subject = subject[:max_subject_length]

            post_data = {
                'content': subject,
                'embeds': [
                    {
                        'type': 'rich',
                        'description': text,
                    }
                ],
            }
        else:
            post_data = {'content': text}

        logger.info(f'Sending Discord request with post_data: {post_data}')

        with self.http_client as http_client:
            result = http_client.post(webhook_url, json=post_data, timeout=60)
        try:
            if result.status_code in {200, 204}:
                logger.info('Discord response: ok')
            else:
                logger.error(f'Discord error: {result.text}')
        except ValueError:
            logger.error(
                f'Failed to parse Discord response. HTTP status code: {result.status_code}, content: {result.content!r}'
            )
        return result


class ProwlReporter(TextReporter):
    """Send a detailed notification via prowlapp.com."""

    # contributed by nitz https://github.com/thp/urlwatch/pull/633

    __kind__ = 'prowl'

    config: _ConfigReportProwl

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def submit(self) -> None:  # type: ignore[override]
        api_add = 'https://api.prowlapp.com/publicapi/add'

        text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))

        # 'subject' used in the config file, but the API uses what might be called the subject as the 'event'
        event = self.subject_with_args(filtered_job_states)

        # 'application' is prepended to the message in prowl, to show the source of the notification. this too,
        # is user configurable, and may reference subject args
        from webchanges import __project_name__, __version__

        application = self.config['application']
        if application is not None:
            application = self.subject_with_args(filtered_job_states, application)
        else:
            application = f'{__project_name__} v{__version__}'

        # build the data to post
        post_data = {
            'event': event[:1024],
            'description': text[:10000],
            'application': application[:256],
            'apikey': self.config['api_key'],
            'priority': self.config['priority'],
        }

        # all set up, add the notification!
        with self.http_client as http_client:
            result = http_client.post(api_add, data=post_data, timeout=60)

        try:
            if result.status_code in {200, 204}:
                logger.info('Prowl response: ok')
            else:
                raise RuntimeError(f'Prowl error: {result.text}')
        except ValueError:
            logger.error(
                f'Failed to parse Prowl response. HTTP status code: {result.status_code}, content: {result.content!s}'
            )


class NtfyReporter(TextReporter):
    """Send messages to a ntfy server."""

    __kind__ = 'ntfy'

    config: _ConfigReportNtfy

    def submit(self, **kwargs: Any) -> None:  # type: ignore[override]
        topic_url = self.config['topic_url']
        headers = Headers({})
        config_priorities = self.config.get('priorities', {})
        if priority := config_priorities.get('default'):
            headers['Priority'] = str(priority)
        if authorization := self.config.get('authorization'):
            headers['Authorization'] = authorization

        for job_state in self.report.get_filtered_job_states(self.job_states):
            from webchanges import __project_name__

            title = f'{__project_name__.upper()} {job_state.verb.upper()}: {job_state.job.pretty_name()}'
            differ = job_state.job.differ or {}
            content = self._format_content(job_state, differ)

            job_headers = headers.copy()
            job_headers['Title'] = title

            if priority := config_priorities.get(job_state.verb.split(',')[0]):
                job_headers['Priority'] = priority

            job_headers['Actions'] = f'view, Open URL, "{job_state.job.get_location()}", clear=true'

            if httpx:
                with self.http_client as http_client:
                    result = http_client.post(topic_url, headers=job_headers, content=content)
            else:
                result = http_client.post(topic_url, headers=job_headers, data=content.encode() if content else None)
            if result.status_code != 200:
                raise RuntimeError(f"Failed to publish tp ntfy topic '{topic_url}': {result.text}")
