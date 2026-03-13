"""Filter defined alongside reporters (BetweenLinesFilter)."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import re
from typing import Any, Generator, Sequence

from webchanges.filters._base import FilterBase


def get_lines_between(
    lines: Sequence[str],
    start_pattern: str | None = None,
    end_pattern: str | None = None,
) -> Generator[str, None, None]:
    """Yield lines between start and end patterns."""
    started = False
    for line in lines:
        if not started:
            if start_pattern and re.search(start_pattern, line):
                started = True
            continue
        if end_pattern and re.search(end_pattern, line):
            break

        yield line


class BetweenLinesFilter(FilterBase):
    """Filter to extract lines between two patterns."""

    __kind__ = 'between'

    __supported_subfilters__ = {
        'start': 'Pattern to match the start line.',
        'end': 'Pattern to match the end line.',
    }

    __default_subfilter__ = 'indent'

    def filter(
        self,
        data: str | bytes,
        mime_type: str,
        subfilter: dict[str, Any],
    ) -> tuple[str | bytes, str]:
        """Filter lines between start and end patterns."""
        start_pattern = subfilter.get('start')
        end_pattern = subfilter.get('end')

        lines = str(data).splitlines(keepends=True)
        filtered_lines = get_lines_between(lines, start_pattern, end_pattern)

        return (
            '\n'.join(filtered_lines),
            mime_type,
        )
