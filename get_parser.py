import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from webchanges.config import CommandConfig


def get_parser() -> ArgumentParser:
    """Returns the parser to be used by argparse-manpages
    https://github.com/praiskup/argparse-manpage/blob/main/README.md
    """

    null_path = Path()
    return CommandConfig([], null_path, null_path, null_path, null_path, null_path).parse_args([])
