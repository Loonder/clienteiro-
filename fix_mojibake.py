#!/usr/bin/env python3
"""
Repair common mojibake artifacts in text files.

Default scope: templates/*.html
Usage:
  python fix_mojibake.py
  python fix_mojibake.py templates/admin.html templates/index.html
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BAD_MARKERS = ("\u00C3", "\u00C2", "\u00E2", "\u00F0", "\u00D0", "\uFFFD")
TOKEN_RE = re.compile(r"""[^\s<>"']+""")


def has_bad_marker(text: str) -> bool:
    return any(marker in text for marker in BAD_MARKERS)


def decode_mojibake_token(token: str) -> str:
    if not has_bad_marker(token):
        return token
    try:
        fixed = token.encode("latin1").decode("utf-8")
    except UnicodeError:
        return token
    if has_bad_marker(fixed):
        return token
    return fixed


def fix_text(content: str) -> str:
    return TOKEN_RE.sub(lambda match: decode_mojibake_token(match.group(0)), content)


def gather_targets(args: list[str]) -> list[Path]:
    if args:
        return [Path(arg) for arg in args]
    return sorted(Path("templates").rglob("*.html"))


def process_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False

    original = path.read_text(encoding="utf-8", errors="replace")
    fixed = fix_text(original)
    if fixed == original:
        return False

    path.write_text(fixed, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    targets = gather_targets(sys.argv[1:])
    changed: list[Path] = []

    for file_path in targets:
        if process_file(file_path):
            changed.append(file_path)

    if changed:
        print("Mojibake fixed in:")
        for item in changed:
            print(f"- {item.as_posix()}")
    else:
        print("No mojibake changes detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
