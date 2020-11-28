.. _advanced_topics:

==============
Usage examples
==============

Checking different sources at different intervals
-------------------------------------------------

You can divide your jobs into multiple job lists depending on how often you want to check.  For example, you can have
a ``daily.yaml`` job list for daily jobs, and a ``weekly.yaml`` for weekly ones.  You then set up the scheduler to
run `webchanges`, defining which job list to use, at different intervals.  For example in Linux using cron::

  0 0 * * * webchanges --jobs daily.yaml
  0 0 0 * * webchanges --jobs weekly.yaml


Getting reports via different channel for different sources
-----------------------------------------------------------

Job-specific alerts (reports) are not enabled, so the workaround is to create two job lists and two configurations.
For example, you can have a ``slack.yaml`` job list for jobs you want to be notified of via slack, and a ``email.yaml``
one for jobs you want to be notified of via email.  You then create two configuration files, for example
``config-slack.yaml`` and ``config-email.yaml``, and set them the first for slack reporting and the second for email
reporting.  Finally, you schedule them similarly to the below (in Linux using cron)::

  00 00 * * * webchanges --jobs slack.yaml --config config-slack.yaml
  05 00 * * * webchanges --jobs email.yaml --config config-email.yaml


.. _timeout:

Changing the default timeout
----------------------------

By default, url jobs timeout after 60 seconds. If you want a different timeout period, use the ``timeout`` directive to
specify it in number of seconds, or set it to 0 to never timeout.

.. code-block:: yaml

   url: https://example.com/
   timeout: 300


.. _cookies:

Supplying cookie data
---------------------

It is possible to add cookies to HTTP requests for pages that need it, the YAML syntax for this is:

.. code-block:: yaml

   url: https://example.com/
   cookies:
       Key: ValueForKey
       OtherKey: OtherValue


.. _compared_versions:

Comparing with several latest snapshots
---------------------------------------

If a webpage frequently changes between several known stable states, it may be desirable to have changes reported only
if the webpage changes into a new unknown state. You can use ``compared_versions`` to do this:

.. code-block:: yaml

   url: https://example.com/
   compared_versions: 3

In this example, changes are only reported if the webpage becomes different from the latest three distinct states. The
differences are shown relative to the closest match.

.. _ssl_no_verify:

Ignoring SSL errors
-------------------

Setting `ssl_no_verify` to true may be useful during local development or testing.

When set to true, `webchanges` requests will accept any TLS certificate presented by the server, and will ignore
hostname mismatches and/or expired certificates, which will make your application vulnerable to man-in-the-middle (MitM)
attacks.

.. code-block:: yaml

   url: https://example.com/
   ssl_no_verify: true


.. _ignore_errors:

Ignoring connection errors
--------------------------

In some cases, it might be useful to ignore (temporary) network errors to avoid notifications being sent. While there is
a ``display.error`` config option (defaulting to ``true``) to control reporting of errors globally, to ignore network
errors for specific jobs only, you can use the ``ignore_connection_errors`` directive in the job list configuration file:

.. code-block:: yaml

   url: https://example.com/
   ignore_connection_errors: true

Similarly, you might want to ignore some (temporary) HTTP errors on the server side:

.. code-block:: yaml

   url: https://example.com/
   ignore_http_error_codes: 408, 429, 500, 502, 503, 504

or ignore all HTTP errors if you like:

.. code-block:: yaml

   url: https://example.com/
   ignore_http_error_codes: 4xx, 5xx


.. _encoding:

Overriding the content encoding
-------------------------------

For web pages with misconfigured HTTP headers or rare encodings, it may be useful to explicitly specify an encoding from
Python’s `Standard Encodings <https://docs.python.org/3/library/codecs.html#standard-encodings>`__:

.. code-block:: yaml

   url: https://example.com/
   encoding: utf-8


Receiving a report every time webchanges runs
---------------------------------------------
If you are watching pages that change seldomly, but you still want to be notified daily if ``webchanges`` still works,
you can watch the output of the ``date`` command, for example:

.. code-block:: yaml

   name: "webchanges watchdog"
   command: "date"

Since the output of ``date`` changes every second, this job should produce a report every time webchanges is run.


.. _json_dict:

Selecting items from a JSON dictionary
--------------------------------------
If you are watching JSON-encoded dictionary data but are only interested in the data contained in (a) certain key(s),
you can use a Python command to easily extract it:


.. code-block:: yaml

   url: https://example.com/
   shellpipe: "python3 -c \"import sys, json; print(json.load(sys.stdin)['data'])\""


Or, more complex and with formatting for html reporters:

.. code-block:: yaml

   url: https://example.com/
   shellpipe "python3 -c \"import sys, json; d = json.load(sys.stdin); [print(f\"\"[{v['Title']}]({v['DownloadUrl']})\"\") for v in d['value']]\""
   is_markdown: true



Using Redis as a cache backend
------------------------------
To use Redis as a database (cache) backend instead of the default SQLite3 file::

    webchanges --cache=redis://localhost:6379/

There is no migration path from the existing SQLite3 database, the cache will be empty the first time Redis is used.


Watching changes on .onion (Tor) pages
--------------------------------------

Since pages on the `Tor Network`_ are not accessible via public DNS and TCP, you need to either configure a Tor client
as HTTP/HTTPS proxy or use the ``torify(1)`` tool from the ``tor`` package (``apt install tor`` on Debian,``brew install
tor`` on macOS). Setting up Tor is out of scope for this document. On a properly set up Tor installation, one can just
prefix the ``webchanges`` command with the ``torify`` wrapper to access .onion pages:

.. code-block:: bash

   torify webchanges

.. _Tor Network: https://www.torproject.org


Watching Facebook page events
-----------------------------

If you want to be notified of new events on a public Facebook page, you can use the following job pattern, replace
``PAGE`` with the name of the page (can be found by navigating to the events page on your browser):

.. code-block:: yaml

   url: https://m.facebook.com/PAGE/pages/permalink/?view_type=tab_events
   filter:
     - css:
         selector: div#objects_container
         exclude: 'div.x, #m_more_friends_who_like_this, img'
     - re.sub:
         pattern: '(/events/\d*)[^"]*'
         repl: '\1'
     - html2text:
   comparison_filter: additions


Passing diff output to a custom script
--------------------------------------

In some situations, it might be useful to run a script with the diff as input when changes were detected (e.g. to start
an update or process something). This can be done by combining ``diff_filter`` with the ``shellpipe`` filter, which
can be any custom script.

The output of the custom script will then be the diff result as reported by webchanges, so if it outputs any status, the
``CHANGED`` notification that webchanges does will contain the output of the custom script, not the original diff. This
can even have a "normal" filter attached to only watch links (the ``css: a`` part of the filter definitions):

.. code-block:: yaml

   url: https://example.org/downloadlist.html
   filter:
     - css: a
   diff_filter:
     - shellpipe: /usr/local/bin/process_new_links.sh


Using word-based differ (Linux)
-------------------------------

You can also specify an external ``diff``-style tool (a tool that takes two filenames (old, new) as parameter and
returns on its standard output the difference of the files), for example to use GNU ``wdiff`` to get word-based
differences instead of line-based difference:

.. code-block:: yaml

   url: https://example.com/
   diff_tool: wdiff

Note that ``diff_tool`` specifies an external command-line tool, so that tool must be installed separately (e.g. ``apt
install wdiff`` on Debian or ``brew install wdiff`` on macOS). Coloring is supported for ``wdiff``-style output, but
potentially not for other diff tools.


.. _chromium_revision:

Using a Chromium revision matching a Google Chrome / Chromium release
---------------------------------------------------------------------
Unfortunately the Chromium revision number does not match the Google Chrome / Chromium release one.
There are multiple ways of finding what the revision number is for a stable Chrome release; the one I found useful is
to go to https://chromium.cypress.io/, selecting the "stable" release channel `for the OS you need`, and clicking on
"get downloads" for the one you want.  At the top you will see something like "Base revision: 782793.
Found build artifacts at 782797 [browse files]".  You want the revision with build artifacts, in this case 782797.

Be aware that the same Google Chrome / Chromium release may be based on a different Chromium revision on different OSs,
and that not all Chromium revisions are available for all OS platforms (Linux_x64, Mac, Win and Win_x64).  Using a
release number that cannot be found will lead to a ``zipfile.BadZipFile: File is not a zip file`` error from the
Pyppeter code.

Please note that everytime you change the chromium_revision, a new download is initiated. The old ones are kept on
your system, and if you no longer need them you can delete them.  If you can't find the directory, try
``python3 -c "from pyppeteer.chromium_downloader import DOWNLOADS_FOLDER; print(DOWNLOADS_FOLDER)"``

To specify the Chromium revision to use (and other defaults) globally, edit config.yaml:

.. code-block:: yaml

   job_defaults:
     browser:
       chromium_revision: 782797
       switches:
         - --enable-experimental-web-platform-features
         - '--window-size=1920,1080'

To specify the Chromium revision to use , individual job:

.. code-block:: yaml

   url: https://example.com/
   use_browser: true
   chromium_revision: 782797
   switches:
     - --enable-experimental-web-platform-features
     - '--window-size=1920,1080'

.. _local_storage:

Browsing websites using local storage for authentication
---------------------------------------------------------

Some sites don't use cookies, rather store their functional equivalent using 'Local Storage'.  In these circumstances,
you can use `webchanges` with ``use_browser: true`` directive and its ``user_data_dir`` sub-directive to instruct it to
use a pre-existing user directory.

Specifically:

# create an empty directory somewhere (e.g. `/userdir`)
# run Chromium Google Chrome browser with the ``--user-data-dir`` switch pointing to this directory (e.g.
`chrome.exe --user-data-dir=/userdir``
# browse to the site that you're interested in tracking and log in or do whatever is needed
# quit the browser

You can now run a `webchanges` job defined as such:

.. code-block:: yaml

   url: https://example.org/usedatadir.html
   use_browser: true
   user_data_dir: /userdir
