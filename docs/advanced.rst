.. _advanced_topics:

==============
Advanced usage
==============

.. _post:

Using POST request method
-------------------------
The ``POST`` `HTTP request method <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods>`__ is used to submit
form-encoded data to the specified resource (server). In :program:`webchanges`, simply supply your data in the ``data``
directive. The ``method`` will be automatically changed to ``POST`` and, if no `Content-type
<https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type>`__ header is supplied, it will be set to
``application/x-www-form-urlencoded``.

.. code-block:: yaml

   url: https://example.com/
   data:
       Element1: Data
       Element2: OtherData

For a string (e.g. JSON-encoded data, if supported by the server):

.. code-block:: yaml

   url: https://example.com/
   data: '{"Element1": "Data", "Element2": "OtherData"}'


.. _json_dict:

Selecting items from a JSON dictionary
--------------------------------------
If you are watching JSON-encoded dictionary data but are only interested in the data contained in (a) certain key(s),
you can use the :ref:`jq` filter (Linux/macOS only, ASCII only) to extract it, or write a cross-platform Python command
like the one below:


.. code-block:: yaml

   url: https://example.com/api_data.json
   user_visible_url: https://example.com
   filter:
     - execute: "python3 -c \"import sys, json; print(json.load(sys.stdin)['data'])\""

Escaping of the Python is a bit complex due to being inside a double quoted shell string inside a double quoted YAML
string. For example, ``"`` code becomes ``\\\"`` and ``\n`` becomes ``\\n`` -- and so on. The example below provides
seemingly complex escaping as well how to inform the downstream html reporter that the extracted data is in Markdown:

.. code-block:: yaml

   url: https://example.com/api_data.json
   user_visible_url: https://example.com
   filter:
     - execute: "python3 -c \"import sys, json; d = json.load(sys.stdin); [print(f\\\"[{v['Title']}]\\n({v['DownloadUrl']})\\\") for v in d['value']]\""
   is_markdown: true

Alternatively, you could run a script like this

.. code-block:: yaml

   url: https://example.com/api_data.json
   user_visible_url: https://example.com
   filter:
     - execute: python3 ~/.config/webchanges/parse.py
   is_markdown: true

With the script file ~/.config/webchanges/parse.py containing the following:

.. code-block:: python

   # ~/.config/webchanges/parse.py
   import json
   import sys

   data = json.load(sys.stdin)
   for v in d['value']:
       print(f"[{v['Title']}]\n({v['DownloadUrl']})")



Selecting HTML elements with wildcards
--------------------------------------
Some pages appends/generates random characters to the end of the class name, which change every time it's loaded. For
example:
contentWrap--qVat7asG
contentWrap--wSlxapCk
contentWrap--JV0HGsqD
etc.

``element-by-class`` does not support this, but XPATH does:

.. code-block:: yaml

   filter:
     - xpath: //div[contains(@class, 'contentWrap-')]
     - html2text

Alternatively, especially if you want to do more custom filtering, you can write an external Python script that uses
e.g. Beautiful Soup and call it:

.. code-block:: yaml

   filter:
     - execute: python3 ~/.config/webchanges/content_wrap.py
     - html2text

With the script file ~/.config/webchanges/content_wrap.py containing the following:

.. code-block:: python

   # ~/.config/webchanges/content_wrap.py
   import os
   import re
   import sys

   from bs4 import BeautifulSoup

   data = sys.stdin.read()
   soup = BeautifulSoup(data, 'lxml')

   # search for "div" elements with the according class
   for element in soup.find_all('div', {'class' : re.compile(r'contentWrap-*')}):
       print(element)



.. _overriding_content_encoding:

Overriding the content encoding
-------------------------------
For web pages with missing or incorrect ``'Content-type'`` HTTP header or whose (rare) encoding cannot be
`correctly guessed <https://docs.python-requests.org/en/master/api/#requests.Response.apparent_encoding>`__
by the `chardet <https://chardet.readthedocs.io/en/latest/faq.html#what-is-character-encoding-auto-detection>`__
library we use, it may be useful to explicitly specify an encoding as defined in Python’s `Standard Encodings
<https://docs.python.org/3/library/codecs.html#standard-encodings>`__ like this:

.. code-block:: yaml

   url: https://example.com/
   encoding: utf-8

.. _tor:

.onion (Tor) top level domain name
----------------------------------
.onion is a special-use top level domain name designating an anonymous onion service reachable only via the `Tor
network <https://www.torproject.org>`__. As sites with URLs in the .onion pseudo-TLD are not accessible via public DNS
and TCP, you need to run a Tor service as a SOCKS5 proxy service and use it to proxy these websites through it. Note the
"h" in ``socks5h//``, which tells the underlying urllib3 library to resolve the hostname using the SOCKS5 server (see
`here <https://github.com/urllib3/urllib3/issues/1035>`__):

.. code-block:: yaml

   name: A .onion website (unencrypted http)
   url: http://www.example.onion
   http_proxy: socks5h://localhost:9050
   ---
   name: Another .onion website
   url: https://www.example2.onion
   https_proxy: socks5h://localhost:9050

Setting up Tor is out of scope for this document, but in Windows install the Windows Expert Bundle from `here
<https://www.torproject.org/download/tor/>`__ and execute ``tor --service install`` as an Administrator per
instructions `here <https://www.torproject.org/docs/faq#NTService>`__; in Linux the installation of the *tor* package
usually is sufficient to create a SOCKS5 proxy service, otherwise run with ``tor --options RunAsDaemon 1``.  Some
useful options may be ``HardwareAccel 1 CircuitPadding 0 ConnectionPadding 0 ClientUseIPv6 1 FascistFirewall 1``
(check documentation)

Alternatively (Linux/macOS only), instead of proxying those sites you can use the *torsocks* (fka *torify*) tool from
the *tor* package to to make every Internet communication go through the Tor network. Just run :program:`webchanges`
within the *torsocks* wrapper:

.. code-block:: bash

   torsocks webchanges



.. _custom_diff:

Customized diffing
------------------

.. _diff_script:

Passing diff output to a custom script
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In some situations, it might be useful to run a script with the diff as input when changes were detected (e.g. to start
an update or process something). This can be done by combining ``diff_filter`` with the ``shellpipe`` filter, which
can run any custom script.

The output of the custom script will then be the diff result as reported by webchanges, so if it outputs any status, the
``CHANGED`` notification that webchanges does will contain the output of the custom script, not the original diff. This
can even have a "normal" filter attached to only watch links (the ``css: a`` part of the filter definitions):

.. code-block:: yaml

   url: https://example.org/downloadlist.html
   filter:
     - css: a
   diff_filter:
     - execute: /usr/local/bin/process_new_links.sh

If running on Linux/macOS, please read about file permission restrictions in the filter's explanation
:ref:`here <shellpipe>`.

.. _word_based_differ:

Using word-based differ (``wdiff``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You can also specify an **external** ``diff``-style tool (a tool that takes two filenames (old, new) as parameter and
returns the difference of the files on its standard output). For example, to to get word-based differences instead of
line-based difference, use GNU ``wdiff``:

.. code-block:: yaml

   url: https://example.com/
   diff_tool: wdiff

In order for this to work, ``wdiff`` needs to  be installed separately (e.g. ``apt install wdiff`` on Debian/Ubuntu,
``brew install wdiff`` on macOS, or download from `here <https://www.di-mgt.com.au/wdiff-for-windows.html>`__ for
Windows).

You can more finely control the output of ``wdiff`` with command line arguments; see the manual for your installation
(or a generic one `here <https://www.gnu.org/software/wdiff/manual/>`__) for more information.

.. hint::
   If you use an ``html`` report with ``diff_tool: wdiff``, the output of ``wdiff`` will be colorized.

Note: the use of an external differ will override the ``diff`` setting of the ``html`` report.



Creating a separate notification for each change
------------------------------------------------
Currently this cannot be done natively.

However, iterating over the list of jobs one by one with something like ``for i in {1..30}; do urlwatch $i; done``
(Linux) would achieve this but at the loss of parallelism; the function is documented :ref:`here <job_subset>`. The
current list of jobs including indexes can be printed with ``--list``.


Using environment variables in URLs
-----------------------------------
Currently this cannot be done natively.

However, as a workaround you can use a job with a :ref:command to invoke e.g. ``curl`` or ``wget`` which in turn reads
the environment variable. Example:

.. code-block:: yaml

   command: wget https://www.example.com/test?resource=$RESOURCE



.. _pyppeteer:

Jobs with use_browser: true (Pyppeteer)
---------------------------------------

.. _pyppeteer_chromium_revision:

Using a Chromium revision matching a Google Chrome release
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
:program:`webchanges` currently specifies a Chromium release equivalent to Google Chrome version 89.0.4389.72. If you
want a different one, you can do so, but unfortunately the Chromium revision number does not match the Google Chrome /
Chromium release one, so for a given stable Google Chrome release you have to find out the equivalent Chromium
revision number.

There are multiple ways of doing so; the one I found easiest is to go to https://chromium.cypress.io/, selecting the
"stable" release channel *for the OS you need*, and clicking on "get downloads" for the release you want. At the top
you will see something similar to "Base revision: 843830. Found build artifacts at 843831 [browse files]". You want the
revision with build artifacts, in this example 843831.


.. attention::
   The same Google Chrome / Chromium release may be based on a different Chromium revision on different OSs,
   and not all Chromium revisions are available for all OS platforms (Linux_x64, Mac, Win and Win_x64). The full
   list of revisions available for download by *Pyppeteer* is at
   https://commondatastorage.googleapis.com/chromium-browser-snapshots/index.html. Specifying a release number that is
   not available for download is the cause of a ``zipfile.BadZipFile: File is not a zip file`` error from the
   *Pyppeteer* code.


.. note::
   Every time you change the chromium_revision, a new download is initiated and the old version is kept on your
   system, using up space. You must delete unneeded versions manually; you will find the name of the directories
   containing the files by running:

   .. code-block:: bash

      webchanges --chromium-directory


To specify the Chromium revision to use (and other defaults) globally, edit config.yaml:

.. code-block:: yaml

   job_defaults:
     browser:
       chromium_revision:
         linux: 843831
       switches:
         - --enable-experimental-web-platform-features
         - '--window-size=1298,1406'

To specify the same on an individual job:

.. code-block:: yaml

   url: https://example.com/
   use_browser: true
   chromium_revision:
     linux: 843831
   switches:
     - --enable-experimental-web-platform-features
     - '--window-size=1298,1406'


If you use multiple OSs, you can specify different Chromium revisions to use based on the OS :program:`webchanges` is
running in by using a dict with one or more of ``linux``, ``mac``, ``win32`` and/or ``win64`` keys, either as a global
default (like below) or in individual jobs:

.. code-block:: yaml

   job_defaults:
     browser:
       chromium_revision:
         linux: 843831
         win64: 843846
         win32: 843832
         mac: 843846


.. _pyppeteer_target_closed:

Running in low-memory environments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In certain Linux environments with limited memory, jobs with ``use_browser: true`` may fail with a
``pyppeteer.errors.NetworkError: Protocol error Runtime.callFunctionOn: Target closed.`` error.

In such cases, try adding the `--disable-dev-shm-usage
<https://peter.sh/experiments/chromium-command-line-switches/#disable-dev-shm-usage>`__ Chromium switch in the config
file as follows:

.. code-block:: yaml

   job_defaults:
     browser:
       switches:
         - --disable-dev-shm-usage

This switch disables the use of the faster RAM-based temporary storage file system, whose size limit may cause Chromium
to crash, forcing instead the use of the drive-based filesystem, which may be slower but of ampler capacity.


.. _pyppeteer_local_storage:

Using local storage for authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Some sites don't use cookies for authentication but store their functional equivalent using 'Local Storage'. In these
circumstances, you can use :program:`webchanges` with ``use_browser: true`` directive and its ``user_data_dir``
sub-directive to instruct it to use a pre-existing user directory.

Specifically:

#. Create an empty directory somewhere (e.g. ``/userdir``)
#. Run Chromium Google Chrome browser with the ``--user-data-dir`` switch pointing to this directory (e.g. ``chrome.exe
   --user-data-dir=/userdir``)
#. Browse to the site that you're interested in tracking and log in or do whatever is needed for it to save the
   authentication data in local storage
#. Exit the browser

You can now run a :program:`webchanges` job defined like this:

.. code-block:: yaml

   url: https://example.org/usedatadir.html
   use_browser: true
   user_data_dir: /userdir

.. _pyppeteer_block_elements:

Speeding up jobs by blocking elements
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. danger::

   This feature is experimental and on certain sites it totally freeze execution; test before use!

If you're not interested in all elements of a website you can skip downloading the ones that you don't care, paying
attention that some elements may be required for the correct rendering of the website (always test!). Typical elements
to skip include ``stylesheet``, ``font``, ``image``, and ``media``, and they can be specified like this on a
job-by-job basis:

.. code-block:: yaml

   name: This is a Javascript site
   note: It's just a test
   url: https://www.example.com
   use_browser: true
   block_elements:
     - stylesheet
     - font
     - image
     - media

or like this in the config file for all ``use_browser: true`` jobs:

.. code-block:: yaml

   job_defaults:
     browser:
       block_elements:
         - stylesheet
         - font
         - image
         - media


Under the hood
--------------

Parallelism
^^^^^^^^^^^
All jobs are run in parallel threads for optimum speed.

If there are no jobs to run that have ``use_browser: true``, then the default number of threads is the default one from
Python's `concurrent.futures.ThreadPoolExecutor
<https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor>`__, which is currently
set to the number of processors on the machine multiplied by 5.

If at least one of the jobs has ``use_browser: true``, and therefore Pyppetter must be run, the upper limit is set by
the lower of the number of processors on the machine or, if known, the sum of available virtual memory and swap memory
divided by 140 MB.


Use of headers when determining if a webpage has changed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Once a website (``url``) has been checked once, any subsequent checks will be made as a conditional request by setting
the HTTP headers ``If-Modified-Since`` and, if an ETag was returned, the ``If-None-Match``.

The conditional request is an optimization to speed up execution since if there are no changes the server doesn't need
to send the document but just a 304 HTTP response code, which :program:webchanges: interprets as indicating that there
were no changes to the resource.

With the ``If-Modified-Since`` request HTTP header the server sends back the requested resource, with a 200 status, only
if it has been last modified after the given date. If the resource has not been modified since, the response is a 304
without any body; the Last-Modified response header of a previous request contains the date of last modification.

With the ``If-None-Match HTTP`` request HTTP header, for GET and HEAD methods, the server will return the requested
resource, with a 200 status, only if it doesn't have an ETag matching the given ones. For other methods, the request
will be processed only if the eventually existing resource's ETag doesn't match any of the values listed. When the
condition fails for GET and HEAD methods, then the server must return HTTP status code 304 (Not Modified). The
comparison with the stored ETag uses the weak comparison algorithm, meaning two files are considered identical if the
content is equivalent — they don't have to be identical byte by byte. For example, two pages that differ by their
creation date in the footer would still be considered identical. When used in combination with ``If-Modified-Since``,
``If-None-Match`` has precedence (if the server supports it).
