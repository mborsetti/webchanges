Added
-----
* Support for Python 3.11. Please note that the dependency ``lxml`` may fail to install on Windows due to
  `this <https://bugs.launchpad.net/lxml/+bug/1977998>`__ bug and that therefore for now **webchanges** can only be
  run in Python 3.10 on Windows.

Removed
-------
* Support for Python 3.7. As a reminder, older Python versions are supported for 3 years after being obsoleted by a new
  major release; support for Python 3.8 will be removed on or about 5 October 2023.

Fixed
-----
* Job sorting for reports is now case-insensitive.
* Documentation on how to anonymously monitor GitHub releases (due to changes in GitHub) (contributed by `Luis Aranguren
  <https://github.com/mercurytoxic>`__ `upstream <https://github.com/thp/urlwatch/issues/723>`__).
* Handling of ``method`` subfilter for filter ``html2text`` (reported by `kongomondo <https://github.com/kongomondo>`__
  `upstream <https://github.com/thp/urlwatch/issues/588>`__).
