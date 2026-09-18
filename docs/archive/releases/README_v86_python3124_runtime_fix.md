# LaserProg v86 - Python 3.12.4 runtime selection fix

This package keeps the v86 application code and pinned runtime package versions,
but fixes the Windows setup/launcher Python selection.

## Why

The previous installer could fall back to `py -3`, which selects the newest
installed Python 3.x. On a machine with Python 3.14 installed, dependencies were
installed into Python 3.14 even though LaserProg's tested Qt/PyVista/VTK stack
must run on Python 3.12.4.

## Fixed

- `INSTALL_DEPENDENCIES.bat` now searches only for Python 3.12.4 exactly.
- `RUN_LASERPROG_STUDIO.bat` now searches only for Python 3.12.4 exactly.
- The scripts try:
  - `py -3.12`
  - `python`
  - `%LocalAppData%\Programs\Python\Python312\python.exe`
  - `%ProgramFiles%\Python312\python.exe`
  - `%ProgramFiles(x86)%\Python312\python.exe`
  - `py -3`, but only if it is exactly 3.12.4
- `scripts/check_dependencies.py` now fails if the selected Python is not exactly 3.12.4.
- Dependency install uses `--force-reinstall` when the exact pins do not match.

## Required runtime

```text
Python==3.12.4
numpy==2.0.1
pillow==10.4.0
shapely==2.1.2
PySide6==6.8.3
pyvista==0.46.5
pyvistaqt==0.11.4
vtk==9.4.2
pyserial==3.5
```

`manifold3d` remains presence-only because it was not pinned in the working v73 runtime.

## If Python 3.12.4 is installed but not found

Run this in PowerShell and send the output:

```powershell
py -0p
```
