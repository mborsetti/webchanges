"""ShellJob — run a shell command and capture its output."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from webchanges.filters import FilterBase
from webchanges.jobs._base import Job

if TYPE_CHECKING:
    from webchanges.handler import JobState

logger = logging.getLogger(__name__)


class ShellJob(Job):
    """Run a shell command and get its standard output."""

    __kind__ = 'command'

    __required__: tuple[str, ...] = ('command',)
    __optional__: tuple[str, ...] = (
        'stderr',  # ignored; here for backwards compatibility
    )

    def get_location(self) -> str:
        """Get the 'location' of the job, i.e. the command.

        :returns: The command of the job.
        """
        return self.user_visible_url or self.command

    def set_base_location(self, location: str) -> None:
        """Sets the job's location (command or url) to location.  Used for changing location (uuid)."""
        self.command = location
        self.guid = self.get_guid()

    def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data, ETag (which is blank) and mime_type (also blank).

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved and the ETag and mime_type.
        :raises subprocess.CalledProcessError: Subclass of SubprocessError, raised when a process returns a non-zero
           exit status.
        :raises subprocess.TimeoutExpired: Subclass of SubprocessError, raised when a timeout expires while waiting for
           a child process.
        """
        logger.info(f'Job {self.index_number}: Running shell command: {self.command}')
        needs_bytes = FilterBase.filter_chain_needs_bytes(self.filters)

        # deprecations
        if self.stderr:
            raise ValueError(f"Job {job_state.job.index_number}: Directive 'stderr' is deprecated and does nothing.")

        try:
            response = subprocess.run(  # noqa: S602 `shell=True`, security issue
                self.command,
                capture_output=True,
                shell=True,
                check=True,
                text=(not needs_bytes),
            )
        except subprocess.CalledProcessError as e:
            logger.info(f'Job {self.index_number}: Command: {e.cmd} ')
            logger.info(f'Job {self.index_number}: Failed with returncode {e.returncode}')
            logger.info(f'Job {self.index_number}: stderr : {e.stderr}')
            logger.info(f'Job {self.index_number}: stdout : {e.stdout}')
            raise
        return (response.stdout, '', 'application/octet-stream' if needs_bytes else 'text/plain')

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        if isinstance(exception, subprocess.CalledProcessError):
            # Instead of a full traceback, just show the HTTP error
            return (
                f'Error: Exit status {exception.returncode} returned from subprocess:\n'
                f'{(exception.stderr or exception.stdout).strip()}'
            )
        if isinstance(exception, FileNotFoundError):
            return f'Error returned by OS: {str(exception).strip()}'
        return tb
