Changed
--------
* Tweaked colors (esp. green) of HTML reporter to work with Dark Mode
* Restored API documentation using Sphinx's autodoc (removed in 3.2.4 as it was not building correctly)

Internal
--------
* Replaced custom atomic_rename function with built-in `os.replace()
  <https://docs.python.org/3/library/os.html#os.replace>`__ (new in Python 3.3) that does the same thing
* Added type hinting to the entire code
* Added new tests, increasing coverage to 57%
* GitHub Actions CI now runs faster as it's set to cache required packages from prior runs

Known issues
------------
* Discovered that upstream (legacy) `urlwatch` 2.22 code has the database growing to infinity; run ``webchanges
  --clean-cache`` periodically to discard old snapshots until this is addressed in a future release
* ``url`` jobs with ``use_browser: true`` (i.e. using Pyppeteer) will at times display the below error message in stdout
  (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed in the
  future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``
  ``Future exception was never retrieved``
