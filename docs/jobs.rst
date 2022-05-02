.. _jobs:

****
Jobs
****
Each job contains the pointer to the source of the data to be monitored (:ref:`URL <url>` or :ref:`command <command>`)
and related directives, plus eventual directives on transformations (:ref:`filters <filters>`) to apply to the data
(and/or diff) once retrieved.

The list of jobs is contained in the jobs file ``jobs.yaml``, a :ref:`YAML <yaml_syntax>` text file editable with the
command ``webchanges --edit`` or using any text editor.

**YAML tips**

The YAML syntax has lots of idiosyncrasies that make it finicky, and new users often have issues with it. Below are
some tips and things to look for when using YAML, but please also see a more comprehensive introduction to
YAML :ref:`here <yaml_syntax>`.

* Indentation: All indentation must be done with spaces (2 spaces is suggested); tabs are not recognized/allowed.
  Indentation is mandatory.
* Nesting: the indentation logic sometimes changes when nesting dictionaries.

.. code-block:: yaml

    filter:
      - html2text:           # notice 2 spaces before the '-'
          pad_tables: true   # notice 6 spaces before the name


* There must be a space after the ``:`` between the key name and its value. The lack of such space is often the
  reason behind "Unknown filter kind" errors with no arguments.

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

For additional information on YAML, see the :ref:`yaml_syntax` page and the references at the bottom of that page.

**Multiple jobs**

Multiple jobs are separated by a line containing three hyphens, i.e. ``---``.

**Naming a job**

While optional, it is recommended that each job starts with a ``name`` entry. If omitted and the data monitored is
HTML or XML, :program:`webchanges` will automatically use the first 60 characters of the document's title if present for
a name.

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
   As this job type renders the page in a headless Google Chrome instance, it requires **significantly more resources**
   and time than a simple ``url`` job; use it only for resources where omitting ``use_browser: true`` does not
   give the right results and when you can't find alternate sources (e.g. an API).

.. tip::
   In many instances you can get the data you want to monitor from a REST API (URL) called by the site during its
   page loading. Monitor the page load with a browser's Developer's Tools (e.g. `Chrome DevTools
   <https://developers.google.com/web/tools/chrome-devtools>`__) to see if this is the case.

.. important::
   * The optional `Playwright <https://playwright.dev/python/>`__ Python package must be installed; run
     ``pip install webchanges[use_browser]`` to install it.
   * The first time you run a job with ``use_browser:true``, if the latest version of Google Chrome is not found,
     :program:`Playwright` will download it (~350 MiB). This it could take some time (and bandwidth). You can
     pre-install the latest version of Chrome at any time with ``webchanges --install-chrome``.

.. versionchanged:: 3.0
   JavaScript rendering is done using the ``use_browser: true`` directive instead of replacing the ``url`` directive
   with ``navigate``, which is now deprecated.

.. versionchanged:: 3.10
   Using Playwright and Google Chrome instead of Pyppeteer and Chromium.


Required directives
-------------------
url
^^^
The URI of the resource to monitor. ``https://``, ``http://``, ``ftp://`` and ``file://`` are supported.


Optional directives (all ``url`` jobs)
--------------------------------------
The following optional directives are available for all ``url`` jobs:


use_browser
^^^^^^^^^^^
Whether to use a Chrome web browser (true/false). Defaults to false.

If true, it renders the URL via a JavaScript-enabled web browser and extracts the HTML after rendering (see
:ref:`above <use_browser>` for important information).

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

Note that with ``browser: true`` a ``Referer`` header specified here may be replaced by the ``referer`` directive.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

http_proxy
^^^^^^^^^^
Proxy server to use for HTTP requests (a string). If unspecified or null/false, the system environment variable
``HTTP_PROXY``, if defined, will be used.

E.g. ``\http://username:password@proxy.com:8080``.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

https_proxy
^^^^^^^^^^^
Proxy server to use for HTTPS (i.e. secure) requests (a string). If unspecified or null/false, the system environment
variable ``HTTPS_PROXY``, if defined, will be used.

E.g. ``\https://username:password@proxy.com:8080``.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

timeout
^^^^^^^
Override the default timeout, in seconds (a number). The default is 60 seconds for URL jobs unless they have the
directive ```use_browser: true``, in which case it's 90 seconds.  If set to 0, timeout is disabled.

See example :ref:`here <timeout>`.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

method
^^^^^^
`HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__ to use (a string).

Must be one of ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``. Defaults to ``GET``
unless the ``data`` directive, below, is set when it defaults to ``POST``.

.. error::

   Setting a method other than ``GET`` with ``use_browser: true`` may result in any 3xx redirections received by the
   website to be ignored and the job hanging until it times out. This is due to bug `#937719
   <https://bugs.chromium.org/p/chromium/issues/detail?id=937719>`__ in Chromium. Please take the time to add a star to
   the bug report so it will be prioritized for a faster fix.

.. versionchanged:: 3.8
   Works for all url jobs, including those with ``use_browser: true``.

data
^^^^
Data to send with an `HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__ like ``POST``
(a dict or string).

When this directive is specified:

* If no ``method`` directive is specified, it is set to ``POST``.
* If no `Content-type
  <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type>`__ ``header`` is specified, such header is
  set to ``application/x-www-form-urlencoded``.

See example :ref:`here <post>`.

.. versionchanged:: 3.8
   Works for all url jobs, including those with ``use_browser: true``.

note
^^^^
Informational note added under the header in reports (a string).

.. versionadded:: 3.2


.. _ignore_connection_errors:

ignore_connection_errors
^^^^^^^^^^^^^^^^^^^^^^^^
Ignore (temporary) connection errors (true/false). Defaults to false.

See more :ref:`here <ignoring_http_connection_errors>`.

.. versionchanged:: 3.5
   Works for all url jobs, including those with ``use_browser: true``.


.. _ignore_timeout_errors:

ignore_timeout_errors
^^^^^^^^^^^^^^^^^^^^^
Ignore error if caused by a timeout (true/false). Defaults to false.

See more :ref:`here <ignoring_http_connection_errors>`.

.. versionchanged:: 3.5
   Works for all url jobs, including those with ``use_browser: true``.


.. _ignore_too_many_redirects:

ignore_too_many_redirects
^^^^^^^^^^^^^^^^^^^^^^^^^
Ignore error if caused by a redirect loop (true/false). Defaults to false.

See more :ref:`here <ignoring_http_connection_errors>`.

.. versionchanged:: 3.5
   Works for all url jobs, including those with ``use_browser: true``.


.. _ignore_http_error_codes:

ignore_http_error_codes
^^^^^^^^^^^^^^^^^^^^^^^
Ignore error if a specified `HTTP response status code <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status>`__ is
received (an integer, string, or list).

Also accepts ``3xx``, ``4xx``, and ``5xx`` as values to denote an entire class of response status codes. For example,
``4xx`` will suppress any error from 400 to 499 inclusive, i.e. all client error response status codes.

See more :ref:`here <ignoring_http_connection_errors>`.

.. versionchanged:: 3.5
   Works for all url jobs, including those with ``use_browser: true``.


.. _ignore_cached:

ignore_cached
^^^^^^^^^^^^^
Do not use cache control values (ETag/Last-Modified) (true/false). Defaults to false.

.. versionchanged:: 3.10
   Works for all url jobs, including those with ``use_browser: true``.



Optional directives (without ``use_browser: true``)
--------------------------------------------------------
The following directives are available only for ``url`` jobs without ``use_browser: true``:


.. _no_redirects:

no_redirects
^^^^^^^^^^^^
Disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD redirection (true/false). Defaults to false.

.. versionadded:: 3.2.7


.. _ssl_no_verify:

ssl_no_verify
^^^^^^^^^^^^^
Do not verify SSL certificates (true/false).

See more :ref:`here <ignoring_tls_ssl_errors>`.


.. _ignore_dh_key_too_small:

ignore_dh_key_too_small
^^^^^^^^^^^^^^^^^^^^^^^
Enable insecure workaround for servers using a weak (smaller than 2048-bit) Diffie-Hellman (true/false). Defaults to
false.

A weak key can allow a man-in-the-middle attack with through the `Logjam Attack <https://weakdh.org/>`__ against the TLS
protocol and therefore generates an error. This workaround attempts the use of a potentially weaker cipher, one that
doesn't rely on a DH key and therefore doesn't trigger the error.

Set it as a last resort if you're getting a ``ssl.SSLError: [SSL: DH_KEY_TOO_SMALL] dh key too small (_ssl.c:1129)``
error and can't get the anyone to fix the security vulnerability on the server.

.. versionadded:: 3.9.2


.. _encoding:

encoding
^^^^^^^^
Override the character encoding from the server or determined programmatically (a string).

See more :ref:`here <overriding_content_encoding>`.



Optional directives (only with ``use_browser: true``)
-----------------------------------------------------
The following directives are available only for ``url`` jobs with ``use_browser: true`` (i.e. using :program:`Chrome`):



.. ignore_default_args:

ignore_default_args
^^^^^^^^^^^^^^^^^^^
If true, Playwright does not pass its own configurations args to Google Chrome and only uses the ones from ``switches``
(args in Playwright-speak); if a list is given, then it filters out the given default arguments (true/false or list).
Defaults to false.

Dangerous option; use with care. However, the following settings at times improves things:

.. code-block: yaml

  ignore_default_args:
    - --enable-automation
    - --disable-extensions

.. versionadded:: 3.10



.. _ignore_https_errors:

ignore_https_errors
^^^^^^^^^^^^^^^^^^^
Ignore HTTPS errors (true/false). Defaults to false.

.. versionadded:: 3.0


.. _switches:

switches
^^^^^^^^^^^^^^^^^^^
Additional command line `switch(es) <https://peter.sh/experiments/chromium-command-line-switches/>`__  to pass to
Google Chrome, which is a derivative of Chromium (a list). These are called args in Playwright.

.. versionadded:: 3.0


.. _user_data_dir:

user_data_dir
^^^^^^^^^^^^^^^^^^^
A path to a pre-existing user directory (containing, e.g., cookies etc.) that Chrome should be using (a string).

.. versionadded:: 3.0


.. _wait_for_function:

wait_for_function
^^^^^^^^^^^^^^^^^
Waits for a JavaScript string to be evaluated in the browser context to return a truthy value (a string or dict).

If the string (or the string in the ``expression`` key of the dict) looks like a function declaration, it is interpreted
as a function. Otherwise, it is evaluated as an expression.

Additional options can be passed when a dict is used: see `here
<https://playwright.dev/python/docs/api/class-page#page-wait-for-function>`__.

If ``wait_for_url`` and/or ``wait_for_selector`` is also used, ``wait_for_function`` is applied after.

.. versionadded:: 3.10

.. versionchanged:: 3.10
   Replaces ``wait_for`` with a JavaScript function.


.. _wait_for_selector:

wait_for_selector
^^^^^^^^^^^^^^^^^
Waits for the element specified by selector string to become visible (a string or dict).

This happens when for the element to have non-empty bounding box and no visibility:hidden. Note that an element without
any content or with display:none has an empty bounding box and is not considered visible.

Selectors supported include text, css, layout, XPath, React and Vue, as well as the ``:has-text()``, ``:text()``,
``:has()`` and ``:nth-match()`` pseudo classes. More information on working with selectors is `here
<https://playwright.dev/python/docs/selectors>`__.

Additional options (especially what state to wait for, which could be one of ``attached``, ``detached`` and ``hidden``
in addition to the default ``visible``) can be passed by using a dict. See `here
<https://playwright.dev/python/docs/api/class-page#page-wait-for-selector>`__ for all the arguments and additional
details.

If ``wait_for_url`` is also used, ``wait_for_selector`` is applied after.

.. versionadded:: 3.10

.. versionchanged:: 3.10
   Replaces ``wait_for`` with a selector or xpath string.


.. wait_for_timeout:

wait_for_timeout
^^^^^^^^^^^^^^^^^^^
Waits for the given timeout in seconds (a number).

If ``wait_for_url``, ``wait_for_selector`` and/or ``wait_for_function`` is also used, ``wait_for_timeout`` is applied
after.

Cannot be used with ``block_elements``.

.. versionadded:: 3.10

.. versionchanged:: 3.10
   Replaces ``wait_for`` with a number.


.. _wait_for_url:

wait_for_url
^^^^^^^^^^^^^^^^^^^
Wait until navigation lands on a URL matching this text (a string or dict).

The string (or the string in the ``url`` key of the dict) can be a glob pattern or regex pattern to match while
waiting for the navigation. Note that if the parameter is a string without wildcard characters, the method will wait for
navigation to a URL that is exactly equal to the string.

Useful to avoid capturing intermediate redirect pages.

Additional options can be passed when a dict is used: see `here
<https://playwright.dev/python/docs/api/class-page#page-wait-for-url>`__.


If other ``wait_for_*`` directives are used, ``wait_for_url`` is applied first.

Cannot be used with ``block_elements``.

.. versionadded:: 3.10

.. versionchanged:: 3.10
   Replaces ``wait_for_navigation``


.. _wait_until:

wait_until
^^^^^^^^^^^^^^^^^^^
The event of when to consider navigation succeeded (a string):

* ``load`` (default): Consider operation to be finished when the ``load`` event is fired.
* ``domcontentloaded``: Consider operation to be finished when the ``DOMContentLoaded`` event is fired.
* ``networkidle`` (old ``networkidle0`` and ``networkidle2`` map here): Consider operation to be finished when
  there are no network connections  for at least 500 ms.
* ``commit``: Consider operation to be finished when network response is received and the document started loading.

.. versionadded:: 3.0

.. versionchanged:: 3.10
   ``networkidle0`` and ``networkidle2`` are replaced by ``networkidle``;  added ``commit``.


.. initialization_url:

initialization_url
^^^^^^^^^^^^^^^^^^
The browser will load the ``initialization_url`` before navigating to ``url`` (a string). This could be useful for
monitoring pages on websites that rely on a state established when you first land on their "home" page.

Note that all the ``wait_for_*`` directives are apply only after navigating to ``url``.

.. versionadded:: 3.10


.. initialization_js:

initialization_js
^^^^^^^^^^^^^^^^^^
Only used with ``initialization_url``, executes the JavaScript after loading ```initialization_url`` and before
navigating to ``url`` (a string). This could be useful to programmatically emulate performing an action, such as logging
in.

.. versionadded:: 3.10


.. _referer:

referer
^^^^^^^
The referer header value (a string). If provided, it will take preference over the ``Referer`` header value set within
the ``headers`` directive.

.. versionadded:: 3.10


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

.. _command_directive:

command
^^^^^^^
The shell command to execute.

Optional directives (for all job types)
=======================================
These optional directives apply to all job types:


.. _name:

name
----
Human-readable name/label of the job used in reports (a string).

If this directive is not specified, the label used in reports will either be the ``url`` or the ``command`` itself or,
for ``url`` jobs retrieving HTML or XML data, the first 60 character of the contents of the <title> field if found.

.. versionchanged:: 3.0
   Added auto-detect <title> tag in HTML or XML.


.. _user_visible_url:

user_visible_url
----------------
URL or text to use in reports instead of contents of ``url`` or ``command`` (a string).

Useful e.g. when a watched URL is a REST API endpoint or you are using a custom script but you want a link to the
webpage on your report.

.. versionadded:: 3.0.3

.. versionchanged:: 3.8
   Added support for ``command`` jobs; previously worked only with ``url`` jobs.


.. _max_tries:

max_tries
---------
Number of consecutive times the job has to fail before reporting an error (an integer). Defaults to 1.

Due to legacy naming, this directive doesn't do what intuition would tell you it should do, rather, it tells
:program:`webchanges` **not** to report a job error until the job has failed for the number of consecutive times of
``max_tries``.

Specifically, when a job fails for *any* reason, :program:`webchanges` increases an internal counter; it will report an
error only when this counter reaches or exceeds the number of ``max_tries`` (default: 1, i.e. at the first error
encountered). The internal counter is reset to 0 when the job succeeds.

For example, if you set a job with ``max_tries: 12`` and run :program:`webchanges` every 5 minutes, you will only get
notified if the job has failed every single time during the span of one hour (5 minutes * 12 = 60 minutes) and from then
onwards at every run until the job succeeds again.


.. _filter:

filter
------
Filter(s) to apply to the data retrieved (a list of dicts).

See :ref:`here <filters>`.

Can be tested with ``--test``.


.. _diff_tool:

diff_tool
---------
Command to an external tool for generating diff text (a string).

Please see warning :ref:`above <important_note_for_command_jobs>` for file security required to run jobs with this
directive in Linux.

See example usage :ref:`here <word_based_differ>`.

.. versionchanged:: 3.0.1
   * Reports now show date/time of diffs generated using ``diff_tool``.
   * Output from ``diff_tool: wdiff`` is colorized in html reports.


.. _diff_filter:

diff_filter
-----------
Filter(s) to be applied to the diff result (a list of dicts).

See :ref:`here <diff_filters>`.

Can be tested with ``--test-diff``.


.. _additions_only_(jobs):

additions_only
--------------
Filter the unified diff output to keep only addition lines (no value required).

See :ref:`here <additions_only>`.

.. versionadded:: 3.0


.. _deletions_only_(jobs):

deletions_only
--------------
Filter the unified diff output to keep only deleted lines (no value required).

See :ref:`here <deletions_only>`.

.. versionadded:: 3.0


.. _monospace:

monospace
---------
Data is to be reported using a monospace font (true/false). Defaults to false.

Tells the ``html`` report that the data should be reported using a monospace font. Useful e.g. for tabular text
extracted by the  ``pdf2text`` filter.

.. versionadded:: 3.9


.. _is_markdown:

is_markdown
-----------
Data is in Markdown format (true/false). Defaults to false unless set by a filter such as ``html2text``.

Tells the ``html`` report that the data is in Markdown format and should be reconstructed into HTML.


.. kind

kind
----
For Python programmers only, this is used to associate the job to a custom job Class defined in ``hooks.py``, by
matching the contents of this directive to the ```__kind__`` variable of the class.


Setting default directives
==========================
See :ref:`here <job_defaults>` for how to set default directives for all jobs.
