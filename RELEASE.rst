Added
-----
* Python 3.13: **webchanges** now is tested on Python 3.13 before releasing. However, the `aioxmpp
  <https://pypi.org/project/aioxmpp/>`__ library required by the ``xmpp`` reporter will not install in Python 3.13 (at
  least on Windows), and the development of the `library <https://codeberg.org/jssfr/aioxmpp>`__ has been
  halted.

  - Python 3.13t (free-threaded, GIL-free) remains unsupported due to the lack of free-threaded wheels of dependencies
    such as ``cryptography``, ``msgpack``, ``lxml``, and the optional ``jq``.
* New Sub-directive in ``pypdf`` Filter: Added ``extraction_mode`` sub-directive.

Internals
---------
* Added ``ai_google`` directive to the ``image`` differ to test Generative AI summarization of differences between two
  images, but the results are still fairly bad and practically. This feature is in ALPHA and undocumented, and will
  not be developed further until the models improve to produce useful summaries.
