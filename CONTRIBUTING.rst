============
Contributing
============

|contributors|

.. |contributors| image:: https://img.shields.io/github/contributors/mborsetti/webchanges
    :target: https://www.github.com/mborsetti/webchanges
    :alt: contributors

Everyone is welcomed to contribute: there's even a `wish list
<https://github.com/mborsetti/webchanges/blob/master/WISHLIST.md>`__! Beginner? It's easy-ish to start! Please see this
`tutorial <https://github.com/firstcontributions/first-contributions/blob/master/README.md>`__.

If you can contribute with a `pull request
<https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull
-requests/about-pull-requests>`__, please do so. If not, open an issue `here
<https://github.com/mborsetti/webchanges/issues>`__ and someone will look into it.

Please make your contributions to the `unreleased <https://github.com/mborsetti/webchanges/tree/unreleased>`__ branch
and make sure to write a test for it (no decrease in coverage).

Documentation
-------------
Great documentation is absolutely key in any project. Please feel free to contribute edits and additions to
**webchanges**, especially if you're new! It is written in reStructuredText for Sphinx, and you can read a primer `here
<https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`__.

Code
----
Inline code docstrings, additional test coverage, bug fixes, extension of existing functionality, new
functionalities, and much more are always welcomed.

Please keep in mind PEP-20's `Zen of Python <https://www.python.org/dev/peps/pep-0020/>`__ when writing code:

- Beautiful is better than ugly.
- Explicit is better than implicit.
- Simple is better than complex.
- Complex is better than complicated.
- Flat is better than nested.
- Sparse is better than dense.
- Readability counts.
- Special cases aren't special enough to break the rules.
- Although practicality beats purity.
- Errors should never pass silently.
- Unless explicitly silenced.
- In the face of ambiguity, refuse the temptation to guess.
- There should be one-- and preferably only one --obvious way to do it.
- Although that way may not be obvious at first unless you're Dutch.
- Now is better than never.
- Although never is often better than *right* now.
- If the implementation is hard to explain, it's a bad idea.
- If the implementation is easy to explain, it may be a good idea.
- Namespaces are one honking great idea -- let's do more of those!


If you are contributing a filter, please make sure that you add an example to the documentation (``/docs/filters.rst``)
and the relevant data to ``/tests/data/docs_filters_testdata.yaml`` file to allow the example to be automatically
tested by ``/tests/docs_filters_test.py``.


Testing contributions
---------------------

Testing code
~~~~~~~~~~~~
You can ensure that your code contributions pass all tests by running tests locally (after installing all Python dev
packages, as below) before creating a pull request, starting from the project's root directory:

.. code-block:: bash

   uv pip install --update tox
   tox --parallel

Alternatively, you can manually run the following commands:

.. code-block:: bash

   uv pip install --update -r tests/requirements_pre-commit.txt -r tests/requirements_pytest.txt -r docs/requirements.txt
   pre-commit autoupdate
   pre-commit run -a
   python -m pytest -v --cov --cov-report=term

All tests need to pass, and the amount of lines covered by tests should not decrease (please write new tests or update
the existing ones to cover your new code!)

Testing documentation
~~~~~~~~~~~~~~~~~~~~~
You can build the documentation locally by using ``$ make html`` (Linux) or ``make_html.bat`` (Windows) from within
the docs directory to check for errors before contributing.


Unreleased version
------------------
To install the unreleased version with ``uv`` (recommended), please run:

.. code-block:: bash

   uv pip install https://github.com/mborsetti/webchanges/archive/unreleased.tar.gz

Using ``pip``:

.. code-block:: bash

   pip install https://github.com/mborsetti/webchanges/archive/unreleased.tar.gz
