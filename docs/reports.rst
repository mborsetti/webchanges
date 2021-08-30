.. _reports:

=======
Reports
=======
Reports are the text of the summary (diff), and can be one of the following formats (depending on what
:ref:`reporter <reporters>` you use):

* :ref:`text`
* :ref:`html`
* :ref:`markdown`



.. _text:

Text
----
Unicode text

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``minimal``: An abbreviated version (true/false); defaults to false (if set to true directives below are ignored)
* ``line_length``: The maximum length of each line; defaults to 75
* ``show_details``: Includes the diff of each job (true/false); defaults to true
* ``show_footer``: Show footer listing number of jobs and elapsed time (true/false); defaults to true



.. _html:

HTML
----
HTML

.. role:: underline
    :class: underline

.. role:: additions
    :class: additions

.. role:: deletions
    :class: deletions

These reports are by default ``unified`` diffs that are prettified by :program:`webchanges` by:

* Making links `clickable <https://pypi.org/project/webchanges/>`__!
* Preserving formatting such as **bolding / headers**, *italics*, :underline:`underlining`, list bullets (•) and
  indentation
* Using color and strikethrough to highlight :additions:`added` and :deletions:`deleted` lines


If for some reason you want the output to be a Python `HtmlDiff
<https://docs.python.org/3/library/difflib.html#difflib.HtmlDiff>`__ HTML table, set the sub-directive ``diff`` to
``table``.

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``diff``: ``unified`` (default) or ``table``; see above. Note that the use of an external differ (i.e. using the
  ``diff_tool`` directive in the job) will override this.



.. _markdown:

Markdown
--------
Markdown text, used for the ``matrix`` and ``webhook`` reporters (if the latter has the sub-directive
``markdown: true``)

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``minimal``: An abbreviated version (true/false); defaults to false (if set to true directives below are ignored)
* ``show_details``: Includes the diff of each job (true/false); defaults to true
* ``show_footer``: Show footer listing number of jobs and elapsed time (true/false); defaults to true
