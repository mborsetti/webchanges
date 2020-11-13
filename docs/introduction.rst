.. _introduction:

============
Introduction
============

`webchanges` monitors the output of web sources (or of commands on your computer).

Every time you run `webchanges`, it:

#. retrieves the output;
#. transforms and filters it (optional);
#. compares this with an identically transformed and filtered version saved from the previous run, producing a "diff"
   report if it finds any changes;
#. (optional) filters the diff report;
#. displays such report (default) and/or sends it via one or more methods such as email;
#. saves the output to use the next time it's run.


:ref:`Jobs`
-----------
Each web source or command to be monitored is a "job".

The instructions for each such job are contained in a config file in the **YAML format** called ``jobs.yaml`` and
located in the following directory:

* Linux: ``~/.config/webchanges``
* MacOS: ``~/Library/Preferences/webchanges``
* Windows: ``%USERPROFILE%/Documents/webchanges`` (the webchanges folder within your Documents folder)

You can edit it with any text editor or by running:

.. code:: bash

   webchanges --edit

* For additional information on YAML, see the `YAML specifications <https://yaml.org/spec/>`__.
* For when to use quotes in YAML see `here <https://www.yaml.info/learn/quote.html#flow>`__
  (note: the library we use supports YAML 1.1, and our examples use "flow scalars").
* URLs are always safe and don't need to be enclosed in quotes.


The minimum configuration necessary for `webchanges` to work is a single ``url`` directive (for web resources) or
``command`` directive (for the output of a shell command):

.. code-block:: yaml

   url: https://example.com/

If you have multiple sources to monitor, i.e. multiple "jobs", separate each with a line of three dashes
(``---``):

.. code-block:: yaml

   url: https://example.com/
   ---
   url: https://example.com/page2
   ---
   command: dir

By default, the content is downloaded as-is. Certain webpages need for their JavaScript to be run in order for their
content to be rendered; in this case either find the API used by the JavaScript to get the data you care about and
monitor that API (preferred), or add the directive ``use_browser: true`` to use a virtual browser to render using
JavaScript. This requires additional installations and uses many resources; see :ref:`here <use_browser>` for more
information.

.. code-block:: yaml

   url: https://example.com/
   use_browser: true

You can add a ``name`` to a job to help you identify what you're monitoring, but `webchanges` will automatically try
to use a webpage's title if you don't do so:

.. code-block:: yaml

   name: Example
   url: https://example.com/

You can enter remarks in your YAML configuration file by using ``#``:

.. code-block:: yaml

   # I am monitoring this site because I expect it to change for the better
   name: Sample  # One more remark
   url: https://example.com/

Finally, you have a choice of many and many options to finely control the data acquisition; see :ref:`here <jobs>`.


:ref:`Filters`
--------------
Once you have collected the output, you may transform it to increase its utility. You use the ``filter`` directive to
activate one or more :ref:`filters <filters>` to:

* select HTML or (XML): ``css``, ``xpath``, ``element-by-class``, ``element-by-id``, ``element-by-style``, ``element-by-tag``
* extract text from HTML: ``html2text``
* make HTML more readable: ``beautify``
* extract text from PDF: ``pdf2text``
* extract text from images or PDF: ``ocr``
* make JSON more readable: ``format-json``
* make XML more readable: ``format-xml``
* make iCal more readable: ``ical2text``
* make binary readable: ``hexdump``
* detect if anything changed: ``sha1sum``
* edit text: ``keep_lines_containing``, ``delete_lines_containing``, ``re.sub``, ``strip``, ``sort``

If all you're doing is monitoring the text of a website, this filter will do it:

.. code-block:: yaml

    url: https://example.com/
    filters:
      - html2text:  # notice the 2 empty spaces before the hyphen and the colon at the end

Filters can be chained. As an example, after retrieving an HTML document by using the ``url`` directive, you
can extract a selection with the ``xpath`` filter, convert it to text with ``html2text``, extract only lines matching
a specific regular expression with ``keep_lines_containing``, and sort the result with ``sort``:

.. code-block:: yaml

    name: Sample webchanges job definition
    url: https://example.com/
    https_proxy: http://user:password@example.net:8080
    max_tries: 2
    filter:
      - xpath: //section[@role="main"]
      - html2text:
          method: html2text
          unicode_snob: true
          body_width: 0
          inline_links: false
          ignore_links: true
          ignore_images: true
          pad_tables: false
          single_line_break: true
      - keep_lines_containing: lines I care about
      - sort:
    ---

Filters are explained :ref:`here <filters>`.


Comparison
----------
`webchanges` then automatically performs a comparison between the filtered data collected in this run with
the one saved from a prior run, computing a diff in the `unified format
<https://en.wikipedia.org/wiki/Diff#Unified_format>`__ ('unified diff') by default.


:ref:`Diff filters <diff_filters>`
----------------------------------
After the comparison is generated, you can apply one of the filters above to the diff itself  or one of the two
diff-specific ones:

- ``additions_only``
- ``deletions_only``

Diff filters Reports are explained :ref:`here <diff_filters>`.

If all you're doing is monitoring the text of a website to see if anything was added, this job definition will do it:

.. code-block:: yaml

    url: https://example.com/
    filters:
      - html2text:  # notice the 2 empty spaces before the hyphen and the colon at the end
    additions_only:


:ref:`Reports`
--------------
You can select settings to tailor what elements are included in the report, depending on the format (``text``,
``html`` and/or ``markdown``)

Reports are explained :ref:`here <reports>`.


:ref:`Reporters`
----------------
Finally, by default `webchanges` displays the diff report on the ``stdout`` console, but you can add (or change to) one
or more of:

- ``stdout``
- ``browser``
- ``email`` (using SMTP or sendmail)
- ``xmpp``
- ``slack``
- ``telegram``
- ``pushover``
- ``pushbullet``
- ``ifttt``
- ``matrix``
- ``mailgun``

Reporters are explained :ref:`here <reporters>`.

Scheduling
----------

``webchanges`` will check for changes every time you run it, but does not include a scheduler. We recommend using a
system scheduler to automatically run `webchanges` periodically:

- In Linux, you can use cron; `crontab.guru <https://crontab.guru>`__ will build a schedule expression for you. If you
  have never used cron before, see `here <https://www.computerhope.com/unix/ucrontab.htm>`__.
- On Windows, you can use the built-in `Windows Task Scheduler
  <https://en.wikipedia.org/wiki/Windows_Task_Scheduler>`__.