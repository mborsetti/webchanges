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
   name: "This one has a: colon followed by a space and a space followed by a # hash mark"
   name: "I must escape \"double\" quotes within a double quoted string"

* You can learn more about quoting special characters `here <https://www.yaml.info/learn/quote.html#flow>`__ (the
  library we use supports YAML 1.1, and our examples use "flow scalars"). URLs and XPaths are always safe and don't
  need to be enclosed in quotes.

For additional information on YAML, see the :ref:`yaml_syntax` page and the references at the bottom of that page.

**Multiple jobs**

Multiple jobs are separated by a line containing three hyphens, i.e. ``---``.

**Naming a job**

While optional, it is recommended that each job starts with a ``name`` entry. If omitted and the data monitored is
HTML or XML, :program:`webchanges` will automatically use for a name the first 60 characters of the document's title
(if present).

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
   followed by a unique remark (the # and everything after is typically discarded by a web server, but captured by
   :program:`webchanges`):

   .. code-block:: yaml

      name: Example homepage
      url: https://example.org/
      ---
      name: Example homepage -- again!
      url: https://example.org/#2

Internally, this type of job has the attribute ``kind: url``.


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
   As this job type renders the page in a headless Google Chrome instance, it requires more resources and time than a
   simple ``url`` job; use it only for resources where omitting ``use_browser: true`` does not give the right results
   and when you can't find alternate sources (e.g. an API).

.. _rest_api:

.. tip:: In many instances you can get the data you want to monitor directly from a REST API (URL) called by the site
   during its page loading. Monitor what happens during the page load with a browser's Developer's Tools (e.g. `Chrome
   DevTools <https://developers.google.com/web/tools/chrome-devtools>`__ using Ctrl+Shift+I, specifically its `network
   activity inspection tab <https://developer.chrome.com/docs/devtools/network/>`__) to see if this is the case. If so,
   get the URL, method, and data for this API and use it in a job that you can run without ``use_browser: true``.

.. important::
   * The optional `Playwright <https://playwright.dev/python/>`__ Python package must be installed; run
     ``pip install webchanges[use_browser]`` to install it.
   * The first time you run a job with ``use_browser:true``, if the latest version of Google Chrome is not found,
     :program:`Playwright` will download it (~350 MiB). This it could take some time (and bandwidth). You can
     pre-install the latest version of Chrome at any time with ``webchanges --install-chrome``.

When using ``use_browser: true``, you do not need to set any headers in the configuration file or job unless the site
you're monitoring has special requirements.

We implement measures to reduce the chance that a website can detect that the request is coming from a
headless Google Chrome instance, and we pass all detection tests `here
<https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html>`__, but we cannot guarantee
that this will always work (other measures, such as rate limiting or session initialization, for which you can use
:ref:`initialization_url`, may be in place to block or limit the effectiveness of automated tools).

.. tip:: Please see the :ref:`no_conditional_request` directive if you need to turn off the use of :ref:`conditional
   requests <conditional_requests>` for those extremely rare websites that don't handle it (e.g. Google Flights).

.. tip:: If a job fails, you can run in verbose (``-v``) mode to save in the temporary folder a screenshot, a full
   page image, and the HTML contents at the moment of failure (see log for filenames) to aid in debugging.

Internally, this type of job has the attribute ``kind: browser``.


.. versionchanged:: 3.0
   JavaScript rendering is done using the ``use_browser: true`` directive instead of replacing the ``url`` directive
   with ``navigate``, which is now deprecated.

.. versionchanged:: 3.10
   Using Playwright and Google Chrome instead of Pyppeteer and Chromium.

.. versionchanged:: 3.11
   Implemented measures to reduce the chance of detection.

.. versionchanged:: 3.14
   Saves the screenshot, full page image and HTML contents when a job fails while running in verbose mode.


Required directives
-------------------


.. _ulr:

url
^^^
The URI of the resource to monitor. ``https://``, ``http://``, ``ftp://`` and ``file://`` are supported.


Optional directives (all ``url`` jobs)
--------------------------------------
The following optional directives are available for all ``url`` jobs:


.. _use_browser_directive:

use_browser
^^^^^^^^^^^
Whether to use a Chrome web browser (true/false). Defaults to false.

If true, it renders the URL via a JavaScript-enabled web browser and extracts the HTML after rendering (see
:ref:`above <use_browser>` for important information).


.. _compared_versions:

compared_versions
^^^^^^^^^^^^^^^^^
Number of saved snapshots to compare against (int). Defaults to 1.

If set to a number greater than 1, instead of comparing the current data to only the very last snapshot captured, it
is matched against any of *n* snapshots. This is very useful when a webpage frequently changes between several known
stable states (e.g. they're doing A/B testing), as changes will be reported only when the content changes to a new
unknown state, in which case the differences are shown relative to the closest match.

Refer to the command line argument ``--max-snapshots`` to ensure that you are saving the number of snapshots you need
for this directive to run successfully (default is 4) (see :ref:`here<max-snapshots>`).

.. versionadded:: 3.10.2


.. _cookies:

cookies
^^^^^^^
Cookies to send with the request (a dict).

See examples :ref:`here <cookies>`.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _enabled:

enabled
^^^^^^^
Convenience setting to disable running the job while leaving it in the jobs file (true/false).  Defaults to true.

.. versionadded:: 3.18


.. _headers:

headers
^^^^^^^
Headers to send along with the request (a dict).

See examples :ref:`here <default_headers>`.

Note that with ``browser: true`` the `Referer
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referer>`__ header will be replaced by the
contents of the :ref:`referer <referer>` directive if specified.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _http_client:

http_client
^^^^^^^^^^^
The Python HTTP client library to be used, either `HTTPX <https://www.python-httpx.org/>`__ or `requests
<https://requests.readthedocs.io/en/latest/>`__. Defaults to ``HTTPX``.

We use ``HTTPX`` as some web servers will refuse a connection or serve an error if a connection is attempted using an
earlier version than the newer HTTP/2 network protocol. Use ``http_client: requests`` to use the ``requests``
library used by default in releases prior to 3.16 (but it only supports up to HTTP/1.1 protocol).

Required packages
"""""""""""""""""
To use ``http_client: requests``, unless the ``requests`` library is already installed in the system, you need to
first install :ref:`additional Python packages <optional_packages>` as follows:

.. code-block:: bash

   pip install --upgrade webchanges[requests]


.. versionadded:: 3.16


.. _http_proxy:

http_proxy
^^^^^^^^^^
Proxy server to use for HTTP requests (a string). If unspecified or null/false, the system environment variable
``HTTP_PROXY``, if defined, will be used. Can be one of ``https://``, ``http://`` or ``socks5://`` protocols.

E.g. ``https://username:password@proxy.com:8080``.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _https_proxy:

https_proxy
^^^^^^^^^^^
Proxy server to use for HTTPS (i.e. secure) requests (a string). If unspecified or null/false, the system environment
variable ``HTTPS_PROXY``, if defined, will be used. Can be one of ``https://``, ``http://`` or ``socks5://`` protocols.

E.g. ``https://username:password@proxy.com:8080``.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _data:

data
^^^^
The request payload to send with an `HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__
like ``POST`` (a dict or string).

If the data is a dict, it will be sent `urlencoded <https://en.wikipedia.org/wiki/URL_encoding>`__ unless the
directive ``data_as_json: true`` is also present, in which case it will be serialized as `JSON
<https://en.wikipedia.org/wiki/JSON>`__ before being sent.

When this directive is specified:

* If no ``method`` directive is specified, it is set to ``POST``.
* If no `Content-type
  <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type>`__ ``header`` is specified, such header is
  set to ``application/x-www-form-urlencoded`` unless the ``data_as_json: true`` directive is present, in which case
  it is set to ``application/json``.

See example :ref:`here <post>`.

.. versionchanged:: 3.8
   Works for all ``url`` jobs, including those with ``use_browser: true``.

.. versionchanged:: 3.15
   Added ``data_as_json: true``.


.. _data_as_json:

data_as_json
^^^^^^^^^^^^
The data in ``data`` is to be sent in `JSON <https://en.wikipedia.org/wiki/JSON>`__ format (true/false). Defaults to
false.

If true, the ``data`` will be serialized into JSON before being sent, and if no `Content-type
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type>`__ ``header`` is specified, such header is
set to ``application/json``.

See example within the directive ':ref:`data`'.

.. versionadded:: 3.15


.. _method:

method
^^^^^^
`HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__ to use (a string).

Must be one of ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``. Defaults to ``GET``
unless the ``data`` directive, below, is set when it defaults to ``POST``.

.. error:: Setting a method other than ``GET`` with ``use_browser: true`` may result in any 3xx redirections received by
   the website to be ignored and the job hanging until it times out. This is due to bug `#937719
   <https://bugs.chromium.org/p/chromium/issues/detail?id=937719>`__ in Chromium. Please take the time to add a star to
   the bug report so it will be prioritized for a faster fix.

.. versionchanged:: 3.8
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _no_conditional_request:

no_conditional_request
^^^^^^^^^^^^^^^^^^^^^^^^
In order to speed things up, :program:`webchanges` sets the ``If-Modified-Since`` and/or ``If-None-Match`` headers
on all requests, making them conditional requests (see more :ref:`here <conditional_requests>`). In extremely rare cases
(e.g. Google Flights) the ``If-Modified-Since`` will cause the website to hang or return invalid data, so you can
disable conditional requests with the directive ``no_conditional_request: true`` to ensure it is not added to the
query.


.. _note:

note
^^^^
Informational note added under the header in reports (a string).  Example:

.. code-block:: yaml

   name: Weather warnings
   note: If there's a hurricane watch, book a flight to get out of town
   url: https://example.org/weatherwarnings


.. versionadded:: 3.2


.. _ignore_cached:

ignore_cached
^^^^^^^^^^^^^
Do not use cache control values (ETag/Last-Modified) (true/false). Defaults to false.

Also see :ref:`no_conditional_request`.

.. versionchanged:: 3.10
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _ignore_connection_errors:

ignore_connection_errors
^^^^^^^^^^^^^^^^^^^^^^^^
Ignore (temporary) connection errors (true/false). Defaults to false.

See more :ref:`here <ignoring_http_connection_errors>`.

.. versionchanged:: 3.5
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _ignore_http_error_codes:

ignore_http_error_codes
^^^^^^^^^^^^^^^^^^^^^^^
Ignore error if a specified `HTTP response status code <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status>`__ is
received (an integer, string, or list).

Also accepts ``3xx``, ``4xx``, and ``5xx`` as values to denote an entire class of response status codes. For example,
``4xx`` will suppress any error from 400 to 499 inclusive, i.e. all client error response status codes.

See more :ref:`here <ignoring_http_connection_errors>`.

.. versionchanged:: 3.5
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _ignore_timeout_errors:

ignore_timeout_errors
^^^^^^^^^^^^^^^^^^^^^
Ignore error if caused by a timeout (true/false). Defaults to false.

See more :ref:`here <ignoring_http_connection_errors>`.

.. versionchanged:: 3.5
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _ignore_too_many_redirects:

ignore_too_many_redirects
^^^^^^^^^^^^^^^^^^^^^^^^^
Ignore error if caused by a redirect loop (true/false). Defaults to false.

See more :ref:`here <ignoring_http_connection_errors>`.

.. versionchanged:: 3.5
   Works for all ``url`` jobs, including those with ``use_browser: true``.


.. _timeout:

timeout
^^^^^^^
Override the default timeout, in seconds (a number). The default is 60 seconds for ``url`` jobs unless they have the
directive ```use_browser: true``, in which case it's 90 seconds.  If set to 0, timeout is disabled.

See example :ref:`here <timeout>`.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.



Optional directives (without ``use_browser: true``)
--------------------------------------------------------
The following directives are available only for ``url`` jobs without ``use_browser: true``:


.. _encoding:

encoding
^^^^^^^^
Override the character encoding from the server or determined programmatically (a string).

See more :ref:`here <overriding_content_encoding>`.


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


.. _no_redirects:

no_redirects
^^^^^^^^^^^^
Disables GET, OPTIONS, POST, PUT, PATCH, DELETE, HEAD redirection (true/false). Defaults to false (i.e. redirection
is enabled) for all methods except HEAD. See more `here
<https://requests.readthedocs.io/en/latest/user/quickstart/#redirection-and-history>`__.  Redirection takes place
whenever an HTTP status code of 301, 302, 303, 307 or 308 is returned.

Example:

.. code-block:: yaml

   url: "https://donneespubliques.meteofrance.fr/donnees_libres/bulletins/BCM/203001.pdf"
   no_redirects: true
   filter:
     - html2text:

Returns:

.. code-block::

   302 Found
   ---------

   # Found
   The document has moved [here](https://donneespubliques.meteofrance.fr/?fond=donnee_indisponible).
   * * *
   Apache/2.2.15 (CentOS) Server at donneespubliques.meteofrance.fr Port 80


.. versionadded:: 3.2.7


.. _retries:

retries
^^^^^^^
Number of times to retry a url before giving up. Default 0. Setting it to 1 will often solve the ``('Connection aborted
.', ConnectionResetError(104, 'Connection reset by peer'))`` error received when attempting to connect to a
misconfigured server.

.. code-block:: yaml

   url: "https://www.example.com/"
   retries: 1
   filter:
     - html2text:


.. _ssl_no_verify:

ssl_no_verify
^^^^^^^^^^^^^
Do not verify SSL certificates (true/false).

See more :ref:`here <ignoring_tls_ssl_errors>`.



Optional directives (only with ``use_browser: true``)
-----------------------------------------------------
The following directives are available only for ``url`` jobs with ``use_browser: true`` (i.e. using :program:`Chrome`):


.. _ignore_default_args:

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


.. _initialization_js:

initialization_js
^^^^^^^^^^^^^^^^^^
Only used with ``initialization_url``, executes the JavaScript after loading ```initialization_url`` and before
navigating to ``url`` (a string). This could be useful to e.g. logging in when it's done by calling a JavaScript
function.

.. versionadded:: 3.10


.. _initialization_url:

initialization_url
^^^^^^^^^^^^^^^^^^
The browser will load the ``initialization_url`` before navigating to ``url`` (a string). This could be useful for
monitoring pages on websites that rely on a state established when you first land on their "home" page.  Also see
``initialization_js`` below.

Note that all the ``wait_for_*`` directives are apply only after navigating to ``url``.

.. versionadded:: 3.10


.. _referer:

referer
^^^^^^^
The referer header value (a string). If provided, it will take preference over the the `Referer
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referer>`__ header value set within the :ref:`headers`
directive.

.. versionadded:: 3.10


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


.. _wait_for_timeout:

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



.. _command:

Command
=======
This job type allows you to watch the output of arbitrary shell commands. This could be useful for monitoring files
in a folder, output of scripts that query external devices (RPi GPIO), and many other applications.

.. code-block:: yaml

   name: What is in my home directory?
   command: dir -al ~

.. _important_note_for_command_jobs:

.. important:: On Linux and macOS systems, due to security reasons a ``command`` job or a job with ``diff_tool`` will
   not run unless **both** the jobs file **and** the directory it is located in are **owned** and **writeable** by
   **only** the user who is running the job (and not by its group or by other users). To set this up:

   .. code-block:: bash

      cd ~/.config/webchanges  # could be different
      sudo chown $USER:$(id -g -n) . *.yaml
      sudo chmod go-w . *.yaml

   * ``sudo`` may or may not be required.
   * Replace ``$USER`` with the username that runs :program:`webchanges` if different than the use you're logged in when
     making the above changes, similarly with ``$(id -g -n)`` for the group.

Internally, this type of job has the attribute ``kind: command``.

.. versionchanged:: 3.11
   ``kind`` attribute was renamed from ``shell`` to ``command`` but the former is still recognized.

Required directives
-------------------

.. _command_directive:

command
^^^^^^^
The shell command to execute.

Optional directives (for all job types)
=======================================
These optional directives apply to all job types:


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


.. _diff_filter:

diff_filter
-----------
Filter(s) to be applied to the diff result (a list of dicts).

See :ref:`here <diff_filters>`.

Can be tested with ``--test-diff``.


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


.. _filter:

filter
------
Filter(s) to apply to the data retrieved (a list of dicts).

See :ref:`here <filters>`.

Can be tested with ``--test``.


.. _kind:

kind
----
For Python programmers only, this is used to associate the job to a custom job Class defined in ``hooks.py``, by
matching the contents of this directive to the ``__kind__`` variable of the custom Class.

The three built-in job Classes are:

- ``kind: url`` for ``url`` jobs without the ``browser`` directive;
- ``kind: browser`` for ``url`` jobs with the ``browser: true`` directive;
- ``kind: command`` for ``command`` jobs (formerly called ``shell``).


.. _is_markdown:

is_markdown
-----------
Data is in Markdown format (true/false). Defaults to false unless set by a filter such as ``html2text``.

Tells the ``html`` report that the data is in Markdown format and should be reconstructed into HTML.


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
notified after the job has failed every single time during the span of one hour (5 minutes * 12 = 60 minutes), and from
then onwards at every run until the job succeeds again and the counter resets to 0.


.. _monospace:

monospace
---------
Data is to be reported using a monospace font (true/false). Defaults to false.

When using an ``html`` report the data will be displayed using a monospace font. Useful e.g. for tabular text
extracted by the ``pdf2text`` filter or for the output of the ``format-json`` filter.

.. versionadded:: 3.9


.. _name:

name
----
Human-readable name/label of the job used in reports (a string).

If this directive is not specified, the label used in reports will either be the ``url`` or the ``command`` itself or,
for ``url`` jobs retrieving HTML or XML data, the first 60 character of the contents of the <title> field if found.

While jobs are executed in parallel for speed, they appear in the report in alphabetical order by name, so
you can control the order in which they appear through their naming.

.. versionchanged:: 3.0
   Added auto-detect <title> tag in HTML or XML.

.. versionchanged:: 3.11
   Reports are sorted by job name.


.. _user_visible_url:

user_visible_url
----------------
URL or text to use in reports instead of contents of ``url`` or ``command`` (a string).

Useful e.g. when a watched URL is a REST API endpoint or you are using a custom script but you want a link to the
webpage on your report.

.. versionadded:: 3.0.3

.. versionchanged:: 3.8
   Added support for ``command`` jobs; previously worked only with ``url`` jobs.


Setting default directives
==========================
See :ref:`here <job_defaults>` for how to set default directives for all jobs or for jobs of an individual ``kind``.
