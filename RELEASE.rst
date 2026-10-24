⚠ Breaking Changes
``````````````````
* The ``empty_as_transient`` job directive, introduced 3 days earlier in version 3.37.0, has been retired in favor
  of the new ``empty_as_error`` one (see below), whose name describes what you actually observe. It is no longer
  recognized: if you use it, rename it in your jobs file, or the run aborts with the error
  ``Directive 'empty_as_transient' is unrecognized``.
  See https://webchanges.readthedocs.io/en/stable/jobs.html#empty-as-error.

Added
`````
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
  https://webchanges.readthedocs.io/en/stable/jobs.html#markdown-extras.

Changed
```````
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
* The bundled ``config.schema.json`` JSON Schema, used by editors to validate and autocomplete the configuration
  file, marked every sub-directive of every reporter as required, flagging as invalid a configuration file from which
  any of them had been trimmed. **webchanges** fills in any missing one with its default value, so none is required.
* The ``xmpp`` reporter raised an ``AttributeError`` instead of a clear error message when the ``keyring`` Python
  package is not installed and no ``insecure_password`` is set.
* ``--detailed-versions`` crashed with an ``UnboundLocalError`` when Playwright is installed but ``psutil`` is not.
* The ``email`` reporter using the ``smtp`` method, and ``--smtp-login``, waited indefinitely for an SMTP server that
  did not accept the connection or did not answer; they now give up after 60 seconds with a timeout error. See
  https://webchanges.readthedocs.io/en/stable/reporters.html#smtp.

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
* The filter modules declare ``__lazy_modules__`` (PEP 810, https://peps.python.org/pep-0810/), so that on Python
  3.15 and newer the standard-library and third-party modules they use are imported only when first needed; it has
  no effect on earlier Python versions.
* CI: the CodeQL workflow's analysis step had been mistakenly replaced by a second initialization step in version
  3.34.2, so no code scanning results were produced since; it has been restored.
* CI: the Redis storage tests never ran, as the ``REDIS_URI`` environment variable they require was exported in a
  step of its own and therefore lost before the tests ran. In addition, the workflow's token is now read-only except
  in the deploy job, and test jobs time out after 30 minutes.
* CI: before publishing, the deploy job now checks that the release tag matches both ``__version__`` and the version
  header of the top ``CHANGELOG.rst`` section, and that this section is no longer dated "Unreleased".
