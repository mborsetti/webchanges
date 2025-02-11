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
cron (``crontab -e``)::

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
``crontab -e``)::

  00 00 * * * webchanges --jobs slack.yaml --config config-slack.yaml
  05 00 * * * webchanges --jobs email --config config-email  # .yaml not necessary if no conflict


.. _always_report:


Comparing with several latest snapshots
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If a webpage frequently changes between several known stable states (e.g. A/B layout testing), it may be desirable to
have changes reported only if the content (webpage, URI, command result, etc.) changes into a new unknown state. You
can use compared_versions to do this.

.. code-block:: yaml

   url: https://example.com/
   compared_versions: 3

In this example, changes are only reported if the webpage becomes different from the latest three distinct states.
The differences are shown relative to the closest match.

Receiving a report for every run
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If you are watching pages that change seldomly, but you still want to be notified every time :program:`webchanges`
runs to know it's still working, you can add a job that monitors the output of the ``date`` command, for example:

.. code-block:: yaml

   name: Run date
   command: date

Since the output of ``date`` changes every second, this job should produce a report every time :program:`webchanges` is
run.


.. _resolving_issues:

.. _watching_sites:

Watching specific sites
-----------------------

.. _facebook_posts:

Facebook posts
^^^^^^^^^^^^^^
If you want to be notified of new posts on a public Facebook page, you can use the following job pattern; just
replace ``USERNAME`` with the name of the user (which can be found by navigating to user's page on your browser):

.. code-block:: yaml

   name: USERNAME's Facebook posts
   url: https://m.facebook.com/USERNAME/pages/permalink/?view_type=tab_posts
   filters:
     - xpath: //div[@data-ft='{"tn":"*s"}']
     - html2text: strip_tags
   additions_only: true


.. _facebook_events:

Facebook events
^^^^^^^^^^^^^^^
If you want to be notified of new events on a public Facebook page, you can use the following job pattern; just
replace ``USERNAME`` with the name of the user (which can be found by navigating to the user's page on your browser):

.. code-block:: yaml

   name: USERNAME's Facebook events
   url: https://m.facebook.com/USERNAME/pages/permalink/?view_type=tab_events
   filters:
     - css:
         selector: div#objects_container
         exclude: 'div.x, #m_more_friends_who_like_this, img'
     - re.sub:
         pattern: '(/events/\d*)[^"]*'
         repl: '\1'
     - html2text:
   additions_only: true


.. _github:

GitHub releases
^^^^^^^^^^^^^^^
This is an example how to anonymously watch the GitHub "releases" page of a project to be notified of new releases
(i.e. the latest/top-most tag):

.. code-block:: yaml

   url: https://github.com/git/git/releases
   filters:
     - xpath:
         path: //*[@class="Link--primary"]
         maxitems: 1
     - html2text:

If you only want to monitor the latest release and not include pre-releases:

.. code-block:: yaml

   url: https://github.com/Novik/ruTorrent/releases/latest
   filters:
     - xpath: //*[@class="ml-1"]
     - html2text:

Note that the easiest way to be notified if you have a GitHub account is to simply "watch" the project and subscribe
to email notifications (see `here
<https://docs.github.com/en/github/managing-subscriptions-and-notifications-on-github/managing-subscriptions-for
-activity-on-github/viewing-your-subscriptions>`__.


.. _gitlab:

GitLab tags (releases)
^^^^^^^^^^^^^^^^^^^^^^
This is an example how to anonymously watch the GitLab "tags" page for a given project to be notified of new releases:

.. code-block:: yaml

   url: https://gitlab.com/gitlab-org/gitlab/-/tags
   filters:
     - xpath: (//a[contains(@class,"item-title ref-name")])[1]
     - html2text:


.. _issues:

Resolving typical issues
-------------------------
Below are some job configurations that have helped to solve typical issues.

.. _default_headers:

Setting default headers
^^^^^^^^^^^^^^^^^^^^^^^
Many websites expect to receive headers that look like they came from a browser, and will fail if they don't. It is
possible to set default headers for HTTP requests by entering them in ``config.yaml`` under ``job_defaults``. If
``headers`` are also specified in a job, for that job the default headers will be merged (case-insensitively) and the
header(s) specified in the job will replace any default settings.

Below are headers extracted from Google Chrome 128 running in incognito mode on Windows in US English, in YAML format
useful for the ``config.yaml`` file. Note that the header "Accept-Encoding" is not included as it is set by the
ref:`Python HTTP client library <http_client>` based on what is supported by your system and the compression libraries
installed (e.g. see :ref:`here <zstd>` for support of zstd compression).

.. code-block:: yaml

   job_defaults:
     url:
       headers:
         Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7
         Accept-Language: en-US,en;q=0.9
         DNT: 1
         Priority: u=0, i
         Sec-CH-UA: '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"'
         Sec-CH-UA-Mobile: ?0
         Sec-CH-UA-Platform: '"Windows"'
         Sec-Fetch-Dest: document
         Sec-Fetch-Mode: navigate
         Sec-Fetch-Site: none
         Sec-Fetch-User: ?1
         Upgrade-Insecure-Requests: 1
         User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; 64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36


.. _example_cookies:

Supplying cookies
^^^^^^^^^^^^^^^^^
It is possible to add cookies to HTTP requests for pages that need them. For example:

.. code-block:: yaml

   url: https://example.com/
   cookies:
     Key: ValueForKey
     OtherKey: OtherValue


.. _example_timeout:

Changing the default timeout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
By default, ``url`` jobs timeout after 60 seconds. If you want a different timeout period, use the ``timeout`` directive
to specify it in number of seconds, or set it to 0 to never timeout.

.. code-block:: yaml

   url: https://example.com/
   timeout: 300


.. _ignoring_tls_ssl_errors:

Ignoring TLS/SSL errors
^^^^^^^^^^^^^^^^^^^^^^^
Setting ``ssl_no_verify`` to true may be useful during local development or testing.

When set to true, :program:`webchanges` requests will accept any TLS certificate presented by the server, and will
ignore hostname mismatches and/or expired certificates. Because this will make your application vulnerable to
man-in-the-middle (MitM) attacks, never use it outside of local development or testing.

.. code-block:: yaml

   url: https://example.com/
   ssl_no_verify: true


.. _ignoring_http_connection_errors:

Ignoring HTTP connection errors
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In some cases, it might be useful to ignore (temporary) network errors to avoid notifications being sent. While
you can set the ``errors`` directive of the ``display`` section to ``false`` in the :ref:`configuration file
<configuration_display>` to suppress global reporting of all jobs that end up with any type of error, to ignore
network errors for specific jobs only you can use the ``ignore_connection_errors`` directive in the job. For
connection errors during local development or testing with an invalid TLS certificate use the :ref:`ssl_no_verify`
directive above instead.

.. code-block:: yaml

   url: https://example.com/
   ignore_connection_errors: true

Similarly, you might want to ignore some (temporary) HTTP errors on the server side by using
``ignore_http_error_codes``:

.. code-block:: yaml

   url: https://example.com/
   ignore_http_error_codes: 408, 429, 500, 502, 503, 504

or ignore all HTTP errors if you like by using :ref:`ignore_http_error_codes`:

.. code-block:: yaml

   url: https://example.com/
   ignore_http_error_codes: 4xx, 5xx


Receive short notifications only containing the URL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If you only want to be alerted that there is a change without any information about the change itself, you can use a
a reporter that uses text and set report -> text -> details to false to avoid details being sent; you can also set
report -> text -> footer to false to make the report even shorter.

Don't forget that you can also use the directive :ref:`user_visible_url` to customize the URL that is reported visible
(e.g. watching a REST API endpoint, but wanting to show the "web-visible" URL in the report).

If you want the alert for one job only (of many), consider using the :ref:`sha1sum` filter instead.

For example, for email set these in the configuration file (``webchanges --edit-config``):

.. code-block:: yaml

   report:
     # ...
     text:
       details: false
       footer: false
       # ...
     email:
       html: false
       # ...


.. _errno_8:

Avoiding ``[Errno 8] nodename nor servname provided, or not known``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
On MacOS, if the DNS resolver is slow, jobs may start returning ``[Errno 8] nodename nor servname provided, or not
known`` errors.

If this is the case, you can either slow down the concurrency of jobs by running webchanges with a low value for
``--max-workers``, or, even better, try to fix the upstream DNS resolver issue.  For example, if you're only using the
public internet, you may want to try changing the default DNS servers to e.g. [Cloudflare]
(https://developers.cloudflare.com/1.1.1.1/ip-addresses/) and/or [Google]
(https://developers.google.com/speed/public-dns/docs/using) servers, following [Apple's instructions]
(https://support.apple.com/en-asia/guide/mac-help/mh14127/mac) or one of the many tutorials on the internet. You can
mix these servers for additional resiliency, e.g. use ``8.8.8.8``, ``1.1.1.1``, ``2001:4860:4860::8888`` and
``2606:4700:4700::1111``.
