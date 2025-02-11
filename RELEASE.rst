Changed
-------
* Differ ``ai_google`` (BETA) now defaults to using the newer ``gemini-2.0-flash`` GenAI model, as it performs better.
  Please note that this model "only" handles 1,048,576 input tokens: if you require the full 2M tokens, manually revert
  to using the ``gemini-1.5-pro`` GenAI model or try the newer ``gemini-2.0-pro-exp-02-05`` `experimental
  <https://ai.google.dev/gemini-api/docs/models/experimental-models#available-models>`__ one.

Fixed
-----
* Fixed bug introduced in 3.28.0 throwing an Exception when reading a configuration file that does not contain the new
  directive ``differ_defaults``. Thanks `yubiuser <https://github.com/yubiuser>`__ for
  reporting this in `issue #93 <https://github.com/mborsetti/webchanges/issues/93>`__.

Internals
---------
* When running with ``-verbose``, no longer logs an INFO message for the internal exception raised when receiving a
  an HTTP 304 status code "Not Modified".
