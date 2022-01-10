⚠ Breaking changes in the near future (opt-in now):
---------------------------------------------------
Jobs with``use_browser: true`` will use Playwright instead of Pyppeteer (can opt in now)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The implementation of ``use_browser: true`` jobs (i.e. those running on a browser to run JavaScript) using Pyppeteer
has been very problematic, as the library:

* is in alpha,
* is very slow,
* defaults to years-old obsolete versions of Chromium,
* is not vetted for security (TLS certificates were disabled for downloading browsers!)
* at times holds back versions of other packages (e.g. requires obsolete version of websockets)
* is poorly documented,
* is poorly maintained,
* and it freezes when running it in the current version of Python (3.10)!

The `open issues <https://github.com/pyppeteer/pyppeteer/issues>`__ now exceed 100.

As a result, I have been investigating a substitute, and found one in `Playwright
<https://playwright.dev/python/>`__, in combination with the latest stable version of Google Chrome. This package has
none of the issues above, the core dev team apparently is the same who did Puppetter, and is supported by the might
of Microsoft who has been keeping the Python version up-to-date (pyppeteer is several versions behind Puppetter, which
it is based upon).

You can upgrade to Playwright now (and your help is needed)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The Playwright implementation in this release of **webchanges** is extremely stable, fully tested (even on Python
3.10!), and much faster than Pyppeteer (some of my jobs are running 3x faster!), but before switching over I am
releasing it as an opt-in beta just in case there are some bugs outside of the test cases.

I urge you to try Playwright. To do so:

Install dependencies::

   pip install --upgrade webchanges[playwright]

Ensure you have an up-to-date Chrome installation::

   webchanges --install-chrome

Edit your configuration file...::

   webchanges --edit-config

...to add ``_beta_use_playwright`` under the ``browser`` section of ``job_defaults`` like this (note the leading
underline):

.. code-block:: yaml

   job_defaults:
     browser:
         _beta_use_playwright: true

That's it!

All job sub-directives works as they are, with only two minor exceptions:

* ``wait_for`` needs to be replaced with either ``wait_for_selector`` (see more `here
  <https://playwright.dev/python/docs/api/class-frame/#frame-wait-for-function>`__) or ``wait_for_function`` (see
  more `here <https://playwright.dev/python/docs/api/class-frame/#frame-wait-for-function>`__).
  These can still be strings (in which case they will be either the selector or the expression) but also dicts with
  arguments accepted by those functions (except for timeout, which is set by the ``timeout`` sub-directory).
* The experimental ``block_elements`` sub-directive is not implemented (yet?) and is simply ignored.

The following sub-directives are new:

* ``referer``: Referer header value. If provided it will take preference over the referer header value set by the
  ``headers`` sub-directive.
* ``headless`` (true/false): Launch browser in headless mode (i.e. invisible) (defaults to true). Set it to false to see
  what's going on in the browser for debugging purposes.

Please make sure to open a GitHub `issue <https://github.com/mborsetti/webchanges/issues>`__ if you encounter
anything wrong!

If you decide to stick with Playwright, you can free up disk space (if no other package uses Pyppeteer) by removing
the downloaded Chromium by *deleting the directory shown* by running::

   webchanges --chromium-directory

and uninstalling the Pyppeteer package by running::

   pip uninstall pyppeteer

Another improvement I made is that now the parallilzation of jobs when ``use_browser: true`` jobs are present is
determined by based on the amount of free memory available, which seems to be the relevant constraint.

Changed
-------
* The method ``bs4`` of filter ``html2text`` has a new ``strip`` sub-directive which is passed to BeautifulSoup, and
  its default value now conforms to BeautifulSoup's default of false since it gives better output in most cases. To
  restore the previous behavior, add the ``strip: true`` sub-directive of the ``html2text`` filter to impacted jobs.
* When multiple URL jobs have the same network location, a random delay between 0.1 and 1.0 seconds is added to
  all jobs to that network location after the first one. This prevents being blocked by the site as a result of being
  flooded by **webchanges**'s parallelism sending multiple requests from the same source at the same exact time.

Added
-----
* The ``html`` report type has a new job directive ``monospace``, which sets the output to use a monospace font.
  This can be useful e.g. for tabular text extracted by the ``pdf2text`` filter.
* The method ``bs4`` of filter ``html2text`` now accepts the sub-directives ``separator`` and ``strip``.
* When using the command line argument ``--test-diff``, the output can now be sent to a specific reporter by also
  specifying the ``--test-reporter`` argument. For example, if running on a machine with a web browser, you can see
  the HTML version of the last diff(s) from job 1 with ``webchanges --test-diff 1 --test-reporter browser`` on your
  local browser.
* New filter ``remove-duplicate-lines``. Contributed by `Michael Sverdlin <https://github.com/sveder>`__ upstream `here
  <https://github.com/thp/urlwatch/pull/653>`__ (with modifications).
* New filter ``csv2text``. Contributed by `Michael Sverdlin <https://github.com/sveder>`__ upstream `here
  <https://github.com/thp/urlwatch/pull/658>`__ (with modifications).
* Beta version of Playwright as a replacement for pyppeteer for jobs with ``use_browser: true`` (see above).

Fixed
-----
* During conversion of Markdown to HTML,
  * Code blocks were not rendered in monospace font with no wrapping;
  * Spaces immediately after ````` (code block opening) were being dropped.
* The ``email`` reporter's ``sendmail`` sub-directive was not passing the ``from`` sub-directive (when specified) to
  the ``sendmail`` executable as ``-f`` command line argument. Contributed by
  `Jonas Witschel <https://github.com/diabonas>`__ upstream `here <https://github.com/thp/urlwatch/pull/671>`__ (with
  modifications).
* When the job name is determined from the <title> tag of the data monitored (if present), HTML characters were not
  being unescaped.
* Command line argument ``--test-diff`` was only showing the last diff instead of all saved ones.

Documentation
-------------
* Updated the "recipe" for monitoring Facebook public posts.
* Improved documentation for filter ``pdf2text``.

Internals
---------
* Support for Python 3.10 (except for ``use_browser`` using pyppeteer since it does not yet support it).
* Improved speed of detection and handling of lines starting with spaces during conversion of Markdown to HTML.
* Logs now show thread IDs to help with debugging.
