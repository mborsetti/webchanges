Added
-------------------
* Support for Python 3.13.
* The ``--hooks`` command line argument now accepts glob patterns.
* Multiple hook files or glob patterns can now be specified by repeating the ``--hooks`` argument.
* ``--detailed-versions`` will now show the default value for ``--max-threads`` on the system it's running.
* Optional support of ``zstd`` compression in URL jobs without ``browser: true`` (requires ``pip install -U
  webchanges[zstd]``).
* Addition to the ``ai_google`` differ (BETA):

  - New ``task`` subdirective ``summarize_new``. When used, the report will contain an AI-generated summary of the
    new text found. This is useful, for example, when monitoring a page to which new content, such as the text of
    press releases, is periodically added;
  - New ``unified_diff_new`` filed for the ``prompt`` directive.

Changed
-------------------
* The security requirement that a file containing ``command`` jobs or ``shellpipe`` filters, or any hook file, be
  owned and writeable only by the user currently running the program has been relaxed to include ownership by the
  root user.
* Changes to the ``ai_google`` differ (BETA):

  - ⚠ breaking change: ``old_data`` and ``new_data`` fields in the ``prompt`` directive have been renamed to
    ``old_text`` and  ``new_text`` for clarity;
  - Significantly improved the quality of the output by rewriting the default values for ``system_instructions`` and
    ``prompt``.
  - Improved and updated the documentation.

Fixed
-------------------
* Improved handling of links with empty text in the Markdown to HTML converter.
* Fixed ``image`` differ's HTML formatting.

Removed
-------
* Removed support for Python 3.9. A reminder that older Python versions are supported for 3 years after being
  obsoleted by a new major release (i.e. about 4 years since their original release).
