.. _reporters:

=========
Reporters
=========

By default `webchanges` prints out information about changes to the data collected to standard output (``stdout``),
which is your terminal if you run it interactively. If running via `cron` or another scheduler service, the destination
of this output depends on the schedure and its configuration.

You can change the settings to add or change where the report is sent to.  Settings are contained in the configuration
file ``webchanges.yaml``, a text file located in the ``~\.urwatch\`` directory (Linux) or in a ``webchanges`` folder
within your Documents folder, i.e. ``%USERPROFILE%/Documents/webchanges`` (Windows) and editable using any text editor
or with the command ``webchanges --edit--config``.  The configuration for the reporters will be listed under the
``reporters`` section.

Tip: to test a reporter, use the ``--test-reporter`` command-line option with the name of the reporter, e.g.::

   webchanges --test-reporter stdout

`webchanges` will generate test  ``new``, ``changed``, ``unchanged`` and ``error`` notifications and send (the ones
configured to be sent under ``display``) via the ``stdout`` reporter (if it is enabled). Any reporter that is
configured and enabled can be tested. To test if your email reporter is configured correctly, you use::

   webchanges --test-reporter email

If the test does not work, check your configuration and/or add the ``--verbose`` command-line option to show
detailed debug logs::

   webchanges --verbose --test-reporter email

At the moment, the following reporters are available

* :ref:`stdout` (enabled by default): Display summary on stdout (the console)
* :ref:`browser`: Display summary on the default web browser
* :ref:`email`: Send summary via email (including SMTP)
* :ref:`xmpp`: Send a message using the Extensible Messaging and Presence Protocol (XMPP)
* :ref:`slack`: Send a message to a Slack channel
* :ref:`telegram`: Send a message using Telegram
* :ref:`pushbullet`: Send summary via pushbullet.com
* :ref:`pushover`: Send summary via pushover.net
* :ref:`ifttt`: Send summary via IFTTT
* :ref:`matrix`: Send a message to a room using the Matrix protocol
* :ref:`mailgun`: Send email via the Mailgun service

.. To convert the "webchanges --features" output, use:
   webchanges --features | sed -e 's/^  \* \(.*\) - \(.*\)$/- **\1**: \2/'

Each reporter has a directive called ``enabled`` that can be toggled (true/false).


Please note that many reporters need additional Python packages installed to work, as noted below and in
:ref:`dependencies`.


.. _stdout:

stdout
------

Displays the summary in text format on stdout (the console)

**Optional directives**
~~~~~~~~~~~~~~~~~~~~~~~

* color: Uses color (green for additions, red for deletions) (true/false)


.. _browser:

Browser
-------

Displays the summary in HTML format using the system's default web browser



.. _email:

Email
-----

Sends email, via smtp or sendmail.


**sub-directives**
~~~~~~~~~~~~~~~~~~

* ``method``: Either `smtp` or `sendmail`
* ``from``: The sender's email address. **Do not use your main email address** but create a throwaway one!
* ``to``: The destination email address
* ``subject``: The subject line. Use {count} for the number of reports, {jobs} for the titles of the jobs reported
* ``html``: Whether the email includes HTML (true/false)

SMTP
~~~~

.. _smtp-login-with-keyring:

SMTP login with keyring
^^^^^^^^^^^^^^^^^^^^^^^

For added security, you can store your password on a keychain if you have one installed.  To do so, run ``webchanges
--smtp-login`` and enter your password.  Note that this won't allow you to run `webchanges` unattended
(e.g. from a scheduler), so you can save it in the ``insecure_password`` directive in the SMTP config instead. However,
as the name says, storing the password as plaintext in the configuration is insecure and bad practice,
but for an email account that’s only dedicated for sending emails this might be a way.

**Never ever use this method with your your primary email account!**

Seriously! Create a throw-away Gmail (or other) account just for sending out these emails!

.. code-block:: yaml

   report:
     email:
       method: smtp
         auth: true
         insecure_password: 'this_is_my_secret_password'

Once again, note that this makes it really easy for your password to be picked up by software running on your machine,
by other users logged into the system and/or for the password to appear in log files accidentally.


**SMTP sub-directives**
^^^^^^^^^^^^^^^^^^^^^^^

* ``host``: The address of the smtp server
* ``port``: The port used to communicate with the server
* ``starttls``: Whether the server uses TLS (secure)
* ``auth``: Whether authentication via username/password is required (true/false)
* ``user``: The username used to authenticate
* ``insecure_password``: The passowrd used to authenticate (if no ``keyring``)


Gmail example
^^^^^^^^^^^^^

WARNING: You **do not want to do this with your primary Google account**, but rather get a free separate one just for
sending mails from `webchanges` and similar programs. Allowing less secure apps and storing the password (even if it's
in the keychain) is not good security practice for your primary account. You have been warned!

First configure your Gmail account to allow for "less secure" (password-based) apps to login:

#. Go to https://myaccount.google.com/
#. Click on "Security"
#. Scroll all the way down to "less secure apps access" and turn it on

Then configure these directives as follows:

.. code-block:: yaml

   report:
     email:
       enabled: true
       from: your.username@gmail.com  # (edit accordingly; don't use your primary account for this!!)
       to: your.destination@example.org  # The email address of where want to receive reports
       subject: '{count} changes: {jobs}'
       html: true
       method: smtp
         host: smtp.gmail.com
         insecure_password: 'this_is_my_secret_password'
         auth: true
         port: 587
         starttls: true

Amazon Simple Email Service (SES) example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

First ensure that you have configured SES as per the `Quick start
<https://docs.aws.amazon.com/ses/latest/DeveloperGuide/quick-start.html>`__

Create a user just for `webchanges` for security reasons (so you can easily recover from a compromised user/password
leak from, e.g. from a scan of your jobs file), then configure these directives as follows:

.. code-block:: yaml

   report:
     email:
       enabled: true
       from: you@verified_domain.com  # (edit accordingly)
       to: your.destination@example.org  # The email address you want to send reports to
       subject: '{count} changes: {jobs}'
       html: true
       method: smtp
         host: email-smtp.us-west-2.amazonaws.com  # (edit accordingly)
         user: ABCDEFGHIJ1234567890  # (edit  accordingly)
         insecure_password: 'this_is_my_secret_password'  # (edit accordingly)
         auth: true
         port: 587  # (25 or 465 also work)
         starttls: true


.. _sendmail:

sendmail
~~~~~~~~

(Linux only)

Calls the `sendmail <https://www.proofpoint.com/us/products/email-protection/open-source-email-solution>`__ program .

.. _xmpp:

XMPP
----

You can have notifications sent to you through the `XMPP protocol`.

To achieve this, you should register a new XMPP account that is just used for `webchanges`.

Here is a sample configuration:

.. code:: yaml

   xmpp:
     enabled: true
     sender: 'BOT_ACCOUNT_NAME'
     recipient: 'YOUR_ACCOUNT_NAME'

For added security, you can store your password on a keychain if you have one installed.  To do so, run ``webchanges
--xmpp-login`` and enter your password.  Note that this won't allow you to run `webchanges` unattended
(e.g. from a scheduler), so you can save it in the ``insecure_password`` directive in the XMPP config instead. However,
as the name says, storing the password as plaintext in the configuration is insecure and bad practice,
but for an account that’s only dedicated for this purpose this might be a way.

.. code-block:: yaml

   report:
     xmpp:
       enabled: true
       sender: 'BOT_ACCOUNT_NAME'
       recipient: 'YOUR_ACCOUNT_NAME'
       insecure_password: 'this_is_my_secret_password'


**Required packages**
~~~~~~~~~~~~~~~~~~~~~
To run jobs with this filter, you need to install :ref:`optional_packages`. Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[xmpp]



.. _slack:

Slack
-----

Slack notifications are configured using “Slack Incoming Webhooks”. Here is a sample configuration:

.. code:: yaml

   slack:
     enabled: true
     webhook_url: 'https://hooks.slack.com/services/T50TXXXXXU/BDVYYYYYYY/PWTqwyFM7CcCfGnNzdyDYZ'

To set up Slack, from you Slack Team, create a new app and activate “Incoming Webhooks” on a channel, you’ll get a
webhook URL, copy it into the configuration as seen above.



.. _telegram:

Telegram
--------

Telegram notifications are configured using the Telegram Bot API. For this, you’ll need a Bot API token and a chat id
(see https://core.telegram.org/bots). Sample configuration:

.. code:: yaml

   telegram:
     enabled: true
     bot_token: '999999999:3tOhy2CuZE0pTaCtszRfKpnagOG8IQbP5gf' # your bot api token
     chat_id: '88888888' # the chat id where the messages should be sent

To set up Telegram, from your Telegram app, chat up BotFather (New Message, Search, “BotFather”), then say ``/newbot``
and follow the instructions. Eventually it will tell you the bot token (in the form seen above,
``<number>:<random string>``) - add this to your config file.

You can then click on the link of your bot, which will send the message ``/start``. At this point, you can use the
command ``webchanges --telegram-chats`` to list the private chats the bot is involved with. This is the chat ID that you
need to put into the config file as ``chat_id``. You may add multiple chat IDs as a YAML list:

.. code:: yaml

   telegram:
     enabled: true
     bot_token: '999999999:3tOhy2CuZE0pTaCtszRfKpnagOG8IQbP5gf' # your bot api token
     chat_id:
       - '11111111'
       - '22222222'

Don’t forget to also enable the reporter.



.. _pushover:

Pushover
--------

You can configure webchanges to send real time notifications about changes via `Pushover <https://pushover.net/>`__.
To enable this, ensure you
have the ``chump`` python package installed (see :doc:`dependencies`). Then edit your config (``webchanges
--edit-config``) and enable pushover. You will also need to add to the config your Pushover user key and a unique app
key (generated by registering webchanges as an application on your `Pushover account
<https://pushover.net/apps/build>`__.

You can send to a specific device by using the device name, as indicated when you add or view your list of devices in
the Pushover console. For example ``device:  'MyPhone'``, or ``device: 'MyLaptop'``. To send to *all* of your devices,
set ``device: null`` in your config (``webchanges --edit-config``) or leave out the device configuration completely.

Setting the priority is possible via the ``priority`` config option, which can be ``lowest``, ``low``, ``normal``,
``high`` or ``emergency``. Any other setting (including leaving the option unset) maps to ``normal``.

**Required packages**
~~~~~~~~~~~~~~~~~~~~~
To use this report you need to install :ref:`optional_packages`. Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[pushover]



.. _pushbullet:

Pushbullet
----------

Pushbullet notifications are configured similarly to Pushover (see above). You’ll need to add to the config your
Pushbullet Access Token, which you can generate at https://www.pushbullet.com/#settings


**Required packages**
~~~~~~~~~~~~~~~~~~~~~
To use this report you need to install :ref:`optional_packages`. Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[pushbullet]



.. _ifttt:

IFTTT
-----

To configure IFTTT events, you need to retrieve your key from `<https://ifttt.com/maker_webhooks/settings>`__.

The URL shown in "Account Info" has the following format:

.. code::

   https://maker.ifttt.com/use/{key}

In this URL, ``{key}`` is your API key. The configuration should look like this (you can pick any event name you want):

.. code:: yaml

   ifttt:
     enabled: true
     key: aA12abC3D456efgHIjkl7m
     event: event_name_you_want

The event will contain three values in the posted JSON:

* ``value1``: The type of change (``new``, ``changed``, ``unchanged`` or ``error``)
* ``value2``: The name of the job (``name`` directive in ``jobs.yaml``)
* ``value3``: The location of the job (``url`` or ``command`` directive in ``jobs.yaml``)

These values will be passed on to the Action in your Recipe.


.. _matrix:

Matrix
------

Sends notifications through the `Matrix protocol <https://matrix.org>`__.

You first need to register a Matrix account for the bot on any home server.

You then need to acquire an access token and room ID, using the following instructions adapted from `this
guide <https://t2bot.io/docs/access_tokens/>`__:

1. Open `Riot.im <https://riot.im/app/>`__ in a private browsing window
2. Register/Log in as your bot, using its user ID and password.
3. Set the display name and avatar, if desired.
4. In the settings page, select the "Help & About" tab, scroll down to the bottom and click Access Token:
   <click to reveal>.
5. Copy the highlighted text to your configuration.
6. Join the room that you wish to send notifications to.
7. Go to the Room Settings (gear icon) and copy the *Internal Room ID* from the bottom.
8. Close the private browsing window **but do not log out, as this invalidates the Access Token**.

Here is a sample configuration:

.. code:: yaml

   matrix:
     enabled: true
     homeserver: https://matrix.org
     access_token: 'YOUR_TOKEN_HERE'
     room_id: '!roomroomroom:matrix.org'

You will probably want to use the following configuration for the ``markdown`` reporter, if you intend to post change
notifications to a public Matrix room, as the messages quickly become noisy:

.. code:: yaml

   markdown:
     enabled: true
     details: false
     footer: false
     minimal: true



.. _mailgun:

Mailgun
-------

Sends email using the commercial `Mailgun <https://www.mailgun.com/>`__ service.


**sub-directives**
~~~~~~~~~~~~~~~~~~

* ``domain``: The domain
* ``api_key``: API key (see `here
  <https://help.mailgun.com/hc/en-us/articles/203380100-Where-Can-I-Find-My-API-Key-and-SMTP-Credentials->`__)
* ``from_name``: Sender's name
* ``from_mail``: Sender's email address
* ``to``: Recipient's email address
* ``subject``: The subject line. Use {count} for the number of reports, {jobs} for the titles of the jobs reported
* ``region`` (optional)
