Added
-------------------
* Multiple job files or glob patterns can now be specified by repeating the ``--jobs`` argument.
* Job list filtering using `Python regular expression
  <https://docs.python.org/3/library/re.html#regular-expression-syntax>`__. Example: ``webchanges --list blue`` lists
  jobs with 'blue' in their name (case-sensitive, so not 'Blue'), while ``webchanges --list (?i)blue`` is
  `case-insensitive <https://docs.python.org/3/library/re.html#re.I>`__.
* New URL job directive ``params`` for specifying URL parameters (query strings), e.g. as a dictionary.
* New ``gotify`` reporter (upstream contribution: `link <https://github.com/thp/urlwatch/pull/823/files>`__).
* Improved messaging at startup when a legacy database that requires conversion is found.

Changed
-------------------
* Updated ``ai_google`` differ to reflect Gemini 1.5 Pro's 2M token context window.

Fixed
-------------------
* Corrected the automated handling in differs and reporters of data with a 'text/markdown' MIME type.
* Multiple ``wdiff`` differ fixes and improvements:
  - Fixed body font issues;
  - Removed spurious ``^\n`` insertions;
  - Corrected ``range_info`` lines;
  - Added word break opportunities (``<wbr>``) in HTML output for better browser handling of long lines.
* ``deepdiff`` differ now breaks a list into its individual elements.
* Improved URL matching for jobs by normalizing %xx escapes and plus signs (e.g. ``https://www.example.org/El Niño``
  will now match ``https://www.example.org/El+Ni%C3%B1o`` and vice versa).
* Improved the text-to-HTML URL parser to accurately extract URLs with multiple parameters.

Internals
-------------------
* Replaced ``requests.structures.CaseInsensitiveDict`` with ``httpx.Headers`` as the Class holding headers.
* The ``Job.headers`` attribute is now initialized with an empty ``httpx.Headers`` object instead of None.
