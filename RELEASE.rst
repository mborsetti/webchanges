⚠ Breaking Changes
```````````````````
* Removed support for Python 3.10. As a reminder, older Python versions are supported for 3 years after being obsoleted
  by a new major release.

Fixed
`````
* Fixed regression in error handling leading to interpreting errors as empty responses causing diffs to be be sent out.
  Reported in #`104 <https://github.com/mborsetti/webchanges/issues/104>`__.

Internals
`````````
* Implemented testing for Python 3.14t (GIL-lock-free).
* Additional code security improvements.
