Added
`````
* Documented the ``deepdiff`` differ for side-effects when using ``ignore_order: true``.
* Added the ``utf-8`` configuration  within the ``smtp`` emailer (``email`` report) to turn off RFC 6531
  Internationalized Email, aka SMTPUTF8 service extension. Requested in #`108
  <https://github.com/mborsetti/webchanges/issues/108>`__.

Fixed
`````
* Fixed regresion: getting messages with deletion when the content still seems to be there. Reported in #`104
  <https://github.com/mborsetti/webchanges/issues/104>`__.
* Fixed handling of Playwright exceptions for ``browser: true`` jobs. Reported in #`106
  <https://github.com/mborsetti/webchanges/issues/106>`__.
* Fixed ``--detailed-versions`` CLI, which raised an Exception if playwright was installed but no Chromium browser was
  available.
* Fixed ``monospace: true`` in HTML reports, which was overly applied to include Comparison Type banners.
* Fixed ``deepdiff`` differ, which would not convert Markdown to HTML when needed.
* Fixed url jobs with ``no_redirects: true``, who would not report the redirect response correctly.
* Fixed ``delete-snapshot``, which would not display the time of snapshots in the timezone set for reports (if one is
  set).
* Fixed ``xpath`` filter, which would throw an Exception with an XPath ``concat()`` string function.

Internals
`````````
* Code is now formated with ``ruff format`` instead of ``black``.
* Code is now linted with ``ruff check`` instead of ``isort`` and ``flake8`` and its extensions.
* Packages in test environments are now installed with ``uv``.
* Experimenting with `Gemini CLI GitHub Action <https://github.com/google-github-actions/run-gemini-cli/>`__ to triage
  issues and perform pull request reviews (thanks to Google's generous free-of-charge quotas).
* Starting to implement lazy loading of packages and modules to improve startup time for command line arguments.
