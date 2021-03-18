.. _command_line:

=====================
Command line switches
=====================

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
    --cache FILE          use FILE as a cache (snapshots database), alternatively can accept a redis URI

  job management:
    --list                list jobs
    --test JOB, --test-filter JOB
                          test filter output of job by location or index
    --test-diff JOB, --test-diff-filter JOB
                          test diff filter output of job by location or index (needs at least 2
                          snapshots)
    --errors              list jobs with errors or no data captured
    --add JOB             add job (key1=value1,key2=value2,...) (obsolete; use --edit)
    --delete JOB          delete job by location or index (obsolete; use --edit)

  reporters:
    --test-reporter REPORTER
                          send a test notification
    --smtp-login          check SMTP login
    --telegram-chats      list telegram chats the bot is joined to
    --xmpp-login          enter password for XMPP (store in keyring)

  launch editor ($EDITOR/$VISUAL):
    --edit                edit URL/job list
    --edit-config         edit configuration file
    --edit-hooks          edit hooks script

  miscellaneous:
    --gc-cache            garbage collect the cache database by removing old snapshots plus all data of
                          jobs not in the jobs file
    --clean-cache         remove old snapshots from the cache database
    --rollback-cache TIMESTAMP
                          delete recent snapshots > timestamp; backup the database before using!
    --database-engine {sqlite3,redis,minidb,textfiles}
                          database engine to use (default: sqlite3 unless redis URI in --cache)
    --features            list supported job types, filters and reporters


.. _rollback-cache:

Rollback the database
---------------------

You can rollback the snapshots database to an earlier time by running `webchanges` with the ``--rollback-cache`` switch
followed by a `Unix timestamp <https://en.wikipedia.org/wiki/Unix_time>`__ indicating the point in time you want to go
back to. Useful when you missed notifications or they got lost: rollback the database to the time of the last good
report, then run `webchanges` again to get a new report with the differences since that time.

You can find multiple sites that calculate Unix time for you, such as `www.unixtimestamp.com
<https://www.unixtimestamp.com/>`__

**WARNING: all snapshots captured after the time of the timestamp are permanently deleted. This is irreversible.**  Back
up the database before doing a rollback in case of a mistake (or fat-finger).

This feature does not work with database engines ``redis``, ``textfiles`` or ``minidb``.


`New in version 3.2.`



.. _database-engine:

Select a database engine
-------------------------

Default
~~~~~~~
The requirement for the ``minidb`` Python package has been removed in version 3.2 and the database system has migrated
to one that relies on the built-in ``sqlite3``, is more efficient due to indexing, creates smaller files due to data
compression with `msgpack <https://msgpack.org/index.html>`__, and provides additional functionality.

Migration of the latest snapshots from the legacy (minidb) database is done automatically and the old file is preserved
for manual deletion.

Redis
~~~~~
To use Redis as a database (cache) backend, simply specify a redis URI in the ``--cache switch``:

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
command line switch ``--cache-engine minidb``. The ``minidib`` Python package must be installed for this to work.


`New in version 3.2.`
