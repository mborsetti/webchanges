.. _command_line:

=====================
Command line switches
=====================

.. code-block:: none

  optional arguments:
    -h, --help            show this help message and exit
    -V, --version         show program's version number and exit
    -v, --verbose         show debug output

  override file defaults:
    --jobs FILE           read job list (URLs and/or commands) from FILE
    --config FILE         read configuration from FILE
    --hooks FILE          use FILE as hooks.py module
    --cache FILE          use FILE as cache database, alternatively can accept a redis URI

  job management:
    --list                list jobs
    --test JOB            test filter output of job by location or index
    --test-diff JOB       test diff filter output of job by location or index (needs at least 2 snapshots)
    --errors              list jobs with errors or no data captured
    --add JOB             add job (key1=value1,key2=value2,...) (obsolete; use --edit)
    --delete JOB          delete job by location or index (obsolete; use --edit)

  reporters:
    --test-reporter REPORTER
                          Send a test notification
    --smtp-login          Check SMTP login
    --telegram-chats      List telegram chats the bot is joined to
    --xmpp-login          Enter password for XMPP (store in keyring)

  launch editor ($EDITOR/$VISUAL):
    --edit                edit/create job list
    --edit-config         edit configuration file
    --edit-hooks          edit hooks script

  miscellaneous:
    --gc-cache            remove old cache entries (snapshots)
    --features            list supported jobs/filters/reporters
