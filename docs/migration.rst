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
optimize it for HTML, and is backward-compatible with `urlwatch 2.22`'s job and configuration files.

Upgrading from a `urlwatch` 2.22 setup is automatic (see more below), and in addition to the visual improvements listed
in the :ref:`introduction <introduction>`, it also implements:

* An upgrade in Pyppeteer-based browsing to render JavaScript that includes:

  * using the same browser engine powering Chrome 89
  * using Python's built-in ``asyncio.run()`` to manage the asyncio event loop, finalizing asynchronous generators, and
    closing the threadpool instead of legacy custom code managing to increase reliability (only if running **Python
    3.7** or higher)
  * reduction in concurrency for higher stability
  * new directives allowing much more flexibility and control: ``chromium_revision``, ``switches``, ``wait_until``,
    ``ignore_https_errors``, ``wait_for_navigate``, ``wait_for``, ``user_data_dir``, ``block_elements``, ``cookies``,
    ``headers``, ``http_proxy``, ``https_proxy``, and ``timeout``
* A new, more efficient indexed database that is smaller, allows for additional functionality such as rollbacks, and
  removes the need for a dependency
* The use of the webpage's title as a job ``name`` if one isn't provided and the ability to add a job ``note`` in the
  report
* The optimization of the default settings of the ``html2text`` filter for web content
* A new ``--errors`` command line switch to show any jobs that error out or have empty responses after filters are
  applied
* The support of Unicode throughout, including in filters and in the YAML files containing jobs and configuration
* The fixing of the ``format-json`` filter from unexpectedly reordering contents of dictionaries, now controllable by
  the new subdirective ``sort_keys``
* An 11 percentage point increase in code testing coverage, completely new continuous integration (CI) and
  continuous delivery (CD) pipeline, and testing on both Ubuntu **and** macOS (Windows 10 x64 to come) to
  increase reliability of new releases
* The support for Python 3.9
* A vast improvements in documentation and error text

How-to
------
If you are using `urlwatch` 2.22, simply install `webchanges` and run it. It will find the existing `urlwatch` files,
read them, and, unless you were still running ``lynx`` (see below), it will run just fine as is.  It may complain about
some directive name changes and other :ref:`deprecations <migration_deprecations>`, but you will have time to make the
edits.

If you encounter any problems or have any suggestions please open an issue `here
<https://github.com/mborsetti/webchanges/issues>`__ and someone will look into it.

If you are upgrading from a version prior to 2.22, before running `webchanges` make sure that you have implemented all
`urlwatch` breaking changes in your job and configuration files and you can run `urlwatch` 2.22 (including running on
Python 3.6 or higher).  For example:

.. code-block:: yaml

   url: https://example.com/
   filter: html2text

no longer works in `urlwatch` 2.22, and therefore in `webchanges`, as all filters must be specified as subfilters like
this: (see `here <https://github.com/thp/urlwatch/pull/600#issuecomment-753944678>`__)

.. code-block:: yaml

   url: https://example.com/
   filter:
     - html2text:

.. _migration_deprecations:

Deprecations
------------
Of the changes (see below), the following are deprecations. While they will be removed in a future release, they
are still working:

* The ``html2text`` filter's ``lynx`` method is no longer supported as it was obsoleted by Python libraries; use the
  default method instead or construct a custom ``shellpipe``
* Job directive ``kind`` is unused: remove from job
* Job directive ``navigate`` is deprecated: use ``url`` and add ``use_browser: true``
* Method ``pyhtml2text`` of filter ``html2text`` is deprecated; since that method is now the default, remove the method
  subdirective
* Method ``re`` of filter ``html2text`` is renamed to ``strip_tags``
* Filter ``grep`` is renamed to ``keep_lines_containing``
* Filter ``grepi`` is renamed to ``delete_lines_containing``
* Command line ``--test-filter`` switch is renamed to ``--test``
* Command line ``--test-diff-filter`` switch is renamed to ``--test-diff``

Also be aware that:

* The ``html2text`` filter's ``lynx`` method is no longer supported as it was obsoleted by Python libraries; use the
  default method instead or construct a custom ``shellpipe``
* The name of the default job file has changed to ``jobs.yaml`` (if at startup only ``urls.yaml`` is found as during an
  upgrade, it is copied to ``jobs.yaml`` automatically)
* The location of config and jobs files in Windows has changed to ``%USERPROFILE%/Documents/webchanges``
  where they can be more easily edited and backed up (if at startup the only files found are in the old location as
  during an upgrade, they will be copied to the  new directory automatically)

.. _migration_changes:

Detailed information
--------------------

Breaking Changes
~~~~~~~~~~~~~~~~
Relative to `urlwatch` 2.22:

* The ``html2text`` filter's ``lynx`` method is no longer supported as it was obsoleted by Python libraries; use the
  default method instead or construct a custom ``shellpipe``

Additions and changes
~~~~~~~~~~~~~~~~~~~~~
Everything, except using ``lynx`` instead of the internal ``html2text`` filter, should work out of the box with a
`urlwatch` 2.22 setup, but the following changes and deprecations are made for better clarity and future development:

* Navigation by full browser is now accomplished by specifying the ``url`` and adding the ``use_browser: true``
  directive. The `navigate` directive has been deprecated for clarity and will trigger a warning; it will be removed in
  a future release
* The name of the default program configuration file has been changed to ``config.yaml``; if at program launch
  ``urlwatch.yaml`` is found and no ``config.yaml`` exists, it is copied over for backward-compatibility.
* In Windows, the location of config files has been moved to ``%USERPROFILE%\Documents\webchanges``
  where they can be more easily edited (they are indexed there) and backed up
* The ``html2text`` filter defaults to using the Python ``html2text`` package (with optimized defaults) instead of
  ``re``
* New ``additions_only`` directive to report only added lines (useful when monitoring only new content)
* New ``deletions_only`` directive to report only deleted lines
* ``keyring`` and ``minidb`` Python packages are no longer installed by default
* ``html2text`` and ``markdown2`` Python packages are installed by default
* Installation of Python packages required by a feature is now made easier with pip extras (e.g. ``pip install -U
  webchanges[ocr,pdf2text]``)
* The name of the default job's configuration file has been changed to ``jobs.yaml``; if at program launch `urlwatch`'s
  ``urls.yaml`` is found and no ``jobs.yaml`` exists, it is copied over for backward-compatibility
* The ``html2text`` filter's ``re`` method has been renamed ``strip_tags``, the old name deprecated and will trigger a
  warning
* The ``grep`` filter has been renamed ``keep_lines_containing``, the old name deprecated and will trigger a warning; it
  will be removed in a future release
* The ``grepi`` filter has been renamed ``delete_lines_containing``, the old name deprecated and will trigger a warning; it
  will be removed in a future release
* Both the ``keep_lines_containing`` and ``delete_lines_containing`` accept ``text`` (default) in addition to ``re``
  (regular expressions)
* ``--test`` command line switch is used to test a job (formerly ``--test-filter``, deprecated and will be removed in
  a future release)
* ``--test-diff`` command line switch is used to test a jobs' diff (formerly ``--test-diff-filter``, deprecated and will
  be removed in a future release)
* A new ``--errors`` command line switch will let you know what jobs error out or have empty responses after filters are
  applied
* ``-V`` command line switch added as an alias to ``--version``
* If a filename for ``--jobs``, ``--config`` or ``--hooks`` is supplied without a path and the file is not present in
  the current directory, `webchanges` now looks for it in the default configuration directory
* If a filename for ``--jobs`` or ``--config`` is supplied without a '.yaml' suffix, `webchanges` now also looks for one
  with such a suffix
* In Windows, ``--edit`` defaults to using built-in notepad.exe if either the %EDITOR% or %VISUAL% environment variable
  is not set
* When using ``--job`` command line switch, if there's no file by that name in the specified directory will look in
  the default one before giving up.
* The use of the ``kind`` directive in ``jobs.yaml`` configuration files has been deprecated (but is, for now, still
  used internally); it will be removed in a future release
* The ``slack`` webhook reporter allows the setting of maximum report length (for, e.g., usage with Discord) using the
  ``max_message_length`` sub-directive
* Legacy lib/hooks.py file location is no longer supported: ``hooks.py`` needs to be in the same directory as the
  configuration files.
* The name of the default job file has changed to ``jobs.yaml`` (if at startup only ``urls.yaml`` is found as during an
  upgrade, it is copied to ``jobs.yaml`` automatically)
* The location of config and jobs files in Windows has changed to ``%USERPROFILE%/Documents/webchanges``
  where they can be more easily edited and backed up (if at startup the only files found are in the old location as
  during an upgrade, they will be copied to the  new directory automatically)
* The mix of default and optional dependencies has been updated (see documentation) to enable "Just works"
* Dependencies are now specified as PyPi `extras
  <https://stackoverflow.com/questions/52474931/what-is-extra-in-pypi-dependency>`__ to simplify their installation
* Changed timing from `datetime <https://docs.python.org/3/library/datetime.html>`__ to `timeit.default_timer
  <https://docs.python.org/3/library/timeit.html#timeit.default_timer>`__
* Upgraded concurrent execution loop to `concurrent.futures.ThreadPoolExecutor.map
  <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor.map>`__
* Reports' elapsed time now always has at least 2 significant digits
* Using flake8 to check PEP-8 compliance and more
* Using coverage to check unit testing coverage
* Unicode is supported throughout, including in filters and YAML files containing jobs and configuration
* A 10 percentage point increase in code testing coverage, a completely new continuous integration (CI) and continuous
  delivery (CD) pipeline, and testing on both Ubuntu **and** macOS (Windows 10 x64 to come) increases reliability
* A vast improvements in documentation and error text
* The support for Python 3.9

Fixed
~~~~~
Relative to `urlwatch` 2.22:

* The ``html2text`` filter's ``html2text`` method defaults to Unicode handling
* HTML href links ending with spaces are no longer broken by ``xpath`` replacing spaces with `%20`
* Initial config file no longer has directives sorted alphabetically, but are saved logically (e.g. 'enabled' is always
  the first sub-directive)
* The presence of the ``data`` directive in a job would force the method to POST, impeding the ability to do PUTs
* ``format-json`` filter from unexpectedly reordered contents of dictionaries; it no longer does that, but a new
  subdirective ``sort_keys`` allows you to set it to do so
* Various system errors and freezes when running ``url`` jobs with ``use_browser: true`` (formerly ``navigate`` jobs)
