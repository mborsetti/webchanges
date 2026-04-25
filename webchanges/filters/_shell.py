"""Shell execution filters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys
from typing import Any

from webchanges import __project_name__
from webchanges.filters._base import FilterBase

logger = logging.getLogger(__name__)


def _pipe_filter(f_cls: FilterBase, data: str | bytes, subfilter: dict[str, Any]) -> str:
    if 'command' not in subfilter:
        raise ValueError(f"The '{f_cls.__kind__}' filter needs a command. ({f_cls.job.get_indexed_location()})")

    # Work on a copy of the environment as not to modify the outside environment
    env = os.environ.copy()
    env.update(
        {
            f'{__project_name__.upper()}_JOB_JSON': json.dumps(f_cls.job.to_dict()),
            f'{__project_name__.upper()}_JOB_NAME': f_cls.job.pretty_name(),
            f'{__project_name__.upper()}_JOB_LOCATION': f_cls.job.get_location(),
            f'{__project_name__.upper()}_JOB_INDEX_NUMBER': str(f_cls.job.index_number),
            'URLWATCH_JOB_NAME': f_cls.job.pretty_name(),  # urlwatch 2 compatibility
            'URLWATCH_JOB_LOCATION': f_cls.job.get_location(),  # urlwatch 2 compatibility
        }
    )

    if subfilter.get('escape_characters') and sys.platform == 'win32':
        escaped_command = re.sub(r'([()!^"<>&|])', r'^\1', subfilter['command']).replace('%', '%%')
        # escaped_command = _windows_escape_cmd(subfilter['command'])
    else:
        escaped_command = subfilter['command']

    if f_cls.__kind__ == 'execute':
        command = shlex.split(escaped_command)
        shell = False
    else:  # 'shellpipe'
        command = escaped_command
        shell = True

    try:
        return subprocess.run(  # noqa: S603 Check for untrusted input
            command,
            input=data,
            capture_output=True,
            shell=shell,
            check=True,
            text=True,
            env=env,
        ).stdout
    except subprocess.CalledProcessError as e:
        logger.error(
            f"The '{f_cls.__kind__}' filter returned error code {e.returncode} ({f_cls.job.get_indexed_location()}):\n"
            f'{e.stderr}\n---\n{e.stdout}'
        )
        raise e
    except FileNotFoundError as e:
        logger.error(f"The '{f_cls.__kind__}' filter returned error ({f_cls.job.get_indexed_location()}):\n{e}")
        raise FileNotFoundError(e, f'with command {command}') from None


class ExecuteFilter(FilterBase):
    """Filter using a command."""

    __kind__ = 'execute'

    __supported_subfilters__: dict[str, str] = {
        'command': 'Command to execute for filtering (required)',
        'escape_characters': 'Whether to escape characters when running in Windows',
    }

    __default_subfilter__ = 'command'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not mime_type.startswith('text'):
            mime_type = 'text/plain'
        return _pipe_filter(self, data, subfilter), mime_type


class ShellPipeFilter(FilterBase):
    """Filter using a shell command."""

    __kind__ = 'shellpipe'

    __supported_subfilters__: dict[str, str] = {
        'command': 'Shell command to execute for filtering (required)',
        'escape_characters': 'Whether to escape characters when running in Windows',
    }

    __default_subfilter__ = 'command'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not mime_type.startswith('text'):
            mime_type = 'text/plain'
        return _pipe_filter(self, data, subfilter), mime_type
