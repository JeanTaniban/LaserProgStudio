from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "setup_dependencies", ROOT / "scripts" / "setup_dependencies.py"
)
assert SPEC is not None and SPEC.loader is not None
setup_dependencies = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_dependencies)


def _fake_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (root / "requirements.txt").write_text("example-package==1.0\n", encoding="utf-8")
    (scripts / "check_dependencies.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    return root, root / "diagnostics" / "setup_dependencies.log"


def test_final_check_is_authoritative_after_recoverable_pip_error(tmp_path, monkeypatch) -> None:
    root, log_path = _fake_root(tmp_path)
    results = iter((0, 0, 1, 1, 0))

    def fake_run(command, log):
        return setup_dependencies.CommandResult(next(results), tuple(command))

    monkeypatch.setattr(setup_dependencies, "_python_is_supported", lambda: True)
    monkeypatch.setattr(setup_dependencies, "_run_logged", fake_run)

    assert setup_dependencies.run_setup(root, log_path) == 0
    text = log_path.read_text(encoding="utf-8")
    assert "pip reported a recoverable issue" in text
    assert "RESULT: SUCCESS" in text
    assert "RESULT: FAILURE" not in text


def test_failed_final_check_produces_one_clear_failure(tmp_path, monkeypatch) -> None:
    root, log_path = _fake_root(tmp_path)
    results = iter((0, 0, 1, 0, 1))

    def fake_run(command, log):
        return setup_dependencies.CommandResult(next(results), tuple(command))

    monkeypatch.setattr(setup_dependencies, "_python_is_supported", lambda: True)
    monkeypatch.setattr(setup_dependencies, "_run_logged", fake_run)

    assert setup_dependencies.run_setup(root, log_path) == 1
    text = log_path.read_text(encoding="utf-8")
    assert "RESULT: FAILURE" in text
    assert "RESULT: SUCCESS" not in text


def test_batch_delegates_status_to_python_helper() -> None:
    text = (ROOT / "scripts" / "install_dependencies.bat").read_text(encoding="utf-8")
    assert "setup_dependencies.py" in text
    assert 'set "SETUP_EXIT=!ERRORLEVEL!"' in text
    assert "--force-reinstall" not in text
    assert "final dependency check" in (ROOT / "scripts" / "setup_dependencies.py").read_text(
        encoding="utf-8"
    ).lower()
