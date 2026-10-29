"""System command reporters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

__lazy_modules__ = ['json', 'shlex', 'subprocess', 'warnings']

import logging
import os
import shlex
import subprocess
import warnings
from typing import TYPE_CHECKING, Any

from webchanges import __project_name__
from webchanges.reporters._base import TextReporter
from webchanges.util import SettingError

if TYPE_CHECKING:
    from webchanges.handler import JobState
    from webchanges.storage import _ConfigReportRunCommand, _ConfigReportShell

import json

logger = logging.getLogger(__name__)


class RunCommandReporter(TextReporter):
    """Run a command."""

    __kind__ = 'run_command'

    config: _ConfigReportRunCommand

    def submit(self) -> None:  # ty:ignore[invalid-method-override]
        if not self.config['command']:
            raise SettingError('Reporter "run_command" needs a command')

        text = '\n'.join(super().submit())

        if not text:
            logger.info('Reporter %s has nothing to report; execution aborted', self.__kind__)
            return

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        env = self.environment(filtered_job_states)

        subject_args = {
            'text': text,
            'count': len(filtered_job_states),
            'jobs': ', '.join(job_state.job.pretty_name() for job_state in filtered_job_states),
        }
        command = shlex.split(self.config['command'].format(**subject_args))

        try:
            result = subprocess.run(  # noqa: S603 subprocess call - check for execution of untrusted input.
                command,
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            logger.error("The '%s' filter with command %s returned error:\n%s", self.__kind__, command, e.stderr)
            raise e
        except FileNotFoundError as e:
            logger.error("The '%s' filter with command %s returned error:\n%s", self.__kind__, command, e)
            raise FileNotFoundError(e, f'with command {command}')  # noqa: B904
        print(result.stdout, end='')

    def environment(self, filtered_job_states: list[JobState]) -> dict[str, str]:
        """The environment the command runs in.

        A copy of the current one (so that the outside one is not modified) with the report's configuration and the
        directives of the jobs reported on added in JSON format.

        :param filtered_job_states: The job states reported on.
        :returns: The environment variables.
        """
        jobs_json = json.dumps([job_state.job.to_dict() for job_state in filtered_job_states], default=str)
        env = dict(os.environ)
        env[f'{__project_name__.upper()}_REPORT_CONFIG_JSON'] = json.dumps(self.report.config)
        env[f'{__project_name__.upper()}_CHANGED_JOBS_JSON'] = jobs_json
        # Undocumented name, which until 3.39 held the report's configuration instead of the jobs; kept as is.
        env[f'{__project_name__.upper()}_REPORT_REPORTED_JOBS_JSON'] = jobs_json
        return env


class ShellReporter(RunCommandReporter):
    """Pipe the text report to a command (urlwatch's 'shell' reporter); deprecated, use run_command instead."""

    __kind__ = 'shell'

    config: _ConfigReportShell  # ty:ignore[invalid-attribute-override]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        warnings.warn("'shell' reporter is deprecated; use 'run_command' instead", DeprecationWarning, stacklevel=1)
        super().__init__(*args, **kwargs)

    def submit(self) -> None:
        """Run the command with the report on its standard input, as urlwatch does.

        The command (a string or a list of arguments) is run without a shell and with no substitutions, its output is
        logged unless ignored, and a non-zero exit code is logged as an error.
        """
        command = self.config['command']
        if not command:
            raise SettingError('Reporter "shell" needs a command')

        text = '\n'.join(TextReporter.submit(self))
        if not text:
            logger.info('Reporter %s has nothing to report; execution aborted', self.__kind__)
            return

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))
        logger.debug('Reporter %s: running %s', self.__kind__, command)
        try:
            result = subprocess.run(  # noqa: S603 subprocess call - check for execution of untrusted input.
                command,
                input=f'{text}\n'.encode(),
                capture_output=True,
                check=False,
                env=self.environment(filtered_job_states),
            )
        except FileNotFoundError as e:
            logger.error("The '%s' reporter with command %s returned error:\n%s", self.__kind__, command, e)
            raise FileNotFoundError(e, f'with command {command}')  # noqa: B904
        if result.stdout and not self.config['ignore_stdout']:
            logger.info('Standard output from reporter %s: %s', self.__kind__, result.stdout.decode(errors='replace'))
        if result.stderr and not self.config['ignore_stderr']:
            logger.warning(
                'Standard error output from reporter %s: %s', self.__kind__, result.stderr.decode(errors='replace')
            )
        if result.returncode:
            logger.error('Reporter %s command %s exited with %d', self.__kind__, command, result.returncode)
