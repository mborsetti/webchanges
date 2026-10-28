"""The primary HTTP client: ``httpx2``, else ``httpx`` (same API) imported as ``httpx2``, else ``None``.

Modules get the client from here (``from webchanges._httpx import httpx2``) so that the choice is made in one place.
If neither is installed, ``requests`` and then ``curl_cffi`` are used instead (see ``UrlJob._select_http_client()`` in
``webchanges/jobs/_url.py``), so every use of ``httpx2`` must be guarded with ``if httpx2 is None`` / ``if httpx2``.
"""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ['Headers', 'h2', 'httpx2']

# The fallback assignments below are hidden from the type checker behind `if not TYPE_CHECKING`. Otherwise the type
# checker infers the union of all bindings (e.g. `<module 'httpx2'> | None`), and every reference to a module
# attribute — including in annotations such as `httpx2.Response`, which cannot be guarded at runtime — is reported as
# unresolved. Hiding the fallbacks keeps the httpx2 module type, which is what these code paths are guarded to run
# under.
try:
    import httpx2
    from httpx2 import Headers
except ImportError:  # pragma: no cover
    if not TYPE_CHECKING:
        try:
            import httpx as httpx2
            from httpx import Headers
        except ImportError:
            httpx2 = None
            from webchanges._vendored.headers import Headers

# HTTP/2 support (used only by the client above).
try:
    import h2
except ImportError:  # pragma: no cover
    h2 = None
