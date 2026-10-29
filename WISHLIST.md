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
- [ ] Resolve TODOs
  - [ ] Can/should defusedxml be used?
