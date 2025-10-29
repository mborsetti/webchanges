.. _under_the_hood:

==============
Under the hood
==============

Parallelism
-----------
All jobs are run in parallel threads for optimum speed.

Jobs that don't have ``use_browser: true`` are run first using the default maximum number of workers set by Python's
`concurrent.futures.ThreadPoolExecutor
<https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor>`__, currently the
number of processors on the machine multiplied by 5 (Python 3.10).

Jobs that have ``use_browser: true`` (and therefore require the Google Chrome browser to run) will be run next using
a maximum number of workers that is the lower of the number of processors on the machine and, if known, the available
physical memory (as reported by the Python package `psutil <https://psutil.readthedocs.io/en/latest/#memory>`__) divided
by 200 MB.

You can see the number of threads employed on your machine by running :program:`webchanges` with ``--verbose`` and
searching for the DEBUG log messages having the text ``max_workers``.

.. _conditional_requests:

Use of conditional requests (timestamp, ETag)
---------------------------------------------
:program:`webchanges` uses `RFC 7232 <https://datatracker.ietf.org/doc/html/rfc7232>`__ conditional requests to 
efficiently check for website updates. After the first check of a ``url`` job, subsequent requests include special 
HTTP headers:

*   ``If-Modified-Since``: Uses the timestamp of the last check.
*   ``If-None-Match``: Uses a unique identifier (ETag) provided by the server from the previous check.

This mechanism applies to all ``url`` jobs, including those that use a browser (``use_browser: true``).

This is a performance optimization. If the content hasn't changed, the server responds with a ``304 Not Modified`` 
status code and no content, speeding up execution and reducing bandwidth usage. :program:`webchanges` understands this 
response and knows that the content is unchanged.

In the extremely rare cases where the web server does not correctly process conditional requests (e.g. Google Flights),
it can be turned off with the ``no_conditional_request: true`` :ref:`directive <no_conditional_request>`.

Details
^^^^^^^
The ``If-Modified-Since`` header tells the server to send the resource only if it has been modified after the specified
date. If not, the server sends a ``304`` response without the content. The ``Last-Modified`` header from the server's
previous response provides this date.

The ``If-None-Match`` header works similarly, but with ETags. For ``GET`` and ``HEAD`` requests, the server sends the
full resource only if the ETag doesn't match. Otherwise, it returns a ``304`` status.

:program:`webchanges` accepts "weak comparison" for ETags. This means that content may be considered identical by a
server if it's semantically equivalent, even if not byte-for-byte the same. For instance, a page that only changes its
footer timestamp to the current time could be considered unchanged by the server if nothing else but the time diplayed
is modified between visits.

When both headers are used, ``If-None-Match`` takes precedence if the server supports it.
