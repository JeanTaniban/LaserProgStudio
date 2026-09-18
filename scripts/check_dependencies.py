# -*- coding: ascii -*-
"""Check LaserProg Studio runtime dependencies.

The Windows launcher uses this helper before starting the application.
LaserProg's Qt/PyVista/VTK overlay stack is sensitive to runtime package
versions, so the Python interpreter and packages pinned with ``==`` in
requirements.txt must match exactly.  Unpinned requirements are only checked
for presence.

Exit codes:
  0 when Python and every required package match the pinned runtime versions,
  1 when Python is not from the 3.12.x series or a package is missing/different,
  2 when requirements.txt cannot be read.
"""
from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path


REQUIRED_PYTHON_SERIES = (3, 12)

_REQUIREMENT_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*([<>=!~]{1,2})?\s*([^\s,;]+)?")
_VERSION_TOKEN_RE = re.compile(r"\d+|[A-Za-z]+")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _clean_requirement(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # Drop inline comments and pip environment markers for this simple checker.
    line = line.split("#", 1)[0].strip()
    line = line.split(";", 1)[0].strip()
    return line or None


def _split_requirement(requirement: str) -> tuple[str, str | None, str | None]:
    """Return ``(name, operator, version)`` for runtime checks.

    Exact pins stay exact.  This is intentional: LaserProg's visible 2D overlays
    depend on the tested PySide6/PyVista/VTK combination, so newer versions must
    be treated as incompatible until explicitly validated.
    """
    match = _REQUIREMENT_RE.match(requirement)
    if not match:
        return requirement.strip(), None, None
    name, operator, version = match.groups()
    if operator not in {"==", ">=", ">", "<=", "<", "~=", "!="}:
        operator = None
        version = None
    return name.strip(), operator, version.strip() if version else None


def _normalise_version(version: str) -> tuple[object, ...]:
    """Small PEP-440-ish version key good enough for LaserProg's stable pins."""
    cleaned = version.split("+", 1)[0].split("-", 1)[0]
    tokens: list[object] = []
    for token in _VERSION_TOKEN_RE.findall(cleaned):
        if token.isdigit():
            tokens.append(int(token))
        else:
            tokens.append(token.lower())
    return tuple(tokens)


def _cmp_versions(left: str, right: str) -> int:
    left_key = list(_normalise_version(left))
    right_key = list(_normalise_version(right))
    max_len = max(len(left_key), len(right_key))
    left_key.extend([0] * (max_len - len(left_key)))
    right_key.extend([0] * (max_len - len(right_key)))
    for left_item, right_item in zip(left_key, right_key):
        if left_item == right_item:
            continue
        if isinstance(left_item, int) and isinstance(right_item, str):
            return -1
        if isinstance(left_item, str) and isinstance(right_item, int):
            return 1
        return -1 if left_item < right_item else 1
    return 0


def _version_satisfies(installed: str, operator: str | None, required: str | None) -> bool:
    if not operator or not required:
        return True
    cmp_result = _cmp_versions(installed, required)
    if operator == "==":
        return cmp_result == 0
    if operator == "!=":
        return cmp_result != 0
    if operator == ">=":
        return cmp_result >= 0
    if operator == ">":
        return cmp_result > 0
    if operator == "<=":
        return cmp_result <= 0
    if operator == "<":
        return cmp_result < 0
    if operator == "~=":
        # Conservative for the launcher: accept the tested version only.
        return cmp_result == 0
    return True


def _python_version_label(version_info: object | None = None) -> str:
    if version_info is None:
        version_info = sys.version_info
    return f"{version_info.major}.{version_info.minor}.{version_info.micro}"


def _python_version_satisfies(version_info: object | None = None) -> bool:
    if version_info is None:
        version_info = sys.version_info
    return (version_info.major, version_info.minor) == REQUIRED_PYTHON_SERIES


def main() -> int:
    root = _project_root()
    if not _python_version_satisfies():
        required = ".".join(str(part) for part in REQUIRED_PYTHON_SERIES) + ".x"
        print(f"ERROR: Python {_python_version_label()} is selected; LaserProg requires Python {required}.")
        print("Install any stable Python 3.12 release and make INSTALL_DEPENDENCIES.bat select it before installing packages.")
        return 1

    req_path = root / "requirements.txt"
    if not req_path.exists():
        print(f"ERROR: requirements.txt not found: {req_path}")
        return 2

    requirements = []
    for raw_line in req_path.read_text(encoding="utf-8").splitlines():
        clean = _clean_requirement(raw_line)
        if clean:
            requirements.append(_split_requirement(clean))

    missing: list[str] = []
    incompatible: list[str] = []

    for dist_name, operator, required_version in requirements:
        try:
            installed_version = metadata.version(dist_name)
        except metadata.PackageNotFoundError:
            missing.append(dist_name)
            continue
        if not _version_satisfies(installed_version, operator, required_version):
            requirement = f"{operator}{required_version}" if operator and required_version else "installed"
            incompatible.append(f"{dist_name} installed={installed_version} required={requirement}")

    if missing:
        print("Missing packages:")
        for name in missing:
            print(f"  - {name}")
    if incompatible:
        print("Packages with a different pinned runtime version:")
        for item in incompatible:
            print(f"  - {item}")

    if missing or incompatible:
        return 1

    print("All dependencies are installed with the pinned LaserProg runtime versions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
