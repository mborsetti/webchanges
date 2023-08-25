#!/usr/bin/env python3

"""Convenience script to run package, e.g. from a Git checkout."""

import sys
from pathlib import Path

sys.path.insert(1, str(Path(__file__).parent))

from webchanges.cli import main  # noqa: E402 module level import not at top of file.

main()
