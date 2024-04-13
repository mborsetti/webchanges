.. _advanced_topics:

==============
Advanced usage
==============


.. _docker:

Running in Docker
-----------------
:program:`webchanges` can be run in a Docker container. Please see `<https://github.com/yubiuser/webchanges-docker>`__
for one such implementation.


.. _post:

Making POST requests
--------------------
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
If you are watching JSON-encoded dictionary data but are only interested in the data contained in certain key,
you can use the :ref:`jq` filter (Linux/macOS only, ASCII only) to extract it, or write a cross-platform Python command
like the one below:


.. code-block:: yaml

   url: https://example.com/api_data.json
   user_visible_url: https://example.com
   filter:
     - execute: "python3 -c \"import sys, json; print(json.load(sys.stdin)['data'])\""

Escaping of the Python is a bit complex due to being inside a double quoted shell string inside a double quoted YAML
string. For example, ``"`` code becomes ``\\\"`` and ``\n`` becomes ``\\n`` -- and so on. The example below provides
seemingly complex escaping and also informs the downstream html reporter that the extracted data is in Markdown:

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

More advanced programmers can write their own Class and :ref:`hook <hooks>` it into :program:`webchanges`.


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

More advanced programmers can write their own Class and :ref:`hook <hooks>` it into :program:`webchanges`.


.. _tor:

.onion (Tor) top level domain name
----------------------------------
.onion is a special-use top level domain name designating an anonymous onion service reachable only via the `Tor
network <https://www.torproject.org>`__. As sites with URLs in the .onion pseudo-TLD are not accessible via public DNS
and TCP, you need to run a Tor service as a SOCKS5 proxy service and use it to proxy these websites through it, as per
this example:

.. code-block:: yaml

   name: A .onion website (unencrypted http)
   url: http://www.example.onion
   http_proxy: socks5h://localhost:9050
   ---
   name: Another .onion website
   url: https://www.example2.onion
   https_proxy: socks5h://localhost:9050

Note the "h" in ``socks5h//``, which tells the underlying urllib3 library to resolve the hostname using the SOCKS5
server (see `here <https://github.com/urllib3/urllib3/issues/1035>`__).

Setting up Tor is out of scope for this document, but in Windows install the Windows Expert Bundle from `here
<https://www.torproject.org/download/tor/>`__ and execute ``tor --service install`` as an Administrator per
instructions `here <https://www.torproject.org/docs/faq#NTService>`__; in Linux the installation of the *tor* package
usually is sufficient to create a SOCKS5 proxy service, otherwise run with ``tor --options RunAsDaemon 1``. Some
useful options may be ``HardwareAccel 1 CircuitPadding 0 ConnectionPadding 0 ClientUseIPv6 1 FascistFirewall 1``
(check documentation).

Alternatively (Linux/macOS only), instead of proxying those sites you can use the **torsocks** (fka **torify**) tool
from the **tor** package to to make every Internet communication go through the Tor network. Just run
:program:`webchanges` within the **torsocks** wrapper:

.. code-block:: bash

   torsocks webchanges



.. _diff_script:

Passing diff output to a custom script
--------------------------------------
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

Using word-based differ (``wdiff`` or ``pandiff``)
--------------------------------------------------
You can also specify an **external** ``diff``-style tool (a tool that takes two filenames (old, new) as parameter and
returns the difference of the files on its standard output). For example, to to get word-based differences instead of
line-based difference, use GNU ``wdiff``:

.. code-block:: yaml

   url: https://example.com/
   diff_tool: wdiff

In order for this to work, ``wdiff`` needs to be installed separately (e.g. ``apt install wdiff`` on Debian/Ubuntu,
``brew install wdiff`` on macOS, or download from `here <https://www.di-mgt.com.au/wdiff-for-windows.html>`__ for
Windows).

You can more finely control the output of ``wdiff`` with command line arguments; see the manual for your installation
(or a generic one `here <https://www.gnu.org/software/wdiff/manual/>`__) for more information.

.. hint::
   If you use an ``html`` report with ``diff_tool: wdiff``, the output of ``wdiff`` will be colorized.

Alternatively you can use `PanDiff <https://github.com/davidar/pandiff>`__ to get markdown differences.

.. code-block:: yaml

   url: https://example.com/
   diff_tool: pandiff
   is_markdown: true

Note: the use of an external differ will override the ``diff`` setting of the ``html`` report.


Creating a separate notification for each change
------------------------------------------------
Each type of reports (:ref:`text`, :ref:`HTML` or :ref:`Markdown`) have an optional sub-directive ``separate``, which
when set to true will cause :program:`webchanges` to send a report for each job separately instead of a single combined
report with all jobs.

These sub-directives are set in the :ref:`configuration <reports-and-reporters>`.


Using environment variables in URLs
-----------------------------------
Currently this cannot be done natively.

However, as a workaround you can use a job with a :ref:command to invoke e.g. ``curl`` or ``wget`` which in turn reads
the environment variable. Example:

.. code-block:: yaml

   command: wget https://www.example.com/test?resource=$RESOURCE


Authenticated requests
----------------------
Set the ``Authorization`` header to provide credentials that authenticate a ``url`` job with a server, allowing access
to a protected resource. Some of the most popular authentication schemes are ``Basic``, ``Digest`` and ``NTLM``. For
more information, see `here <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Authorization>`__.



.. _use_browser_local_storage:

Using persistent browser storage (for e.g. authentication)
----------------------------------------------------------
Some sites may use a combination of cookies and/or their functional equivalent of storing data in 'Local Storage' to
authenticate or initialize their state and will not display the content you want unless you first authenticate (or
accept cookies or whatever). In these circumstances, you can use :program:`webchanges` with ``use_browser: true``
directive and its ``user_data_dir`` sub-directive to instruct it to use a pre-existing user directory, which you can
pre-initialize beforehand. Specifically:

#. Create an empty directory somewhere (e.g. ``mkdir ~/chrome_user_data_webchanges``);
#. Run a Google Chrome browser with the ``--user-data-dir`` switch pointing to this directory (e.g. ``chrome.exe
   --user-data-dir=~/chrome_user_data_webchanges``);
#. Browse to the site that you're interested in tracking and log in or do whatever is needed for it to save the
   authentication data in local storage;
#. Exit the browser.

You can now run a :program:`webchanges` job defined like this:

.. code-block:: yaml

   url: https://example.org/usedatadir.html
   use_browser: true
   user_data_dir: ~/chrome_user_data_webchanges


.. _overriding_content_encoding:

Overriding the content encoding
-------------------------------
(rare) For web pages with missing or incorrect ``'Content-type'`` HTTP header or whose encoding cannot be
`correctly guessed <https://docs.python-requests.org/en/master/api/#requests.Response.apparent_encoding>`__
by the `chardet <https://chardet.readthedocs.io/en/latest/faq.html#what-is-character-encoding-auto-detection>`__
library we use, it may be useful to explicitly specify an encoding from Python’s `Standard Encodings
<https://docs.python.org/3/library/codecs.html#standard-encodings>`__ list like this:

.. code-block:: yaml

   url: https://example.com/
   encoding: utf-8


Monitoring the HTTP response status code
----------------------------------------
To monitor the `HTTP response status code <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status>`__ of a resource
and be notified when it changes, use an external command like `curl <https://curl.haxx.se/>`__ to extract it. Here's a
job example:

.. code-block:: yaml

   command: curl --silent --output /dev/null --write-out '%{response_code}' https://example.com
   name: Example.com response status code
   note: Requires curl


Selecting recipients by individual job
--------------------------------------
Right now, reporter-related configuration per job isn't possible.

To achieve this, you have to rely on having multiple configurations and/or set up mailing lists or something. Because
reports are grouped (so there's only one notification sent out if both are changed) it wouldn't even be possible
without some additional logic to split reports in those cases. Also, there are some reporters that don't have the
concept of a "recipient".


Creating job urls based on keywords
-----------------------------------
:program:`webchanges` does not support arrays and loops to generate jobs (e.g. to check different pricing of a set of
products on a set of shots). The best way to do this is to use some template language outside of
:program:`webchanges` and let it generate the ``urls.yaml`` file from that template.


.. _use_browser_block_elements:

.. role:: strike
    :class: strike

:strike:`Speeding up browser jobs by blocking elements`
-------------------------------------------------------

.. warning::

   This Pyppeteer feature is not (yet?) implemented by Playwright, and therefore the ``block_elements`` directive
   is ignored (does nothing) for the time being.

.. rst-class:: strike

If you're running a browser job (``use_browser: true``) and not interested in all elements of a website, you can skip
downloading the ones that you don't care, paying attention that some elements may be required for the correct rendering
of the website (always test!). Typical elements to skip include ``stylesheet``, ``font``, ``image``, ``media``, and
``other``, and they can be specified like this on a job-by-job basis:

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

.. rst-class:: strike

or like this in the config file for all ``use_browser: true`` jobs:

.. code-block:: yaml
   :class: strike

   job_defaults:
     browser:
       block_elements:
         - stylesheet
         - font
         - image
         - media
         - other

The full list of supported resources is the following (from `here
<https://playwright.dev/docs/api/class-request#request-resource-type>`__):

- ``document``
- ``stylesheet``
- ``image``
- ``media``
- ``font``
- ``script``
- ``texttrack``
- ``xhr``
- ``fetch``
- ``eventsource``
- ``websocket``
- ``manifest``
- ``other``
