Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.13 was
released on 7 October 2024, the codebase will be streamlined by removing support for Python 3.12 on or after 7
October 2027.

Removed
```````
* Installation on Windows with Python 3.15: The extra step of setting ``PYYAML_FORCE_LIBYAML=0`` is no longer needed,
  as PyYAML now publishes ready-made packages for Python 3.15.
* ``deepdiff`` and ``deepdiff_xml`` extras: No longer limited to ``deepdiff`` < 9.1 on Python 3.15, as the ``cachebox``
  package that newer versions require now installs there.

Internals
`````````
* Updated the vendored fallback copies of ``typeguard`` from v4.6.0 to v4.6.1 (``ReadOnly`` items of a ``TypedDict``
  are now type-checked) and of ``httpx2``'s ``Headers`` class from v2.16.0 to v2.16.2 (type annotations only).
