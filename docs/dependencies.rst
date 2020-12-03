.. _dependencies:

============
Dependencies
============

.. _optional_packages:

Optional packages
-----------------

Certain features require additional Python packages to work. These optional packages are installed by appending
to the name `webchanges` the name of the feature (from the table below) inside square brackets, like so::

    pip install --upgrade webchanges[use_browser]
    pip install --upgrade webchanges[use_browser,redis]

+-------------------------+-------------------------------------------------------------------------+
| Feature                 | Python package(s) installed                                             |
+=========================+=========================================================================+
| ``use _browser`` set to | * `pyppeteer <https://github.com/pyppeteer/pyppeteer>`__                |
| true (in a url job)     |   Note: you may also have to **separately install**                     |
|                         |   OS-specific dependencies [#f1]_                                       |
+-------------------------+-------------------------------------------------------------------------+
| ``bs4`` method of the   | * `beautifulsoup4 <https://www.crummy.com/software/BeautifulSoup/>`__   |
| html2text filter        |                                                                         |
|                         |                                                                         |
+-------------------------+-------------------------------------------------------------------------+
| ``beautify`` filter     | * `beautifulsoup4 <https://www.crummy.com/software/BeautifulSoup/>`__   |
|                         | * `jsbeautifier <https://pypi.org/project/jsbeautifier/>`__ [#f2]_      |
|                         | * `cssbeautifier <https://pypi.org/project/cssbeautifier/>`__ [#f3]_    |
+-------------------------+-------------------------------------------------------------------------+
| ``pdf2text`` filter     | * `pdftotext <https://github.com/jalan/pdftotext>`__                    |
|                         |   Note: you will also have to **separately install** the required       |
|                         |   OS-specific dependencies [#f4]_                                       |
+-------------------------+-------------------------------------------------------------------------+
| ``ocr`` filter          | * `pytesseract <https://github.com/madmaze/pytesseract>`__              |
|                         |   Note: requires Tesseract to be **separately installed** [#f5]_        |
|                         | * `Pillow <https://python-pillow.org>`__                                |
+-------------------------+-------------------------------------------------------------------------+
| ``ical2text`` filter    | * `vobject <https://eventable.github.io/vobject/>`__                    |
+-------------------------+-------------------------------------------------------------------------+
| ``pushover`` reporter   | * `chump <https://github.com/karanlyons/chump/>`__                      |
+-------------------------+-------------------------------------------------------------------------+
| ``pushbullet`` reporter | * `pushbullet.py <https://github.com/randomchars/pushbullet.py>`__      |
+-------------------------+-------------------------------------------------------------------------+
| ``matrix`` reporter     | * `matrix_client <https://github.com/matrix-org/matrix-python-sdk>`__   |
+-------------------------+-------------------------------------------------------------------------+
| ``xmpp`` reporter       | * `aioxmpp <https://github.com/horazont/aioxmpp>`__                     |
+-------------------------+-------------------------------------------------------------------------+
| ``redis`` database      | * `msgpack <https://msgpack.org/>`__                                    |
|                         | * `redis <https://github.com/andymccurdy/redis-py>`__                   |
+-------------------------+-------------------------------------------------------------------------+
| ``safe_password``       | * `keyring <https://github.com/jaraco/keyring>`__                       |
| storage for email and   |                                                                         |
| xmpp reporters          |                                                                         |
+-------------------------+-------------------------------------------------------------------------+
| ``testing``             | * `pytest <https://docs.pytest.org/en/latest/>`__                       |
|                         | * `coverage <https://github.com/nedbat/coveragepy>`__                   |
| (to work on             | * `flake8 <https://gitlab.com/pycqa/flake8>`__                          |
| contributions to the    | * `flake8-import-order                                                  |
| project)                |   <https://github.com/PyCQA/flake8-import-order>`__                     |
|                         | * `docutils <https://docutils.sourceforge.io>`__                        |
|                         | * `sphinx <https://www.sphinx-doc.org/en/master/>`__                    |
|                         | * `sphinx_rtd_theme <https://github.com/readthedocs/sphinx_rtd_theme>`__|
|                         | * all the dependencies listed above except for pdf2text and ocr         |
+-------------------------+-------------------------------------------------------------------------+
| ``all``                 | * all the optional packages listed above, including for testing         |
|                         |   Note: you will also have to **separately install** the required       |
|                         |   OS-specific dependencies [#f1]_ [#f4]_ [#f5]_                         |
+-------------------------+-------------------------------------------------------------------------+

.. rubric:: Footnotes

.. [#f1] ``pypetteer``'s OS-specific dependencies (non required in Windows or MacOS) are listed `here
   <https://github.com/puppeteer/puppeteer/blob/main/docs/troubleshooting.md#chrome-headless-doesnt-launch>`__.
   A missing dependency is often the cause of the error ``pyppeteer.errors.BrowserError: Browser closed unexpectedly``.
.. [#f2] Optional, to beautify content of <script> tags
.. [#f3] Optional, to beautify content of <style> tags
.. [#f4] see https://github.com/jalan/pdftotext#os-dependencies
.. [#f5] see https://tesseract-ocr.github.io/tessdoc/Home.html


Installed packages
------------------

These Python packages are installed automatically by `pip`:

* `appdirs <https://github.com/ActiveState/appdirs>`__
* `cssselect <https://github.com/scrapy/cssselect>`__ (required by lxml.cssselect)
* `html2text <https://github.com/Alir3z4/html2text>`__
* `lxml <https://lxml.de>`__
* `markdown2 <https://github.com/trentm/python-markdown2>`__
* `minidb <https://thp.io/2010/minidb/>`__
* `PyYAML <https://pyyaml.org/>`__
* `requests <https://requests.readthedocs.io/en/master/>`__
* `colorama <https://github.com/tartley/colorama>`__  (for Windows installations)