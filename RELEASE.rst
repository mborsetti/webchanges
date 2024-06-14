Added
-------------------
* Command line argument ``--rollback-database`` now accepts dates in ISO-8601 format in addition to Unix timestamps.
  If the library dateutil (not a dependency of **webchanges**) is found installed, then it will also accept any
  string recognized by ``dateutil.parser`` such as date only, time only, date and time, etc. (Suggested
  by `Markus Weimar <https://github.com/Markus00000>`__ in issue `#78
  <https://github.com/mborsetti/webchanges/issues/78>`__).
* ``ai-google`` differ (BETA) now supports calls to the Gemini 1.5 Pro with 2M tokens model (early access required).
