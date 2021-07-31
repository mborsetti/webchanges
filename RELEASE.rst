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
* If a newer version of :program:`webchanges` has been released to PyPi, an advisory notice is printed to stdout and
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
  20.9, released on 2021-02-20, used to check if the version in PyPi is higher than the current one.
* Migrated from unmaintained Python package AppDirs to its friendly fork `platformdirs
  <https://github.com/platformdirs/platformdirs>`__, which is maintained and offers more functionality. Unless used
  by another package, you can uninstall appdirs with ``pip uninstall appdirs``.
