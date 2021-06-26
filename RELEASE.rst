Reminder
--------
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.7 was
released on 27 June 2018, the codebase will be streamlined by removing support for Python 3.6 on or after 27 June 2021.

Changed
-------
* Improved ``telegram`` reporter now uses MarkdownV2 and preserves most formatting of HTML sites processed by the
  ``html2text`` filter, e.g. clickable links, bolding, underlining, italics and strikethrough.

Added
-----
* New filter ``execute`` to filter the data using an executable without invoking the shell (as ``shellpipe`` does)
  and therefore exposing to additional security risks
* New sub-directive ``silent`` for ``telegram`` reporter to receive a notification with no sound (true/false) (default:
  false)
* Github Issues templates for bug reports and feature requests

Fixed
-----
* Job ``headers`` stored in the configuration file (``config.yaml``) are now merged correctly and case-insensitively
  with those present in the job (in ``jobs.yaml``). A header in the job replaces a header by the same name if already
  present in the configuration file, otherwise is added to the ones present in the configuration file.
* Fixed ``TypeError: expected string or bytes-like object`` error in cookiejar (called by requests module) caused by
  some ``cookies`` being read from the jobs YAML file in other formats

Internals
---------
* Strengthened testing with `bandit <https://pypi.org/project/bandit/>`__ to catch common security issues
* Standardized code formatting with `black <https://pypi.org/project/black/>`__
* Improved pre-commit speed by using local libraries when practical
* More improvements to type hinting (moving towards testing with `mypy <https://pypi.org/project/mypy/>`__)
