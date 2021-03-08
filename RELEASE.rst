.. Categories used (in order):
   ⚠ Breaking Changes for changes that break existing functionality.
   Added for new features.
   Changed for changes in existing functionality.
   Deprecated for soon-to-be removed features.
   Removed for now removed features.
   Fixed for any bug fixes.
   Security in case of vulnerabilities.
   Internals for changes that don't affect users.

Added
-----
* Job directive ``note``: adds a freetext note appearing in the report after the job header
* Job directive ``wait_for_navigation`` for URL jobs with ``use_browser: true`` (i.e. using Pyppeteer): wait for
  navigation to reach a URL starting with the specified one before extracting content. Useful when the URL redirects
  elsewhere before displaying content you're interested in and Pyppeteer would capture the intermediate page.
* Command line switch ``--rollback-cache TIMESTAMP``: rollback the snapshot database to a previous time, useful when
  you miss notifications; see `here <https://webchanges.readthedocs.io/en/stable/cli.html#rollback-cache>`__
* Command line switch ``--cache-engine ENGINE``: specify ``minidib`` to continue using the database structure used
  in prior versions and `urlwatch` 2.  Default ``sqlite3`` creates a smaller database due to data compression with
  `msgpack <https://msgpack.org/index.html>`__; migration from old minidb database is done automatically and the old
  database preserved for manual deletion
* Job directive ``block_elements`` for URL jobs with ``use_browser: true`` (i.e. using Pyppeteer) (⚠ ignored in Python
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
  results from ``--test-diffs`` util more snapshots are captured.  To continue using the legacy database format, launch
  with ``database-engine minidb`` and ensure that the package ``minidb`` is installed.
* If any jobs have ``use_browser: true`` (i.e. are using Pyppeteer), the maximum number of concurrent threads is set to
  the number of available CPUs instead of the `default
  <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor>`__ to avoid
  instability due to Pyppeteer's high usage of CPU
* Default configuration now specifies the use of Chromium revisions equivalent to Chrome 89.0.4389.72 827102
  for URL jobs with ``use_browser: true`` (i.e. using Pyppeteer) to increase stability. Note: if you already have a
  configuration file and want to upgrade to this version, see `here
  <https://webchanges.readthedocs.io/en/stable/advanced.html#using-a-chromium-revision-matching-a-google-chrome-chromium-release>`__
  The Chromium revisions used now are 'linux': 843831, 'win64': 843846, 'win32': 843832, and 'macos': 843846.
* Temporarily removed code autodoc from the documentation as it's wasn't building correctly

Fixed
-----
* Specifying ``chromium_revision`` had no effect (bug introduced in version 3.1.0)
* Improved the text of the error message when ``jobs.yaml`` has a mistake in the job parameters

Internals
---------
* Removed dependency on ``minidb`` package and are now directly using Python's built-in ``sqlite3`` without additional
  layer allowing for better control and increased functionality
* Database is now smaller due to data compression with `msgpack <https://msgpack.org/index.html>`__
* An old schema database is automatically detected and the last snapshot for each job will be migrated to the new one,
  preserving the old database file for manual deletion
* No longer backing up database to `*.bak` (introduced in version 3.0.0) now that it can be rolled back
* New command line argument ``--database-engine`` allows selecting engine and accepts ``sqlite3`` (default),
  ``minidb`` (legacy compatibility, requires package by the same name) and ``textfiles`` (creates a text file of the
  latest snapshot for each job)
* When running in Python 3.7 or higher, jobs with ``use_browser: true`` (i.e. using Pyppeteer) are a bit more reliable
  as they are now launched using ``asyncio.run()``, and therefore Python takes care of managing the asyncio event loop,
  finalizing asynchronous generators, and closing the threadpool, tasks that previously were handled by custom code
* 11 percentage point increase in code testing coverage, now also testing jobs that retrieve content from the internet
  and (for Python 3.7 and up) use Pyppeteer

Known issues
------------
* ``url`` jobs with ``use_browser: true`` (i.e. using Pyppeteer) will at times display the below error message in stdout
  (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed in the
  future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``
