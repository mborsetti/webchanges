.. _jobs:

====
Jobs
====
Each job contains the source of the data to be monitored (:ref:`URL <url>` or :ref:`command <command>`) and related
directives, plus directives on transformations to apply to the data (ref:`filters <filters>`) once retrieved.

The list of jobs is contained in the jobs file ``jobs.yaml``, a :ref:`YAML <yaml_syntax>` text file editable with the
command ``webchanges --edit`` or using any text editor.

**YAML tips**

YAML has lots of idiosyncrasies that make it and finicky, and new users often have issues with it.  Here are some tips
and things to look for when using YAML.  A more comprehensive syntax explanation is :ref:`here <yaml_syntax>`.

* Indentation: All indentation must be done with spaces (2 spaces is suggested); tabs are not recognized/allowed.
  Indentation is mandatory.
* Nesting: the indentation logic sometimes changes when nesting dictionaries.

.. code-block:: yaml

    filter:
      - html2text:           # notice 2 spaces before the '-'
          pad_tables: true   # notice 6 spaces before the name


* There must be a space after the ``:`` between the key name and its value. The lack of such space is often the
  reason behind "Unknown filter kind" errors with no arguments

.. code-block:: yaml

   filter:
     - re.sub: text  # This is correct

.. code-block:: yaml

   filter:
     - re.sub:text  # This is INCORRECT; space is required

* Escaping special characters: Certain characters at the beginning of the line such as a ``-``, a ``:`` followed by a
  space, a space followed by ``#``, the ``%`` sign (anywhere), all sort of brackets, and more are all considered special
  characters by YAML. Strings containing these characters or sequences need to be enclosed in quotes:

.. code-block:: yaml

   name: This is a human-readable name/label of the job  # and this is a remark
   name: "This human-readable name/label has a: colon followed by a space and a space followed by a # hash mark"
   name: "I can escape \"double\" quotes within a double quoted string which also has a colon: followed by a space"

* You can learn more about quoting special characters `here <https://www.yaml.info/learn/quote.html#flow>`__ (the
  library we use supports YAML 1.1, and our examples use "flow scalars").  URLs and XPaths are always safe and don't
  need to be enclosed in quotes.

For additional information on YAML, see the :ref:yaml_syntax and the references at the bottom of that page.

**Multiple jobs**

Multiple jobs are separated by a line containing three hyphens, i.e. ``---``.

**Naming a job**

While optional, it is recommended that each job starts with a ``name`` entry. If omitted and the data monitored is
HTML or XML, `webchanges` will automatically use the pages' title (up to 60 characters) for a name.

.. code-block:: yaml

   name: This is a human-readable name/label of the job
   url: https://example.org/


.. _url:

URL
---
This is the main job type -- it retrieves a document from a web server.

.. code-block:: yaml

   name: Example homepage
   url: https://example.org/
   ---
   name: Example page 2
   url: https://example.org/page2


Important: due to a legacy architectural choice, URLs must be **unique** to each job. If for some reason you want to
monitor the same resource multiple times, make each job's URL unique by adding # at the end of the link followed by a
unique remark (the # and everything after is discarded by a web server, but captured by `webchanges`):

.. code-block:: yaml

   name: Example homepage
   url: https://example.org/
   ---
   name: Example homepage -- again!
   url: https://example.org/#2


.. _use_browser:

JavaScript rendering
""""""""""""""""""""
If you're monitoring a website that requires for its content to be rendered with JavaScript in order to monitor the data
you are interested in, add the directive ``use_browser: true`` to the job:

.. code-block:: yaml

   name: A page with JavaScript
   url: https://example.org/
   use_browser: true

Important notes for use_browser directive
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* The optional `Pyppeteer <https://github.com/pyppeteer/pyppeteer>`__ Python package must be installed; run
  ``pip install webchanges[use_browser]`` to install it
* Additional OS-specific dependencies may be required as well (see :ref:`here <optional_packages>`);
  missing dependencies are often the cause of the ``pyppeteer.errors.BrowserError:
  Browser closed unexpectedly`` error; see `here
  <https://github.com/puppeteer/puppeteer/blob/main/docs/troubleshooting.md#chrome-headless-doesnt-launch>`__
* As this job type
  renders the page in a headless Chromium instance, it requires **massively more resources** and time than a simple
  ``url`` job; use it only on pages where omitting ``use_browser: true`` does not give the right results
* **Pro tip**: in many instances you can get the data you want to monitor from an API (URL) called by the site during
  page loading instead of using ``use_browser: true`` on a page; monitor page load with a browser's Developer's Tools
  (e.g. `Chrome DevTools  <https://developers.google.com/web/tools/chrome-devtools>`__) to see if this is the case
* The first time you run a job with ``use_browser:true``, `Pyppeteer` needs to download the `Chromium browser
  <https://www.chromium.org/getting-involved/download-chromium>`__ (~150 MiB) if it is not found on the system, and
  therefore it could take some time (and bandwidth); to avoid this, ensure that a suitable Chromium binary is
  pre-installed; one way to do this is to run ``pyppeteer-install``
* At the moment, the Chromium version used by `Pyppeteer` does not support ARM devices (e.g. Raspberry Pi) but only
  supports Linux (x86_64), macOS (x86_64) and Windows (both x86 and x64); see `this issue
  <https://github.com/pyppeteer/pyppeteer/issues/155>`__ in the `Pyppeteer` project.
* If you get ``pyppeteer.errors.NetworkError: Protocol error Runtime.callFunctionOn: Target closed.`` error, see
  :ref:`here <pyppeteer_target_closed>` for a potential solution


Required directives
"""""""""""""""""""
- ``url``: The URL to the web document to monitor

Optional directives
"""""""""""""""""""
For all ``url`` jobs:

- ``use_browser``: If true, renders the URL via a JavaScript-enabled web browser and extracts HTML after rendering
- ``use_browser``: If true, renders the URL via a JavaScript-enabled web browser and extracts HTML after rendering
- ``cookies``: Cookies to send with the request (a dict) (see :ref:`here <cookies>`). `Changed in version 3.0:` Works
  for all ``url`` jobs.
- ``headers``: Headers to send along with the request (a dict). `Changed in version 3.0:` Works for all ``url`` jobs.
- ``http_proxy``: Proxy server to use for HTTP requests (e.g. \http://username:password@proxy.com:8080). `Changed in
  version 3.0:` Works for all ``url`` jobs.
- ``https_proxy``: Proxy server to use for HTTPS requests. `Changed in version 3.0:` Works for all ``url`` jobs.
- ``timeout``: Override the default timeout, in seconds (see :ref:`here <timeout>`). `Changed in version 3.0:` Works for
  all ``url`` jobs.
- ``user_visible_url``: Use this text in reports (e.g. when watched URL is a REST API endpoint but you want to link to
  the webpage instead). `New in version 3.0.3.`
- ``note``: Information added under the header in reports. `New in version 3.2.`
- ``ignore_connection_errors``: Ignore (temporary) connection errors (true/false) (see :ref:`here <ignore_errors>`).
  `Changed in version 3.5:` Works with all ``url`` jobs.
- ``ignore_timeout_errors``: Do not report errors when the timeout is hit (true/false) (see :ref:`here
  <ignore_errors>`). `Changed in version 3.5:` Works with all ``url`` jobs.
- ``ignore_too_many_redirects``: Ignore redirect loops (true/false) (see :ref:`here <ignore_errors>`). `Changed in
  version 3.5:` Works with all ``url`` jobs.
- ``ignore_http_error_codes``: List of HTTP errors to ignore (see :ref:`here <ignore_errors>`). `Changed in version
  3.5:` Works with all ``url`` jobs.

For ``url`` jobs that do not have ``use_browser`` (or it is set to ``false``):

- ``method``: `HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__ to use
  (default: ``GET`` unless ``data``, below, is set)
- ``data``: HTTP data (defaults request method to ``POST`` and `Content-type
  <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type>`__ header to
  ``application/x-www-form-urlencoded``)
- ``no_redirects``: Disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection (true/false). `New in version 3.2.7`
- ``ssl_no_verify``: Do not verify SSL certificates (true/false) (see :ref:`here <ssl_no_verify>`)
- ``ignore_cached``: Do not use cache control (ETag/Last-Modified) values (true/false)
- ``encoding``: Override the character encoding from the server (see :ref:`here <encoding>`)

For ``url`` jobs that have ``use_browser: true``:

- ``chromium_revision``: The revision number of the Chromium browser to use (see note :ref:`here <chromium_revision>`).
  This can be different for different OSs, in which case is a list of one or more of the following keys: ``linux``,
  ``mac``, ``win32`` and ``win64``. `New in version 3.0.` `Changed in version 3.1:` Added keys for different OSs.
- ``ignore_https_errors``: Ignore HTTPs errors (true/false). `New in version 3.0.`
- ``user_data_dir``: A path to a pre-existing user directory that Chromium should be using. `New in version 3.0.`
- ``switches``: Additional command line `switch(es) for Chromium
  <https://peter.sh/experiments/chromium-command-line-switches/>`__ (list). `New in version 3.0.`
- ``wait_until``: When to consider navigation succeeded (``load``, ``domcontentloaded``, ``networkidle0``, or
  ``networkidle2``) (see
  `documentation <https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.goto>`__). `New in version
  3.0.`
- ``wait_for_navigation``: Wait until navigation lands on a URL starting with this text (e.g. due to redirects); helps
  to avoid the ``pyppeteer.errors.NetworkError: Execution context was destroyed, most likely because of a navigation``
  error. If ``wait_for`` is also used, ``wait_for_navigation`` is applied first. Cannot be used with ``block_elements``.
  `New in version 3.2.`
- ``wait_for``: Wait until a timeout in seconds (if number), JavaScript function, or a selector string or xpath
  string is matched, before getting the HTML content (see `documentation
  <https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.waitFor>`__ - but we use seconds). If
  ``wait_for_navigation`` is also used, ``wait_for`` is applied after. Cannot be used with ``block_elements``.
- ``block_elements`` (⚠ Python >= 3.7) (experimental feature): Do not request (download) specified `resource types
  <https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest/ResourceType>`__ as to
  speed up retrieval of the content (list). Only resource types `supported by Chromium
  <https://developer.chrome.com/docs/extensions/reference/webRequest/#type-ResourceType>`__ are allowed. See
  :ref:`here <pyppeteer_block_elements>`. `New in version 3.2.`
- Setting the system environment variable ``PYPPETEER_NO_PROGRESS_BAR`` to true will prevent showing a download
  progress bar if `Pyppeteer` needs to be downloaded; however, this will cause a `crash
  <https://github.com/pyppeteer/pyppeteer/pull/224>`__ in Pyppetter ≤ 0.2.25

Known issues
""""""""""""
* ``url`` jobs with ``use_browser: true`` (i.e. using `Pyppeteer`) will at times display the below error message in
  stdout (terminal console). This does not affect `webchanges` as all data is downloaded, and hopefully it will be fixed
  in the future (see `Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):

  ``Future exception was never retrieved``
  ``future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>``
  ``pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.``



.. _command:

Command
-------
This job type allows you to watch the output of arbitrary shell commands, which is useful for e.g. monitoring an FTP
uploader folder, output of scripts that query external devices (RPi GPIO), etc.

.. code-block:: yaml

   name: What is in my home directory?
   command: dir -al ~

.. _important_note_for_command_jobs:

Important note for command jobs
"""""""""""""""""""""""""""""""
When `webchanges` is run in Linux, for security purposes a ``command`` job will only run if the job file is both
owned by the same user running `webchanges` and can **only** be written by such user. To change the ownership and the
access permissions of the file (i.e. remove write permission for the group and all other users), run the following
commands:

.. code-block:: bash

   cd ~/.config/webchanges  # could be different
   sudo chown $USER:$(id -g -n) *.yaml
   sudo chmod go-w *.yaml

* ``sudo`` may or may not be required.
* Replace ``$USER`` with the username that runs `webchanges` if different than the use you're logged in when making the
  above changes, similarly with ``$(id -g -n)`` for the group.

Required directives
"""""""""""""""""""
- ``command``: The shell command to execute

Optional directives
"""""""""""""""""""
- none

Optional directives (for all job types)
---------------------------------------
These optional directives apply to all job types:

- ``name``: Human-readable name/label of the job (if not specified and the job is ``url`` and the content is HTML or
  XML, the title (up to 60 characters) will be used; otherwise the URL or command). `Changed in version 3.0:`
  Added auto-detect from HTML or XML.
- ``max_tries``: Number of consecutive times the job has to fail before reporting an error (default: 1); see
  :ref:`below <max_tries>`
- ``diff_tool``: Command to an external tool for generating diff text. See example usage :ref:`here <word_based_differ>`
- ``compared_versions``: Number of :ref:`versions to compare <compared_versions>` for similarity
- ``filter``: :ref:`filters` (if any) to apply to the output (can be tested with ``--test``)
- ``diff_filter``: :ref:`diff_filters` (if any) applied to the diff result (can be tested with ``--test-diff``)
- ``additions_only``: Filters unified diff output to keep only :ref:`addition lines <additions_only>`
- ``deletions_only``: Filters unified diff output to keep only :ref:`deleted lines <deletions_only>`
- ``is_markdown``: Lets html reporter know that data is markdown and should be reconstructed (default: false, but could
  be set by a filter such as ``html2text``)

.. _max_tries:

max_tries
"""""""""
Due to legacy naming, this directive doesn't do what intuition would tell you it should do, rather, it tells
`webchanges` **not** to report a job error until the job has failed for the number of consecutive times of
``max_tries``. Specifically, when a job fails, `webchanges` increases an internal counter, and will report an error
only when this counter reaches or exceeds the number of ``max_tries`` (default: 1, i.e. immediately). The internal
counter is reset to 0 when the job succeeds.

For example, if you set a job with ``max_tries: 12`` and run `webchanges` every 5 minutes, you will only get notified
if the job has failed every single time during the span of one hour (5 minutes * 12).

Setting default directives
""""""""""""""""""""""""""
See :ref:`job_defaults` for how to set default directives for all jobs
