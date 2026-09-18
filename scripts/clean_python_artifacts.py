# -*- coding: utf-8 -*-
"""Remove local Python cache artifacts before packaging or archiving."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEAN_ROOTS = (ROOT / "src", ROOT / "tests", ROOT / "scripts", ROOT / "examples")


def clean_python_artifacts() -> tuple[int, int]:
    removed_dirs = 0
    removed_files = 0
    for base in CLEAN_ROOTS:
        if not base.exists():
            continue
        for cache_dir in sorted(base.rglob("__pycache__"), reverse=True):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir, ignore_errors=True)
                removed_dirs += 1
        for pyc in sorted(base.rglob("*.py[co]")):
            if pyc.is_file():
                try:
                    pyc.unlink()
                    removed_files += 1
                except FileNotFoundError:
                    pass
    return removed_dirs, removed_files


def main() -> int:
    dirs, files = clean_python_artifacts()
    print(f"Removed Python cache artifacts: {dirs} dirs, {files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
