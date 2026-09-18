# Dependency setup status v105

The Windows installer no longer uses nested `cmd.exe` error-level branches to decide whether package installation succeeded. `scripts/install_dependencies.bat` selects a compatible Python 3.12.x interpreter and delegates the workflow to `scripts/setup_dependencies.py`.

The helper records each command and exit code, performs an initial dependency check, installs pinned requirements only when required, and always performs a final dependency check. The final check is authoritative. A non-zero pip result is logged as a warning when the required packages are nevertheless present and compatible at the end.

Every completed log ends with exactly one explicit status marker:

- `RESULT: SUCCESS`
- `RESULT: FAILURE`

The launcher also writes the selected command, exact Python patch version, and actual interpreter path without relying on fragile `for /f` quoting.
