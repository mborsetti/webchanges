Added
-----
* ``re.findall`` filter to extract, delete or replace non-overlapping text using Python ``re.findall``.

Changed
-------
* ``--test-reporter`` now allows testing of reporters that are not enabled; if a reporter is not enabled, a warning
  will be issued. This simplifies testing.
* ``email`` reporter (both SMTP and sendmail) supports sending to multiple "to" addresses.

Fixed
-----
* Reports from jobs with ``monospace: true`` were not being rendered correctly in Gmail.
