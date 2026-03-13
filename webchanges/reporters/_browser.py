"""Browser reporter."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import time
from pathlib import Path

from webchanges.reporters._base import HtmlReporter

logger = logging.getLogger(__name__)


class BrowserReporter(HtmlReporter):
    """Display HTML summary using the default web browser."""

    __kind__ = 'browser'

    def submit(self) -> None:  # type: ignore[override]
        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        if not filtered_job_states:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        html_reporter = HtmlReporter(
            self.report, self.config, self.job_states, self.duration, self.jobs_files, self.differ_defaults
        )
        body_html = '\n'.join(html_reporter.submit())

        # recheck after running as diff_filters can modify job_states.verb
        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        if not filtered_job_states:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        import tempfile
        import webbrowser

        # Create a temporary file using a 'with' statement
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(body_html)
            temp_path = Path(f.name)

        # Open the file in the browser after it has been written and closed
        webbrowser.open(temp_path.as_uri())  # .as_uri() is more robust for local files
        time.sleep(2)

        # Clean up the file
        temp_path.unlink()
