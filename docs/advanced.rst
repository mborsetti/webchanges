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
   execute: "python3 -c \"import sys, json; print(json.load(sys.stdin)['data'])\""


Escaping of the Python is a bit complex due to being inside a double quoted shell string inside a double quoted YAML
string. For example, ``"`` code becomes ``\\\"`` and ``\n`` becomes ``\\n`` -- and so on. The example below provides
seemingly complex escaping as well how to inform the downstream html reporter that the extracted data is in Markdown:

.. code-block:: yaml

   url: https://example.com/api_data.json
   user_visible_url: https://example.com
   execute: "python3 -c \"import sys, json; d = json.load(sys.stdin); [print(f\\\"[{v['Title']}]\\n({v['DownloadUrl']})\\\") for v in d['value']]\""
   is_markdown: true


.. _encoding:

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

Watching changes on .onion (Tor) pages
--------------------------------------
Since pages on the `Tor Network <https://www.torproject.org>`__ are not accessible via public DNS and TCP, you need to
either configure a Tor client as an HTTP/HTTPS proxy or, in Linux/macOS, use the `torify` tool from the `tor` package
(installable using ``apt install tor`` on Debian or Ubuntu or ``brew install tor`` on macOS). Setting up Tor is out of
scope for this document.

If using `torify`, just prefix the :program:`webchanges` command with the `torify` wrapper to access .onion pages:

.. code-block:: bash

   torify webchanges

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
     - shellpipe: /usr/local/bin/process_new_links.sh

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

.. tip::
   When using ``diff_tool: wdiff`` with an ``html`` report, the output of ``wdiff`` will be colorized.

Note: the use of an external differ will override the ``diff`` setting of the ``html`` report.

.. _pyppeteer:

Jobs with use_browser: true (Pyppeteer)
---------------------------------------

.. _pyppeteer_chromium_revision:

Using a Chromium revision matching a Google Chrome release
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
`:program:`webchanges`` currently specifies a Chromium release equivalent to Google Chrome version 89.0.4389.72. If you
want a different one, you can do so, but unfortunately the Chromium revision number does not match the Google Chrome /
Chromium release one, so you have to find out what the revision number is for a stable Chrome release.

There are multiple ways of doing so; the one I found easiest is to go to https://chromium.cypress.io/, selecting the
"stable" release channel `for the OS you need`, and clicking on "get downloads" for the one you want. At the top you
will see something like "Base revision: 843830. Found build artifacts at 843831 [browse files]". You want the
revision with build artifacts, in this example 843831.


.. attention::
   The same Google Chrome / Chromium release may be based on a different Chromium revision on different OSs,
   and not all Chromium revisions are available for all OS platforms (Linux_x64, Mac, Win and Win_x64). The full
   list of revisions available for download by `Pyppeteer` is at
   https://commondatastorage.googleapis.com/chromium-browser-snapshots/index.html. Specifying a release number that is
   not available for download is the cause of a ``zipfile.BadZipFile: File is not a zip file`` error from the
   `Pyppeteer` code.


.. note::
   Every time you change the chromium_revision, a new download is initiated and the old version is kept
   on your system, using up space. You must delete it manually; you will find it in the directory specified by running

   .. code-block:: bash

      python3 -c "from pyppeteer.chromium_downloader import DOWNLOADS_FOLDER; print(DOWNLOADS_FOLDER)"


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


If you use multiple OSs, you can specify different Chromium revisions to use based on the OS `:program:`webchanges`` is
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

   This feature is experimental and on certain sites it totally freeze execution; test before use

If you're not interested in all elements of a website you can skip downloading the ones that you don't care, paying
attention that some elements may be required for the correct rendering of the website (always test!). Typical elements
to skip include ``stylesheet``, ``font``, ``image``, and ``media``, and they can be specified like this (on a
job-by-job basis):

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

or in the config file (for all ``use_browser: true`` jobs):

.. code-block:: yaml

   job_defaults:
     browser:
       block_elements:
         - stylesheet
         - font
         - image
         - media
