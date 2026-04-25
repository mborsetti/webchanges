Added
`````
* New ``curl_cffi`` option for the ``http_client`` job directive, using the `curl_cffi
  <https://github.com/lexiforest/curl_cffi>`__ library to wrap libcurl-impersonate. This replays real browser TLS
  fingerprints (Chrome, Firefox, Safari, Edge) at the wire level, enabling retrieval of pages behind Cloudflare,
  Akamai, and similar bot-walls that fingerprint the TLS handshake (JA3) or HTTP/2 ``SETTINGS`` frame, without
  needing a full headless browser job.
* New ``impersonate`` job directive controlling the browser TLS fingerprint used by the ``curl_cffi`` HTTP client
  (e.g. ``chrome``, ``chrome124``, ``safari17_0``, ``firefox133``). Defaults to ``chrome``. Ignored by the
  ``httpx`` and ``requests`` backends.
* New ``fingerprints`` job directive for advanced low-level TLS/HTTP fingerprint overrides with the ``curl_cffi``
  HTTP client. Accepts a mapping with optional ``ja3``, ``akamai``, and ``extra_fp`` keys, forwarded verbatim to
  ``curl_cffi``. See the `curl_cffi customization documentation
  <https://curl-cffi.readthedocs.io/en/latest/impersonate/customize.html>`__ for details. Ignored by the ``httpx``
  and ``requests`` backends.
* New ``http_version`` job directive to pin the HTTP protocol version (``v1``, ``v2``, ``v2tls``,
  ``v2_prior_knowledge``, ``v3``, ``v3only``) when using the ``httpx`` or ``curl_cffi`` HTTP clients. ``httpx``
  supports ``v1`` and ``v2`` (the latter requires the ``h2`` package); ``curl_cffi`` supports all values.
* New HTTP client selection logic. While webchanges installs ``httpx``, the program will work in in environments where
  ``httpx``  has been uninstalled by falling back to ``requests`` or ``curl_cffi``, enabling custom lightweight
  installs.
* The ``initialization_url`` job directive now works for all ``url`` jobs (not only those with
  ``use_browser: true``). A ``GET`` request is made to the initialization URL within the same session; cookies
  received are automatically carried over to the main request.
* The ``use_browser`` job directive now accepts a browser name string in addition to a boolean. Supported values
  any value starting with ``chrome`` or ``msedge`` (e.g. ``chrome``, ``chrome-beta``,  ``msedge-dev``), ``firefox``, or
  ``webkit``, or. ``true`` continues to mean the ``chrome`` channel.

Internals
`````````
* The ``requests`` and ``curl_cffi`` HTTP client backends now use session objects (``requests.Session`` and
  ``curl_cffi.requests.Session``) for connection reuse and automatic cookie persistence across initialization and
  main requests.

Fixed
`````
* A report will now be created for jobs initialized with ``--prepare-jobs`` when  ``display``  > ``new`` configuration
  has a ``true`` value.
