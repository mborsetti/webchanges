.. _command_line:

======================
Command line arguments
======================

.. code block to column ~103 only; beyond has horizontal scroll bar
   1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123

.. include:: cli_help.txt
   :code:


.. _job_subset:

Select subset of jobs
---------------------
Add job number(s) (a ``joblist``) to the command line to run a subset of jobs; for example, ``webchanges 2 3 9`` will
only run jobs #2, #3, and #9, and ``webchanges -1`` will only run the last job. Find the index numbering of your jobs by
running ``webchanges --list``. API is experimental and may change in the near future.

.. versionadded:: 3.6

.. versionchanged:: 3.8
   Accepts negative indices.

Show errors and no-data jobs
----------------------------
You can run all jobs and see those that result in an error or who, after filtering, return no data, by running
:program:`webchanges` with the ``--error`` command line argument. This can help with detecting jobs that may no longer
be monitoring resources as expected. No snapshots are saved from this run.

By default, the output will go to :ref:`stdout`, but you can add any :ref:`reporter <reporters>` name to the command
line argument to have the output use that reporter. For example, to be notified by email of any errors, run the
following:

.. code-block:: bash

   webchanges --errors email

.. versionchanged:: 3.17
   Send output to any reporter.


.. _test:

Test run a job or check config and job files for errors
-------------------------------------------------------
You can test a job and its filter by using the command line argument ``--test`` followed by the job index number
(from ``--list``) or its URL/command; :program:`webchanges` will display the filtered output. This allows to easily
test changes in filters. Use a negative index number to select a job from the bottom of your job list (i.e. -1 is the
last job, -2 is the second to last job, etc.).  Combine ``--test`` with ``--verbose`` to get more information, for
example the text returned from a website with a 4xx (client error) status code, or, if using ``use_browser: true``, a
screenshot, a full page image, and the HTML contents at the moment of failure (see log for filenames):

.. code-block:: bash

   webchanges --verbose --test 1

Please note that ``max_tries`` will be ignored by ``--test``.

To only check the config, job and hooks files for errors, use ``--test`` without a JOB:

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

.. _test-diff:

Show diff from saved snapshots
------------------------------
You can use the command line argument ``--test-diff`` followed by the job index number (from ``--list``) or its
URL/command will display diffs and apply the :ref:`diff filters <diff_filters>` currently defined from all snapshots
that have been saved; obviously a minimum of 2 saved snapshots are required. This allows you to test the effect of a
diff filter and/or retrieve historical diffs (changes). Use a negative index number to select a job from the bottom
of your job list (i.e. -1 is the last job, -2 is the second to last job, etc.)

You can test how the diff looks like with a reporter by combining this with ``--test-reporter``. For example, to see
how diffs from job 1 look like in HTML if running on a machine with a web browser, run this::

   webchanges --test-diff 1 --test-reporter browser


.. versionchanged:: 3.3
   Will now display all saved snapshots instead of only the latest 10.

.. versionchanged:: 3.8
   Accepts negative indices.

.. versionchanged:: 3.9
   Can be used in combination with ``--test-reporter``.


.. _test-reporter:

Test a reporter
---------------
You can test a reporter by using the command line argument ``--test-reporter`` followed by the
:ref:`reporter <reporters>` name; :program:`webchanges` will create a dummy report and send it through the selected
reporter. This will help in debugging issues, especially when used in conjunction with ``-vv``::

   webchanges -vv --test-reporter telegram

.. versionchanged:: 3.9
   Can be used in combination with ``--test-diff`` to redirect the output of the diff to a reporter.


.. _footnote:

Add a footnote to your reports
------------------------------
You can use the command line argument ``--footnote`` to add a footnote to the reports::

   webchanges --footnote "This report was made by me."

.. versionadded:: 3.13


.. _change-location:

Updating a URL and keeping past history
---------------------------------------
Job history is stored based on the value of the ``url`` or ``command`` parameter, so updating a job's URL in the
configuration file ``urls.yaml`` will create a new job with no history. Retain history by using ``--change-location``::

    webchanges --change-location https://example.org#old https://example.org#new
    # or
    webchanges --change-location old_command new_command

.. versionadded:: 3.13


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


.. _rollback-database:

Rollback the database
---------------------
You can rollback the snapshots database to an earlier time by running :program:`webchanges` with the
``--rollback-database`` command line argument followed by a `Unix timestamp <https://en.wikipedia
.org/wiki/Unix_time>`__ indicating the point in time you want to go back to. Useful when you missed notifications or
they got lost: rollback the database to the time of the last good report, then run :program:`webchanges` again to get
a new report with the differences since that time.

You can find multiple sites that calculate Unix time for you, such as `www.unixtimestamp.com
<https://www.unixtimestamp.com/>`__

.. warning::
  All snapshots captured after the timestamp are **permanently** deleted. This deletion is **irreversible.** Do
  back up the database file before doing a rollback in case of a mistake (or fat-finger).

This feature does not work with database engines ``redis``, ``textfiles`` or ``minidb``.

.. versionadded:: 3.2

.. versionchanged:: 3.11
   Renamed from ``--rollback-cache``.


.. _compact-database:

Compact the database
--------------------
You can compact the snapshots database by running :program:`webchanges` with either the ``--gc-database`` ('garbage
collect') or ``--clean-database`` command line argument.

Running with ``--gc-database`` will purge all snapshots of jobs that are no longer in the jobs file **and**, for those
in the jobs file, older changed snapshots other than the most recent one for each job. It will also rebuild (and
therefore defragment) the database using SQLite's `VACUUM <https://www.sqlite.org/lang_vacuum.html#how_vacuum_works>`__
command.  You can indicate a RETAIN_LIMIT for the number of older changed snapshots to retain (default: 1, the
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
