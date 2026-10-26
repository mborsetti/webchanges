"""Email handler."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

__lazy_modules__ = [
    'base64',
    'email',
    'email.message',
    'email.utils',
    'getpass',
    'importlib.util',
    're',
    'smtplib',
    'socket',
    'subprocess',
]

import base64
import getpass
import importlib.util
import logging
import re
import smtplib
import socket
import subprocess
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.utils import formatdate
from typing import TYPE_CHECKING

from webchanges.util import missing_dependency

# The optional dependency keyring is imported only when a password is stored in or read from it (see
# missing_dependency() in webchanges/util.py).

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

logger = logging.getLogger(__name__)


def _ehlo_hostname() -> str:
    """The local hostname to send in the SMTP EHLO greeting, determined exactly as smtplib.SMTP does by default.

    RFC 2821 says to use the fully qualified domain name, or, if that can't be determined, a domain literal (the
    encoded IP address, e.g. [192.0.2.1]).

    :returns: The hostname.
    """
    fqdn = socket.getfqdn()
    if '.' in fqdn:
        return fqdn
    addr = '127.0.0.1'
    try:
        addr = socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        pass
    return f'[{addr}]'


def import_keyring(used_by: str) -> ModuleType:
    """Import the optional keyring package (used to store passwords), or raise the standard ImportError.

    :param used_by: What needs keyring, for the error message (e.g. "storing the SMTP password in the keyring").
    :returns: The keyring module.
    """
    try:
        import keyring
    except ImportError as e:  # pragma: no cover
        raise missing_dependency(e, 'keyring', used_by=used_by, extra='safe_password') from e
    return keyring


# Seconds to wait for the SMTP server, both to connect and for each reply, before giving up; without it an unreachable
# or unresponsive server blocks the run indefinitely.
SMTP_TIMEOUT = 60


class Mailer:
    """Mailer class."""

    def send(self, msg: EmailMessage) -> None:
        """Send a message.

        :param msg: The message to be sent.
        :raises NotImplementedError: Use a subclass of EmailMessage to send a message.
        """
        raise NotImplementedError

    @staticmethod
    def msg(
        from_email: str,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        utf_8: bool = True,
        reply_to: str | None = None,
    ) -> EmailMessage:
        """Create an Email object for a message.

        :param from_email: The 'From' email address
        :param to_email: The 'To' email address
        :param subject: The 'Subject' of the email
        :param text_body: The body in text format
        :param html_body: The body in html format (optional)
        :param utf_8: Whether to format the message using SMTPUTF8 (optional)
        :param reply_to: The 'Reply-To' email address(es) (optional; the header is omitted if empty)
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

        msg = EmailMessage(policy=policy.SMTPUTF8 if utf_8 else policy.SMTP)
        msg['From'] = from_email
        msg['To'] = to_email
        if reply_to:
            msg['Reply-To'] = reply_to
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg.set_content(text_body, subtype='plain')
        if html_body is not None:
            if ';base64,' not in html_body:
                msg.add_alternative(html_body, subtype='html')
            else:
                html_body, cid_dict = extract_inline_images(html_body)
                msg.add_alternative(html_body, subtype='html')
                payloads: EmailMessage = msg.get_payload()[1]  # ty:ignore[invalid-argument-type, invalid-assignment]
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
        passwd = ''
        if self.auth:
            if self.insecure_password:
                passwd = self.insecure_password
            else:
                keyring = import_keyring(used_by="the SMTP password (as no 'insecure_password' is set)")
                key_pass = keyring.get_password(self.smtp_server, self.smtp_user)
                if key_pass is None:
                    raise ValueError(f'No password available in keyring for {self.smtp_server} {self.smtp_user}')
                passwd = key_pass

        # The local hostname sent in EHLO is looked up before connecting (the argument is evaluated first), as smtplib
        # would otherwise look it up after connecting, which can take seconds on hosts with slow reverse DNS and make
        # the server time out waiting for the EHLO (e.g. Amazon SES: '451 4.4.2 Timeout waiting for data from client').
        with smtplib.SMTP(
            self.smtp_server, self.smtp_port, local_hostname=_ehlo_hostname(), timeout=SMTP_TIMEOUT
        ) as server:
            server.ehlo()
            if self.tls:
                server.starttls()
            if self.auth:
                server.login(self.smtp_user, passwd)
            if msg:
                server.send_message(msg)
                logger.info(f'SMTP email sent to {msg.get("to")} via {self.smtp_server}')


@dataclass
class SendmailMailer(Mailer):
    """The Mailer class to use sendmail executable."""

    sendmail_path: str | Path

    def send(self, msg: EmailMessage) -> None:
        """Send a message via the sendmail executable.

        :param msg: The message to be sent.
        """
        if msg['From']:
            command = [self.sendmail_path, '-oi', '-f', msg['From']] + [addr.strip() for addr in msg['To'].split(',')]
        else:
            command = [self.sendmail_path, '-oi'] + [addr.strip() for addr in msg['To'].split(',')]
        p = subprocess.run(  # noqa: S603 subprocess call - check for execution of untrusted input.
            command,
            check=False,
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
    if importlib.util.find_spec('keyring') is None:
        return False

    import keyring

    return keyring.get_password(smtp_server, from_email) is not None


def smtp_set_password(smtp_server: str, from_email: str) -> None:
    """Set the keyring password for the email service. Interactive.

    :param smtp_server: The address of the SMTP server.
    :param from_email: The email address of the sender.
    """
    keyring = import_keyring(used_by='storing the SMTP password in the keyring')
    password = getpass.getpass(prompt=f'Enter password for {from_email} using {smtp_server}: ')
    keyring.set_password(smtp_server, from_email, password)
