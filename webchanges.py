#!/usr/bin/env python3
# Convenience script to run package from a Git checkout or a Docker build
# This is NOT the script that gets installed as part of "setup.py install"

import os
import sys

sys.path.insert(1, os.path.join(os.path.dirname(os.path.realpath(__file__))))

from webchanges.cli import main

main()
