==========
webchanges
==========

|pypi| |support| |licence|

|readthedocs| |travis| |coverage|

.. |pypi| image:: https://img.shields.io/pypi/v/webchanges.svg?style=flat-square
    :target: https://pypi.org/project/webchanges/
    :alt: pypi version

.. |support| image:: https://img.shields.io/pypi/pyversions/webchanges.svg?style=flat-square
    :target: https://pypi.org/project/webchanges/
    :alt: supported Python version

.. |licence| image:: https://img.shields.io/pypi/l/webchanges.svg?style=flat-square
    :target: https://pypi.org/project/webchanges/
    :alt: licence

.. |readthedocs| image:: https://img.shields.io/readthedocs/webchanges/latest.svg?style=flat-square&label=Read%20the%20Docs
   :alt: Read the documentation at https://webchanges.readthedocs.io/
   :target: https://webchanges.readthedocs.io/

.. |travis| image:: https://img.shields.io/travis/mborsetti/webchanges/master.svg?style=flat-square&label=Travis%20Build
    :target: https://travis-ci.org/mborsetti/webchanges
    :alt: Travis CI build status

.. |appveyor| image:: https://img.shields.io/appveyor/ci/mborsetti/webchanges/master.svg?style=flat-square&logo=appveyor
    :target: https://ci.appveyor.com/project/mborsetti/webchanges
    :alt: appveyor build status

.. |coverage| image:: https://codecov.io/github/mborsetti/webchanges/coverage.svg?branch=master
    :target: https://codecov.io/github/mborsetti/webchanges?branch=master
    :alt: code coverage

`webchanges` checks webpages (or the output of local commands) for changes, and notifies you via e-mail or
one of many other supported services if one is detected. The notification includes the changed URL or command and
a summary of what has changed. This project is a fork of `urlwatch <https://github.com/thp/urlwatch>`__ as suggested
`here <https://github.com/thp/urlwatch/pull/518#discussion_r456885484>`__ and is optimized for HTML, ensuring that it
"just works".

Installation
============

`webchanges` is available on `PyPI <https://pypi.org/project/webchanges/>`__ and can be installed using `pip`::

   pip install webchanges

Optional dependencies may be needed; see `here <https://webchanges.readthedocs.io/en/stable/dependencies.html>`__.

Documentation
=============

The documentation is hosted on `Read the Docs <ttps://webchanges.readthedocs.io/en/stable/>`__

Code
====

The code and issues tracker are hosted on `GitHub <https://github.com/mborsetti/webchanges>`__

Quick Start
============

#. Run ``webchanges --edit`` to customize your job list (this will create ``jobs.yaml`` and ``config.yaml``)
#. Run ``webchanges --edit-config`` if you want to set up e-mail sending

The interval for checking is defined by how often you run ``webchanges``.  It is recommended to use schedulers to
automatically run `webchanges` periodically:

- In Linux, you can use cron. Use
  `crontab.guru <https://crontab.guru>`__ to figure out the schedule expression for the checking interval, we recommend
  no more often than 30 minutes (this would be ``*/30 * * * *``). If you have never used cron before, check out the
  `crontab command help <https://www.computerhope.com/unix/ucrontab.htm>`__.
- On Windows, use the `Windows Task Scheduler <https://en.wikipedia.org/wiki/Windows_Task_Scheduler>`__
  or see `this <https://stackoverflow.com/q/132971/1047040>`__ question on StackOverflow for alternatives.

Contributing
============

We welcome many types of contributions, e.g. documentation, bug reports, pull requests (code, infrastructure or
documentation fixes and more!). For more information about how to contribute to the project, see `here
<https://github.com/mborsetti/webchanges/blob/master/CONTRIBUTING.rst>`__.

License
=======

Released under the `MIT License <https://opensource.org/licenses/MIT>`__, but including code licensed under the
`BSD 3-Clause License <https://opensource.org/licenses/BSD-3-Clause>`__. See the license `here
<https://github.com/mborsetti/webchanges/blob/master/COPYING>`__.
