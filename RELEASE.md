## Fixed
- Configuration loading no longer fails with `NameError: name '_ConfigDisplay' is not defined` (or similar) when
  an obsolete version of `typeguard` (<4.5) is found in the system.

## Internals
- RELEASE documentation is now in Markdown format.
- Updated vendored `packaging.version` (used as a fallback when the optional `packaging` dependency is unavailable)
  from v24.2 to v26.2.
