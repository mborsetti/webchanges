Reminder
--------
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.7 was
released on 7 June 2018, the codebase will be streamlined by removing support for Python 3.6 on or after 7 June 2021.

Added
-----
* Clearer results messages for `--delete-snapshot` command line argument


Fixed
-----
* First run would fail when creating new ``config.yaml`` file. Thanks to `David <https://github.com/notDavid>`__ in
  issue `#10 <https://github.com/mborsetti/webchanges/issues/10>`__.
* Use same duration precision in all reports
