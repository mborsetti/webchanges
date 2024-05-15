.. role:: additions
    :class: additions
.. role:: deletions
    :class: deletions

.. _differs:

==================
Differs
==================
A differ is applied to the filtered data if it has changed from the previous run(s). A differ summarizes the changes in
the data and produces the content of the report sent to you. The output of the differ can be further filtered using any
of the filters listed in :ref:`filters` (see :ref:`diff_filters` below).

.. To convert the "webchanges --features" output, use:
   webchanges --features | sed -e 's/^  \* \(.*\) - \(.*\)$/- **\1**: \2/'

At the moment, the following differs are available:

  - :ref:`unified <unified_diff>`: (default) Compares data line-by-line, showing changed lines in a "unified format";
  - :ref:`command <command_diff>`: Executes an outside command that acts as a differ (e.g. wdiff);
  - :ref:`deepdiff <deepdiff_diff>`: Compares structured data (JSON or XML) element-by-element.
  - :ref:`table <table_diff>`: A Python version of the :ref:`unified <unified_diff>` differ where the changes are
    displayed as an HTML table;

In addition, the following BETA differs are available:

  - :ref:`ai_google <ai_google_diff>`: Detects and summarizes changes using Generative AI (free API key required).
  - :ref:`image <image_diff>`: Detects changes in an image and displays them as overlay over a grayscale version of the
    old image.


A differ is specified using the job directive ``differ``. To select a differ with its default directive values,
assign the name of the differ as the value:

.. code-block:: yaml

   url: https://example.net/unified.html
   differ: unified  # this entire line can be omitted as it's the default differ

.. code-block:: yaml

   url: https://example.net/deepdiff.html
   differ: deepdiff  # use the deepdiff differ with its default values


Otherwise, the ``differ`` directive is a dictionary, and the ``name`` key contains the name of the differ:

.. code-block:: yaml

   url: https://example.net/unified_no_range.html
   differ:
     name: unified
     range_info: false


.. _unified_diff:

unified
-------
The default differ used when the ``differ`` job directive is not specified (except, for backward compatibility, when
in the configration file the ``html`` report has the deprecated ``diff`` key set to ``table``).

It does a line-by-line comparison, and reports lines that have been added (:additions:`+`), deleted (:deletions:`-`),
or changed. Changed lines are displayed twice: once marked as "deleted" (:deletions:`-`) representing the old
content, and once as "added" (:additions:`+`) representing the new content. Results are displayed in the `unified
format <https://en.wikipedia.org/wiki/Diff#Unified_format>`__ (the "*unified diff*").

For HTML reports, :program:`webchanges` colorizes the unified diff for easier legibility.

Examples:

.. code-block:: yaml

   url: https://example.net/unified.html
   differ: unified  # this can also be omitted as it's the default


.. code-block:: yaml

   url: https://example.net/unified_no_range.html
   differ:
     name: unified
     range_info: false

.. _contextlines:

The ``context_lines`` directive causes a unified diff to have a set number of context lines that might be different from
Python's default of 3 (or 0 if the job contains ``additions_only: true`` or ``deletions_only: true``).

Example:

.. code-block:: yaml

   url: https://example.com/#lots_of_contextlines
   differ:
     name: unified
     context_lines: 5

Output:

.. code-block::

   ---------------------------------------------------------------------------
   CHANGED: https://example.com/#lots_of_contextlines
   ---------------------------------------------------------------------------
   --- @   Sat, 01 Oct 2020 00:00:00 +0000
   ... @   Sat, 01 Oct 2020 01:00:00 +0000
   @@ -1,15 +1,15 @@
    This is line 10
    This is line 11
    This is line 12
    This is line 13
    This is line 14
   -This is line 15
   +This is line fifteen
    This is line 16
    This is line 17
    This is line 18
    This is line 19
    This is line 20

Example (using the default, i.e. 3):

.. code-block:: yaml

   url: https://example.com/#default_contextlines

Output:

.. code-block::

   ---------------------------------------------------------------------------
   CHANGED: https://example.com/#default_contextlines
   ---------------------------------------------------------------------------
   --- @   Sat, 01 Oct 2020 00:00:00 +0000
   ... @   Sat, 01 Oct 2020 01:00:00 +0000
   @@ -1,15 +1,15 @@
    This is line 12
    This is line 13
    This is line 14
   -This is line 15
   +This is line fifteen
    This is line 16
    This is line 17
    This is line 18


Optional directives
```````````````````
* ``context_lines`` (int): The number of lines on each side surrounding changes to include in the report (default: 3).
* ``range_info`` (true/false): Whether to include line range information lines (those starting with ``@``) (default:
  true).

.. versionchanged:: 3.21
   Became a standalone differ.
   Added the ``range_info`` directive.
   Added the ``context_line`` directive, which replaces the job directive ``contextlines``.

.. versionadded:: 3.0
   ``contextlines`` (as a job directive)

.. _ai_google_diff:


ai_google
---------
.. versionadded:: 3.21

This differ is currently in BETA and the name and/or directives MAY change in the future, mostly because of the rapid
advances in the technology and the prospect of integrating more generative AI models. Feedback welcomed `here
<https://github.com/mborsetti/webchanges/discussions>`__.

Prefaces a unified diff with a textual summary of changes generated by any of Google's `Gemini Generative AI
models <https://ai.google.dev/gemini-api/docs/models/gemini>`__ called via an API call. This is free of charge
for most developers.

.. important:: Requires a system environment variable ``GOOGLE_AI_API_KEY`` containing the Google Cloud AI Studio
   API Key, which you obtain `here <https://aistudio.google.com/app/apikey>`__ and which itself requires a `Google
   Cloud <https://cloud.google.com/>`__ account. To access a Gemini 1.5 model
   during the `Preview <https://cloud.google.com/products?hl=en#product-launch-stages>`__ period, you may have to
   make a request `here <https://aistudio.google.com/app/waitlist/97445851>`__. Please note that the use of Gemini API
   from a project that has billing enabled is `pay-as-you-go pricing <https://ai.google.dev/pricing>`__. To avoid
   surprises, we recommend you set up your API key on a GCP project without billing or, at a minimum, set up a `budget
   <https://console.cloud.google.com/billing/01457C-2ABCC1-8A6144/budgets>`__ with threshold notification.

.. note:: These models are only available in 38 languages and over 200 regions; see `here
   <https://ai.google.dev/gemini-api/docs/available-regions>`__.

Gemini 1.5 models are the first widely available model with a context window of up to 1 million tokens, which allow
to analyze changes in long documents (up to 350,000 words, or about 700 pages single-spaced) such as terms and
conditions, privacy policies, etc. that other models can't handle. For clarity, these models can handle up to 700,000
words, but to do a comparison we need up to a half of this for the old text and the rest for the new text.

By default, we use the latest stable version of the `Gemini 1.5 Flash
<https://ai.google.dev/gemini-api/docs/models/gemini#gemini-1.5-flash-expandable>`__ model (``gemini-1.5-flash``)
(in `preview <https://cloud.google.com/products?hl=en#product-launch-stages>`__) as
it's faster, allows more concurrency and, if you are on a paid plan, is cheaper.

You can use the ``model`` directive
to specify the latest version (instead of stable version) of this model (``gemini-1.5-flash-latest``) or to use
the more powerful `Gemini 1.5 Pro <https://ai.google.dev/gemini-api/docs/models/gemini#gemini-1.5-pro-expandable>`__
model (``gemini-1.5-pro`` or ``gemini-1.5-pro-latest``). Similarly, you can specify the use of the older Gemini 1.0 Pro
model (``gemini-1.0-pro``), whose access is available to all but which handles a lower number of tokens and is not as
good.

To improve speed and reduce the number of tokens, by default we generate a separate, complete, unified diff which we
feed to the Generative AI model to summarize. See below for a custom prompt that instead feeds both the old data and
the new data to the model asking it to make the comparison.

.. warning:: Generative AI can "hallucinate" (make things up), so **always** double-check the AI-generated summary with
   the accompanying unified diff.

Examples
````````
Using the default ``prompt``, a summary is prefaced to the unified diff:

.. raw:: html

   <embed>
     <div style="padding:12px;margin-bottom:24px;font-family:Roboto,sans-serif;font-size:13px;
     border:1px solid#e1e4e5;background:white;">
     <strong>Summary of Changes:</strong><br><br>
     The provided unified diff shows a single line change:<br><br>
     <ul style="line-height:1.2em">
     <li><strong>Line 1:</strong> The timestamp was updated from
     <span style="font-family:monospace;white-space:pre-wrap">Sat Apr 6 10:46:13 UTC 2024</span> to
     <span style="font-family:monospace;white-space:pre-wrap">Sat Apr 6 10:55:04 UTC 2024</span>. </li>
     </ul>
     <table style="border-collapse:collapse">
     <tr><td style="font-family:monospace;color:darkred">--- @ Sat, 06 Apr 2024 10:46:13 +0000</td></tr>
     <tr><td style="font-family:monospace;color:darkgreen">+++ @ Sat, 06 Apr 2024 10:55:04 +0000</td></tr>
     <tr><td style="background-color:#fbfbfb">@@ -1 +1 @@</td></tr>
     <tr style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through">
       <td>Sat Apr 6 10:46:13 UTC 2024</td>
     </tr>
     <tr style="background-color:#d1ffd1;color:#082b08"><td>Sat Apr 6 10:55:04 UTC 2024</td></tr>
     </table>
     <i><small>
     ---<br>
     Summary generated by Google Generative AI (differ directive(s): model=gemini-1.5-flash)
     </small></i>
     </div>
   </embed>

The job directive below uses a custom ``prompt`` to have the Generative AI make the comparison. This requires a lot
more tokens and time, but may work better in certain cases. More information about writing input prompts for these
models can be found `here <https://ai.google.dev/docs/prompt_best_practices>`__.

.. code-block:: yaml

   command: date
   differ:
     name: ai_google
     prompt: Identify and summarize the changes:\n\n<old>\n{old_data}\n</old>\n\n<new>\n{new_data}\n</new>

Mandatory environment variable
``````````````````````````````
* ``GOOGLE_AI_API_KEY``: Must contain your Google Cloud AI Studio `API Key <https://aistudio.google.com/app/apikey>`__.

Optional directives
```````````````````
This differ is currently in BETA and these directives MAY change in the future.

.. model default is retrievable from
   https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest?key=$GOOGLE_AI_API_KEY

* ``model`` (str): A `model code <https://ai.google.dev/models/gemini>`__ (default: ``gemini-1.5-flash``).
* ``prompt`` (str): The prompt sent to the model; the strings ``{unified_diff}``, ``{old_data}`` and ``{new_data}`` will
  be replaced by the respective content (default: ``Analyze this unified diff and create a summary listing only the
  changes:\n\n{unified_diff}``).
* ``prompt_ud_context_lines`` (int): Number of context lines in the unified diff sent to the model if
  ``{unified_diff}`` is present in the ``prompt`` (default: 999). If the resulting model prompt becomes approximately
  too big for the model to handle, the unified diff will be recalculated with the default number of context lines (3).
  Note that this unified diff is a different one than the diff included in the report itself.
* ``timeout`` (float): The number of seconds before timing out the API call (default: 300).
* ``temperature`` (float between 0.0 and 1.0): The model's Temperature parameter, which controls randomness; higher
  values increase diversity (see note below) (default: 0.0).
* ``top_k`` (int of 1 or greater): The model's TopK parameter, i.e. sample from the k most likely next tokens at
  each step; lower k focuses on higher probability tokens (see note below) (default: model-dependent, but typically 1,
  see Google documentation; not available in ``gemini-1.5-pro-latest``)
* ``top_p`` (float between 0.0 and 1.0): The model's TopP parameter, or the cumulative probability cutoff for token
  selection; lower p means sampling from a smaller, more top-weighted nucleus and reduces diversity (see note below)
  (default: model-dependent, but typically 0.95 or 1.0, see Google documentation)
* ``token_limit`` (int): An override of the maximum size of the model's context window (used for internal testing).
* ``unified`` (dict): directives passed to :ref:`unified differ <unified_diff>`, which prepares the unified diff
  attached to this report.

Directives for the underlying :ref:`unified differ <unified_diff>` can be passed in as key called ```unified``, as
follows:

.. code-block:: yaml

   command: date
   differ:
     name: ai_google
     name: unified
       context_lines: 5
       range_info: false



.. note:: You can learn about Temperature, TopK and TopP parameters `here
   <https://ai.google.dev/docs/concepts#model-parameters>`__. In general, temperature increases creativity and
   diversity in phrasing variety, while top-p and top-k influences variety of individual words with low values leading
   to potentially repetitive summaries. The only way to get these "right" is through experimentation with actual
   data, as the results are highly dependent on it and subjective to your personal preferences.

.. tip:: You can do "dry-runs" of this (or any) differ on an existing job by editing the differ in the job file and
   running e.g. ``webchanges --test-differ 1 --test-reporter browser``. Don't forget to revert your job file if you
   don't like the new outcome!



.. _command_diff:

command
-------
Call an external differ (e.g. wdiff). The old data and new data are written to a temporary file, and the names of the
two files are appended to the command. The external program will have to exit with a status of 0 if no differences
were found, a status of 1 if any differences were found, or any other status for any error.

If ``wdiff`` is used, its output will be colorized when displayed on stdout (typically a screen) and for HTML reports.

For increased legibility, the differ directive ``name`` is not required (``command`` is sufficient).

Example:

.. code-block:: yaml

   url: https://example.net/command.html
   differ:
     command: wdiff

Please see :ref:`important note <important_note_for_command_jobs>` for the file security settings required to run jobs
with this differ in Linux.

.. versionchanged:: 3.21
   Was previously a job sub-directive by the name of ``diff_tool``.

.. _deepdiff_diff:

deepdiff
--------
.. versionadded:: 3.21

Inspects structured data (JSON or XML) on an element by element basis and reports which elements have changed, using a
customized report based on deepdiff's library `DeepDiff
<https://zepworks.com/deepdiff/current/diff.html#module-deepdiff.diff>`__ module.

Examples:

.. code-block:: yaml

   url: https://example.net/deepdiff_json.html
   differ: deepdiff  # defaults to json data


.. code-block:: yaml

   url: https://example.net/deepdiff_xml_ignore_oder.html
   differ:
     name: deepdiff
     data_type: xml
     ignore_order: true

Example diff:

.. raw:: html

   <embed>
   <div style="padding:12px;margin-bottom:24px;font-family:Roboto,sans-serif;font-size:13px;
   border:1px solid#e1e4e5;background:white;"><span style="font-family:monospace;white-space:pre-wrap;font-size:13px;">Differ: deepdiff for json
   <span style="color:darkred">Old Sat, 13 Apr 2024 21:19:36 +0800</span>
   <span style="color:darkgreen">New Sun, 14 Apr 2024 21:24:14 +0800</span>
   ------------------------------------
   • Type of [&#39;Items&#39;][0][&#39;<wbr>CurrentInventory&#39;] changed from int to NoneType and value changed from <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through">&quot;1&quot;</span> to <span style="background-color:#d1ffd1;color:#082b08">None</span>.
   • Type of [&#39;Items&#39;][0][&#39;<wbr>Description&#39;] changed from str to NoneType and value changed from <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through">&quot;Gadget&quot;</span> to <span style="background-color:#d1ffd1;color:#082b08">None</span>.
   </span>
   </div>
   </embed>


Optional directives
```````````````````
* ``data_type`` (``json`` or ``xml``): The type of data being analyzed (default: ``json``).
* ``ignore_order`` (true/false): Whether to ignore the order in which the items have appeared (default: false).
* ``ignore_string_case`` (true/false): Whether to be case-sensitive or not when comparing strings (default: false).
* ``significant_digits`` (int): The number of digits AFTER the decimal point to be used in the comparison (default:
  no limit).

Required packages
`````````````````
To run jobs with this differ, you need to first install :ref:`additional Python packages <optional_packages>` as
follows:

.. code-block:: bash

   pip install --upgrade webchanges[deepdiff]



.. _image_diff:

image
-----
.. versionadded:: 3.21

This differ is currently in BETA, mostly because it's unclear what more needs to be changed or parametrized in order
to make the differ work with a vast variety of images. Feedback welcomed `here
<https://github.com/mborsetti/webchanges/discussions>`__.

Highlights changes in an image by overlaying them in yellow on a greyscale version of the original image. Only works
with HTML reports.

.. code-block:: yaml

   url: https://example.net/image.html
   differ:
     name: image
     data_type: url

Optional directives
```````````````````
This differ is currently in BETA and the directives may change in the future.

* ``data_type`` (``url``, ``filename``, ``ascii85`` or ``base64``): The type of data to process: a link to the image,
  the path to the file containing the image, or the image itself encoded as `Ascii85
  <https://en.wikipedia.org/wiki/Ascii85>`__ or `RFC 4648 <https://datatracker.ietf.org/doc/html/rfc4648.html>`__
  `Base_64 <https://en.wikipedia.org/wiki/Base64>`__ text (default: ``url``).
* ``mse_threshold`` (float): The minimum mean squared error (MSE) between two images to consider them changed;
  requires the package ``numpy`` to be installed (default: 2.5).

.. note:: If you pass a ``url`` or ``filename`` to the differ, it will detect changes only if the url or
  filename changes, not if the image behind the url/filename does; no change will be reported if the url or filename
  changes but the image doesn't. To detect changes in an image when the url or filename doesn't change, build a job
  that captures the image itself encoded in Ascii85 (preferably, see the :ref:`ascii85` filter) or Base64 and set
  ``data_type`` accordingly.

Required packages
`````````````````
To run jobs with this differ, you need to first install :ref:`additional Python packages <optional_packages>` as
follows:

.. code-block:: bash

   pip install --upgrade webchanges[imagediff]

In addition, you can only run it with a default configuration of :program:webchanges:, which installsthe
``httpx`` HTTP Client library; ``requests`` is not supported.



.. _table_diff:

table
-----
Similar to :ref:`unified <unified_diff>`, it performs a line-by-line comparison and reports lines that have been added,
deleted, or changed, but the HTML table format produced by Python's `difflib.HtmlDiff
<https://docs.python.org/3/library/difflib.html#difflib.HtmlDiff>`__. Example output:

.. raw:: html

   <embed>
     <style>
        .diff { border: 2px solid; }
        .diff_add { color: green; background-color: lightgreen; }
        .diff_sub { color: red; background-color: lightred; }
        .diff_chg { color: orange; background-color: lightyellow; }
     </style>
     <!-- Created in Python 3.12 -->
     <div style="padding:12px;margin-bottom:24px;font-family:Roboto,sans-serif;font-size:13px;
     border:1px solid#e1e4e5;background:white;">
     <table class="diff" id="difflib_chg_to0__top" cellspacing="0" cellpadding="0" rules="groups" >
       <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
       <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
       <tbody>
       <tr>
         <td class="diff_next" id="difflib_chg_to0__1"><a href="#difflib_chg_to0__0">f</a></td>
         <td class="diff_header" id="from0_1">1</td>
         <td nowrap="nowrap">This&nbsp;line&nbsp;is&nbsp;the&nbsp;same</td>
         <td class="diff_next"><a href="#difflib_chg_to0__0">f</a></td>
         <td class="diff_header" id="to0_1">1</td>
         <td nowrap="nowrap">This&nbsp;line&nbsp;is&nbsp;the&nbsp;same</td>
       </tr>
       <tr>
         <td class="diff_next"><a href="#difflib_chg_to0__1">n</a></td>
         <td class="diff_header" id="from0_2">2</td>
         <td nowrap="nowrap"><span class="diff_sub">This&nbsp;line&nbsp;is&nbsp;in&nbsp;the&nbsp;left&nbsp;file&nbsp;but&nbsp;not&nbsp;the&nbsp;right</span></td>
         <td class="diff_next"><a href="#difflib_chg_to0__1">n</a></td>
         <td class="diff_header"></td>
         <td nowrap="nowrap"></td>
       </tr>
       <tr>
         <td class="diff_next"></td>
         <td class="diff_header" id="from0_3">3</td>
         <td nowrap="nowrap">Another&nbsp;line&nbsp;that&nbsp;is&nbsp;the&nbsp;same</td>
         <td class="diff_next"></td>
         <td class="diff_header" id="to0_2">2</td>
         <td nowrap="nowrap">Another&nbsp;line&nbsp;that&nbsp;is&nbsp;the&nbsp;same</td>
       </tr>
       <tr>
         <td class="diff_next"><a href="#difflib_chg_to0__top">t</a></td>
         <td class="diff_header"></td>
         <td nowrap="nowrap"></td>
         <td class="diff_next"><a href="#difflib_chg_to0__top">t</a></td>
         <td class="diff_header" id="to0_3">3</td>
         <td nowrap="nowrap"><span class="diff_add">This&nbsp;line&nbsp;is&nbsp;in&nbsp;the&nbsp;right&nbsp;file&nbsp;but&nbsp;not&nbsp;the&nbsp;left</span></td>
       </tr>
       </tbody>
    </table>
    </div>
   </embed>

For backwards compatibility, this is the default differ for an ``html`` reporter with the configuration setting
``diff`` (deprecated) set to ``html``.

.. code-block:: yaml

   url: https://example.net/table.html
   differ: table

Optional directives
```````````````````
* ``tabsize``: Tab stop spacing (default: 8).

.. versionchanged:: 3.21
   Became a standalone differ (previously only accessible through configuration file settings).
   Added the ``tabsize`` directive.
