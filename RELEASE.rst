Added
-----
* Python 3.13 Support: **webchanges** now supports Python 3.13, but complete testing is pending due to dependencies
  such has ``lxml`` not having yet published installation packages ("wheels") for 3.13.
* Glob Pattern Support for Hooks Files: The ``--hooks`` command-line argument now accepts glob patterns for flexible
  hook file selection.
* Multiple Hook Specifications: Specify multiple hook files or glob patterns by repeating the ``--hooks`` argument.
* Enhanced Version Information: ``--detailed-versions`` now displays the system's default value for
  ``--max-threads``.
* Optional ``zstd`` Compression: URL jobs without ``browser: true`` can now utilize ``zstd`` compression for
  improved efficiency (requires ``pip install -U webchanges[zstd]``).
* ``ai_google`` Differ Enhancements (BETA):

  * New ``additions_only`` Subdirective: When set to true, generates AI-powered summaries of only the added text. This
    is particularly helpful for monitoring pages with regularly added content (e.g., press releases).
  * New ``unified_diff_new`` Field: Added to the ``prompt`` directive.

Changed
-------
* Relaxed Security for Job and Hook Files: The ownership requirement for files containing ``command`` jobs,
  ``shellpipe`` filters, or hook files has been expanded to include root ownership, in addition to the current user.
* ``ai_google`` Differ Refinements (BETA):

  *  Renamed Prompt Fields (⚠ BETA breaking change):  For clarity, ``old_data`` and ``new_data`` fields in the
     ``prompt`` directive have been renamed to ``old_text`` and ``new_text``, respectively.
  *  Improved Output Quality: Significantly enhanced output quality by revising the default values for
     ``system_instructions`` and ``prompt``.
  *  Updated Documentation.

Fixed
-----
* Markdown Handling: Improved handling of links with empty text in the Markdown to HTML converter.
* ``image`` Differ Formatting: Fixed HTML formatting issues within the ``image`` differ.

Removed
-------
* Python 3.9 Support: Support for Python 3.9 has been dropped. As a reminder, older Python versions are supported for 3
  years after being superseded by a new major release (i.e. approximately 4 years after their initial release).
