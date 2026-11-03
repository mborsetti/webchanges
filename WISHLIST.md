- [ ] Remove sole reliance on ``hashlib.sha1``, which may not be available in FIPS builds
- [ ] Fix linkify for links with ampersands
- [ ] Improve testing coverage
- [ ] Create a downloadable Windows executable
- [ ] Smart "just works for the web" philosophy automatically applies correct filters for monitoring webpages
- [ ] Simplify main legacy Urlwatcher class
- [ ] Implement the ``stealth`` job directive for browser jobs using ``playwright-stealth`` (the ``JobBase.stealth``
  attribute and the ``playwright-stealth`` entry in ``--detailed-versions`` are already in place; then add it to
  ``jobs.schema.json`` and document it)
- [ ] Add ``html-to-markdown`` (https://pypi.org/project/html-to-markdown/) as an opt-in ``method`` of the
  ``html2text`` filter, keeping the ``html2text`` package as the default so that existing jobs don't report a change.
  Compared in Oct-26: it produced the best Markdown (aligned tables, fenced code, ``<script>`` dropped) about 5× faster
  than ``html2text`` and 12× faster than ``markdownify``; MIT licensed (``html2text`` is GPL-3.0) and the fastest-growing
  (×10.7 in downloads May→Sep 2026). Caveats: frequent releases (v2 Oct-25, v3 Mar-26, ~210 releases) whose output
  changes would send one-off change reports, so cap the extra at its current major version (``html-to-markdown>=3,<4``)
  and say so in the docs; essentially a single maintainer; its ``abi3`` wheels don't load on free-threaded Python (needs
  a Rust build there, so leave it out of ``tests/requirements_pytest_free-threaded.txt``); and it keeps relative links,
  so make them absolute first (as the ``absolute_links`` filter does) to match ``html2text``'s output
- [ ] Validate the jobs and configuration files against ``jobs.schema.json`` and ``config.schema.json`` at run time,
  replacing the typeguard checks and most of ``BrowserJob.validate()`` (checked 03-Nov-26: the schema already rejects
  what that code checks, except a malformed ``http_credentials`` (add a ``pattern``) and the obsolete ``wait_for``
  (remove it from the schema), and also rejects ``headers: 5`` and misspelled ``job_defaults`` directives if their
  sections reference the job directives). Use ``fastjsonschema`` (pure Python, no dependencies, compiles the schema to
  code) with the schemas moved to draft-07 (rename ``$defs`` to ``definitions`` in ``config.schema.json``; check that
  editors still flag ``deprecated`` directives), not ``jsonschema``, which needs ``rpds-py`` (Rust) for draft 2020-12.
  Extend the loaded schema at start-up with the job kinds, directives and filters registered by ``hooks.py``, as
  the bundled schema is closed. Then the vendored typeguard may go too, if ``config.yaml`` moves to its schema as well
- [ ] Resolve TODOs
  - [ ] Can/should defusedxml be used?
