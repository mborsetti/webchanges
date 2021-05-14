Added
-----
* Run a subset of jobs by adding their index number(s) as command line arguments. For example, run ``webchanges 2 3`` to
  only run jobs #2 and #3 of your jobs list. Run ``webchanges --list`` to find the job numbers. Suggested by `Dan Brown
  <https://github.com/dbro>`__ upstream `here <https://github.com/thp/urlwatch/pull/641>`__.  API is experimental and
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

Known issues
------------
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed
  in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``
