"""Email handler."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import getpass
import logging
import smtplib
import subprocess
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from pathlib import Path
from typing import Optional, Union

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class Mailer(object):
    """Mailer class."""

    def send(self, msg: Union[EmailMessage]) -> None:
        """Send a message.

        :param msg: The message to be sent.
        :raises NotImplementedError: Use a subclass of EmailMessage to send a message.
        """
        raise NotImplementedError

    @staticmethod
    def msg(
        from_email: str, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None
    ) -> EmailMessage:
        """Create an Email object for a message.

        :param from_email: The 'From' email address
        :param to_email: The 'To' email address
        :param subject: The 'Subject' of the email
        :param text_body: The body in text format
        :param html_body: The body in html format (optional)
        """
        msg = EmailMessage(policy=policy.SMTPUTF8)
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.set_content(text_body, subtype='plain')
        if html_body is not None:
            msg.add_alternative(html_body, subtype='html')

        return msg


@dataclass
class SMTPMailer(Mailer):
    """The Mailer class for SMTP.

    :param smtp_user: The username for the SMTP server.
    :param smtp_server: The address of the SMTP server.
    :param smtp_port: The port of the SMTP server.
    :param tls: Whether tls is to be used to connect to the SMTP server.
    :param auth: Whether authentication is to be used with the SMTP server.
    :param insecure_password: The password for the SMTP server (optional, to be used only if no keyring is present).
    """

    smtp_user: str
    smtp_server: str
    smtp_port: int
    tls: bool
    auth: bool
    insecure_password: Optional[str] = None

    def send(self, msg: Optional[EmailMessage]) -> None:
        """Send a message via the SMTP server.

        :param msg: The message to be sent. Optional in order to allow server login testing.
        """
        passwd = ''  # nosec: B105 Possible hardcoded password
        if self.auth:
            if self.insecure_password:
                passwd = self.insecure_password
            elif keyring is not None:
                key_pass = keyring.get_password(self.smtp_server, self.smtp_user)
                if key_pass is None:
                    raise ValueError(f'No password available in keyring for {self.smtp_server} {self.smtp_user}')
                else:
                    passwd = key_pass
            else:
                raise ValueError(f'No password available for {self.smtp_server} {self.smtp_user}')

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.ehlo()
            if self.tls:
                server.starttls()
            if self.auth:
                server.login(self.smtp_user, passwd)
            if msg:
                server.send_message(msg)
                logger.info(f"SMTP email sent to {msg.get('to')} via {self.smtp_server}")


@dataclass
class SendmailMailer(Mailer):
    """The Mailer class to use sendmail executable."""

    sendmail_path: Union[str, Path]

    def send(self, msg: Union[EmailMessage]) -> None:
        """Send a message via the sendmail executable.

        :param msg: The message to be sent.
        """
        if msg['From']:
            command = [self.sendmail_path, '-oi', msg['To']]
        else:
            command = [self.sendmail_path, '-oi', '-f', msg['From'], msg['To']]
        p = subprocess.run(
            command,
            input=msg.as_string(),
            capture_output=True,
            text=True,
        )
        if p.returncode:
            logger.error(f'Sendmail failed with {p.stderr}')


def smtp_have_password(smtp_server: str, from_email: str) -> bool:
    """Check whether the keyring password is set for the email service.

    :param smtp_server: The address of the SMTP server.
    :param from_email: The email address of the sender.
    :returns: True if the keyring password is set.
    """
    if keyring is None:
        return False

    return keyring.get_password(smtp_server, from_email) is not None


def smtp_set_password(smtp_server: str, from_email: str) -> None:
    """Set the keyring password for the email service. Interactive.

    :param smtp_server: The address of the SMTP server.
    :param from_email: The email address of the sender.
    """
    if keyring is None:
        raise ImportError('keyring module missing - service unsupported')

    password = getpass.getpass(prompt=f'Enter password for {from_email} using {smtp_server}: ')
    keyring.set_password(smtp_server, from_email, password)
