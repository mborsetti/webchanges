.. _upgrading:


.. role:: underline
    :class: underline

.. role:: additions
    :class: additions

.. role:: deletions
    :class: deletions

=======================
Upgrading from urlwatch
=======================
:program:`webchanges` reads your :program:`urlwatch` jobs and configuration files as they are, so you keep every job
you have built and gain clearer reports, AI summaries, image and structured-data diffs, and an HTTP client that gets
past bot walls. It began as a fork of :program:`urlwatch` 2.21 and has been developed independently since 2020, while
staying compatible with :program:`urlwatch`'s files: most setups need no edits at all.

For a feature-by-feature table, see the `webchanges vs urlwatch comparison <_static/webchanges-vs-urlwatch.html>`__.


Why switch
----------

Reports you can read at a glance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* HTML reports keep the page's formatting (**bold**, *italics*, :underline:`underlining`, headers, bulleted lists and
  indentation) and its links stay clickable.
* :additions:`Added` and :deletions:`deleted` lines are marked with color and strikethrough, readable in dark mode
  and in email clients that strip stylesheets, such as Gmail.
* Long lines wrap instead of being cut off.
* The :ref:`table <table_diff>` differ shows changes side by side, and the :ref:`wdiff <wdiff_diff>` differ highlights
  the words that changed within a line.
* The ``telegram`` reporter keeps links, bold, italics, underlining and strikethrough.

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_1.png
    :width: 504

|

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_3.png
    :width: 504

Changes worth being told about
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* The :ref:`ai_google <ai_google_diff>` differ summarizes a long diff (a contract, a policy, terms of service) in a
  paragraph of plain language, using Google's Gemini.
* The :ref:`image <image_diff>` differ watches images and reports an image with the differences highlighted.
* The :ref:`deepdiff <deepdiff_diff>` differ compares JSON, YAML and XML element by element, so that reordered list
  items, reformatting or noise in the last decimal don't raise false alarms.
* :ref:`additions_only <additions_only>` reports only what was added, such as new items in a list, and
  ``deletions_only`` only what was removed.

Sites that block urlwatch
~~~~~~~~~~~~~~~~~~~~~~~~~
* Choose the HTTP client per job with :ref:`http_client`: ``httpx`` (with HTTP/2), ``requests``, or ``curl_cffi``,
  which presents the TLS fingerprint of a real browser to get past Cloudflare, Akamai and similar bot walls.
* :ref:`Browser jobs <use_browser>` run Chrome, Edge, Firefox or WebKit through Playwright, can wait for a URL, a
  selector or a JavaScript condition, block images and other resources, and can attach to a browser that is already
  running (:ref:`connect_over_cdp`).
* :ref:`same_site_delay` spaces out jobs that hit the same site, to stay clear of rate limits.

Fewer false alarms
~~~~~~~~~~~~~~~~~~
* :ref:`empty_as_error` treats an empty response as a transient error instead of reporting the page's content
  disappearing and then reappearing.
* :ref:`suppress_repeated_errors` reports an error once, not on every run, and :ref:`suppress_error_ended` skips the
  report that an error has ended when the content is unchanged.
* ``ignore_connection_errors``, ``ignore_timeout_errors``, ``ignore_http_error_codes`` and the other ``ignore_*``
  directives also work for browser jobs.

Snapshots you can trust
~~~~~~~~~~~~~~~~~~~~~~~
* Snapshots are saved only after the reports have been sent, so a crash or a reporter error no longer loses a change.
* The default SQLite database is indexed and compressed and keeps the latest 4 snapshots of each job (set with
  :ref:`--max-snapshots <max-snapshots>`), so it no longer grows without limit.
* Undo mistakes with :ref:`--rollback-database <rollback-database>` and :ref:`--delete-snapshot <delete-snapshot>`.

Tools for maintaining your jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* :ref:`--errors <error>` runs every job and lists those that fail or whose filters return nothing.
* :ref:`--test-differ <test-differ>` replays the diffs of every snapshot saved, and :ref:`--test <test>` without a
  job checks your jobs and configuration files for errors.
* Editors such as VS Code autocomplete and validate ``jobs.yaml`` and ``config.yaml`` from the JSON Schemas that
  :program:`webchanges` installs next to them.
* The ``!env`` tag reads secrets from :ref:`environment variables <environment_variables>` instead of storing them in
  your files.
* Send different jobs to different destinations by configuring a reporter :ref:`several times <multiple_reporters>`,
  each with its own :ref:`tags <reporter_tags>`, and open a GitHub issue with the :ref:`github_issue` reporter.

Actively maintained
~~~~~~~~~~~~~~~~~~~
Releases ship regularly, supporting Python 3.12 to 3.15 (including the free-threaded build), and every release is
tested on Linux, macOS and Windows.


Switching from urlwatch
-----------------------
1. Confirm that the latest release of :program:`urlwatch` (2.29) runs your jobs without errors.
   :program:`webchanges` reads the same files, so fix any error there first.

2. Install :program:`webchanges`. If any of your jobs uses a browser (it has a ``navigate`` directive), install the
   ``use_browser`` extra:

   .. code-block:: bash

      uv pip install webchanges               # or: uv pip install webchanges[use_browser]

   Browser jobs use Google Chrome; if it is not installed, run ``webchanges --install-chrome``.

3. Check your files:

   .. code-block:: bash

      webchanges --test                        # check the jobs and configuration files for errors

   This first run copies your :program:`urlwatch` files into :program:`webchanges`' own directory: ``urls.yaml``
   becomes ``jobs.yaml``, ``urlwatch.yaml`` becomes ``config.yaml``, ``hooks.py`` keeps its name, and the snapshot
   database ``cache.db`` becomes ``snapshots.db``. :program:`webchanges` looks for them where :program:`urlwatch`
   keeps them (``~/.urlwatch``, or else its default directories), and copies only what it doesn't have yet. The
   originals are left untouched, so :program:`urlwatch` keeps working and you can switch back at any time.

4. Fix what ``--test`` reports, using :ref:`upgrading_changes`. Renamed directives keep working and only print a
   deprecation warning, which you can address when convenient.

5. Run :program:`webchanges`. On the first run it converts its copy of :program:`urlwatch`'s snapshot database to its
   own format, which needs the ``minidb`` package for this one conversion:

   .. code-block:: bash

      uv pip install minidb                     # needed once, for the conversion
      webchanges                                # run all jobs

   You can uninstall ``minidb`` afterwards. Don't point ``--database`` at :program:`urlwatch`'s legacy ``cache.db``
   instead of letting :program:`webchanges` upgrade it into its own separate copy.

6. All of the existing files are kept; if you don't like what you see, you can keep on using :program:`urlwatch`.

If you encounter a problem or have a suggestion, open an issue on `GitHub
<https://github.com/mborsetti/webchanges/issues>`__.


.. _upgrading_changes:

What you may need to change
---------------------------
This section lists every difference, relative to :program:`urlwatch` 2.29, that can require you to edit your files or
change how you run the program.

Changes that stop a job or the run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Change these before your first run. (:program:`webchanges` also rejects any directive it does not recognize, instead
of ignoring it, so that a typo cannot go unnoticed.)

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - In :program:`urlwatch`
     - In :program:`webchanges`
   * - ``urlwatch --tags work home``
     - ``webchanges --tags work,home``: separate tags with commas (see :ref:`tags_cli`).
   * - ``hooks.py`` custom code
     - Replace every ``urlwatch`` import with the same import from ``webchanges``, then adapt your classes to the
       :ref:`hooks API <hooks>`: for example, a filter's ``filter()`` method receives the data's media type and returns
       a ``(data, mime_type)`` tuple, and a job's ``retrieve()`` method returns ``(data, etag, mime_type)``.

Renamed names that still work
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
These names were changed for clarity, or replaced by a more capable equivalent. The old ones keep working (most print a
deprecation warning), so you can update them when convenient:

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - :program:`urlwatch` name
     - :program:`webchanges` name
   * - ``navigate: <URL>``
     - ``url: <URL>`` and ``use_browser: true``
   * - ``useragent: <agent>`` (``navigate`` jobs)
     - A ``User-Agent: <agent>`` header in :ref:`headers`
   * - ``browser: firefox``, ``browser: webkit`` (``navigate`` jobs)
     - ``use_browser: firefox``, ``use_browser: webkit`` (see :ref:`use_browser <use_browser_directive>`)
   * - ``wait_for: <selector>`` (``navigate`` jobs)
     - :ref:`wait_for_selector`: ``<selector>``
   * - ``filter``, ``diff_filter``
     - ``filters``, ``diff_filters``
   * - ``diff_tool: <command>``
     - ``differ:`` with ``name: command`` and ``command: <command>`` (see :ref:`differ`)
   * - ``http_proxy``, ``https_proxy``
     - ``proxy``
   * - ``json: true``
     - ``data_as_json`` (see :ref:`data_as_json`)
   * - ``kind: shell``
     - ``kind: command``
   * - ``stderr: urlwatch`` (``command`` jobs)
     - :ref:`stderr`: ``forward``
   * - ``grep``, ``grepi`` filters
     - ``keep_lines_containing``, ``delete_lines_containing``
   * - ``html2text`` methods ``pyhtml2text``, ``re``
     - ``html2text`` (the default), ``strip_tags``
   * - ``html2text`` method ``lynx``
     - The default method, ignoring ``lynx``'s options. Its text is formatted differently, so the first run reports a
       change; to keep ``lynx``'s output, run it with the :ref:`execute` filter instead
   * - ``job_defaults`` keys ``all``, ``url``, ``browser``, ``shell``
     - ``all_jobs``, ``url_jobs``, ``browser_jobs``, ``command_jobs``
   * - ``--urls``, ``--cache``, ``--gc-cache``
     - ``--jobs``, ``--database``, ``--gc-database``
   * - ``--test-filter``, ``--test-diff-filter``
     - ``--test``, ``--test-differ``
   * - ``--list``
     - ``--list-jobs`` (``--list`` is accepted as an abbreviation)
   * - ``slack`` reporter
     - :ref:`webhook` (same sub-directives)
   * - ``mattermost`` reporter
     - :ref:`webhook` with ``markdown: true``
   * - ``shell`` reporter
     - :ref:`run_command`, which inserts the report into the command line with ``{text}`` instead of sending it on
       standard input
   * - ``gotify`` sub-directive ``title``
     - ``subject``

Behavior that differs
~~~~~~~~~~~~~~~~~~~~~
None of these need an edit, but they change what you see:

* The database format has been upgraded for speed, size, and to hold more detail. To keep using :program:`urlwatch`'s
  database format, run with :ref:`--database-engine minidb <database-engine>` (requires the ``minidb`` package).
* The :ref:`html2text` filter without a ``method`` converts HTML to Markdown, while :program:`urlwatch`'s default
  (``re``) only removed the tags; and its ``html2text`` method uses the Python ``html2text`` package, not the
  ``html2text`` program. Jobs using either report a change on their first run. To get the closest to
  :program:`urlwatch`'s default output, add ``method: strip_tags``.
* The database keeps the latest 4 snapshots of each job. To keep them all, as :program:`urlwatch` does, set
  :ref:`max_snapshots <database_max_snapshots>` to 0 in ``config.yaml`` or run with ``--max-snapshots 0``.
* Jobs in reports are sorted alphabetically by name.
* The ``telegram`` reporter's ``monospace`` sub-directive has no effect, as reports are sent in Markdown; it is
  reported as unrecognized.
* When run from a terminal, ``--enable``, ``--disable`` and ``--delete`` ask for confirmation before rewriting the
  jobs file, which (as in :program:`urlwatch`) loses all its remarks (see :ref:`enable_disable`).
* A job selected on the command line by its URL, command or name must match one job only; if it matches several, the
  error lists them and you select one by its index number instead (see :ref:`job_subset`).
* On Windows with Python 3.12 to 3.14, a ``UnicodeEncodeError`` from a ``command`` job or the ``shellpipe`` filter is
  fixed by running Python in `UTF-8 mode <https://docs.python.org/3/using/windows.html#utf-8-mode>`__ (the default
  from Python 3.15).


Legal
-----
The roots of :program:`webchanges` from code of urlwatch 2.21 dated 30 July 2020 are credited throughout, and its
code is appropriately copyrighted/licensed:

(1) :program:`webchanges`' `main page <https://github.com/mborsetti/webchanges/blob/main/README.rst>`__ reads:

::

   License
   =======

   Released under the `MIT License <https://opensource.org/licenses/MIT>`__ but redistributing modified source code from
   `urlwatch 2.21 <https://github.com/thp/urlwatch/tree/346b25914b0418342ffe2fb0529bed702fddc01f>`__ dated 30 July 2020
   licensed under a `BSD 3-Clause License
   <https://raw.githubusercontent.com/thp/urlwatch/346b25914b0418342ffe2fb0529bed702fddc01f/COPYING>`__. See the
   complete license `here <https://github.com/mborsetti/webchanges/blob/main/LICENSE.md>`__.

(2) Each file with code contains this remark at the top:

::

   # The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

Note: There is no requirement anywhere in law to spam the entire 61-line, 465 words license text on Every. Single.
File. In. Every. Single. Directory; the above notice is amply sufficient.

(3) The `license file <https://github.com/mborsetti/webchanges/blob/main/LICENSE.md>`__ reads:

::

   This software redistributes source code of release 2.21 of urlwatch
   https://github.com/thp/urlwatch/tree/346b25914b0418342ffe2fb0529bed702fddc01f of 30 July 2021 which is subject to
   the following copyright notice and license from
   https://raw.githubusercontent.com/thp/urlwatch/346b25914b0418342ffe2fb0529bed702fddc01f/COPYING hereby retained
   and redistributed with the source code (of which this license file is part of), in binary form, and in the
   documentation. The appearance of the name of the author below does not constitute an endorsement or promotion of
   this software by such author.

   Copyright (c) 2008-2020 Thomas Perl <m@thp.io>
   All rights reserved.

   [follows full text of the urlwatch license]

(4) While a significant amount of improvements have been made from urlwatch 2.21, there's no lack of proper and complete
acknowledgement of the package's use of Thomas Perl's code -- in multiple ways, exceeding the required full and explicit
licensing language.
