from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_dependencies", ROOT / "scripts" / "check_dependencies.py")
assert SPEC is not None and SPEC.loader is not None
check_dependencies = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_dependencies)


def test_exact_pins_remain_exact() -> None:
    name, operator, version = check_dependencies._split_requirement("PySide6==6.8.3")
    assert (name, operator, version) == ("PySide6", "==", "6.8.3")


def test_newer_versions_do_not_satisfy_exact_pins() -> None:
    assert not check_dependencies._version_satisfies("6.11.1", "==", "6.8.3")
    assert not check_dependencies._version_satisfies("9.6.2", "==", "9.4.2")
    assert not check_dependencies._version_satisfies("12.2.0", "==", "10.4.0")


def test_exact_versions_satisfy_exact_pins() -> None:
    assert check_dependencies._version_satisfies("6.8.3", "==", "6.8.3")
    assert check_dependencies._version_satisfies("9.4.2", "==", "9.4.2")
    assert check_dependencies._version_satisfies("10.4.0", "==", "10.4.0")


def test_older_versions_do_not_satisfy_runtime_floor() -> None:
    assert not check_dependencies._version_satisfies("6.7.0", ">=", "6.8.3")
    assert not check_dependencies._version_satisfies("9.3.9", ">=", "9.4.2")


class _VersionInfo:
    def __init__(self, major: int, minor: int, micro: int) -> None:
        self.major = major
        self.minor = minor
        self.micro = micro


def test_python_version_accepts_any_312_patch_release() -> None:
    assert check_dependencies._python_version_satisfies(_VersionInfo(3, 12, 0))
    assert check_dependencies._python_version_satisfies(_VersionInfo(3, 12, 4))
    assert check_dependencies._python_version_satisfies(_VersionInfo(3, 12, 10))
    assert not check_dependencies._python_version_satisfies(_VersionInfo(3, 11, 9))
    assert not check_dependencies._python_version_satisfies(_VersionInfo(3, 13, 0))
