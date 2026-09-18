# -*- coding: utf-8 -*-
from __future__ import annotations

from .state_bridge import StateBridge
from .interaction import InteractionLayer
from .selection_context_menu import SelectionContextMenuLayer
from .preview_controller import PreviewControllerLayer
from .scene import SceneStateLayer
from .scene_tabs import SceneTabsLayer
from .tool_selection_policy import ToolSelectionPolicyLayer
from .layout_restore import LayoutRestoreLayer
from .tool_lifecycle import ToolLifecycleLayer
from .split_plane_tool import SplitPlaneToolLayer
from .tool_previews import ToolPreviewLayer
from .camera import CameraNavigationLayer
from .gizmo_overlay import GizmoOverlayLayer
from .transform_geometry import TransformGeometryLayer
from .transform_math import TransformMathLayer
from .transform_drag import TransformDragLayer
from .gizmo_highlight import GizmoHighlightLayer
from .material_tool import MaterialToolLayer
from .texture_projection_tool import TextureProjectionToolLayer
from .image_mask_import import ImageMaskImportLayer
from .gizmo_view import GizmoViewLayer
from .transform_inspector import TransformInspectorLayer
from .boolean_actions import BooleanActionsLayer
from .clipboard_actions import ClipboardActionsLayer
from .scene_edit_actions import SceneEditActionsLayer
from .history_actions import HistoryActionsLayer
from .exporting import ExportingLayer
from .render_output import RenderOutputLayer
from .machine import MachineLayer


class StudioControllers(
    StateBridge,
    InteractionLayer,
    SelectionContextMenuLayer,
    PreviewControllerLayer,
    SceneTabsLayer,
    SceneStateLayer,
    ToolSelectionPolicyLayer,
    LayoutRestoreLayer,
    ToolLifecycleLayer,
    SplitPlaneToolLayer,
    ToolPreviewLayer,
    CameraNavigationLayer,
    GizmoOverlayLayer,
    TransformGeometryLayer,
    TransformMathLayer,
    TransformDragLayer,
    GizmoHighlightLayer,
    MaterialToolLayer,
    TextureProjectionToolLayer,
    ImageMaskImportLayer,
    GizmoViewLayer,
    TransformInspectorLayer,
    BooleanActionsLayer,
    ClipboardActionsLayer,
    SceneEditActionsLayer,
    HistoryActionsLayer,
    ExportingLayer,
    RenderOutputLayer,
    MachineLayer,
):
    """Composite behavior layer for LaserProg Studio's main window."""

    pass
