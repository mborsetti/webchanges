## ⚠ Breaking Changes
- The `empty_as_transient` job directive, introduced 3 days earlier in version 3.37.0, has been retired in favor
  of the new `empty_as_error` one (see below), whose name describes what you actually observe. It is no longer
  recognized: if you use it, rename it in your jobs file, or the run aborts with the error
  `Directive 'empty_as_transient' is unrecognized`.
  See https://webchanges.readthedocs.io/en/stable/jobs.html#empty-as-error.

## Added
- New `!env` YAML tag: inserts the value of environment variables anywhere within a string value of the jobs or
  configuration file. Reference a variable as `${VAR}`, or as `${VAR:-default}` to fall back to `default` when
  the variable is not set; an unset variable without a default aborts the run with an error reporting the variable's
  name and line. Useful to define a value shared by multiple jobs in a single place (e.g. a version number appearing
  in multiple URLs and names, which can even be computed by a wrapper script before invoking **webchanges**) and to
  keep secrets such as API tokens out of the YAML files. Suggested by Marcos Alano in
  https://github.com/mborsetti/webchanges/issues/99. See
  https://webchanges.readthedocs.io/en/stable/advanced.html#using-environment-variables.
- New `empty_as_error` job directive: when the server or a command returns an empty response or output consisting
  only of whitespace, it is treated as a transient error (with the synthetic HTTP response status code 999) instead
  of as valid empty content, so the snapshot database retains the last non-empty content and a flaky site or command
  that intermittently returns nothing no longer triggers a change report when the content "disappears" and another
  one when it is restored. Combine with `max_tries` to be notified only of persistent empty responses, or with
  `ignore_http_error_codes: 999` (or, for `command` jobs, `suppress_errors`) to never be notified of them.
  Suggested by Marcos Alano in https://github.com/mborsetti/webchanges/issues/169. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#empty-as-error.

## Fixed
- In jobs with `use_browser: true`, the `ignore_http_error_codes` job directive now also suppresses transient
  HTTP errors (status codes 429, 500, 502, 503, 504, and the synthetic 999); previously it only matched
  non-transient error responses.
- A job containing both the `url` and the `command` directive is now rejected with an error, as the two are
  mutually exclusive (each one identifies a different job kind). Such a job previously was erroneously accepted and
  run as a `command` one, silently ignoring the URL.
- An HTTP 304 (Not Modified) response received while the job's consecutive-error counter was greater than zero (i.e.
  the preceding run had failed) overwrote the stored snapshot with empty data, discarding the content and the ETag;
  the following successful run then reported a spurious change. Only servers that reply 304 to an unconditional
  request were affected, as **webchanges** strips the conditional request headers while retrying a failed job.
- A dict-valued directive set in `job_defaults` for one job kind (in practice `headers`) leaked into every other
  job of the run, including jobs of a different kind: the defaults were merged into the shared class-level default
  instead of into a copy of it. Headers set under `job_defaults.url` were therefore also sent by jobs with
  `use_browser: true`, and appeared in the output of `--test-diff` and in any jobs file saved during that run.
- Reports of a transient HTTP error (status codes 429, 500, 502, 503, 504, and the synthetic 999) in `url` jobs
  without `use_browser: true`, and in `command` jobs, contained a full Python traceback instead of just the
  error message, making a condition of the monitored resource look like a failure of **webchanges**. Jobs with
  `use_browser: true` were already reporting only the message.
- The bundled `jobs.schema.json` JSON Schema, used by editors to validate and autocomplete the jobs file, rejected
  the `ocr`, `pdf2text`, `pypdf`, `remove-duplicate-lines`, `sha256sum` and `striplines` filters when
  written without sub-directives, flagging valid jobs files as invalid.

## Internals
- Updated the vendored copy of `packaging` (used as a fallback when the `packaging` library is not installed)
  from v26.2 to v26.3.
- CI: a release push updates two refs pointing to the same commit (the branch and the version tag, pushed
  atomically), and each ref triggers its own workflow run; the branch run now detects that its commit is also tagged
  on the remote and skips the test matrix, so the release test suite executes only once (in the tag's run).
- tox: the `pre-commit` environment now runs `pre-commit autoupdate` before running the hooks, so hook version
  updates are picked up as part of a normal local test run.
