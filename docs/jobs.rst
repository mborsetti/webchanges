.. _jobs:

====
Jobs
====

Jobs are made of the sources that `webchanges` can monitor and the instructions on transformations (filters) to apply
to the data once retrieved.

The list of jobs to run are contained in the configuration file ``jobs.yaml``, a text file editable using any text
editor or with the command ``webchanges --edit``.

While optional, it is recommended that each job starts with a ``name`` entry.  If omitted and the data montiroed is
HTML, `webchanges` will automatically use the pages' title for a name.

.. code-block:: yaml

   name: This is a human-readable name/label of the job
   url: https://example.org/


**About YAML special characters**

Certain characters have significance in the YAML format (e.g. certain special characters at the beginning of the line
or additionally a ``:`` followed by a space or a space followed by ``#``, all sort of brackets, and more) and therefore
need to be enclosed in quotes like so:

.. code-block:: yaml

   name: This is a human-readable name/label of the job  # and this is a remark
   name: "This human-readable name/label has a: colon followed by a space and space # followed by hashmark"
   name: "I can escape \"double\" quotes within a double quoted string which also has a colon: followed by a space"

You can learn more about quoting  `here <https://www.yaml.info/learn/quote.html#flow>`__ (note: the library we use
supports YAML 1.1, and our examples use "flow scalars").  URLs are always safe and don't need to be enclosed in quotes.


URL
---

This is the main job type -- it retrieves a document from a web server. Multiple jobs are separated by a line
containing three hyphens, i.e. ``---``.

.. code-block:: yaml

   name: Example homepage
   url: https://example.org/
   ---
   name: Example page 2
   url: https://example.org/page2


Important: due to an early architectural choice, URLs must be unique to each job. If for some reason you want to monitor
the same address twice, make sure each job has a unique URL; you can easily accomplish this by adding a # at the end of
the link followed by a unique remark (the # and everything after is discarded by a web server, but captured by
`webchanges`):

.. code-block:: yaml

   name: Example homepage
   url: https://example.org/
   ---
   name: Example homepage -- again!
   url: https://example.org/#2


.. _use_browser:

The use_browser directive
"""""""""""""""""""""""""

If you're monitoring a website, and you need to render its content with JavaScript in order to monitor it, add
the directive ``use_browser: true`` to the job configuration:

.. code-block:: yaml

   name: A page with JavaScript
   url: https://example.org/
   use_browser: true

**IMPORTANT NOTES** for use_browser
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* The optional `Pyppeteer <https://github.com/pyppeteer/pyppeteer>`__ Python package must be installed; run
  ``pip install webchanges[use_browser]`` to install it.
* Additional OS-dependent dependencies may be required as well;
  missing dependencies are often the cause of ``pyppeteer.errors.BrowserError:
  Browser closed unexpectedly``. See `here
  <https://github.com/puppeteer/puppeteer/blob/main/docs/troubleshooting.md#chrome-headless-doesnt-launch>`__).
* As this job type
  renders the page in a headless Chromium instance, it requires **massively more resources** and time than a simple
  ``url`` job. Use it only on pages where omitting ``use_browser: true`` does not give the right results.
* **Pro tip**: in many instances instead of using ``use_browser: true`` on a page you can monitor the output of an API
  (URL) called by the site during page loading, an API which contains the information you're after. Monitor page load
  with a browser's Developer's Tools (e.g. `Chrome DevTools
  <https://developers.google.com/web/tools/chrome-devtools>`__) to see if this is the case.
* The first time you run a job with ``use_browser:true`` it could take some time (and bandwidth) because
  ``pyppeteer`` needs to download the `Chromium browser
  <https://www.chromium.org/getting-involved/download-chromium>`__ (~150 MiB) if it is not found on the system.
  If you don't like this behavior, ensure that a suitable Chromium binary is pre-installed; one way to do this is to run
  ``pyppeteer-install``.
* At the moment, the Chromium version used by ``pyppeteer`` does not support ARM devices (e.g. Raspberry Pi) but only
  supports Linux (x86_64), macOS (x86_64) and Windows (both x86 and x64). See `this issue
  <https://github.com/pyppeteer/pyppeteer/issues/155>`__ in the Pyppeteer issue tracker.

Required directives
"""""""""""""""""""

- ``url``: The URL to the web document to monitor

Optional directives
"""""""""""""""""""

- ``use_browser``: Render the the URL via a JavaScript-enabled web browser and extract the rendered HTML

For all ``url`` jobs:

- ``cookies``: Cookies to send with the request (a dict) (see :ref:`here <cookies>`)
- ``headers``: Headers to send along with the request (a dict)
- ``http_proxy``: Proxy server to use for HTTP requests (e.g. "http://username:password@proxy.com:8080")
- ``https_proxy``: Proxy server to use for HTTPS requests
- ``timeout``: Override the default timeout, in seconds (see :ref:`here <timeout>`)

For ``url`` jobs that do not have ``use_browser`` (or it is set to ``false``):

- ``method``: `HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__ to use
  (default: ``GET``)
- ``data``: HTTP data (defaults request method to ``POST`` and `Content-type
  <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type>`__ header to
  ``application/x-www-form-urlencoded``)
- ``ssl_no_verify``: Do not verify SSL certificates (true/false) (see :ref:`here <ssl_no_verify>`)
- ``ignore_cached``: Do not use cache control (ETag/Last-Modified) values (true/false)
- ``encoding``: Override the character encoding from the server (see :ref:`here <encoding>`)
- ``ignore_connection_errors``: Ignore (temporary) connection errors (true/false) (see :ref:`here <ignore_errors>`)
- ``ignore_http_error_codes``: List of HTTP errors to ignore (see :ref:`here <ignore_errors>`)
- ``ignore_timeout_errors``: Do not report errors when the timeout is hit (true/false)
- ``ignore_too_many_redirects``: Ignore redirect loops (true/false) (see :ref:`here <ignore_errors>`)

For ``url`` jobs that have ``use_browser: true``:

- ``chromium_revision``: the revision number of the Chromium browser to use (see note :ref:`here <chromium_revision>`)
- ``ignore_https_errors``: Ignore HTTPs errors (true/false)
- ``user_data_dir``: a path to a pre-existing user directory that Chromium should be using
- ``switches``: additional command line switch(es) for Chromium (a dict)
- ``wait_until``: when to consider navigation succeeded (``load``, ``domcontentloaded``, ``networkidle0``, or
  ``networkidle2``) (see
  `documentation <https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.goto>`__)


Command
-------

This job type allows you to watch the output of arbitrary shell commands, which is useful for e.g. monitoring an FTP
uploader folder, output of scripts that query external devices (RPi GPIO), etc...

.. code-block:: yaml

   name: What is in my home directory?
   command: dir -al ~

Required directives
"""""""""""""""""""

- ``command``: The shell command to execute

Optional directives
"""""""""""""""""""

- none

Optional directives (for all job types)
---------------------------------------
These optional directives apply to all job types:

- ``name``: Human-readable name/label of the job; if content is HTML, defaults to tile
- ``max_tries``: Maximum number of times to run the job to retrieve the resource (default: 1)
- ``diff_tool``: Command to a custom tool for generating diff text
- ``compared_versions``: Number of versions to compare for similarity (see :ref:`here <compared_versions>`)
- ``filter``: :ref:`filters` (if any) to apply to the output (can be tested with ``--test``)
- ``diff_filter``: :ref:`diff_filters` (if any) applied to the diff result (can be tested with ``--test-diff``)
- ``additions_only``: Filters unified diff output to keep only addition lines (see :ref:`here <additions_only>`)
- ``deletions_only``: Filters unified diff output to keep only deleted lines (see :ref:`here <deletions_only>`)

Setting default directives
""""""""""""""""""""""""""

See :ref:`job_defaults` for how to configure directives for all jobs at once.
