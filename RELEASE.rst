.. Categories used (in order):
   ⚠ Breaking Changes for changes that break existing functionality.
   Added for new features.
   Changed for changes in existing functionality.
   Deprecated for soon-to-be removed features.
   Removed for now removed features.
   Fixed for any bug fixes.
   Security in case of vulnerabilities.
   Internals for changes that don't affect users.

⚠ Breaking Changes
------------------
* Only the most recent saved snapshots is migrated the first time you run this version due to an upgrade to the
  database. This has no effect on the ordinary use of the program othern than reducing the number of historical results
  from ``--test-diffs`` util more snapshots are captured.

Added
-----
* ``note`` job directive to add a freetext note appearing in the report after the job header
* ``wait_for_navigate`` directive for URL jobs with ``use_browser: true`` (i.e. using Pyppeteer) to wait for
  navigation to reach a URL starting with the specified one before extracting content. Useful when the URL redirects
  elsewhere before displaying content you're interested in and Pyppeteer captures the intermediate page.
* ``block_elements`` directive (⚠ only for Python >= 3.7) for URL jobs with ``use_browser: true`` (i.e. using
  Pyppeteer) to specify `resource types
  <https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest/ResourceType>`__ (elements) to
  skip requesting (downloading) in order to speed up retrieval of the content.  Only resource types `supported by
  Chromium <https://developer.chrome.com/docs/extensions/reference/webRequest/#type-ResourceType>`__ are allowed.
  Typical list includes ``stylesheet``, ``font``, ``image``, and ``media`` but use with caution.

Changes
-------
* If any jobs have ``use_browser: true`` (i.e. are using Pyppeteer), the maximum number of concurrent threads is the
  number of available CPUs instead of the `default
  <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor>`__ to avoid
  instability due to Pyppeteer's high usage of CPU

Fixed
-----
* Specifying ``chromium_revision`` had no effect (bug introduced in version 3.1.0)
* Improved the text of the error message when jobs.yaml has a mistake in the job parameters

Internals
---------
* Removed dependency on ``minidb`` package dependency in favor for Python's built-in ``sqlite3``
* Database is now smaller due to data compression with `msgpack <https://msgpack.org/index.html>`__; will automatically
  detect if an old schema database is found and migrate the last snapshot to the new one
* New command line argument ``--database-engine`` allows selecting engine and accepts ``sqlite3`` (default),
  ``minidb`` (legacy, requiring package by the same name) and ``textfiles`` (creates text files with the latest
  snapshot)
* When running in Python 3.7 or higher, jobs with ``use_browser: true`` (i.e. using Pyppeteer) are a bit more reliable
  as they are now launched using ``asyncio.run()``, and therefore Python takes care of managing the asyncio event loop,
  finalizing asynchronous generators, and closing the threadpool, tasks that previously were handled by custom code
* Additional testing to include test actual jobs that use Pyppeteer (Python 3.7 or higher) and to retrieve content from
  the internet
