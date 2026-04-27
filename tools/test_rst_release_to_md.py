# pragma: exclude file
# ruff: noqa: S101  # Use of `assert` detected
"""Tests for ``rst_release_to_md.py`` (RELEASE.rst -> RELEASE.md converter).

Lives under ``tools/`` (next to the script it tests) rather than ``tests/`` because the converter only needs
verification when *it* changes -- not on every release run. Run with::

    pytest tools/test_rst_release_to_md.py
"""

from __future__ import annotations

from pathlib import Path

from rst_release_to_md import convert, main

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_heading() -> None:
    assert convert('Added\n`````\n') == '## Added\n'


def test_heading_underline_shorter_than_title_is_not_a_heading() -> None:
    # An underline must be at least as long as the title; otherwise the original lines pass through.
    src = 'Added\n```\n'
    assert convert(src) == src


def test_inline_literal() -> None:
    assert convert('Set ``foo`` here.') == 'Set `foo` here.'


def test_inline_literal_with_special_chars() -> None:
    src = 'see ``# yaml-language-server: $schema=config.schema.json`` at the top'
    assert convert(src) == 'see `# yaml-language-server: $schema=config.schema.json` at the top'


def test_bold_unchanged() -> None:
    assert convert('a **bold** word') == 'a **bold** word'


def test_top_level_bullet_normalised_to_dash() -> None:
    assert convert('* item one\n* item two\n') == '- item one\n- item two\n'


def test_nested_bullet_preserved() -> None:
    assert convert('  - subitem\n') == '  - subitem\n'


def test_bullet_continuation_line_preserved() -> None:
    src = '* a long item that wraps onto\n  a second line indented two spaces\n'
    assert convert(src) == '- a long item that wraps onto\n  a second line indented two spaces\n'


def test_trailing_newline_preserved() -> None:
    assert convert('hello\n') == 'hello\n'
    assert convert('hello') == 'hello'


def test_real_release_file_converts_cleanly() -> None:
    md = convert((_REPO_ROOT / 'RELEASE.rst').read_text(encoding='utf-8'))
    assert md.startswith('## ')
    assert '``' not in md  # every double-backtick literal was converted
    for line in md.splitlines():
        # No surviving backtick-underline lines (which would mean a heading wasn't consumed).
        assert not (line and set(line) == {'`'})


def test_main_writes_then_idempotent(tmp_path: Path) -> None:
    src = tmp_path / 'RELEASE.rst'
    src.write_text('Added\n`````\n* foo\n', encoding='utf-8')
    dst = tmp_path / 'RELEASE.md'

    assert main([str(src)]) == 1
    assert dst.read_text(encoding='utf-8') == '## Added\n- foo\n'

    mtime = dst.stat().st_mtime_ns
    assert main([str(src)]) == 0
    assert dst.stat().st_mtime_ns == mtime


def test_main_rewrites_when_md_is_stale(tmp_path: Path) -> None:
    src = tmp_path / 'RELEASE.rst'
    src.write_text('Added\n`````\n', encoding='utf-8')
    dst = tmp_path / 'RELEASE.md'
    dst.write_text('stale content\n', encoding='utf-8')

    assert main([str(src)]) == 1
    assert dst.read_text(encoding='utf-8') == '## Added\n'


def test_main_skips_missing_paths(tmp_path: Path) -> None:
    assert main([str(tmp_path / 'does-not-exist.rst')]) == 0
