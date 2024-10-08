"""Email handler."""

# The code below is subject to the license contained in the LICENSE file, which is part of the source code.

from __future__ import annotations

import base64
import getpass
import logging
import re
import smtplib
import subprocess  # noqa: S404 Consider possible security implications associated with the subprocess module.
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
from types import ModuleType

try:
    import keyring
except ImportError as e:  # pragma: no cover
    keyring = str(e)  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class Mailer:
    """Mailer class."""

    def send(self, msg: EmailMessage) -> None:
        """Send a message.

        :param msg: The message to be sent.
        :raises NotImplementedError: Use a subclass of EmailMessage to send a message.
        """
        raise NotImplementedError

    @staticmethod
    def msg(from_email: str, to_email: str, subject: str, text_body: str, html_body: str | None = None) -> EmailMessage:
        """Create an Email object for a message.

        :param from_email: The 'From' email address
        :param to_email: The 'To' email address
        :param subject: The 'Subject' of the email
        :param text_body: The body in text format
        :param html_body: The body in html format (optional)
        """

        def extract_inline_images(html_body: str) -> tuple[str, dict[str, bytes]]:
            """Extract inline images from the email.

            :param html_body: The HTML with inline images.

            :return: The HTML with src tags and a dictionary of cid and file.
            """
            cid_dict: dict[str, bytes] = {}
            cid_counter = 1

            def replace_img(match: re.Match) -> str:
                """Function to replace the matched img tags with src="cid:<...>"> and to add the cid and the image to
                the cid_dict object.
                """
                nonlocal cid_counter
                image_format, image_data_b64 = match.groups()
                image_data = base64.b64decode(image_data_b64)
                image_cid = f'image{cid_counter}_{image_format.split(";")[0]}'
                cid_dict[image_cid] = image_data
                new_img_tag = f'src="cid:{image_cid}"'
                cid_counter += 1
                return new_img_tag

            edited_html = re.sub(r'src="data:image/(.+?);base64,(.+?)"', replace_img, html_body)
            return edited_html, cid_dict

        msg = EmailMessage(policy=policy.SMTPUTF8)
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg.set_content(text_body, subtype='plain')
        if html_body is not None:
            if ';base64,' not in html_body:
                msg.add_alternative(html_body, subtype='html')
            else:
                html_body, cid_dict = extract_inline_images(html_body)
                msg.add_alternative(html_body, subtype='html')
                payloads: EmailMessage = msg.get_payload()[1]  # type: ignore[assignment,index]
                for image_cid, image_data in cid_dict.items():
                    payloads.add_related(
                        image_data,
                        maintype='image',
                        subtype=image_cid.split('_')[-1],
                        disposition='inline',
                        filename=image_cid,
                        cid=f'<{image_cid}>',
                    )
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
    insecure_password: str | None = None

    def send(self, msg: EmailMessage | None) -> None:
        """Send a message via the SMTP server.

        :param msg: The message to be sent. Optional in order to allow server login testing.
        """
        passwd = ''  # noqa: S105 Possible hardcoded password.
        if self.auth:
            if self.insecure_password:
                passwd = self.insecure_password
            elif isinstance(keyring, ModuleType):
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

    sendmail_path: str | Path

    def send(self, msg: EmailMessage) -> None:
        """Send a message via the sendmail executable.

        :param msg: The message to be sent.
        """
        if msg['From']:
            command = [self.sendmail_path, '-oi', '-f', msg['From']] + [
                addr.strip() for addr in msg['To'].split(',' '')
            ]
        else:
            command = [self.sendmail_path, '-oi'] + [addr.strip() for addr in msg['To'].split(',')]
        p = subprocess.run(  # noqa: S603 subprocess call - check for execution of untrusted input.
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
    if isinstance(keyring, str):
        return False

    return keyring.get_password(smtp_server, from_email) is not None


def smtp_set_password(smtp_server: str, from_email: str) -> None:
    """Set the keyring password for the email service. Interactive.

    :param smtp_server: The address of the SMTP server.
    :param from_email: The email address of the sender.
    """
    if isinstance(keyring, str):
        raise ImportError(f"Python package 'keyring' cannot be loaded - service unsupported\n{keyring}")

    password = getpass.getpass(prompt=f'Enter password for {from_email} using {smtp_server}: ')
    keyring.set_password(smtp_server, from_email, password)
