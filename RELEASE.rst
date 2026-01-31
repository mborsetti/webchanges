Added
`````
* ``ai_google`` differ has new ``thinking_level`` and ``media_resolution`` sub-directives.
* ``command`` differ has a new ``context_lines`` sub-directive for commands starting with wdiff for backwards 
  compatibility (but use the built-in ``wdiff`` differ instead).

Changed
```````
* ``ai_google`` differ is no longer considered BETA.
* Improved logging for the ``evaluate`` directive in URL Jobs with ``browser: true``.
* ``--dump-history JOB`` command line argument will now match any job, even one that is not in the ``--jobs`` file.

Fixed
`````
* Regression: ``http_ignore_error_codes`` not being applied to ``TransientHTTPError`` Exceptions such as '429 Too Many
  Requests' (issue #`119 <https://github.com/mborsetti/webchanges/issues/119>`__).
* ``http_credentials`` directive not being applied to URL jobs with ``browser: true`` and ``user_data_dir``.
* When running with command line argument ``-vv``, browser pages will open with DevTools open.
* Problem parsing Playwright exceptions in BrowserJob class retrieve method  (issue #`141 
  <https://github.com/mborsetti/webchanges/issues/141>`__)..

Internals for ``hooks.py``
``````````````````````````
* The BrowserJob class' ``retrieve`` method has been modularized, and exposes ``response_handler`` (a callable which 
  replaces the built-in page.goto() directive), ``content_handler`` (a callable which replaces the built-in content 
  extractor from the Page),  and ``return_data`` (a callable which replaces all of the built-in functionality after 
  the browser is launched).`

Internals
`````````
* Code type checking is now performed using ``ty`` instead of ``mypy``.
* Improved logging and the saving of snapshots when a browsing error is encountered for URL jobs with ``browser: true``.
