⚠ Last release using Pyppeteer
------------------------------
* This is the last release using Pyppeteer for jobs with ``use_browser: true``, which will be replaced by Playwright
  in release 9.10, forthcoming hopefully in a few weeks. See above for more information on how to prepare -- and start
  using Playwright now!

Added
-----
* New ``ignore_dh_key_too_small`` directive for URL jobs to overcome the ``ssl.SSLError: [SSL: DH_KEY_TOO_SMALL] dh key
  too small (_ssl.c:1129)`` error.
* New ``indent`` sub-directive for the ``beautify`` filter (requires BeautifulSoup version 4.11.0 or later).
* New ``--dump-history JOB`` command line argument to print all saved snapshot history for a job.
* Playwright only: new``--no-headless`` command line argument to help with debugging and testing (e.g. run
  ``webchanges --test 1 --no-headless``).  Not available for Pyppeteer.
* Extracted Discord reporting from ``webhooks`` into its own ``discord`` reporter to fix it not working and to
  add embedding functionality as well as color (contributed by `Michał Ciołek  <https://github.com/michalciolek>`__
  `upstream <https://github.com/thp/urlwatch/issues/683>`__. Reported by `jprokos <https://github.com/jprokos>`__` in
  `#33 <https://github.com/mborsetti/webchanges/issues/33>`__.

Fixed
-----
* We are no longer rewriting to disk the entire database at every run. Now it's only rewritten if there are changes
  (and minimally) and, obviously, when running with the ``--gc-cache`` or ``--clean-cache`` command line argument.
  Reported by `JsBergbau <https://github.com/JsBergbau>`__ `upstream <https://github.com/thp/urlwatch/issues/690>`__.
  Also updated documentation suggesting to run ``--clean-cache`` or ``--gc-cache`` periodically.
* A ValueError is no longer raised if an unknown directive is found in the configuration file, but a Warning is
  issued instead. Reported by `c0deing <https://github.com/c0deing>`__ in `#26
  <https://github.com/mborsetti/webchanges/issues/26>`__.
* The ``kind`` job directive (used for custom job classes in ``hooks.py``) was undocumented and not fully functioning.
* For jobs with ``use_browser: true`` and a ``switch`` directive containing ``--window-size``, turn off Playwright's
  default fixed viewport (of 1280x720) as it overrides ``--window-size``.
* Email headers ("From:", "To:", etc.) now have title case per RFC 2076. Reported by `fdelapena
  <https://github.com/fdelapena>`__ in `#29 <https://github.com/mborsetti/webchanges/issues/29>`__.

Documentation
-------------
* Added warnings for Windows users to run Python in UTF-8 mode. Reported by `Knut Wannheden
  <https://github.com/knutwannheden>`__ in `#25 <https://github.com/mborsetti/webchanges/issues/25>`__.
* Added suggestion to run ``--clean-cache`` or ``--gc-cache`` periodically to compact the database file.
* Continued improvements.

Internals
---------
* Updated licensing file to `GitHub naming standards
  <https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/adding-a-license-to-a-repository>`__
  and updated its contents to more clearly state that this software redistributes source code of release 2.21
  of urlwatch (https://github.com/thp/urlwatch/tree/346b25914b0418342ffe2fb0529bed702fddc01f), retaining its license,
  which is distributed as part of the source code.
* Pyppeteer has been removed from the test suite.
* Deprecated ``webchanges.jobs.ShellError`` exception in favor of Python's native ``subprocess.SubprocessError`` one and
  its subclasses.
