.. The documentation is made with Sphynx, the Python document generator.
   https://www.sphinx-doc.org/en/master/
   To see your changes before contributing, run `make html` (`make.bat html` in Windows)
   and check the html generated.
   Tutorial at https://sphinx-tutorial.readthedocs.io/start/


.. highlight:: none

.. include:: ../README.rst

=================
Table of Contents
=================
.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   Overview <self>
   introduction
   yaml_syntax

.. toctree::
   :maxdepth: 1
   :caption: In Depth

   jobs
   filters
   configuration
   diff_filters
   reports
   reporters
   dependencies

.. toctree::
   :maxdepth: 1
   :caption: Advanced

   advanced
   hooks
   cli

.. toctree::
   :maxdepth: 1
   :caption: Migration

   migration

.. toctree::
   :maxdepth: 1
   :caption: About webchanges

   contributing
   changelog

.. autosummary::
   :toctree: _autosummary
   :caption: Code autodoc
   :recursive:

   webchanges
