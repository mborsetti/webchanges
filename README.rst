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

.. |readthedocs| image:: https://img.shields.io/readthedocs/webchanges/latest.svg?label=
    :target: https://webchanges.readthedocs.io/
    :alt: Read the documentation at https://webchanges.readthedocs.io/

.. |travis| image:: https://img.shields.io/travis/mborsetti/webchanges/master.svg?label=Travis%20CI
    :target: https://travis-ci.com/mborsetti/webchanges
    :alt: Travis CI build status

.. |appveyor| image:: https://img.shields.io/appveyor/ci/mborsetti/webchanges/master.svg?logo=appveyor
    :target: https://ci.appveyor.com/project/mborsetti/webchanges
    :alt: appveyor build status

.. |coverage| image:: https://codecov.io/github/mborsetti/webchanges/coverage.svg
    :target: https://codecov.io/github/mborsetti/webchanges
    :alt: code coverage

`webchanges` checks web content (or the output of local commands) for changes, and notifies you via e-mail or
one of many other supported services if one is detected. The notification includes the changed URL or command and
a summary of what has changed. This project is a fork of `urlwatch <https://github.com/thp/urlwatch>`__ as suggested by
its author to optimize it for HTML.

Installation
============
`webchanges` |pypi_version| is available on `PyPI <https://pypi.org/project/webchanges/>`__ for |support| (versions that
have not been obsoleted by a new major release in the last 3 years) and can be installed using `pip`::

   pip install webchanges

Optional dependencies may be needed; see `here <https://webchanges.readthedocs.io/en/stable/dependencies.html>`__.

Documentation
=============
The documentation is hosted on `Read the Docs <ttps://webchanges.readthedocs.io/en/stable/>`__ |readthedocs|.

Code
====
|issues| |travis| |coverage|

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
<https://github.com/mborsetti/webchanges/blob/master/CONTRIBUTING.rst>`__, and our wishlist is `here
<https://github.com/mborsetti/webchanges/blob/master/WISHLIST.md>`__.

License
=======
|license|

Released under the `MIT License <https://opensource.org/licenses/MIT>`__, but including code licensed under the
`BSD 3-Clause License <https://opensource.org/licenses/BSD-3-Clause>`__. See the license `here
<https://github.com/mborsetti/webchanges/blob/master/COPYING>`__.
