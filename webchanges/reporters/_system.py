"""System command reporters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from typing import TYPE_CHECKING

from webchanges import __project_name__
from webchanges.reporters._base import TextReporter

if TYPE_CHECKING:
    from webchanges.storage import _ConfigReportRunCommand

import json

logger = logging.getLogger(__name__)


class RunCommandReporter(TextReporter):
    """Run a command."""

    __kind__ = 'run_command'

    config: _ConfigReportRunCommand

    def submit(self) -> None:  # type: ignore[override]
        if not self.config['command']:
            raise ValueError('Reporter "run_command" needs a command')

        text = '\n'.join(super().submit())

        if not text:
            logger.info(f'Reporter {self.__kind__} has nothing to report; execution aborted')
            return

        filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))

        # Work on a copy to not modify the outside environment
        env = dict(os.environ)
        env.update({f'{__project_name__.upper()}_REPORT_CONFIG_JSON': json.dumps(self.report.config)})
        env.update({f'{__project_name__.upper()}_REPORT_REPORTED_JOBS_JSON': json.dumps(self.report.config)})

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
            logger.error(f"The '{self.__kind__}' filter with command {command} returned error:\n{e.stderr}")
            raise e
        except FileNotFoundError as e:
            logger.error(f"The '{self.__kind__}' filter with command {command} returned error:\n{e}")
            raise FileNotFoundError(e, f'with command {command}')  # noqa: B904
        print(result.stdout, end='')
