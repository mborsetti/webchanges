Fixed
-----
* Under certain circumstances, certain default jobs directives declared in the configuration file would not be applied
  to jobs.
* Fixed automatic fallback to ``requests`` when the **required** HTTP client package ``httpx`` is not installed.

Added
-----
* ``block_elements`` directive for jobs with ``use_browser: true`` is supported again and can be used to improve
  speed by preventing binary and media content loading, while providing all elements required dynamic web page load
  (see the advanced section of the documentation for a suggestion of elements to block). This was available under
  Pypetteer and has been reintroduced for Playwright.
* ``init_script`` directive for jobs with ``use_browser: true`` to execute a JavaScript in Chrome after launching it
  and before navigating to ``url``. This can be useful to e.g. unset certain default Chrome ``navigator``
  properties by calling a JavaScript function to do so.
