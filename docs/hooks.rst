.. **** IMPORTANT ****
   All code here is automatically tested. See tests/docs_hooks_test.py (the code), tests/data/doc_hooks_jobs.yaml
   (the test jobs, with unique URLs) and tests/data/doc_hooks_testdata.yaml (the "before" and "after" data).
   This ensures that all examples work now and in the future.

.. _hooks:

=========================
Hook your own Python code
=========================
Python programmers can hook their own code to expand :program:`webchanges` with custom functionality by writing such
code into a ``hooks.py`` file located in the same directory as the job and configuration files (or as specified in the
command line using the ``--hooks`` argument). The file will be automatically loaded as a module at startup.

An example ``hooks.py`` file to get you started is below.

Smaller code snippets can also be run using the :ref:`execute` filter, for example as used :ref:`here <json_dict>`
for filtering JSON dictionaries.

.. _important_note_for_hooks_file:

.. important:: On Linux and macOS systems, due to security reasons the hooks module will not be imported unless **both**
   the hooks file **and** the directory it is located in are **owned** and **writeable** by **only** the user who is
   running the job (and not by its group or by other users) or by the root user. To set this up:

   .. code-block:: bash

      cd ~/.config/webchanges  # could be different
      sudo chown $USER:$(id -g -n) . hooks.py
      sudo chmod go-w . hooks.py

   * ``sudo`` may or may not be required.
   * Replace ``$USER`` with the username that runs :program:`webchanges` if different than the use you're logged in when
     making the above changes, similarly with ``$(id -g -n)`` for the group.

Example ``hooks.py`` file:

.. code-block:: python

   """Example hooks file for webchanges (for Python >= 3.13)."""

   import re
   import threading
   from pathlib import Path
   from typing import TYPE_CHECKING

   from webchanges.differs import DifferBase
   from webchanges.filters import AutoMatchFilter, FilterBase, RegexMatchFilter
   from webchanges.jobs import UrlJob, UrlJobBase
   from webchanges.reporters import HtmlReporter, TextReporter

   if TYPE_CHECKING:
       from typing import Any, Literal
   
       from webchanges.handler import JobState
       from webchanges.jobs import JobBase
       from webchanges.storage import _Config

   hooks_custom_login_lock = threading.Lock()


   class CustomLoginJob(UrlJob):
       """Custom job that adds filters and differ and runs login for my webpage.

       Adds a standard filter and differ to the job, and executes code to perform login before retrieving data.

       Add ``kind: hooks_custom_login`` to the job to retrieve data using this class instead of the
       built-in ones.
       """

       __kind__ = 'hooks_custom_login'
       __required__ = ('username', 'password')  # These are added to the ones from the super classes.

       # IMPORTANT!
       # We want to put all job modifications within the with_defaults function so that --test-filters etc. work
       def with_defaults(self, config: _Config) -> JobBase:
           """Obtain a Job object that also contains defaults from the configuration.

           :param config: The configuration as a dict.
           :returns: A JobBase object.
           """
           self.filters = ['jsontoyaml']  # applies to all jobs with ``kind: hooks_custom_login``
           self.differ = {'name': 'deepdiff', 'ignore_order': True, 'compact': True}
           return super().with_defaults(config)

       def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[bytes | str, str, str]:
           """Runs job to retrieve the data, and returns data and ETag.

           :param job_state: The JobState object, to keep track of the state of the retrieval.
           :param headless: For browser-based jobs, whether headless mode should be used.
           :returns: The data retrieved, the ETag, and the media type (fka MIME type)
           :raises NotModifiedError: If an HTTP 304 response is received.
           """
           with hooks_custom_login_lock:  # this site doesn't like parallel logins
               ...  # custom code here to actually do the login.
           additional_headers = {'x-special': 'test'}
           self.headers.update(additional_headers)  # self.headers always an httpx.Headers object
           return super().retrieve(job_state)  # uses the existing code to then browse and capture data


   class CustomBrowserJob(UrlJobBase):
       """Custom browser job.

       Add ``kind: hooks_custom_browser`` to the job to retrieve data using this class instead of the
       built-in ones.
       """

       __kind__ = 'hooks_custom_browser'
       __is_browser__ = True  # This is required for execution in the correct parallel processing queue.

       def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[bytes | str, str, str]:
           """Runs job to retrieve the data, and returns data and ETag.

           :param job_state: The JobState object, to keep track of the state of the retrieval.
           :param headless: For browser-based jobs, whether headless mode should be used.
           :returns: The data retrieved, the ETag, and the media type (fka MIME type)
           :raises NotModifiedError: If an HTTP 304 response is received.
           """
           ...  # custom code here to launch browser and capture data.
           return (
               '<Data captured after browsing to self.url>',
               '<The Etag (if any) or empty string>',
               '<The Content-Type (if any) or empty string>',
           )


   class CaseFilter(FilterBase):
       """Custom filter for changing case.

       Needs to be selected manually, i.e. add `- hooks_case:` (or e.g. `- hooks_case: lower`) to the
       list of filters in the job's `filter:` directive. E.g.:

       .. code-block:: yaml

          url: example.com/hooks/len
          filter:
            - hooks_case: lower
       """

       __kind__ = 'hooks_case'

       __supported_subfilters__: dict[str, str] = {
           'upper': 'Upper case (default)',
           'lower': 'Lower case'
       }

       __default_subfilter__ = 'upper'

       @staticmethod
       def filter(
           data: str | bytes, mime_type: str, subfilter: dict[str, Any]
       ) -> tuple[str | bytes, str]:
           """:returns: The filtered data and its media type (fka MIME type)."""

           if not subfilter or subfilter.get('upper'):
               return data.upper(), mime_type
           elif subfilter.get('lower'):
               return data.lower(), mime_type
           else:
               raise ValueError(f'Unknown case subfilter {subfilter}')


   class IndentFilter(FilterBase):
       """Custom filter for indenting.

       Needs to be selected manually, i.e. add ``- hooks_indent:`` (or e.g. ``- hooks_indent: 4``) to
       the list of filters in the job's ``filter:`` directive. E.g.:


       .. code-block:: yaml

          url: example.com/hooks/indent
          filter:
            - hooks_indent: 4
       """

       __kind__ = 'hooks_indent'

       __supported_subfilters__: dict[str, str] = {
           'indent': 'Number of spaces to indent (default 8)'
       }

       __default_subfilter__ = 'indent'

       @staticmethod
       def filter(
           data: str | bytes, mime_type: str, subfilter: dict[str, Any]
       ) -> tuple[str | bytes, str]:
           """:returns: The filtered data and its media type (fka MIME type)."""

           indent = int(subfilter.get('indent', 8))

           return '\n'.join((' ' * indent) + line for line in data.splitlines()), mime_type


   class CustomMatchUrlFilter(AutoMatchFilter):
       """
       An AutoMatchFilter applies automatically to all jobs that exactly match the MATCH properties set.
       """

       MATCH = {'url': 'https://example.org/'}

       @staticmethod
       def filter(
           data: str | bytes, mime_type: str, subfilter: dict[str, Any]
       ) -> tuple[str | bytes, str]:
           """:returns: The filtered data and its media type (fka MIME type)."""
           return data.replace('foo', 'bar'), mime_type


   class CustomRegexMatchUrlFilter(RegexMatchFilter):
       """
       A RegexMatchFilter applies automatically to all jobs that match the MATCH regex properties set.
       """

       MATCH = {'url': re.compile(r'https://example.org/.*')}

       @staticmethod
       def filter(
           data: str | bytes, mime_type: str, subfilter: dict[str, Any]
       ) -> tuple[str | bytes, str]:
           """:returns: The filtered data and its media type (fka MIME type)."""
           return data.replace('foo', 'bar'), mime_type


   class LenDiffer(DifferBase):
       """Custom differ to show difference in length of the data.

       Needs to be selected manually, i.e. add the directive ``differ: hooks_differ`` the job. E.g.:

       .. code-block:: yaml

          url: example.com/hooks/len
          differ: hooks_lendiffer
       """

       __kind__ = 'hooks_lendiffer'

       __no_subdiffer__ = True
       __supported__report_kinds__ = {'html'}

       def differ(
           self,
           subdiffer: dict[str, Any],
           report_kind: Literal['text', 'markdown', 'html'],
           _unfiltered_diff: dict[Literal['text', 'markdown', 'html'], str] | None = None,
           tz: str | None = None,
       ) -> dict[Literal['text', 'markdown', 'html'], str]:
           len_diff = len(self.state.new_data) - len(self.state.old_data)
           diff_text = f'Length of data has changed by {len_diff:+,}'
           return {
               'text': diff_text,
               'markdown': diff_text,
               'html': diff_text,
           }


   class CustomTextFileReporter(TextReporter):
       """Custom reporter that writes the text-only report to a file. Insert the filename in config.py
       as a filename key to the text reporter.

       Needs to enabled in the config.yaml file:

       .. code-block:: yaml

          report:
            hooks_save_text_report:
              enabled: true
       """

       __kind__ = 'hooks_save_text_report'

       def submit(self) -> None:
           Path(self.config['filename']).write_text('\n'.join(super().submit()))


   class CustomHtmlFileReporter(HtmlReporter):
       """Custom reporter that writes the HTML report to a file. Insert the filename in config.py
       as a filename key to the html reporter.

       .. code-block:: yaml

          report:
            hooks_save_html_report:
              enabled: true
       """

       __kind__ = 'hooks_save_html_report'

       def submit(self) -> None:
           Path(self.config['filename']).write_text('\n'.join(super().submit()))


.. versionchanged:: 3.22
   The definitions of the filter method (of FilterBase and its subclasses) and of the retrieve method (of JobBase and
   its subclasses) have been updated to accommodate the capturing and processing of ``mime_type``:

   .. code-block:: python

      def filter(
          data: str | bytes, mime_type: str, subfilter: dict[str, Any]
      ) -> tuple[str | bytes, str]:
      """:returns: The filtered data and its media type (fka MIME type)."""
      ...

      def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[bytes | str, str, str]:
      """:returns: The data retrieved, the ETag, and the data's media type (fka MIME type) (e.g. HTTP Content-Type)."""
      ...
