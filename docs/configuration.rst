.. _configuration:

=============
Configuration
=============

The global configuration for `webchanges` contains basic settings for the generic behavior of `webchanges` as well as
the :ref:`reporters <reporters>` in **YAML format** called ``config.yaml`` and located in the ``~/.config/webchanges``
(Linux), ``~/Library/Preferences/webchanges`` (MacOS), or in the ``webchanges`` folder within your Documents folder,
i.e. ``%USERPROFILE%/Documents/webchanges`` (Windows). You can edit it with any text editor or:

.. code:: bash

   webchanges --edit-config


(Linux) If you use this command and get an error, set your ``$EDITOR`` (or ``$VISUAL``) environment variable in your
shell with a command such as ``export EDITOR=nano``.



**About YAML special characters**

Certain characters that could be present in names could have significance in the YAML format (e.g. certain special
characters at the beginning of the line or, anywhere, a ``:`` followed by a space or a space followed by ``#``, all
sort of brackets, and more) and therefore need to either be enclosed in quotes like so:

.. code-block:: yaml

   name: This is a human-readable name/label of the job  # and this is a remark
   name: "This human-readable name/label has a: colon followed by a space and space # followed by hashmark"
   name: "I can escape \"double\" quotes within a double quoted string which also has a colon: followed by a space"

You can learn more about quoting `here <https://www.yaml.info/learn/quote.html#flow>`__ (note: the library we use
supports YAML 1.1, and our examples use "flow scalars").  URLs are always safe and don't need to be enclosed in quotes.



.. _configuration_display:

Display
-------

In addition to always reporting changes (which is the whole point of webchanges), webchanges by default reports
newly-added (``new``) pages and errors (``error``). You can change this behavior in the ``display`` section of the
configuration:

.. code:: yaml

   display:
     new: true
     error: true
     unchanged: false

If you set ``unchanged`` to ``true``, webchanges will always report all pages that are checked but have not changed.


Filter changes are not applied for ``unchanged``
************************************************

Due to the way the filtered output is stored, ``unchanged`` will always report the old contents with the filters at the
time of retrieval, meaning that any changes you do to the ``filter`` of a job will not be visible in the ``unchanged``
report. When the page changes, the new filter will be applied.

For this reason, ``unchanged`` cannot be used to test filters, you should use the ``--test-filter`` command line option
to apply your current filter to the current page contents.


Reporters
---------

Configuration of reporters is described in :ref:`reporters <reporters>`.

Here is an example configuration that reports on standard output in color, as well as HTML email using ``sendmail``:

.. code:: yaml

   report:
     text:
       details: true
       footer: true
       line_length: 75
     html:
       diff: unified
     email:
       enabled: true
       method: sendmail
       sendmail:
           path: /usr/sbin/sendmail
       from: 'webchanges@example.org'
       to: 'you@example.org'
       html: true
       subject: '{count} changes: {jobs}'
     stdout:
       color: true
       enabled: true

Any reporter-specific configuration must be below the ``report`` directive in the configuration.

Configuration settings like ``text``, ``html`` and ``markdown`` will apply to all reporters that derive from that
reporter (for example, the ``stdout`` reporter uses ``text``, while the ``email`` reporter with ``html: true``
uses ``html``).

.. _job_defaults:

Job Defaults
------------

If you want to change some settings for all your jobs, edit the ``job_defaults`` section in your config file:

.. code-block:: yaml

   job_defaults:
     all:
       diff_tool: wdiff
     url:
       ignore_connection_errors: true

The above config file sets all jobs to use ``wdiff`` as diff tool, and all ``url`` jobs to ignore connection errors.

The possible sub-directives to ``job_defaults`` are:

* ``all``: Applies to all your jobs, independent of its kind
* ``shell``: Applies only to ``shell`` jobs (with directive ``command``)
* ``url``: Applies only to ``url`` jobs (with directive ``url`` and no ``use_browser``)
* ``browser``: Applies only to ``url`` jobs with directive ``use_browser`` set to **true**

See :ref:`jobs <jobs>` about the different job kinds and directives that can be set.
