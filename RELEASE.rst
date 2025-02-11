Added
-----
* Added support for setting default differ directives in config.yaml. This is particularly useful for the ``ai_google``
  differ to specify a default GenAI model.
* Added automatic installation of the `zstandard <https://github.com/indygreg/python-zstandard>`__ library to support
  zstd (`RFC 8878 <https://datatracker.ietf.org/doc/html/rfc8878>`__) compression in ``url`` jobs using the default
  HTTPX HTTP client.

Changed
-------
* Renamed job directives ``filter`` and ``diff_filter`` to ``filters`` and ``diff_filters`` (plural nouns) to better
  reflect their list nature. The singular forms remain backward-compatible.
* Consolidated HTTP proxy configuration into a single ``proxy`` directive, replacing the separate ``http_proxy`` and
  ``https_proxy`` directives while maintaining backward compatibility.
* Improved maximum parallel executions of ``use_browser: true`` to ensuring each Chrome instance has at least 400 MB
  of available memory (or the maximum available, if lower).

Fixed
-----
* Fixed handling of "Error Ended" reports to only send them with ``suppress_repeated_errors: true``.
* Fixed error message when using job directive ``http_client: requests`` without the `requests
  <https://pypi.org/project/requests/>`__ library installed. Thanks `yubiuser <https://github.com/yubiuser>`__ for
  reporting this in `issue #90 <https://github.com/mborsetti/webchanges/issues/90>`__.
* Improved and standardized lthe ogic and documentation for the use of environment variables ``HTTPS_PROXY`` and
  ``HTTP_PROXY`` in proxy settings.
* Modified ``--prepare-jobs`` command line argument to append never run jobs to command line jobs (``joblist``), if
  present, rather than replacing them.

Internals
---------
* Replaced JobBase attributes ``http_proxy`` and ``https_proxy`` with a unified ``proxy`` attribute.
* Updated JobBase attributes from singular ``filter`` and ``diff_filter`` to plural ``filters`` and ``diff_filters``.
* Removed unused JobBase attribute ``chromium_revision`` (deprecated since Pypetteer removal on 2022-05-02).


Changes in version 3.27.0
=========================
(inadvertently omitted from release notes)

Added
-----
* Python 3.13: **webchanges** is now fully tested on Python 3.13 before releasing. However, ``orderedset``, a dependency
  of the `aioxmpp <https://pypi.org/project/aioxmpp/>`__ library required by the ``xmpp`` reporter will not install in
  Python 3.13 (at least on Windows) and this reporter is therefore not included in the tests. It appears that the
  development of this `library <https://codeberg.org/jssfr/aioxmpp>`__ has been halted.

  - Python 3.13t (free-threaded, GIL-free) remains unsupported due to the lack of free-threaded wheels for dependencies
    such as ``cryptography``, ``msgpack``, ``lxml``, and the optional ``jq``.
* New job directive ``suppress_repeated_errors`` to notify an error condition only the first time it is encountered. No
  more notifications will be sent unless the error resolves or a different error occurs. This enhancement was
  requested by `toxin-x <https://github.com/toxin-x>`__ in issue `#86
  <https://github.com/mborsetti/webchanges/issues/86>`__.
* New command line argument ``--log-file`` to write the log to a file. Suggested by `yubiuser
  <https://github.com/yubiuser>`__ in `issue #88 <https://github.com/mborsetti/webchanges/issues/88>`__.
* ``pypdf`` filter has a new ``extraction_mode`` optional sub-directive to enable experimental layout text extraction
  mode functionality.
* New command-line option ``--prepare-jobs`` to run only newly added jobs (to capture and save their initial snapshot).

Fixed
-----
* Fixed command line argument ``--errors`` to use the same exact logic as the one used when running *webchanges*.
  Reported by `yubiuser <https://github.com/yubiuser>`__ in `issue #88
  <https://github.com/mborsetti/webchanges/issues/88>`__.
* Fixed incorrect reporting of job error when caused by an HTTP response status code that is not `IANA-registered
  <https://docs.python.org/3/library/http.html#http-status-codes>`__.

Changed
-------
* Command line ``--test`` can now be combined with ``--test-reporter`` to have the output sent to a different reporter.
* Improved error reporting, including reporting error message in ``--test`` and adding proxy information if the error
  is a network error and the job has a proxy and.
* Updated the default model instructions for the ``ai_google`` (BETA) differ to improve quality of summary.

Internals
---------
* Now storing error information in snapshot database.
* Added ``ai_google`` directive to the ``image`` differ to test Generative AI summarization of changes between two
  images, but in testing the results are unusable. This feature is in ALPHA and undocumented, and will not be
  developed further until the models improve to the point where the summary becomes useful.
