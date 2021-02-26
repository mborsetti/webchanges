============
Contributing
============

|contributors|

.. |contributors| image:: https://img.shields.io/github/contributors/mborsetti/webchanges
    :target: https://www.github.com/mborsetti/webchanges
    :alt: contributors

Everyone is welcomed to contribute!

Beginner? It's easy-ish to start! Please see this `tutorial
<https://github.com/firstcontributions/first-contributions/blob/master/README.md>`__.

Please make your contributions to the `unrealeased <https://github.com/mborsetti/webchanges/tree/unreleased>`__ branch.

Documentation
-------------
Great documentation is absolutely key in any a project.  Please feel free to contribute edits and additions to it,
especially if you're new!  It is written in reStructuredText for Sphinx, and you can read a primer `here
<https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`__.

Code
----
Inline code docstrings (sorely needed!), additional test coverage (also needed!), type hinting, bug fixes, extension of
existing functionality, new functionalities, and much more are always welcomed.

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


Testing code
~~~~~~~~~~~~
You can ensure that your code contributions pass all tests by running tests locally (after installing all Python dev
packages, as below) before creating a pull request, starting from the project's root directory:

.. code-block:: bash

   pip install -U tox -r tests/requirements_testing.txt
   tox

Alternatively, you can manually run the following commands

   pip install -U -r tests/requirements_testing.txt
   pre-commit autoupdate
   pre-commit run -a
   python -m pytest -v

All tests need to pass, and the amount of lines covered by tests should not decrease.

Testing documentation
~~~~~~~~~~~~~~~~~~~~~
For documentation, build it locally using ``$ make html`` (Linux) or ``make_html.bat`` (Windows) from within the docs
directory and monitor for errors.

Open an issue
-------------
If you can provide a solution as a pull request, please do so. If not, open an issue `here
<https://github.com/mborsetti/webchanges/issues>`__ and someone will look into it.
