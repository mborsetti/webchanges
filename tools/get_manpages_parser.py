from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser


sys.path.insert(0, str(Path.cwd()))

from webchanges.config import CommandConfig


def get_manpages_parser() -> ArgumentParser:
    """Returns the parser to be used by argparse-manpage.

    https://github.com/praiskup/argparse-manpage/blob/main/README.md
    """

    null_path = Path()
    return CommandConfig([], null_path, null_path, null_path, null_path, null_path).parse_args([])
