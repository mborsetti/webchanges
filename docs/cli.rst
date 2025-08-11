.. _command_line:

======================
Command line arguments
======================

.. code-block to column ~103 only; beyond has horizontal scroll bar
   1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123

.. include:: ..\cli_help.txt
   :code:


.. _job_subset:

Select subset of jobs
---------------------
Add job index number(s) (a "joblist") to the command line to run a subset of jobs; for example, ``webchanges 2 3 9``
will only run jobs #2, #3, and #9, and ``webchanges -1`` will only run the last job. Find the index numbering of your
jobs by running ``webchanges --list``.

.. versionadded:: 3.6

.. versionchanged:: 3.8
   Accepts negative indices.


.. _cli_jobs:

Custom job file specification
-----------------------------

By default, the job file is named ``jobs.yaml`` and is located in the following directory:

* Linux: ``~/.config/webchanges``
* macOS: ``~/Library/Preferences/webchanges``
* Windows: ``%USERPROFILE%\Documents\webchanges`` (the webchanges folder within your Documents folder)

Use the ``--jobs`` command line argument to specify a file with a different name or location or a `glob pattern
<https://en.wikipedia.org/wiki/Glob_(programming)>`__ for multiple files (the contents of matching files will be
combined)

- If you specify a file name without a directory, :program:`webchanges` searches:
  1. The current directory
  2. The default directory (if not found in the current directory)

- If you specify a file name without a suffix and the file is not found, :program:`webchanges` will attempt to load a
  file with the ``.yaml`` suffix.
- If you specify a file name that does not start with ``jobs``, :program:`webchanges` will attempt to load a file with a
  ``jobs-`` prefix (and one with both a ``jobs-`` prefix and a ``.yaml`` suffix).

  Example: ``--jobs test`` is equivalent to ``--jobs test`` or ``--jobs test.yaml`` or ``--jobs jobs-test`` or
  ``--jobs jobs-test.yaml`` and the first matching file will be loaded.

Multiple job files
^^^^^^^^^^^^^^^^^^

To load multiple job files in a single run, glob patterns are supported, as well as repeating the ``--jobs`` argument:

``webchanges --jobs file1.yaml --jobs file2.yaml --jobs morningrun/*.yaml``

The contents of all specified files will be combined by appending them in order.


.. versionchanged:: 3.25
   Added ability to repeat the argument multiple times.


.. _smart-file-specification:

Smart file specification
========================

The command-line arguments ``--jobs``, ``--config``, and ``--hooks`` feature a "smart file specification" capability.
This allows you to provide a shorthand name for your files, and  :program:`webchanges` will automatically search for
several variations of that name.

The search process is as follows:

*   **For** ``--jobs <name>``:
    #. ``<name>``
    #. ``<name>.yaml``
    #. ``jobs-<name>``
    #. ``jobs-<name>.yaml``

    *Example:* ``--jobs myjobs`` will look for ``myjobs``, then ``myjobs.yaml``, ``jobs-myjobs``, and finally
    ``jobs-myjobs.yaml``.

*   **For** ``--config <name>``:
    #. ``<name>``
    #. ``<name>.yaml``
    #. ``config-<name>``
    #. ``config-<name>.yaml``

    *Example:* ``--config myconfig`` will look for ``myconfig``, then ``myconfig.yaml``, ``config-myconfig``, and
    finally ``config-myconfig.yaml``.

*   **For** ``--hooks <name>``:
    #. ``<name>``
    #. ``<name>.py``
    #. ``hooks-<name>``
    #. ``hooks-<name>.py``

    *Example:* ``--hooks myhooks`` will look for ``myhooks``, then ``myhooks.py``, ``hooks-myhooks``, and
    finally ``hooks-myhooks.py``.

.. versionchanged::  3.31
   Added prefix and expanded from ``--jobs`` to also include ``--config`` and ``--hooks``.


.. _list:

List jobs and their index number
--------------------------------
You can list all the jobs in a jobs file by using the command line argument ``--list``. You can filter this list by
following this argument with a `Python regular expression
<https://docs.python.org/3/library/re.html#regular-expression-syntax>`__. For example ``--list blue`` will list only
jobs that have the word 'blue' in their listing name (but not 'BLUE'), while ``--list (?i)blue`` will do the same but
in a `case-insensitive manner <https://docs.python.org/3/library/re.html#re.I>`__.

.. versionchanged:: 3.25
   Added ability to filter list using a RegEx.


.. _error:

Show errors and no-data jobs
----------------------------
You can run all jobs and see those that result in an error or who, after filtering, return no data, by running
:program:`webchanges` with the ``--error`` command line argument. This can help with detecting jobs that may no longer
be monitoring resources as expected. No snapshots are saved from this run.

.. warning::
   Do not use this argument to test newly modified jobs since it does `conditional requests
   <https://developer.mozilla.org/en-US/docs/Web/HTTP/Conditional_requests>`__ on websites, and those reporting
   no changes since the time :program:`webchanges` saved a snapshot are skipped. Use ``--test`` instead. To remove a
   blank snapshot use ``--delete-snapshot``; to see the saved snapshots use ``--dump-history``.

By default, the output will go to :ref:`stdout`, but you can add any :ref:`reporter <reporters>` name to the command
line argument to have the output use that reporter. For example, to be notified by email of any errors, run the
following:

.. code-block:: bash

   webchanges --error email

Please note that since no reporting is involved, ``--error`` runs faster than a regular run and this has been known to
cause DNS errors (e.g. ``[Errno-3] Try again``) when using a slow resolver (see `here
<https://github.com/mborsetti/webchanges/issues/88>`__). To reduce this (and other) errors,  ``--max_workers`` is
defaulted to 1 (no parallel job execution).

.. versionchanged:: 3.17
   Send output to any reporter.

.. versionchanged:: 3.18
   Use conditional requests to improve speed.

.. versionchanged:: 3.31
   Default ``--max-workers`` to 1 to reduce spurious errors.



.. _test:

Test run a job or check config and job files for errors
-------------------------------------------------------
You can test a job and its filter by using the command line argument ``--test`` followed by the job index number
(from ``--list``) or its URL/command; :program:`webchanges` will display the filtered output. This allows to easily
test changes in filters. Use a negative index number to select a job from the bottom of your job list (i.e. -1 is the
last job, -2 is the second to last job, etc.).

Combine ``--test`` with ``--verbose`` to get more information, for example the text returned from a website with a 4xx
(client error) status code, or, if using ``use_browser: true``, save to a temporary folder in case of failure a
screenshot, a full page image, and the HTML contents of the page (see log for filenames):

.. code-block:: bash

   webchanges --verbose --test 1

The output of the test can be redirected to any reporter by combining it with --test-reporter:

.. code-block:: bash

   webchanges --verbose --test 1 --test-reporter browser

Please note that ``max_tries`` will be ignored by ``--test``.

To only check the config, job and hooks files for errors, use ``--test`` without specifying a JOB:

.. code-block:: bash

   webchanges --test


.. versionchanged:: 3.8
   Accepts negative indices.

.. versionchanged:: 3.10.2
   JOB no longer required (will only check the config and job files for errors).

.. versionchanged:: 3.11
   When JOB is not specified, the hooks file is also checked for syntax errors (in addition to the config and jobs
   files).

.. versionchanged:: 3.14
   Saves the screenshot, full page image and HTML contents when a ``url`` job with ``use_browser: true`` fails
   while running in verbose mode.

.. versionchanged:: 3.27
   Uses built-in repoters for output, and can be combined with ``--test-reporter``.


.. _test-differ:

Show diff from saved snapshots
------------------------------
You can use the command line argument ``--test-differ`` followed by the job index number (from ``--list``) or its
URL/command will display diffs and apply the :ref:`diff filters <diff_filters>` currently defined from all snapshots
that have been saved; obviously a minimum of 2 saved snapshots are required. This allows you to test the effect of a
diff filter and/or retrieve historical diffs (changes). Use a negative index number to select a job from the bottom
of your job list (i.e. -1 is the last job, -2 is the second to last job, etc.)

You can test how the diff looks like with a reporter by combining this with ``--test-reporter``. For example, to see
how diffs from job 1 look like in HTML if running on a machine with a web browser, run this::

   webchanges --test-differ 1 --test-reporter browser


Optionally, you can specify the maximum number of comparisons (diffs) to run, instead of producing diffs for all
the snapshots that have been saved::

   webchanges --test-differ 1 2 --test-reporter browser  # run differ for job 1 a maximum of 2 times



.. versionchanged:: 3.3
   Will now display all saved snapshots instead of only the latest 10.

.. versionchanged:: 3.8
   Accepts negative indices.

.. versionchanged:: 3.9
   Can be used in combination with ``--test-reporter``.

.. versionchanged:: 3.22
   Added the maximum number of comparisons to perform (optional).


.. _test-reporter:

Test a reporter
---------------
You can test a reporter by using the command line argument ``--test-reporter`` followed by the
:ref:`reporter <reporters>` name; :program:`webchanges` will create a dummy report and send it through the selected
reporter. This will help in debugging issues, especially when used in conjunction with ``-vv``::

   webchanges -vv --test-reporter telegram

.. versionchanged:: 3.9
   Can be used in combination with ``--test-differ`` to redirect the output of the diff to a reporter.


.. _footnote:

Add a footnote to your reports
------------------------------
You can use the command line argument ``--footnote`` to add a footnote to the reports::

   webchanges --footnote "This report was made by me."

.. versionadded:: 3.13


.. _clean-database:

Compact the database
--------------------
You can compact the snapshots database by running :program:`webchanges` with either the ``--gc-database`` ('garbage
collect') or ``--clean-database`` command line argument.

Running with ``--gc-database`` will purge all snapshots of jobs that are no longer in the jobs file **and**, for those
in the jobs file, older changed snapshots other than the most recent one for each job. It will also rebuild (and
therefore defragment) the database using SQLite's `VACUUM <https://www.sqlite.org/lang_vacuum.html#how_vacuum_works>`__
command. You can indicate a RETAIN_LIMIT for the number of older changed snapshots to retain (default: 1, the
latest).

.. tip:: If you use multiple jobs files, use ``--gc-database`` in conjunction with a glob ``--jobs`` command, e.g.
   ``webchanges --jobs "jobs*.yaml" --gc-database``. To ensure that the glob is correct, run e.g. ``webchanges --jobs
   "jobs*.yaml" --list``.

Running with ``--clean-database`` will remove all older snapshots keeping the most recent RETAIN_LIMIT ones for
each job (whether it is still present in the jobs file or not) and rebuild (and therefore defragment) the database
using SQLite's `VACUUM <https://www.sqlite.org/lang_vacuum.html#how_vacuum_works>`__ command.

.. versionchanged:: 3.11
   Renamed from ``--gc-cache`` and ``--clean-cache``.

.. versionchanged:: 3.13
   Added RETAIN_LIMIT.


.. _rollback-database:

Rollback the database
---------------------
You can rollback the snapshots database to an earlier time by running :program:`webchanges` with the
``--rollback-database`` command line argument followed by either an `ISO-8601 <https://en.wikipedia
.org/wiki/ISO_8601>`__ formatted date or a `Unix timestamp <https://en.wikipedia.org/wiki/Unix_time>`__ indicating the
point in time you want to go back to. If you have the Python library `dateutil
<https://github.com/dateutil/dateutil>`__ installed in the system (not a dependency of :program:`webchanges`), then
you can use any string recognized by ``dateutil.parser``, including date only, time only, date and time, etc.
See examples `here <https://dateutil.readthedocs.io/en/stable/examples.html#parse-examples>`__.

Useful when you missed notifications or they got lost: rollback the database to the time of the last good report,
then run :program:`webchanges` again to get a new report with the differences since that time.

You can find multiple sites that calculate Unix time for you, such as `www.unixtimestamp.com
<https://www.unixtimestamp.com/>`__

.. warning::
  All snapshots captured after the timestamp are **permanently** deleted. This deletion is **irreversible.** Do
  back up the database file before doing a rollback in case of a mistake (or fat-finger).

This feature does not work with database engines ``redis``, ``textfiles`` or ``minidb``.

.. versionadded:: 3.2

.. versionchanged:: 3.11
   Renamed from ``--rollback-cache``.

.. versionchanged:: 3.24
   Recognizes ISO-8601 formats and defaults to using ``dateutil.parser`` if found installed.


.. _prepare-jobs:

Save snapshot for newly added job
---------------------------------
To run only newly added jobs to capture and save their initial snapshot, run with ``--prepare-jobs``. Can be combined
with a "joblist" on the command line, in which case it will add these new jobs to the joblist provided.  The following
will run jobs #10 and #12 plus any jobs that have never been run before (i.e. no starting snapshot has ever been
captured)::

   webchanges --prepare-jobs 10 12

.. versionadded:: 3.27

.. versionchanged:: 3.28
   Added ability to combine with joblist.



.. _delete-snapshot:

Delete the latest saved snapshot
--------------------------------
You can delete the latest saved snapshot of a job by running :program:`webchanges` with the ``--delete-snapshot``
command line argument followed by the job index number (from ``--list``) or its URL/command. This is extremely
useful when a website is redesigned and your filters behave in unexpected ways (for example, by capturing nothing):

* Update your filters to once again capture the content you're monitoring, testing the job by running
  :program:`webchanges` with the ``--test`` command line argument (see :ref:`here <test>`);
* Delete the latest job's snapshot using ``--delete-snapshot``;
* Run :program:`webchanges` again; this time the diff report will contain useful information on whether any content has
  changed.

This feature does not work with database engines ``textfiles`` and ``minidb``.

.. versionadded:: 3.5

.. versionchanged:: 3.8
   Also works with ``redis`` database engine.


.. _change-location:

Updating a URL and keeping past history
---------------------------------------
Job history is stored based on the value of the ``url`` or ``command`` parameter, so updating a job's URL in the
configuration file ``urls.yaml`` will create a new job with no history. Retain history by using
``--change-location``, before modifying the jobs file (i.e. while the job is still listed with the old URL or command):

.. code-block:: bash

    webchanges --change-location https://example.org#old https://example.org#new
    # or
    webchanges --change-location old_command new_command

.. versionadded:: 3.13


.. _database-engine:

Database engine
---------------
``--database-engine`` will override the value in the configuration file (see :ref:`database_engine`).

.. versionadded:: 3.2


.. _max-snapshots:

Maximum number of snapshots to save
-----------------------------------
``--max-snapshots`` will override the value in the configuration file (see :ref:`database_max_snapshots`).

.. versionadded:: 3.3
   For default ``sqlite3`` database engine only.


.. todo::
    This part of documentation needs your help!
    Please consider :ref:`contributing <contributing>` a pull request to update this.

Log -v/--verbose output to file
-------------------------------
Use ``--log-file`` to send the log output from ``-v`` or ``-vv`` to a file:

.. code-block:: bash

    webchanges -vv -log-file webchanges.log

.. versionadded:: 3.27
