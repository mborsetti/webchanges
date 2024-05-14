⚠ Breaking Changes
------------------
* The ``ai-google`` (BETA) differ now defaults to using the new ``gemini-1.5-flash`` model (see documentation `here
  <https://ai.google.dev/gemini-api/docs/models/gemini#gemini-1.5-flash-expandable>`__), as it still supports
  1M tokens, "excels at summarization" (per `here <https://blog
  .google/technology/ai/google-gemini-update-flash-ai-assistant-io-2024/#gemini-model-updates:~:text=1
  .5%20flash%20excels%20at%20summarization%2C>`__), allows for a higher number of requests per minute (in the
  free version, 15 vs. 2 of ``gemini-1.5-pro``), is faster, and, if you're paying for it, cheaper. To continue to
  use ``gemini-1.5-pro``, which may produce more "complex" results, specify it in the job's ``differ`` directive.

Fixed
-----
* Fixed header of ``deepdiff`` and ``image`` (BETA) differs to be more consistent with the default ``unified`` differ.
* Fixed the way images are handled in the email reporter so that they now display correctly in clients such as Gmail.

Internals
---------
* Command line argument ``--test-differs`` now processes the new ``mime_type`` attribute correctly (``mime_type`` is
  an internal work in progress attribute to facilitate future automation of filtering, diffing, and reporting).
