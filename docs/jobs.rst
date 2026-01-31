.. _jobs:

****
Jobs
****
Each job contains the pointer to the source of the data to be monitored (:ref:`URL <url>` or :ref:`command <command>`)
and related directives, plus eventual directives on transformations (:ref:`filters <filters>`) to apply to the data
(and/or diff) once retrieved.

The list of jobs is contained by default in the jobs file ``jobs.yaml``, a :ref:`YAML <yaml_syntax>` text file editable
with the command ``webchanges --edit`` or using any text editor.

**YAML tips**

The YAML syntax has lots of idiosyncrasies that make it finicky, and new users often have issues with it. Below are
some tips and things to look for when using YAML, but please also see a more comprehensive introduction to
YAML :ref:`here <yaml_syntax>`.

* Indentation: All indentation must be done with spaces (2 spaces is suggested); tabs are not recognized/allowed.
  Indentation is mandatory and needs to be consistent throughout the file.
* Nesting: The indentation logic sometimes changes when nesting dictionaries.

.. code-block:: yaml

    filters:
      - html2text:           # a list item; notice 2 spaces before the '-'
          pad_tables: true   # a directory item; notice 6 spaces before the name


* There must be a space after the ``:`` between the key name and its value. The lack of such space is often the
  reason behind "Unknown filter kind" errors with no arguments.

.. code-block:: yaml

   filters:
     - re.sub: text  # This is correct

.. code-block:: yaml

   filters:
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
HTML or XML, :program:`webchanges` will automatically use the first 60 characters of the document's title (if
present) as the job's name.

.. code-block:: yaml

   name: This is a human-readable name/label of the job
   url: https://example.org/

**Initializing newly added jobs**

After adding new jobs, you can run :program:`webchanges` with ``--prepare-jobs`` to take and save a snapshot for
these new jobs without running all your existing jobs.


.. _url:

URL
===
This is the main job type. It retrieves a document from a web server (``https://`` or ``http://``), an ftp server
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

   If you specify :ref:`user_visible_url`, then the value of this directive is the one used for this restriction.

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
   simple ``url`` job. Only use when you can't find alternate ways to get to the data you want to monitor (e.g. by
   monitoring an API being called by the page, see tip below).

.. _rest_api:

.. tip:: In many instances you can get the data you want to monitor directly from a REST API (URL) called by the site
   during its page loading. Use browser developer tools (e.g., `Chrome DevTools
   <https://developers.google.com/web/tools/chrome-devtools>`__ - Ctrl+Shift+I) to inspect network activity (use the
   its `network activity inspection tab <https://developer.chrome.com/docs/devtools/network/>`__. If you find
   relevant API calls, extract the URL, method, and data to monitor it in a ``url`` job without the need to
   specify ``use_browser: true``.

.. attention::
   Due to browser limitations, ``use_browser: true`` cannot be used to capture a pdf file (e.g.
   https://www.example.com/prices.pdf). For a technical discussion, see `here
   <https://github.com/microsoft/playwright/issues/7822>`__.

.. important::
   * The optional `Playwright <https://playwright.dev/python/>`__ Python package must be installed; run
     ``pip install webchanges[use_browser]`` to install it.
   * The first time you run a job with ``use_browser:true``, if the latest version of Google Chrome is not found,
     :program:`Playwright` will download it (~350 MiB). This it could take some time (and bandwidth). You can
     pre-install the latest version of Chrome at any time by running ``webchanges --install-chrome``.

When using ``use_browser: true``, you do not need to set any headers in the configuration file or job unless the site
your monitoring has special requirements.

While we implement measures to minimize website detection of headless Chrome, passing basic detection tests `here
<https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html>`__, some sites use advanced
anti-automation methods such as rate limiting, session initialization (see :ref:initialization_url for handling),
CAPTCHAs, browser fingerprinting, etc. that might block your monitoring.

.. tip:: Please see the :ref:`no_conditional_request` directive if you need to turn off the use of :ref:`conditional
   requests <conditional_requests>` for those extremely rare websites that don't handle it (e.g. Google Flights).

.. tip:: If a job fails, you can run in verbose (``-v``) mode to save in the temporary folder a screenshot, a full
   page image, and the HTML contents at the moment of failure (see log for filenames) to aid in debugging.  If you have
   a screen, you can run in ``--no-headless`` and very verbose (``vv``), and the browser will open with `Chrome DevTools
   <https://developer.chrome.com/docs/devtools>`__ enabled.

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
for this directive to run successfully (default is 4) (see :ref:`here <max-snapshots>`).

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
Convenience setting to disable running the job while leaving it in the jobs file (true/false). Defaults to true.

.. versionadded:: 3.18


.. _headers:

headers
^^^^^^^
Headers to send along with the request (a dict).

The headers found in a job are merged case-insensitively with the default ones (including those found in ``config
.yaml``).  In case of conflicts, the header in the job will replace the default one.

See examples :ref:`here <default_headers>`.

Jobs without ``browser: true``
******************************
The default headers are:

.. code-block:: yaml

   accept: '*/*'
   accept-encoding:  # depends on libraries installed; at a minimum 'gzip, deflate'
   connection: 'keep-alive'
   user-agent: # set by the HTTP client, e.g. 'python-httpx/0.27.0'

Jobs with ``browser: true``
***************************
The default headers are set by the browser.

Note that if the :ref:`referer <referer>` directive if specified, its contents will replace the content of the `Referer
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referer>`__ header.


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
*****************
To use ``http_client: requests``, you need to have the ``requests`` library installed on your system. If it's not
installed, you can install this :ref:`additional Python package <optional_packages>` as follows:

.. code-block:: bash

   pip install --upgrade webchanges[requests]

.. versionadded:: 3.16


.. _proxy:

proxy
^^^^^
Proxy server to use for HTTP requests (a string). If unspecified or null/false, the system environment variable
``HTTPS_PROXY`` or ``HTTP_PROXY`` (based on the url's scheme), if defined, will be used. Can be one of ``https://``,
``http://`` or ``socks5://`` protocols.

E.g. ``https://username:password@proxy.com:8080``.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.

.. versionchanged:: 3.28
   Replaces two separate directives, ``http_proxy`` and ``https_proxy``.



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
* If the ``method`` directive is set to ``GET`` or ``HEAD``, the data is interpreted to contain the query parameters.
* If no `Content-type
  <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type>`__ ``header`` is specified, such header is
  set to ``application/x-www-form-urlencoded`` unless the ``data_as_json: true`` directive is present, in which case
  it is set to ``application/json``.

Examples:

For a POST, specifying a dictionary:

.. code-block:: yaml

   url: https://example.com/
   data:
       Element1: Data
       Element2: OtherData

For a POST, specifying a dictionary to be JSON-encoded:

.. code-block:: yaml

   url: https://example.com/
   data:
       Element1: Data
       Element2: OtherData
   data_as_json: true

For a PUT request method with a string :

.. code-block:: yaml

   url: https://example.com/
   method: PUT
   data: 'Special format data {"Element1": "Data", "Element2": "OtherData"}'

.. versionchanged:: 3.8
   Works for all ``url`` jobs, including those with ``use_browser: true``.

.. versionchanged:: 3.15
   Added ``data_as_json: true``.


.. _data_as_json:

data_as_json
^^^^^^^^^^^^
Specified that the data in ``data`` is to be sent in `JSON <https://en.wikipedia.org/wiki/JSON>`__ format (true/false).
Defaults to false.

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
Disable conditional requests (true/false). Defaults to false.

In rare cases where a web server does not correctly handle conditional requests (e.g., Google Flights), you can disable
this feature by setting ``no_conditional_request: true``. This prevents :program:`webchanges` from sending the
``If-Modified-Since`` and ``If-None-Match`` headers.

Please see :ref:`here  <conditional_requests>` to learn more about how :program:`webchanges` uses conditional requests
to improve performance and reduce bandwidth usage.


.. _note:

note
^^^^
Informational note added under the header in reports (a string, optionally in Markdown). Example:

.. code-block:: yaml

   name: Weather warnings
   note: If there's a hurricane watch, book a flight to get out of town
   url: https://example.org/weatherwarnings


If the string is in Markdown, it will be converted to HTML by an HTML report.

.. versionadded:: 3.2

.. versionchanged:: 3.30
   Accepts Markdown strings.


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
directive ```use_browser: true``, in which case it's 90 seconds. If set to 0, timeout is disabled.

See example :ref:`here <timeout>`.

.. versionchanged:: 3.0
   Works for all ``url`` jobs, including those with ``use_browser: true``.



Optional directives (without ``use_browser: true``)
--------------------------------------------------------
The following directives are available only for ``url`` jobs without ``use_browser: true``:


.. _encoding:

encoding
^^^^^^^^
Override the character encoding from the server or determined programmatically by the HTTP client library (a string).

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
<https://requests.readthedocs.io/en/latest/user/quickstart/#redirection-and-history>`__. Redirection takes place
whenever an HTTP status code of 301, 302, 303, 307 or 308 is returned.

Example:

.. code-block:: yaml

   url: https://donneespubliques.meteofrance.fr/donnees_libres/bulletins/BCM/203001.pdf
   no_redirects: true
   filters:
     - html2text:

Returns (HTML report version):

.. raw:: html

   <embed>
   <div class="output-box">
   Redirect <strong>302 Found</strong> to <a style="font-family:inherit" rel="noopener" target="_blank" href="https://donneespubliques.meteofrance.fr/?fond=donnee_indisponible">https://donneespubliques.meteofrance.fr/?fond=donnee_indisponible</a>:<br>
   <br>
   <strong>Found</strong><br>
   The document has moved <a style="font-family:inherit" rel="noopener" target="_blank" href="https://donneespubliques.meteofrance.fr/?fond=donnee_indisponible">here</a>.<br>
   --------------------------------------------------------------------------------<br>
   Apache/2.2.15 (CentOS) Server at donneespubliques.meteofrance.fr Port 80
   </div>
   </embed>

.. versionadded:: 3.2.7


.. _params:

params
^^^^^^
For parameter of a GET or HEAD request.

Example (equivalent to the URL https://example.com/?Element1=Data&Element2=OtherData):

.. code-block:: yaml

   url: https://example.com/
   params:
       Element1: Data
       Element2: OtherData

.. versionadded:: 3.25


.. _retries:

retries
^^^^^^^
Number of times to retry a url after receiving an error before giving up (a number). Default 0.

Setting it to 1 will often solve the ``('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))``
error received when attempting to connect to a misconfigured server.

.. code-block:: yaml

   url: https://www.example.com/
   retries: 1
   filters:
     - html2text:


.. _ssl_no_verify:

ssl_no_verify
^^^^^^^^^^^^^
Do not verify SSL certificates (true/false).

See more :ref:`here <ignoring_tls_ssl_errors>`.



Optional directives (only with ``use_browser: true``)
-----------------------------------------------------
The following directives are available only for ``url`` jobs with ``use_browser: true`` (i.e. using :program:`Chrome`):

.. _block_elements:

block_elements
^^^^^^^^^^^^^^
Do not load specified resource types requested by page loading (a list).

Used to speed up loading (typical elements to skip  include ``stylesheet``, ``font``, ``image``, ``media``, and
``other``).

.. code-block:: yaml
   :class: strike

   name: This is a Javascript site
   note: It's just a test
   url: https://www.example.com
   use_browser: true
   block_elements:
     - stylesheet
     - font
     - image
     - media
     - other

Supported `resources <https://playwright.dev/docs/api/class-request#request-resource-type>`__ are ``document``,
``stylesheet``, ``image``, ``media``, ``font``, ``script``, ``texttrack``, ``xhr``, ``fetch``, ``eventsource``,
``websocket``, ``manifest``, and ``other``.

.. versionadded:: 3.19


.. _http_credentials:

http_credentials
^^^^^^^^^^^^^^^^
Credentials for HTTP authentication.

A string in the format of 'username:password'.  For example, if the username is Adam and the password is Eve, use
``http_credentials: 'Adam:eve'``.

.. code-block:: yaml

   name: This website requires authentication
   note: It's just a test
   url: https://www.example.com
   use_browser: true
   http_credentials: 'user:password'

.. versionadded:: 3.32


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


.. _init_script:

init_script
^^^^^^^^^^^
Executes the JavaScript in Chrome after launching it and before navigating to ``url`` (a string).

This could be useful to e.g. unset certain default Chrome ``navigator`` properties by calling a JavaScript function
to do so.

.. versionadded:: 3.19


.. _initialization_js:

initialization_js
^^^^^^^^^^^^^^^^^
Only used with ``initialization_url``, executes the JavaScript in Chrome after navigating to ``initialization_url`` and
before navigating to ``url`` (a string).

This could be useful to e.g. emulate logging in when it's done by a JavaScript function.

.. versionadded:: 3.10


.. _initialization_url:

initialization_url
^^^^^^^^^^^^^^^^^^
The browser will navigate to ``initialization_url`` before navigating to ``url`` (a string).

This could be useful for monitoring subpages on websites that rely on a state established when first landing on their
"home" page. Also see ``initialization_js`` above. Note that all the ``wait_for_*`` directives apply only after
navigating to ``url`` and not after ``initialization_url``.

.. versionadded:: 3.10


.. _referer:

referer
^^^^^^^
The referer header value (a string).

If provided, it will take preference over the the `Referer
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referer>`__ header value set within the :ref:`headers`
directive.

.. versionadded:: 3.10


.. _switches:

switches
^^^^^^^^
Additional command line `switch(es) <https://peter.sh/experiments/chromium-command-line-switches/>`__ to pass to
Google Chrome, which is a derivative of Chromium (a list). These are called ``args`` in Playwright.

.. versionadded:: 3.0


.. _user_data_dir:

user_data_dir
^^^^^^^^^^^^^
A path to a pre-existing user directory (containing, e.g., cookies etc.) that Chrome should be using (a string).

.. versionadded:: 3.0


.. _wait_for_function:

wait_for_function
^^^^^^^^^^^^^^^^^
Waits for a JavaScript string to be evaluated in the browser context to return a truthy value (a string or dict).

If the string (or the string in the ``expression`` key of the dict) looks like a function declaration, it is interpreted
as a function. Otherwise, it is evaluated as an expression.

If ``wait_for_url`` and/or ``wait_for_selector`` is also used, ``wait_for_function`` is applied after these.

Sub-directives
**************
* ``expression`` (string): (default) JavaScript expression to be evaluated in the browser context. If the expression
  evaluates to a function, the function is automatically invoked.
* ``polling`` (float): An interval in milliseconds at which the function would be executed. Default is for the
  expression to be constantly executed in requestAnimationFrame callback.
* ``timeout`` (float): Maximum time in milliseconds. Defaults to the job's ``timeout``. Pass 0 to disable timeout.


.. versionadded:: 3.10

.. versionchanged:: 3.10
   This directive replaces ``wait_for`` containing a JavaScript function.


.. _wait_for_selector:

wait_for_selector
^^^^^^^^^^^^^^^^^
Waits for the element specified by selector string to become visible (a string or dict).

This happens when for the element to have non-empty bounding box and no visibility:hidden. Note that an element without
any content or with display:none has an empty bounding box and is not considered visible.

Selectors supported include CSS selectors, XPath expressions, text (prefixed by ``text=``), React locators (experimental
and prefixed by ```_react=```) and Vue locators (experimental and prefixed by ``_vue=``).

The following CSS pseudo-classes are supported: ``:has-text()``, ``:text()``, ``:text-is()``, ``:text-matches()``,
``:visible``, ``:has()``, ``:is()``, and ``:nth-match()``, plus the Playwright layout CSS pseudo-classes listed `here
<https://playwright.dev/docs/other-locators#css-matching-elements-based-on-layout>`__.

More information on working with selectors (called "other locators" by Playwright) is `here
<https://playwright.dev/python/docs/other-locators>`__.

To wait for more than one selector, ``wait_for_selector`` can be a list of items, which is executed in order.

If ``wait_for_url`` is also used, ``wait_for_selector`` is applied after.  If ``wait_for_function`` is also used,
``wait_for_selector`` is applied before.

Examples:

To wait until no spans having "loading" in their class are visible:

.. code-block:: yaml

  wait_for_selector:
    selector: //span[contains(@class, "loading")]
    state: hidden

To wait until no spans having "loading" in their class are present AND that the div with id "data" is visible:

.. code-block:: yaml

  wait_for_selector:
    - selector: //span[contains(@class, "loading")]
      state: detached
    - //div[@id="data"]

Sub-directives
**************
* ``selector`` (string): (default) the selector to query for.
* ``state`` (string): one of ``attached``, ``detached``, ``visible`` (default) or ``hidden``:

  - ``attached`` - wait for element to be present in DOM.
  - ``detached`` - wait for element to not be present in DOM.
  - ``visible`` (default) - wait for element to have non-empty bounding box and no visibility:hidden. Note that element
    without any content or with display:none has an empty bounding box and is not considered visible.
  - ``hidden`` - wait for element to be either detached from DOM, or have an empty bounding box or visibility:hidden.
    This is opposite to the 'visible' option.
* ``strict`` (true/false): When true (default), the call requires selector to resolve to a single element. If given
  selector resolves to more than one element, the call throws an exception.
* ``timeout`` (float): Maximum time in milliseconds. Defaults to the job's ``timeout``. Pass 0 to disable timeout.

.. versionadded:: 3.10

.. versionchanged:: 3.10
   This directive replaces ``wait_for`` containing a CSS selector or XPath expression.

.. versionchanged:: 3.31
   This directive can now be a list to wait for multple selectors.

.. _wait_for_timeout:

wait_for_timeout
^^^^^^^^^^^^^^^^
Waits for the given timeout in seconds (a number).

If ``wait_for_url``, ``wait_for_selector`` and/or ``wait_for_function`` is also used, ``wait_for_timeout`` is applied
after.

Cannot be used with ``block_elements``.

.. versionadded:: 3.10

.. versionchanged:: 3.10
   This directive replaces ``wait_for`` containing a number.


.. _wait_for_url:

wait_for_url
^^^^^^^^^^^^
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
   This directive replaces ``wait_for_navigation``.


.. _wait_until:

wait_until
^^^^^^^^^^
The event of when to consider navigation succeeded (a string):

* ``load`` (default): Consider operation to be finished when the ``load`` event is fired (document's HTML is fully
  parsed and all resources are loaded).
* ``domcontentloaded``: Consider operation to be finished when the ``DOMContentLoaded`` event is fired (document's HTML
  is fully parsed, but resources may not be loaded yet).
* ``networkidle``: Consider operation to be finished when there are no network connections for at least 500 ms.
  Deprecated  ``networkidle0`` and ``networkidle2`` map here.
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

.. important:: On Linux and macOS systems, due to security reasons, a ``command`` job or a job with a ``command`` differ
   will not run unless **both** the jobs file **and** the directory it is located in are **owned** and **writeable** by
   **only** the user who is running the job (and not by its group or by other users) or by the root user. To set this
   up:

   .. code-block:: bash

      cd ~/.config/webchanges  # could be different
      sudo chown $USER:$(id -g -n) . *.yaml
      sudo chmod go-w . *.yaml

   * ``sudo`` may or may not be required.
   * Replace ``$USER`` with the username that runs :program:`webchanges` if different than the one you're logged in when
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
Filter the unified diff output to keep only deletion lines (no value required).

See :ref:`here <deletions_only>`.

.. versionadded:: 3.0


.. _diff_filters_job_directive:

diff_filters
------------
Filter(s) to be applied to the diff result (a list of dicts).

See :ref:`here <diff_filters>`.

Can be tested with ``--test-differ``.

.. versionchanged:: 3.28
   Renamed from ``diff_filter`` (singular).


diff_tool (deprecated)
----------------------
Deprecated command to an external tool for generating diff text (a string). See new :ref:`differs` directive
:ref:`command_diff`.

Replace:

.. code-block:: yaml

    diff_tool: my_command


with:

.. code-block:: yaml

    differ:
      command: my_command

.. versionchanged:: 3.21
   *Deprecated* and replaced with differ :ref:`command_diff`.

.. versionchanged:: 3.0.1
   * Reports now show date/time of diffs generated using ``diff_tool``.
   * Output from ``diff_tool: wdiff`` is colorized in html reports.


.. _filters_job_directive:

filters
-------
Filter(s) to apply to the data retrieved (a list of dicts).

See :ref:`here <filters>`.

Can be tested with ``--test``.

.. versionchanged:: 3.28
   Renamed from ``filter`` (singular).

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
Use a monospace font for reports for this job (true/false). Defaults to false unless set to true by a filter or a
differ (see the documentation for that filter/differ). Especially useful with HTML reports, including when displaying
tabular data extracted by the ``pdf2text`` filter.

.. versionadded:: 3.9

.. versionchanged:: 3.20
   Default setting can be overridden by a filter or differ.


.. suppress_repeated_errors:

suppress_repeated_errors
------------------------
Mute repeated notifications (once every run) of the same error condition (true/false). Defaults to false.

If you set ``suppress_repeated_errors`` to ``true``, :program:`webchanges` will only send a notification for an error
the first time it is encountered. No more error notifications will be sent unless for the same error, and you will
be notified only if the error resolves or a different error occurs.

.. versionadded:: 3.27


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
