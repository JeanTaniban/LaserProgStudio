# Cleanup report

This cleaned version applies the following changes:

- Translated remaining French user-facing text, comments, and documentation to English.
- Removed accents and non-ASCII characters from text files.
- Reorganized the project into `src/`, `scripts/`, `examples/`, `docs/`, `diagnostics/`, and `exports/`.
- Renamed French folders and files to English names.
- Removed generated Python cache folders and old generated logs from the deliverable.
- Added a clean Python module entrypoint: `python -m laserprog_studio.main`.
- Added a root `run.py` convenience launcher.
- Updated launch scripts to use the new `src` layout.
- Updated sample paths from `Documents/boite.3mf` and `Documents/pieces_a_plat*` to `examples/box.3mf` and `examples/layflat_parts*`.

Compatibility note: some internal imports intentionally remain simple (`work_model`, `tools.*`, and `laser_3mf_gui`) to preserve the original behavior without a full package refactor. The application bootstrap configures `sys.path` so those imports continue to work.

## Windows launch scripts

The project now includes root-level BAT wrappers:

- `INSTALL_DEPENDENCIES.bat`
- `RUN_LASERPROG_STUDIO.bat`

The real implementation lives in `scripts/`:

- `scripts/install_dependencies.bat`
- `scripts/run_laserprog_studio.bat`
- `scripts/check_dependencies.py`

Older script names are kept as compatibility wrappers:

- `scripts/install_dependencies_stable_qt_pyvista.bat`
- `scripts/run_laserprog_studio_v18.bat`

The installer uses the selected central Python directly, creates no central Python environment, prefers Python 3.12, checks `requirements.txt`, installs only when packages are missing or pinned versions do not match, and writes logs to `diagnostics/setup_dependencies.log`.
