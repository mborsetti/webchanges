Fixed
-----
* Fixed incorrect handling of HTTP client libraries when ``httpx`` is not installed (should graciously fallback to
  ``requests``).  Reported by `drws <https://github.com/drws>`__ as an add-on to `issuse #66
  <https://github.com/mborsetti/webchanges/issues/66>`__.

Added
-----
* Job directive ``enabled`` to allow disabling of a job without removing or commenting it in the jobs file (contributed
  by `James Hewitt <https://github.com/Jamstah>`__ `upstream <https://github.com/thp/urlwatch/pull/785>`__).
* ``webhook`` reporter has a new ``rich_text`` config option for preformatted rich text for Slack (contributed
  by `K̶e̶v̶i̶n̶ <https://github.com/vimagick>`__ `upstream <https://github.com/thp/urlwatch/pull/780>`__).

Changed
-------
* Command line argument ``--errors`` now uses conditional requests to improve speed. Do not use to test newly modified
  jobs since websites reporting no changes from the last snapshot stored by **webchanges** are skipped; use
  ``--test`` instead.
* If the ``simplejson`` library is installed, it will be used instead of the built-in ``json`` module (see
  https://stackoverflow.com/questions/712791).
