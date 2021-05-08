==========
webchanges
==========

.. |pypi_version| image:: https://img.shields.io/pypi/v/webchanges.svg?label=
    :target: https://pypi.org/project/webchanges/
    :alt: pypi version

.. |support| image:: https://img.shields.io/pypi/pyversions/webchanges.svg
    :target: https://pypi.org/project/webchanges/
    :alt: supported Python version

.. |license| image:: https://img.shields.io/pypi/l/webchanges.svg
    :target: https://pypi.org/project/webchanges/
    :alt: license

.. |issues| image:: https://img.shields.io/github/issues-raw/mborsetti/webchanges
    :target: https://github.com/mborsetti/webchanges/issues
    :alt: issues

.. |readthedocs| image:: https://img.shields.io/readthedocs/webchanges/stable.svg?label=
    :target: https://webchanges.readthedocs.io/
    :alt: Read the documentation at https://webchanges.readthedocs.io/

.. |CI| image:: https://github.com/mborsetti/webchanges/workflows/Tests/badge.svg?branch=main
    :target: https://github.com/mborsetti/webchanges/actions
    :alt: CI testing status

.. |coverage| image:: https://codecov.io/gh/mborsetti/webchanges/branch/main/graphs/badge.svg
    :target: https://app.codecov.io/gh/mborsetti/webchanges/branch/main
    :alt: code coverage by Codecov

.. |coveralls| image:: https://coveralls.io/repos/github/mborsetti/webchanges/badge.svg?branch=main
    :target: https://coveralls.io/github/mborsetti/webchanges?branch=main
    :alt: code coverage by Coveralls

.. role:: underline
    :class: underline

.. role:: additions
    :class: additions

.. role:: deletions
    :class: deletions

`webchanges` checks web content (or the output of local commands) for changes, and notifies you via e-mail or
one of many other supported services if one is detected. The notification includes the changed URL or command and
a summary of what has changed. This project is a fork of `urlwatch <https://github.com/thp/urlwatch>`__ as suggested by
its author to optimize it for HTML.


Requirements
============
`webchanges` requires |support|.

You should use the latest version of Python if possible. If you’re using an older version, be aware that for each minor
version (3.x), only the latest bugfix release (3.x.y) is officially supported. Older Python versions are supported
for 3 years after being obsoleted by a new major release.


Installation
============
Install `webchanges` |pypi_version| with::

   pip install webchanges


Documentation
=============
The documentation is hosted on `Read the Docs <https://webchanges.readthedocs.io/>`__ |readthedocs|.


Quick Start
============
Initialize
----------

1. Create the default ``config.yaml`` configuration file and open an editor to the ``jobs.yaml`` where to write the
   `jobs <https://webchanges.readthedocs.io/en/stable/jobs.html>`__ to run:

.. code-block:: bash

   webchanges --edit


2. If you want to change the default configuration, e.g. to enable `e-mail sending
   <https://webchanges.readthedocs.io/en/stable/reporters.html#smtp>`__ of change reports, run:

.. code-block:: bash

   webchanges --edit-config


Run
---
.. code-block:: bash

   webchanges

This checks the sources in your jobs, and will report on (e.g. display) any changes from the previous run.


`webchanges` does not include a scheduler. We recommend using a system scheduler to automatically run `webchanges`
periodically:

- On Linux or MacOS, you can use cron; `crontab.guru <https://crontab.guru>`__ will build a schedule expression for
  you; if you have never used cron before, see `here <https://www.computerhope.com/unix/ucrontab.htm>`__.
- On Windows, you can use the built-in `Windows Task Scheduler
  <https://en.wikipedia.org/wiki/Windows_Task_Scheduler>`__.


Code
====
|coveralls| |issues|

The code and issues tracker are hosted on `GitHub <https://github.com/mborsetti/webchanges>`__.


Contributing
============
We welcome any contribution, e.g. documentation, bug reports, new features, etc., as both pull requests and
`issues <https://github.com/mborsetti/webchanges/issues>`__.
More information for developers and documenters is `here
<https://github.com/mborsetti/webchanges/blob/main/CONTRIBUTING.rst>`__, and our wishlist is `here
<https://github.com/mborsetti/webchanges/blob/main/WISHLIST.md>`__.


License
=======
|license|

Released under the `MIT License <https://opensource.org/licenses/MIT>`__, but including code licensed under the
`BSD 3-Clause License <https://opensource.org/licenses/BSD-3-Clause>`__. See the license `here
<https://github.com/mborsetti/webchanges/blob/main/COPYING>`__.


Improvements from `urlwatch`
============================

You can seamlessly upgrade from `urlwatch` 2.23 (see `here
<https://webchanges.readthedocs.io/en/stable/migration.html>`__) and benefit from these HTML-focused improvements:

* Links are `clickable <https://pypi.org/project/webchanges/>`__!
* Formatting such as **bolding / headers**, *italics*, :underline:`underlining`, list bullets (•) and indentation is
  preserved
* Uses color and strikethrough to highlight :additions:`added` and :deletions:`deleted` lines.,and long lines wrap
  around
* HTML is rendered correctly by email clients who override stylesheets (e.g. Gmail)
* Other legibility improvements
* Multiple changes to how Pyppeteer is run (for websites that need JavaScript rendering before capture) increasing
  stability, reliability, flexibility and control
* New filters such as `additions_only <https://webchanges.readthedocs.io/en/stable/diff_filters.html#additions-only>`__,
  which makes it easier to track content that was added without the distractions of the content that was deleted
* Better documentation
* More reliability and stability, including a 22 percentage point increase in testing coverage
* Many many other additions, refinements and fixes (see `detailed information
  <https://webchanges.readthedocs.io/en/stable/migration.html#detailed-information>`__)

Examples:

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_1.png
    :width: 504

|

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_3.png
    :width: 504
