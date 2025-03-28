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
  - :ref:`command <command_diff>`: Executes an outside command that acts as a differ;
  - :ref:`deepdiff <deepdiff_diff>`: Compares structured data (JSON or XML) element-by-element;
  - :ref:`table <table_diff>`: A Python version of the :ref:`unified <unified_diff>` differ where the changes are
    displayed as an HTML table;
  - :ref:`wdiff <wdiff_diff>`: Compares data word-by-word, highlighting changed words and maintaining line breaks.

In addition, the following BETA differs are available:

  - :ref:`ai_google <ai_google_diff>`: Detects and summarizes changes using Generative AI (free API key required);
  - :ref:`image <image_diff>`: Detects changes in an image and displays them as overlay over a grayscale version of the
    old image.


A differ is specified using the job directive ``differ``. To select a differ with its default directive values, simply
use the name of the differ as the directive's value:

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
This is the default differ used when the ``differ`` job directive is not specified (except, for backward compatibility,
when in the configration file the ``html`` report has the deprecated ``diff`` key set to ``table``).

It does a line-by-line comparison of the data  and reports lines that have been added (:additions:`+`), deleted
(:deletions:`-`), or changed. Changed lines are displayed twice: once marked as "deleted" (:deletions:`-`)
representing the old content, and once as "added" (:additions:`+`) representing the new content. Results are
displayed in the `unified format <https://en.wikipedia.org/wiki/Diff#Unified_format>`__ (the "*unified diff*").

For HTML reports, :program:`webchanges` colorizes the unified diff for easier legibility.

Examples
````````
Using default settings:

.. code-block:: yaml

   url: https://example.net/unified.html
   differ: unified  # this can also be omitted as it's the default


Range information lines
:::::::::::::::::::::::

Range information lines (those starting with ``@@``) can be suppressed using ``range_info: false``:

.. code-block:: yaml

   url: https://example.net/unified_no_range.html
   differ:
     name: unified
     range_info: false

.. _contextlines:

Context lines
:::::::::::::

The ``context_lines`` directive causes a unified diff to have a set number of context lines that might be different from
Python's default of 3 (or 0 if the job contains ``additions_only: true`` or ``deletions_only: true``).

Example using 5 context lines:

.. code-block:: yaml

   url: https://example.com/#lots_of_contextlines
   differ:
     name: unified
     context_lines: 5

Output:

.. raw:: html

  <embed>
  <div class="output-box-mono">---------------------------------------------------------------------------
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
  </div>
  <embed>

The same example using the default number of context lines, i.e. 3:

.. code-block:: yaml

   url: https://example.com/#default_contextlines

Output:

.. raw:: html

   <embed>
   <div class="output-box-mono">---------------------------------------------------------------------------
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
   </div>
   <embed>

Optional directives
```````````````````
* ``context_lines`` (int): The number of lines on each side surrounding changes to include in the report (default: 3).
* ``range_info`` (true/false): Whether to include line range information lines (those starting with ``@``) (default:
  true).

.. versionchanged:: 3.21
   Became a standalone differ. Added the ``range_info`` and ``context_line`` directives, the latter replacing the
   job directive ``contextlines`` (added in version 3.0).


.. _ai_google_diff:

ai_google
---------
.. versionadded:: 3.21
   as BETA.

.. note:: This differ is currently in BETA and the name and/or directives MAY change in the future, mostly because of
   the rapid advances in the technology and the prospect of integrating more generative AI models. Feedback welcomed
   `here <https://github.com/mborsetti/webchanges/discussions>`__.

Prefaces a unified diff with a textual summary of changes generated by any of Google's `Gemini Generative AI
models <https://ai.google.dev/gemini-api/docs/models/gemini>`__ called via an API call. This can be free of charge
for most developers.

Gemini models are the first widely available models with a large context window (currently 2 million tokens),
which allow to analyze changes in long documents (of 700,000 words, or about 1,400 pages single-spaced) such as terms
and conditions, privacy policies, etc. that other models can't handle. For clarity, these models can handle
approximately 1,400,000 words, but to do a full comparison we need a half of this for the old text and the other
half for the changed text.

.. important:: Requires a system environment variable ``GOOGLE_AI_API_KEY`` containing the Google Cloud AI Studio
   API Key, which you obtain `here <https://aistudio.google.com/app/apikey>`__ and which itself requires a `Google
   Cloud <https://cloud.google.com/>`__ account.

.. warning:: Gemini developer models are free only on the **free of charge plan**, which you obtain by creating an API
   key from a Google Cloud project with `billing disabled
   <https://cloud.google.com/billing/docs/how-to/modify-project#disable_billing_for_a_project>`__. Most jobs should
   work within free plan; if not, we highly recommend that you set up a `budget
   <https://console.cloud.google.com/billing/01457C-2ABCC1-8A6144/budgets>`__ with threshold notification enabled to
   avoid any expensive surprises!

By default, we specify the latest version of the `Gemini 2.0 Flash
<https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-flash>`__ model (``gemini-2.0-flash``) as it's faster
than Pro, allows more concurrency, and if you are on a paid plan, is `cheaper
<https://ai.google.dev/gemini-api/docs/pricing>`__; however, note that it has a context window of 1 million tokens (max
document size of approx 350,000 words, or about 700 pages single-spaced). For larger applications you can use the
``model`` directive to specify another `model <https://ai.google.dev/models/gemini>`__, such as the more powerful
`Gemini 1.5 Pro <https://ai.google.dev/gemini-api/docs/models/gemini#gemini-1.5-pro>`__ with a context window of 2
million tokens (``model: gemini-1.5-pro-latest``). The full list of models available is `here
<https://ai.google.dev/gemini-api/docs/models/gemini>`__. You can manually evaluate responses side-by-side across the
various models using the tools `here <https://aistudio.google.com/app/prompts/new_comparison>`__.

You can also set the default model in the :ref:`configuration <configuration>` file as follows:

.. code-block:: yaml

   differ_defaults:
     _note: Default directives that are applied to individual differs.
     unified: {}
     ai_google:
       model: gemini-2.5-pro-exp
     command: {}
     deepdiff: {}
     image: {}
     table: {}
     wdiff: {}


.. note:: These models work with `38 languages
   <https://ai.google.dev/gemini-api/docs/models/gemini#available-languages>`__ and are available in over `200 countries
   and territories <https://ai.google.dev/gemini-api/docs/available-regions>`__.

.. To improve speed and reduce the number of tokens, by default we generate a separate, complete, unified diff which we
   feed to the Generative AI model to summarize. See below for a custom prompt that instead feeds both the old data and
   the new data to the model asking it to make the comparison.

.. warning:: Generative AI can "hallucinate" (make things up), so **always** double-check the AI-generated summary with
   the accompanying unified diff.

The default prompt asks the Generative AI model make the comparison (see below for default prompt). However, to save
tokens and time (and potentially $), you might want the model to only summarize the differences from a unified diff
by using a prompt similar to the one here:

.. code-block to column ~103 only; beyond has horizontal scroll bar
   1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123

.. code-block:: yaml

   differ:
     name: ai_google
     prompt: >-
       Describe the differences between the two versions of text as summarized in this unified diff,
       highlighting the most significant modifications:\n\n{unified_diff}

More information about writing input prompts for these models can be found `here
<https://ai.google.dev/gemini-api/docs/prompting-intro>`__. You may also use the "Help me write"
function in `AI Vertex Vertex Prompt <https://console.cloud.google.com/vertex-ai/studio/freeform>`__ or
ask the model itself (in `AI Studio <https://aistudio.google.com/>`__) to suggest prompts that are appropriate to your
use case.

Example
```````
Using the default ``prompt``, a summary is prefaced to a unified diff:

.. raw:: html

   <embed>
     <div class="output-box">
     The new version simply updates the time from 00:00:00 UTC to 01:00:00 UTC. This represents a difference of 1 hour.<br><br>
     <table style="border-collapse:collapse">
     <tr><td style="font-family:monospace;color:darkred">--- @ Sat, 01 Oct 2020 00:00:00 +0000</td></tr>
     <tr><td style="font-family:monospace;color:darkgreen">+++ @ Sat, 01 Oct 2020 01:00:00 +0000</td></tr>
     <tr><td style="background-color:#fbfbfb">@@ -1 +1 @@</td></tr>
     <tr style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through">
       <td>Sat Oct 1 00:00:00 UTC 2020</td>
     </tr>
     <tr style="background-color:#d1ffd1;color:#082b08"><td>Sat Oct 1 01:00:00 UTC 2020</td></tr>
     </table>
     <i><small>
     ---<br>
     Summary generated by Google Generative AI (differ directive(s): model=gemini-2.0-flash)
     </small></i>
     </div>
   </embed>

.. tip:: You can do "dry-runs" of this (or any) differ on an existing job by editing the differ in the job file and
   running e.g. ``webchanges --test-differ 1 --test-reporter browser``. Don't forget to revert your job file if you
   don't like the new outcome!

Mandatory environment variable
``````````````````````````````
* ``GOOGLE_AI_API_KEY``: Must contain your Google Cloud AI Studio `API Key <https://aistudio.google.com/app/apikey>`__.

Optional directives
```````````````````
This differ is currently in BETA and these directives MAY change in the future.

* ``model`` (str): A `model code <https://ai.google.dev/gemini-api/docs/models/gemini>`__ (default:
  ``gemini-2.0-flash``).
* ``system_instructions``: Optional tone and style instructions for the model (default: see below).
* ``prompt`` (str): The prompt sent to the model; the strings ``{unified_diff}``, ``{unified_diff_new}``,
  ``{old_text}`` and ``{new_text}`` will be replaced by the respective content; Any ``\n`` in the prompt will be
  replaced by a newline (default: see below).
* ``timeout`` (float): The number of seconds before timing out the API call (default: 300).

Data to diff
::::::::::::

* ``additions_only`` (bool): provide a summary of only the new text (i.e. the lines added per unified diff).
* ``prompt_ud_context_lines`` (int): if ``{unified_diff}`` is present in the ``prompt``, the number of context lines in
  the unified diff sent to the model (default: 999). If the resulting model prompt becomes approximately
  too big for the model to handle, the unified diff will be recalculated with the default number of context lines (3).
  Note that this unified diff is a different one than the diff included in the report itself.

Model tuning
::::::::::::

.. model defaults are retrievable from
   https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash?key=$GOOGLE_AI_API_KEY

* ``temperature`` (float between 0.0 and 2.0): The model's Temperature parameter, which controls randomness; higher
  values increase diversity (default: 0.0).
* ``top_k`` (int of 1 or greater): The model's TopK parameter, i.e. k most likely next tokens to sample from at
  each step. Lower k focuses on higher probability tokens (default: model-dependent, but typically 1; see
  `model documentation <https://ai.google.dev/gemini-api/docs/models/gemini>`__).
* ``top_p`` (float between 0.0 and 1.0): The model's TopP parameter, or the cumulative probability cutoff for token
  selection. Lower p means sampling from a smaller, more top-weighted nucleus and reduces diversity (default: 1.0 if
  ``temperature`` is 0.0 (default), otherwise model-dependent, but typically 0.95 or 1.0; see `model documentation
  <https://ai.google.dev/gemini-api/docs/models/gemini>`__).
* ``tools`` (list): Data passed on to the API's 'tool' field, for example to ground the response (see `here
  <https://ai.google.dev/api/caching#Tool>`__).

.. note:: You can learn about Temperature, TopK and TopP parameters `here
   <https://ai.google.dev/gemini-api/docs/models/generative-models#model-parameters>`__. In general, temperature
   increases creativity and diversity in phrasing variety, while top-p and top-k influences variety of individual
   words with low values leading to potentially repetitive summaries. The only way to get these "right" is through
   experimentation with actual data, as the results are highly dependent on the input and subjective to your personal
   preferences.

Underlying unified diff
:::::::::::::::::::::::

* ``unified`` (dict): Directives passed to :ref:`unified differ <unified_diff>`, which prepares the unified diff
  attached to this report.  Example:

.. code-block:: yaml

   command: date
   differ:
     name: ai_google
     unified:
       context_lines: 5
       range_info: false


Default system instructions and prompts:
::::::::::::::::::::::::::::::::::::::::

Special variables for prompt
............................
When present in the prompt text, the following will be replaced:

* ``{old_text}``: Replaced with the old text.
* ``{new_text}``: Replaced with the new (currently retrieved) text.
* ``{unified_diff}``: Replaced with a unified_diff, with 999 context lines unless changed by
  ``prompt_ud_context_lines`` (see above).
* ``{unified_diff_new}`` Replaced with the added lines from the unified_diff, with the initial ``+`` stripped
  (e.g. roughly the new text).


Default
.......

System instructions
'''''''''''''''''''
   You are a skilled journalist tasked with analyzing two versions of a text and summarizing the key differences in
   meaning between them. The audience for your summary is already familiar with the text's content, so you can focus on
   the most significant changes.

   **Instructions:**

   1. Carefully examine the old version of the text, provided within the ``<old_version>`` and ``</old_version>`` tags.
   2. Carefully examine the new version of the text, provided within the ``<new_version>`` and ``</new_version>`` tags.
   3. Compare the two versions, identifying areas where the meaning differs. This includes additions, removals, or
      alterations that change the intended message or interpretation.
   4. Ignore changes that do not affect the overall meaning, even if the wording has been modified.
   5. Summarize the identified differences, except those ignored, in a clear and concise manner, explaining how the
      meaning has shifted or evolved in the new version compared to the old version only when necessary. Be specific
      and provide examples to illustrate your points when needed.
   6. If there are only additions to the text, then summarize the additions.
   7. Use Markdown formatting to structure your summary effectively. Use headings, bullet points, and other Markdown
      elements as needed to enhance readability.
   8. Restrict your analysis and summary to the information provided within the ``<old_version>`` and ``<new_version>``
      tags. Do not introduce external information or assumptions.

Prompt
''''''
   <old_version>
   {old_text}
   </old_version>

   <new_version>
   {new_text}
   </new_version>


With ``additions_only``
.......................

System instructions
'''''''''''''''''''
   You are a skilled journalist. Your task is to summarize the provided text in a clear and concise manner.  Restrict
   your analysis and summary *only* to the text provided. Do not introduce any external information or assumptions.

   Format your summary using Markdown. Use headings, bullet points, and other Markdown elements where appropriate to
   create a well-structured and easily readable summary.

Prompt
''''''
   {unified_diff_new}


.. versionchanged::
   No detail changes are tracked here as the differ is BETA; please refer to the :ref:`changelog`.



.. _command_diff:

command
-------
Call an external differ. The old data and new data are written to a temporary file, and the names of the
two files are appended to the command. The external program will have to exit with a status of 0 if no differences
are found, a status of 1 if any differences are found, or any other status to signify an error (mimicking wdiff's
behavior).

If your differ outputs HTML, you should set ``is_html`` is true.

Although we recommend you use the built-in :ref:`wdiff_diff` differ for word-by-word diffing, if ``wdiff`` is called
its output will be colorized when displayed on stdout (typically a screen) and for HTML reports.

.. tip:: Use the job directive :ref:`monospace` if you want to use a monospace font in the report.

Example
```````

.. code-block:: yaml

   url: https://example.net/command.html
   differ:
     name: command
     command: python mycustomscript.py
     is_html: true  # if the custom differ outputs HTML

.. note:: See :ref:`this note <important_note_for_command_jobs>` for the file security settings required to
   run jobs with this differ in Linux.

.. versionchanged:: 3.21
   Was previously a job sub-directive by the name of ``diff_tool``.

.. versionchanged:: 3.29
   Added ``is_html`` directive.


Required directives
```````````````````
* ``command``: The command to execute.

Optional directives
```````````````````
* ``is_html`` (true/false): Whether the output of the command is HTML, for correct formatting in reports (default:
  false).

.. versionchanged:: 3.29
   Added ``is_html`` sub-directive.



.. _deepdiff_diff:

deepdiff
--------
.. versionadded:: 3.21

Inspects structured data (JSON, YAML, or XML) on an element by element basis and reports which elements have changed,
using a customized report based on deepdiff's library `DeepDiff
<https://zepworks.com/deepdiff/current/diff.html#module-deepdiff.diff>`__ module.

Examples
````````

.. code-block:: yaml

   url: https://example.net/deepdiff_json.html
   differ: deepdiff


.. code-block:: yaml

   url: https://example.net/deepdiff_xml_ignore_oder.html
   differ:
     name: deepdiff
     data_type: xml  # override deriving this from data/MIME type or, if unable, json default
     ignore_order: true

Output:

.. raw:: html

   <embed>
   <div class="output-box-mono">Differ: deepdiff for json
   <span style="color:darkred">Old 01 Oct 2020 00:00:00 +0000</span>
   <span style="color:darkgreen">New 01 Oct 2020 01:00:00 +0000</span>
   • Type of [&#39;Items&#39;][0][&#39;<wbr>CurrentInventory&#39;] changed from int to NoneType and value changed from <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through">&quot;1&quot;</span> to <span style="background-color:#d1ffd1;color:#082b08">None</span>.
   • Type of [&#39;Items&#39;][0][&#39;<wbr>Description&#39;] changed from str to NoneType and value changed from <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through">&quot;Gadget&quot;</span> to <span style="background-color:#d1ffd1;color:#082b08">None</span>.
   </div>
   </embed>


Optional directives
```````````````````
* ``data_type`` (``json``, ``yaml``, or ``xml``): The type of data being analyzed if different than the data's media
  type (fka MIME type), defaulting to ``json`` if unable to derive.
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

.. versionchanged:: 3.31
   Added support for YAML data.



.. _image_diff:

image
-----
.. versionadded:: 3.21
   As BETA.

.. note:: This differ is currently in BETA, mostly because it's unclear what more needs to be developed, changed or
   parametrized in order to make the differ work with the vast variety of images. Feedback welcomed `here
   <https://github.com/mborsetti/webchanges/discussions>`__.

Highlights changes in an image by overlaying them in yellow on a greyscale version of the original image. Only works
with HTML reports.

Examples
````````

Monitor a URL of an image directly, and see if the image changes:

.. code-block:: yaml

   url: https://sources.example.net/productimage.jpg
   filter:
     - ascii85
   differ:
     name: image
     data_type: ascii85


Extract an image URL from an HTML <img> tag and monitor if this URL changes:

.. code-block:: yaml

   url: https://www.example.net/productpage.html
   filter:
     - xpath: //div[@class="image"]/img/@src
   differ:
     name: image
     data_type: url

Optional directives
```````````````````
This differ is currently in BETA and these directives may change in the future.

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

In addition, you can only run it with a default configuration of :program:webchanges:, which installs the
``httpx`` HTTP client library; ``requests`` is not supported.



.. _table_diff:

table
-----
Similar to :ref:`unified <unified_diff>`, it performs a line-by-line comparison and reports lines that have been added,
deleted, or changed, but the HTML table format produced by Python's `difflib.HtmlDiff
<https://docs.python.org/3/library/difflib.html#difflib.HtmlDiff>`__.

Example
```````
.. code-block:: yaml

   url: https://example.net/table.html
   differ: table


Output:

.. raw:: html

   <embed>
     <style>
        .diff { border: 2px solid; }
        .diff_add { color: green; background-color: lightgreen; }
        .diff_sub { color: red; background-color: lightred; }
        .diff_chg { color: orange; background-color: lightyellow; }
     </style>
     <div class="output-box">
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

Example:

.. code-block:: yaml

   url: https://example.net/table.html
   differ: table

Optional directives
```````````````````
* ``tabsize``: Tab stop spacing (default: 8).

.. versionchanged:: 3.21
   Became a standalone differ (previously only accessible through configuration file settings).
   Added the ``tabsize`` directive.


.. _wdiff_diff:

wdiff
-----
.. versionadded:: 3.24

Performs a word-by-word comparison highlighting words that have been added (:additions:`added`) or deleted
(:deletions:`deleted`). Changed words are displayed twice: once marked as "deleted" (:deletions:`deleted`)
representing the old word(s), and the new word(s) as "added" (:additions:`added`). Line breaks are maintained.

It is similar to `GNU's Wdiff <https://www.gnu.org/software/wdiff/>`__, but requires no external dependency.

When unchanged lines are skipped, they are reported using ``@@``. For example, ``@@ 1...22 @@`` means that lines 1 to
22 are skipped from the report as they are unchanged.

Example
```````

.. code-block:: yaml

   command: The time now is %time% UTC  # Windows
   differ: wdiff

Output:

.. raw:: html

   <embed>
     <div class="output-box">
     <span style="font-family:monospace">Differ: wdiff<br>
     <span style="color:darkred">--- @ Sat, 01 Oct 2020 00:00:00 +0000</span><br>
     <span style="color:darkgreen">+++ @ Sat, 01 Oct 2020 01:00:00 +0000</span><br>
     The time now is <span style="background-color:#fff0f0;color:#9c1c1c;text-decoration:line-through">
     00:00:00.00</span>
     <span style="background-color:#d1ffd1;color:#082b08">01:00:00.00</span> UTC</span>
     <hr style="margin-top:0.5em;margin-bottom:0.5em">
     <span style="font-style:italic">Checked 1 source in 0.1 seconds with <a href="https://pypi.org/project/webchanges/" target="_blank">webchanges</a>.</span>
     </div>
   </embed>

Optional directives
```````````````````
* ``context_lines``: The number of context lines on each side of changes to provide surrounding content to
  better understand the changes (default: 3).
* ``range_info``: Include range information lines for unreported lines (default: true).
