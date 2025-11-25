=========
Changelog
=========

This changelog mostly follows '`keep a changelog <https://keepachangelog.com/en/1.0.0/>`__'. Release numbering mostly
follows the logic of `Semantic Versioning <https://semver.org/spec/v2.0.0.html#semantic-versioning-200>`__
(``<major>.<minor>.<patch>``) and the syntax of Python's `Packaging 
<https://packaging.python.org/en/latest/discussions/versioning/>`__. Release date is UTC. Major backward incompatible
(breaking) changes will be introduced in major versions with advance notice in the Deprecations section. Documentation
updates are ongoing and mostly unlisted here.

**Development**

The unreleased versions can be installed as follows (`git
<https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`__ needs to be installed):

.. code-block:: bash

   pip install git+https://github.com/mborsetti/webchanges.git@unreleased

Unreleased documentation is `here <https://webchanges.readthedocs.io/en/unreleased/>`__.

`Contributions <https://github.com/mborsetti/webchanges/blob/main/CONTRIBUTING.rst>`__ are always welcomed, and you
can check out the `wish list <https://github.com/mborsetti/webchanges/blob/main/WISHLIST.md>`__ for inspiration.

.. Categories used (in order):
   ⚠ Breaking Changes, for changes that break existing functionality. [minor revision or, if to API, major revision]
   Added, for new features. [triggers a minor revision]
   Changed, for changes in existing functionality. [triggers a minor revision or, if to API, major revision]
   Deprecated, for soon-to-be removed features.
   Removed, for now removed features. [if to API, triggers a major revision]
   Fixed, for any bug fixes. [triggers a minor patch]
   Security, in case of vulnerabilities. [triggers a minor patch]
   Internals impacting hooks.py, for changes that affect developers only. [triggers a minor patch]
   Internals, for changes that don't affect users. [triggers a minor patch]


Version 3.32.1
-------------------
Unreleased

Changes
```````
* Improved logging for the ``evaluate`` directive in URL Jobs with ``browser: true``.
* ``--dump-history JOB`` command line argument will now match any job, even one that is not in the ``--jobs`` file.

Fixed
`````
* Regression ``http_ignore_error_codes`` not being applied to ``TransientHTTPError`` Exceptions such as '429 Too Many Requests' (issue #`119 <https://github.com/mborsetti/webchanges/issues/119>`__).


Version 3.32.0
-------------------
2025-11-16

⚠ Breaking Changes
```````````````````
* Removed support for Python 3.10. As a reminder, older Python versions are supported for 3 years after being obsoleted
  by a new major release.

Added
`````
* Support for Python 3.14t (free-threaded, GIL-free). Please note that while **webchanges** now supports free-threaded 
  Python, certain optional dependencies do not (currently, these are ``playwright`` and ``jq``).

Fixed
`````
* Fixed regression in error handling leading to interpreting errors as empty responses causing diffs to be be sent out.
  Reported in #`104 <https://github.com/mborsetti/webchanges/issues/104>`__.

Internals
`````````
* Implemented testing for Windows (in addition to Linux and macOS).
* Implemented testing for Python 3.14t (free threading / GIL-free).
* Additional code security improvements.
* Removed Gemini Github Actions workflows (beta trial).
* In URL jobs, the ``TransientHTTPError`` Exception will be raised when a transient HTTP error is detected, paving the
  way for a new ``ignore_transient_error`` directive (not yet implemented) requested in #`119
  <https://github.com/mborsetti/webchanges/issues/119>`__.

  The following HTTP response codes are considered to be transient errors:

    - 429 Too Many Requests
    - 500 Internal Server Error
    - 502 Bad Gateway
    - 503 Service Unavailable
    - 504 Gateway Timeout

  For jobs with ``browser: true``, browser errors starting with ``net::`` and corresponding to the range 100-199
  (Connection related errors) are also considered to be transient (full list at
  https://source.chromium.org/chromium/chromium/src/+/main:net/base/net_error_list.h).


Version 3.31.4
------------------
2025-10-25

Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.10 was
released on 24 October 2022, the codebase will be streamlined by removing support for Python 3.10 on or after 24 
October 2025.

Added
`````
* Support for Python 3.14.

Fixed
`````
* Fixed ``deepdiff`` differ to handle text strings correctly (e.g. when an API typically returning JSON starts
  returning an error in HTML).

Internals (impacting hooks.py)
``````````````````````````````
* In the ``Differ`` Class' ``process`` method, the ``report_kind``'s value ``text`` has been renamed ``plain`` for 
  clarity and to align with IANA's media type nomenclature for different types of text.

Internals (other)
`````````````````
* Implemented testing for Python 3.14.
* Implemented OpenSSF Scorecard and improved code security.
* Enabled additional ``ruff check`` linters and improved code quality.


Version 3.31.3
------------------
2025-09-24

Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.10 was
released on 24 October 2022, the codebase will be streamlined by removing support for Python 3.10 on or after 24 
October 2025.

Fixed
`````
* Certain job Exceptions would fail with a yaml Exception.

Internals
`````````
* Removed non-unique elements in pyproject.toml's classifiers,
* Updated run-gemini-cli to fix GitHub error.
* Fixed pre-commit.ci failing checks on new PRs.


Version 3.31.2
------------------
2025-09-16

Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.10 was
released on 24 October 2022, the codebase will be streamlined by removing support for Python 3.10 on or after 24 
October 2025.

Fixed
`````
* Fixed UnboundLocalError when using new ``utf-8`` sub-directive within the ``smtp`` emailer (``email`` report).
  Reported in #`110 <https://github.com/mborsetti/webchanges/issues/110>`__.

Internals
`````````
* Removed workaround for Python 3.9, which is no longer supported.


Version 3.31.1
------------------
2025-09-14

Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.10 was
released on 24 October 2022, the codebase will be streamlined by removing support for Python 3.10 on or after 24 
October 2025.

Added
`````
* Documented the ``deepdiff`` differ for side-effects when using ``ignore_order: true``.
* Added the ``utf-8`` configuration sub-directive within the ``smtp`` emailer (``email`` report) to enable turning off 
  RFC 6531 Internationalized Email, aka SMTPUTF8 service extension, for backward compatibility with old SMTP servers.
  Requested in #`108 <https://github.com/mborsetti/webchanges/issues/108>`__.

Fixed
`````
* Fixed regresion: getting messages with deletion when the content still seems to be there. Reported in #`104
  <https://github.com/mborsetti/webchanges/issues/104>`__.
* Fixed handling of Playwright exceptions for ``browser: true`` jobs. Reported in #`106
  <https://github.com/mborsetti/webchanges/issues/106>`__.
* Fixed ``--detailed-versions`` CLI, which raised an Exception if playwright was installed but no Chromium browser was
  available.
* Fixed ``monospace: true`` in HTML reports, which was overly applied to include Comparison Type banners.
* Fixed ``deepdiff`` differ, which would not convert Markdown to HTML when needed.
* Fixed url jobs with ``no_redirects: true``, who would not report the redirect response correctly.
* Fixed ``--delete-snapshot`` CLI, which would not display the snapshot time in the timezone set for reports (if one is
  set).
* Fixed ``xpath`` filter, which would throw an Exception with an XPath ``concat()`` string function.
* Fixed default port for SMTP email to ``port: 587``, as is the correct one given the default ``starttls: true``.

Internals
`````````
* Code is now formated with ``ruff format`` instead of ``black``.
* Code is now linted with ``ruff check`` instead of ``isort`` and ``flake8`` (and its extensions).
* Packages in test environments are now installed with ``uv``.
* Experimenting with `Gemini CLI GitHub Action <https://github.com/google-github-actions/run-gemini-cli/>`__ to triage
  issues and perform pull request reviews (thanks to Google's generous free-of-charge quotas).
* Starting to implement lazy loading of packages and modules to improve startup time to execute simple command line 
  arguments.


Version 3.31.0
------------------
2025-07-30

⚠ Breaking Changes
```````````````````
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
* HTML reports now treat the job directive ``note`` as Markdown.

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

Internals / hooks.py
````````````````````
* GUID is now assigned to the job when it's loaded, enabling for a hook to programmatically change ``job.url``,
  ``job.user_visible_url`` and/or ``job.command`` without causing processing errors downstream.
* Jobs with a directive ``kind`` belonging to a Class defined in hooks.py, and which inherits from UrlJob, BrowserJob or
  ShellJob, were not initialized with the default configurations for the parent class (fixed).
* Updated vendored code providing httpx.Headers (when httpx is not installed) to mirror version 0.28.1.
* Updated vendored code providing packaging.versions (when packaging is not installed) to mirror version 24.2.
* Minor code fixes resulting from newly using Pyright / Pylance in the IDE.


Version 3.30.0
------------------
2025-03-29

Added
`````
* README links to a new Docker implementation which includes the Chrome browser. Generously offered by and maintained
  by `Jeff Hedlund <https://github.com/jhedlund>`__ as per `#96 <https://github.com/mborsetti/webchanges/issues/96>`__.
* New filter ``jsontoyaml`` to convert JSON to YAML, which is generally more readable in a report for humans.
* New ``yaml`` data type for the ``deepdiff`` differ (in addition to ``json`` and ``xml``).

Changed
```````
* The ``deepdiff`` differ will now try to derive the ``data-type`` (when it is not specified) from the data's media
  type (fka MIME type) before defaulting to ``json``.

Fixed
`````
* Fixed confusing warning when no default hooks.py file exists. Thanks to `Marcos Alano <https://github.com/mhalano>`__
  for reporting in `#97 <https://github.com/mborsetti/webchanges/issues/97>`__.
* The ``format-json`` filter now uses JSON text instead of plain text to report errors caused by it not receiving
  valid JSON data, to be compatible with downstream filters or differs.
* Fixed the differ ``ai_google`` (BETA), which under certain circumstances was omitting the footnote with the version
  of the GenAI model used.


Version 3.29.0
------------------
2025-03-23

⚠ Breaking Changes
``````````````````
* The differ ``command`` now requires that the ``name: command`` subdirective of ``differ`` be specified.

Changed
```````
* The differ ``command`` now has a sub-directive ``is_html`` to indicate when output is in HTML format. Thanks to `Jeff
  Hedlund <https://github.com/jhedlund>`__ for requesting this enhancement in
  `#95 <https://github.com/mborsetti/webchanges/issues/95>`__.
* Added a tip in the documentation on how to `add bullet points
  <https://webchanges.readthedocs.io/en/stable/advanced.html#bullet-points>`__ to improve the legibility of HTML
  reports.

Fixed
`````
* Fixed reporting of errors arising from filters or reporters.
* Fixed reporting of repeated errors (i.e. when the same error occurs multiple times).
* Fixed header and colorization of the differ ``command``.


Version 3.28.2
------------------
2025-03-11

Changed
```````
* The filter ``format-json`` will no longer raise an error when it is not fed JSON data, but, to facilitate
  troubleshooting, it will report the JSONDecodeError details and the full string causing the error.
* Documentation for the ``css`` and ``xml`` filters has been split into two separate entries for ease of reference.
* Minor word editing of error messages to improve clarity.
* Various updates to the differ ``ai_google`` (BETA):

  - ``top_p`` is set to 1.0 if ``temperature`` is 0.0 (its default value) to eliminate randomness in results.
  - Wordsmitting of the default system prompt leading to small improvements.
  - The footnote now shows the model actually used vs. the one specified in the ``model`` sub-directive, useful when
    omitting the version when using an experimental version (e.g. specifying ``gemini-2.0-pro-exp`` instead of
    ``gemini-2.0-pro-exp-02-05``).

Internals
`````````
* Tested the ``image`` differ's ``ai_google`` directive (ALPHA, undocumented), which uses GenAI to summarize
  differences between two images, with the new ``gemini-2.0-pro-exp-02-05`` `experimental
  <https://ai.google.dev/gemini-api/docs/models/experimental-models#available-models>`__ and improved default system
  prompt. While the new model shows improvements by producing a plausible-sounding summary instead of gibberish, the
  summary is highly inaccurate and therefore unusable. Development paused again until model accuracy improves.



Version 3.28.1
------------------
2025-02-11

Changed
```````
* Differ ``ai_google`` (BETA) now defaults to using the newer ``gemini-2.0-flash`` GenAI model, as it performs better.
  Please note that this model "only" handles 1,048,576 input tokens: if you require the full 2M tokens, manually revert
  to using the ``gemini-1.5-pro`` model or try the newer ``gemini-2.0-pro-exp-02-05`` `experimental
  <https://ai.google.dev/gemini-api/docs/models/experimental-models#available-models>`__ one.

Fixed
`````
* Fixed bug introduced in 3.28.0 causing an execution error when loading a configuration file that does not contain
  the new directive ``differ_defaults``. Thanks `yubiuser <https://github.com/yubiuser>`__ for
  reporting this in `issue #93 <https://github.com/mborsetti/webchanges/issues/93>`__.

Internals
`````````
* When running with ``-verbose``, no longer logs an INFO message for the internal exception raised when receiving a
  an HTTP 304 status code "Not Modified".



Version 3.28.0
------------------
2025-02-11

Added
`````
* Added support for setting default differ directives in config.yaml. This is particularly useful for the ``ai_google``
  differ to specify a default GenAI model.
* Added automatic installation of the `zstandard <https://github.com/indygreg/python-zstandard>`__ library to support
  zstd (`RFC 8878 <https://datatracker.ietf.org/doc/html/rfc8878>`__) compression in ``url`` jobs using the default
  HTTPX HTTP client.

Changed
```````
* Renamed job directives ``filter`` and ``diff_filter`` to ``filters`` and ``diff_filters`` (plural nouns) to better
  reflect their list nature. The singular forms remain backward-compatible.
* Consolidated HTTP proxy configuration into a single ``proxy`` directive, replacing the separate ``http_proxy`` and
  ``https_proxy`` directives while maintaining backward compatibility.
* Improved maximum parallel executions of ``use_browser: true`` to ensuring each Chrome instance has at least 400 MB
  of available memory (or the maximum available, if lower).

Fixed
`````
* Fixed handling of "Error Ended" reports to only send them with ``suppress_repeated_errors: true``.
* Fixed error message when using job directive ``http_client: requests`` without the `requests
  <https://pypi.org/project/requests/>`__ library installed. Thanks `yubiuser <https://github.com/yubiuser>`__ for
  reporting this in `issue #90 <https://github.com/mborsetti/webchanges/issues/90>`__.
* Improved and standardized the ogic and documentation for the use of environment variables ``HTTPS_PROXY`` and
  ``HTTP_PROXY`` in proxy settings.
* Modified ``--prepare-jobs`` command line argument to append never run jobs to command line jobs (``joblist``), if
  present, rather than replacing them.

Internals
`````````
* Replaced JobBase attributes ``http_proxy`` and ``https_proxy`` with a unified ``proxy`` attribute.
* Updated JobBase attributes from singular ``filter`` and ``diff_filter`` to plural ``filters`` and ``diff_filters``.
* Removed unused JobBase attribute ``chromium_revision`` (deprecated since Pypetteer removal on 2022-05-02).



Version 3.27.0
------------------
2025-02-03

Added
`````
* Python 3.13: **webchanges** is now fully tested on Python 3.13 before releasing. However, ``orderedset``, a dependency
  of the `aioxmpp <https://pypi.org/project/aioxmpp/>`__ library required by the ``xmpp`` reporter will not install in
  Python 3.13 (at least on Windows) and this reporter is therefore not included in the tests. It appears that the
  development of this `library <https://codeberg.org/jssfr/aioxmpp>`__ has been halted.

  - Python 3.13t (free-threaded, GIL-free) remains unsupported due to the lack of free-threaded wheels for dependencies
    such as ``cryptography``, ``msgpack``, ``lxml``, and the optional ``jq``.
* New job directive ``suppress_repeated_errors`` to notify an error condition only the first time it is encountered. No
  more notifications will be sent unless the error resolves or a different error occurs. This enhancement was
  requested by `toxin-x <https://github.com/toxin-x>`__ in issue `#86
  <https://github.com/mborsetti/webchanges/issues/86>`__.
* New command line argument ``--log-file`` to write the log to a file. Suggested by `yubiuser
  <https://github.com/yubiuser>`__ in `issue #88 <https://github.com/mborsetti/webchanges/issues/88>`__.
* ``pypdf`` filter has a new ``extraction_mode`` optional sub-directive to enable experimental layout text extraction
  mode functionality.
* New command-line option ``--prepare-jobs`` to run only newly added jobs (to capture and save their initial snapshot).

Fixed
`````
* Fixed command line argument ``--errors`` to use the same exact logic as the one used when running *webchanges*.
  Reported by `yubiuser <https://github.com/yubiuser>`__ in `issue #88
  <https://github.com/mborsetti/webchanges/issues/88>`__.
* Fixed incorrect reporting of job error when caused by an HTTP response status code that is not `IANA-registered
  <https://docs.python.org/3/library/http.html#http-status-codes>`__.

Changed
```````
* Command line ``--test`` can now be combined with ``--test-reporter`` to have the output sent to a different reporter.
* Improved error reporting, including reporting error message in ``--test`` and adding proxy information if the error
  is a network error and the job has a proxy and.
* Updated the default model instructions for the ``ai_google`` (BETA) differ to improve quality of summary.

Internals
`````````
* Now storing error information in snapshot database.
* Added ``ai_google`` directive to the ``image`` differ to test Generative AI summarization of changes between two
  images, but in testing the results are unusable. This feature is in ALPHA and undocumented, and will not be
  developed further until the models improve to the point where the summary becomes useful.



Version 3.26.0
------------------
2024-10-13

Added
`````
* Python 3.13 Support: **webchanges** now supports Python 3.13, but complete testing is pending due to dependencies
  such as ``lxml`` not having yet published installation packages ("wheels") for 3.13.
* Glob Pattern Support for Hooks Files: The ``--hooks`` command-line argument now accepts glob patterns for flexible
  hook file selection.
* Multiple Hook Specifications: Specify multiple hook files or glob patterns by repeating the ``--hooks`` argument.
* Enhanced Version Information: ``--detailed-versions`` now displays the system's default value for
  ``--max-threads``.
* Optional ``zstd`` Compression: URL jobs without ``browser: true`` can now utilize ``zstd`` compression for
  improved efficiency (requires ``pip install -U webchanges[zstd]``).
* ``ai_google`` Differ Enhancements (BETA):

  * New ``additions_only`` Sub-directive: When set to true, generates AI-powered summaries of only the added text. This
    is particularly helpful for monitoring pages with regularly added content (e.g., press releases).
  * New ``unified_diff_new`` Field: Added to the ``prompt`` directive.

Changed
```````
* Relaxed Security for job and hook Files: The ownership requirement for files containing ``command`` jobs,
  ``shellpipe`` filters, or hook files has been expanded to include root ownership, in addition to the current user.
* ``ai_google`` Differ Refinements (BETA):

  *  Renamed Prompt Fields (⚠ BETA breaking change):  For clarity, ``old_data`` and ``new_data`` fields in the
     ``prompt`` directive have been renamed to ``old_text`` and ``new_text``, respectively.
  *  Improved Output Quality: Significantly enhanced output quality by revising the default values for
     ``system_instructions`` and ``prompt``.
  *  Updated documentation.

Fixed
`````
* Markdown Handling: Improved handling of links with empty text in the Markdown to HTML converter.
* ``image`` Differ Formatting: Fixed HTML formatting issues within the ``image`` differ.

Removed
```````
* Python 3.9 Support: Support for Python 3.9 has been dropped. As a reminder, older Python versions are supported for 3
  years after being superseded by a new major release (i.e. approximately 4 years after their initial release).



Version 3.25.0
------------------
2024-08-15

Added
`````
* Multiple job files or glob patterns can now be specified by repeating the ``--jobs`` argument.
* Job list filtering using `Python regular expression
  <https://docs.python.org/3/library/re.html#regular-expression-syntax>`__. Example: ``webchanges --list blue`` lists
  jobs with 'blue' in their name (case-sensitive, so not 'Blue'), while ``webchanges --list (?i)blue`` is
  `case-insensitive <https://docs.python.org/3/library/re.html#re.I>`__.
* New URL job directive ``params`` for specifying URL parameters (query strings), e.g. as a dictionary.
* New ``gotify`` reporter (upstream contribution: `link <https://github.com/thp/urlwatch/pull/823/files>`__).
* Improved messaging at startup when a legacy database that requires conversion is found.

Changed
```````
* Updated ``ai_google`` differ to reflect Gemini 1.5 Pro's 2M token context window.

Fixed
`````
* Corrected the automated handling in differs and reporters of data with a 'text/markdown' media type (fka MIME type).
* Multiple ``wdiff`` differ fixes and improvements:
  - Fixed body font issues;
  - Removed spurious ``^\n`` insertions;
  - Corrected ``range_info`` lines;
  - Added word break opportunities (``<wbr>``) in HTML output for better browser handling of long lines.
* ``deepdiff`` differ now breaks a list into its individual elements.
* Improved URL matching for jobs by normalizing %xx escapes and plus signs (e.g. ``https://www.example.org/El Niño``
  will now match ``https://www.example.org/El+Ni%C3%B1o`` and vice versa).
* Improved the text-to-HTML URL parser to accurately extract URLs with multiple parameters.

Internals
`````````
* Replaced ``requests.structures.CaseInsensitiveDict`` with ``httpx.Headers`` as the Class holding headers.
* The ``Job.headers`` attribute is now initialized with an empty ``httpx.Headers`` object instead of None.



Version 3.24.1
------------------
2024-06-14

Added
`````
* Command line argument ``--rollback-database`` now accepts dates in ISO-8601 format in addition to Unix timestamps.
  If the library dateutil (not a dependency of **webchanges**) is found installed, then it will also accept any
  string recognized by ``dateutil.parser`` such as date only, time only, date and time, etc. (suggested
  by `Markus Weimar <https://github.com/Markus00000>`__ in issue `#78
  <https://github.com/mborsetti/webchanges/issues/78>`__).
* ``ai-google`` differ (BETA) now supports calls to the Gemini 1.5 Pro with 2M tokens model (early access required).


Version 3.24.0
------------------
2024-06-06

Added
`````
* New ``wdiff`` differ to perform word-by-word comparisons. Replaces the dependency on an outside executable and
  allows for much better formatting and integration.
* New ``system_instructions`` directive added to the ``ai-google`` differ (BETA).
* Added to the documentation examples on how to use the ``re.findall`` filter to extract only the first or last line
  (suggested by `Marcos Alano <https://github.com/malano>`__ in issue `#81
  <https://github.com/mborsetti/webchanges/issues/81>`__).

Changed
```````
* Updated the documentation for the ``ai-google`` differ (BETA), mostly to reflect billing changes by Google, which is
  still free for most.

Fixed
`````
* Fixed a data type check in preventing ``URL`` jobs' ``data`` (for POSTs etc.) to be a list.


Version 3.23.1
------------------
2024-05-22

Changed
```````
* Updated the ``ai-google`` differ (BETA)'s default model to  ``gemini-1.5-flash-latest`` due to changes in the Google
  API, and its default prompt to ``Identify and summarize the changes between the old and new
  documents:\n\n<old>\n{old_data}\n</old>\n\n``, due to the old prompt not generating the expected output.  Updated
  the documentation.


Version 3.23.0
------------------
2024-05-15

Changed
```````
* The ``ai-google`` (BETA) differ now defaults to using the new ``gemini-1.5-flash`` model (see documentation `here
  <https://ai.google.dev/gemini-api/docs/models/gemini#gemini-1.5-flash-expandable>`__), as it still supports
  1M tokens, "excels at summarization" (per `here <https://blog
  .google/technology/ai/google-gemini-update-flash-ai-assistant-io-2024/#gemini-model-updates:~:text=1
  .5%20flash%20excels%20at%20summarization%2C>`__), allows for a higher number of requests per minute (in the
  free version, 15 vs. 2 of ``gemini-1.5-pro``), is faster, and, if you're paying for it, cheaper. To continue to
  use ``gemini-1.5-pro``, which may produce more "complex" results, specify it in the job's ``differ`` directive.

Fixed
`````
* Fixed header of ``deepdiff`` and ``image`` (BETA) differs to be more consistent with the default ``unified`` differ.
* Fixed the way images are handled in the email reporter so that they now display correctly in clients such as Gmail.

Internals
`````````
* Command line argument ``--test-differs`` now processes the new ``mime_type`` attribute correctly (``mime_type`` is
  an internal work in progress attribute to facilitate future automation of filtering, diffing, and reporting).


Version 3.22
------------------
2024-04-25

⚠ Breaking Changes
```````````````````
* Developers integrating custom Python code (hooks.py) should refer to the "Internals" section below for important
  changes.

Changed
```````
* Snapshot database

  - Moved the snapshot database from the "user_cache" directory (typically not backed up) to the "user_data" directory.
    The new paths are (typically):

    - Linux: ``~/.local/share/webchanges`` or ``$XDG_DATA_HOME/webchanges``
    - macOS: ``~/Library/Application Support/webchanges``
    - Windows: ``%LOCALAPPDATA%\webchanges\webchanges``

  - Renamed the file from ``cache.db`` to ``snapshots.db`` to more clearly denote its contents.
  - Introduced a new command line option ``--database`` to specify the filename for the snapshot database, replacing
    the previous ``--cache`` option (which is deprecated but still supported).
  - Many thanks to `Markus Weimar <https://github.com/Markus00000>`__ for pointing this problem out in issue `#75
    <https://github.com/mborsetti/webchanges/issues/75>`__.

* Modified the command line argument ``--test-differ`` to accept a second parameter, specifying the maximum number of
  diffs to generate.
* Updated the command line argument ``--dump-history`` to display the ``mime_type`` attribute when present.
* Enhanced differs functionality:

  - Standardized headers for ``deepdiff`` and ``imagediff`` (BETA) to align more closely with those of ``unified``.
  - Improved the ``google_ai`` differ (BETA):

    - Enhanced error handling: now, the differ will continue operation and report errors rather than failing outright
      when Google API errors occur.
    - Improved the default prompt to ``Analyze this unified diff and create a summary listing only the
      changes:\n\n{unified_diff}`` for improved results.

Fixed
`````
* Fixed an AttributeError Exception when the fallback HTTP client package ``requests`` is not installed, as reported
  by `yubiuser <https://github.com/yubiuser>`__ in `issue #76 <https://github.com/mborsetti/webchanges/issues/76>`__.
* Addressed a ValueError in the ``--test-differ`` command, a regression reported by `Markus Weimar
  <https://github.com/Markus00000>`__ in `issue #79 <https://github.com/mborsetti/webchanges/issues/79>`__.
* To prevent overlooking changes, webchanges now refrains from saving a new snapshot if a differ operation fails
  with an Exception.

Internals
`````````
* New ``mime_type`` attribute: we are now capturing and storing the data's media type (fka MIME type) alongside data in
  the snapshot database to facilitate future automation of filtering, diffing, and reporting. Developers using custom
  Python code will need to update their filter and retrieval methods in classes inheriting from FilterBase and
  JobBase, respectively, to accommodate the ``mime_type`` attribute. Detailed updates are available in the `hooks
  documentation <https://webchanges.readthedocs.io/en/stable/hooks.html#:~:text=Changed%20in%20version%203.22>`__.
* Updated terminology: References to ``cache`` in object names have been replaced with ``ssdb`` (snapshot database).
* Introduced a new NamedTuple, ``Snapshot``, to streamline the process of retrieving and saving data to the database.


Version 3.21
------------------
2024-04-16

Added
`````
* **Job selectable differs**: The differ, i.e. the method by which changes are detected and summarized, can now be
  selected job by job. Also gone is the restriction to have only unified diffs, HTML table diff, or calling an outside
  executable, as differs have become modular.

  - Python programmers can write their own custom differs using the ``hooks.py`` file.
  - Backward-compatibility is preserved, so your current jobs will continue to work.
* **New differs**:

  - ``difflib`` to report element-by-element changes in JSON or XML structured data.
  - ``imagediff`` (BETA) to report an image showing changes in an **image** being tracked.
  - ``ai_google`` (BETA) to use a **Generative AI provide a summary of changes** (free API key required). We use
    Google's Gemini Pro 1.5 since it is the first model that can ingest 1M tokens, allowing to analyze changes in
    long documents (up to 350,000 words, or about 700 pages single-spaced) such as terms and conditions, privacy
    policies, etc. where summarization adds the most value and which other models can't handle. The differ can call
    the Gen AI model to summarize a unified diff or to find and summarize the differences itself. Also supported is
    Gemini 1.0, but it can handle a lower number of tokens.

Changed
```````
* Filter ``absolute_links`` now converts URLs of the ``action``, ``href`` and ``src`` attributes in any HTML tag, as
  well as the ``data`` attribute of the ``<object>`` tag; it previously converted only the ``href`` attribute of
  ``<a>`` tags.
* Updated explanatory text and error messages for increased clarity.
* You can now select jobs to run by using its url/command instead of its number, e.g. ``webchanges https://test.com`` is
  just as valid as ``webchanges 1``.

Deprecated
----------
* Job directive ``diff_tool``. Replaced with the ``command`` differ (see `here
  <https://webchanges.readthedocs.io/en/stable/differs.html#command_diff>`__.

Fixed
`````
* ``webchanges --errors`` will no longer check jobs who have ``disabled: true`` (thanks to `yubiuser
  <https://github.com/yubiuser>`__ for reporting this in issue `# 73
  <https://github.com/mborsetti/webchanges/issues/73>`__).
* Markdown links with no text were not clickable when converted to HTML; conversion now adds a 'Link without text'
  label.

Internals
`````````
* Improved speed of creating a unified diff for an HTML report.
* Reduced excessive logging from ``httpx``'s sub-modules ``hpack`` and ``httpcore`` when running with ``-vv``.


Version 3.20.2
------------------
2024-03-16

Fixed
`````
* Parsing the ``to`` address for the ``sendmail`` ``email`` reporter.

Version 3.20.1
------------------
2024-03-16

Fixed
`````
* Regression introduced in supporting sending to multiple "to" addresses.


Version 3.20
------------------
2024-03-15

Added
`````
* ``re.findall`` filter to extract, delete or replace non-overlapping text using Python ``re.findall``.

Changed
```````
* ``--test-reporter`` now allows testing of reporters that are not enabled; if a reporter is not enabled, a warning
  will be issued. This simplifies testing.
* ``email`` reporter (both SMTP and sendmail) supports sending to multiple "to" addresses.

Fixed
`````
* Reports from jobs with ``monospace: true`` were not being rendered correctly in Gmail.


Version 3.19.1
------------------
2024-03-07

Fixed
`````
* Added the ``Date`` header field to SMTP email messages to ensure the timestamp is present even when it is not added
  by the server upon receipt. Contributed by `Dominik <https://github.com/DL6ER>`__ in `#71
  <https://github.com/mborsetti/webchanges/pull/71>`__.


Version 3.19
------------------
2024-02-28

Fixed
`````
* Under certain circumstances, certain default jobs directives declared in the configuration file would not be applied
  to jobs.
* Fixed automatic fallback to ``requests`` when the **required** HTTP client package ``httpx`` is missing.

Added
`````
* ``block_elements`` directive for jobs with ``use_browser: true`` is supported again and can be used to improve
  speed by preventing binary and media content loading, while providing all elements required dynamic web page load
  (see the advanced section of the documentation for a suggestion of elements to block). This was available under
  Pypetteer and has been reintroduced for Playwright.
* ``init_script`` directive for jobs with ``use_browser: true`` to execute a JavaScript in Chrome after launching it
  and before navigating to ``url``. This can be useful to e.g. unset certain default Chrome ``navigator`` properties
  by calling a JavaScript function to do so.


Version 3.18.1
------------------
2024-02-20

Fixed
`````
* Fixed regression whereby configuration key ``empty-diff`` was inadvertently renamed ``empty_diff``.


Version 3.18
------------------
2024-02-19

Fixed
`````
* Fixed incorrect handling of HTTP client libraries when ``httpx`` is not installed (should graciously fallback to
  ``requests``).  Reported by `drws <https://github.com/drws>`__ as an add-on to `issuse #66
  <https://github.com/mborsetti/webchanges/issues/66>`__.

Added
`````
* Job directive ``enabled`` to allow disabling of a job without removing or commenting it in the jobs file (contributed
  by `James Hewitt <https://github.com/Jamstah>`__ `upstream <https://github.com/thp/urlwatch/pull/785>`__).
* ``webhook`` reporter has a new ``rich_text`` config option for preformatted rich text for Slack (contributed
  by `K̶e̶v̶i̶n̶ <https://github.com/vimagick>`__ `upstream <https://github.com/thp/urlwatch/pull/780>`__).

Changed
```````
* Command line argument ``--errors`` now uses conditional requests to improve speed. Do not use to test newly modified
  jobs since websites reporting no changes from the last snapshot stored by **webchanges** are skipped; use
  ``--test`` instead.
* If the ``simplejson`` library is installed, it will be used instead of the built-in ``json`` module (see
  https://stackoverflow.com/questions/712791).


Version 3.17.2
------------------
2023-12-11

Fixed
`````
* Exception in error handling when ``requests`` is not installed (reported by
  `yubiuser <https://github.com/yubiuser>`__ in `#66 <https://github.com/mborsetti/webchanges/issues/66>`__).


Version 3.17.1
------------------
2023-12-10

Fixed
`````
* Removed dependency on ``requests`` library inadvertently left behind (reported by
  `yubiuser <https://github.com/yubiuser>`__ in `#65 <https://github.com/mborsetti/webchanges/issues/65>`__).


Version 3.17
------------------
2023-12-10

Added
`````
* You can now specify a reporter name after the command line argument ``--errors`` to send the output to the reporter
  specified. For example, to be notified by email of any jobs that result in an error or who, after filtering,
  return no data (indicating they may no longer be monitoring resources as expected), run ``webchanges --errors
  email`` (requested by `yubiuser <https://github.com/yubiuser>`__ in `#63
  <https://github.com/mborsetti/webchanges/issues/63>`__).
* You can now suppress the ``footer`` in an ``html`` report using the new ``footer: false`` sub-directive in
  ``config.yaml`` (same as the one already existing with ``text`` and ``markdown``).

Internals
`````````
* Fixed a regression on the default ``User-Agent`` header for ``url`` jobs with the ``use_browser: true`` directive.


Version 3.16
------------------
2023-12-07

Added
`````
* The HTTP/2 network protocol (the same used by major browsers) is now used in ``url`` jobs. This allows the
  monitoring of certain websites who block requests made with older protocols like HTTP/1.1. This is implemented by
  using the ``HTTPX`` and ``h2`` HTTP client libraries instead of the ``requests`` one used previously.

  Notes:

  - Handling of data served by sites whose encoding is misconfigured is done slightly differently by ``HTTPX``, and if
    you newly encounter instances where extended characters are rendered as ``�`` try adding ``encoding:
    ISO-8859-1`` to that job.
  - To revert to the use of the ``requests`` HTTP client library, use the new job sub-directive ``http_client:
    requests`` (in individual jobs or in the configuration file for all ``url`` jobs) and install ``requests`` by
    running ``pip install --upgrade webchanges[requests]``.
  - If the system is misconfigured and the ``HTTPX`` HTTP client library is not found, an attempt to use the
    ``requests`` one will be made. This behaviour is transitional and will be removed in the future.
  - HTTP/2 is theoretically faster than HTTP/1.1 and preliminary testing confirmed this.

* New ``pypdf`` filter to convert pdf to text **without having to separately install OS dependencies**. If you're
  using ``pdf2text`` (and its OS dependencies), I suggest you switch to ``pypdf`` as it's much faster; however do note
  that the ``raw`` and ``physical`` sub-directives are not supported. Install the required library by running ``pip
  install --upgrade webchanges[pypdf]``.
* New ``absolute_links`` filter to convert relative links in HTML ``<a>`` tags to absolute ones. This filter is not
  needed if you are already using the ``beautify`` or ``html2text`` filters (requested by by `Paweł Szubert
  <https://github.com/pawelpbm>`__ in `#62 <https://github.com/mborsetti/webchanges/issues/62>`__).
* New ``{jobs_files}`` substitution for the ``subject`` of the ``email`` reporter. This will be replaced by the
  name of the jobs file(s) different than the default ``jobs.yaml`` in parentheses, with a prefix of ``jobs-`` in the
  name removed. To use, replace the ``subject`` line for your reporter(s) in ``config.yaml`` with e.g. ``[webchanges]
  {count} changes{jobs_files}: {jobs}``.
* ``html`` reports now have a configurable ``title`` to set the HTML document title, defaulting to
  ``[webchanges] {count} changes{jobs_files}: {jobs}``.
* Added reference to a Docker implementation to the documentation (requested by by `yubiuser
  <https://github.com/yubiuser>`__ in `#64 <https://github.com/mborsetti/webchanges/issues/64>`__).

Changed
```````
* ``url`` jobs will use the ``HTTPX`` library instead of ``requests`` if it's installed since it uses the HTTP/2 network
  protocol (when the ``h2`` library is also installed) as browsers do. To revert to the use of ``requests`` even if
  ``HTTPX`` is installed on the system, add ``http_client: requests`` to the relevant jobs or make it a default by
  editing the configuration file to add the sub-directive ``http_client: requests`` for ``url`` jobs under
  ``job_defaults``.
* The ``beautify`` filter converts relative links to absolute ones; use the new ``absolute_links: false``
  sub-directive to disable.

Internals
`````````
* Removed transitional support for the ``beautifulsoup<4.11`` library (i.e. older than 7 April 2022) for the
  ``beautify`` filter.
* Removed dependency on the ``requests`` library and its own dependency on the ``urllib3`` library.
* Code cleanup, including removing support for Python 3.8.



Version 3.15
------------------
2023-10-25

Added
`````
* Support for Python 3.12.
* ``data_as_json`` job directive for ``url`` jobs to indicate that ``data`` entered as a dict should be
  serialized as JSON instead of urlencoded and, if missing, the header ``Content-Type`` set to ``application/json``
  instead of ``application/x-www-form-urlencoded``.

Changed
```````
* Improved error handling and documentation on the need of an external install when using ``parser: html5lib`` with the
  ``bs4`` method of the ``html2text`` filter and added ``html5lib`` as an optional dependency keyword (thanks to
  `101Dude <https://github.com/101Dude>`__'s report in `59 <https://github.com/mborsetti/webchanges/issues/59>`__).

Removed
```````
* Support for Python 3.8. A reminder that older Python versions are supported for 3 years after being obsoleted by a
  new major release (i.e. about 4 years since their original release).

Internals
`````````
* Upgraded build environment to use the ``build`` frontend and ``pyproject.toml``, eliminating ``setup.py``.
* Migrated to ``pyproject.toml`` the configuration of all tools who support it.
* Increased the default ``timeout`` for ``url`` jobs with ``use_browser: true`` (i.e. using Playwright) to 120 seconds.


Version 3.14
------------------
2023-09-01

Added
`````
* When running in verbose (``-v``) mode, if a ``url`` job with ``use_browser: true`` fails with a Playwright error,
  capture and save in the temporary folder a screenshot, a full page image, and the HTML contents of the page at the
  moment of the error (see logs for filenames).


Version 3.13
------------------
2023-08-28

Added
`````
* Reports have a new ``separate`` configuration option to split reports into one-per-job.
* ``url`` jobs without ``use_browser`` have a new ``retries`` directive to specify the  number of times to retry a
  job that errors before giving up. Using ``retries: 1`` or higher will often solve the ``('Connection aborted.',
  ConnectionResetError(104, 'Connection reset by peer'))`` error received from a misconfigured server at the first
  connection.
* ``remove_duplicates`` filter has a new ``adjacent`` sub-directive to de-duplicate non-adjacent lines or items.
* ``css`` and ``xpath`` have a new ``sort`` subfilter to sort matched elements lexicographically.
* Command line arguments:

  * New ``--footnote`` to add a custom footnote to reports.
  * New ``--change-location`` to keep job history when the ``url`` or ``command`` changes.
  * ``--gc-database`` and ``--clean-database`` now have optional argument ``RETAIN-LIMIT`` to allow increasing
    the number of retained snapshots from the default of 1.
  * New ``--detailed-versions`` to display detailed version and system information, inclusive of the versions of
    dependencies and, in certain Linux distributions (e.g. Debian), of system libraries. It also reports available
    memory and disk space.

Changed
```````
* ``command`` jobs now have improved error reporting which includes the error text from the failed command.
* ``--rollback-database`` now confirms the date (in ISO-8601 format) to roll back the database to and, if
  **webchanges** is being run in interactive mode, the user will be asked for positive confirmation before proceeding
  with the un-reversible deletion.

Internals
`````````
* Added `bandit <https://github.com/PyCQA/bandit>`__ testing to improve the security of code.
* ``headers`` are now turned into strings before being passed to Playwright (addresses the error
  ``playwright._impl._api_types.Error: extraHTTPHeaders[13].value: expected string, got number``).
* Exclude tests from being recognized as package during build (contributed by `Max
  <https://github.com/aragon999>`__ in `#54 <https://github.com/mborsetti/webchanges/pull/54>`__).
* Refactored and cleaned up some tests.
* Initial testing with Python 3.12.0-rc1, but a reported bug in ``typing.TypeVar`` prevents the ``pyee`` dependency
  of ``playwright`` from loading, causing a failure. Awaiting for fix in Python 3.12.0-rc2 to retry.


Version 3.12
------------------
2022-11-19

Added
`````
* Support for Python 3.11. Please note that the ``lxml`` dependency may fail to install on Windows due to
  `this <https://bugs.launchpad.net/lxml/+bug/1977998>`__ bug and that therefore for now **webchanges** can only be
  run in Python 3.10 on Windows.  [Update: ``lxml wheels`` for Python 3.11 on Windows are available as of 2022-12-13].

Removed
```````
* Support for Python 3.7. As a reminder, older Python versions are supported for 3 years after being obsoleted by a new
  major release; support for Python 3.8 will be removed on or about 5 October 2023.

Fixed
`````
* Job sorting for reports is now case-insensitive.
* Documentation on how to anonymously monitor GitHub releases (due to changes in GitHub) (contributed by `Luis Aranguren
  <https://github.com/mercurytoxic>`__ `upstream <https://github.com/thp/urlwatch/issues/723>`__).
* Handling of ``method`` subfilter for filter ``html2text`` (reported by `kongomondo <https://github.com/kongomondo>`__
  `upstream <https://github.com/thp/urlwatch/issues/588>`__).

Internals
`````````
* Jobs base class now has a ``__is_browser__`` attribute, which can be used with custom hooks to identify jobs that run
  a browser so they can be executed in the correct parallel processing queue.
* Fixed static typing to conform to the latest mypy checks.
* Extended type checking to testing scripts.


Version 3.11
------------------
2022-09-22

Notice
------
Support for Python 3.7 will be removed on or about 22 October 2022 as older Python versions are supported for 3
years after being obsoleted by a new major release.

Added
`````
* The new ``no_conditional_request`` directive for ``url`` jobs turns off conditional requests for those extremely rare
  websites that don't handle it (e.g. Google Flights).
* Selecting the database engine and the maximum number of changed snapshots saved is now set through the configuration
  file, and the command line arguments ``--database-engine`` and ``--max-snapshots`` are used to override such
  settings. See documentation for more information. Suggested by `jprokos <https://github.com/jprokos>`__ in `#43
  <https://github.com/mborsetti/webchanges/issues/43>`__.
* New configuration setting ``empty-diff`` within the ``display`` configuration for backwards compatibility only:
  use the ``additions_only`` job directive instead to achieve the same result. Reported by
  `bbeevvoo <https://github.com/bbeevvoo>`__ in `#47 <https://github.com/mborsetti/webchanges/issues/47>`__.
* Aliased the command line arguments ``--gc-cache`` with ``--gc-database``, ``--clean-cache`` with ``--clean-database``
  and ``--rollback-cache`` with ``--rollback-database`` for clarity.
* The configuration file (e.g. ``conf.yaml``) can now contain keys starting with a ``_`` (underscore) for remarks (they
  are ignored).

Changed
```````
* Reports are now sorted alphabetically and therefore you can use the ``name`` directive to affect the order by which
  your jobs are displayed in reports.
* Implemented measures for ``url`` jobs using ``browser: true`` to avoid being detected: **webchanges** now passes all
  the headless Chrome detection tests `here
  <https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html>`__.
  Brought to attention by `amammad <https://github.com/amammad>`__ in `#45
  <https://github.com/mborsetti/webchanges/issues/45>`__.
* Running ``webchanges --test`` (without specifying a JOB) will now check the hooks file (if any) for syntax errors in
  addition to the config and jobs file. Error reporting has also been improved.
* No longer showing the the text returned by the server when a 404 - Not Found error HTTP status code is returned by for
  all ``url`` jobs (previously only for jobs with ``use_browser: true``).

Fixed
`````
* Bug in command line arguments ``--config`` and ``--hooks``. Contributed by
  `Klaus Sperner <https://github.com/klaus-tux>`__ in PR `#46 <https://github.com/mborsetti/webchanges/pull/46>`__.
* Job directive ``compared_versions`` now works as documented and testing has been added to the test suite. Reported by
  `jprokos <https://github.com/jprokos>`__ in `#43 <https://github.com/mborsetti/webchanges/issues/43>`__.
* The output of command line argument ``--test-differ`` now takes into consideration ``compared_versions``.
* Markdown containing code in a link text now converts correctly in HTML reports.

Internals
`````````
* The job ``kind`` of ``shell`` has been renamed ``command`` to better reflect what it does and the way it's described
  in the documentation, but ``shell`` is still recognized for backward compatibility.
* Readthedocs build upgraded to Python 3.10



Version 3.10.3
------------------
2022-07-22

Added
`````
* ``url`` jobs with ``use_browser: true`` that receive an error HTTP status code from the server will now include the
  text returned by the server in the error message (e.g. "Rate exceeded.", "upstream request timeout", etc.), except if
  HTTP status code 404 - Not Found is received.

Changed
```````
* The command line argument ``--jobs`` used to specify a jobs file now accepts a `glob pattern
  <https://en.wikipedia.org/wiki/Glob_(programming)>`__, e.g. wildcards, to specify multiple files. If more than one
  file matches the pattern, their contents will be concatenated before a job list is built. Useful e.g. if you have
  multiple jobs files that run on different schedules and you want to clean the snapshot database of URLs/commands no
  longer monitored ("garbage collect") using ``--gc-cache`` (e.g. ``webchanges --jobs *.yaml --gc-cache``).
* The command line argument ``--list`` will now list the full path of the jobs file(s).
* Traceback information for Python Exceptions is suppressed by default. Use the command line argument ``--verbose``
  (or ``-v``) to display it.

Fixed
`````
* Fixed ``Unicode strings with encoding declaration are not supported.`` error in the ``xpath`` filter using
  ``method: xml`` under certain conditions (MacOS only). Reported by `jprokos <https://github.com/jprokos>`__ in `#42
  <https://github.com/mborsetti/webchanges/issues/42>`__.

Internals
`````````
* The source distribution is now available on PyPI to support certain packagers like ``fpm``.
* Improved handling and reporting of Playwright browser errors (for ``url`` jobs with ``use_browser: true``).



Version 3.10.2
------------------
2022-06-22

⚠ Breaking Changes
``````````````````
* Due to a fix to the ``html2text`` filter (see below), the first time you run this new version **you may get a change
  report with deletions and additions of lines that look identical. This will happen one time only** and will prevent
  future such change reports.

Added
`````
* You can now run the command line argument ``--test`` without specifying a JOB; this will check the config
  (default: ``config.yaml``) and job (default: ``job.yaml``) files for syntax errors.
* New job directive ``compared_versions`` allows change detection to be made against multiple saved snapshots;
  useful for monitoring websites that change between a set of states (e.g. they are running A/B testing).
* New command line argument ``--check-new`` to check if a new version of **webchanges** is available.
* Error messages for ``url`` jobs failing with HTTP reason codes of 400 and higher now include any text returned by the
  website (e.g. "Rate exceeded.", "upstream request timeout", etc.). Not implemented in jobs with ``use_browser: true``
  due to limitations in Playwright.

Changed
```````
* On Linux and macOS systems, for security reasons we now check that the hooks file **and** the directory it is located
  in are **owned** and **writeable** by **only** the user who is running the job (and not by its group or by other
  users), identical to what we do with the jobs file if any job uses the ``shellpipe`` filter. An
  explanatory ImportWarning message will be issued if the permissions are not correct and the import of the hooks module
  is skipped.
* The command line argument ``-v`` or ``--verbose`` now shows reduced verbosity logging output while ``-vv`` (or
  ``--verbose --verbose``) shows full verbosity.

Fixed
`````
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
`````````
* Changed bootstrapping logic so that when using ``-vv`` the logs will include messages relating to the registration of
  the various classes.
* Improved execution speed of certain informational command line arguments.
* Updated the vendored version of ``packaging.version.parse()`` to 21.3, released on 2021-11-27.
* Changed the import logic for the ``packaging.version.parse()`` function so that if ``packaging`` is found to be
  installed, it will be imported from there instead of from the vendored module.
* ``urllib3`` is now an explicit dependency due to the refactoring of the ``requests`` package (we previously used
  ``requests.packages.urllib3``). Has no effect since ``urllib3`` is already being installed as a dependency of
  ``requests``.
* Added ``py.typed`` marker file to implement `PEP 561 <https://peps.python.org/pep-0561/>`__.



Version 3.10.1
------------------
2022-05-03

Fixed
`````
* ``KeyError: 'indent'`` error when using ``beautify`` filter. Reported by `César de Tassis Filho
  <https://github.com/CTassisF>`__ in `#37 <https://github.com/mborsetti/webchanges/issues/37>`__.



Version 3.10
------------------
2022-05-02

⚠ Breaking Changes
``````````````````

Pyppeteer has been replaced with Playwright
:::::::::::::::::::::::::::::::::::::::::::
This change only affects jobs that ``use_browser: true`` (i.e. those running on a browser to run JavaScript). If none
of your jobs have ``use_browser: true``, there's nothing new here (and nothing to do).

Must do
:::::::
If *any* of your jobs have ``use_browser: true``, you **MUST**:

1) Install the new dependencies:

.. code-block:: bash

   pip install --upgrade webchanges[use_browser]

2) (Optional) ensure you have an up-to-date Google Chrome browser:

.. code-block:: bash

   webchanges --install-chrome

Additionally, if any of your ``use_browser: true`` jobs use the ``wait_for`` directive, it needs to be replaced with
one of:

* ``wait_for_function`` if you were specifying a JavaScript function (see
  `here <https://playwright.dev/python/docs/api/class-frame/#frame-wait-for-function>`__ for full function details).
* ``wait_for_selector`` if you were specifying a selector string or xpath string (see `here
  <https://playwright.dev/python/docs/api/class-frame/#frame-wait-for-selector>`__ for full function details), or
* ``wait_for_timeout`` if you were specifying a timeout; however, this function should only be used for debugging
  because it "is going to be flaky", so use one of the other two ``wait_for`` if you can.; full details `here
  <https://playwright.dev/python/docs/api/class-frame#frame-wait-for-timeout>`__.

Optionally, the values of ``wait_for_function`` and ``wait_for_selector`` can now be dicts to take full advantage of all
the features offered by those functions in Playwright (see documentation links above).

If you are using the ``wait_for_navigation`` directive, it is now called ``wait_for_url`` and offers both glob pattern
and regex matching; ``wait_for_navigation`` will act as an alias for now but but a deprecation warning will be issued.

If you are using the ``chromium_revision`` or ``_beta_use_playwright`` directives in your configuration file, you
should delete them to prevent future errors (for now only a deprecation warning is issued).

Finally, if you are  using the experimental ``block_elements`` sub-directive, it is not (yet?) implemented in Playwright
and is simply ignored.

Improvements
::::::::::::
``wait_until`` has additional functionality, and now takes one of:

* ``load`` (default): Consider operation to be finished when the ``load`` event is fired.
* ``domcontentloaded``: Consider operation to be finished when the ``DOMContentLoaded`` event is fired.
* ``networkidle`` (old ``networkidle0`` and ``networkidle2`` map into this): Consider operation to be finished when
  there are no network connections  for at least 500 ms.
* ``commit`` (new): Consider operation to be finished when network response is received and the document started
  loading.

New directives
::::::::::::::
The following directives are new to the Playwright implementation:

* ``referer``: Referer header value (a string). If provided, it will take preference over the referer header value set
  by the ``headers`` sub-directive.
* ``initialization_url``: A url to navigate to before the ``url`` (e.g. a home page where some state gets set).
* ``initialization_js``: Only used in conjunction with ``initialization_url``, a JavaScript to execute after
  loading ``initialization_url`` and before navigating to the ``url`` (e.g. to emulate a log in).  Advanced usage
* ``ignore_default_args`` directive for ``url`` jobs with ``use_browser: true`` (using Chrome) to control how Playwright
  launches Chrome.

In addition, the new ``--no-headless`` command line argument will run the Chrome browser in "headed" mode, i.e.
displaying the website as it loads it, to facilitate with debugging and testing (e.g. ``webchanges --test 1
--no-headless --test-reporter email``).

See more details of the new directives in the updated documentation.


Freeing space by removing Pyppeteer
:::::::::::::::::::::::::::::::::::
You can free up disk space if no other packages use Pyppeteer by, in order:

1) Removing the downloaded Chromium images by deleting the entire *directory* (and its subdirectories) shown by running:

.. code-block:: bash

   python -c "import pathlib; from pyppeteer.chromium_downloader import DOWNLOADS_FOLDER; print(pathlib.Path(DOWNLOADS_FOLDER).parent)"

2) Uninstalling the Pyppeteer package by running:

.. code-block:: bash

   pip uninstall pyppeteer


Rationale
:::::::::
The implementation of ``use_browser: true`` jobs (i.e. those running on a browser to run JavaScript) using Pyppeteer
and the Chromium browser it uses has been very problematic, as the library:

* is in alpha,
* is very slow,
* defaults to years-old obsolete versions of Chromium,
* can be insecure (e.g. found that TLS certificates were disabled for downloading browsers!),
* creates conflicts with imports (e.g. requires obsolete version of websockets),
* is poorly documented,
* is poorly maintained,
* may require OS-specific dependencies that need to be separately installed,
* does not work with Arm-based processors,
* is prone to crashing,
* and outright freezes withe the current version of Python (3.10)!

Pyppeteer's `open issues <https://github.com/pyppeteer/pyppeteer/issues>`__ now exceed 130 and are growing almost daily.

`Playwright <https://playwright.dev/python/>`__ has none of the issues above, the core dev team apparently is the same
who wrote Puppeteer (of which Pyppeteer is a port to Python), and is supported by the deep pockets of Microsoft. The
Python version is officially supported and up-to-date, and (in our configuration) uses the latest stable version of
Google Chrome out of the box without the contortions of manually having to pick and set revisions.

Playwright has been in beta testing within **webchanges** for months and has been performing very well (significantly
more so than Pyppeteer).


Documentation
-------------
* Major updates on anything that has to do with ``use_browser``.
* Fixed two examples of the ``email`` reporter. Reported by `jprokos  <https://github.com/jprokos>`__ in
  `#34 <https://github.com/mborsetti/webchanges/issues/34>`__.


Advanced
--------
* If you subclassed JobBase in your ``hooks.py`` file, and are defining a ``retrieve`` method, please note that the
  number of arguments has been increased to 3 as follows:

.. code-block:: python

   def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str]:
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved and the ETag.
        """


Version 3.9.2
------------------
2022-04-13

⚠ Last release using Pyppeteer
```````````````````````````````
* This is the last release using Pyppeteer for jobs with ``use_browser: true``, which will be replaced by Playwright
  in release 9.10, forthcoming hopefully in a few weeks. See above for more information on how to prepare -- and start
  using Playwright now!

Added
`````
* New ``ignore_dh_key_too_small`` directive for ``url`` jobs to overcome the ``ssl.SSLError: [SSL: DH_KEY_TOO_SMALL] dh
  key too small (_ssl.c:1129)`` error.
* New ``indent`` sub-directive for the ``beautify`` filter (requires BeautifulSoup version 4.11.0 or later).
* New ``--dump-history JOB`` command line argument to print all saved snapshot history for a job.
* Playwright only: new``--no-headless`` command line argument to help with debugging and testing (e.g. run
  ``webchanges --test 1 --no-headless``).  Not available for Pyppeteer.
* Extracted Discord reporting from ``webhooks`` into its own ``discord`` reporter to fix it not working and to
  add embedding functionality as well as color (contributed by `Michał Ciołek  <https://github.com/michalciolek>`__
  `upstream <https://github.com/thp/urlwatch/issues/683>`__. Reported by `jprokos <https://github.com/jprokos>`__` in
  `#33 <https://github.com/mborsetti/webchanges/issues/33>`__.)

Fixed
`````
* We are no longer rewriting to disk the entire database at every run. Now it's only rewritten if there are changes
  (and minimally) and, obviously, when running with the ``--gc-cache`` or ``--clean-cache`` command line argument.
  Reported by `JsBergbau <https://github.com/JsBergbau>`__ `upstream <https://github.com/thp/urlwatch/issues/690>`__.
  Also updated documentation suggesting to run ``--clean-cache`` or ``--gc-cache`` periodically.
* A ValueError is no longer raised if an unknown directive is found in the configuration file, but a Warning is
  issued instead. Reported by `c0deing <https://github.com/c0deing>`__ in `#26
  <https://github.com/mborsetti/webchanges/issues/26>`__.
* The ``kind`` job directive (used for custom job classes in ``hooks.py``) was undocumented and not fully functioning.
* For jobs with ``use_browser: true`` and a ``switch`` directive containing ``--window-size``, turn off Playwright's
  default fixed viewport (of 1280x720) as it overrides ``--window-size``.
* Email headers ("From:", "To:", etc.) now have title case per RFC 2076. Reported by `fdelapena
  <https://github.com/fdelapena>`__ in `#29 <https://github.com/mborsetti/webchanges/issues/29>`__.

Documentation
-------------
* Added warnings for Windows users to run Python in UTF-8 mode. Reported by `Knut Wannheden
  <https://github.com/knutwannheden>`__ in `#25 <https://github.com/mborsetti/webchanges/issues/25>`__.
* Added suggestion to run ``--clean-cache`` or ``--gc-cache`` periodically to compact the database file.
* Continued improvements.

Internals
`````````
* Updated licensing file to `GitHub naming standards
  <https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/adding-a-license-to-a-repository>`__
  and updated its contents to more clearly state that this software redistributes source code of release 2.21 dated 30
  July 2020 of urlwatch (https://github.com/thp/urlwatch/tree/346b25914b0418342ffe2fb0529bed702fddc01f) retaining its
  license, which is distributed as part of the source code.
* Pyppeteer has been removed from the test suite.
* Deprecated ``webchanges.jobs.ShellError`` exception in favor of Python's native ``subprocess.SubprocessError`` one and
  its subclasses.

Version 3.9.1
------------------
2022-01-27

Fixed
`````
* Config file directives checker would incorrect reject reports added through ``hooks.py``. Reported by `Knut Wannheden
  <https://github.com/knutwannheden>`__ in `#24 <https://github.com/mborsetti/webchanges/issues/24>`__.


Version 3.9
------------------
2022-01-26

Changed
```````
* The method ``bs4`` of filter ``html2text`` has a new ``strip`` sub-directive which is passed to BeautifulSoup, and
  its default value has changed to false to conform to BeautifulSoup's default. This gives better output in most
  cases. To restore the previous non-standard behavior, add the ``strip: true`` sub-directive to the ``html2text``
  filter of jobs.
* Pyppeteer (used for ``url`` jobs with ``use_browser: true``) is now crashing during certain tests with Python 3.7.
  There will be no new development to fix this as the use of Pyppeteer will soon be deprecated in favor of Playwright.
  See above to start using Playwright now (highly suggested).

Added
`````
* The method ``bs4`` of filter ``html2text`` now accepts the sub-directives ``separator`` and ``strip``.
* When using the command line argument ``--test-diff``, the output can now be sent to a specific reporter by also
  specifying the ``--test-reporter`` argument. For example, if running on a machine with a web browser, you can see
  the HTML version of the last diff(s) from job 1 with ``webchanges --test-diff 1 --test-reporter browser`` on your
  local browser.
* New filter ``remove-duplicate-lines``. Contributed by `Michael Sverdlin <https://github.com/sveder>`__ upstream `here
  <https://github.com/thp/urlwatch/pull/653>`__ (with modifications).
* New filter ``csv2text``. Contributed by `Michael Sverdlin <https://github.com/sveder>`__ upstream `here
  <https://github.com/thp/urlwatch/pull/658>`__ (with modifications).
* The ``html`` report type has a new job directive ``monospace`` which sets the output to use a monospace font.
  This can be useful e.g. for tabular text extracted by the ``pdf2text`` filter.
* The ``command_run`` report type has a new environment variable ``WEBCHANGES_CHANGED_JOBS_JSON``.
* Opt-in to use Playwright for jobs with ``use_browser: true`` instead of pyppeteer (see above).

Fixed
`````
* During conversion of Markdown to HTML,
  * Code blocks were not rendered without wrapping and in monospace font;
  * Spaces immediately after ````` (code block opening) were being dropped.
* The ``email`` reporter's ``sendmail`` sub-directive was not passing the ``from`` sub-directive (when specified) to
  the ``sendmail`` executable as an ``-f`` command line argument. Contributed by
  `Jonas Witschel <https://github.com/diabonas>`__ upstream `here <https://github.com/thp/urlwatch/pull/671>`__ (with
  modifications).
* HTML characters were not being unescaped when the job name is determined from the <title> tag of the data monitored
  (if present).
* Command line argument ``--test-diff`` was only showing the last diff instead of all saved ones.
* The ``command_run`` report type was not setting variables ``count`` and ``jobs`` (always 0). Contributed by
  `Brian Rak <https://github.com/devicenull>`__ in `#23 <https://github.com/mborsetti/webchanges/issues/23>`__.

Documentation
-------------
* Updated the "recipe" for monitoring Facebook public posts.
* Improved documentation for filter ``pdf2text``.

Internals
`````````
* Support for Python 3.10 (except for ``url`` jobs with ``use_browser`` using Pyppeteer since it does not yet support
  it; use Playwright instead).
* Improved speed of detection and handling of lines starting with spaces during conversion of Markdown to HTML.
* Logging (``--verbose``) now shows thread IDs to help with debugging.

Known issues
````````````
* Pyppeteer (used for ``url`` jobs with ``use_browser: true``) is now crashing during certain tests with Python 3.7.
  There will be no new development to fix this as the use of Pyppeteer will soon be deprecated in favor of Playwright.
  See above to start using Playwright now (highly suggested).


Version 3.8.3
------------------
2021-08-29

Fixed
`````
* Fixed incorrect handling of timeout when checking if new version has been released.

Internals
`````````
* DictType hints for configuration.


Version 3.8.2
------------------
2021-08-19

⚠ Breaking Changes (dependencies)
`````````````````````````````````
* Filter ``pdf2text``'s dependency Python package `pdftotext <https://github.com/jalan/pdftotext>`__ in its latest
  version 2.2.0 has changed the way it displays text to no longer try to emulate formatting (columns etc.). This is
  generally a welcome improvement as changes in formatting no longer trigger change reports, but if you want to
  return to the previous layout we have added a ``physical`` sub-directive which you need to set to ``true`` on the
  jobs affected. **Note that otherwise all your** ``pdf2text`` **jobs will report changes (in formatting) the first
  time they are run after the pdftotext Python package is updated**.

Changed
```````
* Updated default Chromium executables to revisions equivalent to Chromium 92.0.4515.131 (latest stable release); this
  fixes unsupported browser error thrown by certain websites. Use ``webchanges --chromium-directory`` to locate where
  older revision were downloaded to delete them manually.

Added
`````
* Filter ``pdf2text`` now supports the ``raw`` and ``physical`` sub-directives, which are passed to the underlying
  Python package `pdftotext <https://github.com/jalan/pdftotext>`__ (version 2.2.0 or higher).
* New ``--chromium-directory`` command line displays the directory where the downloaded Chromium executables are
  located to facilitate the deletion of older revisions.
* Footer now indicates if the run was made with a jobs file whose stem name is not the default 'jobs', to ease
  identification when running *webchanges* with a variety of jobs files.

Fixed
`````
* Fixed legacy code handling ``--edit-config`` command line argument to allow editing of a configuration file
  with YAML syntax errors (`#15 <https://github.com/mborsetti/webchanges/issues/15>`__ by
  `Markus Weimar <https://github.com/Markus00000>`__).
* Telegram reporter documentation was missing instructions on how to notify channels (`#16
  <https://github.com/mborsetti/webchanges/issues/16>`__ by `Sean Tauber <https://github.com/buzzeddesign>`__).

Internals
`````````
* Type hints are checked during pre-commit by `mypy <http://www.mypy-lang.org/>`__.
* Imports are rearranged during pre-commit by `isort <https://pycqa.github.io/isort/>`__.
* Now testing all database engines, including redis, and more, adding 4 percentage points of code coverage to 81%.
* The name of a FilterBase subclass is always its __kind__ + Filter (e.g. the class for ``element-by-id`` filter is
  named ElementByIDFilter and not GetElementByID)


Version 3.8.1
------------------
2021-08-03

Fixed
`````
* Files in the new _vendored directory are now installed correctly.


Version 3.8
------------------
2021-07-31

Added
`````
* ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) now recognize ``data`` and ``method`` directives,
  enabling e.g. to make a ``POST`` HTTP request using a browser with JavaScript support.
* New ``tz`` key for  ``report`` in the configuration sets the timezone for the diff in reports (useful if running
  e.g. on a cloud server in a different timezone). See `documentation
  <https://webchanges.readthedocs.io/en/stable/reporters.html#tz>`__.
* New ``run_command`` reporter to execute a command and pass the report text as its input. Suggested by `Marcos Alano
  <https://github.com/mhalano>`__ upstream `here <https://github.com/thp/urlwatch/issues/650>`__.
* New ``remove_repeated`` filter to remove repeated lines (similar to Unix's ``uniq``). Suggested by `Michael
  Sverdlin <https://github.com/Sveder>`__ upstream `here <https://github.com/thp/urlwatch/pull/653>`__.
* The ``user_visible_url`` job directive now applies to all type of jobs, including ``command`` ones. Suggested by
  `kongomongo <https://github.com/kongomongo>`__ upstream `here <https://github.com/thp/urlwatch/issue/608>`__.
* The ``--delete-snapshot`` command line argument now works with Redis database engine (``--database-engine redis``).
  Contributed by `Scott MacVicar <https://github.com/scottmac>`__ with pull request
  #`13 <https://github.com/mborsetti/webchanges/pull/13>`__.
* The ``execute`` filter (and ``shellpipe``) sets more environment variables to allow for more flexibility; see improved
  `documentation <https://webchanges.readthedocs.io/en/stable/filters.html#execute>`__ (including more examples).
* Negative job indices are allowed; for example, run ``webchanges -1`` to only run the last job of your jobs list, or
  ``webchanges --test -2`` to test the second to last job of your jobs list.
* Configuration file is now checked for invalid directives (e.g. typos) when program is run.
* Whenever a HTTP client error (4xx) response is received, in ``--verbose`` mode the content of the response is
  displayed with the error.
* If a newer version of **webchanges** has been released to PyPI, an advisory notice is printed to stdout and
  added to the report footer (if footer is enabled).

Fixed
`````
* The ``html2text`` filter's method ``strip_tags`` was returning HTML character references (e.g. &gt;, &#62;, &#x3e;)
  instead of the corresponding Unicode characters.
* Fixed a rare case when html report would not correctly reconstruct a clickable link from Markdown for items inside
  elements in a list.
* When using the ``--edit`` or ``--edit-config`` command line arguments to edit jobs or configuration files, symbolic
  links are no longer overwritten. Reported by `snowman <https://github.com/snowman>`__ upstream
  `here <https://github.com/thp/urlwatch/issues/604>`__.

Internals
`````````
* ``--verbose`` command line argument will now list configuration keys 'missing' from the file, keys for which default
  values have been used.
* ``tox`` testing can now be run in parallel using ``tox --parallel``.
* Additional testing, adding 3 percentage points of coverage to 78%.
* bump2version now follows `PEP440 <https://www.python.org/dev/peps/pep-0440/>`__ and has new documentation in
  the file ``.bumpversion.txt`` (cannot document ``.bumpversion.cfg`` as remarks get deleted at every version bump).
* Added a vendored version of packaging.version.parse() from `Packaging <https://www.pypi.com/project/packaging/>`__
  20.9, released on 2021-02-20, used to check if the version in PyPI is higher than the current one.
* Migrated from unmaintained Python package AppDirs to its friendly fork `platformdirs
  <https://github.com/platformdirs/platformdirs>`__, which is maintained and offers more functionality. Unless used
  by another package, you can uninstall appdirs with ``pip uninstall appdirs``.


Version 3.7
------------------
2021-06-27

⚠ Breaking Changes
``````````````````
* Removed Python 3.6 support to simplify code. Older Python versions are supported for 3 years after being obsoleted by
  a new major release; as Python 3.7 was released on 27 June 2018, the last date of Python 3.6 support was 26 June 2021

Changed
```````
* Improved ``telegram`` reporter now uses MarkdownV2 and preserves most formatting of HTML sites processed by the
  ``html2text`` filter, e.g. clickable links, bolding, underlining, italics and strikethrough

Added
`````
* New filter ``execute`` to filter the data using an executable without invoking the shell (as ``shellpipe`` does)
  and therefore exposing to additional security risks
* New sub-directive ``silent`` for ``telegram`` reporter to receive a notification with no sound (true/false) (default:
  false)
* Github Issues templates for bug reports and feature requests

Fixed
`````
* Job ``headers`` stored in the configuration file (``config.yaml``) are now merged correctly and case-insensitively
  with those present in the job (in ``jobs.yaml``). A header in the job replaces a header by the same name if already
  present in the configuration file, otherwise is added to the ones present in the configuration file.
* Fixed ``TypeError: expected string or bytes-like object`` error in cookiejar (called by requests module) caused by
  some ``cookies`` being read from the jobs YAML file in other formats

Internals
`````````
* Strengthened security with `bandit <https://pypi.org/project/bandit/>`__ to catch common security issues
* Standardized code formatting with `black <https://pypi.org/project/black/>`__
* Improved pre-commit speed by using local libraries when practical
* More improvements to type hinting (moving towards testing with `mypy <https://pypi.org/project/mypy/>`__)
* Removed module jobs_browser.py (needed only for Python 3.6)


Version 3.6.1
------------------
2021-05-28

Reminder
--------
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.7 was
released on 27 June 2018, the codebase will be streamlined by removing support for Python 3.6 on or after 27 June 2021.

Added
`````
* Clearer results messages for ``--delete-snapshot`` command line argument

Fixed
`````
* First run would fail when creating new ``config.yaml`` file. Thanks to `David <https://github.com/notDavid>`__ in
  issue `#10 <https://github.com/mborsetti/webchanges/issues/10>`__.
* Use same run duration precision in all reports


Version 3.6
------------------
2021-05-14

Added
`````
* Run a subset of jobs by adding their index number(s) as command line arguments. For example, run ``webchanges 2 3`` to
  only run jobs #2 and #3 of your jobs list. Run ``webchanges --list`` to find the job numbers. Suggested by `Dan Brown
  <https://github.com/dbro>`__ upstream `here <https://github.com/thp/urlwatch/pull/641>`__. API is experimental and
  may change in the near future.
* Support for ``ftp://`` URLs to download a file from an ftp server

Fixed
`````
* Sequential job numbering (skip numbering empty jobs). Suggested by `Markus Weimar
  <https://github.com/Markus00000>`__ in issue `#9 <https://github.com/mborsetti/webchanges/issues/9>`__.
* Readthedocs.io failed to build autodoc API documentation
* Error processing jobs with URL/URIs starting with ``file:///``

Internals
`````````
* Improvements of errors and DeprecationWarnings during the processing of job directives and their inclusion in tests
* Additional testing adding 3 percentage points of coverage to 75%
* Temporary database being written during run is now in memory-first (handled by SQLite3) (speed improvement)
* Updated algorithm that assigns a job to a subclass based on directives found
* Migrated to using the `pathlib <https://docs.python.org/3/library/pathlib.html>`__ standard library


Version 3.5.1
------------------
2021-05-06

Fixed
`````
* Crash in ``RuntimeError: dictionary changed size during iteration`` with custom headers; updated testing scenarios
* Autodoc not building API documentation


Version 3.5
------------------
2021-05-04

Added
`````
* New sub-directives to the ``strip`` filter:

  * ``chars``: Set of characters to be removed (default: whitespace)
  * ``side``: One-sided removal, either ``left`` (leading characters) or ``right`` (trailing characters)
  * ``splitlines``: Whether to apply the filter on each line of text (true/false) (default: ``false``, i.e. apply to
    the entire data)
* ``--delete-snapshot`` command line argument: Removes the latest saved snapshot of a job from the database; useful
  if a change in a website (e.g. layout) requires modifying filters as invalid snapshot can be deleted and
  **webchanges** rerun to create a truthful diff
* ``--log-level`` command line argument to control the amount of logging displayed by the ``-v`` argument
* ``ignore_connection_errors``, ``ignore_timeout_errors``, ``ignore_too_many_redirects`` and ``ignore_http_error_codes``
  directives now work with ``url`` jobs having ``use_browser: true`` (i.e. using *Pyppeteer* when running in Python
  3.7 or higher

Changed
```````
* Diff-filter ``additions_only`` will no longer report additions that consist exclusively of added empty lines
  (issue `#6 <https://github.com/mborsetti/webchanges/issues/6>`__, contributed by `Fedora7
  <https://github.com/Fedora7>`__)
* Diff-filter ``deletions_only`` will no longer report deletions that consist exclusively of deleted empty lines
* The job's index number is included in error messages for clarity
* ``--smtp-password`` now checks that the credentials work with the SMTP server (i.e. logs in)

Fixed
`````
* First run after install was not creating new files correctly (inherited from *urlwatch*); now **webchanges** creates
  the default directory, config and/or jobs files if not found when running (issue `#8
  <https://github.com/mborsetti/webchanges/issues/8>`__, contributed  by `rtfgvb01 <https://github.com/rtfgvb01>`__)
* ``test-diff`` command line argument was showing historical diffs in wrong order; now showing most recent first
* An error is now raised when a ``url`` job with ``use_browser: true`` returns no data due to an HTTP error (e.g.
  proxy_authentication_required)
* Jobs were included in email subject line even if there was nothing to report after filtering with ``additions_only``
  or ``deletions_only``
* ``hexdump`` filter now correctly formats lines with less than 16 bytes
* ``sha1sum`` and ``hexdump`` filters now accept data that is bytes (not just text)
* An error is now raised when a legacy ``minidb`` database is found but cannot be converted because the ``minidb``
  package is not installed
* Removed extra unneeded file from being installed
* Wrong ETag was being captured when a URL redirection took place

Internals
`````````
* ``url`` jobs using ``use_browser: true`` (i.e. using *Pyppeteer*) now capture and save the ETag
* Snapshot timestamps are more accurate (reflect when the job was launched)
* Each job now has a run-specific unique index_number, which is assigned sequentially when loading jobs, to use in
  errors and logs for clarity
* Improvements in the function chunking text into numbered lines, which used by certain reporters (e.g. Telegram)
* More tests, increasing code coverage by an additional 7 percentage points to 72% (although keyring testing had to be
  dropped due to issues with GitHub Actions)
* Additional cleanup of code and documentation

Known issues
````````````
* ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) will at times display the below error message in
  stdout (terminal console). This does not affect **webchanges** as all data is downloaded, and hopefully it will be
  fixed in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.4.1
------------------
2021-04-17

Internals
`````````
* Temporary database (``sqlite3`` database engine) is copied to permanent one exclusively using SQL code instead of
  partially using a Python loop

Known issues
````````````
* ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) will at times display the below error message in
  stdout (terminal console). This does not affect **webchanges** as all data is downloaded, and hopefully it will be
  fixed in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.4
------------------
2021-04-12

⚠ Breaking Changes
``````````````````
* Fixed the database from growing unbounded to infinity. Fix only works when running in Python 3.7 or higher and using
  the new, default, ``sqlite3`` database engine. In this scenario only the latest 4 snapshots are kept, and older ones
  are purged after every run; the number is selectable with the new ``--max-snapshots`` command line argument. To keep
  the existing grow-to-infinity behavior, run **webchanges** with ``--max-snapshots 0``.

Added
`````
* ``--max-snapshots`` command line argument sets the number of snapshots to keep stored in the database; defaults to
  4. If set to 0 an unlimited number of snapshots will be kept. Only applies to Python 3.7 or higher and only works if
  the default ``sqlite3`` database is being used.
* ``no_redirects`` job directive (for ``url`` jobs) to disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection
  (true/false). Suggested by `snowman <https://github.com/snowman>`__ upstream `here
  <https://github.com/thp/urlwatch/issues/635>`__.
* Reporter ``prowl`` for the `Prowl <https://prowlapp.com>`__ push notification client for iOS (only). Contributed
  by `nitz <https://github.com/nitz>`__ upstream in PR `633 <https://github.com/thp/urlwatch/pull/633>`__.
* Filter ``jq`` to parse, transform, and extract ASCII JSON data. Contributed by `robgmills
  <https://github.com/robgmills>`__ upstream in PR `626 <https://github.com/thp/urlwatch/pull/626>`__.
* Filter ``pretty-xml`` as an alternative to ``format-xml`` (backwards-compatible with *urlwatch* 2.28)
* Alert user when the jobs file contains unrecognized directives (e.g. typo)

Changed
```````
* Job name is truncated to 60 characters when derived from the title of a page (no directive ``name`` is found in a
  ``url`` job)
* ``--test-diff`` command line argument displays all saved snapshots (no longer limited to 10)

Fixed
`````
* Diff (change) data is no longer lost if **webchanges** is interrupted mid-execution or encounters an error in
  reporting: the permanent database is updated only at the very end (after reports are dispatched)
* ``use_browser: false`` was not being interpreted correctly
* Jobs file (e.g. ``jobs.yaml``) is now loaded only once per run

Internals
`````````
* Database ``sqlite3`` engine now saves new snapshots to a temporary database, which is copied over to the permanent one
  at execution end (i.e. database.close())
* Upgraded SMTP email message internals to use Python's `email.message.EmailMessage
  <https://docs.python.org/3/library/email.message.html#email.message.EmailMessage>`__ instead of ``email.mime``
  (obsolete)
* Pre-commit documentation linting using ``doc8``
* Added logging to ``sqlite3`` database engine
* Additional testing increasing overall code coverage by an additional 4 percentage points to 65%
* Renamed legacy module browser.py to jobs_browser.py for clarity
* Renamed class JobsYaml to YamlJobsStorage for consistency and clarity

Known issues
````````````
* ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) will at times display the below error message in
  stdout (terminal console). This does not affect **webchanges** as all data is downloaded, and hopefully it will be
  fixed in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.2.6
------------------
2021-03-21

Changed
```````
* Tweaked colors (esp. green) of HTML reporter to work with Dark Mode
* Restored API documentation using Sphinx's autodoc (removed in 3.2.4 as it was not building correctly)

Internals
`````````
* Replaced custom atomic_rename function with built-in `os.replace()
  <https://docs.python.org/3/library/os.html#os.replace>`__ (new in Python 3.3) that does the same thing
* Added type hinting to the entire code
* Added new tests, increasing coverage to 61%
* GitHub Actions CI now runs faster as it's set to cache required packages from prior runs

Known issues
````````````
* Discovered that upstream (legacy) *urlwatch* 2.22 code has the database growing to infinity; run ``webchanges
  --clean-cache`` periodically to discard old snapshots until this is addressed in a future release
* ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) will at times display the below error message in
  stdout (terminal console). This does not affect **webchanges** as all data is downloaded, and hopefully it will be
  fixed in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.2
------------------
2021-03-08

Added
`````
* Job directive ``note``: adds a freetext note appearing in the report after the job header
* Job directive ``wait_for_navigation`` for ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*): wait for
  navigation to reach a URL starting with the specified one before extracting content. Useful when the URL redirects
  elsewhere before displaying content you're interested in and *Pyppeteer* would capture the intermediate page.
* command line argument ``--rollback-cache TIMESTAMP``: rollback the snapshot database to a previous time, useful when
  you miss notifications; see `here <https://webchanges.readthedocs.io/en/stable/cli.html#rollback-cache>`__. Does not
  work with database engine ``minidb`` or ``textfiles``.
* command line argument ``--cache-engine ENGINE``: specify ``minidb`` to continue using the database structure used
  in prior versions and *urlwatch* 2. New default ``sqlite3`` creates a smaller database due to data compression with
  `msgpack <https://msgpack.org/index.html>`__ and offers additional features; migration from old minidb database is
  done automatically and the old database preserved for manual deletion.
* Job directive ``block_elements`` for ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) (⚠ ignored in
  Python < 3.7) (experimental feature): specify `resource types
  <https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest/ResourceType>`__ (elements) to
  skip requesting (downloading) in order to speed up retrieval of the content; only resource types `supported by
  Chromium <https://developer.chrome.com/docs/extensions/reference/webRequest/#type-ResourceType>`__ are allowed
  (typical list includes ``stylesheet``, ``font``, ``image``, and ``media``). ⚠ On certain sites it seems to totally
  freeze execution; test before use.

Changed
```````
* A new, more efficient indexed database is used and only the most recent saved snapshot is migrated the first time you
  run this version. This has no effect on the ordinary use of the program other than reducing the number of historical
  results from ``--test-diffs`` util more snapshots are captured. To continue using the legacy database format, launch
  with ``database-engine minidb`` and ensure that the package ``minidb`` is installed.
* If any jobs have ``use_browser: true`` (i.e. are using *Pyppeteer*), the maximum number of concurrent threads is set
  to the number of available CPUs instead of the `default
  <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor>`__ to avoid
  instability due to *Pyppeteer*'s high usage of CPU
* Default configuration now specifies the use of Chromium revisions equivalent to Chrome 89.0.4389.72
  for ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) to increase stability. Note: if you already have
  a configuration file and want to upgrade to this version, see `here
  <https://webchanges.readthedocs.io/en/stable/advanced.html#using-a-chromium-revision-matching-a-google-chrome-chromium-release>`__.
  The Chromium revisions used now are 'linux': 843831, 'win64': 843846, 'win32': 843832, and 'mac': 843846.
* Temporarily removed code autodoc from the documentation as it was not building correctly

Fixed
`````
* Specifying ``chromium_revision`` had no effect (bug introduced in version 3.1.0)
* Improved the text of the error message when ``jobs.yaml`` has a mistake in the job parameters

Internals
`````````
* Removed dependency on ``minidb`` package and are now directly using Python's built-in ``sqlite3``, allowing for better
  control and increased functionality
* Database is now smaller due to data compression with `msgpack <https://msgpack.org/index.html>`__
* Migration from an old schema database is automatic and the last snapshot for each job will be migrated to the new one,
  preserving the old database file for manual deletion
* No longer backing up database to \*.bak now that it can be rolled back
* New command line argument ``--database-engine`` allows selecting engine and accepts ``sqlite3`` (default),
  ``minidb`` (legacy compatibility, requires package by the same name) and ``textfiles`` (creates a text file of the
  latest snapshot for each job)
* When running in Python 3.7 or higher, jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) are a bit more reliable
  as they are now launched using ``asyncio.run()``, and therefore Python takes care of managing the asyncio event loop,
  finalizing asynchronous generators, and closing the threadpool, tasks that previously were handled by custom code
* 11 percentage point increase in code testing coverage, now also testing jobs that retrieve content from the internet
  and (for Python 3.7 and up) use *Pyppeteer*

Known issues
````````````
* ``url`` jobs with ``use_browser: true`` (i.e. using *Pyppeteer*) will at times display the below error message in
  stdout (terminal console). This does not affect **webchanges** as all data is downloaded, and hopefully it will be
  fixed in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``


Version 3.1.1
------------------
2021-02-08

Fixed
`````
* Documentation was failing to build at https://webchanges.readthedocs.io/


Version 3.1
------------------
2021-02-07

Added
`````
* Can specify different values of ``chromium_revision`` (used in jobs with ``use_browser" true``, i.e. using
  *Pyppeteer*) based on OS by specifying keys ``linux``, ``mac``, ``win32`` and/or ``win64``
* If ``shellpipe`` filter returns an error it now shows the error text
* Show deprecation warning if running on the lowest Python version supported (mentioning the 3 years support from the
  release date of the next major version)

Fixed
`````
* ``telegram`` reporter's ``chat_id`` can be numeric (fixes # `610 <https://github.com/thp/urlwatch/issues/610>`__
  upstream by `ramelito <https://github.com/ramelito>`__)

Internals
`````````
* First PyPI release with new continuous integration (CI) and continuous delivery (CD) pipeline based on `bump2version
  <https://pypi.org/project/bump2version/>`__, git tags, and `GitHub Actions <https://docs.github.com/en/actions>`__
* Moved continuous integration (CI) testing from Travis to `GitHub Actions <https://docs.github.com/en/actions>`__
* Moved linting (flake8) and documentation build testing from pytest to the `pre-commit
  <https://pre-commit.com>`__ framework
* Added automated pre-commit local testing using `tox <https://tox.readthedocs.io/en/latest/>`__
* Added continuous integration (CI) testing on macOS platform


Version 3.0.3
------------------
2020-12-21

⚠ Breaking Changes
``````````````````
* Compatibility with *urlwatch* 2.22, including the ⚠ breaking change of removing the ability to write custom filters
  that do not take a subfilter as argument (see `here
  <https://urlwatch.readthedocs.io/en/latest/deprecated.html#filters-without-subfilters-since-2-22>`__ upstream)
* Inadvertently released as a PATCH instead of a MAJOR release as it should have been under `Semantic Versioning
  <https://semver.org/spec/v2.0.0.html#semantic-versioning-200>`__ rules given the incompatible API change upstream (see
  discussion `here <https://github.com/thp/urlwatch/pull/600#issuecomment-754525630>`__ upstream)

Added
`````
* New job sub-directive ``user_visible_url`` to replace the URL in reports, useful e.g. if the watched URL is a REST
  API endpoint but you want to link to the webpage instead (# `590 <https://github.com/thp/urlwatch/pull/590>`__
  upstream by `huxiba <https://github.com/huxiba>`__)

Changed
```````
* The Markdown reporter now supports limiting the report length via the ``max_length`` parameter of the ``submit``
  method. The length limiting logic is smart in the sense that it will try trimming the details first, followed by
  omitting them completely, followed by omitting the summary. If a part of the report is omitted, a note about this is
  added to the report. (# `572 <https://github.com/thp/urlwatch/issues/572>`__ upstream by `Denis Kasak
  <https://github.com/dkasak>`__)

Fixed
`````
* Make imports thread-safe. This might increase startup times a bit, as dependencies are imported on boot instead of
  when first used, but importing in Python is not (yet) thread-safe, so we cannot import new modules from the parallel
  worker threads reliably (# `559 <https://github.com/thp/urlwatch/issues/559>`__ upstream by `Scott MacVicar
  <https://github.com/scottmac>`__)
* Write Unicode-compatible YAML files

Internals
`````````
* Upgraded to use of `subprocess.run <https://docs.python.org/3/library/subprocess.html#subprocess.run>`__


Version 3.0.2
------------------
2020-12-06

Fixed
`````
* Logic error in reading ``EDITOR`` environment variable (# `1 <https://github.com/mborsetti/webchanges/issues/1>`__
  contributed by `MazdaFunSun <https://github.com/mazdafunsunn>`__)


Version 3.0.1
------------------
2020-12-05

Added
`````
* New ``format-json`` sub-directive ``sort_keys`` sets whether JSON dictionaries should be sorted (defaults to false)
* New ``markdown`` directive for ``webhook`` reporter for services such as Mattermost, which expects
  Markdown-formatted text
* Code autodoc, highlighting just how badly the code needs documentation!
* Output from ``diff_tool: wdiff`` is colorized in html reports
* Reports now show date/time of diffs when using an external ``diff_tool``

Changed and deprecated
``````````````````````
* Reporter ``slack`` has been renamed to ``webhook`` as it works with any webhook-enabled service such as Discord.
  Updated documentation with Discord example. The name ``slack``, while deprecated and in line to be removed in a future
  release, is still recognized.
* Improvements in report colorization code

Fixed
`````
* Fixed ``format-json`` filter from unexpectedly reordering contents of dictionaries
* Fixed documentation for ``additions_only`` and ``deletions_only`` to specify that value of true is required
* No longer creating a config directory if command line contains both ``--config`` and ``--urls``. Allow running on
  read-only systems (e.g. using redis or a database cache residing on a writeable volume)
* Deprecation warnings now use the ``DeprecationWarning`` category, which is always printed
* All filters take a subfilter (# `600 <https://github.com/thp/urlwatch/pull/600>`__ upstream by `Martin Monperrus
  <https://github.com/monperrus>`__)


Version 3.0
------------------
2020-11-12

Milestone
`````````
Initial release of **webchanges**, based on reworking of code from *urlwatch* 2.21 dated 30 July 2020.

Added
`````
Relative to *urlwatch* 2.21:

* If no job ``name`` is provided, the title of an HTML page will be used for a job name in reports
* The Python ``html2text`` package (used by the ``html2text`` filter, previously known as ``pyhtml2text``) is now
  initialized with the following purpose-optimized non-default `options
  <https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options>`__: unicode_snob = True,
  body_width = 0, single_line_break = True, and ignore_images = True
* The output from ``html2text`` filter is reconstructed into HTML (for html reports), preserving basic formatting
  such as bolding, italics, underlining, list bullets, etc. as well as, most importantly, rebuilding clickable links
* HTML formatting uses color (green or red) and strikethrough to mark added and deleted lines
* HTML formatting is radically more legible and useful, including long lines wrapping around
* HTML reports are now rendered correctly by email clients who override stylesheets (e.g. Gmail)
* Filter ``format-xml`` reformats (pretty-prints) XML
* ``webchanges --errors`` will run all jobs and list all errors and empty responses (after filtering)
* Browser jobs now recognize ``cookies``, ``headers``, ``http_proxy``, ``https_proxy``, and ``timeout`` sub-directives
* The revision number of Chromium browser to use can be selected with ``chromium_revision``
* Can set the user directory for the Chromium browser with ``user_data_dir``
* Chromium can be directed to ignore HTTPs errors with ``ignore_https_errors``
* Chromium can be directed as to when to consider a page loaded with ``wait_until``
* Additional command line arguments can be passed to Chromium with ``switches``
* New ``browser`` reporter to display HTML-formatted report on a local browser
  when monitoring only new content)
* New ``additions_only`` directive to report only added lines (useful when monitoring only new content)
* New ``deletions_only`` directive to report only deleted lines
* New ``contextlines`` directive to set the number of context lines in the unified diff
* Support for Python Version 3.9
* Backward compatibility with *urlwatch* 2.21 (except running on Python 3.5 or using ``lynx``, which is replaced by
  the built-in ``html2text`` filter)

Changed and deprecated
``````````````````````
Relative to *urlwatch* 2.21:

* Navigation by full browser is now accomplished by specifying the ``url`` and adding the ``use_browser: true``
  directive. The ``navigate`` directive has been deprecated for clarity and will trigger a warning; it will be
  removed in a future release
* The name of the default program configuration file has been changed to ``config.yaml``; if at program launch
  ``urlwatch.yaml`` is found and no ``config.yaml`` exists, it is copied over for backward-compatibility.
* In Windows, the location of config files has been moved to ``%USERPROFILE%\Documents\webchanges``
  where they can be more easily edited (they are indexed there) and backed up
* The ``html2text`` filter defaults to using the Python ``html2text`` package (with optimized defaults) instead of
  ``re``
* ``keyring`` Python package is no longer installed by default
* ``html2text`` and ``markdown2`` Python packages are installed by default
* Installation of Python packages required by a feature is now made easier with pip extras (e.g. ``pip install -U
  webchanges[ocr,pdf2text]``)
* The name of the default job's configuration file has been changed to ``jobs.yaml``; if at program launch ``urls.yaml``
  is found and no ``jobs.yaml`` exists, it is copied over for backward-compatibility
* The ``html2text`` filter's ``re`` method has been renamed ``strip_tags``, which is deprecated and will trigger a
  warning
* The ``grep`` filter has been renamed ``keep_lines_containing``, which is deprecated and will trigger a warning; it
  will be removed in a future release
* The ``grepi`` filter has been renamed ``delete_lines_containing``, which is deprecated and will trigger a warning; it
  will be removed in a future release
* Both the ``keep_lines_containing`` and ``delete_lines_containing`` accept ``text`` (default) in addition to ``re``
  (regular expressions)
* ``--test`` command line argument is used to test a job (formerly ``--test-filter``, deprecated and will be removed in
  a future release)
* ``--test-diff`` command line argument is used to test a jobs' diff (formerly ``--test-diff-filter``, deprecated and
  will be removed in a future release)
* ``-V`` command line argument added as an alias to ``--version``
* If a filename for ``--jobs``, ``--config`` or ``--hooks`` is supplied without a path and the file is not present in
  the current directory, **webchanges** now looks for it in the default configuration directory
* If a filename for ``--jobs`` or ``--config`` is supplied without a '.yaml' suffix, **webchanges** now looks for one
  with such a suffix
* In Windows, ``--edit`` defaults to using built-in notepad.exe if %EDITOR% or %VISUAL% are not set
* When using ``--job`` command line argument, if there's no file by that name in the specified directory will look in
  the default one before giving up.
* The use of the ``kind`` directive in ``jobs.yaml`` configuration files has been deprecated (but is, for now, still
  used internally); it will be removed in a future release
* The ``slack`` webhook reporter allows the setting of maximum report length (for, e.g., usage with Discord) using the
  ``max_message_length`` sub-directive
* Legacy ``lib/hooks.py`` file is no longer supported; ``hooks.py`` needs to be in the same directory as the
  configuration files.
* The database (cache) file is backed up at every run to \*.bak
* The mix of default and optional dependencies has been updated (see documentation) to enable "Just works"
* Dependencies are now specified as PyPI `extras
  <https://stackoverflow.com/questions/52474931/what-is-extra-in-pypi-dependency>`__ to simplify their installation
* Changed timing from `datetime <https://docs.python.org/3/library/datetime.html>`__ to `timeit.default_timer
  <https://docs.python.org/3/library/timeit.html#timeit.default_timer>`__
* Upgraded concurrent execution loop to `concurrent.futures.ThreadPoolExecutor.map
  <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor.map>`__
* Reports' elapsed time now always has at least 2 significant digits
* Expanded (only slightly) testing
* Using flake8 to check PEP-8 compliance and more
* Using coverage to check unit testing coverage
* Upgraded Travis CI to Python Version 3.9 from Version 3.9-dev and cleaned up pip installs

Removed
```````
Relative to *urlwatch* 2.21:

* The ``html2text`` filter's ``lynx`` method is no longer supported; use ``html2text`` instead
* Python 3.5 (obsoleted by 3.6 on December 23, 2016) is no longer supported

Fixed
`````
Relative to *urlwatch* 2.21:

* The ``html2text`` filter's ``html2text`` method defaults to Unicode handling
* HTML href links ending with spaces are no longer broken by ``xpath`` replacing spaces with ``%20``
* Initial config file no longer has directives sorted alphabetically, but are saved logically (e.g. 'enabled' is always
  the first sub-directive)
* The presence of the ``data`` directive in a job would force the method to POST preventing PUTs

Security
````````
Relative to *urlwatch* 2.21:

* None

Documentation changes
`````````````````````
Relative to *urlwatch* 2.21:

* Complete rewrite of the documentation

Known bugs
``````````
* None
