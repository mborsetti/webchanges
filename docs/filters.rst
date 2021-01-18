.. **** IMPORTANT ****
   All code examples here need to have a unique URL that maps to an entry in the file
   test/data/filter_documentation_testdata.yaml. This will be used by testing to ensure that all examples work.

.. _filters:

=======
Filters
=======
Filters can be applied at either of two stages of processing:

* Applied to the downloaded data before storing it and diffing for changes (``filter``)
* Applied to the diff result before reporting the changes (``diff_filter``)

While creating your job pipeline, you might want to preview what the filtered output looks like. For filters applied
to the data, you can run `webchanges` with the ``--test-filter`` command-line option, passing in the index (from
``--list``) or the URL/command of the job to be tested::

   webchanges --test 1   # Test the first job in the list and show the data colleted after it's filtered
   webchanges --test https://example.net/  # Test the job that matches the given URL

This command will show the output that will be captured and stored, and used to compare to the old version stored from
a previous run against the same url or shell command.

Once `webchanges` has collected at least 2 historic snapshots of a job (two different states of a webpage) you can start
testing the effects of your ``diff_filter`` with the command-line option ``--test-diff``, passing in the index (from
``--list``) or the URL/command of the job to be tested, which using the historic data saved locally in the cache::

   webchanges --test-diff 1   # Test the first job in the list and show the report


At the moment, the following filters are available:

.. To convert the "webchanges --features" output, use:
   webchanges --features | sed -e 's/^  \* \(.*\) - \(.*\)$/- **\1**: \2/'

* To select HTML (or XML) elements:

  - :ref:`css <css-and-xpath>`: Filter XML/HTML using CSS selectors
  - :ref:`xpath <css-and-xpath>`: Filter XML/HTML using XPath expressions
  - :ref:`element-by-class <element-by->`: Get all HTML elements by class
  - :ref:`element-by-id <element-by->`: Get an HTML element by its ID
  - :ref:`element-by-style <element-by->`: Get all HTML elements by style
  - :ref:`element-by-tag <element-by->`: Get an HTML element by its tag

* To make HTML more readable:

  - :ref:`html2text`: Convert HTML to plaintext
  - :ref:`beautify`: Beautify HTML

* To make PDFs readable:

  - :ref:`pdf2text`: Convert PDF to plaintext

* To extract text from images:

  - :ref:`ocr`: Extract text from images

* To make JSON more readable:

  - :ref:`format-json`: Reformat (pretty-print) JSON

* To make XML more readable:

  - :ref:`format-xml`: Reformat (pretty-print) XML

* To make iCal more readable:

  - :ref:`ical2text`: Convert iCalendar to plaintext

* To make binary readable:

  - :ref:`hexdump`: Display data in hex dump format

* To just detect changes:

  - :ref:`sha1sum`: Calculate the SHA-1 checksum of the data

* To edit/filter text:

  - :ref:`keep_lines_containing`: Keep only lines containing specified text or matching`Python regular expression
    <https://docs.python.org/3/library/re.html#regular-expression-syntax>`__
  - :ref:`delete_lines_containing`: Delete lines containing specified text or matching a `Python regular expression
    <https://docs.python.org/3/library/re.html#regular-expression-syntax>`__
  - :ref:`re.sub`: Replace or remove text matching a `Python regular expression
    <https://docs.python.org/3/library/re.html#regular-expression-syntax>`__
  - :ref:`strip`: Strip leading and trailing whitespace (entire document, not line-by-line)
  - :ref:`sort`: Sort lines
  - :ref:`reverse`: Reverse the order of items (lines)

* Any custom script or program:

  - :ref:`shellpipe`: Run a program or custom script

Python programmers can write their own plug-in that could include filters; see :ref:`hooks`.



.. _css-and-xpath:

css and xpath
-------------
The ``css`` filter extracts content based on a `CSS selector <https://www.w3.org/TR/selectors/>`__. It uses the
`cssselect <https://pypi.org/project/cssselect/>`__ Python package, which has limitations and extensions as explained
in its `documentation <https://cssselect.readthedocs.io/en/latest/#supported-selectors>`__.

The ``xpath`` filter extracts content based on a `XPath <https://www.w3.org/TR/xpath>`__ expression.

Examples: to filter only the ``<body>`` element of the HTML document, stripping out everything else:

.. code-block:: yaml

   url: https://example.net/css.html
   filter:
     - css: ul#groceries > li.unchecked

.. code-block:: yaml

   url: https://example.net/xpath.html
   filter:
     - xpath: /html/body/marquee

See Microsoft’s `XPath Examples <https://msdn.microsoft.com/en-us/library/ms256086(v=vs.110).aspx>`__ page for some
other examples

Using CSS and XPath filters with XML and exclusions
"""""""""""""""""""""""""""""""""""""""""""""""""""
By default, CSS and XPath filters are set up for HTML documents, but it is possible to use them for XML documents as
well.

Example to parse an RSS feed and filter only the titles and publication dates:

.. code-block:: yaml

   url: https://example.com/blog/css-index.rss
   filter:
     - css:
         method: xml
         selector: 'item > title, item > pubDate'
     - html2text: re

.. code-block:: yaml

   url: https://example.com/blog/xpath-index.rss
   filter:
     - xpath:
         method: xml
         path: '//item/title/text()|//item/pubDate/text()'

To match an element in an `XML namespace <https://www.w3.org/TR/xml-names/>`__, use a namespace prefix before the tag
name. Use a ``|`` to separate the namespace prefix and the tag name in a CSS selector, and use a ``:`` in an XPath
expression.

.. code-block:: yaml

   url: https://example.org/feed/css-namespace.xml
   filter:
     - css:
         method: xml
         selector: 'item > media|keywords'
         namespaces:
           media: http://search.yahoo.com/mrss/
     - html2text

.. code-block:: yaml

   url: https://example.net/feed/xpath-namespace.xml
   filter:
     - xpath:
         method: xml
         path: '//item/media:keywords/text()'
         namespaces:
           media: http://search.yahoo.com/mrss/


Alternatively, use the XPath expression ``//*[name()='<tag_name>']`` to bypass the namespace entirely.

Another useful option with XPath and CSS filters is ``exclude``. Elements selected by this ``exclude`` expression are
removed from the final result. For example, the following job will not have any ``<a>`` tag in its results:

.. code-block:: yaml

   url: https://example.org/css-exclude.html
   filter:
     - css:
         selector: 'body'
         exclude: 'a'

Limiting the returned items from a CSS Selector or XPath
""""""""""""""""""""""""""""""""""""""""""""""""""""""""
If you only want to return a subset of the items returned by a CSS selector or XPath filter, you can use two additional
subfilters:

* ``skip``: How many elements to skip from the beginning (default: 0)
* ``maxitems``: How many elements to return at most (default: no limit)

For example, if the page has multiple elements, but you only want to select the second and third matching element (skip
the first, and return at most two elements), you can use this filter:

.. code:: yaml

   url: https://example.net/css-skip-maxitems.html
   filter:
     - css:
         selector: div.cpu
         skip: 1
         maxitems: 2

Duplicated results
""""""""""""""""""
If you get multiple results from one page, but you only expected one (e.g. because the page contains both a mobile and
desktop version in the same HTML document, and shows/hides one via CSS depending on the viewport size), you can use
'``maxitems: 1``' to only return the first item.


Optional directives
"""""""""""""""""""
* ``selector`` (for css) or ``path`` (for xpath) [can be entered as the value of the `xpath` or `css` directive]
* ``method``: Either of ``html`` (default) or ``xml``
* ``namespaces`` Mapping of XML namespaces for matching
* ``exclude``: Elements to remove from the final result
* ``skip``: 'Number of elements to skip from the beginning (default: 0)
* ``maxitems``: Maximum number of items to return (default: all)


.. _element-by-:

element-by-
-----------
The filters **element-by-class**, **element-by-id**, **element-by-style**, and **element-by-tag** allow you to select
all matching instances of a given HTML element.

Examples:

To extract only the ``<body>`` of a page:

.. code-block:: yaml

   url: https://example.org/bodytag.html
   filter:
     - element-by-tag: body


To extract ``<div id="something">.../<div>`` from a page:

.. code-block:: yaml

   url: https://example.org/idtest.html
   filter:
     - element-by-id: something

Since you can chain filters, use this to extract an element within another element:

.. code-block:: yaml

   url: https://example.org/idtest_2.html
   filter:
     - element-by-id: outer_container
     - element-by-id: something_inside

To make the output human-friendly you can chain html2text on the result:

.. code-block:: yaml

   url: https://example.net/id2text.html
   filter:
     - element-by-id: something
     - html2text:



.. _html2text:

html2text
-------------
This filter converts HTML (or XML) to plaintext.

Optional directives
"""""""""""""""""""
* ``method``: One of:

 - ``html2text``: Uses the `html2text <https://pypi.org/project/html2text/>`__ Python package (default) and retains
   some simple formatting (Markup language)
 - ``bs4``: Uses the `BeautifulSoup <https://pypi.org/project/beautifulsoup4/>`__ Python package to extract text
 - ``re``: Uses regex to strip tags


``html2text``
^^^^^^^^^^^^^
This filter converts HTML into `Markdown <https://www.markdownguide.org/>`__.
using the `html2text <https://pypi.org/project/html2text/>`__ Python package.

It is the recommended option to convert all types of HTML into readable text.

Example configuration:

Note: If the content has tables, adding the sub-directive `pad_tables: true` *may* improve readability.

.. code-block:: yaml

    url: https://example.com/html2text.html
    filter:
      - xpath: '//section[@role="main"]'
      - html2text:
          pad_tables: true

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* See `documentation <https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options>`__
* Note that the following options are set by default (but can be overridden): ensure that accented
  characters are kept as they are (`unicode_snob: true`), lines aren't chopped up
  (`body_width: 0`), additional empty lines aren't added between sections
  (`single_line_break: true`), and images are ignored (`ignore_images: true`).


``bs4``
^^^^^^^
This filter extracts unformatted text from HTML using the `BeautifulSoup
<https://pypi.org/project/beautifulsoup4/>`__, specifically its `get_text(strip=True)
<https://www.crummy.com/software/BeautifulSoup/bs4/doc/#get-text>`__ method.

Note that as of Beautiful Soup version 4.9.0, when lxml or html.parser are in use, the contents of <script>, <style>,
and <template> tags are not considered to be ‘text’, since those tags are not part of the human-visible content of the
page.

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``parser``: As per `documentation
  <https://www.crummy.com/software/BeautifulSoup/bs4/doc/#specifying-the-parser-to-use>`__  (default: ``lxml``)

Required packages
~~~~~~~~~~~~~~~~~
To run jobs with this filter, you need to install :ref:`additional Python packages <optional_packages>`.
Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[bs4]

``re``
^^^^^^
A simple HTML/XML tag stripper based on applying a regex.  Very fast but may
not yield the prettiest results.


.. _beautify:

beautify
--------
This filter uses the `BeautifulSoup <https://pypi.org/project/beautifulsoup4/>`__, `jsbeautifier
<https://pypi.org/project/jsbeautifier/>`__ and `cssbeautifier <https://pypi.org/project/cssbeautifier/>`__ Python
packages to reformat an HTML document to make it more readable.

Required packages
"""""""""""""""""
To run jobs with this filter, you need to install :ref:`additional Python packages <optional_packages>`.
Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[beautify]



.. _pdf2text:

pdf2text
--------
This filter converts a PDF file to plaintext using the `pdftotext
<https://github.com/jalan/pdftotext/blob/master/README.md#pdftotext>`__ Python library, itself based on the `Poppler
<https://poppler.freedesktop.org/>`__ library.

This filter *must* be the first filter in a chain of filters.

.. code-block:: yaml

   url: https://example.net/pdf-test.pdf
   filter:
     - pdf2text


If the PDF file is password protected, you can specify its password:

.. code-block:: yaml

   url: https://example.net/pdf-test-password.pdf
   filter:
     - pdf2text:
         password: webchangessecret

Optional sub-directives
"""""""""""""""""""""""
* ``password``: Password for a password-protected PDF file

Required packages
"""""""""""""""""
To run jobs with this filter, you need to install :ref:`additional Python packages <optional_packages>`.
Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[pdf2text]

In addition, you need to install any of the OS-specific dependencies of Poppler (see
`website <https://github.com/jalan/pdftotext/blob/master/README.md#os-dependencies>`__).


.. _ocr:

ocr
---
This filter extracts text from images using the `Tesseract OCR engine <https://github.com/tesseract-ocr>`_. Any file
format supported by the `Pillow <https://python-pillow.org>`_ (PIL Fork) Python package is supported.

This filter *must* be the first filter in a chain of filters, since it consumes binary data.

.. code-block:: yaml

   url: https://example.net/ocr-test.png
   filter:
     - ocr:
         timeout: 5
         language: eng

Optional sub-directives
"""""""""""""""""""""""
* ``timeout``: Timeout for the recognition, in seconds (default: 10 seconds)
* ``language``: Text language (e.g. ``fra`` or ``eng+fra``) (default: ``eng``)

Required packages
"""""""""""""""""
To run jobs with this filter, you need to install :ref:`additional Python packages <optional_packages>`.
Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[ocr]

In addition, you need to install `Tesseract <https://tesseract-ocr.github.io/tessdoc/Home.html>`__.



.. _format-json:

format-json
---------------
This filter deserializes a JSON object and reformats it using Python's `json.dumps
<https://docs.python.org/3/library/json.html#json.dumps>`__ with indentations.

Optional sub-directives
"""""""""""""""""""""""
* ``indentation``: Number of characters indent to pretty-print JSON array elements; ``None`` selects the most compact
  representation (default: 4)
* ``sort_keys`` (true/false): Whether to sort the output of dictionaries by key (default: false)

Advanced tip
""""""""""""
Python programmers can use an advanced technique to select only certain elements of the JSON object; see
:ref:`json_dict`.

.. _format-xml:

format-xml
----------
This filter deserializes an XML object and reformats it using the `lxml <https://lxml.de>`__ Python package's
etree.tostring `pretty_print <https://lxml.de/apidoc/lxml.etree.html#lxml.etree.tostring>`__ option.



.. _ical2text:

ical2text
---------
This filter reads an iCalendar document and converts them to easy-to read text

.. code-block:: yaml

   name: "Make iCal file readable test"
   url: https://example.com/cal.ics
   filter:
     - ical2text:

Required packages
"""""""""""""""""
To run jobs with this filter, you need to install :ref:`additional Python packages <optional_packages>`.
Install them using:

.. code-block:: bash

   pip install --upgrade webchanges[ical2text]



.. _hexdump:

hexdump
-----------
This filter display the contents both in binary and ASCII (hex dump format).

.. code-block:: yaml

   name: Display binary and ASCII test
   command: cat testfile
   filter:
     - hexdump:



.. _sha1sum:

sha1sum
-----------
This filter calculates a SHA-1 hash for the document.

.. code-block:: yaml

   name: "Calculate SHA-1 hash test"
   url: https://example.com/sha.html
   filter:
     - sha1sum:



.. _keep_lines_containing:

keep_lines_containing
---------------------
This filter keeps only lines that contain the text specified (default) or match the Python `regular
expression <https://docs.python.org/3/library/re.html#regular-expression-syntax>`__ specified, discarding the others.
Note that while this filter emulates Linux's `grep`, it **does not** use the executable `grep`.

Examples:

.. code-block:: yaml

   name: "convert HTML to text, strip whitespace, and only keep lines that have the sequence ``a,b:`` in them"
   url: https://example.com/keep_lines_containing.html
   filter:
     - html2text:
     - keep_lines_containing: 'a,b:'

.. code-block:: yaml

   name: "keep only lines that contain 'error' irrespective of its case (e.g. Error, ERROR, error, etc.)"
   url: https://example.com/keep_lines_containing_re.txt
   filter:
     - keep_lines_containing:
         re: '(?i)error'

Note: in regex ``(?i)`` is the inline flag for `case-insensitive matching <https://docs.python.org/3/library/re.html#re.I>`__.

Optional sub-directives
"""""""""""""""""""""""
* ``text`` (default): Match the text provided
* ``re``: Match the the Python `regular
  expression <https://docs.python.org/3/library/re.html#regular-expression-syntax>`__ provided



.. _delete_lines_containing:

delete_lines_containing
-----------------------
This filter is the inverse of ``keep_lines_containing`` above and discards all lines that contain the text specified
(default) or match the Python `regular expression
<https://docs.python.org/3/library/re.html#regular-expression-syntax>`__, keeping the others.

Examples:

.. code-block:: yaml

   name: "eliminate lines that contain 'xyz'"
   url: https://example.com/delete_lines_containing.txt
   filter:
     - delete_lines_containing: 'xyz'


.. code-block:: yaml

   name: "eliminate lines that start with 'warning' irrespective of its case (e.g. Warning, Warning, warning, etc.)"
   url: https://example.com/delete_lines_containing_re.txt
   filter:
     - delete_lines_containing:
         re: '^(?i)warning'

Notes: in regex ``^`` (caret) matches the `start of the string
<https://docs.python.org/3/library/re.html#regular-expression-syntax>`__ and ``(?i)`` is the inline flag for
`case-insensitive matching <https://docs.python.org/3/library/re.html#re.I>`__.



Optional sub-directives
"""""""""""""""""""""""
* ``text`` (default): Match the text provided
* ``re``: Match the the Python `regular
  expression <https://docs.python.org/3/library/re.html#regular-expression-syntax>`__ provided



.. _re.sub:

re.sub
------
This filter deletes or replaces text using Python `regular expressions
<https://docs.python.org/3/library/re.html#regular-expression-syntax>`__.

Just specifying a regular expression (regex) as the value will remove the match. Patterns can be replaced with another
string using ``pattern`` as the expression and ``repl`` as the replacement.

All features are described in Python’s re.sub `documentation <https://docs.python.org/3/library/re.html#re.sub>`__. The
``pattern`` and ``repl`` values are passed to this function as-is; if ``repl`` is missing, then it's considered to be an
empty string, and this filter deletes the the leftmost non-overlapping occurrences of ``pattern``.

The following example applies the filter 3 times:

.. code-block:: yaml

   name: "Strip href and change a few tags"
   url: https://example.com/re_sub.html
   filter:
     - re.sub: '\s*href="[^"]*"'
     - re.sub:
         pattern: '<h1>'
         repl: 'HEADING 1: '
     - re.sub:
         pattern: '</([^>]*)>'
         repl: '<END OF TAG \1>'

You can use the entire range of Python's `regular expression (regex) syntax
<https://docs.python.org/3/library/re.html#regular-expression-syntax>`__: for example groups (``()``) in the ``pattern``
and ``\1`` (etc.) to refer to these groups in the ``repl`` as in the example below, which replaces the number of
milliseconds (which may vary each time you check this page and generate a change report) with an X (which therefore
never changes):

.. code-block:: yaml

   name: "Replace a changing number in a sentence with an X"
   url: https://example.com/re_sub_group.html
   filter:
     - html2text:
     - re.sub:
         pattern: '(Page generated in )([0-9.])*( milliseconds.)'
         repl: '\1X\3'

Optional sub-directives
"""""""""""""""""""""""
* ``pattern``: Regular expression to match for replacement; this sub-directive must be specified when using the ``repl``
  sub-directive, otherwise the pattern can be specified as the value of ``re.sub`` (in which case a match will be
  deleted)
* ``repl``: The string for replacement. If this sub-directive is missing, defaults to empty string (i.e. deletes the
  string matched in ``pattern``)


.. _strip:

strip
-----
This filter removes leading and trailing whitespace.  Unlike many other filters, this filter is applied to the entire
document and is **not** applied line-by line.

.. code-block:: yaml

   name: "Stripping leading and trailing whitespace test"
   url: https://example.com/strip.html
   filter:
     - strip:


.. _sort:

sort
----
This filter performs a line-based sorting, ignoring cases (i.e. case folding as per Python's `implementation
<https://docs.python.org/3/library/stdtypes.html#str.casefold>`__).

If the source provides data in random order, you should sort it before the comparison in order to avoid diffing based
only on changes in the sequence.

.. code-block:: yaml

   name: "Sorting lines test"
   url: https://example.net/sorting.txt
   filter:
     - sort

The sort filter takes an optional ``separator`` parameter that defines the item separator (by default sorting is
line-based), for example to sort text paragraphs (text separated by an empty line):

.. code:: yaml

   url: https://example.org/paragraphs.txt
   filter:
     - sort:
         separator: "\n\n"

This can be combined with a boolean ``reverse`` option, which is useful for sorting and reversing with the same
separator (using ``%`` as separator, this would turn ``3%2%4%1`` into ``4%3%2%1``):

.. code:: yaml

   url: https://example.org/sort-reverse-percent.txt
   filter:
     - sort:
         separator: '%'
         reverse: true

Optional sub-directives
"""""""""""""""""""""""
* ``separator``: The string used to separate items to be sorted (default: ``\n``, i.e. line-based sorting)
* ``reverse`` (true/false): Whether the sorting direction is reversed (default: false)



.. _reverse:

reverse
-------

This filter reverses the order of items (lines) without sorting:

.. code:: yaml

   url: https://example.com/reverse-lines.txt
   filter:
     - reverse

This behavior can be changed by using an optional separator string argument (e.g. items separated by a pipe (``|``)
symbol, as in ``1|4|2|3``, which would be reversed to ``3|2|4|1``):

.. code:: yaml

   url: https://example.net/reverse-separator.txt
   filter:
     - reverse: '|'

Alternatively, the filter can be specified more verbose with a dict. In this example ``"\n\n"`` is used to separate
paragraphs (items that are separated by an empty line):

.. code:: yaml

   url: https://example.org/reverse-paragraphs.txt
   filter:
     - reverse:
         separator: "\n\n"


Optional sub-directives
"""""""""""""""""""""""
* ``separator`` (optional): The string used to separate items whose order is to be reversed (default: ``\n``, i.e.
  line-based reversing); it can also be specified inline as the value of ``reverse``



.. _shellpipe:

shellpipe
---------
The data to be filtered is passed to a 'shell' command or script and the output from this is used by `webchanges`. The
environment variable ``URLWATCH_JOB_NAME`` will have the name of the job, while ``URLWATCH_JOB_LOCATION`` its 'location'
(the value of either ``url`` or ``command``).

.. code-block:: yaml

   url: https://example.net/shellpipe.html
   filter:
     - shellpipe: echo TEST

If the command errors, the output of that error will be in the first line, before the traceback.

WARNING: On Linux systems, this filter will not run for security reasons unless both the config directory and the jobs
file are owned by and writeable **only** by the same user (and not by the group or other users) who is running the job.
To set this up:

.. code-block:: bash

   cd ~/.config/webchanges
   sudo chown $USER:$GROUP . *
   chmod g-w . *
   chmod o-w . *
