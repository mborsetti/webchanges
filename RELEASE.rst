⚠ Breaking Changes
------------------
* Developers integrating custom Python code (``hooks.py``) should refer to the "Internals" section below for important
  changes.

Changed
-------
* Snapshot database

  - Moved the snapshot database from the "user_cache" directory (typically not backed up) to the "user_data" directory.
    The new paths are (typically):

    - Linux: ``~/.local/share/webchanges`` or ``$XDG_DATA_HOME/webchanges``
    - macOS: ``~/Library/Application Support/webchanges``
    - Windows: ``%LOCALAPPDATA%\webchanges\webchanges``

  - Renamed the file from ``cache.db`` to ``snapshots.db`` to more clearly denote its contents.
  - Introduced a new command line option ``--database`` to specify the filename for the snapshot database, replacing
    the previous ``--cache`` option (which is deprecated but still supported).
  - Many thanks to `Markus Weimar <https://github.com/Markus00000>`__ for pointing this problem out in issue `#75
    <https://github.com/mborsetti/webchanges/issues/75>`__.

* Modified the command line argument ``--test-differ`` to accept a second parameter, specifying the maximum number of
  diffs to generate.
* Updated the command line argument ``--dump-history`` to display the ``mime_type`` attribute when present.
* Enhanced differs functionality:

  - Standardized headers for ``deepdiff`` and ``imagediff`` to align more closely with those of ``unified``.
  - Improved the ``google_ai`` differ:

    - Enhanced error handling: now, the differ will continue operation and report errors rather than failing outright
      when Google API errors occur.
    - Improved the default prompt to ``Analyze this unified diff and create a summary listing only the
      changes:\n\n{unified_diff}`` for improved results.

Fixed
-----
* Fixed an AttributeError Exception when the fallback HTTP client package ``requests`` is not installed, as reported
  by `yubiuser <https://github.com/yubiuser>`__ in `issue #76 <https://github.com/mborsetti/webchanges/issues/76>`__.
* Addressed a ValueError in the ``--test-differ`` command, a regression reported by `Markus Weimar
  <https://github.com/Markus00000>`__ in `issue #79 <https://github.com/mborsetti/webchanges/issues/79>`__.
* To prevent overlooking changes, webchanges now refrains from saving a new snapshot if a differ operation fails
  with an Exception.

Internals
---------
* New ``mime_type`` attribute: we are now capturing and storing the data type (as a MIME type) alongside data in the
  snapshot database to facilitate future automation of filtering, diffing, and reporting. Developers using custom
  Python code will need to update their filter and retrieval methods in classes inheriting from FilterBase and
  JobBase, respectively, to accommodate the ``mime_type`` attribute. Detailed updates are available in the `hooks
  documentation <https://webchanges.readthedocs.io/en/stable/hooks.html#:~:text=Changed%20in%20version%203.22>`__.
* Updated terminology: References to ``cache`` in object names have been replaced with ``ssdb`` (snapshot database).
* Int
