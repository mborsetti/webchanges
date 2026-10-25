- [ ] Remove sole reliance on ``hashlib.sha1``, which may not be available in FIPS builds
- [ ] Fix linkify for links with ampersands
- [ ] Improve testing coverage
- [ ] Create a downloadable Windows executable
- [ ] Smart "just works for the web" philosophy automatically applies correct filters for monitoring webpages
- [ ] Simplify main legacy Urlwatcher class
- [ ] Implement the ``stealth`` job directive for browser jobs using ``playwright-stealth`` (the ``JobBase.stealth``
  attribute and the ``playwright-stealth`` entry in ``--detailed-versions`` are already in place; then add it to
  ``jobs.schema.json`` and document it)
- [ ] Resolve TODOs
  - [ ] Can/should defusedxml be used?
