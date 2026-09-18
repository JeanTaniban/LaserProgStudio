# -*- coding: utf-8 -*-
"""Historical aggregate for transform and gizmo controller mixins."""
from __future__ import annotations

from laserprog_studio.controllers.gizmo_highlight import GizmoHighlightLayer
from laserprog_studio.controllers.gizmo_overlay import GizmoOverlayLayer
from laserprog_studio.controllers.gizmo_view import GizmoViewLayer
from laserprog_studio.controllers.transform_drag import TransformDragLayer
from laserprog_studio.controllers.transform_geometry import TransformGeometryLayer
from laserprog_studio.controllers.transform_inspector import TransformInspectorLayer
from laserprog_studio.controllers.transform_math import TransformMathLayer


class GizmoTransformLayer(
    GizmoOverlayLayer,
    TransformGeometryLayer,
    TransformMathLayer,
    TransformDragLayer,
    GizmoHighlightLayer,
    GizmoViewLayer,
    TransformInspectorLayer,
):
    """Composition aggregate; new code should use the focused layers."""

    pass


__all__ = ["GizmoTransformLayer"]
