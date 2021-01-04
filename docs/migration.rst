.. _migration:

============================
Migration from urlwatch 2.22
============================

`webchanges` |version| is backward compatible with `urlwatch` 2.22 and its configuration files.

Changes
-------
The following items have changed and the old ones deprecated (will eventually be removed):

* Job directive ``kind`` is unused: remove from job
* Job directive ``navigate`` is deprecated: use ``url`` and add ``use_browser: true``
* Method ``pyhtml2text`` of filter ``html2text`` is deprecated; since that method is now the default, use no method
* Method ``re`` of filter ``html2text`` is changed: use ``strip_tags`` instead
* Filter ``grep`` is changed: use ``keep_lines_containing`` instead
* Filter ``grepi`` is changed: use ``delete_lines_containing`` instead
* Command line ``--test-filter`` is changed: use ``--test`` instead
* Command line ``--test-diff-filter`` is changed: use ``--test-diff`` instead
* The location of config files in Windows has changed to ``%USERPROFILE%/Documents/urlwatch``
  where they can be more easily edited and backed up
* The name of the default job file has changed to ``jobs.yaml`` (if ``urls.yaml`` is found at startup,
  it is copied to ``jobs.yaml`` automatically)

If you are upgrading from a version prior to 2.22, make sure that you have implemented all breaking changes in your
job and configuration files.  For example:

.. code-block:: yaml

   url: https://example.com/
   filter: html2text

no longer works in `urlwatch` 2.22, and therefore in `webchanges`, as all filters must be specified as subfilters like
this: (see `here <https://github.com/thp/urlwatch/pull/600#issuecomment-753944678>`_)

.. code-block:: yaml

   url: https://example.com/
   filter:
     - html2text:

