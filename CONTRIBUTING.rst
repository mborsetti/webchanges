Everyone is welcomed to contribute!

Beginners see this `tutorial <https://github.com/firstcontributions/first-contributions/blob/master/README.md>`__;
documentation is a great place to start.

Documentation
-------------

Great documentation is absolutely key in any a project.  Please feel free to contribute edits and additions to it,
especially if you're new!  It is written in reStructuredText for Sphinx, and you can read a primer `here
<https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`__.

Code
----

Inline code docstrings (sorely needed!), additional test coverage (also needed!), bug fixes, extension of existing
functionality, new functionalities, and more are always welcomed.

Tip: you can ensure that your contribution will pass all tests by running tests locally (after installing
all Python dev packages):

.. code-block:: bash

   pip install -U webchanges[testing]
   # linux:
   coverage run --source=webchanges -m pytest -v
   # Windows:
   coverage.bat

All tests need to pass, and the amount of lines covered by tests should not decrease.

Open an issue
-------------

If you can provide a solution as a pull request, please do so. If not, open an issue `here
<https://github.com/mborsetti/webchanges/issues>`__ and someone will look into it.