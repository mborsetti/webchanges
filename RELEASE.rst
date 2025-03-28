Added
-----
* README links to a new Docker implementation which includes the Chrome browser. Generously offered by and maintained
  by `Jeff Hedlund <https://github.com/jhedlund>`__ as per `#96 <https://github.com/mborsetti/webchanges/issues/96>`__.
* New filter ``jsontoyaml`` to convert JSON to YAML, which is generally more readable in a report for humans.
* New ``yaml`` data type for the ``deepdiff`` differ (in addition to ``json`` and ``xml``).

Changed
-------
* The ``deepdiff`` differ will now try to derive the ``data-type`` (when it is not specified) from the data's media
  type (fka MIME type) before defaulting to ``json``.

Fixed
-----
* Fixed confusing warning when no default hooks.py file exists. Thanks to `Marcos Alano <https://github.com/mhalano>`__
  for reporting in `#97 <https://github.com/mborsetti/webchanges/issues/97>`__.
* The ``format-json`` filter now uses JSON text instead of plain text to report errors caused by it not receiving
  valid JSON data, to be compatible with downstream filters or differs.
* Fixed the differ ``ai_google`` (BETA), which under certain circumstances was omitting the footnote with the version
  of the GenAI model used.
