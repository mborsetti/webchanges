.. _command_line:

======================
Command line arguments
======================

.. code block to column ~103 only; beyond has horizontal scroll bar
   1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123

.. code-block::

   usage: webchanges [-h] [-V] [-v] [--jobs FILE] [--config FILE] [--hooks FILE] [--cache FILE] [--list]
                 [--errors] [--test [JOB]] [--no-headless] [--test-diff JOB] [--dump-history JOB]
                 [--max-workers WORKERS] [--test-reporter REPORTER] [--smtp-login] [--telegram-chats]
                 [--xmpp-login] [--edit] [--edit-config] [--edit-hooks] [--gc-database]
                 [--clean-database] [--rollback-database TIMESTAMP] [--delete-snapshot JOB]
                 [--check-new] [--install-chrome] [--features] [--detailed-versions]
                 [--database-engine DATABASE_ENGINE] [--max-snapshots NUM_SNAPSHOTS] [--add JOB]
                 [--delete JOB]
                 [joblist ...]

   Checks web content to detect any changes since the prior run. If any are found, it shows what changed
   ('diff') and/or sends it via e-mail and/or other supported services. Can check the output of local
   commands as well.

   positional arguments:
     joblist               job(s) to run (by index as per --list) (default: run all jobs)

   options:
     -h, --help            show this help message and exit
     -V, --version         show program's version number and exit
     -v, --verbose         show logging output; use -vv for maximum verbosity

   override file defaults:
     --jobs FILE, --urls FILE
                           read job list (URLs) from FILE or files matching a glob pattern
     --config FILE         read configuration from FILE
     --hooks FILE          use FILE as imported hooks.py module
     --cache FILE          use FILE as cache (snapshots database), alternatively a redis URI

   job management:
     --list                list jobs and their index number
     --errors              test run all jobs and list those with errors or no data captured
     --test [JOB], --test-filter [JOB]
                           test a job (by index or URL/command) and show filtered output; if no JOB,
                           check syntax of config and jobs file(s)
     --no-headless         turn off browser headless mode (for jobs using a browser)
     --test-diff JOB, --test-diff-filter JOB
                           show diff(s) using existing saved snapshots of a job (by index or
                           URL/command)
     --dump-history JOB    print all saved changed snapshots for a job (by index or URL/command)
     --max-workers WORKERS
                           maximum number of parallel threads

   reporters:
     --test-reporter REPORTER
                           test a reporter or redirect output of --test-diff
     --smtp-login          verify SMTP login credentials with server (and enter or check password if
                           using keyring)
     --telegram-chats      list telegram chats program is joined to
     --xmpp-login          enter or check password for XMPP (stored in keyring)

   launch editor ($EDITOR/$VISUAL):
     --edit                edit job (URL/command) list
     --edit-config         edit configuration file
     --edit-hooks          edit hooks script

   database:
     --gc-database, --gc-cache
                           garbage collect the cache database by removing old changed snapshots plus all
                           data of jobs not in the jobs file
     --clean-database, --clean-cache
                           remove old changed snapshots from the database
     --rollback-database TIMESTAMP, --rollback-cache TIMESTAMP
                           delete recent changed snapshots since TIMESTAMP (backup the database before
                           using!)
     --delete-snapshot JOB
                           delete the last saved changed snapshot of job (index or URL/command)

   miscellaneous:
     --check-new           check if a new release is available
     --install-chrome      install or update Google Chrome browser (for jobs using a browser)
     --features            list supported job kinds, filters and reporters (including those loaded by
                           hooks)
     --detailed-versions   list detailed versions including of installed dependencies

   override configuration file:
     --database-engine DATABASE_ENGINE
                           override database engine to use
     --max-snapshots NUM_SNAPSHOTS
                           override maximum number of changed snapshots to retain in database (sqlite3
                           only)

   backward compatibility (WARNING: all remarks are deleted from jobs file; use --edit instead):
     --add JOB             add a job (key1=value1,key2=value2,...) [use --edit instead]
     --delete JOB          delete a job (by index or URL/command) [use --edit instead]

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

.. _test:

Test run a job or check config and job files for errors
-------------------------------------------------------
You can test a job and its filter by using the command line argument ``--test`` followed by the job index number
(from ``--list``) or its URL/command; :program:`webchanges` will display the filtered output. This allows to easily
test changes in filters. Use a negative index number to select a job from the bottom of your job list (i.e. -1 is the
last job, -2 is the second to last job, etc.).  Combine ``--test`` with ``--verbose`` to get more information, for
example the text returned from a website with a 4xx (client error) status code:

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
You can test a reporter by using the command line argument ``--test-reporter`` followed by the reporter name;
:program:`webchanges` will create a dummy report and send it through the selected reporter. This will help in
debugging issues, especially when used in conjunction with ``-vv``::

   webchanges -vv --test-reporter telegram


.. versionchanged:: 3.9
   Can be used in combination with ``--test-diff`` to redirect the output of the diff to a reporter.


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
command.

.. tip:: If you use multiple jobs files, use ``--gc-database`` in conjunction with a glob ``--jobs`` command, e.g.
   ``webchanges --jobs "jobs*.yaml" --gc-database``. To ensure that the glob is correct, run e.g. ``webchanges --jobs
   "jobs*.yaml" --list``.

Running with ``--clean-database`` will remove all older snapshots keeping the most recent one for each job (whether it
is still present in the jobs file or not) and rebuild (and therefore defragment) the database using SQLite's `VACUUM
<https://www.sqlite.org/lang_vacuum.html#how_vacuum_works>`__ command.

.. versionchanged:: 3.11
   Renamed from ``--gc-cache`` and ``--clean-cache``.

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
