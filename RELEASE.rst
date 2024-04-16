Added
-----
* **Job selectable differs**: The differ, i.e. the method by which changes are detected and summarized, can now be
  selected job by job. Also gone is the restriction to have only unified diffs, HTML table diff, or calling an outside
  executable, as differs have become modular.

  - Python programmers can write their own custom differs using the ``hooks.py`` file.
  - Backward-compatibility is preserved, so your current jobs will continue to work.
* **New differs**:

  - ``difflib`` to report element-by-element changes in JSON or XML structured data.
  - ``imagediff`` (BETA) to report an image showing changes in an **image** being tracked.
  - ``ai_google`` (BETA) to use a **Generative AI provide a summary of changes** (free API key required). We use
    Google's Gemini Pro 1.5 since it is the first model that can ingest 1M tokens, allowing to analyze changes in
    long documents (up to 350,000 words, or about 700 pages single-spaced) such as terms and conditions, privacy
    policies, etc. where summarization adds the most value and which other models can't handle. The differ can call
    the Gen AI model to summarize a unified diff or to find and summarize the differences itself. Also supported is
    Gemini 1.0, but it can handle a lower number of tokens.

Changed
-------
* Filter ``absolute_links`` now converts URLs of the ``action``, ``href`` and ``src`` attributes in any HTML tag, as
  well as the ``data`` attribute of the ``<object>`` tag; it previously converted only the ``href`` attribute of
  ``<a>`` tags.
* Updated explanatory text and error messages for increased clarity.
* You can now select jobs to run by using its url/command instead of its number, e.g. ``webchanges https://test.com`` is
  just as valid as ``webchanges 1``.

Deprecated
----------
* Job directive ``diff_tool``. Replaced with the ``command`` differ (see `here
  <https://webchanges.readthedocs.io/en/stable/differs.html#command_diff>`__.

Fixed
-----
* ``webchanges --errors`` will no longer check jobs who have ``disabled: true`` (thanks to `yubiuser
  <https://github.com/yubiuser>`__ for reporting this in issue `# 73
  <https://github.com/mborsetti/webchanges/issues/73>`__).
* Markdown links with no text were not clickable when converted to HTML; conversion now adds a 'Link without text'
  label.

Internals
---------
* Improved speed of creating a unified diff for an HTML report.
* Reduced excessive logging from ``httpx``'s sub-modules ``hpack`` and ``httpcore`` when running with ``-vv``.
