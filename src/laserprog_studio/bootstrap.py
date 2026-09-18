# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StudioPaths:
    root: Path
    src_dir: Path
    toolbox_dir: Path
    generator_2d_dir: Path
    examples_dir: Path
    diagnostics_dir: Path
    exports_dir: Path
    log_path: Path


def compute_paths() -> StudioPaths:
    # .../src/laserprog_studio/bootstrap.py -> parents[2] = project root
    root = Path(__file__).resolve().parents[2]
    src_dir = root / "src"
    studio_dir = src_dir / "laserprog_studio"
    toolbox_dir = studio_dir / "fabrication"
    generator_2d_dir = studio_dir / "engraving"
    examples_dir = root / "examples"
    diagnostics_dir = root / "diagnostics"
    exports_dir = root / "exports"
    log_path = diagnostics_dir / "laserprog_studio_v18.log"
    return StudioPaths(
        root=root,
        src_dir=src_dir,
        toolbox_dir=toolbox_dir,
        generator_2d_dir=generator_2d_dir,
        examples_dir=examples_dir,
        diagnostics_dir=diagnostics_dir,
        exports_dir=exports_dir,
        log_path=log_path,
    )


def configure_process_environment() -> None:
    # Safe AMD/VTK profile.
    os.environ.setdefault("QT_OPENGL", "desktop")
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "false")
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")


def configure_sys_path(paths: StudioPaths) -> None:
    # Only the source root is needed. The retired top-level import shims
    # (`work_model`, `tools.*`, `laser_3mf_gui`, etc.) were removed in pass 4.
    sp = str(paths.src_dir)
    if sp not in sys.path:
        sys.path.insert(0, sp)


def ensure_runtime_dirs(paths: StudioPaths) -> None:
    paths.diagnostics_dir.mkdir(exist_ok=True)
    paths.exports_dir.mkdir(exist_ok=True)


def bootstrap() -> StudioPaths:
    """Prepare process environment + sys.path and return studio paths."""
    paths = compute_paths()
    configure_process_environment()
    ensure_runtime_dirs(paths)
    configure_sys_path(paths)
    return paths
