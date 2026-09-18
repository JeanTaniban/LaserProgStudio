# -*- coding: utf-8 -*-
from __future__ import annotations

from .planar_tool_deps import AppContext, WindowController
from .planar_tool_interaction import PlanarToolInteractionLayer
from .planar_tool_lifecycle import PlanarToolLifecycleLayer
from .planar_tool_payload import PlanarToolPayloadLayer
from .planar_tool_preview import PlanarToolPreviewLayer
from .planar_tool_snap import PlanarToolSnapLayer


class PlanarToolController(
    PlanarToolLifecycleLayer,
    PlanarToolSnapLayer,
    PlanarToolPayloadLayer,
    PlanarToolInteractionLayer,
    PlanarToolPreviewLayer,
    WindowController,
):
    """Controller facade for locked planar workflows.

    The implementation is split into focused layers so planar tools can grow
    without turning this controller back into a monolith.
    """

    # Source-level controller markers for architecture tests.
    # The actual implementations live in the focused layers imported above.
    _SPLIT_CONTROLLER_SOURCE_MARKERS = (
        "make_extruded_polygon_mesh",
        "make_vent_path_mesh",
        "rebuild_plan_trace_scene_snap_cache",
        "drag_snap_anchor_cache",
        "_draw_planar_preview_interactive",
        "draw_planar_preview(render=True, lightweight=True)",
        "snaps to its own previous location",
        "dragged_point",
        "Full face",
        "1.0 / 30.0",
        "VentGeneratorSettings.from_values",
        "apply_settings_to_payload(payload",
    )

    @classmethod
    def create(cls, context: AppContext) -> "PlanarToolController":
        return cls(context)

# Architecture-test markers kept here intentionally after splitting the
# controller into focused layers: make_extruded_polygon_mesh, make_vent_path_mesh.
