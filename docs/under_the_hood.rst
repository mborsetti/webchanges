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
by 120 MB.

You can see the number of threads employed on your machine by running :program:`webchanges` with ``--verbose`` and
searching for the DEBUG log messages having the text ``max_workers``.

Use of conditional requests (timestamp, ETag)
---------------------------------------------
Once a website (``url``) has been checked once, any subsequent checks will be made as a conditional request by setting
the HTTP headers ``If-Modified-Since`` and, if an ETag was returned, the ``If-None-Match``. This is also true for jobs
where ``use_browser`` is set to ``true`` (i.e. using Google Chrome).

The conditional request is an optimization to speed up execution: if there are no changes to the resource, the server
doesn't need to send it but instead just sends a 304 HTTP response code which :program:`webchanges` understands.

Details
^^^^^^^
With the ``If-Modified-Since`` request HTTP header the server sends back the requested resource, with a 200 status, only
if it has been last modified after the given date. If the resource has not been modified since, the response is a 304
without any body; the ``Last-Modified`` response header of a previous request contains the date of last modification.

With the ``If-None-Match`` request HTTP header, for ``GET`` and ``HEAD`` methods, the server will return the requested
resource, with a 200 status, only if it doesn't have an ETag matching the given ones. For other methods, the request
will be processed only if the eventually existing resource's ETag doesn't match any of the values listed. When the
condition fails for ``GET`` and ``HEAD`` methods, then the server must return HTTP status code 304 (Not Modified). The
comparison with the stored ETag uses the weak comparison algorithm, meaning two files are considered identical if the
content is equivalent — they don't have to be identical byte by byte. For example, two pages that differ by their
creation date in the footer would still be considered identical. When used in combination with ``If-Modified-Since``,
``If-None-Match`` has precedence (if the server supports it).
