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

Introduction
------------
You can easily upgrade to **webchanges** from the current version of **urlwatch** using the same job and
configuration files (see `here <https://webchanges.readthedocs.io/en/stable/upgrading.html>`__) and benefit from many
improvements, including:

* :underline:`AI-Powered Summaries`: Summary of changes in plain text using generative AI, useful for long documents
  (e.g. legal);
* :underline:`Image Change Detection`: Monitor changes to images and receive notifications with an image highlighting
  the differences;
* :underline:`Structured Data Monitoring`: Track changes in JSON or XML data on an element-by-element basis;
* :underline:`Improved Documentation`: We've revamped the `documentation <https://webchanges.readthedocs.io/>`__ to make
  implementation easier;
* :underline:`Enhanced HTML Reports`: HTML reports are now much clearer and include:

  * Clickable links!
  * Retention of most original formatting (**bolding / headers**, *italics*, :underline:`underlining`, lists with
    bullets (•), and indentation;
  * :additions:`added` and :deletions:`deleted` lines clearly highlighted with color and strikethrough;
  * Wrapping of long lines (instead of truncation);
  * Improved compatibility with a wider range of HTML email clients, including those that override stylesheets (e.g.,
    Gmail);
  * General legibility improvements.

* :underline:`New Filtering Options`: New filters, like `additions_only
  <https://webchanges.readthedocs.io/en/stable/diff_filters.html#additions-only>`__, which allows you to focus on
  added content without the distraction of deletions;
* :underline:`New Command Line Arguments`: New command-line arguments such as ``--errors``, which helps you identify
  jobs that are no longer functioning correctly;
* :underline:`Increased Reliability and Stability`: Testing coverage has increased by approximately 30 percentage
  points;
* :underline:`Additional Enhancements`: Numerous other additions, refinements, and bug fixes have been implemented.
  For more information, see `here <https://webchanges.readthedocs.io/en/stable/migration.html#upgrade-details>`__.

Example enhancements to HTML reporting:

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_1.png
    :width: 504

|

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_3.png
    :width: 504


Installation
------------
:program:`webchanges` |version| is derived from `urlwatch <https://github.com/thp/urlwatch>`__ and is mostly
backward-compatible with the latest version of :program:`urlwatch`'s job and configuration files.

Upgrading from a :program:`urlwatch` setup is automatic (see more below), and gives you:

* Vastly improved HTML email reporting, including:

  * Links that are `clickable <https://pypi.org/project/webchanges/>`__!
  * Formatting such as **bolding / headers**, *italics*, :underline:`underlining`, list bullets (•) and indentation is
    preserved
  * Use of color (compatible with Dark Mode) and strikethrough to highlight :additions:`added` and :deletions:`deleted`
    lines
  * Correct wrapping of long lines
  * Correct rendering by email clients who override stylesheets (e.g. Gmail)
  * Better HTML-to-text translation with updated defaults for the ``html2text`` filter
  * Other legibility improvements
* Improved ``telegram`` reporter that uses MarkdownV2 and preserves most formatting of HTML sites including clickable
  links, bolding, underlining, italics and strikethrough.
* A more complete use of Playwright  for browsing jobs to render JavaScript (called ``navigate`` in
  :program:`urlwatch`), including:

  * Upgraded browser engine to the latest released version of Google Chrome
  * Higher stability by optimizing of concurrency
  * More flexibility and control with new directives  ``switches``, ``wait_until``, ``ignore_https_errors``,
    ``wait_for_url``, ``wait_for_function``, ``wait_for_selector``, ``wait_for_timeout``, ``user_data_dir``,
    ``initialization_url``, ``initialization_js``, ``block_elements``, ``cookies``,  ``headers``, ``referrer``,
    ``http_proxy``, ``https_proxy``, and ``timeout`` plus the implementation for this type of jobs of the
    ``ignore_connection_errors``, ``ignore_timeout_errors``, ``ignore_too_many_redirects`` and
    ``ignore_http_error_codes`` directives
  * Faster runs due to handling of ETags allowing servers to send a simple "HTTP 304 Not Modified" message when
    relevant
  * A new ``--no-headless`` command line argument to help with debugging

* A new, more efficient indexed database that is smaller, allows for additional functionality such as rollbacks, and
  does not infinitely grow
* *Diffs* (changes) that are no longer lost if :program:`webchanges` is interrupted mid-execution or encounters an
  error with a reporter
* The use of the webpage's title as a job ``name`` if one isn't provided
* The ability to add a job ``note`` for the report
* New filters such as `additions_only <https://webchanges.readthedocs.io/en/stable/diff_filters.html#additions-only>`__,
  which makes it easier to track content that was added without the distractions of the content that was deleted
* A new ``--errors`` command line argument to help catching any problems by listing all jobs that error out or have
  empty data after filters are applied
* The support of Unicode throughout, including in filters and in the jobs and configuration YAML files
* The fixing of the ``format-json`` filter from unexpectedly reordering contents of dictionaries, now controllable by
  the new sub-directive ``sort_keys``
* The ability to undo mistakes by rolling back the database using ``--rollback-database``.
* More reliable releases due to:

  * A 32 percentage point increase in code testing coverage (to ~74%)
  * Completely new continuous integration (CI) and continuous delivery (CD) pipeline (GitHub Actions with pre-commit)
  * Uses of flake8 and doc8 linters and pre-commit checks
  * Code security checks using bandit
  * Type-hinted code checked using mypy
  * Testing on both Linux (Ubuntu) **and** macOS, with Windows 10 x64 to come
* A vast improvement in documentation and error text
* And much more!

Examples:

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_1.png
    :width: 504

|

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_3.png
    :width: 504


How-to
------
If you are using the latest version of :program:`urlwatch`, simply install :program:`webchanges` and run it. It will
find the existing :program:`urlwatch` job and configuration files, and, unless you were still running ``lynx`` or have
custom code (see below), it *should* run just fine as is. It may complain about some directive name being changed for
clarity and other :ref:`deprecations <upgrade_deprecations>`, but you will have time to make the edits if you decide
to stick around!

.. tip:: If running on Windows and are getting ``UnicodeEncodeError``, make sure that you are running Python in UTF-8
   mode as per instructions `here <https://docs.python.org/3/using/windows.html#utf-8-mode>`__.

However, if *any* of your jobs use a browser (i.e. have ``navigate`` or ``use_browser: true``), you **MUST** install
Playwright:

1) Install the new dependencies:

.. code-block:: bash

   pip install --upgrade webchanges[use_browser]

2) (Optional) ensure you have an up-to-date Google Chrome browser:

.. code-block:: bash

   webchanges --install-chrome

If upgrading from :program:`urlwatch` 2.27 or earlier, you can free up disk space if no other packages use Pyppeteer
by, in order:

1) Removing the downloaded Chromium images by deleting the entire *directory* (and its subdirectories) shown by running:

.. code-block:: bash

   python -c "import pathlib; from pyppeteer.chromium_downloader import DOWNLOADS_FOLDER; print(pathlib.Path(DOWNLOADS_FOLDER).parent)"

2) Uninstalling the Pyppeteer package by running:

.. code-block:: bash

   pip uninstall pyppeteer

If you encounter any problems or have any suggestions please open an issue `here
<https://github.com/mborsetti/webchanges/issues>`__ and someone will look into it.

.. note::

   If you are upgrading from an older version of :program:`urlwatch`, before running :program:`webchanges` make
   sure that you can run the latest version of :program:`urlwatch` successfully, having implemented all
   :program:`urlwatch` breaking changes in your job and configuration files.

   For example, per :program:`urlwatch` issue `#600
   <https://github.com/thp/urlwatch/pull/600#issuecomment-753944678>`__

   .. code-block:: yaml

      url: https://example.com/
      filter: html2text

   no longer works in the latest version of :program:`urlwatch`, and therefore in :program:`webchanges`, as all filters
   must be specified as sub-directives like this:

   .. code-block:: yaml

      url: https://example.com/
      filter:
        - html2text:


.. _upgrade_changes:

Upgrade details
---------------
Most everything, except the breaking changes below, *should* work out of the box when upgrading from a
:program:`urlwatch` setup for version 2.29. No changes to the files are made, so that you can switch back whenever you
want.

⚠ Breaking Changes
~~~~~~~~~~~~~~~~~~
Relative to :program:`urlwatch`:

* Must run on Python version 3.9 or higher.
* By default a new much improved database engine is used; run with ``--database-engine minidb`` command line argument to
  preserve backwards-compatibility.
* By default only 4 snapshots are kept with the new database engine, and older ones are purged after every run; run
  with ``--max-snapshots 0`` command line argument to keep the existing behavior (but beware of its infinite database
  growth!).
* The ``html2text`` filter's ``lynx`` method is no longer supported as it was obsoleted by Python packages; use the
  default method instead or, if you must, construct a custom command using the :ref:`execute` filter.
* If you are using the ``shellpipe`` filter and are running in Windows, ensure that Python is set to `UTF-8 mode
  <https://docs.python.org/3/using/windows.html#utf-8-mode>`__ to avoid getting ``UnicodeEncodeError``.
* If you're using a hooks file (e.g. ``hooks.py``), all imports from ``urlwatch`` need to be replaced with identical
  imports from ``webchanges``.
* If you are using the ``slack`` reporter you need to rename it ``webhook`` (unified reporter).
* If you are using browser (``navigate``) jobs, see above for upgrading to Playwright.
* Reporter ``shell`` imitates :program:`webchanges`:'s ``run_command`` and is not supported (use ``run_command``
  reporter instead).

Additions and changes
~~~~~~~~~~~~~~~~~~~~~
Relative to the latest version of :program:`urlwatch`:

* Installation and command line

  * New ``--errors`` command line argument will let you know the jobs that result in an error or have empty responses
    after filters are applied.
  * ``--test`` command line argument is used to test a job (formerly ``--test-filter``, deprecated and will be removed
    in a future release).
  * ``--test-differ`` command line argument is used to test a jobs' differ (formerly ``--test-diff-filter``, deprecated
    and will be removed in a future release) and display diff history.
  * ``--test-differ`` command line argument is no longer limited to displaying the last 10 snapshots.
  * Add job number(s) in command line to run a subset of jobs; for example, run ``webchanges 2 3`` to only run jobs #2
    and #3 of your jobs list (find job numbers by running ``webchanges --list``). Negative job indices are allowed; for
    example, run ``webchanges -1`` to only run the last job of your jobs list, or ``webchanges --test -2`` to test
    the second to last job of your jobs list.
  * New ``--max-snapshots`` command line argument sets the number of snapshots to keep stored in the database; defaults
    to 4. If set to 0, and unlimited number of snapshots will be kept. Only works if the default ``sqlite3`` database
    is being used.
  * New ``--database-engine ENGINE`` command line argument to specify database engine. New default ``sqlite3`` creates a
    smaller database due to data compression with `msgpack <https://msgpack.org/index.html>`__, higher speed due to
    indexing, and offers additional features and flexibility; migration from old 'minidb' database is done automatically
    and the old database preserved for manual deletion. Specify ``minidb`` to continue using the legacy database used
    by :program:`urlwatch`.
  * New ``--rollback-database TIMESTAMP`` new command line argument to rollback the snapshot database to a previous
    time, useful when you lose notifications. Does not work with database engine ``minidb`` or ``textfiles``.
  * New ``--delete-snapshot`` command line argument to removes the latest saved snapshot of a job from the database;
    useful if a change in a website (e.g. layout) requires modifying filters as invalid snapshot can be deleted and
    :program:`webchanges` rerun to create a truthful diff.
  * New ``--chromium-directory`` command line displays the directory where the downloaded Chromium executables are
    located to facilitate the deletion of older revisions.
  * New ``-V`` command line argument, as an alias to ``--version``.
  * New ``--log-level`` command line argument to control the amount of logging displayed by the ``-v`` argument.
  * If a filename for ``--jobs``, ``--config`` or ``--hooks`` is supplied without a path and the file is not present in
    the current directory, :program:`webchanges` now looks for it in the default configuration directory.
  * If a filename for ``--jobs`` or ``--config`` is supplied without a '.yaml' extension, or a filename for ``--hooks``
    without a '.py' extension, :program:`webchanges` now also looks for one with such an extension appended to it.
  * In Windows, ``--edit`` defaults to using the built-in notepad.exe text editor if both the %EDITOR% and %VISUAL%
    environment variables are not set.
  * Run a subset of jobs by adding their index number(s) as command line arguments. For example, run
    ``webchanges 2 3`` to only run jobs #2 and #3 of your jobs list. Run ``webchanges --list`` to find the job numbers.
    API is experimental and may change in the near future.
  * Installation of optional Python packages required by a feature or filter is now made easier with pip `extras
    <https://stackoverflow.com/questions/52474931/what-is-extra-in-pypi-dependency>`__  (e.g. ``pip
    install -U webchanges[ocr,pdf2text]``).
  * ``html2text``, ``markdown2`` and ``msgpack`` Python packages are now installed by default, while ``keyring`` and
    ``minidb`` Python are no longer installed by default.

* Files and location

  * The default name of the jobs file has been changed to ``jobs.yaml``; for backward-compatibility if at program launch
    no ``jobs.yaml`` exists but ``urls.yaml`` is found, its contents are copied into a newly created ``jobs.yaml`` file
    and the original preserved for manual deletion.
  * The default name of the program configuration file has been changed to ``config.yaml``; for backward-compatibility
    if at program launch no ``config.yaml`` exists but ``urlwatch.yaml`` is found, its contents are copied into a
    newly created ``config.yaml`` file and the original preserved for manual deletion.
  * In Windows, the location of the jobs and configuration files has been moved to
    ``%USERPROFILE%\Documents\webchanges``, where they can be more easily edited (they are indexed there) and backed up;
    if at program launch jobs and configurations files are only found in the old location (such as during an upgrade),
    these will be copied to the new directory automatically and the old ones preserved for manual deletion.
  * Legacy ``lib/hooks.py`` file location is no longer supported: ``hooks.py`` needs to be in the same directory as the
    job and configuration files.

* Directives

  * Navigation by full browser is now accomplished by specifying the ``url`` and adding the ``use_browser: true``
    directive. The use of the ``navigate`` directive instead of the ``url`` one has been deprecated for clarity and will
    trigger a warning; this directive will be removed in a future release.
  * The ``html2text`` filter defaults to using the Python ``html2text`` package (with optimized defaults) instead of
    ``re`` (now renamed `strip_tags`` for clarity).
  * New ``additions_only`` directive to report only added lines (useful when monitoring only new content).
  * New ``deletions_only`` directive to report only deleted lines.
  * New ``contextlines`` directive to specify the number of context lines in a unified diff.
  * New ``no_redirects`` job directive (for ``url`` jobs) to disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection.
  * New directives for ``use_browser: true`` (i.e. using **Chrome**) jobs to allow more flexibility and control:
    ``switches``, ``wait_until``, ``ignore_https_errors``, ``wait_for_navigation``, ``wait_for``,
    ``user_data_dir``, ``block_elements``, ``cookies``, ``headers``, ``http_proxy``, ``https_proxy``, and ``timeout``.
  * New ``note`` job directive to ad a freetext note appearing in the report after the job header.
  * New sub-directives for the ``strip`` filter: ``chars``, ``side`` and ``splitlines``.
  * The ``html2text`` filter's ``re`` method has been renamed ``strip_tags`` for clarity, the old name is deprecated and
    will trigger a warning.
  * The ``pdf2text`` filter now supports the ``raw`` and ``physical`` sub-directives, which are passed to the underlying
    Python package `pdftotext <https://github.com/jalan/pdftotext>`__ (version 2.2.0 or higher).
  * New ``format-xml`` filter to pretty-print xml using the lxml Python package’s etree.tostring pretty_print function
  * ``url`` directive supports ``ftp://`` URLs.
  * The ``user_visible_url`` job directive now applies to all type of jobs, including ``command`` ones.
  * The ``grep`` filter has been renamed ``keep_lines_containing`` for clarity, the old name is deprecated and will
    trigger a warning; it will be removed in a future release.
  * The ``grepi`` filter has been renamed ``delete_lines_containing`` for clarity, the old name deprecated and will
    trigger a warning; it will be removed in a future release.
  * Both the ``keep_lines_containing`` and ``delete_lines_containing`` accept ``text`` (default) in addition to ``re``
    (regular expressions).
  * New filter ``execute`` to filter the data using an executable without invoking the shell (as ``shellpipe`` does)
    and therefore exposing to additional security risks.
  * Support for ``ftp://`` URLs to download a file from an ftp server.
  * The use of the ``kind`` directive in ``jobs.yaml`` configuration files has been deprecated for simplicity (but is,
    for now, still used internally); it will be removed in a future release.
  * New ``browser`` reporter to display HTML-formatted report on a local browser.
  * The ``telegram`` reporter now uses MarkdownV2 and preserves most formatting of HTML sites processed by the
    ``html2text`` filter, e.g. clickable links, bolding, underlining, italics and strikethrough.
  * New sub-directive ``silent`` for ``telegram`` reporter to receive a notification with no sound.
  * The ``slack`` webhook reporter allows the setting of maximum report length (for, e.g., usage with Discord) using the
    ``max_message_length`` sub-directive.
  * ``url`` jobs with ``use_browser: true`` (i.e. using **Chrome**) now recognize ``data`` and ``method`` directives,
    enabling e.g. to make a ``POST`` HTTP request using a browser with JavaScript support.
  * New ``tz`` key for  ``report`` in configuration file sets the timezone for the diff in reports (useful if running
    e.g. on a cloud server in a different timezone).
  * New ``run_command`` reporter to execute a command and pass the report text as its input.
  * New ``remove_repeated`` filter to remove repeated lines (similar to Unix's ``uniq``).
  * The ``execute`` filter (and ``shellpipe``) sets more environment variables to allow for more flexibility.
  * Whenever a HTTP client error (4xx) response is received, in ``--verbose`` mode the content of the response is
    displayed with the error.
  * The user is now alerted when the job file and/or configuration file contains unrecognized directives (e.g. typo).
  * If a newer version of :program:`webchanges` has been released to PyPI, an advisory notice is printed to stdout.

* Reports

  * Reports are now sorted alphabetically.
  * If a newer version of :program:`webchanges` has been released to PyPI, an advisory notice is added to the report
    footer (if footer is enabled).

* Internals

  * Concurrency with ``use_browser: true`` (i.e. using **Chrome**) jobs takes into account amount of free memory for
    higher stability.
  * Upgraded concurrent execution loop to `concurrent.futures.ThreadPoolExecutor.map
    <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor.map>`__.
  * A new, more efficient indexed database no longer requiring external Python package  ``minidb``.
  * Changed timing from `datetime <https://docs.python.org/3/library/datetime.html>`__ to `timeit.default_timer
    <https://docs.python.org/3/library/timeit.html#timeit.default_timer>`__.
  * Replaced custom atomic_rename function with built-in `os.replace().
    <https://docs.python.org/3/library/os.html#os.replace>`__ (new in Python 3.3) that does the same thing.
  * Upgraded email construction from using ``email.mime`` (obsolete) to `email.message.EmailMessage
    <https://docs.python.org/3/library/email.message.html#email.message.EmailMessage>`__.
  * Reports' elapsed time now always has at least 2 significant digits.
  * Unicode is supported throughout, including in filters and jobs and configuration YAML files.
  * Implemented `pathlib <https://docs.python.org/3/library/pathlib.html>`__ (new in Python 3.4) for better
    code readability and functionality.
  * A 32 percentage point increase in code testing coverage (to ~74%), a completely new continuous integration
    (CI) and continuous delivery (CD) pipeline (`GitHub Actions <https://github.com/features/actions>`__), and testing
    on Ubuntu and macOS (with Windows 10 x64 to come) increases reliability of new releases.
  * Using `flake8 <https://pypi.org/project/flake8/>`__ to check PEP-8 compliance and more.
  * Using `coverage <https://pypi.org/project/coverage/>`__ to check unit testing coverage.
  * Strengthened security with `bandit <https://pypi.org/project/bandit/>`__ to catch common security issues.
  * Standardized code formatting with `black <https://pypi.org/project/black/>`__.
  * Properly arranging imports with `isort <https://pycqa.github.io/isort/>`__.
  * Added type hinting to the entire code and using `mypy <https://pypi.org/project/mypy/>`__ to check it.
  * A vast improvement in documentation and error text.
  * The support for Python 3.11.

Fixed
~~~~~
Relative to :program:`urlwatch`:

* Diff (change) data is no longer lost if :program:`webchanges` is interrupted mid-execution or encounters an error in
  reporting: the permanent database is updated only at the very end (after reports are sent).
* The database no longer grows unbounded to infinity. Fix only works when using the new, default, ``sqlite3`` database
  engine. In this scenario only the latest 4 snapshots are kept, and older ones are purged after every run; the number
  is selectable with the new ``--max-snapshots`` command line argument. To keep the existing grow-to-infinity behavior,
  run :program:`webchanges` with ``--max-snapshots 0``.
* The ``html2text`` filter's ``html2text`` method defaults to Unicode handling.
* The ``html2text`` filter's ``strip_tags`` method is no longer returning HTML character references (e.g. &gt;, &#62;
  , &#x3e;) but the corresponding Unicode characters.
* HTML href links ending with spaces are no longer broken by ``xpath`` replacing spaces with ``%20``.
* Initial config file no longer has directives sorted alphabetically, but are saved logically (e.g. 'enabled' is always
  the first sub-directive for a reporter).
* The presence of the ``data`` directive in a job no longer forces the method to POST allowing e.g. PUTs.
* ``format-json`` filter no longer unexpectedly reorders contents of dictionaries, but the new sub-directive
  ``sort_keys`` allows you to set it to do so if you want to.
* When using the ``--edit`` or ``--edit-config`` command line arguments to edit jobs or configuration files, symbolic
  file links are maintained (no longer overwritten by the file).
* Jobs file (e.g. ``jobs.yaml``) is now loaded only once per run.
* Fixed various system errors and freezes when running ``url`` jobs with ``use_browser: true`` (formerly ``navigate``
  jobs).
* Job ``headers`` stored in the configuration file (``config.yaml``) are now merged correctly and case-insensitively
  with those present in the job (in ``jobs.yaml``). A header in the job replaces a header by the same name if already
  present in the configuration file, otherwise is added to the ones present in the configuration file.
* Fixed ``TypeError: expected string or bytes-like object`` error in cookiejar (called by requests module) caused by
  some ``cookies`` being read from the jobs YAML file in other formats.
* Use same retrieval duration precision in all reports.
* Fixed a rare case when html report would not correctly reconstruct a clickable link from Markdown for (an) item(s)
  inside an element in a list.
* No longer errors out when ``telegram`` reporter's ``chat_id`` is numeric.
* ``test-differ`` command line argument was showing historical diffs in wrong order; now showing most recent first
* An error is now raised when a ``url`` job with ``use_browser: true`` returns no data due to an HTTP error (e.g.
  proxy_authentication_required).
* Jobs were included in email subject line even if there was nothing to report after filtering with ``additions_only``
  or ``deletions_only``.
* ``hexdump`` filter now correctly formats lines with less than 16 bytes.
* ``sha1sum`` and ``hexdump`` filters now accept data that is bytes (not just text).
* Fixed case of wrong ETag being captured and saved when a URL redirection took place.
* Rewrote most error messages for increased clarity.


.. _upgrade_deprecations:

Deprecations
~~~~~~~~~~~~
Relative to :program:`urlwatch`:

* The ``html2text`` filter's ``lynx`` method is no longer supported as it was obsoleted by Python libraries; use the
  default method instead or construct a custom ``execute`` command.
* The following deprecations are (for now) still working but will issue a warning:

  * Job directive ``kind`` is unused: remove from job.
  * Job directive ``navigate`` is deprecated: use ``url`` and add ``use_browser: true``.
  * Method ``pyhtml2text`` of filter ``html2text`` is deprecated; since that method is now the default, remove the
    method's sub-directive.
  * Method ``re`` of filter ``html2text`` is renamed to ``strip_tags`` for clarity.
  * Filter ``grep`` is renamed to ``keep_lines_containing`` for clarity.
  * Filter ``grepi`` is renamed to ``delete_lines_containing`` for clarity.
  * Command line ``--test-filter`` argument is renamed to ``--test`` for clarity.
  * Command line ``--test-diff-filter`` argument is renamed to ``--test-differ`` for clarity.

* Also be aware that:

  * The name of the default job file has changed to ``jobs.yaml``; if not found, legacy ``urls.yaml`` will be
    automatically copied into it.
  * The name of the default configuration file has changed to ``config.yaml``; if not found, legacy ``urlwatch.yaml``
    will be automatically copied into it.
  * The location of configuration and jobs files in Windows has changed to ``%USERPROFILE%/Documents/webchanges``
    where they can be more easily edited and backed up.


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
   complete license `here <https://github.com/mborsetti/webchanges/blob/main/LICENSE>`__.

(2) Each file with code contains this remark at the top:

::

   # The code below is subject to the license contained in the LICENSE file, which is part of the source code.

Note: There is no requirement anywhere in law to spam the entire 61-line, 465 words license text on Every. Single.
File. In. Every. Single. Directory; the above notice is amply sufficient.

(3) The `license file <https://github.com/mborsetti/webchanges/blob/main/LICENSE>`__ reads:

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

(4) While a lot of improvements have been made from urlwatch 2.21, there's no lack of proper and complete
acknowledgement of the package's use of Thomas Perl's code -- in multiple ways, incuding the required full and explicit
licensing language.
