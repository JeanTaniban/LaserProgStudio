# -*- coding: utf-8 -*-
"""Guard the repository/product boundary for LaserProg Studio.

This check keeps generated runtime folders and historical migration material out
of the future executable payload.  It stays static and does not import the app.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "diagnostics"
REQUIRED_PRODUCT_FILES = (
    ROOT / "run.py",
    ROOT / "requirements.txt",
    ROOT / "pyproject.toml",
    ROOT / "src" / "laserprog_studio" / "assets" / "logo.ico",
    ROOT / "src" / "laserprog_studio" / "assets" / "logo.png",
)
ARCHIVE_DIRS = (
    ROOT / "docs" / "archive",
    ROOT / "docs" / "archive" / "passes",
)


def _fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    missing = [path.relative_to(ROOT).as_posix() for path in REQUIRED_PRODUCT_FILES if not path.exists()]
    if missing:
        _fail("Missing product file(s): " + ", ".join(missing))

    missing_archives = [path.relative_to(ROOT).as_posix() for path in ARCHIVE_DIRS if not path.is_dir()]
    if missing_archives:
        _fail("Missing archive directory/directories: " + ", ".join(missing_archives))

    if DIAGNOSTICS.exists():
        historical_reports = sorted(path for path in DIAGNOSTICS.glob("*.md") if path.name != "README.md")
        if historical_reports:
            rel = ", ".join(path.relative_to(ROOT).as_posix() for path in historical_reports)
            _fail("Move historical diagnostics reports into docs/archive/passes: " + rel)

    root_pass_reports = sorted((ROOT / "docs").glob("source_cleanup_pass*.md"))
    if root_pass_reports:
        rel = ", ".join(path.relative_to(ROOT).as_posix() for path in root_pass_reports)
        _fail("Move historical source-cleanup reports into docs/archive/passes: " + rel)

    python_artifacts = sorted(
        [*(ROOT / "src").rglob("__pycache__"), *(ROOT / "tests").rglob("__pycache__"), *(ROOT / "scripts").rglob("__pycache__"), *(ROOT / "examples").rglob("__pycache__"),
         *(ROOT / "src").rglob("*.py[co]"), *(ROOT / "tests").rglob("*.py[co]"), *(ROOT / "scripts").rglob("*.py[co]"), *(ROOT / "examples").rglob("*.py[co]")]
    )
    if python_artifacts:
        preview = ", ".join(path.relative_to(ROOT).as_posix() for path in python_artifacts[:12])
        suffix = "" if len(python_artifacts) <= 12 else f", ... +{len(python_artifacts) - 12} more"
        _fail("Remove Python cache artifacts before packaging: " + preview + suffix)

    print("Product tree guard OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
