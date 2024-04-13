"""
Extension to Sphinx that generates a hierarchical list of classes using the contents of the ``__kind__`` attribute.
"""

from __future__ import annotations

import importlib
from typing import Iterator, List, TypeVar

from docutils.nodes import literal_block
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx

T = TypeVar('T')


def patch_subclasses(klass: type) -> None:
    """Recursively patch webchanges classes to behave like standard python classes."""
    klass.__subclasses__ = type.__subclasses__.__get__(klass)  # type: ignore[method-assign]

    for kls in klass.__subclasses__():
        patch_subclasses(kls)


def build_tree(klass: type, level: int) -> Iterator[str]:
    """Recurse into klass to build tree."""
    for i, kls in enumerate(klass.__subclasses__()):
        branch = '└───' if i + 1 == len(klass.__subclasses__()) else '├───'
        indent = '│   ' * (level - 1)
        yield ('' if level == 0 else indent + branch) + kls.__kind__  # type: ignore[attr-defined]

        yield from build_tree(kls, level + 1)


class InheritanceAsciiTree(Directive):
    required_arguments = 1

    def run(self) -> List[literal_block]:
        rootparts: List[str] = self.arguments.pop().split('.')
        rootname = rootparts.pop()
        rootmodulename = '.'.join(rootparts)

        rootmodule = importlib.import_module(rootmodulename)
        root = getattr(rootmodule, rootname)

        patch_subclasses(root)

        tree = (element for element in build_tree(root, 0))
        treestring = '\n'.join(tree)
        return [literal_block(treestring, treestring)]


def setup(app: Sphinx) -> None:
    app.add_directive('inheritance-ascii-tree', InheritanceAsciiTree)
