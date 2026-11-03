## Reminder
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.13 was
released on 7 October 2024, the codebase will be streamlined by removing support for Python 3.12 on or after 7
October 2027.

## ⚠ Upgrade Notes
- HTML reports: Markdown tables are shown as tables; `markdown_tables: false` restores the previous look.
- `job_defaults`: A misspelled directive (was ignored) or a wrong value now stops the run with an error naming it.
- `html2text` filter: A misspelled sub-directive (e.g. `pad_table`) or a method given as one (e.g.
  `strip_tags: true`) now fails the job instead of being ignored.
- HTTPS: `httpx2`, the new default HTTP client, checks certificates against the operating system's store instead of
  `certifi`'s; on a certificate error, set `SSL_CERT_FILE`.
- `wdiff` differ: Whitespace-only changes are no longer reported.
- `http_client: curl_cffi`: Sends the impersonated browser's `User-Agent`; some sites may report one change.

## Added
- Sample Dockerfile (`docker/Dockerfile`, `compose.yaml`), tested in CI. See https://webchanges.readthedocs.io/en/stable/advanced.html#docker-sample.
- `ai_google` differ: `diff` sub-directive, choosing the differ of the diff shown after the summary (default
  `unified`). See https://webchanges.readthedocs.io/en/stable/differs.html#ai-google-diff.

## Changed
- Default HTTP client: `httpx2 <https://github.com/pydantic/httpx2>`__, the maintained successor of `httpx`, then
  `httpx`, `requests` and `curl_cffi`; `http_client: httpx` is an alias of `httpx2`.
- HTML reports: Markdown tables are rendered as tables, also in `unified` and `wdiff` diffs. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#markdown-tables.
- `wdiff` differ: Works as `git diff --word-diff`: 550 times faster on a 75 KB page, no matches across distant
  lines, a rewritten phrase shown as one change. See https://webchanges.readthedocs.io/en/stable/differs.html#wdiff-diff.
- Configuration and jobs file errors, and wrong filter, differ or reporter settings, are shown without a traceback.
- Wrong job directive values, also a `headers` that is not a mapping, are reported when the jobs file is loaded.
- `xmpp` reporter: Works again, with `slixmpp` instead of the dead `aioxmpp`; one connection per report.
- HTML reports: Images in Markdown content are at most 600 pixels wide.

## Deprecated
- `ai_google` differ: `unified` sub-directive, replaced by `diff: {name: unified, ...}` (works, with a warning).

## Fixed
- Browser jobs with `data`: Servers could not read it (no `Content-Type`, and strings were percent-encoded).
- Browser jobs with `cookies`: Sent to every site the page loads (e.g. ads) and dropped once the site set a cookie;
  now set for the hosts of `url` and `initialization_url` only, also with `connect_over_cdp` (were ignored). See
  https://webchanges.readthedocs.io/en/stable/jobs.html#cookies.
- Editors' JSON Schemas were not copied next to `config.yaml` and `jobs.yaml` by `pip` or `uv` installs.
- Markdown reporters (`telegram`, `matrix`, `gotify`, `github_issue`; `webhook`/`discord` with
  `markdown: true`): New jobs and `--test` showed a diff against nothing; diff headers were garbled.
- `http_client: curl_cffi`: Sent webchanges' own `User-Agent` (contradicting its TLS fingerprint), and no
  `cookies` to `url` after an `initialization_url` on another host.
- Browser jobs: Network errors (e.g. `net::ERR_TIMED_OUT`) were not recognized, so `ignore_timeout_errors` and
  `ignore_too_many_redirects` had no effect; they are now reported by name.
- `initialization_url`: A landing URL with several `;` parameters failed with "did not find key".
- Browser jobs: `wait_until: networkidle0` or `networkidle2` failed validation; they work again, with a warning.
- Browser jobs: `initialization_js` failed with a dict `wait_for_url`.
- `browser` reporter: Not written in UTF-8, garbling characters such as `€` on Windows.
- Bundled JSON Schemas: False errors (e.g. files missing directives, `_` remarks, `wdiff`'s `color`) and missed
  typos (sub-directives of sections, reporters and `html2text`).
- `wdiff` differ: Long data showed only `@@` with `color: false`; HTML reports garbled Markdown lists and
  headings.
- Minor: `github_issue`'s numeric `milestone` failed validation; `--features` descriptions; clearer errors
  for `ai_google` retries and an invalid `re` of `keep_lines_containing` / `delete_lines_containing`.
- Documentation: `data` with `GET` or `HEAD` is sent as the body, not as query parameters (use `params`).

## Internals impacting hooks.py
- Import `httpx2` instead of `httpx` (same API); the two packages' classes don't mix.
- Wrong settings raise `webchanges.util.SettingError` (a `ValueError`), which custom filters, differs and
  reporters can raise too; catch `ValueError` instead of `TypeError`, `RuntimeError` or `re.error`.
- `UrlJobBase.get_headers()` no longer adds a `Cookie` header (no `include_cookies`): use `get_cookies()`.
- A duplicate (legacy and current) `job_defaults` key raises `ValueError` (was `KeyError`).

## Internals
- The vendored fallback `Headers` class is now `httpx2` v2.16.0's (was `httpx` v0.28.1's).
