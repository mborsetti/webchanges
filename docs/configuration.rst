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

Certain characters have significance in the YAML format, e.g. certain special characters at the beginning of the line,
a ``:`` followed by a space, a space followed by ``#``, all sort of brackets, and more. Strings containing these
characters or sequences need to be enclosed in quotes:

.. code-block:: yaml

   name: This is a human-readable name/label of the job  # and this is a remark
   name: "This human-readable name/label has a: colon followed by a space and a space followed by a # hash mark"
   name: "I can escape \"double\" quotes within a double quoted string which also has a colon: followed by a space"

You can learn more about quoting  `here <https://www.yaml.info/learn/quote.html#flow>`__ (note: the library we use
supports YAML 1.1, and our examples use "flow scalars").  URLs and XPaths are always safe and don't need to be enclosed
in quotes.


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

Here is an example configuration that reports on standard output in color, as well as HTML email using an SMTP server:

.. code:: yaml

   report:
     text:
       details: true
       footer: true
       line_length: 75
       minimal: false
     html:
       diff: unified
     email:
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

Any reporter-specific configuration must be inside the ``report`` directive in the configuration.

Reporter configuration settings for ``text`` and ``html`` apply to all reports that derive from that reporter (for
example, the ``stdout`` reporter uses ``text``, while the ``email`` reporter with ``html: true`` uses ``html``).

.. _job_defaults:

Job Defaults
------------
If you want to change some settings for all your jobs, edit the ``job_defaults`` section in your config file:

.. code-block:: yaml

   job_defaults:
     all:
       headers:
         Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9
         Accept-Language: en-US,en
         DNT: '1'
         Pragma: no-cache
         Sec-Fetch-Dest: document
         Sec-Fetch-Mode: navigate
         Sec-Fetch-Site: same-origin
         Sec-Fetch-User: ?1
         Upgrade-Insecure-Requests: '1'
         User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.66 Safari/537.36
     browser:
       chromium_revision: 782797
       switches:
         - --enable-experimental-web-platform-features
         - '--window-size=1920,1080'

The above config file sets all jobs to use the specified headers, and all ``url`` jobs with ``browser: true`` to
use a specific ref:`<chromium_revision>` and certain feature `switches
<https://peter.sh/experiments/chromium-command-line-switches/>`__.

The possible sub-directives to ``job_defaults`` are:

* ``all``: Applies to all your jobs, independent of its kind
* ``shell``: Applies only to ``shell`` jobs (with directive ``command``)
* ``url``: Applies only to ``url`` jobs (with directive ``url`` and no ``use_browser``)
* ``browser``: Applies only to ``url`` jobs with directive ``use_browser`` set to **true**

See :ref:`jobs <jobs>` about the different job kinds and directives that can be set.
