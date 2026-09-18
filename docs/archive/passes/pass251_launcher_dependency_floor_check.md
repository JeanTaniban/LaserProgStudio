# Pass 251 — Launcher dependency floor check

## Context

A user machine with central Python 3.12 failed to launch v79 even though the required runtime packages were installed. The launcher log showed packages flagged only because they were newer than the exact versions listed in `requirements.txt`:

- `numpy installed=2.4.6 required=2.0.1`
- `pillow installed=12.2.0 required=10.4.0`
- `PySide6 installed=6.11.1 required=6.8.3`
- `pyvista installed=0.48.4 required=0.46.5`
- `vtk installed=9.6.2 required=9.4.2`

The failure was in the launcher dependency checker, not in the Machine/G-code module.

## Fix

- `requirements.txt` now expresses runtime dependency floors with `>=` instead of exact pins.
- `scripts/check_dependencies.py` now treats old exact pins as minimum compatible runtime floors too, so older bundles remain robust.
- Newer installed versions are accepted and logged as accepted newer versions.
- Missing packages or packages below the required floor still fail clearly.
- Launcher wording now says dependencies are missing or below the required runtime version, instead of claiming every mismatch is a wrong version.

## Validation

- `python -m pytest tests/test_check_dependencies.py tests/test_machine_gcode_generator.py -q` -> 6 passed.
- `python scripts/quality_gate.py` -> OK.
