.. _configuration:

=============
Configuration
=============
The global configuration for :program:`webchanges` contains basic settings for the generic behavior of
:program:`webchanges`, including its :ref:`reports <reports>` and :ref:`reporters <reporters>`. It is written in **YAML
format**, is called ``config.yaml``, and is located in the in the following directory:

* Linux: ``~/.config/webchanges``
* MacOS: ``~/Library/Preferences/webchanges``
* Windows: ``%USERPROFILE%/Documents/webchanges`` (the webchanges folder within your Documents folder)

It can be edited with any text editor or with:

.. code:: bash

   webchanges --edit-config

.. tip:: (Linux) If you use this command and get an error, set your ``$EDITOR`` (or ``$VISUAL``) environment variable in
   your shell with a command such as ``export EDITOR=nano``.

For a summary of the YAML syntax, see :ref:`here <yaml_syntax>`.

Keys starting with an underscore (``_``) are ignored and are used by :program:`webchanges` for writing remarks to a
file:

.. code:: yaml

   _note: This is a remark


.. versionchanged:: 3.11
   Keys starting with an underscore (``_``) are ignored.

.. _configuration_display:

Display
-------
In addition to always reporting changes (which is the whole point of the program), :program:`webchanges` by default
reports newly-added (``new``) pages and errors (``error``). You can change this behavior in the ``display`` section of
the configuration:

.. code:: yaml

   display:
     new: true
     error: true
     unchanged: false
     empty_diff: true

If you set ``unchanged`` to ``true``, :program:`webchanges` will always report all pages that are checked but have not
changed.

While the ``empty_diff`` setting is included for backwards-compatibility, :program:`webchanges` uses the easier job
directive :ref:`additions_only` to obtain similar results, which you should use. This deprecated setting controls
what happens if a page is ``changed``, but due to e.g. a ``diff_filter`` the diff is reduced to the empty string. If set
to ``true``, :program:`webchanges`: will report an (empty) change. If set to ``false``, the change will not be included
in the report.


.. _reports-and-reporters:

Reports and Reporters
----------------------
Any report- or reporter-specific configuration must be inside the ``report`` directive in the configuration.

``text``, ``html`` and ``markdown`` are report types, and their settings apply to all reporters that use that type of
report (for example, the ``stdout`` reporter uses ``text``, while the ``email`` reporter with ``html: true`` uses
``html``; see :ref:`reporters <reporters>` for details).

Here is an example configuration that reports using UTC timezone on standard output in color, as well as HTML email
(one report for each job) using an SMTP server:

.. code:: yaml

   report:
     tz: Etc/UTC
     text:
       details: true
       footer: true
       line_length: 75
       minimal: false
       separate: false
     html:
       diff: unified
       separate: true
     email:  # This is the email reporter
       enabled: true
       from: 'Web watcher <webwatcher@example.com>'
       html: true
       method: smtp
       smtp:
         host: smtp.example.com
         user: 'username_goes_here'
         insecure_password: 'password_goes_here'
         auth: true
         port: 587
         starttls: true
       subject: '{count} changes: {jobs}'
       to: 'User <user@example.com>'
       stdout:
         color: true
         enabled: true
     markdown:
       minimal: false
       show_details: true
       show_footer: true
       separate: false

Configuration options for reports is described in :ref:`reports <reports>`.

Configuration options for reporters is described in :ref:`reporters <reporters>`.

Reporters are implemented in a hierarchy, and configuration settings of a report apply to all descendant reporters:

.. inheritance-ascii-tree:: webchanges.reporters.ReporterBase

.. note::
   Setting the ``email`` reporter's ``html`` option to ``true`` will cause it to inherit from the ``html``
   configuration.

.. _job_defaults:

Job Defaults
------------
If you want to apply or change default settings for all your jobs, add them to the ``job_defaults`` section in your
config file. The following example will set default headers for all ``url`` jobs without ``use_browser``:

.. code-block:: yaml

   job_defaults:
     _note: Default directives that are applied to jobs.
     url:
       _note: These are used for URL jobs without 'use_browser'.
       headers:
         Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9
         Accept-Language: en-US,en
         DNT: 1
         Sec-Fetch-Dest: document
         Sec-Fetch-Mode: navigate
         Sec-Fetch-Site: none
         Sec-Fetch-User: ?1
         Sec-GCP: 1
         Upgrade-Insecure-Requests: 1
         User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36

The above config file sets all ``url`` jobs without the ``browser`` directive to use the specified headers.


The possible sub-directives to ``job_defaults`` are:

* ``all``: Applies to all your jobs, including those in hooks.py;
* ``url``: Applies only to jobs with the directive ``url`` without ``use_browser``;
* ``browser``: Applies only to jobs with the directives ``url`` and ``use_browser: true``;
* ``command``: Applies only to jobs with the directive ``command``.

See :ref:`jobs <jobs>` about the different job kinds and directives that can be set.

Duplicate handling
******************
If a directive is specified both in ``all`` and either in ``url``, ``browser`` or ``command``, the one in ``all``
will be overridden, with the contents of ``headers`` being handled as if they were separate directives before being
overridden.



Database configuration
----------------------
If you want to change some settings for all your jobs, edit the ``database`` section in your config file:

.. code-block:: yaml

   database:
     engine: sqlite3
     max_snapshots: 4


.. _database_engine:

Default database engine
-------------------------
``engine``

You can select one of the engines from this list; the default engine can also be changed on an individual run with the
``--cache-engine`` command line argument.

Default (``sqlite3``)
*********************
In version 3.2 we migrated the internal database system to one that relies on the built-in ``sqlite3`` engine. This
is more efficient due to indexing, creates smaller files due to data compression with `msgpack <https://msgpack
.org/index.html>`__, and provides additional functionality such as no data corruption in case of an execution error.

This has also allowed us to remove the requirement for the ``minidb`` Python package. Migration of the latest snapshots
from the legacy (minidb) database is done automatically and the old file is preserved for manual deletion.

Text files (``textfiles``)
**************************
To have the latest snapshot of each job saved as a separate text file instead of as a record in a database, use
``textfiles``.

Legacy (``mindib``)
*******************
This will use a database that is backwards compatible with version 3.1 and with :program:`urlwatch` 2. The ``minidib``
Python package must be installed for this to work.

Redis (``redis://...`` or ``rediss://...``)
*******************************************
To use Redis as a database (cache) backend, specify a redis URI:

.. code-block:: yaml

   database:
     engine: redis://localhost:6379/

For this to work, optional dependencies need to be installed; please see :ref:`here <dependencies>`

There is no migration path from an existing database: the Redis database will be empty the first time it is used.



.. _database_max_snapshots:

Maximum number of snapshots to save
***********************************
``max_snapshots``

Each time you run :program:`webchanges`, it captures the data downloaded from the URL (or the output of the command
specified), applies filters, and if it finds a change it saves the resulting snapshot to a database for future
comparison. By default¹ only the last 4 changed snapshots are kept, but this number can be modified either in the
configuration file or, for an individual run, with the with the ``--max-snapshots`` command line argument.

If set to 0, all changed snapshots are retained (the database will grow unbounded).

.. tip:: Changes (diffs) between saved snapshots can be redisplayed with the ``--test-diff`` command line argument (see
   :ref:`here <test-diff>`).

¹ Note that when using ``redis`` or ``minidb`` database engines all snapshots will be kept, while when using the
``textfiles`` database engine only the last snapshot is kept.


.. versionadded:: 3.11
   for default ``sqlite3`` database engine only.



Omitting configuration directives
---------------------------------
When the ``config.yaml`` file is created, it contains all configuration directives and their default settings. If
you omit/remove any directive from this file, :program:`webchanges` will use the default value for the missing one. You
can see a list of such omitted/missing directives and the default values assigned when running with the ``--vv`` command
line argument.



Keys starting with underline are ignored
----------------------------------------
Keys that start with underline are ignored and can be used for remarks.

.. versionadded:: 3.11
