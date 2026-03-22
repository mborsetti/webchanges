"""Text manipulation filters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import re
import warnings
from typing import Any, Iterator

from webchanges.filters._base import FilterBase

logger = logging.getLogger(__name__)


class KeepLinesContainingFilter(FilterBase):
    """Filter only lines matching a regular expression."""

    __kind__ = 'keep_lines_containing'

    __supported_subfilters__: dict[str, str] = {
        'text': 'Lines matching this text are kept (default)',
        're': 'Lines matching this expression are kept',
    }

    __default_subfilter__ = 'text'

    def filter(
        self: KeepLinesContainingFilter | GrepFilter,
        data: str | bytes,
        mime_type: str,
        subfilter: dict[str, Any],
    ) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'text' in subfilter:
            if isinstance(subfilter['text'], str):
                return (
                    ''.join(line for line in data.splitlines(keepends=True) if subfilter['text'] in line).rstrip(),
                    mime_type,
                )
            raise TypeError(
                f"The '{self.__kind__}' filter requires a string but you provided a "
                f'{type(subfilter["text"]).__name__}. ({self.job.get_indexed_location()})'
            )
        if 're' in subfilter:
            if isinstance(subfilter['re'], str):
                try:
                    return (
                        ''.join(
                            line for line in data.splitlines(keepends=True) if re.search(subfilter['re'], line)
                        ).rstrip(),
                        mime_type,
                    )
                except re.error as e:  # FIXIT: Python version 3.13+ change to re.PatternError
                    e.args = (f'{e.args[0]} (pattern: "{subfilter["pattern"]}")', *e.args[1:])
                    raise
            raise TypeError(
                f"The '{self.__kind__}' filter requires a string but you provided a "
                f'{type(subfilter["re"]).__name__}. ({self.job.get_indexed_location()})'
            )
        raise ValueError(
            f"The '{self.__kind__}' filter requires a 'text' or 're' sub-directive. ({self.job.get_indexed_location()})"
        )


class GrepFilter(FilterBase):
    """Deprecated; use ``keep_lines_containing`` instead."""

    __kind__ = 'grep'

    __supported_subfilters__: dict[str, str] = {
        're': 'Lines matching this expression are kept (required)',
    }

    __default_subfilter__ = 're'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        warnings.warn(
            f"The 'grep' filter is deprecated; replace with 'keep_lines_containing' + 're' subfilter"
            f' ({self.job.get_indexed_location()})',
            DeprecationWarning,
            stacklevel=1,
        )
        return KeepLinesContainingFilter.filter(self, data, mime_type, subfilter)


class DeleteLinesContainingFilter(FilterBase):
    """Remove lines matching a regular expression."""

    __kind__ = 'delete_lines_containing'

    __supported_subfilters__: dict[str, str] = {
        'text': 'Lines matching this text are deleted (default)',
        're': 'Lines matching this expression deleted kept',
    }

    __default_subfilter__ = 'text'

    def filter(
        self: DeleteLinesContainingFilter | GrepIFilter,
        data: str | bytes,
        mime_type: str,
        subfilter: dict[str, Any],
    ) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'text' in subfilter:
            if isinstance(subfilter['text'], str):
                return (
                    ''.join(line for line in data.splitlines(keepends=True) if subfilter['text'] not in line).rstrip(),
                    mime_type,
                )
            raise TypeError(
                f"The '{self.__kind__}' filter requires a string but you provided a "
                f'{type(subfilter["text"]).__name__}. ({self.job.get_indexed_location()})'
            )
        if 're' in subfilter:
            if isinstance(subfilter['re'], str):
                try:
                    return (
                        ''.join(
                            line for line in data.splitlines(keepends=True) if re.search(subfilter['re'], line) is None
                        ).rstrip(),
                        mime_type,
                    )
                except re.error as e:  # FIXIT: Python version 3.13+ change to re.PatternError
                    e.args = (f'{e.args[0]} (pattern: "{subfilter["pattern"]}")', *e.args[1:])
                    raise
            raise TypeError(
                f"The '{self.__kind__}' filter requires a string but you provided a "
                f'{type(subfilter["re"]).__name__}. ({self.job.get_indexed_location()})'
            )
        raise ValueError(
            f"The '{self.__kind__}' filter requires a 'text' or 're' sub-directive. ({self.job.get_indexed_location()})"
        )


class GrepIFilter(FilterBase):
    """Deprecated; use ``delete_lines_containing`` instead."""

    __kind__ = 'grepi'

    __supported_subfilters__: dict[str, str] = {
        're': 'Lines matching this expression are removed (required)',
    }

    __default_subfilter__ = 're'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        warnings.warn(
            f"The 'grepi' filter is deprecated; replace with 'delete_lines_containing' + 're' subfilter"
            f' ({self.job.get_indexed_location()})',
            DeprecationWarning,
            stacklevel=1,
        )
        return DeleteLinesContainingFilter.filter(self, data, mime_type, subfilter)


class StripFilter(FilterBase):
    """Strip leading and trailing whitespace."""

    __kind__ = 'strip'

    __supported_subfilters__: dict[str, str] = {
        'splitlines': 'Apply the filter on each line of text (default: false, apply to the entire data)',
        'chars': 'String specifying the set of characters to be removed. If omitted, defaults to removing whitespace',
        'side': "One-sided removal: either 'left' (leading characters) or 'right' (trailing characters)",
    }

    __default_subfilter__ = 'chars'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if subfilter.get('splitlines'):
            lines = data.splitlines()

            if 'side' in subfilter:
                if subfilter['side'] == 'right':
                    return '\n'.join([line.rstrip(subfilter.get('chars')) for line in lines]), mime_type
                if subfilter['side'] == 'left':
                    return '\n'.join([line.lstrip(subfilter.get('chars')) for line in lines]), mime_type

                raise ValueError(
                    f"The 'strip' filter's 'side' sub-directive can only be 'right' or 'left'. "
                    f'({self.job.get_indexed_location()})'
                )

            return '\n'.join([line.strip(subfilter.get('chars')) for line in lines]), mime_type

        if 'side' in subfilter:
            if subfilter['side'] == 'right':
                return data.rstrip(subfilter.get('chars')), mime_type
            if subfilter['side'] == 'left':
                return data.lstrip(subfilter.get('chars')), mime_type

            raise ValueError(
                f"The 'strip' filter's 'side' sub-directive can only be 'right' or 'left'. "
                f'({self.job.get_indexed_location()})'
            )

        return data.strip(subfilter.get('chars')), mime_type


class StripLinesFilter(FilterBase):
    """Deprecated; use ``strip`` with subfilter ``splitlines`` instead."""

    __kind__ = 'striplines'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        warnings.warn(
            f"The 'strip_each_line' filter is deprecated; replace with 'strip' and sub-directive 'splitlines: "
            f"true' ({self.job.get_indexed_location()})",
            DeprecationWarning,
            stacklevel=1,
        )
        if not isinstance(data, str):
            raise ValueError
        return '\n'.join([line.strip() for line in data.splitlines()]), mime_type


class ReSubFilter(FilterBase):
    """Replace text with regular expressions using Python's re.sub."""

    __kind__ = 're.sub'

    __supported_subfilters__: dict[str, str] = {
        'pattern': 'Regular expression to search for (required)',
        'repl': 'Replacement string (default: empty string)',
    }

    __default_subfilter__ = 'pattern'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if 'pattern' not in subfilter:
            raise ValueError(f"The '{self.__kind__}' filter needs a pattern. ({self.job.get_indexed_location()})")

        # Default: Replace with empty string if no "repl" value is set
        try:
            return re.sub(subfilter['pattern'], subfilter.get('repl', ''), data), mime_type
        except re.error as e:  # FIXIT: Python version 3.13+ change to re.PatternError
            e.args = (f'{e.args[0]} (pattern: "{subfilter["pattern"]}")', *e.args[1:])
            raise


class RegexFindall(FilterBase):
    """Extract text using regular expressions using Python's re.findall"""

    __kind__ = 're.findall'

    __supported_subfilters__: dict[str, str] = {
        'pattern': 'Regular expression to search for (required)',
        'repl': "Replacement string applied iteratively to each match (default: '\\g<0>', or extract all matches)",
    }

    __default_subfilter__ = 'pattern'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        if 'pattern' not in subfilter:
            raise ValueError(f"The '{self.__kind__}' filter needs a pattern. ({self.job.get_indexed_location()})")

        # Default: Replace with full match if no "repl" value is set
        try:
            return (
                '\n'.join(
                    [match.expand(subfilter.get('repl', r'\g<0>')) for match in re.finditer(subfilter['pattern'], data)]
                ),
                mime_type,
            )
        except re.error as e:  # FIXIT: Python version 3.13+ change to re.PatternError
            e.args = (f'{e.args[0]} (pattern: "{subfilter["pattern"]}")', *e.args[1:])
            raise


class SortFilter(FilterBase):
    """Sort input items."""

    __kind__ = 'sort'

    __supported_subfilters__: dict[str, str] = {
        'reverse': 'Set to true to reverse sorting order',
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Filter (process) the data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        if not isinstance(data, str):
            raise ValueError
        reverse = isinstance(subfilter, dict) and subfilter.get('reverse', False) is True
        separator = subfilter.get('separator', '\n')
        return separator.join(sorted(data.split(separator), key=str.casefold, reverse=reverse)), mime_type


class RemoveRepeatedFilter(FilterBase):
    """Remove repeated lines (uniq)."""

    __kind__ = 'remove_repeated'

    __supported_subfilters__: dict[str, str] = {
        'separator': 'Item separator (default: newline)',
        'ignore_case': 'Ignore differences in case when comparing',
        'adjacent': 'Remove only adjacent lines or items (default: true)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        separator = subfilter.get('separator', '\n')
        ignore_case = subfilter.get('ignore_case', False)
        consecutive = subfilter.get('adjacent', True)
        data_lines = data.split(separator)
        uniq_lines = [data_lines[0]]
        if not ignore_case:
            for line in data_lines[1:]:
                if (consecutive and line not in uniq_lines[-1]) or line not in uniq_lines:
                    uniq_lines.append(line)
        else:
            past_lines = [data_lines[0].strip().lower()]
            for line in data_lines[1:]:
                if (
                    consecutive and line.strip().lower() not in past_lines[-1]
                ) or line.strip().lower() not in past_lines:
                    past_lines.append(line.strip().lower())
                    uniq_lines.append(line)

        return separator.join(uniq_lines), mime_type


class RemoveDuplicateLinesFilter(FilterBase):
    """Remove duplicate lines (case sensitive)."""

    __kind__ = 'remove-duplicate-lines'

    __supported_subfilters__: dict[str, str] = {
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if not isinstance(data, str):
            raise ValueError
        separator = subfilter.get('separator', '\n')
        data_lines = data.split(separator)

        def get_unique_lines(lines: list[str]) -> Iterator[str]:
            seen = set()
            for line in lines:
                if line not in seen:
                    yield line
                    seen.add(line)

        return separator.join(get_unique_lines(data_lines)), mime_type


class ReverseFilter(FilterBase):
    """Reverse sort input items."""

    __kind__ = 'reverse'

    __supported_subfilters__: dict[str, str] = {
        'separator': 'Item separator (default: newline)',
    }

    __default_subfilter__ = 'separator'

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        separator = subfilter.get('separator', '\n')
        return separator.join(reversed(data.split(separator))), mime_type
