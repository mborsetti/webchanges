⚠ Breaking Changes
```````````````````
* Newly added ``utf-8`` sub-directive of ``smtp`` ``email`` reporter is now called ``utf_8`` (with an underscore) due to
  Python TypedDict class limitation, but will have backward-compatibility for at least 12 months.

Changed
```````
* ``telegram`` reporter will now look for the environment variable ``TELEGRAM_BOT_TOKEN`` if no token is defined in the
  configuration (i.e. ``bot_token`` is missing or has a ``null`` value).

Fixed
`````
* Regression: Rejecting ``ignore_cached`` job directive  (reported by `Marcos Alano <https://github.com/mhalano>`__
  in issue `#153 <https://github.com/mborsetti/webchanges/issues/153>`__).
* Rejecting ``http_credentials`` job directive in certain circumstances with URL jobs with ``browser: true``.

Internals impacting ``hooks.py``
````````````````````````````````
* Broken up huge files into smaller, more manageable ones. If you are importing from webchanges, the location of
  certain classes may have changed.

Internals
`````````
* Increased amount of free memory required before running URL jobs with ``use_browser: true`` (i.e. Playwright)
  in parallel to 800 MiB.
