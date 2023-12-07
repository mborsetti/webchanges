Added
-----
* The HTTP/2 network protocol (the same used by major browsers) is now used in ``url`` jobs. This allows the
  monitoring of certain websites who block requests made with older protocols like HTTP/1.1. This is implemented by
  using the ``HTTPX`` and ``h2`` HTTP client libraries instead of the ``requests`` one used previously.

  Notes:

  - Handling of data served by sites whose encoding is misconfigured is done slightly differently by ``HTTPX``, and if
    you newly encounter instances where extended characters are rendered as ``�`` try adding ``encoding:
    ISO-8859-1`` to that job.
  - To revert to the use of the ``requests`` HTTP client library, use the new job sub-directive ``http_client:
    requests`` (in individual jobs or in the configuration file for all ``url`` jobs) and install ``requests`` by
    running ``pip install --upgrade webchanges[requests]``.
  - If the system is misconfigured and the ``HTTPX`` HTTP client library is not found, an attempt to use the
    ``requests`` one will be made. This behaviour is transitional and will be removed in the future.
  - HTTP/2 is theoretically faster than HTTP/1.1 and preliminary testing confirmed this.

* New ``pypdf`` filter to convert pdf to text **without having to separately install OS dependencies**. If you're
  using ``pdf2text`` (and its OS dependencies), I suggest you switch to ``pypdf`` as it's much faster; however do note
  that the ``raw`` and ``physical`` sub-directives are not supported. Install the required library by running ``pip
  install --upgrade webchanges[pypdf]``.
* New ``absolute_links`` filter to convert relative links in HTML ``<a>`` tags to absolute ones. This filter is not
  needed if you are already using the ``beautify`` or ``html2text`` filters. Requested by **pawelpbm** in issue #62.
* New ``{jobs_files}`` substitution for the ``subject`` of the ``email`` reporter. This will be replaced by the
  name of the jobs file(s) different than the default ``jobs.yaml`` in parentheses, with a prefix of ``jobs-`` in the
  name removed. To use, replace the ``subject`` line for your reporter(s) in ``config.yaml`` with e.g. ``[webchanges]
  {count} changes{jobs_files}: {jobs}``.
* ``html`` reports now have a configurable ``title`` to set the HTML document title, defaulting to
  ``[webchanges] {count} changes{jobs_files}: {jobs}``.
* Added reference to a Docker implementation to the documentation (contributed by **yubiuser** in #64).

Changed
-------
* ``url`` jobs will use the ``HTTPX`` library instead of ``requests` if it's installed since it uses the HTTP/2 network
  protocol (when the ``h2` library is also installed) as browsers do. To revert to the use of ``requests`` even if
  ``HTTPX`` is installed on the system, add ``http_client: requests`` to the relevant jobs or make it a default by
  editing the configuration file to add the sub-directive ``http_client: requests`` for ``url`` jobs under
  ``job_defaults``.
* The ``beautify`` filter converts relative links to absolute ones; use the new ``absolute_links: false``
  sub-directive to disable.

Internal
--------
* Removed transitional support for ``beautifulsoup <4.11`` library (i.e. older than 7 April 2022) for the ``beautify``
  filter.
* Removed dependency on the ``requests`` library and its own dependency on the ``urllib3`` library.
* Code cleanup, including removing support for Python 3.8.
