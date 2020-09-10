.. _migration:

============================
Migration from urlwatch 2.21
============================

`webchanges` |version| is backward compatible with `urlwatch` 2.21 and its configuration files.

Deprecations
------------
The following items are deprecated and will eventually be removed:

* Job directive ``kind``: remove from job (unused)
* Job directive ``navigate``: use ``url`` and add ``use_browser: true``
* Method ``pyhtml2text`` of filter ``html2text``: use ``html2text`` instead
* Method ``re`` of filter ``html2text``: use ``strip_tags`` instead
* Filter ``grep``: use ``keep_lines_containing`` instead
* Filter ``grepi``: use ``delete_lines_containing`` instead
* Command line ``--test-filter``: use ``--test`` instead
* Command line ``--test-diff-filter``: use ``--test-diff`` instead
* The location of config files in Windows has been moved to ``%USERPROFILE%/Documents/urlwatch``
  where they can be more easily edited and backed up.
* The name of the default job file has been changed to ``jobs.yaml`` (if ``urls.yaml`` is found at startup,
  it is copied over for backward-compatibility).


urwatch's 2.21 `urlwatch.yaml` sample file
------------------------------------------

.. code-block:: yaml

   # A basic URL job just needs a URL
   name: "urlwatch webpage"
   url: "https://thp.io/2008/urlwatch/"
   # You can use a pre-supplied filter for this, here we apply two:
   # the html2text filter that converts the HTML to plaintext and
   # the grep filter that filters lines based on a regular expression
   filter:
     - html2text
     - keep_lines_containing: "Current.*version"
     - strip
   ---
   # Built-in job kind "shell" needs a command specified
   name: "Echo test"
   command: "echo"
   #---
   #name: "Login to some webpage (custom job)"
   #url: "http://example.org/"
   # This job kind is defined in hooks.py, so you need to enable it
   #kind: custom-login
   # Additional parameters for the custom-login job kind can be specified here
   #username: "myuser"
   #password: "secret"
   # Filters can be specified here, separated by comma (these are also from hooks.py)
   #filter: case:upper,indent:5
   ---
   # If you want to use spaces in URLs, you have to URL-encode them (e.g. %20)
   url: "http://example.org/With%20Spaces/"
   ---
   # POST requests are done by providing a post parameter
   url: "http://example.com/search.cgi"
   data: "button=Search&q=something&category=4"
   ---
   # You can use a custom HTTP method, this might be useful for cache invalidation
   url: "http://example.com/foo"
   method: "PURGE"
   ---
   # You can do POST requests by providing data parameter.
   # POST data can be a URL-encoded string (see last example) or a dict.
   url: "http://example.com/search.cgi"
   data:
     button: Search
     q: something
     category: 4
