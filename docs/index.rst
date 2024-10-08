.. The documentation is made with Sphynx, the Python document generator. https://www.sphinx-doc.org/en/master/
   To see your changes before contributing, run 'make html' ('make_html.bat' in Windows) and check the html generated.
   Tutorial at https://sphinx-tutorial.readthedocs.io/start/

.. Excellent cheat sheet at https://sphinx-tutorial.readthedocs.io/cheatsheet/
   We use the recommended sequence for heading levels: = - ` : . ' " ~ ^ * + # ! $ % & ( ) , / ; < > ? @ [ \ ] { | }

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
   differs
   diff_filters
   reports
   reporters
   configuration
   cli
   dependencies
   yaml_syntax

.. toctree::
   :hidden:
   :caption: Examples

   examples

.. toctree::
   :hidden:
   :caption: Advanced

   advanced
   hooks
   under_the_hood

.. toctree::
   :hidden:
   :caption: Upgrading

   upgrading

.. toctree::
   :hidden:
   :caption: About webchanges

   contributing
   changelog
   license

.. see above for command to rebuild the API autodoc files

.. toctree::
   :hidden:
   :caption: API Reference

   _api/webchanges


.. include:: ../README.rst
