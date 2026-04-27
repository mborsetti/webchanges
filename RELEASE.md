## Fixed
- Configuration loading no longer fails with `NameError: name '_ConfigDisplay' is not defined` (or similar) when
  an obsolete version of `typeguard` (<4.5) is found installed.
- `--edit-jobs`, `--edit-config`, `--edit-hooks`, and `--detailed-versions` now run without loading the
  configuration, jobs, and hooks files, so a malformed file no longer prevents launching the editor or the version
  listing from being shown.
- Improved output of `--detailed-versions`, especially when ``packaging`` is available.

## Internals
- RELEASE documentation is now in Markdown format.
- Updated vendored `packaging.version` (used as a fallback when the optional `packaging` dependency is unavailable)
  from v24.2 to v26.2.
