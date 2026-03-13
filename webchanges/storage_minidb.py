"""Backward-compatibility shim — import from webchanges.storage._minidb instead."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from webchanges.storage._minidb import SsdbMiniDBStorage

__all__ = ['SsdbMiniDBStorage']
