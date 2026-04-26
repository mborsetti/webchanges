# Shim required to wire argparse-manpage's build_manpages cmdclass into setuptools.
# All other configuration lives in pyproject.toml.
# See https://github.com/praiskup/argparse-manpage/blob/main/README.md
from __future__ import annotations

from build_manpages import build_manpages, get_build_py_cmd, get_install_cmd
from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.install import install

setup(
    cmdclass={
        'build_manpages': build_manpages,
        'build_py': get_build_py_cmd(build_py),
        'install': get_install_cmd(install),
    },
)
