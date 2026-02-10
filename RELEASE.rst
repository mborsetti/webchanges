Added
``````
* New reporter ``github_issue`` creates a GitHub issue for changes detected.

  - Kindly contributed by `Dmitry Vasiliev <https://github.com/swimmwatch>`__ in `#105
    <https://github.com/mborsetti/webchanges/issues/105>`__.
  - Implemented as a GitHub Action ``webchanges-action`` available `here
    <https://github.com/swimmwatch/webchanges-action>`__.

* The ``wdiff`` filter now handles ``html`` text.
* New ``suppress_error_ended`` and ``suppress_errors``` Job sub-directives to control error notifications job-by-job.

  - Suggested by `Marcos Alano <https://github.com/mhalano>`__ in `#101
    <https://github.com/mborsetti/webchanges/issues/101>`__.

* New ``ntfy`` reporter to support `ntfy <https://ntfy.sh>`__ (pronounced _notify_), an open-source fee simple
  HTTP-based `pub-sub <https://en.wikipedia.org/wiki/Publish%E2%80%93subscribe_pattern>`__ notification service (also
  for upstream compatibility).
* Filters ``execute`` and ``shellpipe`` now have an ``escape_characters`` sub-directive to automatically escape Windows
  command caracters (e.g. ``%`` becomes ``%%``, ``!`` becomes ``^!``, etc.).

Fixed
`````
* All databases, keep-alive connections, and underlying SSL sockets are now closed correctly before exit. Fixes the
  ``ResourceWarning: unclosed database`` and ``ResourceWarning: <ssl.SSLSocket>`` messages when run with environment
  variable ``PYTHONWARNINGS=all``.
