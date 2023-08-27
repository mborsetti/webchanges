Notice
------
Support for Python 3.8 will be removed on or about 5 October 2023 as older Python versions are supported for 3
years after being obsoleted by a new major release.

Added
-----
* New ``adjacent`` sub-directive to the ``remove_duplicates`` filter, enabling the de-duplication of non-adjacent lines
  or items.
* New ``--detailed-versions`` command line argument to display detailed version information, inclusive of those of PyPi
  dependencies and, in certain Linux distributions (e.g. Debian), of dependency libraries. Also reports available
  memory and disk space.
* New ``retries`` directive for ``url`` jobs without ``use_browser`` to set the number of times to retry a url before
  giving up. Using ``retries: 1`` or higher will often solve the ``('Connection aborted.', ConnectionResetError(104,
  'Connection reset by peer'))`` error received initially from a misconfigured server.
* ``css`` and ``xpath`` filters now accept a ``sort`` subfilter to sort matched elements lexicographically.
* Improved error reporting for ``command`` jobs includes the error text from the failed command.

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
