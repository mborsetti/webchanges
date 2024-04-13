.. role:: underline
    :class: underline

.. _dependencies:

============
Dependencies
============

.. _optional_packages:

Optional packages
-----------------
The use of certain features require additional Python packages to work. These optional packages are installed with
:program:`pip` by appending to the name :program:`webchanges` the name of the feature (from the table below) inside
square brackets, like this::

    pip install --upgrade webchanges[use_browser]
    pip install --upgrade webchanges[use_browser,redis]

.. note: also update the list of all possible dependencies in pyproject.tom and show_detailed_versions() in command.py!

+-------------------------+-------------------------------------------------------------------------+
| Feature                 | Python package(s) installed                                             |
+=========================+=========================================================================+
| ``use_browser``         | * `Playwright <https://playwright.dev/python/>`__                       |
| (in a ``url`` job)      | * `psutil <https://github.com/giampaolo/psutil>`__                      |
|                         | * Note: Google Chrome (if not present) will be auto-installed at first  |
|                         |   run                                                                   |
+-------------------------+-------------------------------------------------------------------------+
| :underline:`Filters`                                                                              |
+-------------------------+-------------------------------------------------------------------------+
| ``beautify`` filter     | * `beautifulsoup4 <https://www.crummy.com/software/BeautifulSoup/>`__   |
|                         | * `jsbeautifier <https://pypi.org/project/jsbeautifier/>`__ [#f2]_      |
|                         | * `cssbeautifier <https://pypi.org/project/cssbeautifier/>`__ [#f3]_    |
+-------------------------+-------------------------------------------------------------------------+
| ``bs4`` method of the   | * `beautifulsoup4 <https://www.crummy.com/software/BeautifulSoup/>`__   |
| html2text filter        |                                                                         |
+-------------------------+-------------------------------------------------------------------------+
| ``deepdiff`` differ     | * `deepdiff <https://github.com/seperman/deepdiff>`__                   |
+-------------------------+-------------------------------------------------------------------------+
| ``html5lib`` parser for | * `html5lib <https://pypi.org/project/html5lib/>`__                     |
| the bs4 method of the   |                                                                         |
| html2text filter        |                                                                         |
+-------------------------+-------------------------------------------------------------------------+
| ``ical2text`` filter    | * `vobject <https://eventable.github.io/vobject/>`__                    |
+-------------------------+-------------------------------------------------------------------------+
| ``imagediff`` differ    | * `Pillow <https://python-pillow.org>`__                                |
+-------------------------+-------------------------------------------------------------------------+
| ``jq`` filter           | * `jq <https://github.com/mwilliamson/jq.py>`__                         |
|                         | * **Only available for Linux and macOS** (Windows installation is       |
|                         |   incomplete)                                                           |
+-------------------------+-------------------------------------------------------------------------+
| ``ocr`` filter          | * `pytesseract <https://github.com/madmaze/pytesseract>`__              |
|                         | * Note: requires Tesseract to be **separately installed** [#f4]_        |
|                         | * `Pillow <https://python-pillow.org>`__                                |
+-------------------------+-------------------------------------------------------------------------+
| ``pdf2text`` filter     | * `pdftotext <https://github.com/jalan/pdftotext>`__                    |
|                         | * Note: you will also have to **separately install** OS-specific        |
|                         |   dependencies [#f5]_                                                   |
+-------------------------+-------------------------------------------------------------------------+
| ``pypdf`` filter        | * `pypdf <https://pypi.org/project/pypdf/>`__                           |
|                         | * Note: for PDF files that are not password-protected (otherwise use    |
|                         |   ``pypfd_crytpo``)                                                     |
+-------------------------+-------------------------------------------------------------------------+
| ``pypdf_crypto``        | * `pypdf[crypto] <https://pypi.org/project/pypdf/>`__                   |
|                         | * For the ``pypdf`` filter when using the ``password`` sub-directive    |
|                         |   to extract text from encrypted PDF files.                             |
+-------------------------+-------------------------------------------------------------------------+
| :underline:`Differs`                                                                              |
+-------------------------+-------------------------------------------------------------------------+
| ``deepdiff`` differ     | * `deepdiff <https://github.com/seperman/deepdiff>`__                   |
+-------------------------+-------------------------------------------------------------------------+
| :underline:`Reporters`                                                                            |
+-------------------------+-------------------------------------------------------------------------+
| ``matrix`` reporter     | * `matrix_client <https://github.com/matrix-org/matrix-python-sdk>`__   |
+-------------------------+-------------------------------------------------------------------------+
| ``pushbullet`` reporter | * `pushbullet.py <https://github.com/randomchars/pushbullet.py>`__      |
+-------------------------+-------------------------------------------------------------------------+
| ``pushover`` reporter   | * `chump <https://github.com/karanlyons/chump/>`__                      |
+-------------------------+-------------------------------------------------------------------------+
| ``xmpp`` reporter       | * `aioxmpp <https://github.com/horazont/aioxmpp>`__                     |
+-------------------------+-------------------------------------------------------------------------+
| :underline:`Others`                                                                               |
+-------------------------+-------------------------------------------------------------------------+
| ``redis`` database      | * `redis <https://github.com/andymccurdy/redis-py>`__                   |
+-------------------------+-------------------------------------------------------------------------+
| ``requests`` (to use    | * `requests <https://requests.readthedocs.io/>`__                       |
| ``http_client:          |                                                                         |
| requests`` in a job)    |                                                                         |
|                         |                                                                         |
+-------------------------+-------------------------------------------------------------------------+
| ``safe_password``       | * `keyring <https://github.com/jaraco/keyring>`__                       |
| keyring storage         |                                                                         |
+-------------------------+-------------------------------------------------------------------------+
| ``all``                 | * All the optional packages listed above                                |
|                         | * Note: you will also have to **separately install** OS-specific        |
|                         |   dependencies [#f4]_ [#f5]_                                            |
+-------------------------+-------------------------------------------------------------------------+

.. rubric:: Footnotes

.. [#f2] Optional, to beautify content of ``<script>`` tags.
.. [#f3] Optional, to beautify content of ``<style>`` tags.
.. [#f4] See Tesseract information `here <https://tesseract-ocr.github.io/tessdoc/Installation.html>`__.
.. [#f5] See pdftotext information `here <https://github.com/jalan/pdftotext#os-dependencies>`__.


Installed packages
------------------
These Python packages are installed automatically by :program:`pip` when installing :program:`webchanges`:

* `colorama <https://github.com/tartley/colorama>`__ (only in Windows installations);
* `cssselect <https://github.com/scrapy/cssselect>`__ (required by lxml.cssselect);
* `h2 <https://github.com/python-hyper/h2>`__;
* `html2text <https://github.com/Alir3z4/html2text>`__;
* `httpx <https://github.com/encode/httpx>`__;
* `lxml <https://lxml.de>`__;
* `markdown2 <https://github.com/trentm/python-markdown2>`__;
* `msgpack <https://msgpack.org/>`__;
* `platformdirs <https://github.com/platformdirs/platformdirs>`__;
* `PyYAML <https://pyyaml.org/>`__;
* `tzdata <https://tzdata.readthedocs.io/>`__ (only in Windows installations).
