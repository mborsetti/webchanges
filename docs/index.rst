.. The documentation is made with Sphynx, the Python document generator. https://www.sphinx-doc.org/en/master/
   To see your changes before contributing, run `make html` (`make.bat html` in Windows) and check the html generated.
   Tutorial at https://sphinx-tutorial.readthedocs.io/start/

.. Excellent cheat sheet at https://sphinx-tutorial.readthedocs.io/cheatsheet/

.. To rebuild the API autodoc files run $ sphinx-apidoc -o docs\_api -f -T -e webchanges -n


.. toctree::
   :hidden:
   :caption: Getting Started

   Overview <self>
   introduction

.. toctree::
   :hidden:
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
   :hidden:
   :caption: Advanced

   advanced
   hooks

.. toctree::
   :hidden:
   :caption: Migration

   migration

.. toctree::
   :hidden:
   :caption: About webchanges

   contributing
   changelog

.. see above for command to rebuild the API autodoc files

.. toctree::
   :hidden:
   :caption: API Reference

   _api/webchanges


.. include:: ../README.rst
