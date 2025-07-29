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
* The command-line arguments ``--jobs``, ``--config``, and ``--hooks`` feature a "smart file specification" capability.
  This allows you to provide a shorthand name for your files, and  **webchanges** will automatically search for several
  variations of that name.

Changed
```````
* Differ ``deepdiff``'s report has been improved by indenting multi-line value changes.
* Command line ``--test-job``: Improved display by adding to the report the media type (fka MIME type), ETag (when
  present) and GUID (internal identifier).
* Job directive ``note`` is converted from Markdown by the HTML reporter.

Deprecated
``````````
* Environment variable ``GOOGLE_AI_API_KEY`` for the API key used by differ ``ai_google`` (BETA) is deprecated; use
  ``GEMINI_API_KEY`` instead.

Fixed
`````
* Job directive ``ignore_connection_errors``: Did not work as expected with the default ``httpx`` HTML client library
  (#`100 <https://github.com/mborsetti/webchanges/issues/100>`__.).
* Command line argument ``--error``: Was reporting jobs with sites returning HTTP response code 304 Not Modified as if
  they returned no data (#`102 <https://github.com/mborsetti/webchanges/issues/102>`__).
* Command line argument ``--database``: If filename was not not present in the current directory, it was not searched in
  the default database directory.
* Command line argument ``--test-job``:

  - Output is no longer colorized as if it were a diff.
  - When used in conjunction with ``--test-reporter browser`` or any other HTML reporter and the job has
    ``monospace: true``, the output now uses a monospaced font.
* Configuration ``differ_defaults``: Was not being applied correctly in certain circumstances.
* Differ ``ai_google`` (BETA): Improved reporting of upstream API errors.
* Differ ``images`` (BETA):

  - Report now includes the old image;
  - Minor fixes to the ``ai_google`` summary (ALPHA), including proper application of defaults from the config file
    and the inclusion in the footnote of the actual generative AI model used (vs. the one specified).
