Added
-----
* You can now specify a reporter name after the command line argument ``--errors``. This will send the output to the
  reporter specified. For example, to be notified by email of any jobs that result in an error or who, after filtering,
  return no data (indicating they may no longer be monitoring resources as expected), run ``webchanges --errors
  email``.
* The ``html`` report now has a ``footer`` sub-directive (like ``text`` and ``markdown``).
