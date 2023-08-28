Notice
------
Support for Python 3.8 will be removed on or about 5 October 2023. A reminder that older Python versions are
supported for 3 years after being obsoleted by a new major release (i.e. about 4 years since their original release).

Added
-----
* Reports have a new ``separate`` configuration option to split reports into one-per-job.
* ``url`` jobs without ``use_browser`` have a new ``retries`` directive to specify the  number of times to retry a
  job that errors before giving up. Using ``retries: 1`` or higher will often solve the ``('Connection aborted.',
  ConnectionResetError(104, 'Connection reset by peer'))`` error received from a misconfigured server at the first
  connection.
* ``remove_duplicates`` filter has a new ``adjacent`` sub-directive to de-duplicate non-adjacent lines or items.
* ``css`` and ``xpath`` have a new ``sort`` subfilter to sort matched elements lexicographically.
* Command line arguments:

  * New ``--footnote`` to add a custom footnote to reports.
  * New ``--change-location`` to keep job history when the ``url`` or ``command`` changes.
  * ``--gc-database`` and ``--clean-database`` now have optional argument ``RETAIN-LIMIT`` to allow increasing
    the number of retained snapshots from the default of 1.
  * New ``--detailed-versions`` to display detailed version and system information, inclusive of the versions of
    dependencies and, in certain Linux distributions (e.g. Debian), of system libraries. It also reports available
    memory and disk space.

Changed
-------
* ``command`` jobs now have improved error reporting which includes the error text from the failed command.
* ``--rollback-database`` now confirms the date (in ISO-8601 format) to roll back the database to and, if
  **webchanges** is being run in interactive mode, the user will be asked for positive confirmation before proceeding
  with the un-reversible deletion.

Internals
---------
* Added `bandit <https://github.com/PyCQA/bandit>`__ testing to improve the security of code.
* ``headers`` are now turned into strings before being passed to Playwright (addresses the error
  ``playwright._impl._api_types.Error: extraHTTPHeaders[13].value: expected string, got number``).
* Exclude tests from being recognized as package during build (contributed by `Max
  <https://github.com/aragon999>`__ in `#54 <https://github.com/mborsetti/webchanges/pull/54>`__).
* Refactored and cleaned up some tests.
* Initial testing with Python 3.12.0-rc1, but a reported bug in ``typing.TypeVar`` prevents the ``pyee`` dependency
  of ``playwright`` from loading, causing a failure. Awaiting for fix in Python 3.12.0-rc2 to retry.
