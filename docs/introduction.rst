.. _introduction:

============
Introduction
============
:program:`webchanges` monitors the output of web sources (or of commands on your computer) and issues a "report" when
it finds changes. Specifically, every time you run :program:`webchanges`, it:

#. For each "job":

  #. Retrieves the output from the source (data);
  #. (optional) Filters and transforms it;
  #. Compares it with the version saved from the previous run, producing a "diff" report if it finds any changes;
  #. (optional) Filters and transforms the diff report;

#. Displays such reports (default), if any, and/or sends it via one or more methods such as email;
#. Saves the output to be used the next time it is run.


:ref:`Jobs`
-----------
Each source of data to be monitored (URL or command) is a "job".

The instructions for each such job are contained in a file in the :ref:`YAML format <yaml_syntax>` called ``jobs.yaml``
and located in the following directory:

* Linux: ``~/.config/webchanges``
* MacOS: ``~/Library/Preferences/webchanges``
* Windows: ``%USERPROFILE%/Documents/webchanges`` (the webchanges folder within your Documents folder)

It can be edited with any text editor or using the following command:

.. code:: bash

   webchanges --edit

.. hint::

   If you use this command and get an error, set your ``$EDITOR`` (or ``$VISUAL``) environment
   variable in your shell to your editor (including the path if needed) using a command such as ``export EDITOR=nano``.

A different file can be specified with the ``--jobs`` command line argument as follows:

.. code:: bash

   webchanges --jobs mycustomjobs.yaml --edit

For a summary of the YAML syntax, see :ref:`here <yaml_syntax>`. Some gotchas include that indentation is mandatory,
spaces (and not tabs!) must be used for such indentation, and there must be a space after a colon separating a key from
its value.

For examples of jobs, see :ref:`here <examples>`.

The minimum configuration necessary for :program:`webchanges` to work is a single ``url`` directive (for web
resources) or ``command`` directive (for the output of a shell command):

.. code-block:: yaml

   url: https://example.com/

If you have multiple sources to monitor, i.e. multiple "jobs", separate each with a line of three dashes
(``---``):

.. code-block:: yaml

   url: https://example.com/
   ---
   url: https://example.com/page2
   ---
   command: dir

By default, the content is downloaded as-is. However, certain webpages need for their JavaScript to be run in order
for their content to be rendered; in this case either find the API used by the JavaScript to get the data you care
about directly from the source and monitor that API (preferred), or add the directive ``use_browser: true`` to use a
virtual (`headless`) Google Chrome browser to render the JavaScript. This requires additional installations; see
:ref:`here <use_browser>` for more information.

.. code-block:: yaml

   url: https://example.com/
   use_browser: true

You can add a ``name`` to a job to help you identify what you're monitoring, but :program:`webchanges` will
automatically try to use a webpage's title if you don't do so:

.. code-block:: yaml

   name: Example
   url: https://example.com/

You can enter remarks in your YAML configuration file by using ``#``:

.. code-block:: yaml

   # I am monitoring this site because I expect it to change for the better
   name: Sample  # Here I have an end of line remark
   url: https://example.com/

Finally, you have a choice of many and many directives to finely control the data acquisition step; all directives
are listed and explained :ref:`here <jobs>`.


:ref:`Filters`
--------------
Once :program:`webchanges` has collected the raw output, you may transform it to increase its utility. You use the
``filter`` directive to activate one or more :ref:`filters <filters>` to:

* Select HTML or (XML) elements: ``css``, ``xpath``, ``element-by-class``, ``element-by-id``, ``element-by-style``,
  ``element-by-tag``;
* Extract text from HTML: ``html2text``;
* Make HTML more readable: ``beautify``;
* Extract text from PDF: ``pdf2text``;
* Extract text from images: ``ocr``;
* Extract ASCII text from JSON: ``jq``;
* Make JSON more readable: ``format-json``;
* Make XML more readable: ``format-xml`` or ``pretty-xml``;
* Make iCal more readable: ``ical2text``;
* Make binary readable: ``hexdump``;
* Just detect if anything changed: ``sha1sum``;
* Filter and/or edit text: ``keep_lines_containing``, ``delete_lines_containing``, ``re.sub``, ``strip``, ``sort``,
  ``remove_repeated`` and ``reverse``;
* Run any custom script or program: ``execute``.

If all you want to do is monitoring the displayed text and links of a website, this job will do it:

.. code-block:: yaml

    url: https://example.com/
    filters:
      - html2text:  # notice the 2 empty spaces before the hyphen and the colon at the end

Filters can be chained. As an example, after retrieving an HTML document by using the ``url`` directive, you
can extract a selection with the ``xpath`` filter, convert it to text with ``html2text`` with specific settings, extract
only lines matching a specific regular expression with ``keep_lines_containing``, and sort the result with ``sort``:

.. code-block:: yaml

    name: Sample webchanges job definition
    url: https://example.com/
    https_proxy: http://user:password@example.net:8080
    max_tries: 2
    filter:
      - xpath: //section[@role="main"]
      - html2text:
          method: html2text
          inline_links: false
          ignore_links: true
          ignore_images: false
          pad_tables: true
      - keep_lines_containing: lines I care about
      - sort:
    ---

Filters are explained :ref:`here <filters>`.


:ref:`Differ <differs>` (comparison)
------------------------------------
Once all filters (if any) are applied, :program:`webchanges` automatically performs a comparison between the filtered
data collected in this run with the one saved from a prior run, by default computing a *diff* in the `unified format
<https://en.wikipedia.org/wiki/Diff#Unified_format>`__ ("unified *diff*"). Other comparison methods are avaialable,
such as deepdiff for JSON or XML, HTML table, and Gen AI summarization.

Differs are explained :ref:`here <differs>`.


:ref:`Diff filters <diff_filters>`
----------------------------------
After the comparison is generated, you can apply **any** of the filters above to the *diff itself* using
``diff_filter``, and/or one of the additional ones (work with unified format-diff only):

* To only show lines representing additions: ``additions_only``;
* To only show lines representing deletions: ``deletions_only``.

Diff filters are explained :ref:`here <diff_filters>`.


:ref:`Reports`
--------------
The *diffs* from all jobs are collected and turned into (a) report(s), which can be of one or more of the ``text``,
``html`` and/or ``markdown`` formats. You can select settings to tailor what elements are included in the report.

Reports are explained :ref:`here <reports>`.


:ref:`Reporters`
----------------
Finally, the report(s) is (are) *reported* using a reporter, by default displaying it on the ``stdout`` console, but you
can add (or change to) one or more reporters to:

* Display it on the default web browser: ``browser``;
* Send it to a **Discord** channel: ``discord``;
* Send it via **email** (SMTP or sendmail): ``email``;
* Send it via **IFTTT**: ``ifttt``;
* Send it via email using the external **Mailgun** program: ``mailgun``;
* Send it to a room using the **Matrix** protocol: ``matrix``;
* Send it via **prowlapp.com**: ``prowl``;
* Send it via **pushbullet**.com: ``pushbullet``;
* Send it via **pushover**.net: ``pushover``;
* Run a command on the local system to take care of the notification: ``run_command``;
* Display it on stdout (the text console): ``stdout``;
* Send it via **Telegram**: ``telegram``;
* Send it to a **Slack** or **Mattermost** channel using the service's webhook: ``webhook``;
* Send it as a message using the Extensible Messaging and Presence Protocol (**XMPP**): ``xmpp``.

Reporters are explained :ref:`here <reporters>`.


Scheduling
----------
:program:`webchanges` will check for changes every time you run it, but does not include a scheduler. We recommend
using a system scheduler to automatically run :program:`webchanges` periodically:

- On Linux (or macOS), you can use ``cron`` (if you have never used cron before, see
  `here <https://www.computerhope.com/unix/ucrontab.htm>`__); `crontab.guru <https://crontab.guru>`__ will build a
  schedule expression for you.
- On macOS, `Apple recommends <https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/
  BPSystemStartup/Chapters/ScheduledJobs.html>`__ to use `launchd
  <https://developer.apple.com/documentation/xpc/launchd>`__.
- On Windows, you can use the built-in `Windows Task Scheduler
  <https://en.wikipedia.org/wiki/Windows_Task_Scheduler>`__.


Installing on Windows
---------------------
* Install (or upgrade to) the `latest version of Python <https://www.python.org/downloads/>`__;
* Open a command window by pressing ``⊞ Win`` + ``R`` together, typing ``cmd``, and pressing Enter (or clicking on OK);
* Type ``py -m pip install webchanges`` (or ``py -m pip install webchanges[browser]`` etc.) and press Enter;

  - This will download :program:`webchanges` and install it;
* After this, :program:`webchanges` should be available as a command (type ``webchanges --version`` to check);
* Follow this documentation to configure the program :program:`webchanges`.

.. tip::
  If you receive ``*** fatal error - Internal error: TP_NUM_C_BUFS too small: 50`` when running :program:`webchanges`
  in Windows, try installing python-magic-bin by running ``pip install python-magic-bin``.


Installing on Android
---------------------
:program:`webchanges` is not made to run on your phone/tablet directly, but rather on a server (including one in the
cloud), and can be configured to send notifications (":ref:`reports <reports>`") to your Android device. However,
if you want to run :program:`webchanges` on an Android device as if it were a server, you *may* be able to do so by
tinkering with `Termux <https://termux.dev/>`__.


Installing as a Docker container
--------------------------------
:program:`webchanges` can be run as a Docker container. Please see `here
<https://github.com/yubiuser/webchanges-docker>`__ for one such implementation.
