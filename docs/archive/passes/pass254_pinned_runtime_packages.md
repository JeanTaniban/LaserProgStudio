# Pass 254 — Pinned runtime packages

## Goal

Restore the known-good LaserProg runtime package versions after confirming that
newer PySide6 / PyVista / VTK / NumPy combinations can break visible overlays.

## Changes

- `requirements.txt` uses exact pins again for the tested runtime stack:
  - `numpy==2.0.1`
  - `pillow==10.4.0`
  - `shapely==2.1.2`
  - `PySide6==6.8.3`
  - `pyvista==0.46.5`
  - `pyvistaqt==0.11.4`
  - `vtk==9.4.2`
  - `pyserial==3.5`
- `scripts/check_dependencies.py` treats `==` as a strict exact version.
- Launcher wording now reports missing or non-matching pinned runtime versions.

## Notes

`manifold3d` remains unpinned because the known-good v73 requirements did not
include a fixed version for it.
