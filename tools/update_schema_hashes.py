# pragma: exclude file

# #!/usr/bin/env python3
"""Rewrite the sibling ``.*.schema.sha256`` for every ``*.schema.json`` passed on the command line.

Used as a pre-commit hook so the bundled hashes in ``files/`` stay in sync with the schemas.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def main(paths: list[str]) -> int:
    changed = 0
    for path_str in paths:
        schema = Path(path_str)
        if not schema.is_file():
            continue
        digest = hashlib.sha256(schema.read_bytes()).hexdigest()
        hash_file = schema.with_name(f'.{schema.name}').with_suffix('.sha256')
        new_content = f'{digest}\n'
        try:
            existing = hash_file.read_text(encoding='utf-8')
        except FileNotFoundError:
            existing = ''
        if existing != new_content:
            hash_file.write_text(new_content, encoding='utf-8')
            changed += 1
            print(f'Updated {hash_file} ({digest[:12]}…)')
    return 1 if changed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
