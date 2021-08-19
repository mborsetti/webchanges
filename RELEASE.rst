⚠ Breaking Changes (dependencies)
---------------------------------
* Filter ``pdf2text``'s dependency Python package `pdftotext <https://github.com/jalan/pdftotext>`__ in its latest
  version 2.2.0 has changed the way it displays text to no longer try to emulate formatting (columns etc.). This is
  generally a welcome improvement as changes in formatting no longer trigger change reports, but if you want to
  return to the previous layout we have added a ``physical`` sub-directive which you need to set to ``true`` on the
  jobs affected. **Note that otherwise all your** ``pdf2text`` **jobs will report changes (in formatting) the first
  time they are run after the pdftotext Python package is updated**.

Changed
-------
* Updated default Chromium executables to revisions equivalent to Chromium 92.0.4515.131 (latest stable release); this
  fixes unsupported browser error thrown by certain websites. Use ``webchanges --chromium-directory`` to locate where
  older revision were downloaded to delete them manually.

Added
-----
* Filter ``pdf2text`` now supports the ``raw`` and ``physical`` sub-directives, which are passed to the underlying
  Python package `pdftotext <https://github.com/jalan/pdftotext>`__ (version 2.2.0 or higher).
* New ``--chromium-directory`` command line displays the directory where the downloaded Chromium executables are
  located to facilitate the deletion of older revisions.
* Footer now indicates if the run was made with a jobs file whose stem name is not the default 'jobs', to ease
  identification when running *webchanges* with a variety of jobs files.

Fixed
-----
* Fixed legacy code handling ``--edit-config`` command line argument to allow editing of a configuration file
  with YAML syntax errors (`#15 <https://github.com/mborsetti/webchanges/issues/15>`__ by
  `Markus Weimar <https://github.com/Markus00000>`__).
* Telegram reporter documentation was missing instructions on how to notify channels (`#16
  <https://github.com/mborsetti/webchanges/issues/16>`__ by `Sean Tauber <https://github.com/buzzeddesign>`__).

Internals
---------
* Type hints are checked during pre-commit by `mypy <http://www.mypy-lang.org/>`__.
* Imports are rearranged during pre-commit by `isort <https://pycqa.github.io/isort/>`__.
* Now testing all database engines, including redis, and more, adding 4 percentage points of code coverage to 81%.
* The name of a FilterBase subclass is always its __kind__ + Filter (e.g. the class for ``element-by-id`` filter is
  named ElementByIDFilter and not GetElementByID)
