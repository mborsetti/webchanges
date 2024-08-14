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
   running the job (and not by its group or by other users). To set this up:

   .. code-block:: bash

      cd ~/.config/webchanges  # could be different
      sudo chown $USER:$(id -g -n) . hooks.py
      sudo chmod go-w . hooks.py

   * ``sudo`` may or may not be required.
   * Replace ``$USER`` with the username that runs :program:`webchanges` if different than the use you're logged in when
     making the above changes, similarly with ``$(id -g -n)`` for the group.

Example ``hooks.py`` file:

.. code-block:: python

   """Example hooks file for webchanges (for Python >= 3.12)."""

   import re
   from pathlib import Path
   from typing import Any, Literal, Union

   from webchanges.differs import DifferBase
   from webchanges.filters import AutoMatchFilter, FilterBase, RegexMatchFilter
   from webchanges.handler import JobState
   from webchanges.jobs import UrlJob, UrlJobBase
   from webchanges.reporters import HtmlReporter, TextReporter


   class CustomLoginJob(UrlJob):
       """Custom login for my webpage.

       Add ``kind: hooks_custom_login`` to the job to retrieve data using this class instead of the
       built-in ones.
       """

       __kind__ = 'hooks_custom_login'
       __required__ = ('username', 'password')  # These are added to the ones from the super classes.

       def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[bytes | str, str, str]:
           """:returns: The data retrieved, the ETag, and the mime_type (e.g. HTTP Content-Type)."""
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
           """
           :returns: The data retrieved, the ETag, and the data's MIME type (e.g. HTTP Content-Type).
           """

           ...  # custom code here to launch browser and capture data.
           return (
               f'Data captured after browsing to {self.url}\n',
               'The Etag (if any) or empty string',
               'The Content-Type (if any) or empty string',
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

       __supported_subfilters__ = {
           'upper': 'Upper case (default)',
           'lower': 'Lower case'
       }

       __default_subfilter__ = 'upper'

       @staticmethod
       def filter(
           data: Union[str, bytes], mime_type: str, subfilter: dict[str, Any]
       ) -> tuple[Union[str, bytes], str]:
           """:returns: The filtered data and its MIME type."""

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

       __supported_subfilters__ = {
           'indent': 'Number of spaces to indent (default 8)'
       }

       __default_subfilter__ = 'indent'

       @staticmethod
       def filter(
           data: Union[str, bytes], mime_type: str, subfilter: dict[str, Any]
       ) -> tuple[Union[str, bytes], str]:
           """:returns: The filtered data and its MIME type."""

           indent = int(subfilter.get('indent', 8))

           return '\n'.join((' ' * indent) + line for line in data.splitlines()), mime_type


   class CustomMatchUrlFilter(AutoMatchFilter):
       """
       An AutoMatchFilter applies automatically to all jobs that exactly match the MATCH properties set.
       """

       MATCH = {'url': 'https://example.org/'}

       @staticmethod
       def filter(
           data: Union[str, bytes], mime_type: str, subfilter: dict[str, Any]
       ) -> tuple[Union[str, bytes], str]:
           """:returns: The filtered data and its MIME type."""
           return data.replace('foo', 'bar'), mime_type


   class CustomRegexMatchUrlFilter(RegexMatchFilter):
       """
       A RegexMatchFilter applies automatically to all jobs that match the MATCH regex properties set.
       """

       MATCH = {'url': re.compile(r'https://example.org/.*')}

       @staticmethod
       def filter(
           data: Union[str, bytes], mime_type: str, subfilter: dict[str, Any]
       ) -> tuple[Union[str, bytes], str]:
           """:returns: The filtered data and its MIME type."""
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
          data: Union[str, bytes], mime_type: str, subfilter: dict[str, Any]
      ) -> tuple[Union[str, bytes], str]:
      """:returns: The filtered data and its MIME type."""
      ...

      def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[bytes | str, str, str]:
      """:returns: The data retrieved, the ETag, and the data's MIME type (e.g. HTTP Content-Type)."""
      ...
