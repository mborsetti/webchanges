Added
`````
* Added a note in the documentation on the side-effects of using ``ignore_order: true`` with the ``deepdiff`` differ.
* Added the configuration directive ``utf-8`` within ``smtp`` of the ``email`` report, to turn off RFC 6531
  Internationalized Email, aka SMTPUTF8 service extension. Requested in #`108
  <https://github.com/mborsetti/webchanges/issues/108>`__.

Internals
`````````
* Fixed handling of Playwright exceptions for ``browser: true`` jobs. Reported in #`106
  <https://github.com/mborsetti/webchanges/issues/106>`__.
* Code formatting is now done with ``ruff format`` instead of ``black``.
* Code linting is now done with ``ruff --fix`` instead of ``isort`` and ``flake8`` and its extensions.
* Experimenting with `Gemini CLI GitHub Action <https://github.com/google-github-actions/run-gemini-cli/>`__ to triage
  issues and perform pull request reviews (thanks to Google's generous free-of-charge quotas).
