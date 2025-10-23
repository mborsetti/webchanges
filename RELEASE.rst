Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.10 was
released on 24 October 2022, the codebase will be streamlined by removing support for Python 3.10 on or after 24 
October 2025.

Added
`````
* Support for Python 3.14.

Fixed
`````
* Fixed ``deepdiff`` differ to handle text strings correctly (e.g. when an API typically returning JSON starts
  returning an error in HTML).

Internals (impacting hooks.py)
``````````````````````````````
* In the ``Differ`` Class' ``process`` method, the ``report_kind``'s value ``text`` has been renamed ``plain`` for 
  clarity and to align with IANA's media type nomenclature for different types of text.

Internals (other)
`````````````````
* Implemented testing for Python 3.14.
* Implemented OpenSSF Scorecard and improved code security.
* Enabled additional ``ruff check`` linters and improved code quality.
