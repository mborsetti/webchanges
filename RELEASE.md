## Reminder
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.13 was
released on 7 October 2024, the codebase will be streamlined by removing support for Python 3.12 on or after 7
October 2027.

## Added
- Command line arguments that take a job (a joblist, `--test`, `--test-differ`, `--dump-history`,
  `--delete`, `--delete-snapshot`, `--change-location` etc.) also select it by its `name`. See
  https://webchanges.readthedocs.io/en/stable/cli.html#job-subset.
- New `ignore_incomplete_reads` job directive for `url` jobs: ignores the error raised when the server closes the
  connection before sending the complete response. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#ignore-incomplete-reads.
- New `reply_to` sub-directive of the `email` reporter, setting the `Reply-To` header of the email.
- New `--enable` and `--disable` command line arguments, which set a job's `enabled` directive.
  They rewrite the jobs file, so all its remarks are lost. See
  https://webchanges.readthedocs.io/en/stable/cli.html#enable-disable.
- New `stderr` directive for `command` jobs: `ignore` (the default), `forward`,
  `fail` and `stdout` to handle the command's standard error output. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#stderr.
- New `treat_new_as_changed` job directive (for backward compatibility): reports a new job as changed, with its
  content shown as a diff from empty content, so that its differ and `diff_filters` apply from the first run. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#treat-new-as-changed.
- Better backward compatibility: the legacy `useragent`, `browser` and `wait_for` directives of `navigate`
  jobs are translated into a `User-Agent` header, `use_browser` and `wait_for_selector` (`wait_for` used to
  fail the job), and the legacy `mattermost` reporter runs as a `webhook` one with Markdown; all print a
  deprecation warning. See https://webchanges.readthedocs.io/en/stable/upgrading.html.

## Changed
- A job selected by URL/command (or name) that matches more than one job is now an error listing the jobs matched,
  instead of silently selecting the first one; select the job by its index number instead.
- The `html2text` filter's `lynx` method (for backward compatibility) no longer fails the job: it runs the default
  method instead (ignoring `lynx`'s options) and prints a deprecation warning.

## Fixed
- A job selected more than once in a joblist (e.g. a new job selected with `--prepare-jobs`, which also adds the new
  jobs) ran more than once.
- The debug log reported a negative number of disabled jobs.
- The `ntfy` reporter published only the first job of a report, raising
  `RuntimeError: Cannot reopen a client instance, once it has been closed.` on the second one (or a `NameError`
  if `httpx` is not installed). A failed publication no longer prevents the other jobs from being published.
- The `ntfy` reporter no longer adds an "Open URL" action to the messages of `command` jobs.
- With the same `RuntimeError`, the `ifttt` reporter sent only the first job of a report, and the `webhook` (as
  well as the deprecated `slack` and `mattermost`) and `discord` reporters only the first part of a report too
  long for one message.
- On the first run, legacy jobs, configuration and hooks files are now also found and copied from the legacy
  platform-specific configuration directory (e.g. `~/.config/urlwatch` on Linux), and not only from
  `~/.urlwatch`.
- The deprecated `shell` reporter (for backward compatibility) crashed with `KeyError: 'max_message_length'`; it now
  pipes the report to its command's standard input.
- The deprecated `slack` reporter (for backward compatibility) was silently ignored; it now runs as a `webhook`
  reporter.
- The `run_command` reporter did not set the documented `WEBCHANGES_CHANGED_JOBS_JSON` environment variable; it
  now holds the directives of the jobs reported on.
- The subject (or title) of a report with a single change read "1 changes" instead of "1 change".
- Jobs with the deprecated `navigate` directive failed when run with
  "Directive 'navigate' is deprecated with Playwright", although the directive was translated into `url` and
  `use_browser: true`.
- Rewriting the jobs file (with `--add`, `--delete` or `--change-location`) dropped the directives set to false
  or 0, such as `enabled: false` or `contextlines: 0`.
- `--delete` and `--change-location` crashed with `EOFError` at their confirmation prompt when no input was
  available (e.g. `--change-location` run by `cron`, or standard input redirected from the null device, which
  Windows reports as a terminal); they now leave the jobs file unmodified.
