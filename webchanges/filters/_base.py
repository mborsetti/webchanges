"""Base classes for filters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import itertools
import logging
import warnings
from typing import TYPE_CHECKING, Any, Iterator, Literal

import yaml

from webchanges.util import TrackSubClasses

if TYPE_CHECKING:
    import re

    from webchanges.handler import JobState

logger = logging.getLogger(__name__)


FiltersList = Literal[
    'absolute_links',
    'ascii85',
    'base64',
    'beautify',
    'format-json',
    'format-xml',
    'hexdump',
    'html2text',
    'ical2text',
    'jsontoyaml',
    'pretty-xml',
    'remove_repeated',
    'reverse',
    'sha1sum',
    'sort',
    'strip',
]


class FilterBase(metaclass=TrackSubClasses):
    """The base class for filters."""

    __subclasses__: dict[str, type[FilterBase]] = {}
    __anonymous_subclasses__: list[type[FilterBase]] = []

    __kind__: str = ''

    # Typing
    __supported_subfilters__: dict[str, str]
    __default_subfilter__: str
    __no_subfilter__: bool
    __uses_bytes__: bool
    method: str

    def __init__(self, state: JobState) -> None:
        """:param state: the JobState."""
        self.job = state.job
        self.state = state

    @classmethod
    def filter_documentation(cls) -> str:
        """Generates simple filter documentation for use in the --features command line argument.

        :returns: A string to display.
        """
        result: list[str] = []
        for sc in TrackSubClasses.sorted_by_kind(cls):
            default_subfilter = getattr(sc, '__default_subfilter__', None)
            result.extend((f'  * {sc.__kind__} - {sc.__doc__}',))
            if hasattr(sc, '__supported_subfilters__'):
                for key, doc in sc.__supported_subfilters__.items():
                    result.append(
                        f'      {"[" if key == default_subfilter else ""}{key}{"]" if key == default_subfilter else ""}'
                        f' ... {doc}'
                    )
        result.append('\n[] ... Parameter can be supplied as unnamed value\n')
        return '\n'.join(result)

    @classmethod
    def auto_process(cls, state: JobState, data: str | bytes, mime_type: str) -> tuple[str | bytes, str]:
        """Processes all automatic filters (those with "MATCH" set) in JobState.Job over the data.

        :param state: The JobState object.
        :param data: The data to be processed (filtered).
        :returns: The output from the chain of filters (filtered data).
        """
        filters = itertools.chain(
            (filtercls for _, filtercls in sorted(cls.__subclasses__.items(), key=lambda k_v: k_v[0])),
            cls.__anonymous_subclasses__,
        )

        for filtercls in filters:
            filter_instance = filtercls(state)
            if filter_instance.match():
                logger.info(f'Job {state.job.index_number}: Auto-applying filter {filter_instance}')
                data, mime_type = filter_instance.filter(data, mime_type, {})  # All filters take a subfilter

        return data, mime_type

    @classmethod
    def normalize_filter_list(
        cls,
        filter_spec: str | list[str | dict[str, Any]] | None,
        job_index_number: int | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Generates a list of filters that has been checked for its validity.

        :param filter_spec: A list of either filter_kind, subfilter (where subfilter is a dict) or a legacy
           string-based filter list specification.
        :param job_index_number: The job index number.
        :returns: Iterator of filter_kind, subfilter (where subfilter is a dict).
        """
        for filter_kind, subfilter in cls._internal_normalize_filter_list(filter_spec, job_index_number):
            filtercls = cls.__subclasses__.get(filter_kind, None)

            if filtercls is None:
                raise ValueError(
                    f'Job {job_index_number}: Unknown filter kind: {filter_kind} (subfilter or filter directive(s): '
                    f'{subfilter}).'
                )

            if getattr(filtercls, '__no_subfilter__', False) and subfilter:
                raise ValueError(
                    f'Job {job_index_number}: No subfilters or filter directives supported for {filter_kind}.'
                )

            if hasattr(filtercls, '__supported_subfilters__'):
                provided_keys = set(subfilter.keys())
                allowed_keys = set(filtercls.__supported_subfilters__.keys())
                unknown_keys = provided_keys.difference(allowed_keys)
                if unknown_keys and '<any>' not in allowed_keys:
                    if allowed_keys:
                        raise ValueError(
                            f'Job {job_index_number}: Filter {filter_kind} does not support subfilter or filter '
                            f'directive(s) {", ".join(unknown_keys)}. Only {", ".join(allowed_keys)} are supported.'
                        )
                    else:
                        raise ValueError(
                            f'Job {job_index_number}: Filter {filter_kind} does not support any subfilters or filter '
                            f'directives, but {", ".join(unknown_keys)} was supplied.'
                        )

            yield filter_kind, subfilter

    @classmethod
    def _internal_normalize_filter_list(
        cls,
        filter_spec: str | list[str | dict[str, Any]] | None,
        job_index_number: int | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Generates a list of filters with its default subfilter if not supplied.

        :param filter_spec: A list of either filter_kind, subfilter (where subfilter is a dict) or a legacy
           string-based filter list specification.
        :returns: Iterator of filter_kind, subfilter (where subfilter is a dict)
        """
        if isinstance(filter_spec, str):
            old_filter_spec = filter_spec

            # Legacy string-based filter list specification:
            # "filter1:param1,filter2,filter3,filter4:param4"
            filter_spec = [
                (
                    {filter_kind.split(':', maxsplit=1)[0]: filter_kind.split(':', maxsplit=1)[1]}
                    if ':' in filter_kind
                    else {filter_kind: ''}
                )
                for filter_kind in old_filter_spec.split(',')
            ]
            warnings.warn(
                f'String-based filter definitions ({old_filter_spec}) are deprecated, please convert to dict-style:\n\n'
                f'{yaml.safe_dump(filter_spec, default_flow_style=False, allow_unicode=True, sort_keys=False)}',
                DeprecationWarning,
                stacklevel=1,
            )

        if isinstance(filter_spec, list):
            for item in filter_spec:
                if isinstance(item, str):
                    filter_kind, subfilter = item, None
                elif isinstance(item, dict):
                    filter_kind, subfilter = next(iter(item.items()))
                else:
                    raise ValueError(
                        f'Job {job_index_number}: Subfilter or filter directive(s) must be a string or a dictionary.'
                    )

                filtercls = cls.__subclasses__.get(filter_kind, None)

                if isinstance(subfilter, dict):
                    yield filter_kind, subfilter
                elif subfilter is None:
                    yield filter_kind, {}
                elif hasattr(filtercls, '__default_subfilter__') and filtercls is not None:
                    yield filter_kind, {filtercls.__default_subfilter__: subfilter}
                else:
                    yield filter_kind, subfilter

    @classmethod
    def process(
        cls, filter_kind: str, subfilter: dict[str, Any], job_state: JobState, data: str | bytes, mime_type: str
    ) -> tuple[str | bytes, str]:
        """Process the filter.

        :param filter_kind: The name of the filter.
        :param subfilter: The subfilter information.
        :param job_state: The JobState object (containing the Job).
        :param data: The data upon which to apply the filter.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        logger.info(f'Job {job_state.job.index_number}: Applying filter {filter_kind}, subfilter(s) {subfilter}')
        filtercls: type[FilterBase] | None = cls.__subclasses__.get(filter_kind)
        if filtercls:
            return filtercls(job_state).filter(data, mime_type, subfilter)
        return data, mime_type

    @classmethod
    def filter_chain_needs_bytes(cls, filter_name: str | list[str | dict[str, Any]] | None) -> bool:
        """Checks whether the first filter requires data in bytes (not Unicode).

        :param filter_name: The filter.
        :returns: True if the first filter requires data in bytes.
        """
        first_filter = next(cls.normalize_filter_list(filter_name), None)
        if first_filter is not None:
            filter_kind, _ = first_filter
            return cls.is_bytes_filter_kind(filter_kind)

        return False

    @classmethod
    def is_bytes_filter_kind(cls, filter_kind: str) -> bool:
        """Checks whether the filter requires data in bytes (not Unicode).

        :param filter_kind: The filter name.
        :returns: True if the filter requires data in bytes.
        """
        return filter_kind in (
            name for name, class_ in cls.__subclasses__.items() if getattr(class_, '__uses_bytes__', False)
        )

    def match(self) -> bool:
        """Method used by automatch filters.

        :returns: True if an automatch filter.
        """
        return False

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Method used by the filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        raise NotImplementedError

    def raise_import_error(self, package_name: str, filter_name: str, error_message: str) -> None:
        """Raise ImportError for missing package.

        :param package_name: The name of the module/package that could not be imported.
        :param filter_name: The name of the filter that needs the package.
        :param error_message: The error message from ImportError.

        :raises: ImportError.
        """
        raise ImportError(
            f"Filter {filter_name} requires package '{package_name}', which has the following error: {error_message}"
        )


class AutoMatchFilter(FilterBase):
    """Base class for filters that automatically exactly match one or more directives.

    MATCH is a dict of {directive: text to match}.
    """

    MATCH: dict[str, str] | None = None

    def match(self) -> bool:
        """Check whether the filter matches (i.e. needs to be executed).

        :returns: True if match is found.
        """
        if self.MATCH is None:
            return False

        d = self.job.to_dict()
        result = all(d.get(k, None) == v for k, v in self.MATCH.items())
        logger.debug(f'Matching {self} with {self.job} result: {result}')
        return result

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Method used by filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        raise NotImplementedError


class RegexMatchFilter(FilterBase):
    """Base class for filters that automatically match one or more directives.

    Same as AutoMatchFilter but MATCH is a dict of {directive: Regular Expression Object}, where a Regular
    Expression Object is a compiled regex.
    """

    MATCH: dict[str, re.Pattern] | None = None

    def match(self) -> bool:
        """Check whether the filter matches (i.e. needs to be executed).

        :returns: True if match is found.
        """
        if self.MATCH is None:
            return False

        d = self.job.to_dict()

        # It's a match if we have at least one key/value pair that matches,
        # and no key/value pairs that do not match
        matches = [v.match(d[k]) for k, v in self.MATCH.items() if k in d]
        result = len(matches) > 0 and all(matches)
        logger.debug(f'Matching {self} with {self.job} result: {result}')
        return result

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        """Method used by filter to process data.

        :param data: The data to be filtered (processed).
        :param subfilter: The subfilter information.
        :returns: The data and media type (fka MIME type) of the data after the filter has been applied.
        """
        raise NotImplementedError
