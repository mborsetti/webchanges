Notice
------
Support for Python 3.8 will be removed on or about 5 October 2023. Older Python versions are supported for 3 years
after being obsoleted by a new major release.

Added
-----
* New ``adjacent`` sub-directive to the ``remove_duplicates`` filter enables the de-duplication of non-adjacent lines
  or items.
* New ``retries`` directive for ``url`` jobs without ``use_browser`` sets the number of times to retry a url before
  giving up. Using ``retries: 1`` or higher will often solve the ``('Connection aborted.', ConnectionResetError(104,
  'Connection reset by peer'))`` error received from a misconfigured server at the first connection.
* ``css`` and ``xpath`` filters now accept a ``sort`` subfilter to sort matched elements lexicographically.
* New ``separate`` configuration option for reporters to split reports into one-per-job.
* ``command`` jobs now have improved error reporting which includes the error text from the failed command.
* Command line arguments:

  * New ``--footnote`` adds a custom footnote to reports.
  * New ``--change-location`` allows to keep job history when the ``url`` or ``command changes``.
  * ``--gc-database`` and ``--clean-database`` now have optional argument ``RETAIN-LIMIT`` to to allow increasing
    the number of old snapshots to retain when cleaning up the database for the default of 1.
  * New ``--detailed-versions`` displays detailed version and system information inclusive of the versions of
    dependencies and, in certain Linux distributions (e.g. Debian), of dependency system libraries. Also reports
    available memory and disk space.

Changed
-------
* ``--rollback-database`` now confirms the date (in ISO-8601 format) to roll back the database to and, if
  **webchanges** is being run in interactive mode, will ask for human confirmation before proceeding with the
  unrecoverable deletion.

Internals
---------
* Added `bandit <https://github.com/PyCQA/bandit>`__ testing to improve the security of code.
* ``headers`` are now turned into strings before being passed to Playwright (addresses the error
  ``playwright._impl._api_types.Error: extraHTTPHeaders[13].value: expected string, got number``).
* Exclude tests from being recognized as package during build (contributed by `Max
  <https://github.com/aragon999>`__ in `#54 <https://github.com/mborsetti/webchanges/pull/54>`__).
* Refactored and cleaned up some tests.
* Initial testing with Python 3.12, but a reported bug in 3.12.0-rc1 ``typing.TypeVar`` prevents ``pyee`` dependency
  of ``playwright`` from loading; awaiting for 3.12.0-rc2.
