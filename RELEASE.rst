Added
-----
* URL jobs with ``use_browser: true`` that receive an error HTTP status code from the server will now include the text
  returned by the website in the error message (e.g. "Rate exceeded.", "upstream request timeout", etc.), except for
  HTTP status code 404 - Not Found.

Changed
-------
* The command line argument ``--jobs`` used to specify a jobs file will now accept a `glob pattern
  <https://en.wikipedia.org/wiki/Glob_(programming)>`__, e.g. wildcards, to specify multiple files. If more than one
  file matches the pattern, their contents will be concatenated before a job list is built.  Useful e.g. if you have
  multiple jobs files that run on different schedules and you want to clean the snapshot database of URLs/commands no
  longer monitored ("garbage collect") using ``--gc-cache``.
* The command line argument ``--list`` will now list the full path of the jobs file(s).
* Traceback information for Python Exceptions is suppressed by default. Use the command line argument ``--verbose``
  (or ``-v``) to display it.

Fixed
-----
* Fixed ``Unicode strings with encoding declaration are not supported.`` error in the ``xpath`` filter using
  ``method: xml`` under certain conditions (MacOS only). Reported by `jprokos <https://github.com/jprokos>`__ in `#42
  <https://github.com/mborsetti/webchanges/issues/42>`__.

Internals
---------
* The source distribution is now available on PyPI to support certain packagers like ``fpm``.
* Improved handling and reporting of Playwrigt browser errors (for URL jobs with ``use_browser: true``).
