.. _hooks:

============
Python hooks
============

Python programmers can hook their code with custom functionality by writing it into a ``hooks.py`` file and putting it
into the same directory as the job and configuration files.  The code will be automatically loaded at startup.

An example hooks.py file is below:

.. code-block:: python

   # Example hooks file for webchanges

   import re

   from webchanges import filters
   from webchanges import jobs
   from webchanges import reporters


   #class CustomLoginJob(jobs.UrlJob):
   #    """Custom login for my webpage"""
   #
   #    __kind__ = 'custom-login'
   #    __required__ = ('username', 'password')
   #
   #    def retrieve(self, job_state):
   #        return 'Would log in to {} with {} and {}\n'.format(self.url, self.username, self.password)


   #class CaseFilter(filters.FilterBase):
   #    """Custom filter for changing case, needs to be selected manually"""
   #
   #    __kind__ = 'case'
   #
   #    __no_subfilter__ = True
   #
   #    def filter(self, data, subfilter=None):
   #        # The subfilter is specified using a colon, for example the "case"
   #        # filter here can be specified as "case:upper" and "case:lower"
   #
   #        if subfilter is None:
   #            subfilter = 'upper'
   #
   #        if subfilter == 'upper':
   #            return data.upper()
   #        elif subfilter == 'lower':
   #            return data.lower()
   #        else:
   #            raise ValueError('Unknown case subfilter: %r' % (subfilter,))


   #class IndentFilter(filters.FilterBase):
   #    """Custom filter for indenting, needs to be selected manually"""
   #
   #    __kind__ = 'indent'
   #
   #    __no_subfilter__ = True
   #
   #    def filter(self, data, subfilter=None):
   #        # The subfilter here is a number of characters to indent
   #
   #        if subfilter is None:
   #            indent = 8
   #        else:
   #            indent = int(subfilter)
   #
   #        return '\n'.join((' '*indent) + line for line in data.splitlines())


   class CustomMatchUrlFilter(filters.AutoMatchFilter):
       # The AutoMatchFilter will apply automatically to all filters
       # that have the given properties set
       MATCH = {'url': 'https://example.org/'}

       # An auto-match filter does not have any subfilters
       def filter(self, data):
           return data.replace('foo', 'bar')


   class CustomRegexMatchUrlFilter(filters.RegexMatchFilter):
       # Similar to AutoMatchFilter
       MATCH = {'url': re.compile('https://example.org/.*')}

       # An auto-match filter does not have any subfilters
       def filter(self, data):
           return data.replace('foo', 'bar')


   class CustomTextFileReporter(reporters.TextReporter):
       """Custom reporter that writes the text-only report to a file"""

       __kind__ = 'custom_file'

       def submit(self):
           with open(self.config['filename'], 'w') as fp:
               fp.write('\n'.join(super().submit()))


   class CustomHtmlFileReporter(reporters.HtmlReporter):
       """Custom reporter that writes the HTML report to a file"""

       __kind__ = 'custom_html'

       def submit(self):
           with open(self.config['filename'], 'w') as fp:
               fp.write('\n'.join(super().submit()))
