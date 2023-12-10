Added
-----
* You can now specify a reporter name after the command line argument ``--errors`` to send the output to the reporter
  specified. For example, to be notified by email of any jobs that result in an error or who, after filtering,
  return no data (indicating they may no longer be monitoring resources as expected), run ``webchanges --errors
  email``.
* You can now suppress the ``footer`` in an ``html`` report using the new ``footer: false`` sub-directive in
  ``config.yaml`` (same as the one already existing with ``text`` and ``markdown``).

Internal
--------
* Fixed a regression on the default ``User-Agent`` header for ``url`` jobs with the ``use_browser: true`` directive.
