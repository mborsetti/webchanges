"""Stdout reporter."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

__lazy_modules__ = ['enum', 're']

import logging
import re
import sys
from enum import Enum
from typing import TYPE_CHECKING, Any

from webchanges.reporters._base import TextReporter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)


def _enable_windows_ansi() -> bool:
    """Enables the processing of ANSI escape sequences (colors) by the Windows console attached to stdout.

    Windows 10 and later support ANSI escape sequences natively, but the legacy console host (conhost) only honors
    them once ENABLE_VIRTUAL_TERMINAL_PROCESSING is set on the output handle; Windows Terminal sets it by default.

    :returns: True if the console processes ANSI escape sequences (or the platform is not Windows), False otherwise.
    """
    if sys.platform != 'win32':
        return True

    import ctypes

    std_output_handle = -11  # STD_OUTPUT_HANDLE
    enable_virtual_terminal_processing = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(std_output_handle)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            logger.debug('GetConsoleMode failed (error %s); stdout colors disabled', ctypes.get_last_error())
            return False
        if mode.value & enable_virtual_terminal_processing:
            return True
        if not kernel32.SetConsoleMode(handle, mode.value | enable_virtual_terminal_processing):
            logger.debug('SetConsoleMode failed (error %s); stdout colors disabled', ctypes.get_last_error())
            return False
        logger.debug('Enabled ANSI escape sequence processing in the Windows console')
        return True
    except (AttributeError, OSError) as e:
        logger.debug('Unable to enable ANSI escape sequence processing in the Windows console: %s', e)
        return False


class StdoutReporter(TextReporter):
    """Print summary on stdout (the console)."""

    __kind__ = 'stdout'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._has_color = bool(
            sys.stdout.isatty() and self.config['color'] and _enable_windows_ansi()  # ty:ignore[invalid-key]
        )
        self._color_code = '3' if self.config['color'] == 'normal' else '9'  # ty:ignore[invalid-key]

    def _incolor(self, color_id: int, s: str) -> str:
        if self._has_color:
            return f'\033[{self._color_code}{color_id}m{s}\033[0m'
        return s

    def _red(self, s: str) -> str:
        return self._incolor(1, s)

    def _green(self, s: str) -> str:
        return self._incolor(2, s)

    def _blue(self, s: str) -> str:
        return self._incolor(4, s)

    def submit(self, **kwargs: Any) -> None:  # ty:ignore[invalid-method-override]
        cfg = self.get_base_config(self.report)
        line_length = cfg['line_length']

        separators = (line_length * '=', line_length * '-', '--') if line_length else ()
        body = '\n'.join(super().submit())

        if any(
            differ.get('command', '').startswith('wdiff')
            for differ in (job_state.job.differ for job_state in self.job_states if job_state.job.differ)
        ):
            # wdiff colorization
            body = re.sub(r'\{\+.*?\+}', lambda x: self._green(str(x.group(0))), body, flags=re.DOTALL)
            body = re.sub(r'\[-.*?-]', lambda x: self._red(str(x.group(0))), body, flags=re.DOTALL)
            separators = (*separators, '-' * 36)

        class LineType(Enum):
            """Defines the differ line types"""

            SEPARATOR = 1
            ADDITION = 2
            DELETION = 3
            STATUS = 4
            OTHER = 5

        def get_line_type(line: str, separators: Iterable[str]) -> LineType:
            """Classifies each line"""
            if line in separators:
                return LineType.SEPARATOR
            if line.startswith('+'):
                return LineType.ADDITION
            if line.startswith('-'):
                return LineType.DELETION
            if any(line.startswith(prefix) for prefix in ('NEW: ', 'CHANGED: ', 'UNCHANGED: ', 'ERROR: ')):
                return LineType.STATUS
            return LineType.OTHER

        def print_status_line(line: str, print_color: Callable, red_color: Callable, blue_color: Callable) -> None:
            """Prints a status line"""
            first, second = line.split(' ', 1)
            if line.startswith('ERROR: '):
                print_color(first, red_color(second))
            else:
                print_color(first, blue_color(second))

        def process_lines(
            body: str,
            separators: Iterable[str],
            print_color: Callable,
            green_color: Callable,
            red_color: Callable,
            blue_color: Callable,
        ) -> None:
            """Processes the lines"""
            for line in body.splitlines():
                line_type = get_line_type(line, separators)

                match line_type:
                    case LineType.SEPARATOR:
                        print_color(line)
                    case LineType.ADDITION:
                        print_color(green_color(line))
                    case LineType.DELETION:
                        print_color(red_color(line))
                    case LineType.STATUS:
                        print_status_line(line, print_color, red_color, blue_color)
                    case LineType.OTHER:
                        print_color(line)

        process_lines(body, separators, print, self._green, self._red, self._blue)
