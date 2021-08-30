.. _examples:

===================
Examples
===================

Running webchanges
------------------

Checking different sources at different intervals
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You can divide your jobs into multiple job lists depending on how often you want to check. For example, you can have
a ``daily.yaml`` job list for daily jobs, and a ``weekly.yaml`` for weekly ones. You then set up the scheduler to
run :program:`webchanges`, defining which job list to use, at different intervals. For example in Linux/macOS using
crontab::

  0 0 * * * webchanges --jobs daily.yaml
  0 0 0 * * webchanges --jobs weekly  # alias for weekly.yaml (if 'weekly' isn't found)


Alternatively, you can ref:`select of a subset of jobs<job_subset>` to run only a few jobs. For example, if you want
to run all jobs every day at midnight and in addition you want to run jobs 1 and 4 also at noon, you can do (in
Linux/macOS using crontab)::

  0  0 * * * webchanges
  0 12 * * * webchanges 1 4


Getting reports via different channels for different sources
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Job-specific alerts (reports) is not a functionality of :program:`webchanges`, but you can work around this by creating
multiple configurations and job lists, and run :program:`webchanges` multiple times specifying ``--jobs`` and
``--config``.

For example, you can create two configuration files, e.g. ``config-slack.yaml`` and ``config-email.yaml`` (the
first set for slack reporting and the second for email reporting) and two job lists, e.g. ``slack.yaml`` and
``email.yaml`` (the first containing jobs you want to be notified of via slack, the second for jobs you want to be
notified of via email). You can then run :program:`webchanges` similarly to the below example (taken from Linux/macOS
crontab)::

  00 00 * * * webchanges --jobs slack.yaml --config config-slack.yaml
  05 00 * * * webchanges --jobs email --config config-email  # .yaml not necessary if no conflict


.. _always_report:

Receiving a report every time webchanges runs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If you are watching pages that change seldomly, but you still want to be notified evert time :program:`webchanges`
runs to know it's still working, you can monitor the output of the ``date`` command, for example:

.. code-block:: yaml

   name: webchanges run
   command: date

Since the output of ``date`` changes every second, this job should produce a report every time webchanges is run.


.. _resolving_issues:

.. _watching_sites:

Watching specific sites
-----------------------

.. _facebook_posts:

Facebook posts
^^^^^^^^^^^^^^
If you want to be notified of new posts on a public Facebook page, you can use the following job pattern; just replace
``USERNAME`` with the name of the user (which can be found by navigating to user's page on your browser):

.. code-block:: yaml

   name: USERNAME's Facebook posts
   url: https://m.facebook.com/USERNAME/pages/permalink/?view_type=tab_posts
   filter:
     - xpath: //div[@class="story_body_container"]
     - html2text:
   additions_only:


.. _facebook_events:

Facebook events
^^^^^^^^^^^^^^^
If you want to be notified of new events on a public Facebook page, you can use the following job pattern; just replace
``USERNAME`` with the name of the user (which can be found by navigating to the user's page on your browser):

.. code-block:: yaml

   name: USERNAME's Facebook events
   url: https://m.facebook.com/USERNAME/pages/permalink/?view_type=tab_events
   filter:
     - css:
         selector: div#objects_container
         exclude: 'div.x, #m_more_friends_who_like_this, img'
     - re.sub:
         pattern: '(/events/\d*)[^"]*'
         repl: '\1'
     - html2text:
   additions_only:


.. _github:

GitHub releases
^^^^^^^^^^^^^^^
This is an example how to anonymously watch the GitHub “releases” page of a project to be notified of new releases:

.. code-block:: yaml

   url: https://github.com/git/git/releases
   filter:
     - xpath: //div[contains(@class,"release-")]//h4[1]/a|//div[contains(@class,"release-header")]/div/div/a
     - html2text:

Note that the easiest way to be notified if you have a GitHub account is to simply "watch" the project and subscribe
to email notifications (see `here
<https://docs.github.com/en/github/managing-subscriptions-and-notifications-on-github/managing-subscriptions-for
-activity-on-github/viewing-your-subscriptions>`__.


.. _gitlab:

GitLab tags (releases)
^^^^^^^^^^^^^^^^^^^^^^
This is an example how to anonymously watch the GitLab “tags” page for a given project to be notified of new releases:

.. code-block:: yaml

   url: https://gitlab.com/gitlab-org/gitlab/-/tags
   filter:
     - xpath: (//a[contains(@class,"item-title ref-name")])[1]
     - html2text:


.. _issues:

Resolving typical issues
-------------------------
Below are some job configurations that have helped to solve typical issues.


.. _timeout:

Changing the default timeout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
By default, url jobs timeout after 60 seconds. If you want a different timeout period, use the ``timeout`` directive to
specify it in number of seconds, or set it to 0 to never timeout.

.. code-block:: yaml

   url: https://example.com/
   timeout: 300


.. _headers:

Setting default headers
^^^^^^^^^^^^^^^^^^^^^^^
It is possible to set default headers for HTTP requests by entering them in ``config.yaml`` under ``job_defaults``, as
per the example below. If a ``headers`` key is also found in a job, for that job the headers will be merged
(case-insensitively) one by one with any conflict resolved in favor of the header specified in the job.

.. code-block:: yaml

   job_defaults:
     all:
       headers:
         Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9
         Accept-Language: en-US,en
         Device-Memory: '0.25'
         DNT: '1'
         Downlink: '0.384'
         DPR: '1.5'
         ECT: slow-2g
         RTT: '250'
         Sec-CH-UA: '"Google Chrome";v="89", "Chromium";v="89", ";Not A Brand";v="99"'
         Sec-CH-UA-Mobile: '?0'
         Sec-CH-UA-Platform: 'Windows'
         Sec-CH-UA-Platform-Version: '10.0'
         Sec-Fetch-Dest: document
         Sec-Fetch-Mode: navigate
         Sec-Fetch-Site: none
         Sec-Fetch-User: '?1'
         Sec-GPC: '1'
         Upgrade-Insecure-Requests: '1'
         User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; 64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4389.114 Safari/537.36
         Viewport-Width: '1707'


.. _cookies:

Supplying cookies
^^^^^^^^^^^^^^^^^
It is possible to add cookies to HTTP requests for pages that need them, for example:

.. code-block:: yaml

   url: https://example.com/
   cookies:
       Key: ValueForKey
       OtherKey: OtherValue


.. _ssl_no_verify:

Ignoring TLS/SSL errors
^^^^^^^^^^^^^^^^^^^^^^^
Setting ``ssl_no_verify`` to true may be useful during local development or testing.

When set to true, :program:`webchanges` requests will accept any TLS certificate presented by the server, and will
ignore hostname mismatches and/or expired certificates. Because this will make your application vulnerable to
man-in-the-middle (MitM) attacks, never use it outside of local development or testing.

.. code-block:: yaml

   url: https://example.com/
   ssl_no_verify: true


.. _ignore_errors:

Ignoring HTTP connection errors
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In some cases, it might be useful to ignore (temporary) network errors to avoid notifications being sent. While
you can set the ``errors`` directive of the ``display`` section to ``false`` in the ref:`configuration file
<configuration_display>` to suppress global reporting of all jobs that end up with any type of error, to ignore
network errors for specific jobs only you can use the ``ignore_connection_errors`` directive in the job. For
connection errors during local development or testing due to TLS/SSL use the ``ssl_no_verify`` directive above instead.

.. code-block:: yaml

   url: https://example.com/
   ignore_connection_errors: true

Similarly, you might want to ignore some (temporary) HTTP errors on the server side:

.. code-block:: yaml

   url: https://example.com/
   ignore_http_error_codes: 408, 429, 500, 502, 503, 504

or ignore all HTTP errors if you like:

.. code-block:: yaml

   url: https://example.com/
   ignore_http_error_codes: 4xx, 5xx
