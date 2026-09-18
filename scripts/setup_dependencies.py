# -*- coding: utf-8 -*-
"""Reliable dependency setup for LaserProg Studio.

This helper is intentionally implemented in Python instead of complex nested
batch blocks.  Windows ``cmd.exe`` error levels are easy to accidentally keep
or overwrite when a command is executed inside a parenthesised block.  The
final dependency check is authoritative: if every pinned package is available
at the end, setup succeeds even when pip emitted a recoverable non-zero status
while replacing an already-installed package.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, NamedTuple, TextIO


REQUIRED_PYTHON_SERIES = (3, 12)


class CommandResult(NamedTuple):
    returncode: int
    command: tuple[str, ...]


def _python_label() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _python_is_supported() -> bool:
    return sys.version_info[:2] == REQUIRED_PYTHON_SERIES


def _write_line(message: str, log: TextIO, *, console: bool = True) -> None:
    if console:
        print(message, flush=True)
    print(message, file=log, flush=True)


def _command_text(command: Iterable[str]) -> str:
    def quote(value: str) -> str:
        return f'"{value}"' if any(char.isspace() for char in value) else value

    return " ".join(quote(part) for part in command)


def _run_logged(command: list[str], log: TextIO) -> CommandResult:
    """Run a command and append all output to the setup log."""
    _write_line(f"COMMAND: {_command_text(command)}", log, console=False)
    try:
        completed = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError as exc:
        _write_line(f"COMMAND ERROR: {exc}", log, console=False)
        return CommandResult(127, tuple(command))
    _write_line(f"EXIT CODE: {completed.returncode}", log, console=False)
    return CommandResult(completed.returncode, tuple(command))


def _dependency_check_command(root: Path) -> list[str]:
    return [sys.executable, str(root / "scripts" / "check_dependencies.py")]


def _pip_command(*arguments: str) -> list[str]:
    return [sys.executable, "-m", "pip", *arguments]


def _final_result(final_check_exit: int) -> int:
    """The final dependency state is the only success criterion."""
    return 0 if final_check_exit == 0 else 1


def run_setup(root: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        _write_line("----------------------------------------", log)
        _write_line("LaserProg Studio dependency setup", log)
        _write_line("Installation mode: central Python, no venv", log)
        _write_line("Required Python: 3.12.x", log)
        _write_line(f"Selected Python: {sys.executable}", log)
        _write_line(f"Selected version: {_python_label()}", log)
        _write_line(f"Project root: {root}", log, console=False)
        _write_line(f"Log file: {log_path}", log, console=False)
        _write_line("----------------------------------------", log)

        if not _python_is_supported():
            _write_line(
                f"ERROR: Python {_python_label()} is selected; LaserProg requires Python 3.12.x.",
                log,
            )
            _write_line("RESULT: FAILURE", log)
            return 1

        requirements = root / "requirements.txt"
        checker = root / "scripts" / "check_dependencies.py"
        if not requirements.is_file():
            _write_line(f"ERROR: requirements.txt was not found: {requirements}", log)
            _write_line("RESULT: FAILURE", log)
            return 2
        if not checker.is_file():
            _write_line(f"ERROR: dependency checker was not found: {checker}", log)
            _write_line("RESULT: FAILURE", log)
            return 2

        _write_line("Checking pip availability...", log)
        pip_check = _run_logged(_pip_command("--version"), log)
        if pip_check.returncode != 0:
            _write_line("pip is unavailable; trying ensurepip...", log)
            ensurepip = _run_logged([sys.executable, "-m", "ensurepip", "--upgrade"], log)
            if ensurepip.returncode != 0:
                _write_line("ERROR: pip is unavailable and ensurepip failed.", log)
                _write_line("RESULT: FAILURE", log)
                return 1

        _write_line("Updating pip, setuptools and wheel...", log)
        tooling = _run_logged(_pip_command("install", "--upgrade", "pip", "setuptools", "wheel"), log)
        if tooling.returncode != 0:
            _write_line(
                "WARNING: pip tooling could not be updated. Continuing with the available pip version.",
                log,
            )

        _write_line("Checking the currently installed dependencies...", log)
        initial_check = _run_logged(_dependency_check_command(root), log)

        install_result: CommandResult | None = None
        if initial_check.returncode == 0:
            _write_line("Pinned dependencies are already installed. No package replacement is needed.", log)
        else:
            _write_line("Installing the pinned dependencies from requirements.txt...", log)
            install_result = _run_logged(
                _pip_command(
                    "install",
                    "--upgrade",
                    "--upgrade-strategy",
                    "only-if-needed",
                    "-r",
                    str(requirements),
                ),
                log,
            )
            if install_result.returncode != 0:
                _write_line(
                    "WARNING: pip returned a non-zero status. The final dependency check will determine the actual result.",
                    log,
                )

        _write_line("Running the authoritative final dependency check...", log)
        final_check = _run_logged(_dependency_check_command(root), log)
        result = _final_result(final_check.returncode)

        _write_line("----------------------------------------", log)
        if result == 0:
            if install_result is not None and install_result.returncode != 0:
                _write_line(
                    "Setup complete. pip reported a recoverable issue, but every required dependency is correctly installed.",
                    log,
                )
            else:
                _write_line("Setup complete. Every required dependency is correctly installed.", log)
            _write_line("To start the app, run RUN_LASERPROG_STUDIO.bat", log)
            _write_line("RESULT: SUCCESS", log)
        else:
            _write_line("ERROR: The final dependency check failed.", log)
            _write_line("Review the command output above to identify missing or incompatible packages.", log)
            _write_line("RESULT: FAILURE", log)
        _write_line("----------------------------------------", log)
        return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return run_setup(args.root.resolve(), args.log.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
