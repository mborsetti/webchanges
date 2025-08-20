Added
`````
* Documented the ``deepdiff`` differ for side-effects of using ``ignore_order: true``.
* Added the ``utf-8`` configuration  within the ``smtp`` emailer (``email`` report) to turn off RFC 6531
  Internationalized Email, aka SMTPUTF8 service extension. Requested in #`108
  <https://github.com/mborsetti/webchanges/issues/108>`__.

Fixed
`````
* Fixed handling of Playwright exceptions for ``browser: true`` jobs. Reported in #`106
  <https://github.com/mborsetti/webchanges/issues/106>`__.

Internals
`````````
* Code is now formated with ``ruff format`` instead of ``black``.
* Code is now linted with ``ruff --fix`` instead of ``isort`` and ``flake8`` and its extensions.
* Packages in test environments are now done with ``uv``.
* Experimenting with `Gemini CLI GitHub Action <https://github.com/google-github-actions/run-gemini-cli/>`__ to triage
  issues and perform pull request reviews (thanks to Google's generous free-of-charge quotas).
