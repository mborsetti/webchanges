.. **** IMPORTANT ****
   All code here is automatically tested. See tests/docs_hooks_test.py (the code), tests/data/doc_hooks_jobs.yaml
   (the test jobs, with unique URLs) and tests/data/doc_hooks_testdata.yaml (the "before" and "after" data).
   This ensures that all examples work now and in the future.

.. _hooks:

=========================
Hook your own Python code
=========================
Python programmers can hook their own code to expand :program:`webchanges` with custom functionality by writing it into
a ``hooks.py`` file located in the same directory as the job and configuration files. The code will be automatically
loaded at startup.

Smaller code snippets can also be run using the :ref:`execute` filter, for example as used :ref:`here <json_dict>`
for filtering JSON dictionaries.

An example ``hooks.py`` file is below:

.. code-block:: python

   """Example hooks file for webchanges."""

   import re
   from pathlib import Path
   from typing import Any, Dict, Tuple, Optional, Union

   from webchanges.filters import AutoMatchFilter, FilterBase, RegexMatchFilter
   from webchanges.handler import JobState
   from webchanges.jobs import UrlJob
   from webchanges.reporters import HtmlReporter, TextReporter


   class CustomLoginJob(UrlJob):
       """Custom login for my webpage.

       Add `kind: custom_login` to the job to retrieve data using this class instead of the built-in ones.
       """

       __kind__ = 'custom_login'
       __required__ = ('username', 'password')

       def retrieve(self, job_state: JobState, headless: bool = True) -> Tuple[Union[str, bytes], str]:
           """:returns: The data retrieved and the ETag."""
           ...  # custom code here to actually do the login
           return f'Would log in to {self.url} with {self.username} and {self.password}\n', ''


   class CaseFilter(FilterBase):
       """Custom filter for changing case.

       Needs to be selected manually, i.e. add `- case:` (or e.g. `- case: lower`)to the list of filters in the job's
       `filter:` directive.
       """

       __kind__ = 'case'

       __supported_subfilters__ = {
           'upper': 'Upper case (default)',
           'lower': 'Lower case'
       }

       __default_subfilter__ = 'upper'

       @staticmethod
       def filter(data: str, subfilter: Optional[Dict[str, Any]] = None) -> str:

           if not subfilter or subfilter.get('upper'):
               return data.upper()
           elif subfilter.get('lower'):
               return data.lower()
           else:
               raise ValueError(f'Unknown case subfilter {subfilter}')


   class IndentFilter(FilterBase):
       """Custom filter for indenting.

       Needs to be selected manually, i.e. add `- indent:` (or e.g. `- indent: 4`) to the list of filters in the job's
       `filter:` directive.
       """

       __kind__ = 'indent'

       __supported_subfilters__ = {
           'indent': 'Number of spaces to indent (default 8)'
       }

       __default_subfilter__ = 'indent'

       @staticmethod
       def filter(data: str, subfilter: Optional[Dict[str, Any]] = None) -> str:

           indent = int(subfilter.get('indent', 8))

           return '\n'.join((' ' * indent) + line for line in data.splitlines())


   class CustomMatchUrlFilter(AutoMatchFilter):
       """An AutoMatchFilter applies automatically to all jobs that match the MATCH properties set."""

       MATCH = {'url': 'https://example.org/'}

       @staticmethod
       def filter(data: str, subfilter: Optional[Dict[str, Any]] = None) -> str:
           return data.replace('foo', 'bar')


   class CustomRegexMatchUrlFilter(RegexMatchFilter):
       """A RegexMatchFilter applies automatically to all jobs that match the MATCH regex properties set."""

       MATCH = {'url': re.compile(r'https://example.org/.*')}

       @staticmethod
       def filter(data: str, subfilter: Optional[Dict[str, Any]] = None) -> str:
           return data.replace('foo', 'bar')


   class CustomTextFileReporter(TextReporter):
       """Custom reporter that writes the text-only report to a file.

       Needs to enabled in the config.yaml file:
       report:
         custom_file:
           enabled: true
       """

       __kind__ = 'custom_file'

       def submit(self) -> None:
           Path(self.config['filename']).write_text('\n'.join(super().submit()))


   class CustomHtmlFileReporter(HtmlReporter):
       """Custom reporter that writes the HTML report to a file.

       Needs to enabled in the config.yaml file:
       report:
         custom_html:
           enabled: true
       """

       __kind__ = 'custom_html'

       def submit(self) -> None:
           Path(self.config['filename']).write_text('\n'.join(super().submit()))
