"""
Vendored version of requests.structures.CaseInsensitiveDict from requests v2.31.0 released on 22-May-23
https://github.com/psf/requests/tree/v2.31.0.

This is to have this class in case requests isn't available.  Consider using HTTPX's Headers class in the future,
but more evaluation is needed (TODO).

See https://github.com/psf/requests and https://github.com/psf/requests/blob/main/src/requests/structures.py
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, MutableMapping
from typing import Any, Iterable, Iterator, Protocol, TypeVar

_KT = TypeVar('_KT')
_VT = TypeVar('_VT')
_VT_co = TypeVar('_VT_co', covariant=True)


class SupportsKeysAndGetItem(Protocol[_KT, _VT_co]):
    def keys(self) -> Iterable[_KT]:
        pass

    def __getitem__(self, __key: _KT) -> _VT_co:
        pass


# class SupportsKeysAndGetItem(Protocol):
#     def keys(self) -> Iterable[str]:
#         ...
#
#     def __getitem__(self, __key: str) -> Any:
#         ...


class CaseInsensitiveDict(MutableMapping[str, _VT]):
    """A case-insensitive ``dict``-like object.

    Implements all methods and operations of ``MutableMapping`` as well as dict's ``copy``. Also provides
    ``lower_items``.

    All keys are expected to be strings. The structure remembers the case of the last key to be set, and
    ``iter(instance)``, ``keys()``, ``items()``, ``iterkeys()``, and ``iteritems()`` will contain case-sensitive
    keys. However, querying and contains testing is case insensitive:

        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['aCCEPT'] == 'application/json'  # True
        list(cid) == ['Accept']  # True

    For example, ``headers['content-encoding']`` will return the value of a ``'Content-Encoding'`` response header,
    regardless of how the header name was originally stored.

    If the constructor, ``.update``, or equality comparison operations are given keys that have equal ``.lower()``s, the
    behavior is undefined.
    """

    _store: OrderedDict[str, tuple[str, _VT]]

    def __init__(self, data: SupportsKeysAndGetItem | None = None, **kwargs: Any) -> None:
        self._store = OrderedDict()
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key: str, value: _VT) -> None:
        # Use the lowercased key for lookups, but store the actual key alongside the value.
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key: str) -> _VT:
        return self._store[key.lower()][1]

    def __delitem__(self, key: str) -> None:
        del self._store[key.lower()]

    def __iter__(self) -> Iterator[str]:
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    def lower_items(self) -> Iterator[tuple[str, _VT]]:
        """Like iteritems(), but with all lowercase keys."""
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            other = CaseInsensitiveDict(other)
        else:
            return NotImplemented
        # Compare insensitively
        return dict(self.lower_items()) == dict(other.lower_items())

    # Copy is required
    def copy(self) -> 'CaseInsensitiveDict':
        return CaseInsensitiveDict(self._store.values())  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return str(dict(self.items()))
