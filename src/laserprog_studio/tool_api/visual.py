"""Viewport and UI helper namespaces for creator tools."""
from __future__ import annotations

from laserprog_studio.tool_core.gizmos import GizmoHandle, GizmoManipulator, GizmoManager
from laserprog_studio.tool_core.inspector import AutoPreview, AutoPreviewConfig, InspectorActionEvent, InspectorFieldKind, InspectorFieldState, InspectorManager, InspectorPanel, InspectorSection
from laserprog_studio.tool_core.overlay import (
    OverlayActionSpec,
    OverlayButtonStyle,
    OverlayFieldSpec,
    OverlayModeSpec,
    OverlayToolbarSectionSpec,
    OverlayWindowSpec,
    ToolButtonSpec,
    ToolPanelSpec,
    build_command_deck_window,
    build_mode_toolbar_window,
    build_sectioned_toolbar_window,
)
from laserprog_studio.tool_core.preview import PreviewItem, PreviewKind, PreviewManager, TextLabel
from laserprog_studio.tool_core.rendering import RenderScheduler, RenderStats, ViewportAdapter

from . import gizmos, inspector, projected_drawing, styles, ui_catalog
from .status import StatusManager, StatusMessage
from laserprog_studio.tool_core.app_services import ViewFacade

__all__ = [
    "GizmoHandle",
    "GizmoManipulator",
    "GizmoManager",
    "AutoPreview",
    "AutoPreviewConfig",
    "InspectorActionEvent",
    "InspectorFieldKind",
    "InspectorFieldState",
    "InspectorManager",
    "InspectorPanel",
    "InspectorSection",
    "OverlayActionSpec",
    "OverlayButtonStyle",
    "OverlayFieldSpec",
    "OverlayModeSpec",
    "OverlayToolbarSectionSpec",
    "OverlayWindowSpec",
    "PreviewItem",
    "PreviewKind",
    "PreviewManager",
    "projected_drawing",
    "RenderScheduler",
    "RenderStats",
    "StatusManager",
    "StatusMessage",
    "ToolButtonSpec",
    "ToolPanelSpec",
    "styles",
    "ui_catalog",
    "TextLabel",
    "ViewportAdapter",
    "ViewFacade",
    "build_command_deck_window",
    "build_mode_toolbar_window",
    "build_sectioned_toolbar_window",
    "gizmos",
    "inspector",
]
