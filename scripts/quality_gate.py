# -*- coding: utf-8 -*-
"""Run the static quality gate used before destructive migration passes.

The default gate intentionally avoids importing Qt, PyVista, or VTK.  It is safe
for CI, review machines, and packaging preparation.  Add ``--with-tests`` when a
full development environment is available.
"""

from __future__ import annotations

import argparse
import compileall
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"


def _run(command: list[str]) -> None:
    print("\n$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)



def _clean_python_artifacts() -> None:
    _run([sys.executable, "scripts/clean_python_artifacts.py"])


def _clean_runtime_diagnostics() -> None:
    diagnostics = ROOT / "diagnostics"
    if not diagnostics.exists():
        return
    kept = {".gitkeep", "README.md"}
    removed = 0
    for path in sorted(diagnostics.iterdir()):
        if path.is_file() and path.name not in kept:
            path.unlink(missing_ok=True)
            removed += 1
    if removed:
        print(f"Removed runtime diagnostic artifacts: {removed} files")



def _verify_runtime_source_packages() -> None:
    """Prevent generated-diagnostics cleanup from deleting runtime modules.

    ``ROOT/diagnostics`` contains disposable session artifacts.
    ``SRC/laserprog_studio/diagnostics`` is application source and must always
    ship because the shared Projected Drawing renderer imports it at startup.
    """

    required = (
        SRC / "laserprog_studio" / "diagnostics" / "__init__.py",
        SRC / "laserprog_studio" / "diagnostics" / "projected_overlay_debug.py",
        SRC / "laserprog_studio" / "diagnostics" / "app_performance_audit.py",
    )
    missing = [path.relative_to(ROOT) for path in required if not path.is_file()]
    if missing:
        formatted = ", ".join(str(path) for path in missing)
        raise SystemExit(f"Missing required runtime source package files: {formatted}")


def _compile_sources() -> None:
    print("\n$ python -m compileall src tests scripts")
    ok = True
    for target in (SRC, TESTS, ROOT / "scripts"):
        ok = compileall.compile_dir(str(target), quiet=1, force=False) and ok
    if not ok:
        raise SystemExit("compileall failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-tests", action="store_true", help="Also run the pytest suite.")
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, help="Arguments forwarded after pytest.")
    args = parser.parse_args(argv)

    _verify_runtime_source_packages()
    _compile_sources()
    _clean_python_artifacts()
    _verify_runtime_source_packages()
    _run([sys.executable, "scripts/verify_refactor_structure.py"])
    _run([sys.executable, "scripts/audit_architecture_health.py", "--max-mixins", "0", "--max-mixin-aliases", "0"])
    _run([sys.executable, "scripts/audit_api_boundaries.py", "--strict"])
    _run([sys.executable, "scripts/audit_tool_migration.py", "--strict"])
    _run([sys.executable, "scripts/audit_tool_product_quality.py", "--strict"])
    _clean_python_artifacts()
    _clean_runtime_diagnostics()

    if args.with_tests:
        pytest_args = args.pytest_args or []
        _run([sys.executable, "-m", "pytest", *pytest_args])
        _clean_python_artifacts()
        _clean_runtime_diagnostics()

    _clean_runtime_diagnostics()
    _verify_runtime_source_packages()
    _run([sys.executable, "scripts/product_tree_guard.py"])

    print("\nQuality gate OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
