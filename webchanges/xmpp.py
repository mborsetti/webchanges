import getpass

try:
    import keyring
except ImportError:
    keyring = None

try:
    import aioxmpp
except ImportError:
    aioxmpp = None


class XMPP(object):
    def __init__(self, sender, recipient, insecure_password=None):
        if aioxmpp is None:
            raise ImportError('Python package "aioxmpp" not installed')

        self.sender = sender
        self.recipient = recipient
        self.insecure_password = insecure_password

    async def send(self, chunk):
        if self.insecure_password:
            password = self.insecure_password
        elif keyring is not None:
            password = keyring.get_password('urlwatch_xmpp', self.sender)
            if password is None:
                raise ValueError(f'No password available in keyring for {self.sender}')
        else:
            raise ValueError(f'No password available for {self.sender}')

        jid = aioxmpp.JID.fromstr(self.sender)
        client = aioxmpp.PresenceManagedClient(
            jid, aioxmpp.make_security_layer(password)
        )
        recipient_jid = aioxmpp.JID.fromstr(self.recipient)

        async with client.connected() as stream:
            msg = aioxmpp.Message(to=recipient_jid, type_=aioxmpp.MessageType.CHAT,)
            msg.body[None] = chunk

            await stream.send_and_wait_for_sent(msg)


def xmpp_have_password(sender):
    return keyring.get_password('urlwatch_xmpp', sender) is not None


def xmpp_set_password(sender):
    """ Set the keyring password for the XMPP connection. Interactive."""
    if keyring is None:
        raise ImportError('Python package "keyring" missing - service unsupported')

    password = getpass.getpass(prompt=f'Enter password for {sender}: ')
    keyring.set_password('urlwatch_xmpp', sender, password)
