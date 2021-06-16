Reminder
--------
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.7 was
released on 27 June 2018, the codebase will be streamlined by removing support for Python 3.6 on or after 27 June 2021.

Changed
-------
* Improved ``telegram`` reporter to use MarkdownV2 (some formatting of HTML sites is now preserved)

Added
-----
* New filter ``execute`` to run an executable to filter the data without launching the shell (as ``shellpipe`` does)
  and therefore exposing to additional security risks.
* New sub-directive ``silent`` for ``telegram`` reporter to receive a notification with no sound (true/false) (default:
  false)

Fixed
-----
* Job ``headers`` stored in the configuration are now merged correctly and case-insensitively with those present in
  the job (in ``jobs.yaml``). A header in the job replaces a header by the same name already present in the
  configuration file (``config.yaml``) or is added to the ones present in the configuration file.
* ``TypeError: expected string or bytes-like object`` error in cookiejar (called by requests module) caused by some
  ``cookies`` being read from the jobs YAML file in other formats
