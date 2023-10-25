Added
-----
* Support for Python 3.12.
* ``data_as_json`` job directive for ``url`` jobs to indicate that ``data`` entered as a dict should be
  serialized as JSON instead of urlencoded and, if missing, the header ``Content-Type`` set to ``application/json``
  instead of ``application/x-www-form-urlencoded``.

Changed
-------
* Improved error handling and documentation on the need of an external install when using ``parser: html5lib`` with the
  ``bs4`` method of the ``html2text`` filter and added ``html5lib`` as an optional dependency keyword (thanks to
  `101Dude <https://github.com/101Dude>`__'s report in `59 <https://github.com/mborsetti/webchanges/issues/59>`__).

Removed
-------
* Support for Python 3.8. A reminder that older Python versions are supported for 3 years after being obsoleted by a
  new major release (i.e. about 4 years since their original release).

Internals
---------
* Upgraded build environment to use the ``build`` frontend and ``pyproject.toml``, eliminating ``setup.py``.
* Migrated to ``pyproject.toml`` the configuration of all tools who support it.
* Increased the default ``timeout`` for ``url`` jobs with ``use_browser: true`` (i.e. using Playwright) to 120 seconds.
