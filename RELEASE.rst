.. Categories used (in order):
   ⚠ Breaking Changes for changes that break existing functionality.
   Added for new features.
   Changed for changes in existing functionality.
   Deprecated for soon-to-be removed features.
   Removed for now removed features.
   Fixed for any bug fixes.
   Security in case of vulnerabilities.
   Internals for changes that don't affect users.

Added
-----
* Job key ``note`` adds a note in a report appearing after the job header
* New ``wait_for_navigate`` key for jobs with ``use_browser: true`` (i.e. using Pyppeteer) allows to wait for
  navigation to reach a URL starting with the one specified before extracting content. Useful when the URL redirects
  elsewhere before displaying content you're interested in.
* New ``block_elements`` key for jobs with ``use_browser: true`` (i.e. using Pyppeteer) allows to specify
  `resource types
  <https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest/ResourceType>`__ to skip
  requesting (downloading) in order to speed up retrieval of the content.  Only resource types `supported by
  Chromium <https://developer.chrome.com/docs/extensions/reference/webRequest/#type-ResourceType>`__ are allowed.
  Typical list includes ``stylesheet``, ``font``, ``image``, and ``media`` but may break some sites. ⚠ Ignored in
  Python versions < 3.7 and may not work with all Chromium revisions (some hang).

Fixed
-----
* Specifying ``chromium_revision`` had no effect (bug introduced in Version 3.1.0)
* Improved the error message when jobs.yaml has a mistake in the job parameters

Internals
---------
* When running in Python 3.7 or higher, jobs with ``use_browser: true`` (i.e. using Pyppeteer) are a bit more reliable
  as they are now launched using ``asyncio.run()``, and therefore Python takes care of managing the asyncio event loop,
  finalizing asynchronous generators, and closing the threadpool, tasks that previously were handled by custom code
* Additional testing to include Pyppeteer (Python 3.7 or higher) and running jobs that retrieve content from the
  internet
