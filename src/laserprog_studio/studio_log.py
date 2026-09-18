# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
from typing import TextIO

_log_file: TextIO | None = None


def init_log_file(file: TextIO | None) -> None:
    global _log_file
    _log_file = file


def log(msg: str = "") -> None:
    text = str(msg)
    print(text)
    try:
        if _log_file is not None:
            _log_file.write(text + "\n")
            _log_file.flush()
    except Exception:
        pass


def log_section(title: str) -> None:
    log("\n" + "=" * 96)
    log(title)
    log("=" * 96)


def log_exception(prefix: str) -> None:
    log(f"[ERREUR] {prefix}")
    log(traceback.format_exc())


def import_report() -> None:
    # Deferred imports: we want ENV vars set first.
    log_section("IMPORTS / VERSIONS")
    for name in ["PySide6", "pyvista", "pyvistaqt", "vtk", "numpy", "shapely", "PIL"]:
        try:
            mod = __import__(name)
            version = getattr(mod, "__version__", None)
            if name == "vtk":
                version = mod.vtkVersion.GetVTKVersion()
            log(f"{name}: OK version={version}")
        except Exception:
            log_exception(f"import {name}")
    try:
        import pyvista as pv

        log(
            "pyvista theme before: "
            f"smooth={pv.global_theme.smooth_shading} "
            f"multi={getattr(pv.global_theme, 'multi_samples', '?')} "
            f"backend={pv.global_theme.jupyter_backend}"
        )
    except Exception:
        pass
