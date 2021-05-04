Added
-----
* New sub-directives to the ``strip`` filter:

  * ``chars``: Set of characters to be removed (default: whitespace)
  * ``side``: One-sided removal, either ``left`` (leading characters) or ``right`` (trailing characters)
  * ``splitlines``: Whether to apply the filter on each line of text (true/false) (default: ``false``, i.e. apply to
    the entire data)
* ``--delete-snapshot`` command line argument: Removes the latest saved snapshot of a job from the database; useful
  if a change in a website (e.g. layout) requires modifying filters as invalid snapshot can be deleted and `webchanges`
  rerun to create a truthful diff
* ``--log-level`` command line argument to control the amount of logging displayed by the ``-v`` argument
* ``ignore_connection_errors``, ``ignore_timeout_errors``, ``ignore_too_many_redirects`` and ``ignore_http_error_codes``
  directives now work with ``url`` jobs having ``use_browser: true`` (i.e. using `Pyppeteer`)

Changed
-------
* Diff-filter ``additions_only`` will no longer report additions that consist exclusively of added empty lines
  (issue `#6 <https://github.com/mborsetti/webchanges/issues/6>`__, contributed by `Fedora7
  <https://github.com/Fedora7>`__)
* Diff-filter ``deletions_only`` will no longer report deletions that consist exclusively of deleted empty lines
* The job's index number is included in error messages for clarity
* ``--smtp-password`` now checks that the credentials work with the SMTP server (i.e. logs in)

Fixed
-----
* First run after install was not creating new files correctly (inherited from `urlwatch`); now `webwatcher` creates
  the default directory, config and/or jobs files if not found when running (issue `#8
  <https://github.com/mborsetti/webchanges/issues/8>`__, contributed  by `rtfgvb01 <https://github.com/rtfgvb01>`__)
* ``test-diff`` command line argument was showing historical diffs in wrong order; now showing most recent first
* An error is now raised when a ``url`` job with ``use_browser: true`` returns no data due to an HTTP error (e.g.
  proxy_authentication_required)
* Jobs were included in email subject line even if there was nothing to report after filtering with ``additions_only``
  or ``deletions_only``
* ``hexdump`` filter now correctly formats lines with less than 16 bytes
* ``sha1sum`` and ``hexdump`` filters now accept data that is bytes (not just text)
* An error is now raised when a legacy ``minidb`` database is found but cannot be converted because the ``minidb``
  package is not installed
* Removed extra unneeded file from being installed
* Wrong ETag was being captured when a URL redirection took place

Internals
---------
* `Pyppeteer` (``url`` jobs using ``use_browser: true``) now capture and save the ETag
* Snapshot timestamps are more accurate (reflect when the job was launched)
* Each job now has a run-specific unique index_number, which is assigned sequentially when loading jobs, to use in
  errors and logs for clarity
* Improvements in the function chunking text into numbered lines, which used by certain reporters (e.g. Telegram)
* More tests, increasing code coverage by an additional 7 percentage points to 72% (although keyring testing had to be
  dropped due to issues with GitHub Actions)
* Additional cleanup of code and documentation

Known issues
------------
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed
  in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``
