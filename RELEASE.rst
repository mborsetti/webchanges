Notice
------
Support for Python 3.8 will be removed on or about 5 October 2023. A reminder that older Python versions are
supported for 3 years after being obsoleted by a new major release (i.e. about 4 years since their original release).

Added
-----
* When running in verbose (``-v``) mode, if a ``url`` job with ``use_browser: true`` fails with a Playwright error,
  capture and save in the temporary folder a screenshot, a full page image, and the HTML contents of the page at the
  moment of the error (see log file for filenames).
