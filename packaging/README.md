# Packaging

This folder contains build-facing files only. Runtime application code remains in
`src/laserprog_studio`; developer and migration material remains in `docs/` and
`tests/`.

## Windows executable direction

The intended production build path is PyInstaller from the repository root:

```bat
py -3.12 -m pip install -r requirements.txt
py -3.12 -m pip install pyinstaller
py -3.12 -m PyInstaller packaging\pyinstaller\laserprog_studio.spec --clean --noconfirm
```

Before building, run:

```bat
py -3.12 scripts\quality_gate.py
```

The spec intentionally excludes `tests`, `docs`, `examples`, and runtime logs
from the executable payload. Assets and JSON presets used by the application are
included explicitly.
