⚠ Breaking changes
==================

Pyppeteer has been replaced with Playwright
-------------------------------------------
This change only affects jobs that ``use_browser: true`` (i.e. those running on a browser to run JavaScript). If none
of your jobs have ``use_browser: true``, there's nothing new here (and nothing to do).

Must do
~~~~~~~
If *any* of your jobs have ``use_browser: true``, you **MUST**:

1) Install the new dependencies:

.. code-block:: bash

   pip install --upgrade webchanges[use_browser]

2) (Optional) ensure you have an up-to-date Google Chrome browser:

.. code-block:: bash

   webchanges --install-chrome

Additionally, if any of your ``use_browser: true`` jobs use the ``wait_for`` directive, it needs to be replaced with
one of:

* ``wait_for_function`` if you were specifying a JavaScript function (see
  `here <https://playwright.dev/python/docs/api/class-frame/#frame-wait-for-function>`__ for full function details).
* ``wait_for_selector`` if you were specifying a selector string or xpath string (see `here
  <https://playwright.dev/python/docs/api/class-frame/#frame-wait-for-selector>`__ for full function details), or
* ``wait_for_timeout`` if you were specifying a timeout; however, this function should only be used for debugging
  because it "is going to be flaky", so use one of the other two ``wait_for`` if you can.; full details `here
  <https://playwright.dev/python/docs/api/class-frame#frame-wait-for-timeout>`__.

Optionally, the values of ``wait_for_function`` and ``wait_for_selector`` can now be dicts to take full advantage of all
the features offered by those functions in Playwright (see documentation links above).

If you are using the ``wait_for_navigation`` directive, it is now called ``wait_for_url`` and offers both glob pattern
and regex matching; ``wait_for_navigation`` will act as an alias for now but but a deprecation warning will be issued.

If you are using the ``chromium_revision`` or ``_beta_use_playwright`` directives in your configuration file, you
should delete them to prevent future errors (for now only a deprecation warning is issued).

Finally, if you are  using the experimental ``block_elements`` sub-directive, it is not (yet?) implemented in Playwright
and is simply ignored.

Improvements
~~~~~~~~~~~~
``wait_until`` has additional functionality, and now takes one of:

* ``load`` (default): Consider operation to be finished when the ``load`` event is fired.
* ``domcontentloaded``: Consider operation to be finished when the ``DOMContentLoaded`` event is fired.
* ``networkidle`` (old ``networkidle0`` and ``networkidle2`` map into this): Consider operation to be finished when
  there are no network connections  for at least 500 ms.
* ``commit`` (new): Consider operation to be finished when network response is received and the document started
  loading.

New directives
~~~~~~~~~~~~~~
The following directives are new to the Playwright implementation:

* ``referer``: Referer header value (a string). If provided, it will take preference over the referer header value set
  by the ``headers`` sub-directive.
* ``initialization_url``: A url to navigate to before the ``url`` (e.g. a home page where some state gets set).
* ``initialization_js``: Only used in conjunction with ``initialization_url``, a JavaScript to execute after
  loading ``initialization_url`` and before navigating to the ``url`` (e.g. to emulate a log in).  Advanced usage
* ``ignore_default_args`` directive for ``url`` jobs with ``use_browser: true`` (using Chrome) to control how Playwright
  launches Chrome.

In addition, the new ``--no-headless`` command line argument will run the Chrome browser in "headed" mode, i.e.
displaying the website as it loads it, to facilitate with debugging and testing (e.g. ``webchanges --test 1
--no-headless --test-reporter email``).

See more details of the new directives in the updated documentation.


Freeing space by removing Pyppeteer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can free up disk space if no other packages use Pyppeteer by, in order:

1) Removing the downloaded Chromium images by deleting the entire *directory* (and its subdirectories) shown by running:

.. code-block:: bash

   python -c "import pathlib; from pyppeteer.chromium_downloader import DOWNLOADS_FOLDER; print(pathlib.Path(DOWNLOADS_FOLDER).parent)"

2) Uninstalling the Pyppeteer package by running:

.. code-block:: bash

   pip uninstall pyppeteer


Rationale
~~~~~~~~~
The implementation of ``use_browser: true`` jobs (i.e. those running on a browser to run JavaScript) using Pyppeteer
and the Chromium browser it uses has been very problematic, as the library:

* is in alpha,
* is very slow,
* defaults to years-old obsolete versions of Chromium,
* can be insecure (e.g. found that TLS certificates were disabled for downloading browsers!),
* creates conflicts with imports (e.g. requires obsolete version of websockets),
* is poorly documented,
* is poorly maintained,
* may require OS-specific dependencies that need to be separately installed,
* does not work with Arm-based processors,
* is prone to crashing,
* and outright freezes withe the current version of Python (3.10)!

Pyppeteer's `open issues <https://github.com/pyppeteer/pyppeteer/issues>`__ now exceed 130 and are growing almost daily.

`Playwright <https://playwright.dev/python/>`__ has none of the issues above, the core dev team apparently is the same
who wrote Puppeteer (of which Pyppeteer is a port to Python), and is supported by the deep pockets of Microsoft. The
Python version is officially supported and up-to-date, and (in our configuration) uses the latest stable version of
Google Chrome out of the box without the contortions of manually having to pick and set revisions.

Playwright has been in beta testing within **webchanges** for months and has been performing very well (significantly
more so than Pyppeteer).


Documentation
-------------
* Major updates on anything that has to do with ``use_browser``.
* Fixed two examples of the ``email`` reporter. Reported by `jprokos  <https://github.com/jprokos>`__ in
  `#34 <https://github.com/mborsetti/webchanges/issues/34>`__.


Advanced
--------
* If you subclassed JobBase in your ``hooks.py`` file, and are defining a ``retrieve`` method, please note that the
  number of arguments has been increased to 3 as follows:

.. code-block:: python

   def retrieve(self, job_state: JobState, headless: bool = True) -> Tuple[Union[str, bytes], str]:
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved and the ETag.
        """
