"""Email handler."""

import email.mime.multipart
import email.mime.text
import email.utils
import getpass
import logging
import smtplib
import subprocess
from typing import Any, Optional, Union

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger(__name__)


class Mailer(object):
    def send(self, msg: Any) -> None:
        raise NotImplementedError

    @staticmethod
    def msg_plain(from_email: str, to_email: str, subject: str, body: str) -> email.mime.text.MIMEText:
        msg = email.mime.text.MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Date'] = email.utils.formatdate()

        return msg

    @staticmethod
    def msg_html(from_email: str, to_email: str, subject: str, body_text: str,
                 body_html: str) -> email.mime.multipart.MIMEMultipart:
        msg = email.mime.multipart.MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Date'] = email.utils.formatdate()

        msg.attach(email.mime.text.MIMEText(body_text, 'plain', 'utf-8'))
        msg.attach(email.mime.text.MIMEText(body_html, 'html', 'utf-8'))

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

    def send(self, msg: Union[email.mime.text.MIMEText, email.mime.multipart.MIMEMultipart]) -> None:
        s = smtplib.SMTP(self.smtp_server, self.smtp_port)
        s.ehlo()

        if self.tls:
            s.starttls()

        if self.auth:
            if self.insecure_password:
                passwd = self.insecure_password
            elif keyring is not None:
                passwd = keyring.get_password(self.smtp_server, self.smtp_user)
                if passwd is None:
                    raise ValueError(f'No password available in keyring for {self.smtp_server} {self.smtp_user}')
            else:
                raise ValueError(f'No password available for {self.smtp_server} {self.smtp_user}')
            s.login(self.smtp_user, passwd)

        s.sendmail(msg['From'], msg['To'].split(','), msg.as_string())
        s.quit()


class SendmailMailer(Mailer):
    def __init__(self, sendmail_path: str) -> None:
        self.sendmail_path = sendmail_path

    def send(self, msg: Union[email.mime.text.MIMEText, email.mime.multipart.MIMEMultipart]) -> None:
        # Python 3.7
        # p = subprocess.run([self.sendmail_path, '-oi', msg['To']], input=msg.as_string(), capture_output=True,
        #                    text=True)
        p = subprocess.run([self.sendmail_path, '-oi', msg['To']], input=msg.as_string(), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        if p.returncode:
            logger.error(f'Sendmail failed with {p.stderr}')


def smtp_have_password(smtp_server: str, from_email: str) -> bool:
    return keyring.get_password(smtp_server, from_email) is not None


def smtp_set_password(smtp_server: str, from_email: str) -> None:
    """ Set the keyring password for the mail connection. Interactive."""
    if keyring is None:
        raise ImportError('keyring module missing - service unsupported')

    password = getpass.getpass(prompt=f'Enter password for {from_email} using {smtp_server}: ')
    keyring.set_password(smtp_server, from_email, password)
