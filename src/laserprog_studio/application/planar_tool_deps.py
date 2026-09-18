# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math
import time
from typing import Any

from ..app_context import AppContext
from ..planar_tools import (
    FixedPlanarView,
    LockedPlaneSpec,
    PlanTraceAddKind,
    PlanarEditMode,
    PlanarPointerResult,
    PlanarPolygonDraft,
    PlanarToolConfig,
    VentPathDraft,
    VentFlareSide,
    VentSectionKind,
    clamp_world_point_to_plane,
    compile_planar_snap_cache,
    make_extruded_polygon_mesh,
    make_ray,
    intersect_ray_with_locked_plane,
    make_vent_path_mesh,
    nearest_locked_view_from_camera,
    nearest_locked_view_from_forward,
    plane_from_first_hit,
    plane_to_world,
    resolve_pointer_on_plane,
    world_to_plane,
)
from ..studio_log import log_exception
from ..tooling.ids import TOOL_PLAN_TRACE, TOOL_VENT_GENERATOR
from .action_controller import WindowController
from .planar_preview_service import PlanarPreviewService
from .planar_report_service import PlanarReportService
from .planar_pick_service import PlanarPickService


def _qmessagebox():
    from PySide6.QtWidgets import QMessageBox

    return QMessageBox

def _qtimer():
    from PySide6.QtCore import QTimer

    return QTimer
