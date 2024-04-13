.. _reports:

=======
Reports
=======
Reports contain the changes detected (diff) and can be one of the following formats (depending on the :ref:`reporter
<reporters>` used and, at times, its settings):

* :ref:`text`
* :ref:`html`
* :ref:`markdown`


As a reminder, report sub-directives are set in the :ref:`configuration <reports-and-reporters>`.


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
* ``minimal``: An abbreviated report version (true/false); defaults to false.
* ``separate``: Send a separate report for each job instead of a single combined report (true/false); defaults to false.



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

These reports are by default `unified format <https://en.wikipedia.org/wiki/Diff#Unified_format>`__ diffs that are
prettified by :program:`webchanges` by:

* Making links `clickable <https://pypi.org/project/webchanges/>`__;
* Correctly representing Markdown formatting such as **bolding / headers**, *italics*, :underline:`underlining`, list
  bullets (•) and indentation;
* Using intuitive colors and strikethrough to highlight :additions:`added` and :deletions:`deleted` lines.


.. note:: You may receive a report that shows a deletion of some text and the addition of the same exact text: this is
   most likely due to a change in an underlying link.

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``diff``: Deprecated; specify a :ref:`differ <differs>` in the job instead.
* ``footer``: Show footer listing number of jobs and elapsed time (true/false); defaults to true.
* ``separate``: Send a separate report for each job instead of a single combined report (true/false); defaults to false.
* ``title``: The document's title. Use ``{count}`` for the number of reports, ``{jobs}`` for the title of jobs
  reported, and {jobs_files} for a space followed by the name of the jobs file(s) used within parenthesis, stripped
  of preceding ``jobs-``, if not using the default ``jobs.yaml``. Default: ``[webchanges] {count}
  changes:{jobs_files} {jobs}``.

.. versionchanged:: 3.21
   Deprecated the sub-directive ``diff``.


.. _markdown:

Markdown
--------
Markdown text, used in e.g. ``matrix``, ``telegram``, and ``webhook`` reporters (if the latter has the sub-directive
``markdown: true``)

Optional sub-directives
~~~~~~~~~~~~~~~~~~~~~~~
* ``details``: Includes the diff of each job (true/false); defaults to true. Ignored if ``minimal`` is true.
* ``footer``: Show footer listing number of jobs and elapsed time (true/false); defaults to true. Ignored if
  ``minimal`` is true.
* ``minimal``: An abbreviated report version (true/false); defaults to false.
* ``separate``: Send a separate report for each job instead of a single combined report (true/false); defaults to false.
