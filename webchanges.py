#!/usr/bin/env python3

"""Convenience script to run package, e.g. from a Git checkout."""

import os
import sys

sys.path.insert(1, os.path.join(os.path.dirname(os.path.realpath(__file__))))

from webchanges.cli import main  # noqa: E402 module level import not at top of file

main()
