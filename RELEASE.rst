Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.13 was
released on 7 October 2024, the codebase will be streamlined by removing support for Python 3.12 on or after 7
October 2027.

⚠ Upgrade Notes
```````````````
* HTML reports: Markdown tables are now rendered as HTML tables; set ``markdown_tables: false`` to keep the previous
  rendering.
* ``html2text`` filter: Jobs with a misspelled sub-directive (e.g. ``pad_table``) or a method given as a sub-directive
  (e.g. ``strip_tags: true``) now fail with an error instead of silently ignoring it; correct them as it says.
* HTTPS: With ``httpx2``, the default HTTP client, TLS certificates are now verified against the operating system's
  certificate store instead of ``certifi``'s; if a job now fails with a certificate error, set ``SSL_CERT_FILE``.
* ``wdiff`` differ: Changes of whitespace only (spaces, blank lines, line breaks) are no longer reported.
* ``url`` jobs with ``http_client: curl_cffi`` now send the impersonated browser's ``User-Agent``; a site serving
  different content to it will be reported as changed once, on the first run after upgrading.

Added
`````
* A tested sample Dockerfile (``docker/Dockerfile``, with a ``compose.yaml``) to build a container from the source
  code. See https://webchanges.readthedocs.io/en/stable/advanced.html#docker-sample.
* ``ai_google`` differ: New ``diff`` sub-directive choosing the differ of the diff that follows the summary (e.g.
  ``diff: wdiff``), by name or with sub-directives; defaults to ``unified``. See
  https://webchanges.readthedocs.io/en/stable/differs.html#ai-google-diff.

Changed
```````
* The default HTTP client is now httpx2 (https://github.com/pydantic/httpx2), to reduce supply chain and security
  risks (``httpx`` has had no stable release since late 2024); without it, ``httpx`` is used, then ``requests`` or
  ``curl_cffi`` as before. ``http_client: httpx2`` is the new directive value, ``httpx`` remaining an alias. TLS
  certificates are verified against the operating system's store (OpenSSL's on Linux) instead of ``certifi``'s;
  ``SSL_CERT_FILE`` and ``SSL_CERT_DIR`` still override it.
* Errors in the configuration or jobs file, and wrong settings of a filter, differ or reporter, are reported without a
  Python traceback.
* HTML reports: Markdown tables (e.g. from the ``html2text`` filter) are rendered as HTML tables instead of as
  ``|``-separated text, also in the diffs of the ``unified`` and ``wdiff`` differs. See
  https://webchanges.readthedocs.io/en/stable/jobs.html#markdown-tables.
* ``wdiff`` differ: Compares lines first, then words within the changed lines, as ``git diff --word-diff`` does: 550
  times faster on a 75 KB page, and words are no longer matched across distant lines. Whitespace is no longer compared,
  punctuation and Han and kana characters are words of their own, a rewritten phrase is reported as one change, and
  the HTML report of HTML data stays valid HTML. See https://webchanges.readthedocs.io/en/stable/differs.html#wdiff-diff.
* HTML reports: Images in Markdown content are at most 600 pixels wide.
* ``xmpp`` reporter: Works again, using the maintained slixmpp (https://pypi.org/project/slixmpp/) instead of the
  dead ``aioxmpp``; it connects once per report instead of once per message, and gives up after 60 seconds without a
  session.

Deprecated
``````````
* ``ai_google`` differ: The ``unified`` sub-directive, replaced by ``diff`` (``unified: {...}`` becomes
  ``diff: {name: unified, ...}``); it still works, with a warning.

Fixed
`````
* ``html2text`` filter: Misspelled sub-directives (e.g. ``pad_table``) were silently ignored, and a method given as a
  sub-directive (e.g. ``strip_tags: true``) ran the default method; both now raise an error. The bundled JSON Schema
  flags them too, offers all the options of the ``html2text`` method, and no longer offers the unsupported
  ``decode_errors``.
* The JSON schemas copied next to ``config.yaml`` and ``jobs.yaml`` for editors' autocompletion and validation were
  never copied when installed with ``pip`` or ``uv``.
* ``url`` jobs with ``http_client: curl_cffi`` sent **webchanges**' own ``User-Agent`` instead of the
  impersonated browser's, contradicting its TLS fingerprint (a ``User-Agent`` in the job's ``headers`` still prevails).
* ``wdiff`` differ: HTML reports of Markdown data showed list items as literal ``*`` without their indentation, and
  headings and ``* * *`` as full-size headings and horizontal rules; they are now rendered line by line, as with the
  ``unified`` differ.
* ``wdiff`` differ: With ``color: false``, text reports of data longer than ``context_lines`` showed only a ``@@``
  line, and no changes.
* ``url`` jobs with ``use_browser: true``, ``initialization_url`` and ``initialization_js`` failed when
  ``wait_for_url`` was a dict of Playwright options, and an invalid ``wait_for_url`` raised an ``AttributeError``
  instead of a clear error.
* ``github_issue`` reporter: A numeric ``milestone``, as in the documentation's example, failed the validation of the
  configuration file. See https://webchanges.readthedocs.io/en/stable/reporters.html#github-issue.
* Bundled JSON Schemas: The configuration file's schema rejected files missing directives (e.g. written by an earlier
  version), top-level remarks (keys starting with ``_``) and the deprecated ``empty-diff: true``, but accepted
  misspelled sub-directives of sections and reporters; the jobs file's schema rejected a ``command`` differ without
  ``name`` and the ``color`` sub-directive of the ``wdiff`` differ.
* ``wdiff`` differ: In HTML reports, the ``@@`` lines marking skipped lines are now styled as the ``unified`` differ's.
* ``--features``: The ``deepdiff`` and ``wdiff`` differs had no description ("None"), and the descriptions of the
  ``beautify`` and ``xmltoyaml`` filters were cut mid-sentence.
* ``keep_lines_containing`` and ``delete_lines_containing`` filters: Clearer error messages for an invalid regular
  expression in ``re``.
* ``ai_google`` differ: Clearer retry error messages.
* ``telegram``, ``matrix``, ``gotify`` and ``github_issue`` reporters, and ``webhook``/``discord`` with
  ``markdown: true``: New jobs (and ``--test``) were reported as a diff against nothing instead of their content, as
  other reporters do; the code spans around the header lines of a ``unified`` diff were closed on the next line;
  content starting with ``---`` was taken for a diff.

Internals impacting hooks.py
````````````````````````````
* With the switch to ``httpx2`` (see above), a ``hooks.py`` importing ``httpx`` must import ``httpx2`` instead (same
  API: rename ``httpx`` to ``httpx2``); the two packages' classes are unrelated, so mixing them breaks silently.
* New ``webchanges.util.SettingError`` (a ``ValueError`` subclass): a custom filter, differ or reporter can raise it to
  report a wrong setting without a traceback. The bundled ones now raise it, so code catching ``TypeError``,
  ``RuntimeError``, ``re.error`` or ``cssselect.SelectorError`` from them must catch ``ValueError`` (or
  ``SettingError``) instead.
* A duplicate (legacy and current) ``job_defaults`` key in the configuration raises ``ValueError`` (was ``KeyError``).

Internals
`````````
* Replaced the vendored ``httpx`` v0.28.1 ``Headers`` class (used as a fallback) with ``httpx2`` v2.16.0's.
