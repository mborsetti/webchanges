Added
-----
* Python 3.13 Testing: **webchanges** now is tested on Python 3.13 before releasing. However, the `aioxmpp
  <https://pypi.org/project/aioxmpp/>`__ library required by the ``xmpp`` reporter will not install in Python 3.13 (at
  least on Windows), and the development of the `library <https://codeberg.org/jssfr/aioxmpp>`__ has been
  halted.

Internals
---------
* Added ``ai_google`` directive to the ``image`` differ to test Generative AI summarization of differences between two
  images, but the results are still fairly bad and practically. This feature is in ALPHA and undocumented, and will
  not be developed further until the models improve to produce useful summaries.
