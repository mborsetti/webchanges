Added
-----
* ``re.findall`` filter to extract, delete or replace non-overlapping text using Python ``re.findall``.

Changed
-------
* ``--test-reporter`` now allows testing of reporters that are not enabled; the error that the reporter is not enabled
  is now a warning. This simplifies testing.
* ``email`` reporter supports sending to multiple "to" addresses (both SMTP and sendmail)

Fixed
-----
* Reports from jobs with ``monospace: true`` were not being rendered correctly in Gmail.
