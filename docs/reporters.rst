.. _reporters:

=========
Reporters
=========
Reporters display or send the :ref:`report <reports>` containing the changes detected.

By default, the ``stdout`` reporter is enabled, and a :ref:`text <text>` report is sent to the standard output
(your terminal if you are running :program:`webchanges` interactively).

.. note::
   If running :program:`webchanges` via cron or another scheduler service, the destination of the standard output
   depends on the scheduler and how it is configured.

The configuration file ``config.yaml`` contains the directives toggling the reporters available on
or off, and their sub-directives (settings). This file is editable using any text editor or with the command
``webchanges --edit--config``. Reporters are listed  under the ``report`` section.

Each reporter has a directive called ``enabled`` that can be set to true or false.

.. note::
   The ``config.yaml`` file is located in Linux or macOS in the ``~/.config/webchanges`` directory, in Windows in
   the :program:`webchanges` folder within your Documents folder (i.e. ``%USERPROFILE%\Documents\webchanges``).

.. note::
   The ``config.yaml`` file is created at the first run of ``webchanges --edit`` or ``webchanges --edit--config``.

Tip: If you are running :program:`webchanges` on a cloud server on a different timezone (e.g. UTC), see :ref:`tz`
below to set the time zone to be uses for reporting.

.. _reporters-list:

At the moment, the following reporters are available:

* :ref:`stdout` (enabled by default): Display on stdout (the console).
* :ref:`browser`: Launch the default web browser.
* :ref:`discord`: Send to Discord channel.
* :ref:`email`: Send via email (SMTP or sendmail).
* :ref:`ifttt`: Send via IFTTT.
* :ref:`mailgun`: Send via email using the Mailgun service.
* :ref:`matrix`: Send to a room using the Matrix protocol.
* :ref:`prowl`: Send via prowlapp.com.
* :ref:`pushbullet`: Send via Pushbullet.
* :ref:`pushover`: Send via Pushover.
* :ref:`run_command`: Run a custom command on the local system.
* :ref:`telegram`: Send via Telegram.
* :ref:`webhook`: Send to an e.g. Slack or Mattermost channel using the service's webhook.
* :ref:`xmpp`: Send using the Extensible Messaging and Presence Protocol (XMPP).

Programmers can write their own reporter(s) as a :ref:`hook <hooks>`. file.

.. To convert the "webchanges --features" output, use:
   webchanges --features | sed -e 's/^  \* \(.*\) - \(.*\)$/- **\1**: \2/'

Please note that many reporters need the installation of additional Python packages to work, as noted below and in
:ref:`dependencies <dependencies>`.


.. tip:: While jobs are executed in parallel for speed, the output is sorted alphabetically in reports so you can
   use the :ref:`name` to control the order in which they appear in the report.

.. versionchanged:: 3.11
   Reports are sorted by job name.

To test a reporter, use the ``--test-reporter`` command-line option with the name of the reporter, e.g.
``webchanges --test-reporter stdout``. :program:`webchanges` will generate dummy  ``new``, ``changed``, ``unchanged``
and ``error`` notifications and send the ones configured to be sent under ``display`` via the selected
reporter, in this example ``stdout``. Any reporter that is configured and enabled can be tested.

For example, to test if your email reporter is configured correctly, use::

   webchanges --test-reporter email

If the test does not work, check your configuration and/or add the ``--verbose`` command-line option to show
detailed debug logs::

   webchanges --test-reporter email --verbose


Reporters are based on :ref:`reports <reports>`, as follows, and inherit that report's settings:

.. inheritance-ascii-tree:: webchanges.reporters.ReporterBase

.. note::
   Even though the ``email`` reporter is listed under ``text`` for historical reason, it also inherits from the
   ``html`` report when its ``html`` option is set to ``true`` (default).


.. _tz:

Time zone (global setting)
--------------------------
You can set the timezone for reports by entering a `IANA time zone name
<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>`__ in the ``tz`` directive of the ``report`` section.
This is useful if for example you are running :program:`webchanges` on a cloud server on a different timezone (e.g.
UTC). Note that this directive is ignored by any outside differs called by the :ref:``command_diff`` differ.

.. code-block:: yaml

   report:
     tz: America/New York

If the directive is missing, or its value is null or blank, the timezone of the system that :program:`webchanges` runs
on will be used in reports.

.. versionadded:: 3.8



.. _browser:

Browser
-------
Displays the :ref:`HTML report <html>` using the system's default web browser.

.. code-block:: yaml

   report:
     tz: null  # or whatever you want it to be
     browser:
       enabled: true  # don't forget to set this to true! :)

.. versionadded:: 3.0



.. _discord:

Discord
-------
Sends a :ref:`text <text>` report as a message in a Discord channel.

To use this reporter you must first create a webhook in Discord. From your Discord server settings select Integration
and create a "New Webhook", give the webhook a name to post under, select a channel, press on "Copy Webhook URL" and
paste the URL into the configuration as seen below (see
`here <https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks>`__ for Discord's help).

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     webhook:
       enabled: true  # don't forget to set this to true! :)
       webhook_url: https://discordapp.com/api/webhooks/11111XXXXXXXXXXX/BBBBYYYYYYYYYYYYYYYYYYYYYYYyyyYYYYYYYYYYYYYY
       embed: true
       subject: "[webchanges] {count} changes{jobs_files}: {jobs}"
       colored: true

Embedded content might make it easier to read and identify individual reports. If ``embed`` is set to true then the
``subject`` will be the content of the message and the report will be shown as embedded text; if ``colored`` is also
set to true then the report will be embedded as code of diff type, enabling Discord's `syntax highlighting
<https://highlightjs.org/static/demo/>`__ and colorization.

Sub-directives
~~~~~~~~~~~~~~
* ``webhook_url`` (required): The Discord webhook URL.
* ``embed``: If true, the content will be sent as an Embed object (true/false). Default is true.
* ``subject``: Only relevant if ``embed`` is true, it's a string that precedes the embedded report; use ``{count}``
  for the number of reports, ``{jobs}`` for the title of jobs reported, and {jobs_files} for a space followed by
  the name of the jobs file(s) used within parenthesis, stripped of preceding ``jobs-``, if not using the default
  ``jobs.yaml``. Default: ``[webchanges] {count}  changes:{jobs_files} {jobs}``.
* ``colored``: If true, the report will an Embed object formatted as diff code to enable colored syntax highlighting
  (true/false). Default is true.
* ``max_message_length``: The maximum length of a message in characters. Default is the maximum allowed by
  Discord: either 2,000 or, if ``embed`` is true, 4,096.

.. versionchanged:: 3.9.2
   Added sub-directives ``embed``, ``subject`` and ``colored``.


.. _email:

Email
-----
Sends the report via email (via SMTP or the sendmail external program).

Sub-directives
~~~~~~~~~~~~~~
* ``method``: Either ``smtp`` or ``sendmail``.
* ``from``: The sender's email address. **Do not use your main email address** but create a throwaway one!
* ``to``: The destination email address(es); if sending to more than one recipient, concatenate the addresses with a
  comma (``,``).
* ``subject``: The subject line. Use ``{count}`` for the number of reports, ``{jobs}`` for the title of jobs
  reported, and {jobs_files} for a space followed by the name of the jobs file(s) used within parenthesis, stripped
  of preceding ``jobs-``, if not using the default ``jobs.yaml``. Default: ``[webchanges] {count}
  changes:{jobs_files} {jobs}``.
* ``html``: Whether the email includes HTML (true/false).

.. _smtp:

SMTP
~~~~

Plaintext password
^^^^^^^^^^^^^^^^^^
You can save a password in the ``insecure_password`` directive in the SMTP configuration section to enable unattended
scheduled runs of :program:`webchanges`. As the name says, storing the password as plaintext in the configuration is
insecure and bad practice, yet for a throwaway account that is only used for sending these reports this might be a
low-risk way to run unattended.

.. code-block:: yaml

   report:
     tz: null  # or whatever you want it to be
     email:
       enabled: true  # don't forget to set this to true! :)
       from: webchanges <throwawayaccount@example.com>  # (edit accordingly; don't use your primary account for this!!)
       to: myself@example.com, someonelse@example.com  # The email address(es) of where want to receive reports
       subject: "[webchanges] {count} changes: {jobs}"
       html: true
       method: smtp
       smtp:
         host: smtp.example.com
         port: 587
         user: throwawayaccount@example.com  # (edit accordingly; don't use your primary account for this!!)
         starttls: true
         auth: true
         insecure_password: "this_is_my_secret_password"

.. warning::
   **Never ever use this method with your your primary email account!**  Seriously! This method makes it really easy
   for your password to be picked up by software (e.g. a virus) running on your machine, by other users logged into
   the system, and/or for the password to appear in log files accidentally, so it's **insecure**. Create a throw-away
   free email account just for sending out these emails.

.. _smtp-login-with-keychain:

Keyring password
^^^^^^^^^^^^^^^^
A secure way to store your password is to use a keyring by running ``webchanges --smtp-login`` after configuring your
``host`` and ``user``; this requires installing the optional ``safe_password`` dependencies (see optional packages
below). Be aware that the use of keyring won't allow you to run :program:`webchanges` unattended (e.g. from a
scheduler). If you're storing the password in a keyring, the ``insecure_password`` key is ignored and can be left
blank.

SMTP sub-directives
^^^^^^^^^^^^^^^^^^^
* ``host``: The address of the SMTP server. Default is 'localhost'
* ``port``: The port used to communicate with the server. Default is 25.
* ``starttls``: Whether the server uses SSL/TLS encryption (true/false). Default is true.
* ``user``: The username used to authenticate.
* ``auth``: Whether authentication via username/password is required (true/false). Default is true.
* ``insecure_password``: The password used to authenticate (if keyring is not used).

Amazon Simple Email Service (SES) example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
First ensure that you have configured SES as per the `Quick start
<https://docs.aws.amazon.com/ses/latest/DeveloperGuide/quick-start.html>`__

Create an email address just for sending mails from :program:`webchanges` and similar programs for security reasons (so
you can easily recover from a compromised user/password leak from, e.g. from a scan of your jobs file), then configure
these directives as follows:

.. code-block:: yaml

   report:
     tz: America/New_York  # or whatever you want it to be
     email:
       enabled: true  # don't forget to set this to true! :)
       from: my_programs@verified_domain.com  # (edit accordingly)
       to: your.destination@example.org  # The email address you want to send reports to
       subject: "{count} changes: {jobs}"
       html: true
       method: smtp
       smtp:
         host: email-smtp.us-west-2.amazonaws.com  # (edit accordingly)
         user: ABCDEFGHIJ1234567890  # (edit accordingly)
         port: 587  # (25 or 465 also work)
         starttls: true
         auth: true
         insecure_password: "this_is_my_secret_password"  # (edit accordingly)


.. _gmail:

Gmail example
^^^^^^^^^^^^^
.. important::
   The functionality described below is available only on Google Workspace and Google Cloud Identity accounts, but not
   on regular @gmail.com accounts, because as of "May 30, 2022 Google no longer supports the use of third-party apps or
   devices which ask you to sign in to your Google Account using only your username and password". You can still use a
   @gmail account address to send emails using the Amazon Simple Email Service (see above).

.. warning::
   You **do not want to do this with your primary Google account**, but rather set up a separate one just for
   sending mails from :program:`webchanges` and similar programs. Allowing less secure apps and storing the password
   (even if it's in the Keychain) is not good security practice for your primary account. You have been warned!

First configure your Google Workspace or Google Cloud Identity account to allow for "less secure" (password-based)
apps to login:

#. Go to https://myaccount.google.com/lesssecureapps
#. Turn Allow less secure apps access ON

For more information, see `Google's help <https://support.google.com/accounts/answer/6010255>`__. This setting may not
be available if the account administrator turned the functionality off and you therefore cannot use this functionality.

Then configure these directives as follows:

.. code-block:: yaml

   report:
     tz: null  # or whatever you want it to be
     email:
       enabled: true  # don't forget to set this to true! :)
       from: my_programs@googleworkspacedomain.com  # (edit accordingly; don't use your primary account for this!!)
       to: your.destination@example.org  # The email address of where want to receive reports
       subject: "[webchanges] {count} changes: {jobs}"
       html: true
       method: smtp
       smtp:
         host: smtp.gmail.com
         user: my_programs@googleworkspacedomain.com  # (edit accordingly; don't use your primary account for this!!)
         port: 587
         starttls: true
         auth: true
         insecure_password: "this_is_my_secret_password"  # (edit accordingly)

.. _sendmail:

sendmail
~~~~~~~~

Calls the external `sendmail <https://www.proofpoint.com/us/products/email-protection/open-source-email-solution>`__
program (linux only), which must already be installed and configured.

Optional packages
~~~~~~~~~~~~~~~~~
If using a Keychain to store the password, you also need to:

* Install the ``safe_password`` :ref:`optional package <optional_packages>` as per below;
* Install all the dependencies of the ``keyring`` package as per documentation `here
  <https://pypi.org/project/keyring/>`__;
* Configure the ``keyring`` package to use the Keychain backend being used in your system following the instructions
  on the same page.

.. code-block:: bash

   pip install --upgrade webchanges[safe_password]

.. versionchanged:: 3.10
   Can specify multiple "to" email addresses.



.. _ifttt:

IFTTT
-----
Sends a :ref:`text report <text>` as an IFTTT event.

To configure IFTTT events, you need to retrieve your key from `<https://ifttt.com/maker_webhooks/settings>`__.

The URL is shown in "Account Info" and has the following format:

.. code::

   https://maker.ifttt.com/use/{key}

In this URL, ``{key}`` is your API key. The configuration should look like this (you can pick any event name you want):

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     ifttt:
       enabled: true  # don't forget to set this to true! :)
       key: aA12abC3D456efgHIjkl7m
       event: event_name_you_want

The event will contain three values in the posted JSON:

* ``value1``: The type of change (``new``, ``changed``, ``unchanged`` or ``error``)
* ``value2``: The name of the job (``name`` directive in ``jobs.yaml``)
* ``value3``: The location of the job (``url`` or ``command`` directive in ``jobs.yaml``)

These values will be passed on to the Action in your Recipe.



.. _mailgun:

Mailgun
-------
Sends a :ref:`text report <text>` via email using the commercial `Mailgun <https://www.mailgun.com/>`__ service.


Sub-directives
~~~~~~~~~~~~~~
* ``domain``: The domain.
* ``api_key``: API key (see `here
  <https://help.mailgun.com/hc/en-us/articles/203380100-Where-Can-I-Find-My-API-Key-and-SMTP-Credentials->`__).
* ``from_name``: Sender's name.
* ``from_mail``: Sender's email address.
* ``to``: Recipient's email address.
* ``subject``: The subject line. Use ``{count}`` for the number of reports, ``{jobs}`` for the title of jobs
  reported, and {jobs_files} for a space followed by the name of the jobs file(s) used within parenthesis, stripped
  of preceding ``jobs-``, if not using the default ``jobs.yaml``. Default: ``[webchanges] {count}
  changes:{jobs_files} {jobs}``.
* ``region`` (optional): The code of the region if different from the US (e.g. ``eu``).



.. _matrix:

Matrix
------
Sends a :ref:`text <text>` or :ref:`Markdown <markdown>` report as a notification through the `Matrix protocol
<https://matrix.org>`__.

You first need to register a Matrix account for the bot on any home server.

You then need to acquire an access token and room ID, using the following instructions adapted from `this
guide <https://t2bot.io/docs/access_tokens/>`__:

#. Open `Riot.im <https://riot.im/app/>`__ in a private browsing window
#. Register/Log in as your bot, using its user ID and password.
#. Set the display name and avatar, if desired.
#. In the settings page, select the "Help & About" tab, scroll down to the bottom and click Access Token:
   <click to reveal>.
#. Copy the highlighted text to your configuration.
#. Join the room that you wish to send notifications to.
#. Go to the Room Settings (gear icon) and copy the *Internal Room ID* from the bottom.
#. Close the private browsing window **but do not log out, as this invalidates the Access Token**.

Here is a sample configuration:

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     matrix:
       enabled: true  # don't forget to set this to true! :)
       homeserver: https://matrix.org
       access_token: "YOUR_TOKEN_HERE"
       room_id: "!roomroomroom:matrix.org"

You will probably want to use the following configuration for the ``markdown`` report, if you intend to post change
notifications to a public Matrix room, as the messages quickly become noisy:

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     markdown:
       enabled: true  # don't forget to set this to true! :)
       markdown: false
       details: false
       footer: false
       minimal: true



.. _prowl:

Prowl
-----
Sends a :ref:`text report <text>` through the `Prowl <https://www.prowlapp.com>`__ push notification service (iOS only).

To achieve this, you should register a new Prowl account, and have the Prowl application installed on your iOS device.

To create an API key:

#. Log into the Prowl website at https://www.prowlapp.com/api_settings.php.
#. If needed, navigate to the "API Keys" tab.
#. Scroll to the "Generate a new API key" section.
#. Give the key a note that will remind you you've used it for this service.
#. Press "Generate Key".
#. Copy the resulting key.

Here is a sample configuration:

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     prowl:
       enabled: true  # don't forget to set this to true! :)
       api_key: "<your api key here>"
       priority: 2
       application: webchanges example
       subject: "{count} changes: {jobs}"

The "subject" field will be used as the name of the Prowl event. The application field is prepended to the event and
shown as the source of the event in the Prowl App.

Sub-directives
~~~~~~~~~~~~~~
* ``api_key``: The API key.
* ``application``: The application.
* ``priority``: The priority (integer). Default: 0
* ``subject``: The subject line. Use ``{count}`` for the number of reports, ``{jobs}`` for the title of jobs
  reported, and {jobs_files} for a space followed by the name of the jobs file(s) used within parenthesis, stripped
  of preceding ``jobs-``, if not using the default ``jobs.yaml``. Default: ``[webchanges] {count}
  changes:{jobs_files} {jobs}``.


.. versionadded:: 3.0.1



.. _pushbullet:

Pushbullet
----------
Sends a :ref:`text report <text>` through  the `Pushbullet <https://www.pushbullet.com>`__ notification service.

Pushbullet notifications are configured similarly to :ref:`Pushover`. You will need to add to the configuration your
Pushbullet Access Token, which you can generate at https://www.pushbullet.com/#settings.

Required packages
~~~~~~~~~~~~~~~~~
To use this report you need to install :ref:`optional packages <optional_packages>`. Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[pushbullet]

Sub-directives
~~~~~~~~~~~~~~
* ``api_key``: The API key.



.. _pushover:

Pushover
--------
Sends a :ref:`text report <text>` through  the `Pushover <https://pushover.net>`__ notification service.

You can configure webchanges to send real time notifications about changes via `Pushover <https://pushover.net>`__.
Firsly, make sure you have the required packages installed (see below). Then edit your configuration file
(``webchanges --edit-config``) and enable pushover. You will also need to add to the config your Pushover user key
and a unique app key (generated by registering webchanges as an application on your `Pushover account
<https://pushover.net/apps/build>`__.

You can send to a specific device by using the device name, as indicated when you add or view your list of devices in
the Pushover console. For example ``device: MyPhone``, or ``device: MyLaptop``. To send to *all* of your devices,
set ``device: null`` in your config (``webchanges --edit-config``) or leave out the device configuration completely.

Setting the priority is possible via the ``priority`` config option, which can be ``lowest``, ``low``, ``normal``,
``high`` or ``emergency``. Any other setting (including leaving the option unset) maps to ``normal``.

Required packages
~~~~~~~~~~~~~~~~~
To use this report you need to install :ref:`optional packages <optional_packages>`. Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[pushover]

Sub-directives
~~~~~~~~~~~~~~
* ``app``: The application.
* ``user``: The user.
* ``device``: The device. Default: Null.
* ``sound``: The sound (string). Default: ``spacealarm``.
* ``priority``: The priority (string). Default: ``normal``.


.. _run_command:

run_command
-----------
Runs a command on your local system supplying a :ref:`text report <text>`.

Any text in the command that matches the keywords below will be substituted as follows:

+------------------+------------------------------------------------------------------------------------+
| Text in command  | Replacement                                                                        |
+==================+====================================================================================+
| ``{count}``      | The number of reports                                                              |
+------------------+------------------------------------------------------------------------------------+
| ``{jobs}``       | The titles of the jobs reported                                                    |
+------------------+------------------------------------------------------------------------------------+
| ``{text}``       | The report in text format                                                          |
+------------------+------------------------------------------------------------------------------------+

For example, in Windows we can make a MessageBox pop up:

.. code-block:: yaml

   report:
     tz: null  # or whatever you want it to be
     run_command:
       enabled: true  # don't forget to set this to true! :)
       command: start /MIN PowerShell -Command "Add-Type -AssemblyName PresentationFramework;[System.Windows.MessageBox]::Show('{count} changes: {jobs}\n{text}')"

All environment variables are preserved and the following ones added:

+------------------------------------+------------------------------------------------------------------+
| Environment variable               | Description                                                      |
+====================================+==================================================================+
| ``WEBCHANGES_REPORT_CONFIG_JSON``  | All report parameters in JSON format                             |
+------------------------------------+------------------------------------------------------------------+
| ``WEBCHANGES_CHANGED_JOBS_JSON``   | All parameters of changed jobs in JSON format                    |
+------------------------------------+------------------------------------------------------------------+

If the command generates an error, the output of the error will be reported in the first line(s).

.. versionadded:: 3.8
.. versionchanged:: 3.9
   Added environment variable ``WEBCHANGES_CHANGED_JOBS_JSON``



.. _stdout:

stdout
------
Displays a :ref:`text report <text>` on stdout (the console).

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``color``: Uses color (green for additions, red for deletions) (true/false).



.. _telegram:

Telegram
--------
Sends a :ref:`Markdown report <markdown>` to Telegram using its `Bot API <https://core.telegram.org/bots/api>`__.

Groups
~~~~~~
A Telegram `group <https://telegram.org/tour/groups>`__ is the standard method used to receive notifications from
:program:`webchanges`. To create one, from your Telegram app chat up `BotFather
<https://core.telegram.org/bots#6-botfather>`__ (New Message, Search, “BotFather”),
then say ``/newbot`` and follow the instructions. Eventually it will tell you the bot's unique authentication token
(along the lines of ``110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw``); add it to your configuration file (run
``webchanges --edit-config``) as below, and save the file.

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     telegram:
       enabled: true  # don't forget to set this to true! :)
       bot_token: "110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"  # replace with your bot's token
       chat_id: ""  # empty for now

Next click on the link of your chat bot (starts with \https://t.me/) and, on the new screen, click on start (which will
send the message ``/start``) and enter any text ("Hello" is fine). Then run ``webchanges --telegram-chats``, which
will list the group(s) the bot is involved with as well as their unique identifier(s). Enter the identifier(s) of the
group(s) you want to be notified into the configuration file (run ``webchanges --edit-config``) as ``chat_id``:

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     telegram:
       enabled: true  # don't forget to set this to true! :)
       bot_token: "110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"  # replace with your bot's token
       chat_id: 88888888  # the chat id where the messages should be sent
       silent: false  # set to true to receive a notification without any sound

You may add multiple chat IDs as a YAML list:

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     telegram:
       enabled: true  # don't forget to set this to true! :)
       bot_token: "110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"  # replace with your bot's token
       chat_id:
         - 11111111  # positive chat IDs are private groups
         - -22222222  # negative chat IDs are public groups
       silent: true  # set to false to receive a notification with sound

.. note::

   Before adding a group to :program:`webchanges`, make sure that it has at least one message in it.

.. hint::

   Public groups have chat IDs starting with a ``-`` (negative) sign; make sure you don't leave this out by mistake!

Channels
~~~~~~~~
To notify a Telegram `channel <https://telegram.org/tour/channels>`__ of which the bot is admin of, enter the the
username of the channel (the text after \https://t.me/s/, prefixed by an @) as a ``chat_id``, like this:

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     telegram:
       enabled: true  # don't forget to set this to true! :)
       bot_token: "110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"  # replace with your bot's token
       chat_id:
         - "@channelusername"  # replace with your channel's username

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``silent``: Receive a notification without any sound (true/false). Default is false.


.. versionchanged:: 3.7
   Switched from the ``text`` to the ``markdown`` report type.

.. versionadded:: 3.7
   ``silent`` sub-directive.



.. _webhook:

Webhook (Slack, Mattermost etc.)
--------------------------------
Sends a :ref:`text <text>` or :ref:`Markdown <markdown>` report to services such as Slack, Mattermost etc. using a
webhook.

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     webhook:
       enabled: true  # don't forget to set this to true! :)
       webhook_url: https://hooks.slack.com/services/T50TXXXXXU/BDVYYYYYYY/PWTqwyFM7CcCfGnNzdyDYZ

``webhook`` uses the :ref:`text report <text>` type unless the sub-directive ``markdown: true`` is present, in
which case it uses the :ref:`Markdown report <markdown>`.

Slack
~~~~~
To set up Slack, create a new Slack app in the workspace where you want to post messages, toggle **Activate Incoming
Webhooks** on in the Features page, click **Add New Webhook to Workspace**, pick a channel that the app will post to,
then click **Authorize** (see `here
<https://slack.com/intl/en-sg/help/articles/115005265063-Incoming-webhooks-for-Slack>`__). Copy the webhook URL and
paste it into the configuration as seen above.

Mattermost
~~~~~~~~~~
To set up Mattermost follow the documentation `here <https://docs.mattermost.com/developer/webhooks-incoming.html>`__
to generate a webhook URL and paste it into the configuration as such (note that Mattermost prefers markdown so we're
setting ``markdown: true``):

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     webhook:
       enabled: true  # don't forget to set this to true! :)
       webhook_url: http://{your-mattermost-site}/hooks/xxx-generatedkey-xxx
       markdown: true  # Mattermost prefers markdown

Sub-directives
~~~~~~~~~~~~~~
* ``webhook_url`` (required): The webhook URL.
* ``markdown``: Whether to send Markdown instead of plain text (true/false). Default is false.
* ``max_message_length``: The maximum length of a message in characters. Default is 40,000.
* ``rich_text``: Whether to send preformatted rich text (for Slack) (true/false). Default is false.

.. versionchanged:: 3.0.1
   Renamed from ``slack`` to ``webhook`` and added the ``markdown`` sub-directive.


.. _xmpp:

XMPP
----
Sends a :ref:`text report <text>` using the XMPP protocol.

This reporter should be only used with an XMPP account that is exclusively used for :program:`webchanges`; create a
new one for this purpose.

Here is a sample configuration:

.. code:: yaml

   report:
     tz: null  # or whatever you want it to be
     xmpp:
       enabled: true  # don't forget to set this to true! :)
       sender: "BOT_ACCOUNT_NAME"
       recipient: "YOUR_ACCOUNT_NAME"

You can store your password securely on a Keychain if you have one installed by running ``webchanges --xmpp-login``;
this also requires having the optional ``safe_password`` dependencies installed (see below). However, be aware that
the use of safe password and ``keyring`` won't allow you to run :program:`webchanges` unattended (e.g. from a
scheduler), so you can save the password in the ``insecure_password`` directive in the XMPP config instead:

.. code-block:: yaml

   report:
     tz: null  # or whatever you want it to be
     xmpp:
       enabled: true  # don't forget to set this to true! :)
       sender: "BOT_ACCOUNT_NAME"
       recipient: "YOUR_ACCOUNT_NAME"
       insecure_password: "this_is_my_secret_password"

As the name says, storing the password as plaintext in the configuration is insecure and bad practice, yet for an
account that only sends these reports this might be a low-risk way.

Required packages
~~~~~~~~~~~~~~~~~
To run jobs with this reporter, you need to install :ref:`optional packages <optional_packages>`. Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[xmpp]

Optional packages
~~~~~~~~~~~~~~~~~
If using a Keychain to store the password, you also need to:

* install the ``safe_password`` :ref:`optional package <optional_packages>` as per below,
* install all the dependencies of the ``keyring`` package as per documentation `here
  <https://pypi.org/project/keyring/>`_,
* configure the ``keyring`` package to use the keychain backend you're using in your system following the instructions
  on the same page.

.. code-block:: bash

   pip install --upgrade webchanges[safe_password]
