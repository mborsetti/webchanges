Added
-----
* Run a subset of jobs by adding their index number(s) as command line arguments. For example, run ``webchanges 2 3`` to
  only run jobs #2 and #3 of your job list. Run ``webchanges --list`` to find the job numbers. Suggested by `dbro
  <https://github.com/dbro>`__ upstream `here <https://github.com/thp/urlwatch/pull/641>`__.
* Support for ``ftp://`` URLs to download a file from an ftp server

Fixed
-----
* Readthedocs.io failed to build autodoc API documentation
* Error processing jobs with URL/URIs starting with ``file:///``

Internals
---------
* Improvements of errors and DeprecationWarnings during the processing of job directives and their inclusion in tests
* Updated algorithm that assigns a job to a subclass based on directives found
* Migrated to use of the `pathlib <https://docs.python.org/3/library/pathlib.html>`__ standard library
* Temporary database being written during run is now in memory-first (handled by SQLite3)
