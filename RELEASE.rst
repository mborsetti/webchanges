⚠ Breaking Changes
------------------
* Fixed the database from growing unbounded to infinity. Fix only works when running in Python 3.7 or higher and using
  the new, default, ``sqlite3`` database engine. In this scenario only the latest 4 snapshots are kept, and older ones
  are purged after every run; the number is selectable with the new ``--max-snapshots`` command line argument. To keep
  the existing grow-to-infinity behavior, run `webchanges` with ``--max-snapshots 0``.

Added
-----
* ``--max-snapshots`` command line argument sets the number of snapshots to keep stored in the database; defaults to
  4. If set to 0 an unlimited number of snapshots will be kept. Only applies to Python 3.7 or higher and only works if
  the default ``sqlite3`` database is being used.
* ``no_redirects`` job directive (for ``url`` jobs) to disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection
  (true/false). Suggested by `snowman <https://github.com/snowman>`__ upstream `here
  <https://github.com/thp/urlwatch/issues/635>`__.
* Reporter ``prowl`` for the `Prowl <https://prowlapp.com>`__ push notification client for iOS (only). Contributed
  by `nitz <https://github.com/nitz>`__ upstream in PR `633 <https://github.com/thp/urlwatch/pull/633>`__.
* Filter ``jq`` to parse, transform, and extract ASCII JSON data. Contributed by `robgmills
  <https://github.com/robgmills>`__ upstream in PR `626 <https://github.com/thp/urlwatch/pull/626>`__.
* Filter ``pretty-xml`` as an alternative to ``format-xml`` (backwards-compatible with `urlwatch` 2.23)
* Alert user when the jobs file contains unrecognized directives (e.g. typo)

Changed
--------
* Job name is truncated to 60 characters when derived from the title of a page (no directive ``name`` is found in a
  ``url`` job)
* ``--test-diff`` command line argument displays all saved snapshots (no longer limited to 10)

Fixed
-----
* Diff (change) data is no longer lost if `webchanges` is interrupted mid-execution or encounters an error in reporting:
  the permanent database is updated only at the very end (after reports are dispatched)
* ``use_browser: false`` was not being interpreted correctly
* Jobs file (e.g. ``jobs.yaml``) is now loaded only once per run

Internals
---------
* Database ``sqlite3`` engine now saves new snapshots to a temporary database, which is copied over to the permanent one
  at execution end (i.e. database.close())
* Upgraded SMTP email message internals to use Python's `email.message.EmailMessage
  <https://docs.python.org/3/library/email.message.html#email.message.EmailMessage>`__ instead of ``email.mime``
  (obsolete)
* Pre-commit documentation linting using ``doc8``
* Added logging to ``sqlite3`` database engine
* Additional testing increasing overall code coverage by an additional 4 percentage points to 65%
* Renamed legacy module browser.py to jobs_browser.py for clarity
* Renamed class JobsYaml to YamlJobsStorage for consistency and clarity

Known issues
------------
* ``url`` jobs with ``use_browser: true`` (i.e. using Pyppeteer) will at times display the below error message in stdout
  (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed in the
  future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``
