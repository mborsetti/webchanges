Changed
-------
* The filter ``format-json`` will no longer raise an error when it is not fed JSON data to facilitate
  troubleshooting, and will now report the JSONDecodeError details and the full string causing this.
* Documentation for the ``css`` and ``xml`` filters has been split into two separate entries for ease of reference.
* Minor word editing of error messages to improve clarity.
* Various updates to the differ ``ai_google`` (BETA):

  - ``top_p`` is set to 1.0 if ``temperature`` is 0.0 (its default value) to eliminate randomness in results.
  - Wordsmitting of the default system prompt leading to small improvements.
  - The footnote now shows the model actually used vs. the one specified in the ``model`` sub-directive, useful when
    omitting the version when using an experimental version (e.g. specifying ``gemini-2.0-pro-exp`` instead of
    ``gemini-2.0-pro-exp-02-05``).

Internals
---------
* Tested the ``image`` differ's ``ai_google`` directive (ALPHA, undocumented), which uses GenAI to summarize
  differences between two images, with the new ``gemini-2.0-pro-exp-02-05`` `experimental
  <https://ai.google.dev/gemini-api/docs/models/experimental-models#available-models>`__ and improved default system
  prompt. While the new model shows improvements by producing a plausible-sounding summary instead of gibberish, the
  summary is highly inaccurate and therefore unusable. Development paused again until model accuracy improves.
