.. _introduction:

============
Introduction
============
:program:`webchanges` monitors the output of web sources (or of commands on your computer) and issues a 'report' when
it finds changes. Specifically, every time you run :program:`webchanges`, it:

#. Retrieves the output from the source;
#. (optional) Filters and transforms it;
#. Compares it with the version saved from the previous run, producing a "diff" report if it finds any changes;
#. (optional) Filters and transforms the diff report;
#. Displays such report (default) and/or sends it via one or more methods such as email;
#. Saves the output to be used the next time it is run.


:ref:`Jobs`
-----------
Each web source or command to be monitored is a "job".

The instructions for each such job are contained in a file in the **:ref:`YAML format <yaml_syntax>`** called
``jobs.yaml`` and located in the following directory:

* Linux: ``~/.config/webchanges``
* MacOS: ``~/Library/Preferences/webchanges``
* Windows: ``%USERPROFILE%/Documents/webchanges`` (the webchanges folder within your Documents folder)

It can be edited with any text editor or by the following command:

.. code:: bash

   webchanges --edit

.. hint::

   If you use this command and get an error, set your ``$EDITOR`` (or ``$VISUAL``) environment
   variable in your shell to the path to your editor with a command such as ``export EDITOR=nano``.

For a summary of the YAML syntax, see :ref:`here <yaml_syntax>`.

For examples of jobs, see :ref:`here <watching_sites>`.

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
about and monitor that API (preferred), or add the directive ``use_browser: true`` to use a virtual browser to render
the JavaScript. This requires additional installations and uses many resources; see :ref:`here <use_browser>` for more
information.

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
   name: Sample  # One more remark
   url: https://example.com/

Finally, you have a choice of many and many options to finely control the data acquisition; see :ref:`here <jobs>`.


:ref:`Filters`
--------------
Once you have collected the output, you may transform it to increase its utility. You use the ``filter`` directive to
activate one or more :ref:`filters <filters>` to:

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

If all you're doing is monitoring the displayed text and links of a website, this filter will do it:

.. code-block:: yaml

    url: https://example.com/
    filters:
      - html2text:  # notice the 2 empty spaces before the hyphen and the colon at the end

Filters can be chained. As an example, after retrieving an HTML document by using the ``url`` directive, you
can extract a selection with the ``xpath`` filter, convert it to text with ``html2text``, extract only lines matching
a specific regular expression with ``keep_lines_containing``, and sort the result with ``sort``:

.. code-block:: yaml

    name: Sample webchanges job definition
    url: https://example.com/
    https_proxy: http://user:password@example.net:8080
    max_tries: 2
    filter:
      - xpath: //section[@role="main"]
      - html2text:
          method: html2text
          unicode_snob: true
          body_width: 0
          inline_links: false
          ignore_links: true
          ignore_images: true
          pad_tables: false
          single_line_break: true
      - keep_lines_containing: lines I care about
      - sort:
    ---

Filters are explained :ref:`here <filters>`.


Comparison
----------
Once all filters (if any) are applied, :program:`webchanges` then automatically performs a comparison between the
filtered data collected in this run with the one saved from a prior run, computing a diff in the `unified format
<https://en.wikipedia.org/wiki/Diff#Unified_format>`__ ('unified diff') (default--can be changed).


:ref:`Diff filters <diff_filters>`
----------------------------------
After the comparison is generated, you can apply *any* of the filters above to the diff itself or one of the
additional diff-specific ones to:

* Only show lines representing additions: ``additions_only``;
* Only show lines representing deletions: ``deletions_only``.

Diff filters are explained :ref:`here <diff_filters>`.

If all you're doing is monitoring the text of a website to see if anything was added, this job definition will do it:

.. code-block:: yaml

    url: https://example.com/
    filters:
      - html2text:  # notice the 2 empty spaces before the hyphen and the colon at the end
    additions_only:


:ref:`Reports`
--------------
This `diff` is turned into a report of one or more of the formats ``text``, ``html`` and ``markdown``. You can
select settings to tailor what elements are included in the report.

Reports are explained :ref:`here <reports>`.


:ref:`Reporters`
----------------
Finally, the report is `reported`, by default displaying it on the ``stdout`` console, but you can add (or change
to) one or more to:

* Display on stdout (the console): ``stdout``;
* Display on the default web browser: ``browser``;
* Send via email (SMTP or sendmail): ``email``;
* Send a message using the Extensible Messaging and Presence Protocol (XMPP): ``xmpp``;
* Send to a **Slack** or **Discord** channel using the service's webhook: ``webhook``;
* Send via Telegram: ``telegram``;
* Send via pushbullet.com: ``pushbullet``;
* Send via pushover.net: ``pushover``;
* Send via IFTTT: ``ifttt``;
* Send to a room using the Matrix protocol: ``matrix``;
* Send via email using the Mailgun service: ``mailgun``;
* Send via prowlapp.com: ``prowl``;
* Run a command on the local system to take care of the notification: ``run_command``.

Reporters are explained :ref:`here <reporters>`.

Scheduling
----------

:program:`webchanges` will check for changes every time you run it, but does not include a scheduler. We recommend
using a system scheduler to automatically run :program:`webchanges` periodically:

- On Linux or macOS, you can use cron (if you have never used cron before, see
  `here <https://www.computerhope.com/unix/ucrontab.htm>`__); `crontab.guru <https://crontab.guru>`__ will build a
  schedule expression for you.
- On Windows, you can use the built-in `Windows Task Scheduler
  <https://en.wikipedia.org/wiki/Windows_Task_Scheduler>`__.
