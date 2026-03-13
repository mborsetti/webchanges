"""Encoding and hash filters."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import base64
import hashlib
from typing import Any

from webchanges.filters._base import FilterBase


class Sha1SumFilter(FilterBase):
    """Calculate the SHA-1 checksum of the content."""

    __kind__ = 'sha1sum'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        return hashlib.sha1(data, usedforsecurity=False).hexdigest(), 'text/plain'


class Sha256SumFilter(FilterBase):
    """Calculate the SHA-256 checksum of the content."""

    __kind__ = 'sha256sum'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        return hashlib.sha256(data, usedforsecurity=False).hexdigest(), 'text/plain'


class HexDumpFilter(FilterBase):
    """Convert string to hex dump format."""

    __kind__ = 'hexdump'

    __no_subfilter__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        if isinstance(data, str):
            data = data.encode(errors='ignore')
        arr = bytearray(data)
        blocks = [arr[i * 16 : (i + 1) * 16] for i in range(int((len(arr) + (16 - 1)) / 16))]
        return (
            '\n'.join(
                f'{" ".join(f"{c:02x}" for c in block):49}{"".join((chr(c) if (31 < c < 127) else ".") for c in block)}'
                for block in blocks
            ),
            'text/plain',
        )


class Ascii85(FilterBase):
    """Convert bytes data (e.g. images) into an ascii85 string.

    Ascii85 encoding is much more efficient than Base64.
    """

    __kind__ = 'ascii85'

    __no_subfilter__ = True

    __uses_bytes__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        data_to_encode = data.encode() if isinstance(data, str) else data
        return base64.a85encode(data_to_encode).decode(), 'text/plain'


class Base64(FilterBase):
    """Convert bytes data (e.g. images) into a base64 string.

    Base64 encoding causes an overhead of 33–37% relative to the size of the original binary data.
    """

    __kind__ = 'base64'

    __no_subfilter__ = True

    __uses_bytes__ = True

    def filter(self, data: str | bytes, mime_type: str, subfilter: dict[str, Any]) -> tuple[str | bytes, str]:
        data_to_encode = data.encode() if isinstance(data, str) else data
        return base64.b64encode(data_to_encode).decode(), 'text/plain'
