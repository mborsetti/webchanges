⚠ Breaking changes in the near future (opt-in now):
---------------------------------------------------
Pyppetter will be replaced with Playwright (can opt in now!)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The implementation of ``use_browser: true`` jobs (i.e. those running on a browser to run JavaScript) using Pyppeteer
has been very problematic, as the library:

* is in alpha,
* is very slow,
* defaults to years-old obsolete versions of Chromium,
* can be insecure (found that TLS certificates were disabled for downloading browsers!)
* creates conflicts with imports (e.g. requires obsolete version of websockets)
* is poorly documented,
* is poorly maintained,
* and freezes when running it in the current version of Python (3.10)!

Pyppeteer's `open issues <https://github.com/pyppeteer/pyppeteer/issues>`__ now exceed 110.

As a result, I have been investigating a substitute, and found one in `Playwright
<https://playwright.dev/python/>`__. This package has none of the issues above, the core dev team apparently is the same
who wrote Puppetter (of which Pyppeteer is a port to Python), and is supported by the deep pockets of Microsoft. The
Python version is officially supported and up-to-date and we can easily use the latest stable version of Google Chrome
with it without mocking around with setting chromium_revisions.

You can upgrade to Playwright now!
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The Playwright implementation in this release of **webchanges** is extremely stable, fully tested (even on Python
3.10!), and much faster than Pyppeteer (some of my jobs are running 3x faster!). While it's probably production
quality, for the moment it is being released as an opt-in beta only.

I urge you to switch to Playwright. To do so:

Ensure that you have at least Python 3.8 (not tested in 3.7 due to testing limitations).

Install dependencies::

   pip install --upgrade webchanges[playwright]

Ensure you have an up-to-date Chrome installation::

   webchanges --install-chrome

Edit your configuration file...::

   webchanges --edit-config

...to add ``_beta_use_playwright: true`` (note the leading underline) under the ``browser`` section of ``job_defaults``,
 like this:

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
the downloaded Chromium by deleting the *directory* shown by running::

   webchanges --chromium-directory

and uninstalling the Pyppeteer package by running::

   pip uninstall pyppeteer

The Playwright implementation also determines the maximum number of jobs to run in parallel based on the amount of free
memory available, which seems to be the relevant constraint, and this will make **webchanges** faster on machines with
lots of memory and more stable on small ones.

Changed
-------
* The method ``bs4`` of filter ``html2text`` has a new ``strip`` sub-directive which is passed to BeautifulSoup, and
  its default value has changed to false to conform to BeautifulSoup's default. This gives better output in most
  cases. To restore the previous non-standard behavior, add the ``strip: true`` sub-directive to the ``html2text``
  filter of jobs.
* Pyppeteer (used for URL jobs with ``use_browser: true``) is now crashing during certain tests with Python 3.7.
  There will be no new development to fix this as the use of Pyppeteer will soon be deprecated in favor of Playwright.
  See above to start using Playwright now (highly suggested).

Added
-----
* The method ``bs4`` of filter ``html2text`` now accepts the sub-directives ``separator`` and ``strip``.
* When using the command line argument ``--test-diff``, the output can now be sent to a specific reporter by also
  specifying the ``--test-reporter`` argument. For example, if running on a machine with a web browser, you can see
  the HTML version of the last diff(s) from job 1 with ``webchanges --test-diff 1 --test-reporter browser`` on your
  local browser.
* New filter ``remove-duplicate-lines``. Contributed by `Michael Sverdlin <https://github.com/sveder>`__ upstream `here
  <https://github.com/thp/urlwatch/pull/653>`__ (with modifications).
* New filter ``csv2text``. Contributed by `Michael Sverdlin <https://github.com/sveder>`__ upstream `here
  <https://github.com/thp/urlwatch/pull/658>`__ (with modifications).
* The ``html`` report type has a new job directive ``monospace`` which sets the output to use a monospace font.
  This can be useful e.g. for tabular text extracted by the ``pdf2text`` filter.
* The ``command_run`` report type has a new environment variable ``WEBCHANGES_CHANGED_JOBS_JSON``.
* Opt-in to use Playwright for jobs with ``use_browser: true`` instead of pyppeteer (see above).

Fixed
-----
* During conversion of Markdown to HTML,
  * Code blocks were not rendered without wrapping and in monospace font;
  * Spaces immediately after ````` (code block opening) were being dropped.
* The ``email`` reporter's ``sendmail`` sub-directive was not passing the ``from`` sub-directive (when specified) to
  the ``sendmail`` executable as an ``-f`` command line argument. Contributed by
  `Jonas Witschel <https://github.com/diabonas>`__ upstream `here <https://github.com/thp/urlwatch/pull/671>`__ (with
  modifications).
* HTML characters were not being unescaped when the job name is determined from the <title> tag of the data monitored
  (if present).
* Command line argument ``--test-diff`` was only showing the last diff instead of all saved ones.
* The ``command_run`` report type was not setting variables ``count`` and ``jobs`` (always 0). Contributed by
  `Brian Rak <https://github.com/devicenull>`__ in `#23 <https://github.com/mborsetti/webchanges/issues/23>`__.

Documentation
-------------
* Updated the "recipe" for monitoring Facebook public posts.
* Improved documentation for filter ``pdf2text``.

Internals
---------
* Support for Python 3.10 (except for URL jobs with ``use_browser`` using pyppeteer since it does not yet support it;
  use Playwright instead).
* Improved speed of detection and handling of lines starting with spaces during conversion of Markdown to HTML.
* Logging (``--verbose``) now shows thread IDs to help with debugging.

Known issues
------------
* Pyppeteer (used for URL jobs with ``use_browser: true``) is now crashing during certain tests with Python 3.7.
  There will be no new development to fix this as the use of Pyppeteer will soon be deprecated in favor of Playwright.
  See above to start using Playwright now (highly suggested).
