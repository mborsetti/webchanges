Added
-------------------
* New ``wdiff`` differ to perform word-by-word comparisons. Replaces the dependency on an outside executable and
  allows for much better formatting and integration.
* New ``system_instructions`` directive added to the ``ai-google`` differ (BETA).
* Added to the documentation examples on how to use the ``re.findall`` filter to extract only the first or last line
  (suggested by `Marcos Alano <https://github.com/malano>`__ in issue `#81
  <https://github.com/mborsetti/webchanges/issues/81>`__).

Changed
------------------
* Updated the documentation for the ``ai-google`` differ (BETA), mostly to reflect billing changes by Google, which is
  still free for most.

Fixed
------------------
* Fixed a data type check in preventing ``URL`` jobs' ``data`` (for POSTs etc.) to be a list.
