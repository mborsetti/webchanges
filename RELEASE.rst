⚠ Breaking Changes
-------------------
* The differ ``command`` now requires that the ``name: command`` subdirective of ``differ`` be specified.

Changed
-------
* The differ ``command`` now has a sub-directive ``is_html`` to indicate when output is in HTML format. Thanks to `Jeff
  Hedlund <https://github.com/jhedlund>`__ for requesting this enhancement in
  `#95 <https://github.com/mborsetti/webchanges/issues/95>`__.
* Added a tip in the documentation on how to `add bullet points
  <https://webchanges.readthedocs.io/en/stable/advanced.html#bullet-points>`__ to improve the legibility of HTML
  reports.

Fixed
-----
* Fixed reporting of errors arising from filters or reporters.
* Fixed reporting of repeated errors (i.e. when the same error occurs multiple times).
* Fixed header and colorization of the differ ``command``.
