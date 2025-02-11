.. _configuration:

=============
Configuration
=============
The global configuration for :program:`webchanges` contains basic settings for the generic behavior of
:program:`webchanges`, including its :ref:`reports <reports>` and :ref:`reporters <reporters>`. It is written in **YAML
format**, is called ``config.yaml``, and is located in the following directory:

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
reports newly-added (``new``) pages and errors (``error``).

You can change what is reported in the ``display`` section of the configuration:

.. code:: yaml

   display:
     new: true
     error: true
     unchanged: false
     empty-diff: true  # deprecated

If you set ``unchanged`` to ``true``, :program:`webchanges` will always report all pages that are checked but have not
changed.

``empty-diff`` is deprecated, and controls what happens if a page is ``changed`` but the notification is reduced to
an empty string e.g. by a ``diff_filter``. If set to ``true``, :program:`webchanges`: will report an (empty) change.
If set to ``false``, the change will not be included in the report.  Use the job directive :ref:`additions_only`
instead for similar results.


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
       diff: unified  # Deprecated; specify a :ref:`differs <differs>` in the job
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

Job defaults
------------
If you want to apply or change default settings for all your jobs, add them to the ``job_defaults`` section in your
config file. The following example will set default headers for all ``url`` jobs without ``use_browser``:

.. code-block:: yaml

   job_defaults:
     all:
       _note: Default directives that are applied to all job kinds.
       suppress_repeated_errors: true
     url:
       _note: These are defaults for URL jobs without 'use_browser'.
       headers:
         Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7
         Accept-Language: en-US,en;q=0.9
         DNT: 1
         Priority: u=0, i
         Sec-CH-UA: '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"'
         Sec-CH-UA-Mobile: ?0
         Sec-CH-UA-Platform: '"Windows"'
         Sec-Fetch-Dest: document
         Sec-Fetch-Mode: navigate
         Sec-Fetch-Site: none
         Sec-Fetch-User: ?1
         Sec-GCP: 1
         Upgrade-Insecure-Requests: 1
         User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36

The above config file sets all jobs to use the suppress_repeated_errors option and ``url`` jobs without the ``browser``
directive to use the specified headers.

The possible sub-directives to ``job_defaults`` are:

* ``all``: Applies to all your jobs, including those in hooks.py;
* ``url``: Applies only to jobs with the directive ``url`` without ``use_browser``;
* ``browser``: Applies only to jobs with the directives ``url`` and ``use_browser: true``;
* ``command``: Applies only to jobs with the directive ``command``.

See :ref:`jobs <jobs>` for an explanation of the different job kinds and their directives.

Handling of duplicate directives
````````````````````````````````
Any directive specified in either ``url``, ``browser`` or ``command`` will override the same directive specified in
``all``.  In case of the ``headers`` directive, the overriding is done on a header-by-header basis.


.. _differ_defaults:

Differ defaults
---------------
If you want to apply or change default settings for a differ, add them to the ``differ_defaults`` section in your
config file. The following example will set the default model name to ``gemini-2.0-flash`` for the ``ai_google`` differ:

.. code-block:: yaml

   differ_defaults:
     _note: Default directives that are applied to individual differs.
     unified': {}
     ai_google':
       model: gemini-2.0-flash
     command': {}
     deepdiff': {}
     image': {}
     table': {}
     wdiff': {}

See :ref:`differs <differs>` for an explanation of the different differs and their directives.


Database configuration
----------------------
The ``database`` section in your config file contains information on how snapshots are stored from run to run:

.. code-block:: yaml

   database:
     engine: sqlite3
     max_snapshots: 4

.. _database_engine:

Database engine
```````````````
``engine``

You can select one of the database engines as specified below; this can be overridden with the ``--cache-engine``
command line argument.

``sqlite3``
:::::::::::
The default database engine, uses the ``sqlite3`` database built into Python with data compression provided by
`msgpack <https://msgpack.org/index.html>`__. It is the most advanced solution due its speed due to indexing, small
data files, and no data corruption or snapshot storage in case of an execution error.

The migration to this engine in version 3.2 allowed us to remove the requirement for the ``minidb`` Python package.

``textfiles``
:::::::::::::
Saves the latest snapshot of each job as its own individual text file. Only one snapshot can be saved, and both the
ETag (allowing the speeding up of web data retrieval) and MIME type (enabling some diffing and reporting automation)
will be lost.

``redis://...`` or ``rediss://...``
:::::::::::::::::::::::::::::::::::
To use Redis as a database (cache) backend, specify a redis URI:

``mindib``
::::::::::
The deprecated legacy database engine, it is backwards compatible with :program:`urlwatch`. Requires that
the ``minidib`` Python package is installed; MIME types are not stored, is not indexed, data is not compressed, and
the database file will grow indefinitely.

.. code-block:: yaml

   database:
     engine: redis://localhost:6379/

To use Redis, optional dependencies need to be installed; please see :ref:`here <dependencies>`

.. note:: Switching from Legacy (``mindib``) to Default (``sqlite3``) will cause an automatic data migration as long
   as the ``minidb`` Python package is installed; the old file database file is preserved for manual deletion. There is
   no migration path between any other databases types; for example, switching to Redis will create a new empty
   database at the first run.


.. _database_max_snapshots:

``max_snapshots``
`````````````````
Maximum number of snapshots to save

Each time you run :program:`webchanges`, it captures the data downloaded from the URL (or the output of the command
specified), applies filters, and if it finds a change it saves the resulting snapshot to a database for future
comparison. By default, only the last 4 changed snapshots are kept, but this number can be modified either in the
configuration file or with the ``--max-snapshots`` command line argument.

If set to 0, all changed snapshots are retained (the database will grow indefinitely).

.. note:: Only applicable to the ``sqlite3`` (default) database engine. When using ``redis`` or ``minidb``  database
   engines all snapshots will be kept (the database will grow indefinitely), while when using the ``textfiles``
   database engine only the last snapshot is kept.

.. tip:: Changes (diffs) between saved snapshots can be redisplayed with the ``--test-differ`` command line argument
   (see :ref:`here <test-differ>`).


.. versionadded:: 3.11
   For default ``sqlite3`` database engine only.



Omitting configuration directives
---------------------------------
When the ``config.yaml`` file is created, it contains all configuration directives and their default settings. If
you omit/remove any directive from this file, :program:`webchanges` will use the default value for the missing one. You
can see a list of such omitted/missing directives and the default values assigned when running with the ``--vv`` command
line argument.



Remarks
-------
YAML files do not allow for remarks; however, keys that start with underline are ignored and can be used for remarks.

.. versionadded:: 3.11
