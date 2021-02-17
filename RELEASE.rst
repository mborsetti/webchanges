.. Categories used (in order):
   ⚠ Breaking Changes for changes that break existing functionality.
   Added for new features.
   Changed for changes in existing functionality.
   Deprecated for soon-to-be removed features.
   Removed for now removed features.
   Fixed for any bug fixes.
   Security in case of vulnerabilities.
   Internals for changes that don't affect users.

Fixed
-----
* Specifying ``chromium_revision`` had no effect (bug introduced in Version 3.1.0)
* Improved error message when there's a mistake in the job parameters in jobs.yaml

Added
-----
* Job key ``note`` will print the text after the job header in the report
* New ``wait_for_navigate`` key for jobs with ``use_browser: true`` (i.e. using Pyppeteer). Allows to wait for
  navigation to reach a URL starting with the one specified before extracting content. Useful when the URL redirects
  elsewhere before displaying content.
