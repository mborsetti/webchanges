⚠ Breaking Changes
------------------
* Due to a fix to the ``html2text`` filter (see below), the first time you run this new version **you may get a change
  report with deletions and additions of lines that look identical. This will happen one time only** and will prevent
  future such change reports.

Added
-----
* You can now run the command line argument ``--test`` without specifying a JOB; this will run a check of the config and
  job files for syntax errors.
* Error messages for url jobs failing with HTTP reason codes of 400 and higher now include any text returned by the
  website (e.g. "Rate exceeded.", "upstream request timeout", etc.). Not implemented in jobs with ``use_browser: true``
  due to limitations in Playwright.
* New command line argument ``--check-new`` to check if a new version of **webchanges** is available.

Changed
-------
* On Linux and macOS systems, for security reasons we now check that the hooks file **and** the directory it is located
  in are **owned** and **writeable** by **only** the user who is running the job (and not by its group or by other
  users), identical to what we do with the jobs file if any job uses the ``shellpipe`` filter. An
  explanatory ImportWarning message will be issued if the permissions are not correct and the import of the hooks module
  is skipped.
* The command line argument ``-v`` or ``--verbose`` now shows reduced verbosity logging output while ``-vv`` (or
  ``--verbose --verbose``) shows full verbosity.

Fixed
-----
* The ``html2text`` filter is no longer retaining any spaces found in the HTML after *the end of the text* on a line,
  which are not displayed in HTML and therefore a bug in the conversion library used. This was causing a change report
  to be issued whenever the number of such invisible spaces changed.
* The ``cookies`` directive was not adding cookies correctly to the header for jobs with ``browser: true``.
* The ``wait_for_timeout`` job directive was not accepting integers (only floats). Reported by `Markus Weimar
  <https://github.com/Markus00000>`__ in `#39 <https://github.com/mborsetti/webchanges/issues/39>`__.
* Improved the usefulness of the message of FileNotFoundError exceptions in filters ``execute`` and  ``shellpipe``
  and in reporter ``run_command``.
* Fixed an issue in the legacy parser used by the ``xpath`` filter which under specific conditions caused more html
  than expected to be returned.
* Fixed how we determine if a new version has been released (due to an API change by PyPI).
* When adding custom JobBase classes through the hooks file, their configuration file entries are no longer causing
  warnings to be issued as unrecognized directives.

Internals
---------
* Changed bootstrapping logic so that when using ``-vv`` the logs will include messages relating to the registration of
  the various classes.
* Improved execution speed of certain informational command line arguments.
* Updated the vendored version of ``packaging.version.parse()`` to 21.3, released on 2021-11-27.
* Changed the import logic for the ``packaging.version.parse()`` function so that if ``packaging`` is found to be
  installed, it will be imported from there instead of from the vendored module.
* ``urllib3`` is now an explicit dependency due to the refactoring of the ``requests`` package (we previously used
  ``requests.packages.urllib3``). Has no effect since ``urllib3`` is already being installed as a dependency of
  ``requests``.
* Added ``typed.py`` file to implement `PEP 561 <https://peps.python.org/pep-0561/>`__.
