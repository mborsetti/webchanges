"""Email handler."""

import getpass
import logging
import smtplib
import subprocess
from email import policy
from email.message import EmailMessage
from typing import Optional, Union

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger(__name__)


class Mailer(object):
    def send(self, msg: Union[EmailMessage]) -> None:
        raise NotImplementedError

    @staticmethod
    def msg(from_email: str, to_email: str, subject: str, text_body: str, html_body: Optional[str] = None
            ) -> EmailMessage:
        """Create an Email object for a message

        :param from_email: The 'from' email address
        :param to_email: The 'to' email address
        :param subject: The 'subject' of the email
        :param text_body: The body in text format
        :param html_body: The body in html format (optional)
        """
        msg = EmailMessage(policy=policy.SMTPUTF8)
        msg['from'] = from_email
        msg['to'] = to_email
        msg['subject'] = subject
        msg.set_content(text_body, subtype='plain')
        if html_body is not None:
            msg.add_alternative(html_body, subtype='html')

        return msg


class SMTPMailer(Mailer):
    def __init__(self, smtp_user: str, smtp_server: str, smtp_port: int, tls: bool, auth: Optional[str],
                 insecure_password: Optional[str] = None) -> None:
        self.smtp_server = smtp_server
        self.smtp_user = smtp_user
        self.smtp_port = smtp_port
        self.tls = tls
        self.auth = auth
        self.insecure_password = insecure_password

    def send(self, msg: Optional[EmailMessage]) -> None:
        passwd = None
        if self.auth:
            if self.insecure_password:
                passwd = self.insecure_password
            elif keyring is not None:
                passwd = keyring.get_password(self.smtp_server, self.smtp_user)
                if passwd is None:
                    raise ValueError(f'No password available in keyring for {self.smtp_server} {self.smtp_user}')
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


class SendmailMailer(Mailer):
    def __init__(self, sendmail_path: str) -> None:
        self.sendmail_path = sendmail_path

    def send(self, msg: Union[EmailMessage]) -> None:
        # Python 3.7
        # p = subprocess.run([self.sendmail_path, '-oi', msg['To']], input=msg.as_string(), capture_output=True,
        #                    text=True)
        p = subprocess.run([self.sendmail_path, '-oi', msg['To']], input=msg.as_string(), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        if p.returncode:
            logger.error(f'Sendmail failed with {p.stderr}')


def smtp_have_password(smtp_server: str, from_email: str) -> bool:
    """Check whether the keyring password is set for the email service."""
    if keyring is None:
        return False

    return keyring.get_password(smtp_server, from_email) is not None


def smtp_set_password(smtp_server: str, from_email: str) -> None:
    """Set the keyring password for the email service. Interactive."""
    if keyring is None:
        raise ImportError('keyring module missing - service unsupported')

    password = getpass.getpass(prompt=f'Enter password for {from_email} using {smtp_server}: ')
    keyring.set_password(smtp_server, from_email, password)
