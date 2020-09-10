# -*- coding: utf-8 -*-

import email.mime.multipart
import email.mime.text
import email.utils
import getpass
import logging
import smtplib
import subprocess

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger(__name__)


class Mailer(object):
    def send(self, msg):
        raise NotImplementedError

    def msg_plain(self, from_email, to_email, subject, body):
        msg = email.mime.text.MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Date'] = email.utils.formatdate()

        return msg

    def msg_html(self, from_email, to_email, subject, body_text, body_html):
        msg = email.mime.multipart.MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Date'] = email.utils.formatdate()

        msg.attach(email.mime.text.MIMEText(body_text, 'plain', 'utf-8'))
        msg.attach(email.mime.text.MIMEText(body_html, 'html', 'utf-8'))

        return msg


class SMTPMailer(Mailer):
    def __init__(self, smtp_user, smtp_server, smtp_port, tls, auth, insecure_password=None):
        self.smtp_server = smtp_server
        self.smtp_user = smtp_user
        self.smtp_port = smtp_port
        self.tls = tls
        self.auth = auth
        self.insecure_password = insecure_password

    def send(self, msg):
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
    def __init__(self, sendmail_path):
        self.sendmail_path = sendmail_path

    def send(self, msg):
        p = subprocess.Popen([self.sendmail_path, '-oi', msg['To']],
                             stdin=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             universal_newlines=True)
        result = p.communicate(msg.as_string())
        if p.returncode:
            logger.error(f'Sendmail failed with {result}')


def smtp_have_password(smtp_server, from_email):
    return keyring.get_password(smtp_server, from_email) is not None


def smtp_set_password(smtp_server, from_email):
    """ Set the keyring password for the mail connection. Interactive."""
    if keyring is None:
        raise ImportError('keyring module missing - service unsupported')

    password = getpass.getpass(prompt=f'Enter password for {from_email} using {smtp_server}: ')
    keyring.set_password(smtp_server, from_email, password)
