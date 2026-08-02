## Added
- New `connect_over_cdp` job directive for browser (`use_browser: true`) jobs: attach to an already-running
  Chromium browser over the Chrome DevTools Protocol instead of using Playwright to launch a new browser instance
  (`true` attaches to the default endpoint `ws://127.0.0.1:58489/devtools/browser`; a `ws://` URL string attaches
  to that endpoint). Allows the monitoring of websites that block other forms of access except for a "real" user's own
  browser. Can be used with a Chrome browser you launched yourself with `--remote-debugging-port`, to attach to a
  remote browser, or to share a logged-in session across jobs. All such jobs run on a single dedicated worker thread, so
  each unique endpoint requires manual browser authorization only once per run, and the connection is cached for the
  lifetime of the run (set the environment variable `WEBCHANGES_BROWSER_CDP_CACHE=0` to disable caching). See
  https://webchanges.readthedocs.io/en/stable/jobs.html#connect-over-cdp.
- New `empty_as_transient` job directive for `url` jobs (without `use_browser: true`): when the server returns
  an empty response, it is treated as a transient HTTP error (with the synthetic HTTP response status code 999)
  instead of as valid empty content, so the snapshot database retains the last non-empty content and a flaky site
  that intermittently returns nothing no longer triggers a change report when the content "disappears" and another
  one when it is restored. Combine with `max_tries` to be notified only of persistent empty responses, or with
  `ignore_http_error_codes: 999` to never be notified of them. Suggested by Marcos Alano in
  https://github.com/mborsetti/webchanges/issues/169. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#empty-as-transient.
- New `between` filter: extracts the block of lines sitting between a line matching the `start` regular
  expression and one matching the `end` regular expression (the two delimiting lines themselves are discarded;
  omitting `start` extracts from the first line, omitting `end` to the last). Useful for clipping a section out
  of log files, server-status pages, or any text delimited by recognizable markers. See
  https://webchanges.readthedocs.io/en/stable/filters.html#between.
- `deepdiff` differ: new `cutoff_distance_for_pairs`, `cutoff_intersection_for_pairs` and
  `threshold_to_diff_deeper` sub-directives to tune when DeepDiff pairs up changed items (or dictionaries) and
  compares them in depth rather than reporting the whole object as replaced. See
  https://webchanges.readthedocs.io/en/stable/differs.html#deepdiff.
- New `same_site_delay` job directive for `url` and browser (`use_browser: true`) jobs: when an earlier job in
  the list already targets the same site (network location), the job waits this many seconds before retrieving its
  URL, staggering requests that could otherwise hit the same site at the same instant and risk being rate-limited or
  blocked. The first job for a given site is never delayed, and jobs without the directive are never delayed. It can
  be set on an individual job or, for all jobs, through `job_defaults`. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#same-site-delay.
- `ai_google` differ: transient Google AI API errors are now retried automatically instead of immediately failing
  the summary: an HTTP 429 (rate limit) is retried one second after the delay requested by the server (the extra
  second covers the server truncating its requested delay to whole seconds), and an HTTP 503 (service unavailable)
  after a fixed 45 seconds, until the cumulative time spent waiting would exceed 244 seconds.
- `command` jobs: when **webchanges** is run verbosely (`-v`, `-vv` or `-vvv`), the matching verbosity flag
  is now passed on to any Python interpreter invoked by the command, so that the script's own logging shows up
  alongside that of **webchanges** (e.g. when running `webchanges -vv`, a job with
  `command: python summarize.py` is run as `python summarize.py -vv`). The flag is added at the end of the
  invocation, where the script being run will see it, and a verbosity flag you wrote yourself is never removed or
  lowered. Note that a Python script which does not accept a `-v` argument may now fail when **webchanges** is
  run verbosely (including with `--log-file`, which implies `-v`). See
  https://webchanges.readthedocs.io/en/stable/jobs.html#verbosity-is-passed-on-to-python.
- New `version_check` configuration setting: set its `enabled` sub-directive to `false` in `config.yaml` to
  disable the check against PyPi for a newer release of **webchanges** whose result appears in report footers
  (e.g. for air-gapped machines or installations managed by a package manager). The `--check-new` command line
  argument always queries PyPi, regardless of this setting. See
  https://webchanges.readthedocs.io/en/stable/configuration.html#version-check.

## Changed
- `deepdiff` differ: now always reports the individual nested values that changed instead of, in certain
  circumstances, dumping the entire before-and-after contents of a changed dictionary or list item (e.g. a ~750-line
  report for what was in essence a 3-line change). This is achieved by defaulting the deepdiff library's pairing and
  recursion thresholds (see the new sub-directives above) to always compare changed objects in depth, which is almost
  always what is wanted given that the two snapshots being compared come from the same source and are near-identical;
  the library's own, less thorough, defaults can be restored via the new sub-directives should runs with very large
  changed lists become too slow.
- `command` jobs: the command's standard input is now connected to the null device, so a command that unexpectedly
  prompts for input (e.g. Python's `input()`) reads end-of-file and exits with a reported error instead of hanging
  the run forever waiting for keyboard input that will never arrive.
- `wdiff` differ: when diffing Markdown text, bold (`**`) and strikethrough (`~~`) markers are now tokenized
  separately, so a change to a word inside an emphasized phrase no longer reports the unchanged markers as part of
  the change (e.g. `**one flower**` becoming `**two flowers**` is now reported as
  `**[-one-] {+two+} [-flower-] {+flowers+}**`).
- The check for a newer release of **webchanges** on PyPi (whose result appears in report footers and in the
  output of `--check-new`) has been reworked: the answer is now cached on disk for 24 hours, so repeated runs no
  longer query PyPi every time (`--check-new` still always queries); the most recent answer is reused when PyPi is
  unreachable; the query is now made with the Python standard library and therefore also works when `httpx` is not
  installed.
- `--delete-snapshot`: the snapshot listing shown before confirming deletion now includes the size of each snapshot.

## Deprecated
- The `empty-diff` configuration setting (under `display`) is now formally deprecated: a deprecation warning is
  issued at startup when it is set to `true`. It has long been superseded by the `additions_only` job directive.

## Fixed
- `suppress_repeated_errors` job directive: a job failing repeatedly with the same error was reported on every run
  instead of only the first time, as the check was unreachable code (regression introduced in version 3.34.0).
  Reported by Manu in https://github.com/mborsetti/webchanges/issues/189.
- `suppress_error_ended` job directive: it was never consulted (since its introduction in version 3.34.0), so the
  "error ended" notification was sent even when the directive was set to `true`.
- `--test`: the report of a job that ends in an error now contains the full error detail (e.g. for a `command`
  job, the failed subprocess's stderr, or a traceback); it previously showed only the exception's one-line message
  (e.g. `Command '...' returned non-zero exit status 1.`).

## Internals impacting hooks.py
- `JobBase.unserialize()` no longer modifies the dict it is given: the backwards-compatibility migrations it
  applies (e.g. rewriting `kind: shell` to `kind: command`, converting `diff_tool` to `differ` etc.) now
  operate on a copy and no longer corrupt the original.

## Internals
- Updated vendored `typeguard` (used as a fallback for type-checking job directives and configuration keys when the
  optional `typeguard` dependency is unavailable) from v4.5.1 to v4.6.0.
- The configuration loaded from an empty configuration file (or one without `job_defaults`) was the shared default
  configuration object itself rather than a copy of it, so a later modification of the loaded configuration (e.g.
  from `hooks.py`) would silently corrupt the defaults for the rest of the run. The defaults are now deep-copied.
