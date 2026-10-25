Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.13 was
released on 7 October 2024, the codebase will be streamlined by removing support for Python 3.12 on or after 7
October 2027.

⚠ Breaking Changes
``````````````````
* Removed support for Python 3.11. As a reminder, older Python versions are supported for 3 years after being obsoleted
  by a new major release.
* The ``empty_as_transient`` job directive, introduced 3 days earlier in version 3.37.0, has been retired in favor
  of the new ``empty_as_error`` one (see below), whose name describes what you actually observe. It is no longer
  recognized: if you use it, rename it in your jobs file, or the run aborts with the error
  ``Directive 'empty_as_transient' is unrecognized``.
  See https://webchanges.readthedocs.io/en/stable/jobs.html#empty-as-error.

Added
`````
* Support for Python 3.15, including its free-threaded (GIL-free) build 3.15t. Please note that certain optional
  dependencies may not yet support free-threaded Python. On Python 3.15, the ``deepdiff`` and ``deepdiff_xml``
  extras install ``deepdiff`` 8.x, as ``deepdiff`` 9 requires a version of ``cachebox`` that cannot be installed on
  Python 3.15. On Windows, installing on Python 3.15 requires first setting the environment variable
  ``PYYAML_FORCE_LIBYAML=0``, as the ``PyYAML`` dependency does not yet publish packages for Python 3.15 and building
  its optional C extension fails there; see
  https://webchanges.readthedocs.io/en/stable/introduction.html#install-windows.
* New ``xmltojson`` and ``xmltoyaml`` filters: they convert XML (e.g. an API response or a feed) to JSON or YAML using
  the ``xmltodict`` package, so that changes are reported as readable keys and values; attributes become keys prefixed
  with ``@``. ``xmltojson`` supports the same sub-directives as ``format-json``. Install with
  ``uv pip install --upgrade webchanges[xmltodict]``. See
  https://webchanges.readthedocs.io/en/stable/filters.html#xmltojson.
* New ``compact`` sub-directive of the ``format-json`` filter: removes all unnecessary whitespace. See
  https://webchanges.readthedocs.io/en/stable/filters.html#format-json.
* New ``!env`` YAML tag: inserts the value of environment variables anywhere within a string value of the jobs or
  configuration file. Reference a variable as ``${VAR}``, or as ``${VAR:-default}`` to fall back to ``default`` when
  the variable is not set; an unset variable without a default aborts the run with an error reporting the variable's
  name and line. Useful to define a value shared by multiple jobs in a single place (e.g. a version number appearing
  in multiple URLs and names, which can even be computed by a wrapper script before invoking **webchanges**) and to
  keep secrets such as API tokens out of the YAML files. Suggested by Marcos Alano in
  https://github.com/mborsetti/webchanges/issues/99. See
  https://webchanges.readthedocs.io/en/stable/advanced.html#using-environment-variables.
* New ``tags`` job directive: one tag, or a list of tags, grouping jobs so that they can be acted on together. Tags
  are used by the new ``--tags`` command line argument and by the new ``tags`` reporter directive (both below).
  See https://webchanges.readthedocs.io/en/stable/jobs.html#tags.
* New ``--tags`` command line argument: runs only the jobs having any of the tags listed (comma-separated, and the
  argument can be repeated), e.g. ``webchanges --tags personal,team``. Can be combined with a joblist, in which case
  both restrictions apply. See https://webchanges.readthedocs.io/en/stable/cli.html#tags-cli.
* New ``tags`` reporter directive (accepted by every reporter): restricts the reporter to the jobs having any of the
  tags listed. Reports so restricted note in their footer how many of the jobs run they cover, and a job that ends up
  being reported by no reporter at all (typically a typo in a tag) is called out in a warning. See
  https://webchanges.readthedocs.io/en/stable/reporters.html#reporter-tags.
* A reporter can now be configured more than once, by replacing its single set of directives in the configuration
  file with a list of them; each entry is an independent configuration of that reporter, and directives left out of
  an entry take their default value. Combined with the ``tags`` directive above, this allows different jobs to be
  reported to different destinations, e.g. to different email addresses or Telegram chats. See
  https://webchanges.readthedocs.io/en/stable/reporters.html#multiple-reporters.
* The ``html2text`` filter now JSON-decodes data whose media type is JSON and that consists entirely of a JSON string
  (i.e. HTML returned inside a JSON-encoded string), so that its Unicode escape sequences are converted into the
  characters they represent instead of being reported verbatim.
* New ``empty_as_error`` job directive: when the server or a command returns an empty response or output consisting
  only of whitespace, it is treated as a transient error (with the synthetic HTTP response status code 999) instead
  of as valid empty content, so the snapshot database retains the last non-empty content and a flaky site or command
  that intermittently returns nothing no longer triggers a change report when the content "disappears" and another
  one when it is restored. Combine with ``max_tries`` to be notified only of persistent empty responses, or with
  ``ignore_http_error_codes: 999`` (or, for ``command`` jobs, ``suppress_errors``) to never be notified of them.
  Suggested by Marcos Alano in https://github.com/mborsetti/webchanges/issues/169. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#empty-as-error.
* New ``markdown_extras`` job directive: sets the extras (https://github.com/trentm/python-markdown2/wiki/Extras) of
  the ``markdown2`` library used to render Markdown data as HTML in reports, in the same way as the ``html2text``
  filter passes its sub-directives to the ``html2text`` library. Can be set for all jobs with ``job_defaults``. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#markdown-extras.* New ``hook_data`` job directive, for the code in ``hooks.py``: it carries any data (typically a mapping of names to
  values) from a job to the custom job, filter, differ or reporter Classes it uses, which read it as
  ``self.hook_data`` (job) or ``self.job.hook_data`` (the others), so that one custom Class can serve many jobs. Unlike
  directives declared by a custom job Class itself, it is known to the jobs file's JSON Schema, so editors don't flag
  it as an error. See https://webchanges.readthedocs.io/en/stable/jobs.html#hook-data.


Changed
```````
* The error reported when an optional Python package needed by a filter, differ, reporter, job directive or database
  engine cannot be imported now has the same form everywhere: it names what needs the package (and the job, if any),
  the package to install, the underlying error, and the command to install it (e.g.
  ``uv pip install --upgrade webchanges[pdf2text]``). Previously the wording varied, mostly omitted how to install the
  package, and sometimes named it in a way that cannot be installed (e.g. ``BeautifulSoup`` instead of
  ``beautifulsoup4``). In particular, the ``email`` (SMTP) and ``xmpp`` reporters now report that the ``keyring``
  package cannot be imported when they need it for a password, instead of reporting that no password is available.
* The ``jq`` filter is now also available on Windows, as the ``jq`` Python library now publishes packages for it:
  ``webchanges[jq]`` installs it on every operating system. See
  https://webchanges.readthedocs.io/en/stable/filters.html#jq.
* On Windows, the ``stdout`` reporter no longer depends on the ``colorama`` package to display colors: it now enables
  the console's native processing of ANSI escape sequences (supported since Windows 10), and ``colorama`` has been
  dropped from the installation requirements.
* ``ai_google`` differ: the error summary for a transient Google AI API error (HTTP 429 or 503) that persists now
  states how many automatic retries were made and for how long it waited in total, or that it was not retried, so
  that a rate limit that outlasted the retries can be told apart from one that was never retried.
* ``css`` and ``xpath`` filters: the ``selector`` and ``path`` sub-directives respectively are no longer required when
  ``exclude`` is specified; the filter then returns the whole document minus the excluded elements. See
  https://webchanges.readthedocs.io/en/stable/filters.html#css and
  https://webchanges.readthedocs.io/en/stable/filters.html#xpath.
* Markdown emphasis markers (``_`` and ``*``) within a word are no longer converted to emphasis when Markdown is
  rendered as HTML (in ``html`` and ``email`` reports, and by the ``matrix`` reporter): ``snake_case_name`` is now
  shown as written instead of with ``case`` in italics. Emphasis of whole words (``_word_`` or ``*word*``) and strong
  emphasis (``**word**``) are unaffected. To reinstate it, use the new ``markdown_extras`` job directive (see above)
  with ``middle-word-em: true``.

Deprecated
``````````
* The ``remove-duplicate-lines`` filter, inherited from **urlwatch**: use ``remove_repeated`` with
  ``adjacent: false``, which does the same. See https://webchanges.readthedocs.io/en/stable/filters.html#remove-repeated.
* The ``title`` sub-directive of the ``gotify`` reporter: use ``subject`` (see Fixed, below).

Fixed
`````
* In jobs with ``use_browser: true``, the ``ignore_http_error_codes`` job directive now also suppresses transient
  HTTP errors (status codes 429, 500, 502, 503, 504, and the synthetic 999); previously it only matched
  non-transient error responses.
* A job containing both the ``url`` and the ``command`` directive is now rejected with an error, as the two are
  mutually exclusive (each one identifies a different job kind). Such a job previously was erroneously accepted and
  run as a ``command`` one, silently ignoring the URL.
* An HTTP 304 (Not Modified) response received while the job's consecutive-error counter was greater than zero (i.e.
  the preceding run had failed) overwrote the stored snapshot with empty data, discarding the content and the ETag;
  the following successful run then reported a spurious change. Only servers that reply 304 to an unconditional
  request were affected, as **webchanges** strips the conditional request headers while retrying a failed job.
* A dict-valued directive set in ``job_defaults`` for one job kind (in practice ``headers``) leaked into every other
  job of the run, including jobs of a different kind: the defaults were merged into the shared class-level default
  instead of into a copy of it. Headers set under ``job_defaults.url`` were therefore also sent by jobs with
  ``use_browser: true``, and appeared in the output of ``--test-diff`` and in any jobs file saved during that run.
* ``--rollback-database``: the snapshots were deleted while computing the count displayed in the confirmation
  prompt, i.e. before (and regardless of) the answer; declining did not prevent the deletion, and confirming
  reported ``No snapshots found`` as nothing was left to delete. In addition, the count itself was wrong (it
  reported the number of rows affected by the previous database write rather than the number of snapshots to be
  deleted).
* ``--rollback-database``: a Unix timestamp with a fractional part (e.g. ``1789618017.98``) was rejected as unparseable.
* Reports of a transient HTTP error (status codes 429, 500, 502, 503, 504, and the synthetic 999) in ``url`` jobs
  without ``use_browser: true``, and in ``command`` jobs, contained a full Python traceback instead of just the
  error message, making a condition of the monitored resource look like a failure of **webchanges**. Jobs with
  ``use_browser: true`` were already reporting only the message.
* The bundled ``jobs.schema.json`` JSON Schema, used by editors to validate and autocomplete the jobs file, rejected
  the ``ocr``, ``pdf2text``, ``pypdf``, ``remove-duplicate-lines``, ``sha256sum`` and ``striplines`` filters when
  written without sub-directives, flagging valid jobs files as invalid.
* The bundled ``jobs.schema.json`` JSON Schema also rejected a filter's default sub-directive given directly (e.g.
  ``html2text: bs4`` for ``html2text: {method: bs4}``, or ``format-json: 2``) for the ``beautify``, ``csv2text``,
  ``format-json``, ``html2text``, ``jsontoyaml``, ``pdf2text``, ``pretty-xml``, ``pypdf``, ``remove-duplicate-lines``,
  ``remove_repeated``, ``reverse`` and ``sort`` filters, as well as any sub-directive of ``pretty-xml`` and
  ``remove-duplicate-lines``.
* The bundled ``config.schema.json`` JSON Schema, used by editors to validate and autocomplete the configuration
  file, marked every sub-directive of every reporter as required, flagging as invalid a configuration file from which
  any of them had been trimmed. **webchanges** fills in any missing one with its default value, so none is required.
* The ``xmpp`` reporter raised an ``AttributeError`` instead of a clear error message when the ``keyring`` Python
  package is not installed and no ``insecure_password`` is set.
* ``--detailed-versions`` crashed with an ``UnboundLocalError`` when Playwright is installed but ``psutil`` is not.
* On Linux and macOS, **webchanges** could be killed by the operating system without reporting any error (exit
  code 141) when a server it was sending data to closed the connection, e.g. a mail server while sending an ``email``
  report, as it restored the system's default action for the ``SIGPIPE`` signal. Such errors are now reported, while
  output piped into a program that stops reading early (e.g. ``webchanges --list | head``) still ends quietly.
* The ``email`` reporter using the ``smtp`` method, and ``--smtp-login``, waited indefinitely for an SMTP server that
  did not accept the connection or did not answer; they now give up after 60 seconds with a timeout error. See
  https://webchanges.readthedocs.io/en/stable/reporters.html#smtp.
* When ``httpx`` is not installed (**webchanges** then uses ``requests`` or, failing that, ``curl_cffi``), a job with
  ``http_client: httpx``, the ``image`` differ and the AI summaries (the ``ai_google`` differ and the ``image`` differ's
  ``ai_google`` sub-directive) failed with an obscure ``AttributeError``: the ``image`` differ now downloads images with
  ``requests`` (or ``curl_cffi``), and the others report that ``httpx``, which they require, cannot be imported.
* The ``email`` reporter using the ``smtp`` method, and ``--smtp-login``, could fail with
  ``STARTTLS extension not supported by server`` on a computer whose own hostname is slow to look up (e.g. because of
  slow reverse DNS): the hostname, sent in the ``EHLO`` greeting, was looked up after connecting, by which time the
  server could have stopped waiting (e.g. Amazon SES replies ``451 4.4.2 Timeout waiting for data from client``). It is
  now looked up before connecting.
* The ``gotify`` reporter's ``subject`` sub-directive, which sets the message title and is the one shown in the
  documentation, was flagged as unrecognized when the configuration file was loaded, while the ``title`` one listed in
  the default configuration had no effect. ``subject`` is now recognized, and ``title`` is deprecated and treated as
  ``subject``. See https://webchanges.readthedocs.io/en/stable/reporters.html#gotify.
* The bundled ``jobs.schema.json`` JSON Schema did not know the ``fingerprints``, ``http_version`` and
  ``markdown_padded_tables`` job directives, nor the object form of the ``jq`` and ``element-by-…`` filters (e.g.
  ``jq: {query: …}``), so editors flagged valid jobs files as invalid; it offered the ``delay`` and ``stealth`` job
  directives, which do not exist; and it gave the deprecated ``grep`` and ``grepi`` filters a ``text`` sub-directive
  instead of ``re``. The deprecated job directives ``diff_tool``, ``navigate``, ``stderr``, ``wait_for`` and
  ``wait_for_navigation`` are now flagged by editors as deprecated rather than as invalid.
* The deprecation warning of the ``striplines`` filter named it ``strip_each_line``.
* The ``remove_repeated`` filter compared each line with the one before it as text contained within it rather than
  as an equal line: with ``adjacent: true`` (the default), a line contained within the preceding one (e.g. ``ab``
  followed by ``b``) was removed when it had also appeared earlier.
* The ``retries`` job directive, introduced in version 3.13, had no effect: a failed request was never retried. It
  now retries, with any HTTP client, a request that fails with a connection error (e.g. a connection reset by the
  server), a timeout, or a transient HTTP response (status codes 429, 500, 502, 503 and 504), waiting between
  attempts for the time requested by the server's ``Retry-After`` header (up to 60 seconds) or else for 1, 2, 4...
  seconds (up to 30). Other errors (e.g. a 404) are not retried. Reported by 101Dude in
  https://github.com/mborsetti/webchanges/issues/196. See https://webchanges.readthedocs.io/en/stable/jobs.html#retries.
* The ``ignore_dh_key_too_small`` job directive did not work: with the default ``http_client: httpx`` it made every
  request to an HTTPS site fail with ``CERTIFICATE_VERIFY_FAILED`` (it replaced the verification of certificates
  with one using no certificate authorities, and ignored ``ssl_no_verify``), and with ``http_client: requests`` it
  had no effect with version 2.x of the ``urllib3`` library, which current versions of ``requests`` install. With
  both clients it now lowers the OpenSSL security level, so that a server's weak (1024-bit) Diffie-Hellman key is
  accepted, while certificates are verified as usual. It remains unsupported by ``http_client: curl_cffi``. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#ignore-dh-key-too-small.

Internals impacting hooks.py
````````````````````````````
* ``FilterBase.raise_import_error()``, ``DifferBase.raise_import_error()`` and ``ReporterBase.raise_import_error()``
  now accept the ``ImportError`` itself as well as its message, and a new optional ``extra`` argument naming the
  **webchanges** extra that installs the package; they raise the standard error described above. The new
  ``webchanges.util.missing_dependency()`` returns that error for code outside these classes.
* Removed ``webchanges.util.lazy_import()`` and ``webchanges.util.import_optional_dependency()``, which were no longer
  used; use a plain import inside the function that needs the package, with ``missing_dependency()`` for its
  ``ImportError``.

Internals
`````````
* Updated the vendored copy of ``packaging`` (used as a fallback when the ``packaging`` library is not installed)
  from v26.2 to v26.3.
* CI: a release push updates two refs pointing to the same commit (the branch and the version tag, pushed
  atomically), and each ref triggers its own workflow run; the branch run now detects that its commit is also tagged
  on the remote and skips the test matrix, so the release test suite executes only once (in the tag's run).
* tox: the ``pre-commit`` environment now runs ``pre-commit autoupdate`` before running the hooks, so hook version
  updates are picked up as part of a normal local test run.
* The fallback assignments of the optional imports (e.g. ``httpx = None`` when ``httpx`` cannot be imported) are now
  hidden from the type checker, and ``raise_import_error()`` is annotated as ``NoReturn``, restoring a clean
  ``ty`` 0.0.72 run.
* The modules declare ``__lazy_modules__`` (PEP 810, https://peps.python.org/pep-0810/), so that on Python 3.15 and
  newer the standard-library and third-party modules they use only inside functions are imported when first needed,
  speeding up start-up (e.g. ``webchanges --help`` by about 8%); it has no effect on earlier Python versions.
* Optional packages (e.g. ``deepdiff``, ``keyring``, ``pypdf``, ``beautifulsoup4``, ``requests``) are now imported
  only by the code that uses them instead of when **webchanges** starts, so that a run only imports what its jobs and
  reporters need: importing the modules of a run went from about 1.5 s to 0.45 s on Python 3.14, and from 0.95 s to
  0.26 s on Python 3.15 (measured on Windows with all optional packages installed).
* CI: the CodeQL workflow's analysis step had been mistakenly replaced by a second initialization step in version
  3.34.2, so no code scanning results were produced since; it has been restored.
* CI: the Redis storage tests never ran, as the ``REDIS_URI`` environment variable they require was exported in a
  step of its own and therefore lost before the tests ran. In addition, the workflow's token is now read-only except
  in the deploy job, and test jobs time out after 30 minutes.
* CI: before publishing, the deploy job now checks that the release tag matches both ``__version__`` and the version
  header of the top ``CHANGELOG.rst`` section, and that this section is no longer dated "Unreleased".
* CI: the test workflow runs on pushes only to the ``main`` and ``unreleased`` branches and to release tags, so that
  a pull request's branch (e.g. a Dependabot one) is no longer tested twice, once for the push and once for the pull
  request.
* Testing: Python 3.15 and 3.15t replace 3.11 and 3.14t in the CI test matrix (and 3.15 replaces 3.11 in ``tox``), the
  tests that run only on the latest Python version now run on 3.15, and a failing CI test job no longer cancels the
  other ones.
* Code modernized for Python 3.12 and newer: PEP 695 syntax for type aliases and generics.
* CI: removed the ClusterFuzzLite workflow, an unconfigured template (set up for C++, without fuzz targets) that
  failed on every pull request.
* Testing: the ``jq`` filter is now also tested on Windows and on free-threaded Python.
* Testing: a new test checks that the code, the bundled JSON Schemas and the documentation list the same filters (and
  their sub-directives), job directives and configuration directives, so that they no longer drift apart.
