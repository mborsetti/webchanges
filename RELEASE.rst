Added
`````
* Job directives and configuration values are now type-checked when starting **webchanbges**. If a directive has the
  wrong type (e.g. a string where a boolean is expected), this will be shown at launch with a clear error instead of
  failing later during execution.
* New JSON Schemas for ``config.yaml`` and ``jobs.yaml`` are deployed next to those files, so editors that consume
  schemas from the same directory can offer autocompletion and validation. ``config.schema.json`` is written next to
  ``--config``, and ``jobs.schema.json`` next to the first ``--jobs`` file.

  - Note that while some editors automatically start using them, others (e.g. VS Code) require the line
  ``# yaml-language-server: $schema=config.schema.json`` to be inserted at the top of a config file, and the line
  ``# yaml-language-server: $schema=jobs.schema.json`` at the top of a jobs file and repeated after every ``---``
  separator (i.e. each individual job entry starts with it).

* ``--test-reporter <name>`` combined with a positional joblist now overrides the configured reporters: the listed
  jobs are fetched, filtered, and diffed against the snapshot database, and the resulting report is sent to the
  named reporter only (other reporters do not fire). Snapshots are not saved (read-only). Without a joblist,
  ``--test-reporter`` continues to send a dummy report to the named reporter as before.

Changed
```````
* The ``additions_only`` job directive now accepts a numeric ratio in ``[0, 1]`` (interpreted as the **minimum
  fraction of the original content that must remain** before the deletion-safeguard warning is triggered) in addition
  to a boolean. ``true`` remains equivalent to ``0.25`` (the historical default — warn when 25% or less of the
  original content remains, i.e. 75% or more has been removed). The directive also accepts the string
  ``"disable_safeguard"`` to keep additions-only filtering active while never showing deletions, even on a full
  wipe. ``false`` continues to disable additions-only filtering entirely. The diff safeguard message has been
  rephrased and now reports the actual remaining percentage (e.g. "only 45% of the original content remains").
* ``webchanges --list --verbose`` will now also display the internal ``guid`` value.
* ``webchanges --errors`` now honors a "joblist" of positional ``JOB(S)`` arguments (job index numbers and/or
  URLs/commands), restricting the error check to those jobs only. Without a joblist, all enabled jobs are checked
  as before.
* New ``-vvv`` (verbose level 3) command line argument to set the log level to Python's ``NOTSET`` for maximum
  verbosity.

Internals
`````````
* Fixed packaging so that the ``webchanges(1)`` man page is actually generated and installed.
* Improved testing and code coverage (work in progress).
