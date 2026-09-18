# -*- coding: utf-8 -*-
from __future__ import annotations

from .display_modes import DISPLAY_MODES, DisplayModeSpec, get_display_mode
from .handles import (
    ArrowHandleDimensions,
    SPLIT_HANDLE_SHAFT_RADIUS_RATIO,
    SPLIT_HANDLE_TIP_RADIUS_RATIO,
    make_arrow_handle_mesh,
    split_handle_dimensions_from_gizmo_length,
)
from .materials import ActorStyle, actor_style_for_mesh, apply_actor_style
from .scene_renderer import SceneRenderer

__all__ = [
    "SceneRenderer",
    "DISPLAY_MODES",
    "DisplayModeSpec",
    "get_display_mode",
    "ArrowHandleDimensions",
    "SPLIT_HANDLE_SHAFT_RADIUS_RATIO",
    "SPLIT_HANDLE_TIP_RADIUS_RATIO",
    "make_arrow_handle_mesh",
    "split_handle_dimensions_from_gizmo_length",
    "ActorStyle",
    "actor_style_for_mesh",
    "apply_actor_style",
]

from .render_scheduler import (
    CentralRenderScheduler,
    install_central_render_scheduler,
    request_render_for,
    render_now_for,
)

__all__ = [name for name in globals() if not name.startswith("_")]
