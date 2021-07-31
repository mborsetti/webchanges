.. **** IMPORTANT ****
   All code here is automatically tested. See tests/docs_hooks_test.py (the code), tests/data/doc_hooks_jobs.yaml
   (the test jobs, with unique URLs) and tests/data/doc_hooks_testdata.yaml (the "before" and "after" data).
   This ensures that all examples work now and in the future.

.. _hooks:

=================
Python code hook
=================
Python programmers can hook their own code to expand :program:`webchanges` with custom functionality by writing it into
a ``hooks.py`` file and placing it into the same directory as the job and configuration files. The code will be
automatically loaded at startup.

Smaller code snippets can also be run using the :ref:`execute` filter, for example as used :ref:`here <json_dict>`
for filtering JSON dictionaries.

An example ``hooks.py`` file is below:

.. code-block:: python

   """Example hooks file for webchanges."""

   from pathlib import Path
   import re
   from typing import Any, Dict, Optional

   from webchanges.filters import AutoMatchFilter, FilterBase, RegexMatchFilter
   from webchanges.handler import JobState
   from webchanges.jobs import UrlJob
   from webchanges.reporters import HtmlReporter, TextReporter


   class CustomLoginJob(UrlJob):
       """Custom login for my webpage."""

       __kind__ = 'custom-login'
       __required__ = ('username', 'password')

       def retrieve(self, job_state: JobState) -> str:
           ...  # custom code here to actually do the login
           return f'Would log in to {self.url} with {self.username} and {self.password}\n'


   class CaseFilter(FilterBase):
       """Custom filter for changing case, needs to be selected manually."""

       __kind__ = 'case'

       __supported_subfilters__ = {
           'upper': 'Upper case (default)',
           'lower': 'Lower case'
       }

       __default_subfilter__ = 'upper'

       @staticmethod
       def filter(data: str, subfilter: Optional[Dict[str, Any]]) -> str:

           if not subfilter or subfilter.get('upper'):
               return data.upper()
           elif subfilter.get('lower'):
               return data.lower()
           else:
               raise ValueError(f'Unknown case subfilter {subfilter}')


   class IndentFilter(FilterBase):
       """Custom filter for indenting, needs to be selected manually."""

       __kind__ = 'indent'

       __supported_subfilters__ = {
           'indent': 'Number of spaces to indent (default 8)'
       }

       __default_subfilter__ = 'indent'

       @staticmethod
       def filter(data: str, subfilter: Optional[Dict[str, Any]]) -> str:

           indent = int(subfilter.get('indent', 8))

           return '\n'.join((' ' * indent) + line for line in data.splitlines())


   class CustomMatchUrlFilter(AutoMatchFilter):
       """The AutoMatchFilter will apply automatically to all jobs that match the given properties
       set."""

       MATCH = {'url': 'https://example.org/'}

       @staticmethod
       def filter(data: str, subfilter: Optional[Dict[str, Any]]) -> str:
           return data.replace('foo', 'bar')


   class CustomRegexMatchUrlFilter(RegexMatchFilter):
       """The RegexMatchFilter will apply automatically to  all jobs that match the given properties
       set."""

       MATCH = {'url': re.compile(r'https://example.org/.*')}

       @staticmethod
       def filter(data: str, subfilter: Optional[Dict[str, Any]]) -> str:
           return data.replace('foo', 'bar')


   class CustomTextFileReporter(TextReporter):
       """Custom reporter that writes the text-only report to a file."""

       __kind__ = 'custom_file'

       def submit(self) -> None:
           Path(self.config['filename']).write_text('\n'.join(super().submit()))


   class CustomHtmlFileReporter(HtmlReporter):
       """Custom reporter that writes the HTML report to a file."""

       __kind__ = 'custom_html'

       def submit(self) -> None:
           Path(self.config['filename']).write_text('\n'.join(super().submit()))
