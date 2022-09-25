Notice
------
Support for Python 3.7 will be removed on or about 22 October 2022 as older Python versions are supported for 3
years after being obsoleted by a new major release.

Added
-----
* The new ``no_conditional_request`` directive for ``url`` jobs turns off conditional requests for those extremely rare
  websites that don't handle it (e.g. Google Flights).
* Selecting the database engine and the maximum number of changed snapshots saved is now set through the configuration
  file, and the command line arguments ``--database-engine`` and ``--max-snapshots`` are used to override such
  settings. See documentation for more information. Suggested by `jprokos <https://github.com/jprokos>`__ in `#43
  <https://github.com/mborsetti/webchanges/issues/43>`__.
* New configuration file setting ``empty-diff`` within the ``display`` configuration for backwards compatibility only:
  use the ``additions_only`` job directive instead to achieve the same result. Reported by
  `bbeevvoo <https://github.com/bbeevvoo>`__ in `#47 <https://github.com/mborsetti/webchanges/issues/47>`__.
* Aliased the command line arguments ``--gc-cache`` with ``--gc-database``, ``--clean-cache`` with ``--clean-database``
  and ``--rollback-cache`` with ``--rollback-database`` for clarity.
* The configuration file (e.g. ``conf.yaml``) can now contain keys starting with a ``_`` (underscore) for remarks (they
  are ignored).

Changed
-------
* Reports are now sorted alphabetically and therefore you can use the ``name`` directive to affect the order by which
  your jobs are displayed in reports.
* Implemented measures for ``url`` jobs using ``browser: true`` to avoid being detected: **webchanges** now passes all
  the headless Chrome detection tests `here
  <https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html>`__.
  Brought to my attention by `amammad <https://github.com/amammad>`__ in `#45
  <https://github.com/mborsetti/webchanges/issues/45>`__.
* Running ``webchanges --test`` (without specifying a JOB) will now check the hooks file (if any) for syntax errors in
  addition to the config and jobs file. Error reporting has also been improved.
* No longer showing the the text returned by the server when a 404 - Not Found error HTTP status code is returned by for
  all ``url`` jobs (previously only for jobs with ``use_browser: true``).

Fixed
-----
* Bug in command line arguments ``--config`` and ``--hooks``. Contributed by
  `Klaus Sperner <https://github.com/klaus-tux>`__ in PR `#46 <https://github.com/mborsetti/webchanges/pull/46>`__.
* Job directive ``compared_versions`` now works as documented and testing has been added to the test suite. Reported by
  `jprokos <https://github.com/jprokos>`__ in `#43 <https://github.com/mborsetti/webchanges/issues/43>`__.
* The output of command line argument ``--test-diff`` now takes into consideration ``compared_versions``.
* Markdown containing code in a link text now converts correctly in HTML reports.

Internals
---------
* The job ``kind`` of ``shell`` has been renamed ``command`` to better reflect what it does and the way it's described
  in the documentation, but ``shell`` is still recognized for backward compatibility.
* Readthedocs build upgraded to Python 3.10
