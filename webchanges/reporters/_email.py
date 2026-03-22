"""Email reporters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from webchanges.mailer import Mailer, SendmailMailer, SMTPMailer
from webchanges.reporters._base import HtmlReporter, TextReporter

if TYPE_CHECKING:
    from webchanges.storage import _ConfigReportEmail, _ConfigReportMailgun

logger = logging.getLogger(__name__)


class EMailReporter(TextReporter):
    """Send summary via email (including SMTP)."""

    __kind__ = 'email'

    config: _ConfigReportEmail

    def submit(self, **kwargs: Any) -> None:  # ty:ignore[invalid-method-override]
        body_text = '\n'.join(super().submit())

        if not body_text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        subject = self.subject_with_args(filtered_job_states)

        utf_8 = True
        if self.config['method'] == 'smtp':
            smtp_config = self.config['smtp']
            smtp_user = smtp_config['user'] or self.config['from']
            use_auth = smtp_config['auth']
            utf_8 = smtp_config.get('utf-8') or smtp_config.get('utf_8')  # backwards compatible
            mailer: Mailer = SMTPMailer(
                smtp_user,
                smtp_config['host'],
                smtp_config['port'],
                smtp_config['starttls'],
                use_auth,
                smtp_config['insecure_password'],
            )
        elif self.config['method'] == 'sendmail':
            mailer = SendmailMailer(self.config['sendmail']['path'])
        else:
            raise ValueError(f'Unknown email reporter method: {self.config["method"]}')

        if self.config['html']:
            html_reporter = HtmlReporter(
                self.report, self.config, self.job_states, self.duration, self.jobs_files, self.differ_defaults
            )
            body_html = '\n'.join(html_reporter.submit())
            msg = mailer.msg(self.config['from'], self.config['to'], subject, body_text, body_html, utf_8=utf_8)
        else:
            msg = mailer.msg(self.config['from'], self.config['to'], subject, body_text, utf_8=utf_8)

        mailer.send(msg)


class MailgunReporter(TextReporter):
    """Send email via the Mailgun service."""

    __kind__ = 'mailgun'

    config: _ConfigReportMailgun

    def submit(self) -> str | None:  # ty:ignore[invalid-method-override]
        region = self.config['region']
        domain = self.config['domain']
        api_key = self.config['api_key']
        from_name = self.config['from_name']
        from_mail = self.config['from_mail']
        to = self.config['to']

        if region == 'us':
            region = ''
        elif region != '':
            region = f'.{region}'

        body_text = '\n'.join(super().submit())
        body_html = '\n'.join(self.convert(HtmlReporter).submit())

        if not body_text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return None

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        subject = self.subject_with_args(filtered_job_states)

        logger.info(f"Sending Mailgun request for domain: '{domain}'")
        with self.http_client as http_client:
            result = http_client.post(
                f'https://api{region}.mailgun.net/v3/{domain}/messages',
                auth=('api', api_key),
                data={
                    'from': f'{from_name} <{from_mail}>',
                    'to': to,
                    'subject': subject,
                    'text': body_text,
                    'html': body_html,
                },
                timeout=60,
            )

        try:
            json_res = result.json()

            if result.status_code == 200:
                logger.info(f"Mailgun response: id '{json_res['id']}'. {json_res['message']}")
            else:
                raise RuntimeError(f'Mailgun error: {json_res["message"]}')
        except ValueError:
            raise RuntimeError(
                f'Failed to parse Mailgun response. HTTP status code: {result.status_code}, content: {result.text}'
            ) from None
        return None
