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
<https://webchanges.readthedocs.io/en/stable/introduction.html#reporters-list>`__.


Requirements
============
**webchanges** requires |support|.

For the best experience, use the current version of `Python <https://www.python.org/downloads/>`__. We also support
older Python versions for 3 years after they're replaced by a newer one; we just ask that you use the most up-to-date
bug and security fix release from that older version.

For Generative AI summaries (BETA), you need a free `API Key from Google Cloud AI Studio
<https://aistudio.google.com/app/apikey>`__ (see `here
<https://webchanges.readthedocs.io/en/stable/differs.html#ai-google>`__).


Installation
============
|pypi_version| |format| |status| |security|

Install **webchanges**  with:

.. code-block:: bash

   pip install webchanges

Running in Docker
-----------------
**webchanges** can easily run in a `Docker <https://www.docker.com/>`__ container! You will find a minimal
implementation (no browser) `here <https://github.com/yubiuser/webchanges-docker>`__, and one with a browser
`here <https://github.com/jhedlund/webchanges-docker>`__.


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

      webchanges --edit

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

See the `complete licenses <https://raw.githubusercontent.com/mborsetti/webchanges/refs/heads/main/LICENSE>`__ (released
under the `MIT License <https://opensource.org/licenses/MIT>`__ but redistributing modified source code, dated 30
July 2020, from `urlwatch 2.21 <https://github.com/thp/urlwatch/tree/346b25914b0418342ffe2fb0529bed702fddc01f>`__
licensed under a `BSD 3-Clause License
<https://raw.githubusercontent.com/thp/urlwatch/346b25914b0418342ffe2fb0529bed702fddc01f/COPYING>`__).


Compatibility with and improvements from **urlwatch**
=====================================================

This project is based on code from `urlwatch 2.21
<https://github.com/thp/urlwatch/tree/346b25914b0418342ffe2fb0529bed702fddc01f>`__ dated 30 July 2020.

You can easily upgrade to **webchanges** from the current version of **urlwatch** using the same job and
configuration files (see `here <https://webchanges.readthedocs.io/en/stable/upgrading.html>`__) and benefit from many
improvements, including:

* :underline:`AI-Powered Summaries`: Summary of changes in plain text using generative AI, useful for long documents
  (e.g. legal);
* :underline:`Image Change Detection`: Monitor changes to images and receive notifications with an image highlighting
  the differences;
* :underline:`Structured Data Monitoring`: Track changes in JSON or XML data on an element-by-element basis;
* :underline:`Improved Documentation`: We've revamped the `documentation <https://webchanges.readthedocs.io/>`__ to make
  implementation easier;
* :underline:`Enhanced HTML Reports`: HTML reports are now much clearer and include:

  * Clickable links!
  * Retention of most original formatting (**bolding / headers**, *italics*, :underline:`underlining`, lists with
    bullets (•), and indentation;
  * :additions:`added` and :deletions:`deleted` lines clearly highlighted with color and strikethrough;
  * Wrapping of long lines (instead of truncation);
  * Improved compatibility with a wider range of HTML email clients, including those that override stylesheets (e.g.,
    Gmail);
  * General legibility improvements.

* :underline:`New Filtering Options`: New filters, like `additions_only
  <https://webchanges.readthedocs.io/en/stable/diff_filters.html#additions-only>`__, which allows you to focus on
  added content without the distraction of deletions;
* :underline:`New Command Line Arguments`: New command-line arguments such as ``--errors``, which helps you identify
  jobs that are no longer functioning correctly;
* :underline:`Increased Reliability and Stability`: Testing coverage has increased by approximately 30 percentage
  points;
* :underline:`Additional Enhancements`: Numerous other additions, refinements, and bug fixes have been implemented.
  For more information, see `here <https://webchanges.readthedocs.io/en/stable/migration.html#upgrade-details>`__.

Example enhancements to HTML reporting:

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_1.png
    :width: 504

|

.. image:: https://raw.githubusercontent.com/mborsetti/webchanges/main/docs/html_diff_filters_example_3.png
    :width: 504




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
.. |code_style| image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: Code style black
.. |status| image:: https://img.shields.io/pypi/status/webchanges.svg
    :target: https://pypi.org/project/webchanges/
    :alt: Package stability
.. |security| image:: https://img.shields.io/badge/security-bandit-green.svg
    :target: https://github.com/PyCQA/bandit
    :alt: Security Status
