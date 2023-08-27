.. _reports:

=======
Reports
=======
Reports contain the changes detected (diff) and can be one of the following formats (depending on the :ref:`reporter
<reporters>` and its settings):

* :ref:`text`
* :ref:`html`
* :ref:`markdown`



.. _text:

Text
----
Unicode text

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``details``: Includes the diff of each job (true/false); defaults to true. Ignored if ``minimal`` is true.
* ``footer``: Show footer listing number of jobs and elapsed time (true/false); defaults to true. Ignored if
  ``minimal`` is true.
* ``line_length``: The maximum length of each line in characters; defaults to 75 (integer). Ignored if ``minimal`` is
  true.
* ``minimal``: An abbreviated version (true/false); defaults to false.
* ``separate``: Send a report for each job instead of a combined report with all jobs; defaults to false.



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
* Correctly representing Markdown formatting such as **bolding / headers**, *italics*, :underline:`underlining`, list
  bullets (•) and indentation.
* Using color and strikethrough to highlight :additions:`added` and :deletions:`deleted` lines.


.. note: You may receive a report that shows a deletion of some text and the addition of the same exact text: this is
   most likely due to a change in the underlying link, since this is being tracked as well.

If for some reason you want the diff as a Python `HtmlDiff
<https://docs.python.org/3/library/difflib.html#difflib.HtmlDiff>`__ table, set the sub-directive ``diff`` to
``table``:


.. code-block:: yaml

   report:
     html:
       diff: table

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``diff``: ``unified`` (default) or ``table``. Overridden if the job directive ``diff_tool`` (external
  differ) is set.
* ``separate``: Send a report for each job instead of a combined report with all jobs; defaults to false.



.. _markdown:

Markdown
--------
Markdown text, used in e.g. ``matrix``, ``telegram``, and ``webhook`` reporters (if the latter has the sub-directive
``markdown: true``)

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``minimal``: An abbreviated version (true/false); defaults to false.
* ``show_details``: Includes the diff of each job (true/false); defaults to true. Ignored if ``minimal`` is true.
* ``show_footer``: Show footer listing number of jobs and elapsed time (true/false); defaults to true. Ignored if
  ``minimal`` is true.
* ``separate``: Send a report for each job instead of a combined report with all jobs; defaults to false.
