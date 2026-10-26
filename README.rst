.. role:: underline
    :class: underline
.. role:: additions
    :class: additions
.. role:: deletions
    :class: deletions

======================
webchanges |downloads|
======================

**webchanges** *anonymously* checks web content (including images) and commands for changes, delivering instant
notifications and AI-powered summaries to your favorite `platform
<https://webchanges.readthedocs.io/en/stable/introduction.html#reporters>`__.


Highlights
==========
- **Watch anything**: web pages (in a `real browser
  <https://webchanges.readthedocs.io/en/stable/jobs.html#use-browser>`__ if needed), APIs, local files and command
  output.
- **Track only what matters** with over 30 `filters <https://webchanges.readthedocs.io/en/stable/filters.html>`__.
- **Read changes at a glance** in formatted HTML, side by side, word by word, as `AI summaries
  <https://webchanges.readthedocs.io/en/stable/differs.html#ai-google-diff>`__ and more.
- **Get notified anywhere**: email, Telegram, Discord, ntfy, webhooks and `more
  <https://webchanges.readthedocs.io/en/stable/reporters.html>`__.
- **Few false alarms**: transient errors can be held back and repeated ones reported `once
  <https://webchanges.readthedocs.io/en/stable/jobs.html#suppress-repeated-errors>`__.
- **Runs on your machine**, total privacy, no account needed, and extends with Python `hooks
  <https://webchanges.readthedocs.io/en/stable/hooks.html>`__.


Requirements
============
**webchanges** requires |support|. For the best experience, use the current version of `Python
<https://www.python.org/downloads/>`__; older Python versions are supported for 3 years after they're replaced.
Free-threaded Python is supported.

For Generative AI summaries (BETA), you need a free `API Key from Google Cloud AI Studio
<https://aistudio.google.com/app/apikey>`__ (see `here
<https://webchanges.readthedocs.io/en/stable/differs.html#ai-google-diff>`__).


Installation
============
|pypi_version| |format| |status|

Install **webchanges**  with `uv <https://docs.astral.sh/uv/>`__ (recommended):

.. code-block:: bash

   uv pip install webchanges

or with ``pip``:

.. code-block:: bash

   pip install webchanges

On Windows with Python 3.15, first run ``set PYYAML_FORCE_LIBYAML=0`` (in PowerShell:
``$env:PYYAML_FORCE_LIBYAML = "0"``), as explained `here
<https://webchanges.readthedocs.io/en/stable/introduction.html#install-windows>`__.

Other ways to run
-----------------
- In a `Docker <https://www.docker.com/>`__ container: a minimal implementation (no browser) is `here
  <https://github.com/yubiuser/webchanges-docker>`__, and one with a browser is `here
  <https://github.com/jhedlund/webchanges-docker>`__.
- As a `GitHub Action <https://docs.github.com/en/actions>`__: an implementation is `here
  <https://github.com/swimmwatch/webchanges-action>`__.


Documentation |readthedocs|
===========================
The documentation is hosted on `Read the Docs <https://webchanges.readthedocs.io/>`__.


Quick Start
============
Initialize
----------

#. Run the following command to create the default ``config.yaml`` (configuration) and ``jobs.yaml`` (jobs) files and
   open an editor to add your `jobs <https://webchanges.readthedocs.io/en/stable/jobs.html>`__:

   .. code-block:: bash

      webchanges --edit-jobs

#. Run the following command to change the default `configuration
   <https://webchanges.readthedocs.io/en/stable/configuration.html>`__, e.g. to receive change notifications
   ("`reports <https://webchanges.readthedocs.io/en/stable/reporters.html>`__")
   by `email <https://webchanges.readthedocs.io/en/stable/reporters.html#smtp>`__ and/or one of many other methods:

   .. code-block:: bash

      webchanges --edit-config

Run
---
To check the sources in your jobs and report on (e.g. display or via email) any changes found from the last time the
program ran, just run:

.. code-block:: bash

   webchanges


Schedule
--------
**webchanges** leverages the power of a system scheduler:

- On Linux you can use cron, with the help of a tool like `crontab.guru <https://crontab.guru>`__ (help `here
  <https://www.computerhope.com/unix/ucrontab.htm>`__);
- On Windows you can use `Windows Task Scheduler <https://en.wikipedia.org/wiki/Windows_Task_Scheduler>`__;
- On macOS you can use `launchd <https://developer.apple
  .com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html>`__ (help `here
  <https://launchd.info/>`__).


Code
====
|coveralls| |issues| |code_style|

The code, issues tracker, and discussions are hosted on `GitHub <https://github.com/mborsetti/webchanges>`__.


Contributing
============
We welcome any contribution no matter how small, both as pull requests or `issue reports
<https://github.com/mborsetti/webchanges/issues>`__.

More information for code and documentation contributors is `here
<https://webchanges.readthedocs.io/en/stable/contributing.html>`__, and our wishlist is `here
<https://github.com/mborsetti/webchanges/blob/main/WISHLIST.md>`__.


License
=======
|license|

See the `complete licenses
<https://raw.githubusercontent.com/mborsetti/webchanges/refs/heads/main/LICENSE.md>`__ (released under the `MIT
License <https://opensource.org/licenses/MIT>`__ but redistributing modified source code, dated 30 July 2020, from
`urlwatch 2.21 <https://github.com/thp/urlwatch/tree/346b25914b0418342ffe2fb0529bed702fddc01f>`__ licensed under a
`BSD 3-Clause License
<https://raw.githubusercontent.com/thp/urlwatch/346b25914b0418342ffe2fb0529bed702fddc01f/COPYING>`__).


Relationship with **urlwatch**
==============================
This project is a fork of `urlwatch 2.21
<https://github.com/thp/urlwatch/tree/346b25914b0418342ffe2fb0529bed702fddc01f>`__ and has since added many features;
see the `comparison <https://webchanges.readthedocs.io/en/stable/upgrading.html>`__.


.. |support| image:: https://img.shields.io/pypi/pyversions/webchanges.svg
    :target: https://www.python.org/downloads/
    :alt: Supported Python versions
.. |pypi_version| image:: https://img.shields.io/pypi/v/webchanges.svg?label=
    :target: https://pypi.org/project/webchanges/
    :alt: PyPI version
.. |format| image:: https://img.shields.io/pypi/format/webchanges.svg
    :target: https://pypi.org/project/webchanges/
    :alt: Kit format
.. |downloads| image:: https://img.shields.io/pypi/dm/webchanges.svg
    :target: https://www.pepy.tech/project/webchanges
    :alt: PyPI downloads
.. |license| image:: https://img.shields.io/pypi/l/webchanges.svg
    :target: https://pypi.org/project/webchanges/
    :alt: License at https://pypi.org/project/webchanges/
.. |issues| image:: https://img.shields.io/github/issues-raw/mborsetti/webchanges
    :target: https://github.com/mborsetti/webchanges/issues
    :alt: Issues at https://github.com/mborsetti/webchanges/issues
.. |readthedocs| image:: https://img.shields.io/readthedocs/webchanges/stable.svg?label=
    :target: https://webchanges.readthedocs.io/
    :alt: Documentation status
.. |old_CI| image:: https://github.com/mborsetti/webchanges/actions/workflows/ci-cd.yaml/badge.svg?event=push
    :target: https://github.com/mborsetti/webchanges/actions
    :alt: CI testing status
.. |CI| image:: https://img.shields.io/github/check-runs/mborsetti/webchanges/main
    :target: https://github.com/mborsetti/webchanges/actions
    :alt: CI testing status
.. |old_coveralls| image:: https://coveralls.io/repos/github/mborsetti/webchanges/badge.svg?branch=main
    :target: https://coveralls.io/github/mborsetti/webchanges?branch=main
    :alt: Code coverage by Coveralls
.. |coveralls| image:: https://img.shields.io/coverallsCoverage/github/mborsetti/webchanges.svg
    :target: https://coveralls.io/github/mborsetti/webchanges?branch=main
    :alt: Code coverage by Coveralls
.. |code_style| image:: https://img.shields.io/badge/code%20style-ruff-000000.svg
    :target: https://github.com/astral-sh/ruff
    :alt: Code style ruff
.. |status| image:: https://img.shields.io/pypi/status/webchanges.svg
    :target: https://pypi.org/project/webchanges/
    :alt: Package stability
.. .. |security| image:: https://img.shields.io/badge/security-bandit-green.svg
..     :target: https://github.com/PyCQA/bandit
..     :alt: Security Status
.. .. |snyk| image:: https://snyk.io/advisor/python/webchanges/badge.svg
..     :target: https://security.snyk.io/package/pip/webchanges
..     :alt: Snyk Package Health Score