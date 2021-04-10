.. _command_line:

======================
Command line arguments
======================

.. code block to column 105 only; beyond has horizontal scroll bar

.. code-block::

  optional arguments:
    -h, --help            show this help message and exit
    -V, --version         show program's version number and exit
    -v, --verbose         show debug output

  override file defaults:
    --jobs FILE, --urls FILE
                          read job list (URLs) from FILE
    --config FILE         read configuration from FILE
    --hooks FILE          use FILE as hooks.py module
    --cache FILE          use FILE as a cache (snapshots database) or directory, alternatively can
                          accept a redis URI

  job management:
    --list                list jobs
    --errors              list jobs with errors or no data captured
    --test JOB, --test-filter JOB
                          test a job (by index or URL/command) and show filtered output
    --test-diff JOB, --test-diff-filter JOB
                          show up to 10 diffs from saved snapshots (by URL/command or index)
    --add JOB             add job (key1=value1,key2=value2,...). WARNING: all remarks are deleted from
                          jobs file; use --edit instead!
    --delete JOB          delete job by URL/command or index number. WARNING: all remarks are deleted
                          from jobs file; use --edit instead!

  reporters:
    --test-reporter REPORTER
                          send a test notification
    --smtp-login          enter or check password for SMTP email (stored in keyring)
    --telegram-chats      list telegram chats the bot is joined to
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
                          delete recent snapshots > timestamp; backup the database before using!
    --database-engine {sqlite3,redis,minidb,textfiles}
                          database engine to use (default: sqlite3 unless redis URI in --cache)
    --max-snapshots NUM_SNAPSHOTS
                          maximum number of snapshots to retain in sqlite3 database (default: 4) (Python 3.7 or higher)

  miscellaneous:
    --features            list supported job types, filters and reporters


Show errors and no-data jobs
----------------------------
You can run all jobs and see those that result in an error or who, after filtering, return no data, by running
`webchanges` with the ``--error`` argument. This can help with detecting jobs that may no longer be monitoring resources
as expected. No snapshots are saved from this run.

Test run a job
--------------
You can test a job and its filter by using the argument ``--test`` followed by the job index number (from ``--list``) or
its URL/command; `webchanges` will display the filtered output. This allows to easily test changes in filters.

.. _test-diff:

Show diff from saved snapshots
------------------------------
You can use the argument ``--test-diff`` followed by the job index number (from ``--list``) or its URL/command to
display diffs from snapshots that have been saved; obviously a minimum of 2 saved snapshots are required. This allows
you to test the effect of a diff filter or see previous changes.

`Changed in version 3.3: removed the limit of 10 diff being displayed`

.. _rollback-cache:

Rollback the database
---------------------
You can rollback the snapshots database to an earlier time by running `webchanges` with the ``--rollback-cache``
argument followed by a `Unix timestamp <https://en.wikipedia.org/wiki/Unix_time>`__ indicating the point in time you
want to go back to. Useful when you missed notifications or they got lost: rollback the database to the time of the last
good report, then run `webchanges` again to get a new report with the differences since that time.

You can find multiple sites that calculate Unix time for you, such as `www.unixtimestamp.com
<https://www.unixtimestamp.com/>`__

**WARNING: all snapshots captured after the time of the timestamp are permanently deleted. This is irreversible.**  Back
up the database before doing a rollback in case of a mistake (or fat-finger).

This feature does not work with database engines ``redis``, ``textfiles`` or ``minidb``.


`New in version 3.2.`



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
To use Redis as a database (cache) backend, simply specify a redis URI in the ``--cache`` argument:

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
To use the minidb-based database structure used in prior versions and in `urlwatch` 2, launch `webchanges` with the
command line argument ``--cache-engine minidb``. The ``minidib`` Python package must be installed for this to work.


`New in version 3.2.`



.. _max-snapshots:

Maximum number of snapshots to save
-----------------------------------
(Python 3.7 or higher only)

Each time you run `webchanges`, it captures the data downloaded from the URL (or the output of the command specified)
and saves it, after applying filters, to a database for future comparison.  By default (and when using the default
``sqlite3`` database engine) the last 4 snapshots are kept but this number can be changed with the
``--max-snapshots`` command line argument.  If it is set to 0, all snapshots are retained (no deletion of old snapshots
will take place).

Tip: changes between old snapshots can be redisplayed with the ``--test-diff`` command line argument (see
:ref:`here <test-diff>`).

Note that databases with ``redis`` or ``minidb`` database engines, or when running Python 3.6., will always retain all
snapshots (and grow to infinity), while with ``textfiles`` only the last snapshot is kept.


`New in version 3.3.`
