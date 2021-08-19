.. _jobs:

****
Jobs
****
Each job contains the source of the data to be monitored (:ref:`URL <url>` or :ref:`command <command>`) and related
directives, plus eventual directives on transformations (:ref:`filters <filters>`) to apply to the data once retrieved.

The list of jobs is contained in the jobs file ``jobs.yaml``, a :ref:`YAML <yaml_syntax>` text file editable with the
command ``webchanges --edit`` or using any text editor.

**YAML tips**

The YAML syntax has lots of idiosyncrasies that make it and finicky, and new users often have issues with it. Here are
some tips and things to look for when using YAML. A more comprehensive syntax explanation is :ref:`here <yaml_syntax>`.

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
  library we use supports YAML 1.1, and our examples use "flow scalars"). URLs and XPaths are always safe and don't
  need to be enclosed in quotes.

For additional information on YAML, see the :ref:yaml_syntax and the references at the bottom of that page.

**Multiple jobs**

Multiple jobs are separated by a line containing three hyphens, i.e. ``---``.

**Naming a job**

While optional, it is recommended that each job starts with a ``name`` entry. If omitted and the data monitored is
HTML or XML, :program:`webchanges` will automatically use the pages' title (up to 60 characters) for a name.

.. code-block:: yaml

   name: This is a human-readable name/label of the job
   url: https://example.org/


.. _url:

URL
===
This is the main job type. It retrieves a document from a web server (``https://`` and ``http://``), an ftp server
(``ftp://``), or a local file (``file://``).

.. code-block:: yaml

   name: Example homepage
   url: https://www.example.org/
   ---
   name: Example page 2
   url: https://www.example.org/page2
   ---
   name: Example a local file
   url: file://syslog
   ---
   name: Example of an FTP file (username anonymous if not specified)
   url: ftp://username:password@ftp.example.com/file.txt


.. caution:: Due to a legacy architectural choice, URLs must be **unique** to each job. If for some reason you want to
   monitor the same resource multiple times, make each job's URL unique by e.g. adding # at the end of the link
   followed by a unique remark (the # and everything after is discarded by a web server, but captured by
   :program:`webchanges`):

   .. code-block:: yaml

      name: Example homepage
      url: https://example.org/
      ---
      name: Example homepage -- again!
      url: https://example.org/#2

.. versionchanged:: 3.6
   Added support for ``ftp://`` URIs.


.. _use_browser:

JavaScript rendering (``use_browser: true``)
--------------------------------------------
If you're monitoring a website that requires for its content to be rendered with JavaScript in order to monitor the data
you are interested in, add the directive ``use_browser: true`` to the job:

.. code-block:: yaml

   name: A page with JavaScript
   url: https://example.org/
   use_browser: true

.. warning::
   As this job type renders the page in a headless Chromium instance, it requires **massively more resources** and
   time than a simple ``url`` job; use it only on pages where omitting ``use_browser: true`` does not give the right
   results.

.. tip::
   In many instances you can get the data you want to monitor from a REST API (URL) called by the site during its
   page loading. Monitor the page load with a browser's Developer's Tools (e.g. `Chrome DevTools
   <https://developers.google.com/web/tools/chrome-devtools>`__) to see if this is the case.

.. important::
   * The optional `Pyppeteer <https://github.com/pyppeteer/pyppeteer>`__ Python package must be installed; run
     ``pip install webchanges[use_browser]`` to install it.
   * Additional OS-specific dependencies may be required as well (see :ref:`here <optional_packages>`);
     missing dependencies are often the cause of the ``pyppeteer.errors.BrowserError:
     Browser closed unexpectedly`` error; see `here
     <https://github.com/puppeteer/puppeteer/blob/main/docs/troubleshooting.md#chrome-headless-doesnt-launch>`__.
   * The first time you run a job with ``use_browser:true``, :program:`Pyppeteer` needs to download the `Chromium
     browser <https://www.chromium.org/getting-involved/download-chromium>`__ (~150 MiB) if it is not found on the
     system, and therefore it could take some time (and bandwidth).
   * If you receive ``pyppeteer.errors.NetworkError: Protocol error Runtime.callFunctionOn: Target closed.`` error, see
     :ref:`here <pyppeteer_target_closed>` for a potential solution.

.. note::
   * At the moment, the Chromium project does not provide builds for ARM devices (e.g. Raspberry Pi) but only for
     Linux (x86_64), macOS (x86_64) and Windows (both x86 and x64); see `this issue
     <https://github.com/pyppeteer/pyppeteer/issues/155>`__.


Required directives
-------------------
url
^^^
The URI of the resource to monitor.  ``https://``, ``http://``, ``ftp://`` and ``file://`` are supported.


Optional directives - all ``url`` jobs
--------------------------------------
The following optional directives are available for all ``url`` jobs:


use_browser
^^^^^^^^^^^
Whether to use a Chromium web browser (true/false). Defaults to false.

If true, renders the URL via a JavaScript-enabled web browser and extracts HTML after rendering (see
:ref:`above <use_browser>`).

cookies
^^^^^^^
Cookies to send with the request (a dict).

See examples :ref:`here <cookies>`.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.


headers
^^^^^^^
Headers to send along with the request (a dict).

See examples :ref:`here <headers>`.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

http_proxy
^^^^^^^^^^
Proxy server to use for HTTP requests (a string).

E.g. \http://username:password@proxy.com:8080.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

https_proxy
^^^^^^^^^^^
Proxy server to use for HTTPS (i.e. secure) requests (a string).

E.g. \https://username:password@proxy.com:8080.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

timeout
^^^^^^^
Override the default timeout, in seconds (a number).

See example :ref:`here <timeout>`.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

method
^^^^^^
`HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__ to use (one of ``GET``,
``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``).

Defaults to ``GET``, unless the ``data`` directive, below, is set.

.. error::

   Setting a method other than ``GET`` with `use_browser: true` will result in any 3xx redirections received by the
   website to be ignored and the job hanging forever. This is due to bug `#937719
   <https://bugs.chromium.org/p/chromium/issues/detail?id=937719>`__ in Chromium. Please take the time to add a star to
   the bug report so it will be prioritized for a faster fix.

.. versionchanged:: 3.8
   Works for all url jobs, including those with use_browser: true.

data
^^^^
Data to send with a ``POST`` `HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__ (a
dict or a string).

This directive also sets the ``method`` directive  to ``POST`` and, if no `Content-type
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type>`__ header is otherwise specified, such header
to ``application/x-www-form-urlencoded``.

See example :ref:`here <post>`.

.. versionchanged:: 3.8
   Works for all url jobs, including those with use_browser: true.

note
^^^^
Informational note added under the header in reports (a string).

.. versionadded:: 3.2

ignore_connection_errors
^^^^^^^^^^^^^^^^^^^^^^^^
Ignore (temporary) connection errors (true/false). Defaults to false.

See more :ref:`here <ignore_errors>`.

.. versionchanged:: 3.5
   Works for all url jobs, including those with use_browser: true.

ignore_timeout_errors
^^^^^^^^^^^^^^^^^^^^^
Do not report errors when the timeout is hit (true/false). Defaults to false.

See more "ref:`here <ignore_errors>`.

.. versionchanged:: 3.5
   Works for all url jobs, including those with use_browser: true.

ignore_too_many_redirects
^^^^^^^^^^^^^^^^^^^^^^^^^
Ignore redirect loops (true/false). Defaults to false.

See more `here <ignore_errors>`.

.. versionchanged:: 3.5
   Works for all url jobs, including those with use_browser: true.

ignore_http_error_codes
^^^^^^^^^^^^^^^^^^^^^^^
List of HTTP errors to ignore (a list).  Also accepts 2xx, 3xx, 4xx, and 5xx for the entire class of response status
codes.

See more :ref:`here <ignore_errors>`.

.. versionchanged:: 3.5
   Works for all url jobs, including those with use_browser: true.


Optional directives - without ``use_browser: true``
---------------------------------------------------
These directives are available only for ``url`` without ``use_browser: true``:

no_redirects
^^^^^^^^^^^^
Disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection (true/false). Defaults to false.

.. versionadded:: 3.2.7

ssl_no_verify
^^^^^^^^^^^^^
Do not verify SSL certificates (true/false).

See more :ref:`here <ssl_no_verify>`.

ignore_cached
^^^^^^^^^^^^^
Do not use cache control values (ETag/Last-Modified) (true/false). Defaults to false.

encoding
^^^^^^^^
Character encoding to use, overriding the character encoding from the server (a string).

See more :ref:`here <encoding>`.

Optional directives - with ``use_browser: true``
---------------------------------------------------
These directives are available only for ``url`` jobs with ``use_browser: true`` (i.e. using :program:`Pyppeteer`):

chromium_revision
^^^^^^^^^^^^^^^^^
The revision number of the Chromium browser to use (a string, number or dict).

This can be different for different OSs, in which case is a dict with of one or more of the following keys: ``linux``,
``mac``, ``win32`` and ``win64``.

See note :ref:`here <pyppeteer_chromium_revision>`.

.. versionadded:: 3.0
.. versionchanged:: 3.1
   Added keys for different OSs.

ignore_https_errors
^^^^^^^^^^^^^^^^^^^
Ignore HTTPs errors (true/false). Defaults to false.

.. versionadded:: 3.0

user_data_dir
^^^^^^^^^^^^^^^^^^^
A path to a pre-existing user directory that Chromium should be using (a string).

.. versionadded:: 3.0

switches
^^^^^^^^^^^^^^^^^^^
Additional command line `switch(es) for Chromium
<https://peter.sh/experiments/chromium-command-line-switches/>`__ (a list).

.. versionadded:: 3.0

wait_until
^^^^^^^^^^^^^^^^^^^
The value of when to consider navigation succeeded (a string).

Must be one of ``load``, ``domcontentloaded``, ``networkidle0``, or ``networkidle2``.

See `documentation <https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.goto>`__.

.. versionadded:: 3.0

wait_for_navigation
^^^^^^^^^^^^^^^^^^^
Wait until navigation lands on a URL starting with this text (a string).

Useful to avoid capturing intermediate to redirects.

If ``wait_for`` is also used, ``wait_for_navigation`` is applied first.

Cannot be used with ``block_elements``.

Also helps to avoid the
``pyppeteer.errors.NetworkError: Execution context was destroyed, most likely because of a navigation`` error.

.. versionadded:: 3.2

wait_for
^^^^^^^^^^^^^^^^^^^
Wait until a timeout in seconds (if number), JavaScript function, or a selector string or xpath string is matched,
before getting the HTML content (a number or string).

See `documentation
<https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.waitFor>`__ - but we use seconds).

If ``wait_for_navigation`` is also used, ``wait_for`` is applied after.

Cannot be used with ``block_elements``.

.. versionadded:: 3.2

block_elements
^^^^^^^^^^^^^^^^^^^
⚠ experimental feature

Do not request (download) specified `resource types
<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest/ResourceType>`__ (a list of
strings).

Only resource types `supported by Chromium
<https://developer.chrome.com/docs/extensions/reference/webRequest/#type-ResourceType>`__ are allowed.

In most instances, it speeds up retrieval of the content.

See :ref:`here <pyppeteer_block_elements>`.

.. versionadded:: 3.2


System environment values - ``use_browser: true``
-------------------------------------------------

PYPPETEER_NO_PROGRESS_BAR
^^^^^^^^^^^^^^^^^^^^^^^^^
When set to true, it will prevent showing a download progress bar if :program:`Pyppeteer` needs to download the Chromium
executable.

.. warning::
   Setting ``PYPPETEER_NO_PROGRESS_BAR`` to true with Pyppetter ≤ 0.2.25 will cause it to `crash
   <https://github.com/pyppeteer/pyppeteer/pull/224>`__.


Known issues - ``use_browser: true``
-------------------------------------------------
``url`` jobs with ``use_browser: true`` will at times display the below error message in stdout (terminal console)::

   Future exception was never retrieved
   future: <Future finished exception=NetworkError('Protocol error Target.sendMessageToTarget: Target closed.')>
   pyppeteer.errors.NetworkError: Protocol error Target.sendMessageToTarget: Target closed.

The error does not affect :program:`webchanges` at all, and hopefully it will be fixed in the future (see
`Pyppeteer issue #225 <https://github.com/pyppeteer/pyppeteer/issues/225>`__):


.. _command:

Command
=======
This job type allows you to watch the output of arbitrary shell commands. This could be useful for monitoring files
in a folder, output of scripts that query external devices (RPi GPIO), and many other applications.

.. code-block:: yaml

   name: What is in my home directory?
   command: dir -al ~

.. _important_note_for_command_jobs:

.. important:: When :program:`webchanges` is run in Linux, for security purposes a ``command`` job or a job with
   ``diff_tool`` will only run if the job file is both owned by the same user running :program:`webchanges` and
   can **only** be written by such user. To change the ownership and the access permissions of the file (i.e. remove
   write permission for the group and all other users), run the following commands:

   .. code-block:: bash

      cd ~/.config/webchanges  # could be different
      sudo chown $USER:$(id -g -n) *.yaml
      sudo chmod go-w *.yaml

   * ``sudo`` may or may not be required.
   * Replace ``$USER`` with the username that runs :program:`webchanges` if different than the use you're logged in when
     making the above changes, similarly with ``$(id -g -n)`` for the group.

Required directives
-------------------
command
^^^^^^^
The shell command to execute.

Optional directives (for all job types)
=======================================
These optional directives apply to all job types:

name
----
Human-readable name/label of the job used in reports (a string).

If this directive is not specified, the label used in reports will either be the ``url`` or the ``command`` itself or,
for ``url`` jobs retrieving HTML or XML data, up to 60 character of the contents of the <title> field if one is found.

.. versionchanged:: 3.0
   Added auto-detect <title> tag in HTML or XML.

user_visible_url
^^^^^^^^^^^^^^^^
URL or text to use in reports instead of contents of ``url`` or ``command`` (a string).

Useful e.g. when a watched URL is a REST API endpoint or you are using a custom script but you want a link to the
webpage on your report.

.. versionadded:: 3.0.3

.. versionchanged:: 3.8
   Added support for ``command`` jobs; previously worked only with ``url`` jobs.


max_tries
---------
Number of consecutive times the job has to fail before reporting an error (an integer). Defaults to 1.

Due to legacy naming, this directive doesn't do what intuition would tell you it should do, rather, it tells
:program:`webchanges` **not** to report a job error until the job has failed for the number of consecutive times of
``max_tries``.

Specifically, when a job fails for `any` reason, :program:`webchanges` increases an internal counter;
it will report an error only when this counter reaches or exceeds the number of ``max_tries`` (default: 1, i.e.
at the first error encountered). The internal counter is reset to 0 when the job succeeds.

For example, if you set a job with ``max_tries: 12`` and run :program:`webchanges` every 5 minutes, you will only get
notified if the job has failed every single time during the span of one hour (5 minutes * 12).

filter
------
Filter(s) to apply to the data retrieved (a list of dicts).

See :ref:`here <filters>`.

Can be tested with ``--test``.

diff_tool
---------
Command to an external tool for generating diff text (a string).

Please see warning :ref:`above <important_note_for_command_jobs>` for file security required to run jobs with this
directive in Linux.

See example usage :ref:`here <word_based_differ>`.

.. versionchanged:: 3.0.1
   * Reports now show date/time of diffs generated using ``diff_tool``.
   * Output from ``diff_tool: wdiff`` is colorized in html reports.

diff_filter
-----------
Filter(s) to be applied to the diff result (a list of dicts).

See :ref:`here <diff_filters>`.

Can be tested with ``--test-diff``.

additions_only
--------------
Filter the unified diff output to keep only addition lines.

See :ref:`here <additions_only>`.

.. versionadded:: 3.0

deletions_only
--------------
Filter the unified diff output to keep only deleted lines.

See :ref:`here <deletions_only>`.

.. versionadded:: 3.0

is_markdown
-----------
Lets html reporter know that data is markdown and should be reconstructed. Defaults to false unless set by a filter
such as ``html2text``.


Setting default directives
==========================
See :ref:`here <job_defaults>` for how to set default directives for all jobs.
