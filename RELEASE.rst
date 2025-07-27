⚠ Breaking Change
``````````````````
* Differ ``ai_google`` (BETA) now expects the API key to be in the environment variable named ``GEMINI_API_KEY`` to
  maintain consistency with the new API documentation from Google and is interoperable with Gemini CLI. The deprecated
  ``GOOGLE_AI_API_KEY`` will be read until the end of 2025.

Added
`````
* Directive ``wait_for_selector`` of URL jobs with ``browser: true`` (Playwright) can now be a list, enabling waiting
  for multiple selectors in the order given.
* Differ ``deepdiff`` has a new sub-directive ``compact`` which produces a much less wordy report in YAML and ignores
  changes of data type (e.g. "type changed from NoneType to str").

Changed
```````
* Differ ``deepdiff``'s report has been improved by indenting multi-line value changes.
* Command line ``--test-job``: Improved display by adding to the report the media type (fka MIME type), ETag (when
  present) and GUID (internal identifier).
* Job directive ``note`` is converted from Markdown by the HTML reporter.

Deprecated
``````````
* Environment variable ``GOOGLE_AI_API_KEY`` for the API key used by differ ``ai_google`` (BETA) is deprecated; use
  ``GEMINI_API_KEY`` instead. This maintains consistency with the new API documentation from Google and is interoperable
  with Gemini CLI.

Fixed
`````
* Job directive ``ignore_connection_errors``: Did not work as expected with the default ``httpx`` HTML client library
  (#`100 <https://github.com/mborsetti/webchanges/issues/100>`__.).
* Command line argument ``--error``: Was reporting jobs with errors not present during regular execution. Changed
  default ``--max-workers`` to 1 (no parallel jobs) when running with ``--error`` to prevent this. (#`102
  <https://github.com/mborsetti/webchanges/issues/102>`__.)
* Command line argument ``--database``: Filename was not being searched in default database directory if not present in
  current directory.
* Command line argument ``--test-job``:

  - Output is no longer colorized as if it were a diff.
  - When used in conjunction with ``--test-reporter browser`` or any other HTML reporter and job has
    ``monospace: true``: Output now uses a monospaced font.
* Configuration ``differ_defaults``: Was not being applied correctly in certain circumstances.
* Differ ``ai_google`` (BETA): Improved reporting of upstream API errors.
* Differ ``images`` (BETA):

  - Report now includes the old image;
  - Minor fixes to the ``ai_google`` summary (ALPHA), including proper application of defaults from the config file
    and the inclusion in the footnote of the actual generative AI model used (vs. the one specified).

Internals / hooks.py
````````````````````
* GUID is now assigned to the job when it's loaded, enabling for a hook to programmatically change ``job.url``,
  ``job.user_visible_url`` and/or ``job.command`` without causing processing errors downstream.
* Jobs with a directive ``kind`` belonging to a Class defined in hooks.py, and which inherits from UrlJob, BrowserJob or
  ShellJob, were not initialized with the default configurations for the parent class (fixed).
* Updated vendored code providing httpx.Headers (when httpx is not installed) to mirror version 0.28.1.
* Updated vendored code providing packaging.versions (when packaging is not installed) to mirror version 24.2.
* Minor code fixes resulting from newly using Pyright / Pylance in the IDE.
