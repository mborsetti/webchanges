Fixed
`````
* Fixed UnboundLocalError when using new ``utf-8`` sub-directive within the ``smtp`` emailer (``email`` report).
  Reported in #`104 <https://github.com/mborsetti/webchanges/issues/110>`__.

Internals
`````````
* Removed workaround for Python 3.9, which is no longer supported.
