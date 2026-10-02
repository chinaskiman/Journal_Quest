"""Screenshot path security - directory allow-list containment check.

The screenshot endpoint must never serve an arbitrary local file.  A path is
only served when, after full resolution (symlinks, junctions, ``..`` and 8.3
aliases are resolved by ``Path.resolve()``), it is inside one of the
explicitly configured permitted directories.  Comparison is case-insensitive
on Windows via ``os.path.normcase``.

Fail-closed: any resolution error or unmatched path is rejected.
"""
from __future__ import annotations

import os
from pathlib import Path


def _norm(path: Path) -> str:
    return os.path.normcase(str(path))


def is_permitted(path_str: str, roots: list[str]) -> bool:
    """True iff ``path_str`` resolves inside one of ``roots`` (or equals it)."""
    try:
        resolved = Path(path_str).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    target = _norm(resolved)
    for root in roots:
        try:
            root_resolved = Path(root).resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        r = _norm(root_resolved)
        if target == r or target.startswith(r + os.sep):
            return True
    return False
