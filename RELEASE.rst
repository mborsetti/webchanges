Reminder
````````
Older Python versions are supported for 3 years after being obsoleted by a new major release. As Python 3.10 was
released on 24 October 2022, the codebase will be streamlined by removing support for Python 3.10 on or after 24 
October 2025.

Fixed
`````
* Certain job Exceptions would fail with a yaml Exception.

Internals
`````````
* Removed non-unique elements in pyproject.toml's classifiers,
* Updated run-gemini-cli to fix GitHub error.
* Fixed pre-commit.ci failing checks on new PRs
