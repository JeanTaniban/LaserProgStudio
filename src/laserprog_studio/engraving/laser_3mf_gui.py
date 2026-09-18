#!/usr/bin/env python3
"""Stable entry point for the 3MF laser image generator.

The implementation is split into focused modules:
- laser_3mf_core.py: 3MF parsing, geometry, rendering helpers
- image_panel.py: zoomable image viewer
- laser_3mf_app_*.py: Tk application mixins
"""
from __future__ import annotations

from .laser_3mf_core import *  # type: ignore  # noqa: F401,F403
from .image_panel import ImagePanel  # type: ignore  # noqa: F401
from .laser_3mf_app_lifecycle import Laser3MFAppLifecycleLayer  # type: ignore
from .laser_3mf_app_ui import Laser3MFAppUILayer  # type: ignore
from .laser_3mf_app_presets import Laser3MFAppPresetsLayer  # type: ignore
from .laser_3mf_app_render_export import Laser3MFAppRenderExportLayer  # type: ignore


class Laser3MFSingleWindowApp(
    Laser3MFAppLifecycleLayer,
    Laser3MFAppUILayer,
    Laser3MFAppPresetsLayer,
    Laser3MFAppRenderExportLayer,
):
    pass


def main():
    Laser3MFSingleWindowApp().run()


if __name__ == "__main__":
    main()
