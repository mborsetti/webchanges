.. _migration:


.. role:: underline
    :class: underline

.. role:: additions
    :class: additions

.. role:: deletions
    :class: deletions

=======================
Upgrading from urlwatch
=======================

`webchanges` |version| is a fork of `urlwatch <https://github.com/thp/urlwatch>`__ as suggested by its author to
optimize it for HTML, and is backward-compatible with `urlwatch 2.23`'s job and configuration files.

Upgrading from a `urlwatch` 2.23 setup is automatic (see more below), and gives you:

* Vastly improved HTML reporting, including:

  * Links that are `clickable <https://pypi.org/project/webchanges/>`__!
  * Formatting such as **bolding / headers**, *italics*, :underline:`underlining`, list bullets (•) and indentation is
    preserved
  * Use of color (compatible with Dark Mode) and strikethrough to highlight :additions:`added` and :deletions:`deleted`
    lines
  * Correct wrapping of long lines
  * Correct rendering by email clients who override stylesheets (e.g. Gmail)
  * Better HTML-to-text translation with updated defaults for the ``html2text`` filter
  * Other legibility improvements
* Multiple upgrades in `Pyppeteer`-based browsing (called ``navigate`` in `urlwatch`) to render JavaScript, including:

  * Upgraded browser engine (same as Chrome 89)
  * Increased reliability with the use of Python's built-in ``asyncio.run()`` to manage the asyncio event loop,
    finalizing asynchronous generators, and closing the threadpool instead of custom code (only if running in Python 3.7
    or higher)
  * Higher stability by optimizing of concurrency
  * More flexibility and control with new directives ``chromium_revision``, ``switches``, ``wait_until``,
    ``ignore_https_errors``, ``wait_for_navigation``, ``wait_for``, ``user_data_dir``, ``block_elements``, ``cookies``,
    ``headers``, ``http_proxy``, ``https_proxy``, and ``timeout`` plus the implementation for this type of jobs (if
    running in Python 3.7 or higher) of the ``ignore_connection_errors``, ``ignore_timeout_errors``,
    ``ignore_too_many_redirects`` and ``ignore_http_error_codes`` directives
  * Faster runs due to handling of ETags allowing servers to send a simple "HTTP 304 Not Modified" message when
    relevant
  *
     directives now work with these type of jobs

* A new, more efficient indexed database that is smaller, allows for additional functionality such as rollbacks, and
  does not infinitely grow
* Diffs (changes) that are no longer lost if `webchanges` is interrupted mid-execution or encounters an error with a
  reporter
* The use of the webpage's title as a job ``name`` if one isn't provided
* The ability to add a job ``note`` in the report
* New filters such as `additions_only <https://webchanges.readthedocs.io/en/stable/diff_filters.html#additions-only>`__,
  which makes it easier to track content that was added without the distractions of the content that was deleted
* A new ``--errors`` command line argument to help catching any problems by listing all jobs that error out or have
  empty data after filters are applied
* The support of Unicode throughout, including in filters and in the jobs and configuration YAML files
* The fixing of the ``format-json`` filter from unexpectedly reordering contents of dictionaries, now controllable by
  the new sub-directive ``sort_keys``
* More reliable releases due to:

  * A 33 percentage point increase in code testing coverage (to 75%)
  * Completely new continuous integration (CI) and continuous delivery (CD) pipeline (GitHub Actions with pre-commit)
  * Uses of flake8 and doc8 linters and pre-commit checks
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
If you are using `urlwatch` 2.23, simply install `webchanges` and run it. It will find the existing `urlwatch` job and
configuration files, and, unless you were still running ``lynx`` (see below), it will run just fine as is. It may
complain about some directive name being changed for clarity and other :ref:`deprecations <migration_deprecations>`, but
you will have time to make the edits if you decide to stick around!

If you encounter any problems or have any suggestions please open an issue `here
<https://github.com/mborsetti/webchanges/issues>`__ and someone will look into it.

If you are upgrading from a version of `urlwatch` prior to 2.23, before running `webchanges` make sure that you have
implemented all `urlwatch` breaking changes in your job and configuration files and can run `urlwatch` 2.23
successfully.

For example, per `urlwatch` issue `#600 <https://github.com/thp/urlwatch/pull/600#issuecomment-753944678>`__),

.. code-block:: yaml

   url: https://example.com/
   filter: html2text

no longer works in `urlwatch` 2.23, and therefore in `webchanges`, as all filters must be specified as subfilters like
this:

.. code-block:: yaml

   url: https://example.com/
   filter:
     - html2text:


.. _migration_changes:

Upgrade details
---------------
Everything, except the breaking changes below, work out of the box when upgrading from a `urlwatch` 2.23 setup,
and you can switch back whenever you want.

⚠ Breaking Changes
~~~~~~~~~~~~~~~~~~
Relative to `urlwatch` 2.23:

* By default a new much improved database engine is used; run with ``--database-engine minidb`` command line argument to
  preserve backwards-compatibility
* By default only 4 snapshots are kept with the new database engine (if running Python 3.7 or higher), and older ones
  are purged after every run; run with ``--max-snapshots 0`` command line argument to keep the existing behavior
  (but beware of infinite database growth)
* The ``html2text`` filter's ``lynx`` method is no longer supported as it was obsoleted by Python packages; use the
  default method instead or construct a custom ``execute`` command

Additions and changes
~~~~~~~~~~~~~~~~~~~~~
Relative to `urlwatch` 2.23:

* Installation and command line

  * Installation of optional Python packages required by a feature is now made easier with pip `extras
    <https://stackoverflow.com/questions/52474931/what-is-extra-in-pypi-dependency>`__  (e.g. ``pip
    install -U webchanges[ocr,pdf2text]``)
  * ``html2text``, ``markdown2`` and ``msgpack`` Python packages are now installed by default, while ``keyring`` and
    ``minidb`` Python are no longer installed by default
  * New ``--errors`` command line argument will let you know the jobs that result in an error or have empty responses
    after filters are applied
  * ``--test`` command line argument is used to test a job (formerly ``--test-filter``, deprecated and will be removed
    in a future release)
  * ``--test-diff`` command line argument is used to test a jobs' diff (formerly ``--test-diff-filter``, deprecated and
    will be removed in a future release) and display diff history
  * ``--test-diff`` command line argument is no longer limited to displaying the last 10 snapshots
  * Add job number(s) in command line to run a subset of them; for example, run ``webchanges 2 3`` to only run jobs #2
    and #3 of your jobs list (find job numbers by running``webchanges --list``)
  * New ``--max-snapshots`` command line argument sets the number of snapshots to keep stored in the database; defaults
    to 4. If set to 0, and unlimited number of snapshots will be kept. Only applies to Python 3.7 or higher and only
    works if the default ``sqlite3`` database is being used.
  * New ``--cache-engine ENGINE`` command line argument to specify database engine. New default ``sqlite3`` creates a
    smaller database due to data compression with `msgpack <https://msgpack.org/index.html>`__, higher speed due to
    indexing, and offers additional features and flexibility; migration from old 'minidb' database is done automatically
    and the old database preserved for manual deletion. Specify ``minidb`` to continue using the legacy database used
    by `urlwatch`
  * New ``--rollback-cache TIMESTAMP`` new command line argument to rollback the snapshot database to a previous time,
    useful when you lose notifications. Does not work with database engine ``minidb`` or ``textfiles``.
  * New ``--delete-snapshot`` command line argument to removes the latest saved snapshot of a job from the database;
    useful if a change in a website (e.g. layout) requires modifying filters as invalid snapshot can be deleted and
    `webchanges` rerun to create a truthful diff

  * New ``-V`` command line argument, as an alias to ``--version``
  * New ``--log-level`` command line argument to control the amount of logging displayed by the ``-v`` argument
  * If a filename for ``--jobs``, ``--config`` or ``--hooks`` is supplied without a path and the file is not present in
    the current directory, `webchanges` now looks for it in the default configuration directory
  * If a filename for ``--jobs`` or ``--config`` is supplied without a '.yaml' extension, or a filename for ``--hooks``
    without a '.py' extension, `webchanges` now also looks for one with such an extension appended to it
  * In Windows, ``--edit`` defaults to using the built-in notepad.exe text editor if both the %EDITOR% and %VISUAL%
    environment variables are not set

* Files and location

  * The name of the default jobs file has been changed to ``jobs.yaml``; if at program launch ``urls.yaml`` is found
    and no ``jobs.yaml`` exists, this is copied into a newly created ``jobs.yaml`` file for backward-compatibility
  * The name of the default program configuration file has been changed to ``config.yaml``; if at program launch
    ``urlwatch.yaml`` is found and no ``config.yaml`` exists, this is copied into a newly created ``config.yaml`` file
    for backward-compatibility
  * In Windows, the location of the jobs and configuration files has been moved to
    ``%USERPROFILE%\Documents\webchanges``, where they can be more easily edited (they are indexed there) and backed up;
    if at program launch jobs and configurations files are only found in the old location (such as during an upgrade),
    these will be copied to the new directory automatically and the old ones preserved for manual deletion
  * Legacy ``lib/hooks.py`` file location is no longer supported: ``hooks.py`` needs to be in the same directory as the
    configuration files

* Directives

  * Navigation by full browser is now accomplished by specifying the ``url`` and adding the ``use_browser: true``
    directive. The use of the ``navigate`` directive instead of the ``url`` one has been deprecated for clarity and will
    trigger a warning; this directive will be removed in a future release
  * The ``html2text`` filter defaults to using the Python ``html2text`` package (with optimized defaults) instead of
    ``re`` (now renamed `strip_tags`` for clarity)
  * New ``additions_only`` directive to report only added lines (useful when monitoring only new content)
  * New ``deletions_only`` directive to report only deleted lines
  * New ``contextlines`` directive to specify the number of context lines in a unified diff
  * New ``no_redirects`` job directive (for ``url`` jobs) to disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection
  * New directives for ``use_browser: true`` (`Pyppeteer`) jobs to allow more flexibility and control:
    ``chromium_revision``, ``switches``, ``wait_until``, ``ignore_https_errors``, ``wait_for_navigation``, ``wait_for``,
    ``user_data_dir``, ``block_elements``, ``cookies``, ``headers``, ``http_proxy``, ``https_proxy``, and ``timeout``
  * New ``note`` job directive to ad a freetext note appearing in the report after the job header
  * New sub-directives for the ``strip`` filter: ``chars``, ``side`` and ``splitlines``
  * The ``html2text`` filter's ``re`` method has been renamed ``strip_tags`` for clarity, the old name is deprecated and
    will trigger a warning
  * New sub-directives to the ``strip`` filter:

    * ``chars``: Set of characters to be removed (default: whitespace)
    * ``side``: One-sided removal, either ``left`` (leading characters) or ``right`` (trailing characters)
    * ``splitlines``: Whether to apply the filter on each line of text (true/false) (default: ``false``, i.e. apply to
      the entire data)
  * New ``format-xml`` filter to pretty-print xml using the lxml Python package’s etree.tostring pretty_print function
  * ``url`` directive supports ``ftp://`` URLs
  * The ``grep`` filter has been renamed ``keep_lines_containing`` for clarity, the old name is deprecated and will
    trigger a warning; it will be removed in a future release
  * The ``grepi`` filter has been renamed ``delete_lines_containing`` for clarity, the old name deprecated and will
    trigger a warning; it will be removed in a future release
  * Both the ``keep_lines_containing`` and ``delete_lines_containing`` accept ``text`` (default) in addition to ``re``
    (regular expressions)
  * The use of the ``kind`` directive in ``jobs.yaml`` configuration files has been deprecated for simplicity (but is,
    for now, still used internally); it will be removed in a future release
  * The ``slack`` webhook reporter allows the setting of maximum report length (for, e.g., usage with Discord) using the
    ``max_message_length`` sub-directive
  * The user is now alerted when the job file contains unrecognized directives (e.g. typo)
  * Reduction in concurrency for higher stability

* Internals

  * Increased reliability by using Python's built-in ``asyncio.run()`` to manage the asyncio event loop, finalizing
    asynchronous generators, and closing the threadpool instead of legacy custom code (only if running Python
    3.7 or higher)
  * Upgraded concurrent execution loop to `concurrent.futures.ThreadPoolExecutor.map
    <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor.map>`__
  * A new, more efficient indexed database no longer requiring external Python package
  * Changed timing from `datetime <https://docs.python.org/3/library/datetime.html>`__ to `timeit.default_timer
    <https://docs.python.org/3/library/timeit.html#timeit.default_timer>`__
  * Using Chromium revisions equivalent to Chrome 89.0.4389.72 for jobs with ``use_browser: true`` (i.e. using
    `Pyppeteer`)
  * Replaced custom atomic_rename function with built-in `os.replace()
    <https://docs.python.org/3/library/os.html#os.replace>`__ (new in Python 3.3) that does the same thing
  * Upgraded email construction from using ``email.mime`` (obsolete) to `email.message.EmailMessage
    <https://docs.python.org/3/library/email.message.html#email.message.EmailMessage>`__
  * Reports' elapsed time now always has at least 2 significant digits
  * Unicode is supported throughout, including in filters and jobs and configuration YAML files
  * A 33 percentage point increase in code testing coverage (to 75%), a completely new continuous integration
    (CI) and continuous delivery (CD) pipeline (GitHub Actions), and testing on both Ubuntu **and** macOS (Windows 10
    x64 to come) increase reliability of new releases
  * Using flake8 to check PEP-8 compliance and more
  * Using coverage to check unit testing coverage
  * Added type hinting to the entire code
  * A vast improvement in documentation and error text
  * The support for Python 3.9

Fixed
~~~~~
Relative to `urlwatch` 2.23:

* Diff (change) data is no longer lost if `webchanges` is interrupted mid-execution or encounters an error in reporting:
  the permanent database is updated only at the very end (after reports are sent)
* The database no longer grows unbounded to infinity. Fix only works when running in Python 3.7 or higher and using
  the new, default, ``sqlite3`` database engine. In this scenario only the latest 4 snapshots are kept, and older ones
  are purged after every run; the number is selectable with the new ``--max-snapshots`` command line argument. To keep
  the existing grow-to-infinity behavior, run `webchanges` with ``--max-snapshots 0``.
* The ``html2text`` filter's ``html2text`` method defaults to Unicode handling
* HTML href links ending with spaces are no longer broken by ``xpath`` replacing spaces with `%20`
* Initial config file no longer has directives sorted alphabetically, but are saved logically (e.g. 'enabled' is always
  the first sub-directive for a reporter)
* The presence of the ``data`` directive in a job would force the method to POST, impeding the ability to do PUTs
* ``format-json`` filter no longer unexpectedly reorders contents of dictionaries, but the new sub-directive
  ``sort_keys`` allows you to set it to do so
* Jobs file (e.g. ``jobs.yaml``) is now loaded only once per run
* Fixed various system errors and freezes when running ``url`` jobs with ``use_browser: true`` (formerly ``navigate``
  jobs)
* Fixed multiple error messages for clarity


.. _migration_deprecations:

Deprecations
~~~~~~~~~~~~
Relative to `urlwatch` 2.23:

* The ``html2text`` filter's ``lynx`` method is no longer supported as it was obsoleted by Python libraries; use the
  default method instead or construct a custom ``execute`` command

* The following deprecations are (for now) still working with a warning:

  * Job directive ``kind`` is unused: remove from job
  * Job directive ``navigate`` is deprecated: use ``url`` and add ``use_browser: true``
  * Method ``pyhtml2text`` of filter ``html2text`` is deprecated; since that method is now the default, remove the
    method's sub-directive
  * Method ``re`` of filter ``html2text`` is renamed to ``strip_tags``
  * Filter ``grep`` is renamed to ``keep_lines_containing``
  * Filter ``grepi`` is renamed to ``delete_lines_containing``
  * Command line ``--test-filter`` argument is renamed to ``--test``
  * Command line ``--test-diff-filter`` argument is renamed to ``--test-diff``

* Also be aware that:

  * The name of the default job file has changed to ``jobs.yaml``; if not found, legacy ``urls.yaml`` will be
    automatically copied into it
  * The name of the default configuration file has changed to ``config.yaml``; if not found, legacy ``urlwatch.yaml``
    will be automatically copied into it
  * The location of configuration and jobs files in Windows has changed to ``%USERPROFILE%/Documents/webchanges``
    where they can be more easily edited and backed up

Known issues
~~~~~~~~~~~~
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be
  fixed in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``
