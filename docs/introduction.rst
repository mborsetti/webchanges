.. _introduction:

============
Introduction
============

`webchanges` monitors the output of webpages (or commands on your computer shell).

Every time you run `webchanges`, it:

#. retrieves the output;
#. transforms and filters it (optional);
#. compares this with what it saved from the previous run, producing a "diff" report if it finds changes;
#. (optional) filters the diff report;
#. displays such report (default) and/or sends it via one or more methods such as email.


:ref:`Jobs`
-----------
Each such source of data is a "job". The instructions for each such job are contained in a config file in the **YAML
format** called ``jobs.yaml`` and located in ``~/.config/webchanges`` (Linux), ``~/Library/Preferences/webchanges``
(MacOS), or in the ``webchanges`` folder within your Documents folder, i.e. ``%USERPROFILE%/Documents/webchanges``
(Windows).  You can edit it with any text editor or:

.. code:: bash

   webchanges --edit

For additional information on YAML, see the `YAML specifications <https://yaml.org/spec/>`__.  You can learn more about
when to use quotes in YAML `here <https://www.yaml.info/learn/quote.html#flow>`__ (note: the library we use 
supports YAML 1.1, and our examples use "flow scalars").  URLs are always safe and don't need to be enclosed in quotes.


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

By default, the content is downloaded as-is; if you need for a webpage to be
rendered and its JavaScript run and only then the HTML captured, add the directive ``use_browser: true``. This
requires additional installations and uses many resources; see :ref:`here <use_browser>` for more information.

.. code-block:: yaml

   url: https://example.com/
   use_browser: true

You can add a ``name`` to help you identify what you're monitoring, but `webchanges` will automatically try to use a
webpage's title if you don't do so:

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
Once you have collected the output, you may transform it to increase its utility.  You use the ``filter`` directive to
activate one or more :ref:`filters` to:

* select HTML or (XML): ``css``, ``xpath``, ``element-by-class``, ``element-by-id``, ``element-by-style``, ``element-by-tag``
* extract text from HTML: ``html2text``
* make HTML more readable: ``beautify``
* extract text from PDF: ``pdf2text``, ``ocr``
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
    https_proxy: http://user:passwor@example.net:8080
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
<https://en.wikipedia.org/wiki/Diff#Unified_format>`__ by default.


:ref:`Diff filters <diff_filters>`
----------------------------------
After the comparison is generated, you can apply one of the filters above to the diff itself (see
:ref:`diff_filters`) or one of the two diff-specific ones:

- ``additions_only``
- ``deletions_only``


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
