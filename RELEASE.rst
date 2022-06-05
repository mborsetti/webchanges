⚠ Breaking Changes
------------------
* Due to a fix to the ``html2text`` filter (see below), the first time you run this new version **you may get a change
  report with deletions and additions of lines that look identical. This will happen one time only**.

Added
-----
* You can now run the command line argument ``--test`` without specifying a JOB to check the config and job files for
  syntax errors.
* Improved error messages for url jobs failing due to HTTP reason codes of 400 and higher, to include any text returned
  by the website (e.g. "Rate exceeded.", "upstream request timeout", etc.).  Not implemented in jobs with
  ``use_browser: true`` due to limitations in Playwright.
* New command line argument ``--check-new`` to check if a new version is available.

Changed
-------
* On Linux and macOS systems, for security reasons we now check that the hooks file **and** the directory it is located
  in are **owned** and **writeable** by **only** the user who is running the job (and not by its group or by other
  users), identical to what we do with the jobs file if any job uses the ``shellpipe`` filter. An ImportWarning message
  will be issued if the permissions are not correct and the hooks module is therefore not imported.
* The command line argument ``-v`` or ``--verbose`` has reduced verbose output while the new ``-vv`` has full verbosity.

Fixed
-----
* The ``html2text`` filter is no longer retaining any eventual spaces found in the HTML after *the end of the text* on
  a line, which are not displayed in HTML and therefore a bug in the conversion library used. This was causing a change
  report to be issued whenever the number of such invisible spaces changed.
* For job with ``browser: true``, the ``cookies`` directive did not add cookies correctly to the header.
* Configuration file entries relating to job kinds declared in custom JobBase classes in the hooks file no longer issue
  the warning of being unrecognized and potential typos.
* For filters ``execute`` and  ``shellpipe`` and for  reporter ``run_command`` the message of the FileNotFoundError
  exception is more descriptive and helpful.
* The ``wait_for_timeout`` job directive was not accepting integers (only floats). Reported by `Markus Weimar
  <https://github.com/Markus00000>`__ in `#39 <https://github.com/mborsetti/webchanges/issues/39>`__.
* Fixed an issue in the parser used by the ``xpath`` ``filter`` that under specific conditions caused more html than
  expected to be returned.
* Fixed how we determine if a new version has been released due to a change in the data received from PyPi.

Internals
---------
* ``urllib3`` is now an explicit dependency due to the refactoring of the requests package (we previously used
  ``requests.packages.urllib3``). Has no effect since ``urllib3`` is already being installed as a dependency of
  ``requests``.
* Updated the vendored version of ``packaging.version.parse()`` to 21.3, released on 2021-11-27.
* Changed the import logic so if packaging is found to be installed, its ``packaging.version.parse()`` function will be
  used instead of the vendored one.
* Changed loading logic so that with ``-vv`` registration of internal classes shows up in the logs.
* Improved execution speed of certain command line arguments.
* Added typed.py file to implement `PEP 561 <https://peps.python.org/pep-0561/>`__.
