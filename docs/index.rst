.. The documentation is made with Sphynx, the Python document generator.
   https://www.sphinx-doc.org/en/master/
   To see your changes before contributing, run `make html` (`make.bat html` in Windows)
   and check the html generated.
   Tutorial at https://sphinx-tutorial.readthedocs.io/start/

.. to rebuild the API autodoc run $ sphinx-apidoc -f -e -T -o docs\_api webchanges


.. highlight:: none

.. include:: ../README.rst

------------

===============================
Documentation table of contents
===============================
.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   Overview <self>
   introduction

.. toctree::
   :maxdepth: 1
   :caption: In Depth

   jobs
   filters
   configuration
   diff_filters
   reports
   reporters
   cli
   dependencies
   yaml_syntax

.. toctree::
   :maxdepth: 1
   :caption: Advanced

   advanced
   hooks

.. toctree::
   :maxdepth: 1
   :caption: Migration

   migration

.. toctree::
   :maxdepth: 1
   :caption: About webchanges

   contributing
   changelog

.. to rebuild the API autodoc run $ sphinx-apidoc -f -e -T -o docs\_api webchanges

.. toctree::
   :caption: API Reference

   _api/webchanges
