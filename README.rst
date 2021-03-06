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

.. |CI| image:: https://github.com/mborsetti/webchanges/workflows/Tests/badge.svg?event=pull_request&branch=main
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

Installation
============
`webchanges` |pypi_version| is available on `PyPI <https://pypi.org/project/webchanges/>`__ for |support| (Python
versions are supported for 3 years after being obsoleted by a new major release) and can be installed using `pip`::

   pip install webchanges

Optional dependencies may be needed; see `here <https://webchanges.readthedocs.io/en/stable/dependencies.html>`__.

Documentation
=============
The documentation is hosted on `Read the Docs <https://webchanges.readthedocs.io/>`__ |readthedocs|.

Code
====
|issues| |CI| |coverage| |coveralls|

The code and issues tracker are hosted on `GitHub <https://github.com/mborsetti/webchanges>`__.

Quick Start
============
#. Run ``webchanges --edit`` to customize your job list (this will create ``jobs.yaml`` and ``config.yaml``)
#. Run ``webchanges --edit-config`` if you want to set up e-mail sending

``webchanges`` will check for changes every time you run it, but does not include a scheduler. We recommend using a
system scheduler to automatically run `webchanges` periodically:

- In Linux, you can use cron; `crontab.guru <https://crontab.guru>`__ will build a schedule expression for you. If you
  have never used cron before, see `here <https://www.computerhope.com/unix/ucrontab.htm>`__.
- On Windows, you can use the built-in `Windows Task Scheduler
  <https://en.wikipedia.org/wiki/Windows_Task_Scheduler>`__.


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

This fork is optimized for HTML:

* Links are `clickable <https://pypi.org/project/webchanges/>`__!
* Formatting such as **bolding / headers**, *italics*, :underline:`underlining`, list bullets (•) and indentation is
  preserved
* :additions:`Added` and :deletions:`deleted` lines are highlighted with color and strikethrough
* Long lines wrap around
* HTML is rendered correctly by email clients such as Gmail who override stylesheets
* Other legibility improvements

It also has a new `additions_only <https://webchanges.readthedocs.io/en/stable/diff_filters.html#additions-only>`__
filter that makes it easier to track content that was added without the distractions of the content that was deleted
(and a similar `deletions_only <https://webchanges.readthedocs.io/en/stable/diff_filters.html#deletions-only>`__ one)
as well as many other refinements (see `changelog
<https://github.com/mborsetti/webchanges/blob/main/CHANGELOG.rst>`__).

Examples:

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_1.png
    :width: 504

|

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_3.png
    :width: 504
