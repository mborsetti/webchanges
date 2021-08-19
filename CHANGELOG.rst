*********
Changelog
*********

This changelog mostly follows '`keep a changelog <https://keepachangelog.com/en/1.0.0/>`__'. Release numbering mostly
follows `Semantic Versioning <https://semver.org/spec/v2.0.0.html#semantic-versioning-200>`__. Release date is UTC.
Documentation updates and improvements are ongoing and not always listed here.

**Development**

The unreleased versions can be installed as follows (`git
<https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`__ needs to be installed):

.. code-block:: bash

   pip install git+https://github.com/mborsetti/webchanges.git@unreleased

Unreleased documentation is `here <https://webchanges.readthedocs.io/en/unreleased/>`__.

`Contributions <https://github.com/mborsetti/webchanges/blob/main/CONTRIBUTING.rst>`__ are always welcomed, and you
can check out the `wish list <https://github.com/mborsetti/webchanges/blob/main/WISHLIST.md>`__ for inspiration.

.. Categories used (in order):
   ⚠ Breaking Changes, for changes that break existing functionality. [minor revision or, if to API, major revision]
   Added, for new features. [triggers a minor revision]
   Changed, for changes in existing functionality. [triggers a minor revision or, if to API, major revision]
   Deprecated, for soon-to-be removed features.
   Removed, for now removed features. [if to API, triggers a major revision].
   Fixed, for any bug fixes. [triggers a minor patch]
   Security, in case of vulnerabilities. [triggers a minor patch]
   Internals, for changes that don't affect users. [triggers a minor patch]


Version 3.8.2rc0
====================
Unreleased


⚠ Breaking Changes (dependencies)
---------------------------------
* Filter ``pdf2text``'s dependency Python package `pdftotext <https://github.com/jalan/pdftotext>`__ in its latest
  version 2.2.0 has changed the way it displays text to no longer try to emulate formatting (columns etc.). This is
  generally a welcome improvement as changes in formatting no longer trigger change reports, but if you want to
  return to the previous layout we have added a ``physical`` sub-directive which you need to set to ``true`` on the
  jobs affected. **Note that all your** ``pdf2text`` **jobs will report changes (in formatting) the first time they
  are run after the pdftotext Python package is updated**.

Changed
-------
* Updated default Chromium executables to revisions equivalent to Chromium 92.0.4515.131 (latest stable release); this
  fixes unsupported browser error thrown by certain websites. Use ``webchanges --chromium-directory`` to locate where
  older revision were downloaded to delete them manually.

Added
-----
* Filter ``pdf2text`` now supports the ``raw`` and ``physical`` sub-directives, which are passed to the underlying
  Python package `pdftotext <https://github.com/jalan/pdftotext>`__.
* New ``--chromium-directory`` command line displays the directory where the downloaded Chromium executables are
  located to facilitate the deletion of older revisions.
* Footer now indicates if the run was made with a jobs file whose stem name is not the default 'jobs', to ease
  identification when running *webchanges* with a variety of jobs files.

Fixed
-----
* Fixed legacy code handling ``--edit-config`` command line argument to allow editing of a configuration file
  with YAML syntax errors (`#15 <https://github.com/mborsetti/webchanges/issues/15>`__ by
  `Markus Weimar <https://github.com/Markus00000>`__).
* Telegram reporter documentation was missing instructions on how to notify channels (`#16
  <https://github.com/mborsetti/webchanges/issues/16>`__ by `Sean Tauber <https://github.com/buzzeddesign>`__).

Internals
---------
* Type hints are checked during pre-commit by `mypy <http://www.mypy-lang.org/>`__.
* Imports are rearranged during pre-commit by `isort <https://pycqa.github.io/isort/>`__.
* Now testing all database engines, including redis, and more, adding 4 percentage points of code coverage to 81%.


Version 3.8.1
====================
2021-08-03

Fixed
-----
* Files in the new _vendored directory are now installed correctly.


Version 3.8
====================
2021-07-31

Added
-----
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) now recognize ``data`` and ``method`` directives,
  enabling e.g. to make a ``POST`` HTTP request using a browser with JavaScript support.
* New ``tz`` key for  ``report`` in the configuration sets the timezone for the diff in reports (useful if running
  e.g. on a cloud server in a different timezone). See `documentation
  <https://webchanges.readthedocs.io/en/stable/reporters.html#tz>`__.
* New ``run_command`` reporter to execute a command and pass the report text as its input. Suggested by `Marcos Alano
  <https://github.com/mhalano>`__ upstream `here <https://github.com/thp/urlwatch/issues/650>`__.
* New ``remove_repeated`` filter to remove repeated lines (similar to Unix's ``uniq``). Suggested by `Michael
  Sverdlin <https://github.com/Sveder>`__ upstream `here <https://github.com/thp/urlwatch/pull/653>`__.
* The ``user_visible_url`` job directive now applies to all type of jobs, including ``command`` ones. Suggested by
  `kongomongo <https://github.com/kongomongo>`__ upstream `here <https://github.com/thp/urlwatch/issue/608>`__.
* The ``--delete-snapshot`` command line argument now works with Redis database engine (``--database-engine redis``).
  Contributed by `Scott MacVicar <https://github.com/scottmac>`__ with pull request
  #`13 <https://github.com/mborsetti/webchanges/pull/13>`__.
* The ``execute`` filter (and ``shellpipe``) sets more environment variables to allow for more flexibility; see improved
  `documentation <https://webchanges.readthedocs.io/en/stable/filters.html#execute>`__ (including more examples).
* Negative job indices are allowed; for example, run ``webchanges -1`` to only run the last job of your jobs list, or
  ``webchanges --test -2`` to test the second to last job of your jobs list.
* Configuration file is now checked for invalid directives (e.g. typos) when program is run.
* Whenever a HTTP client error (4xx) response is received, in ``--verbose`` mode the content of the response is
  displayed with the error.
* If a newer version of **webchanges** has been released to PyPI, an advisory notice is printed to stdout and
  added to the report footer (if footer is enabled).

Fixed
-----
* The ``html2text`` filter's method ``strip_tags`` was returning HTML character references (e.g. &gt;, &#62;, &#x3e;)
  instead of the corresponding Unicode characters.
* Fixed a rare case when html report would not correctly reconstruct a clickable link from Markdown for items inside
  elements in a list.
* When using the ``--edit`` or ``--edit-config`` command line arguments to edit jobs or configuration files, symbolic
  links are no longer overwritten. Reported by `snowman <https://github.com/snowman>`__ upstream
  `here <https://github.com/thp/urlwatch/issues/604>`__.

Internals
---------
* ``--verbose`` command line argument will now list configuration keys 'missing' from the file, keys for which default
  values have been used.
* ``tox`` testing can now be run in parallel using ``tox --parallel``.
* Additional testing, adding 3 percentage points of coverage to 78%.
* bump2version now follows `PEP440 <https://www.python.org/dev/peps/pep-0440/>`__ and has new documentation in
  the file ``.bumpversion.txt`` (cannot document ``.bumpversion.cfg`` as remarks get deleted at every version bump).
* Added a vendored version of packaging.version.parse() from `Packaging <https://www.pypi.com/project/packaging/>`__
  20.9, released on 2021-02-20, used to check if the version in PyPI is higher than the current one.
* Migrated from unmaintained Python package AppDirs to its friendly fork `platformdirs
  <https://github.com/platformdirs/platformdirs>`__, which is maintained and offers more functionality. Unless used
  by another package, you can uninstall appdirs with ``pip uninstall appdirs``.


Version 3.7
====================
2021-06-27

⚠ Breaking Changes
------------------
* Removed Python 3.6 support to simplify code. Older Python versions are supported for 3 years after being obsoleted by
  a new major release; as Python 3.7 was released on 27 June 2018, the last date of Python 3.6 support was 26 June 2021

Changed
-------
* Improved ``telegram`` reporter now uses MarkdownV2 and preserves most formatting of HTML sites processed by the
  ``html2text`` filter, e.g. clickable links, bolding, underlining, italics and strikethrough

Added
-----
* New filter ``execute`` to filter the data using an executable without invoking the shell (as ``shellpipe`` does)
  and therefore exposing to additional security risks
* New sub-directive ``silent`` for ``telegram`` reporter to receive a notification with no sound (true/false) (default:
  false)
* Github Issues templates for bug reports and feature requests

Fixed
-----
* Job ``headers`` stored in the configuration file (``config.yaml``) are now merged correctly and case-insensitively
  with those present in the job (in ``jobs.yaml``). A header in the job replaces a header by the same name if already
  present in the configuration file, otherwise is added to the ones present in the configuration file.
* Fixed ``TypeError: expected string or bytes-like object`` error in cookiejar (called by requests module) caused by
  some ``cookies`` being read from the jobs YAML file in other formats

Internals
---------
* Strengthened security with `bandit <https://pypi.org/project/bandit/>`__ to catch common security issues
* Standardized code formatting with `black <https://pypi.org/project/black/>`__
* Improved pre-commit speed by using local libraries when practical
* More improvements to type hinting (moving towards testing with `mypy <https://pypi.org/project/mypy/>`__)
* Removed module jobs_browser.py (needed only for Python 3.6)


Version 3.6.1
====================
2021-05-28

Reminder
--------
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.7 was
released on 27 June 2018, the codebase will be streamlined by removing support for Python 3.6 on or after 27 June 2021.

Added
-----
* Clearer results messages for ``--delete-snapshot`` command line argument

Fixed
-----
* First run would fail when creating new ``config.yaml`` file. Thanks to `David <https://github.com/notDavid>`__ in
  issue `#10 <https://github.com/mborsetti/webchanges/issues/10>`__.
* Use same run duration precision in all reports


Version 3.6
====================
2021-05-14

Added
-----
* Run a subset of jobs by adding their index number(s) as command line arguments. For example, run ``webchanges 2 3`` to
  only run jobs #2 and #3 of your jobs list. Run ``webchanges --list`` to find the job numbers. Suggested by `Dan Brown
  <https://github.com/dbro>`__ upstream `here <https://github.com/thp/urlwatch/pull/641>`__. API is experimental and
  may change in the near future.
* Support for ``ftp://`` URLs to download a file from an ftp server

Fixed
-----
* Sequential job numbering (skip numbering empty jobs). Suggested by `Markus Weimar
  <https://github.com/Markus00000>`__ in issue `#9 <https://github.com/mborsetti/webchanges/issues/9>`__.
* Readthedocs.io failed to build autodoc API documentation
* Error processing jobs with URL/URIs starting with ``file:///``

Internals
---------
* Improvements of errors and DeprecationWarnings during the processing of job directives and their inclusion in tests
* Additional testing adding 3 percentage points of coverage to 75%
* Temporary database being written during run is now in memory-first (handled by SQLite3) (speed improvement)
* Updated algorithm that assigns a job to a subclass based on directives found
* Migrated to using the `pathlib <https://docs.python.org/3/library/pathlib.html>`__ standard library


Version 3.5.1
====================
2021-05-06

Fixed
-----
* Crash in ``RuntimeError: dictionary changed size during iteration`` with custom headers; updated testing scenarios
* Autodoc not building API documentation


Version 3.5
====================
2021-05-04

Added
-----
* New sub-directives to the ``strip`` filter:

  * ``chars``: Set of characters to be removed (default: whitespace)
  * ``side``: One-sided removal, either ``left`` (leading characters) or ``right`` (trailing characters)
  * ``splitlines``: Whether to apply the filter on each line of text (true/false) (default: ``false``, i.e. apply to
    the entire data)
* ``--delete-snapshot`` command line argument: Removes the latest saved snapshot of a job from the database; useful
  if a change in a website (e.g. layout) requires modifying filters as invalid snapshot can be deleted and `webchanges`
  rerun to create a truthful diff
* ``--log-level`` command line argument to control the amount of logging displayed by the ``-v`` argument
* ``ignore_connection_errors``, ``ignore_timeout_errors``, ``ignore_too_many_redirects`` and ``ignore_http_error_codes``
  directives now work with ``url`` jobs having ``use_browser: true`` (i.e. using `Pyppeteer`) when running in Python
  3.7 or higher

Changed
-------
* Diff-filter ``additions_only`` will no longer report additions that consist exclusively of added empty lines
  (issue `#6 <https://github.com/mborsetti/webchanges/issues/6>`__, contributed by `Fedora7
  <https://github.com/Fedora7>`__)
* Diff-filter ``deletions_only`` will no longer report deletions that consist exclusively of deleted empty lines
* The job's index number is included in error messages for clarity
* ``--smtp-password`` now checks that the credentials work with the SMTP server (i.e. logs in)

Fixed
-----
* First run after install was not creating new files correctly (inherited from `urlwatch`); now `webwatcher` creates
  the default directory, config and/or jobs files if not found when running (issue `#8
  <https://github.com/mborsetti/webchanges/issues/8>`__, contributed  by `rtfgvb01 <https://github.com/rtfgvb01>`__)
* ``test-diff`` command line argument was showing historical diffs in wrong order; now showing most recent first
* An error is now raised when a ``url`` job with ``use_browser: true`` returns no data due to an HTTP error (e.g.
  proxy_authentication_required)
* Jobs were included in email subject line even if there was nothing to report after filtering with ``additions_only``
  or ``deletions_only``
* ``hexdump`` filter now correctly formats lines with less than 16 bytes
* ``sha1sum`` and ``hexdump`` filters now accept data that is bytes (not just text)
* An error is now raised when a legacy ``minidb`` database is found but cannot be converted because the ``minidb``
  package is not installed
* Removed extra unneeded file from being installed
* Wrong ETag was being captured when a URL redirection took place

Internals
---------
* `Pyppeteer` (``url`` jobs using ``use_browser: true``) now capture and save the ETag
* Snapshot timestamps are more accurate (reflect when the job was launched)
* Each job now has a run-specific unique index_number, which is assigned sequentially when loading jobs, to use in
  errors and logs for clarity
* Improvements in the function chunking text into numbered lines, which used by certain reporters (e.g. Telegram)
* More tests, increasing code coverage by an additional 7 percentage points to 72% (although keyring testing had to be
  dropped due to issues with GitHub Actions)
* Additional cleanup of code and documentation

Known issues
------------
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed
  in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.4.1
====================
2021-04-17

Internals
---------
* Temporary database (``sqlite3`` database engine) is copied to permanent one exclusively using SQL code instead of
  partially using a Python loop

Known issues
------------
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed
  in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.4
====================
2021-04-12

⚠ Breaking Changes
------------------
* Fixed the database from growing unbounded to infinity. Fix only works when running in Python 3.7 or higher and using
  the new, default, ``sqlite3`` database engine. In this scenario only the latest 4 snapshots are kept, and older ones
  are purged after every run; the number is selectable with the new ``--max-snapshots`` command line argument. To keep
  the existing grow-to-infinity behavior, run `webchanges` with ``--max-snapshots 0``.

Added
-----
* ``--max-snapshots`` command line argument sets the number of snapshots to keep stored in the database; defaults to
  4. If set to 0 an unlimited number of snapshots will be kept. Only applies to Python 3.7 or higher and only works if
  the default ``sqlite3`` database is being used.
* ``no_redirects`` job directive (for ``url`` jobs) to disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection
  (true/false). Suggested by `snowman <https://github.com/snowman>`__ upstream `here
  <https://github.com/thp/urlwatch/issues/635>`__.
* Reporter ``prowl`` for the `Prowl <https://prowlapp.com>`__ push notification client for iOS (only). Contributed
  by `nitz <https://github.com/nitz>`__ upstream in PR `633 <https://github.com/thp/urlwatch/pull/633>`__.
* Filter ``jq`` to parse, transform, and extract ASCII JSON data. Contributed by `robgmills
  <https://github.com/robgmills>`__ upstream in PR `626 <https://github.com/thp/urlwatch/pull/626>`__.
* Filter ``pretty-xml`` as an alternative to ``format-xml`` (backwards-compatible with `urlwatch` 2.23)
* Alert user when the jobs file contains unrecognized directives (e.g. typo)

Changed
--------
* Job name is truncated to 60 characters when derived from the title of a page (no directive ``name`` is found in a
  ``url`` job)
* ``--test-diff`` command line argument displays all saved snapshots (no longer limited to 10)

Fixed
-----
* Diff (change) data is no longer lost if `webchanges` is interrupted mid-execution or encounters an error in reporting:
  the permanent database is updated only at the very end (after reports are dispatched)
* ``use_browser: false`` was not being interpreted correctly
* Jobs file (e.g. ``jobs.yaml``) is now loaded only once per run

Internals
---------
* Database ``sqlite3`` engine now saves new snapshots to a temporary database, which is copied over to the permanent one
  at execution end (i.e. database.close())
* Upgraded SMTP email message internals to use Python's `email.message.EmailMessage
  <https://docs.python.org/3/library/email.message.html#email.message.EmailMessage>`__ instead of ``email.mime``
  (obsolete)
* Pre-commit documentation linting using ``doc8``
* Added logging to ``sqlite3`` database engine
* Additional testing increasing overall code coverage by an additional 4 percentage points to 65%
* Renamed legacy module browser.py to jobs_browser.py for clarity
* Renamed class JobsYaml to YamlJobsStorage for consistency and clarity

Known issues
------------
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed
  in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.2.6
===================
2021-03-21

Changed
--------
* Tweaked colors (esp. green) of HTML reporter to work with Dark Mode
* Restored API documentation using Sphinx's autodoc (removed in 3.2.4 as it was not building correctly)

Internal
--------
* Replaced custom atomic_rename function with built-in `os.replace()
  <https://docs.python.org/3/library/os.html#os.replace>`__ (new in Python 3.3) that does the same thing
* Added type hinting to the entire code
* Added new tests, increasing coverage to 61%
* GitHub Actions CI now runs faster as it's set to cache required packages from prior runs

Known issues
------------
* Discovered that upstream (legacy) `urlwatch` 2.22 code has the database growing to infinity; run ``webchanges
  --clean-cache`` periodically to discard old snapshots until this is addressed in a future release
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed
  in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.2
===================
2021-03-08

Added
-----
* Job directive ``note``: adds a freetext note appearing in the report after the job header
* Job directive ``wait_for_navigation`` for URL jobs with ``use_browser: true`` (i.e. using `Pyppeteer`): wait for
  navigation to reach a URL starting with the specified one before extracting content. Useful when the URL redirects
  elsewhere before displaying content you're interested in and `Pyppeteer` would capture the intermediate page.
* command line argument ``--rollback-cache TIMESTAMP``: rollback the snapshot database to a previous time, useful when
  you miss notifications; see `here <https://webchanges.readthedocs.io/en/stable/cli.html#rollback-cache>`__. Does not
  work with database engine ``minidb`` or ``textfiles``.
* command line argument ``--cache-engine ENGINE``: specify ``minidb`` to continue using the database structure used
  in prior versions and `urlwatch` 2. New default ``sqlite3`` creates a smaller database due to data compression with
  `msgpack <https://msgpack.org/index.html>`__ and offers additional features; migration from old minidb database is
  done automatically and the old database preserved for manual deletion.
* Job directive ``block_elements`` for URL jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) (⚠ ignored in Python
  < 3.7) (experimental feature): specify `resource types
  <https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest/ResourceType>`__ (elements) to
  skip requesting (downloading) in order to speed up retrieval of the content; only resource types `supported by
  Chromium <https://developer.chrome.com/docs/extensions/reference/webRequest/#type-ResourceType>`__ are allowed
  (typical list includes ``stylesheet``, ``font``, ``image``, and ``media``). ⚠ On certain sites it seems to totally
  freeze execution; test before use.

Changes
-------
* A new, more efficient indexed database is used and only the most recent saved snapshot is migrated the first time you
  run this version. This has no effect on the ordinary use of the program other than reducing the number of historical
  results from ``--test-diffs`` util more snapshots are captured. To continue using the legacy database format, launch
  with ``database-engine minidb`` and ensure that the package ``minidb`` is installed.
* If any jobs have ``use_browser: true`` (i.e. are using `Pyppeteer`), the maximum number of concurrent threads is set
  to the number of available CPUs instead of the `default
  <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor>`__ to avoid
  instability due to `Pyppeteer`'s high usage of CPU
* Default configuration now specifies the use of Chromium revisions equivalent to Chrome 89.0.4389.72
  for URL jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) to increase stability. Note: if you already have a
  configuration file and want to upgrade to this version, see `here
  <https://webchanges.readthedocs.io/en/stable/advanced.html#using-a-chromium-revision-matching-a-google-chrome-chromium-release>`__.
  The Chromium revisions used now are 'linux': 843831, 'win64': 843846, 'win32': 843832, and 'mac': 843846.
* Temporarily removed code autodoc from the documentation as it was not building correctly

Fixed
-----
* Specifying ``chromium_revision`` had no effect (bug introduced in version 3.1.0)
* Improved the text of the error message when ``jobs.yaml`` has a mistake in the job parameters

Internals
---------
* Removed dependency on ``minidb`` package and are now directly using Python's built-in ``sqlite3``, allowing for better
  control and increased functionality
* Database is now smaller due to data compression with `msgpack <https://msgpack.org/index.html>`__
* Migration from an old schema database is automatic and the last snapshot for each job will be migrated to the new one,
  preserving the old database file for manual deletion
* No longer backing up database to `*.bak` now that it can be rolled back
* New command line argument ``--database-engine`` allows selecting engine and accepts ``sqlite3`` (default),
  ``minidb`` (legacy compatibility, requires package by the same name) and ``textfiles`` (creates a text file of the
  latest snapshot for each job)
* When running in Python 3.7 or higher, jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) are a bit more reliable
  as they are now launched using ``asyncio.run()``, and therefore Python takes care of managing the asyncio event loop,
  finalizing asynchronous generators, and closing the threadpool, tasks that previously were handled by custom code
* 11 percentage point increase in code testing coverage, now also testing jobs that retrieve content from the internet
  and (for Python 3.7 and up) use `Pyppeteer`

Known issues
------------
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed
  in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.1.1
=================
2021-02-08

Fixed
-----
* Documentation was failing to build at https://webchanges.readthedocs.io/


Version 3.1
=================
2021-02-07

Added
-----
* Can specify different values of ``chromium_revision`` (used in jobs with ``use_browser" true``, i.e. using
  `Pyppeteer`) based on OS by specifying keys ``linux``, ``mac``, ``win32`` and/or ``win64``
* If ``shellpipe`` filter returns an error it now shows the error text
* Show deprecation warning if running on the lowest Python version supported (mentioning the 3 years support from the
  release date of the next major version)

Fixed
-----
* ``telegram`` reporter's ``chat_id`` can be numeric (fixes # `610 <https://github.com/thp/urlwatch/issues/610>`__
  upstream by `ramelito <https://github.com/ramelito>`__)

Internals
---------
* First PyPI release with new continuous integration (CI) and continuous delivery (CD) pipeline based on `bump2version
  <https://pypi.org/project/bump2version/>`__, git tags, and `GitHub Actions <https://docs.github.com/en/actions>`__
* Moved continuous integration (CI) testing from Travis to `GitHub Actions <https://docs.github.com/en/actions>`__
* Moved linting (flake8) and documentation build testing from pytest to the `pre-commit
  <https://pre-commit.com>`__ framework
* Added automated pre-commit local testing using `tox <https://tox.readthedocs.io/en/latest/>`__
* Added continuous integration (CI) testing on macOS platform


Version 3.0.3
=============
2020-12-21

⚠ Breaking Changes
------------------
* Compatibility with `urlwatch` 2.22, including the ⚠ breaking change of removing the ability to write custom filters
  that do not take a subfilter as argument (see `here
  <https://urlwatch.readthedocs.io/en/latest/deprecated.html#filters-without-subfilters-since-2-22>`__ upstream)
* Inadvertently released as a PATCH instead of a MAJOR release as it should have been under `Semantic Versioning
  <https://semver.org/spec/v2.0.0.html#semantic-versioning-200>`__ rules given the incompatible API change upstream (see
  discussion `here <https://github.com/thp/urlwatch/pull/600#issuecomment-754525630>`__ upstream)

Added
-----
* New job sub-directive ``user_visible_url`` to replace the URL in reports, useful e.g. if the watched URL is a REST
  API endpoint but you want to link to the webpage instead (# `590 <https://github.com/thp/urlwatch/pull/590>`__
  upstream by `huxiba <https://github.com/huxiba>`__)

Changed
-------
* The Markdown reporter now supports limiting the report length via the ``max_length`` parameter of the ``submit``
  method. The length limiting logic is smart in the sense that it will try trimming the details first, followed by
  omitting them completely, followed by omitting the summary. If a part of the report is omitted, a note about this is
  added to the report. (# `572 <https://github.com/thp/urlwatch/issues/572>`__ upstream by `Denis Kasak
  <https://github.com/dkasak>`__)

Fixed
-----
* Make imports thread-safe. This might increase startup times a bit, as dependencies are imported on boot instead of
  when first used, but importing in Python is not (yet) thread-safe, so we cannot import new modules from the parallel
  worker threads reliably (# `559 <https://github.com/thp/urlwatch/issues/559>`__ upstream by `Scott MacVicar
  <https://github.com/scottmac>`__)
* Write Unicode-compatible YAML files

Internals
---------
* Upgraded to use of `subprocess.run <https://docs.python.org/3/library/subprocess.html#subprocess.run>`__


Version 3.0.2
=============
2020-12-06

Fixed
-----
* Logic error in reading ``EDITOR`` environment variable (# `1 <https://github.com/mborsetti/webchanges/issues/1>`__
  contributed by `MazdaFunSun <https://github.com/mazdafunsunn>`__)


Version 3.0.1
=============
2020-12-05

Added
-----
* New ``format-json`` sub-directive ``sort_keys`` sets whether JSON dictionaries should be sorted (defaults to false)
* New ``webhook_markdown`` reporter for services such as Mattermost, which expects Markdown-formatted text
* Code autodoc, highlighting just how badly the code needs documentation!
* Output from ``diff_tool: wdiff`` is colorized in html reports
* Reports now show date/time of diffs when using an external ``diff_tool``

Changed and deprecated
----------------------
* Reporter ``slack`` has been renamed to ``webhook`` as it works with any webhook-enabled service such as Discord.
  Updated documentation with Discord example. The name ``slack``, while deprecated and in line to be removed in a future
  release, is still recognized.
* Improvements in report colorization code

Fixed
-----
* Fixed ``format-json`` filter from unexpectedly reordering contents of dictionaries
* Fixed documentation for ``additions_only`` and ``deletions_only`` to specify that value of true is required
* No longer creating a config directory if command line contains both ``--config`` and ``--urls``. Allow running on
  read-only systems (e.g. using redis or a database cache residing on a writeable volume)
* Deprecation warnings now use the ``DeprecationWarning`` category, which is always printed
* All filters take a subfilter (# `600 <https://github.com/thp/urlwatch/pull/600>`__ upstream by `Martin Monperrus
  <https://github.com/monperrus>`__)


Version 3.0
=============
2020-11-12

Milestone
---------
Initial release of `webchanges` as a reworked fork of `urlwatch` 2.21

Added
-----
Relative to `urlwatch` 2.21:

* If no job ``name`` is provided, the title of an HTML page will be used for a job name in reports
* The Python ``html2text`` package (used by the ``html2text`` filter, previously known as ``pyhtml2text``) is now
  initialized with the following purpose-optimized non-default `options
  <https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options>`__: unicode_snob = True,
  body_width = 0, single_line_break = True, and ignore_images = True
* The output from ``html2text`` filter is reconstructed into HTML (for html reports), preserving basic formatting
  such as bolding, italics, underlining, list bullets, etc. as well as, most importantly, rebuilding clickable links
* HTML formatting uses color (green or red) and strikethrough to mark added and deleted lines
* HTML formatting is radically more legible and useful, including long lines wrapping around
* HTML reports are now rendered correctly by email clients who override stylesheets (e.g. Gmail)
* Filter ``format-xml`` reformats (pretty-prints) XML
* ``webchanges --errors`` will run all jobs and list all errors and empty responses (after filtering)
* Browser jobs now recognize ``cookies``, ``headers``, ``http_proxy``, ``https_proxy``, and ``timeout`` sub-directives
* The revision number of Chromium browser to use can be selected with ``chromium_revision``
* Can set the user directory for the Chromium browser with ``user_data_dir``
* Chromium can be directed to ignore HTTPs errors with ``ignore_https_errors``
* Chromium can be directed as to when to consider a page loaded with ``wait_until``
* Additional command line arguments can be passed to Chromium with ``switches``
* New ``additions_only`` directive to report only added lines (useful when monitoring only new content)
* New ``deletions_only`` directive to report only deleted lines
* New ``contextlines`` directive to set the number of context lines in the unified diff
* Support for Python 3.9
* Backward compatibility with `urlwatch` 2.21 (except running on Python 3.5 or using ``lynx``, which is replaced by
  internal ``html2text`` filter)

Changed and deprecated
----------------------
Relative to `urlwatch` 2.21:

* Navigation by full browser is now accomplished by specifying the ``url`` and adding the ``use_browser: true``
  directive. The `navigate` directive has been deprecated for clarity and will trigger a warning; it will be removed in
  a future release
* The name of the default program configuration file has been changed to ``config.yaml``; if at program launch
  ``urlwatch.yaml`` is found and no ``config.yaml`` exists, it is copied over for backward-compatibility.
* In Windows, the location of config files has been moved to ``%USERPROFILE%\Documents\webchanges``
  where they can be more easily edited (they are indexed there) and backed up
* The ``html2text`` filter defaults to using the Python ``html2text`` package (with optimized defaults) instead of
  ``re``
* ``keyring`` Python package is no longer installed by default
* ``html2text`` and ``markdown2`` Python packages are installed by default
* Installation of Python packages required by a feature is now made easier with pip extras (e.g. ``pip install -U
  webchanges[ocr,pdf2text]``)
* The name of the default job's configuration file has been changed to ``jobs.yaml``; if at program launch ``urls.yaml``
  is found and no ``jobs.yaml`` exists, it is copied over for backward-compatibility
* The ``html2text`` filter's ``re`` method has been renamed ``strip_tags``, which is deprecated and will trigger a
  warning
* The ``grep`` filter has been renamed ``keep_lines_containing``, which is deprecated and will trigger a warning; it
  will be removed in a future release
* The ``grepi`` filter has been renamed ``delete_lines_containing``, which is deprecated and will trigger a warning; it
  will be removed in a future release
* Both the ``keep_lines_containing`` and ``delete_lines_containing`` accept ``text`` (default) in addition to ``re``
  (regular expressions)
* ``--test`` command line argument is used to test a job (formerly ``--test-filter``, deprecated and will be removed in
  a future release)
* ``--test-diff`` command line argument is used to test a jobs' diff (formerly ``--test-diff-filter``, deprecated and
  will be removed in a future release)
* ``-V`` command line argument added as an alias to ``--version``
* If a filename for ``--jobs``, ``--config`` or ``--hooks`` is supplied without a path and the file is not present in
  the current directory, `webchanges` now looks for it in the default configuration directory
* If a filename for ``--jobs`` or ``--config`` is supplied without a '.yaml' suffix, `webchanges` now looks for one with
  such a suffix
* In Windows, ``--edit`` defaults to using built-in notepad.exe if %EDITOR% or %VISUAL% are not set
* When using ``--job`` command line argument, if there's no file by that name in the specified directory will look in
  the default one before giving up.
* The use of the ``kind`` directive in ``jobs.yaml`` configuration files has been deprecated (but is, for now, still
  used internally); it will be removed in a future release
* The ``slack`` webhook reporter allows the setting of maximum report length (for, e.g., usage with Discord) using the
  ``max_message_length`` sub-directive
* Legacy lib/hooks.py file no longer supported. ``hooks.py`` needs to be in the same directory as the configuration
  files.
* The database (cache) file is backed up at every run to `*.bak`
* The mix of default and optional dependencies has been updated (see documentation) to enable "Just works"
* Dependencies are now specified as PyPI `extras
  <https://stackoverflow.com/questions/52474931/what-is-extra-in-pypi-dependency>`__ to simplify their installation
* Changed timing from `datetime <https://docs.python.org/3/library/datetime.html>`__ to `timeit.default_timer
  <https://docs.python.org/3/library/timeit.html#timeit.default_timer>`__
* Upgraded concurrent execution loop to `concurrent.futures.ThreadPoolExecutor.map
  <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor.map>`__
* Reports' elapsed time now always has at least 2 significant digits
* Expanded (only slightly) testing
* Using flake8 to check PEP-8 compliance and more
* Using coverage to check unit testing coverage
* Upgraded Travis CI to Python 3.9 from 3.9-dev and cleaned up pip installs

Removed
-------
Relative to `urlwatch` 2.21:

* The ``html2text`` filter's ``lynx`` method is no longer supported; use ``html2text`` instead
* Python 3.5 (obsoleted by 3.6 on December 23, 2016) is no longer supported

Fixed
-----
Relative to `urlwatch` 2.21:

* The ``html2text`` filter's ``html2text`` method defaults to Unicode handling
* HTML href links ending with spaces are no longer broken by ``xpath`` replacing spaces with `%20`
* Initial config file no longer has directives sorted alphabetically, but are saved logically (e.g. 'enabled' is always
  the first sub-directive)
* The presence of the ``data`` directive in a job would force the method to POST preventing PUTs

Security
--------
Relative to `urlwatch` 2.21:

* None

Documentation changes
---------------------
Relative to `urlwatch` 2.21:

* Complete rewrite of the documentation

Known bugs
----------
* Documentation could be more complete
* Almost complete lack of inline docstrings in the code
