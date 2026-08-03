## Added
- New `!env` YAML tag: inserts the value of environment variables anywhere within a string value of the jobs or
  configuration file. Reference a variable as `${VAR}`, or as `${VAR:-default}` to fall back to `default` when
  the variable is not set; an unset variable without a default aborts the run with an error reporting the variable's
  name and line. Useful to define a value shared by multiple jobs in a single place (e.g. a version number appearing
  in multiple URLs and names, which can even be computed by a wrapper script before invoking **webchanges**) and to
  keep secrets such as API tokens out of the YAML files. Suggested by Marcos Alano in
  https://github.com/mborsetti/webchanges/issues/99. See
  https://webchanges.readthedocs.io/en/stable/advanced.html#using-environment-variables.

## Changed
- The `empty_as_transient` job directive (introduced in version 3.37.0 for `url` jobs without
  `use_browser: true`) now also works in jobs with `use_browser: true`: an empty response is a zero-byte
  document received from the server. See https://webchanges.readthedocs.io/en/stable/jobs.html#empty-as-transient.

## Fixed
- In jobs with `use_browser: true`, the `ignore_http_error_codes` job directive now also suppresses transient
  HTTP errors (status codes 429, 500, 502, 503, 504, and the synthetic 999); previously it only matched
  non-transient error responses.

## Internals
- CI: a release push updates two refs pointing to the same commit (the branch and the version tag, pushed
  atomically), and each ref triggers its own workflow run; the branch run now detects that its commit is also tagged
  on the remote and skips the test matrix, so the release test suite executes only once (in the tag's run).
- tox: the `pre-commit` environment now runs `pre-commit autoupdate` before running the hooks, so hook version
  updates are picked up as part of a normal local test run.
