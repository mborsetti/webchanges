============
Contributing
============

|contributors|

.. |contributors| image:: https://img.shields.io/github/contributors/mborsetti/webchanges
    :target: https://www.github.com/mborsetti/webchanges
    :alt: contributors

Everyone is welcomed to contribute!

Beginner? It's easy-ish to start! See this `tutorial
<https://github.com/firstcontributions/first-contributions/blob/master/README.md>`__;

Documentation
-------------

Great documentation is absolutely key in any a project.  Please feel free to contribute edits and additions to it,
especially if you're new!  It is written in reStructuredText for Sphinx, and you can read a primer `here
<https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`__.

Code
----

Inline code docstrings (sorely needed!), additional test coverage (also needed!), bug fixes, extension of existing
functionality, new functionalities, and more are always welcomed.

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

Testing
~~~~~~~
Tip: you can ensure that your contribution will pass all tests by running tests locally (after installing
all Python dev packages):

.. code-block:: bash

   pip install -U webchanges[testing]
   # Linux:
   python -m coverage run
   # Windows:
   coverage.bat

All tests need to pass, and the amount of lines covered by tests should not decrease.

Open an issue
-------------

If you can provide a solution as a pull request, please do so. If not, open an issue `here
<https://github.com/mborsetti/webchanges/issues>`__ and someone will look into it.