⚠ Breaking Changes
```````````````````
* Removed support for Python 3.10. As a reminder, older Python versions are supported for 3 years after being obsoleted
  by a new major release.

Added
`````
* Support for Python 3.14t (free-threaded, GIL-free). Please note that while **webchanges** now supports free-threaded 
  Python, certain optional dependencies do not (currently, these are ``playwright`` and ``jq``).

Fixed
`````
* Fixed regression in error handling leading to interpreting errors as empty responses causing diffs to be be sent out.
  Reported in #`104 <https://github.com/mborsetti/webchanges/issues/104>`__.

Internals
`````````
* Implemented testing for Python 3.14t (GIL-lock-free).
* Additional code security improvements.
* Removed Gemini Github Actions workflows (trial)
* In URL jobs, the ``TransientHTTPError`` Exception will be raised when a transient HTTP error is detected, paving the
  way for a new ``ignore_transient_error`` directive (not yet implemented) requested in #`119
  <https://github.com/mborsetti/webchanges/issues/119>`__.

  The following HTTP response codes are considered to be transient errors:

    - 429 Too Many Requests
    - 500 Internal Server Error
    - 502 Bad Gateway
    - 503 Service Unavailable
    - 504 Gateway Timeout

  In addition, for ``browser: true``, browser errors starting with ``net::`` and corresponding to the range 100-199
  (Connection related errors) are considered to be transient; they are listed at
  https://source.chromium.org/chromium/chromium/src/+/main:net/base/net_error_list.h.
