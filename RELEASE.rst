Added
-----
* Support for Python 3.11.

Removed
-------
* Support for Python 3.7. As a reminder, older Python versions are supported for 3 years after being obsoleted by a new
  major release; support for Python 3.8 will be removed on or about 5 October 2023.

Fixed
-----
* Job sorting for reports is now case-insensitive.
* Documentation on how to anonymously monitor GitHub releases (due to changes in GitHub) (contributed by `Luis Aranguren
  <https://github.com/mercurytoxic>`__ `upstream <https://github.com/thp/urlwatch/issues/723>`__).

Internals
---------
* Jobs base class now has a ``__is_browser__`` attribute, which can be used with custom hooks to identify jobs that run
  a browser so they can be executed in the correct parallel processing queue.
* Fixed static typing to conform to the latest mypy checks.
* Extended type checking to testing scripts.
