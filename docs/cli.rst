.. _command_line:

======================
Command line arguments
======================

.. code block to column ~103 only; beyond has horizontal scroll bar
   1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123

.. code-block::

   usage: webchanges [-h] [-V] [-v] [--jobs FILE] [--config FILE] [--hooks FILE] [--cache FILE] [--list]
                 [--errors] [--test [JOB]] [--no-headless] [--test-diff JOB] [--dump-history JOB]
                 [--test-reporter REPORTER] [--smtp-login] [--telegram-chats] [--xmpp-login] [--edit]
                 [--edit-config] [--edit-hooks] [--gc-cache] [--clean-cache]
                 [--rollback-cache TIMESTAMP] [--delete-snapshot JOB]
                 [--database-engine {sqlite3,redis,minidb,textfiles}] [--max-snapshots NUM_SNAPSHOTS]
                 [--check-new] [--install-chrome] [--features] [--add JOB] [--delete JOB]
                 [joblist ...]

   Checks web content to detect any changes since the prior run. If any are found, it shows what changed ('diff') and/or
   sends it via e-mail and/or other supported services. Can check the output of local commands as well.

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
     --errors              list jobs with errors or no data captured
     --test [JOB], --test-filter [JOB]
                           test a job (by index or URL/command) and show filtered output; if no JOB,
                           check syntax of config and jobs file(s)
     --no-headless         turn off browser headless mode (for jobs using a browser)
     --test-diff JOB, --test-diff-filter JOB
                           test and show diff using existing saved snapshots of a job (by index or
                           URL/command)
     --dump-history JOB    print all saved snapshot history for a job (by index or URL/command)

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
     --gc-cache            garbage collect the cache database by removing old snapshots plus all data of
                           jobs not in the jobs file
     --clean-cache         remove old snapshots from the cache database
     --rollback-cache TIMESTAMP
                           delete recent snapshots since TIMESTAMP (backup the database before using!)
     --delete-snapshot JOB
                           delete the last saved snapshot of job (index or URL/command)
     --database-engine {sqlite3,redis,minidb,textfiles}
                           database engine to use (default: sqlite3, unless redis URI in --cache)
     --max-snapshots NUM_SNAPSHOTS
                           sqlite3 only: maximum number of snapshots to retain in database (default: 4)

   miscellaneous:
     --check-new           check if a new release is available
     --install-chrome      install or update Google Chrome browser (for jobs using a browser)
     --features            list supported job types, filters and reporters (including those loaded by hooks)

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

To only check the config and job files for errors, specify --test without a JOB:

.. code-block:: bash

   webchanges --test


.. versionchanged:: 3.8
   Accepts negative indices.

.. versionchanged:: 3.10.2
   JOB no longer required (will only check the config and job files for errors).

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


.. _rollback-cache:

Rollback the database
---------------------
You can rollback the snapshots database to an earlier time by running :program:`webchanges` with the
``--rollback-cache`` command line argument followed by a `Unix timestamp <https://en.wikipedia
.org/wiki/Unix_time>`__ indicating the point in time you want to go back to. Useful when you missed notifications or
they got lost: rollback the database to the time of the last good report, then run :program:`webchanges` again to get
a new report with the differences since that time.

You can find multiple sites that calculate Unix time for you, such as `www.unixtimestamp.com
<https://www.unixtimestamp.com/>`__

**WARNING: all snapshots captured after the time of the timestamp are permanently deleted. This is irreversible.**  Back
up the database before doing a rollback in case of a mistake (or fat-finger).

This feature does not work with database engines ``redis``, ``textfiles`` or ``minidb``.

.. versionadded:: 3.2


.. _compact-cache:

Compact the database
--------------------
You can compact the snapshots database by running :program:`webchanges` with either the ``--gc-cache`` or
``--clean-cache`` command line argument.

Running with ``--gc-cache`` will purge all snapshots of jobs that are no longer in the jobs file **and**, for those in
the jobs file, older snapshots other than the most recent one for each job. It will also rebuild (and therefore
defragment) the database using VACUUM (see `here <https://www.sqlite.org/lang_vacuum.html#how_vacuum_works>`__ for more
details).

.. tip
   If you use multiple jobs files, use ``--cg-cache`` in conjunction with a glob ``--jobs`` command, e.g. ``webchanges
   --jobs "jobs*.yaml" --gc-cache``.  To ensure that the glob is correct, run e.g. ``webchanges --jobs "jobs*.yaml"
   --list``.

Running with ``--clean-cache`` will remove all older snapshots keeping the most recent one for each job (whether it is
still present in the jobs file or not) and rebuild (and therefore defragment) the database using `VACUUM
<https://www.sqlite.org/lang_vacuum.html#how_vacuum_works>`__.



.. _database-engine:

Select a database engine
-------------------------
Default (``sqlite3``)
~~~~~~~~~~~~~~~~~~~~~
The requirement for the ``minidb`` Python package has been removed in version 3.2 and the database system has migrated
to one that relies on the built-in ``sqlite3``, is more efficient due to indexing, creates smaller files due to data
compression with `msgpack <https://msgpack.org/index.html>`__, and provides additional functionality.

Migration of the latest snapshots from the legacy (minidb) database is done automatically and the old file is preserved
for manual deletion.

Redis
~~~~~
To use Redis as a database (cache) backend, simply specify a redis URI in the ``--cache`` command line argument:

.. code-block:: bash

    webchanges --cache=redis://localhost:6379/

For this to work, optional dependencies need to be installed; please see :ref:`here <dependencies>`

There is no migration path from an existing database: the cache will be empty the first time Redis is used.

Text files
~~~~~~~~~~
To have the latest snapshot of each job saved as a separate text file instead of as a record in a database, use
``--cache-engine textfiles``.

minidb (legacy)
~~~~~~~~~~~~~~~
To use the minidb-based database structure used in prior versions and in :program:`urlwatch` 2, launch
:program:`webchanges` with the command line argument ``--cache-engine minidb``. The ``minidib`` Python package must
be installed for this to work.


.. versionadded:: 3.2


.. _max-snapshots:

Maximum number of snapshots to save
-----------------------------------
Each time you run :program:`webchanges` it captures the data downloaded from the URL (or the output of the command
specified), applies filters, and saves the resulting snapshot to a database for future comparison. By default¹ only
the last 4 snapshots are kept, but this number can be changed with the ``--max-snapshots`` command line argument. If
set to 0, all snapshots are retained (the database will grow unbounded).

.. tip:: Changes (diffs) between saved snapshots can be redisplayed with the ``--test-diff`` command line argument (see
   :ref:`here <test-diff>`).

¹ Note that when using ``redis`` or ``minidb`` database engines all snapshots will be kept, while when using the
``textfiles`` database engine only the last snapshot is kept.


.. versionadded:: 3.3
   for default ``sqlite3`` database engine only.


.. todo::
    This part of documentation needs your help!
    Please consider :ref:`contributing <contributing>` a pull request to update this.
