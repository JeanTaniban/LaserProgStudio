# -*- coding: utf-8 -*-
"""Static verification for the LaserProg Studio main-window refactor.

This script intentionally avoids importing Qt/PyVista. It parses source files
with `ast`, so it can run in a lightweight development or CI environment.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .ast_tools import class_methods as _class_methods
from .paths import EXPECTED_WINDOW_METHODS, MIN_EXTRACTED_METHODS, REQUIRED_MODULES, ROOT, STUDIO, WINDOW


def main() -> int:
    missing = [path for path in REQUIRED_MODULES if not path.exists()]
    if missing:
        raise SystemExit("Missing refactor modules: " + ", ".join(str(p) for p in missing))

    tree = ast.parse(WINDOW.read_text(encoding="utf-8"), filename=str(WINDOW))
    main_classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LaserProgStudioV18"]
    if len(main_classes) != 1:
        raise SystemExit("window.py must define exactly one LaserProgStudioV18 class")
    base_names = [getattr(base, "id", getattr(base, "attr", "")) for base in main_classes[0].bases]
    if not base_names or base_names[0] != "QMainWindow":
        raise SystemExit(f"LaserProgStudioV18 must inherit QMainWindow first, got bases={base_names}")
    for required_base in ("UIPanelsLayer", "StudioControllers"):
        if required_base not in base_names:
            raise SystemExit(f"LaserProgStudioV18 is missing required base {required_base}")

    window_methods = set(_class_methods(WINDOW))
    if window_methods != EXPECTED_WINDOW_METHODS:
        raise SystemExit(f"window.py should define constructor plus Qt event bridges {EXPECTED_WINDOW_METHODS}, got {sorted(window_methods)}")

    # Important regression guard: with QMainWindow first in the MRO, Qt virtual
    # methods in later controller layers are shadowed unless LaserProgStudioV18 exposes
    # explicit bridge methods. Viewport selection and transform gizmos depend on
    # these bridges.
    source = WINDOW.read_text(encoding="utf-8")
    required_bridge_targets = {
        "eventFilter": "StudioControllers.eventFilter",
        "keyPressEvent": "StudioControllers.keyPressEvent",
        "keyReleaseEvent": "StudioControllers.keyReleaseEvent",
        "closeEvent": "StudioControllers.closeEvent",
        "set_transform_mode": "UIPanelsLayer.set_transform_mode",
        "update_gizmo": "StudioControllers.update_gizmo",
    }
    for method, target in required_bridge_targets.items():
        if target not in source:
            raise SystemExit(f"Missing Qt virtual bridge for {method}: expected call to {target}")
    for method, target in {
        "request_render": "request_render_for",
        "render_now": "render_now_for",
        "flush_render": "self.render_now",
    }.items():
        if f"def {method}" not in source or target not in source:
            raise SystemExit(f"Missing central render bridge for {method}: expected {target}")

    interaction_lines = (STUDIO / "controllers" / "interaction.py").read_text(encoding="utf-8").splitlines()
    if len(interaction_lines) > 1300:
        raise SystemExit(f"interaction.py has grown beyond the current cleanup baseline, got {len(interaction_lines)} lines")
    scene_lines = (STUDIO / "controllers" / "scene.py").read_text(encoding="utf-8").splitlines()
    if len(scene_lines) > 560:
        raise SystemExit(f"scene.py has grown beyond the current cleanup baseline, got {len(scene_lines)} lines")
    tool_lifecycle_methods = set(_class_methods(STUDIO / "controllers" / "tool_lifecycle.py"))
    tool_policy_methods = set(_class_methods(STUDIO / "controllers" / "tool_selection_policy.py"))
    layout_restore_methods = set(_class_methods(STUDIO / "controllers" / "layout_restore.py"))
    layout_controller_methods = set(_class_methods(STUDIO / "application" / "layout_controller.py"))
    tool_lifecycle_controller_methods = set(_class_methods(STUDIO / "application" / "tool_lifecycle_controller.py"))
    for method in ("open_tool", "close_active_tool", "apply_preview_and_close_tool", "discard_preview_and_close_tool"):
        if method not in tool_lifecycle_methods:
            raise SystemExit(f"ToolLifecycleLayer facade must expose {method}")
        if method not in tool_lifecycle_controller_methods:
            raise SystemExit(f"ToolLifecycleController must own {method}")
    tool_lifecycle_facade = (STUDIO / "controllers" / "tool_lifecycle.py").read_text(encoding="utf-8")
    if len(tool_lifecycle_facade.splitlines()) > 90 or "ToolLifecycleController" not in tool_lifecycle_facade:
        raise SystemExit("ToolLifecycleLayer should stay a thin facade over ToolLifecycleController")
    for method in ("_tool_meets_selection_policy", "_tool_selection_error_message", "_apply_tool_selection_policy"):
        if method not in tool_policy_methods:
            raise SystemExit(f"ToolSelectionPolicyLayer must own {method}")
        if method in tool_lifecycle_methods:
            raise SystemExit(f"ToolLifecycleLayer must delegate selection policy method {method}")
    for method in ("_remember_inspector_mode_before_tool_open", "_restore_inspector_mode_after_tool_close", "_ensure_inspector_open"):
        if method not in layout_restore_methods:
            raise SystemExit(f"LayoutRestoreLayer facade must expose {method}")
        if method in tool_lifecycle_methods:
            raise SystemExit(f"ToolLifecycleLayer must delegate layout restore method {method}")
    for method in ("remember_before_tool_open", "restore_after_tool_close", "ensure_inspector_open", "note_user_splitter_drag"):
        if method not in layout_controller_methods:
            raise SystemExit(f"LayoutController must own inspector layout workflow method {method}")
    preview_facade_methods = set(_class_methods(STUDIO / "controllers" / "preview_controller.py"))
    preview_controller_methods = set(_class_methods(STUDIO / "application" / "preview_controller.py"))
    for method in ("has_preview", "set_preview_meshes", "set_preview_result", "commit_preview_to_model", "discard_preview_only"):
        if method not in preview_facade_methods:
            raise SystemExit(f"PreviewControllerLayer facade must expose {method}")
    for method in ("has_preview", "set_meshes", "set_result", "commit_to_model", "discard_only"):
        if method not in preview_controller_methods:
            raise SystemExit(f"PreviewController must own preview workflow method {method}")
    scene_methods = set(_class_methods(STUDIO / "controllers" / "scene.py"))
    for method in ("has_preview", "set_preview_meshes"):
        if method in scene_methods:
            raise SystemExit(f"SceneStateLayer should not own preview lifecycle method {method}")
    if "discard_preview_only" in tool_lifecycle_methods:
        raise SystemExit("ToolLifecycleLayer should delegate discard_preview_only to PreviewControllerLayer")
    tool_preview_facade = (STUDIO / "controllers" / "tool_previews.py").read_text(encoding="utf-8")
    if len(tool_preview_facade.splitlines()) > 220 or "ToolPreviewController" not in tool_preview_facade:
        raise SystemExit("ToolPreviewLayer should stay a thin facade over ToolPreviewController")

    tool_panels_source = (STUDIO / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    tool_panel_factory_source = (STUDIO / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    tool_panel_catalog_source = (STUDIO / "ui" / "tool_panel_catalog.py").read_text(encoding="utf-8")
    if len(tool_panels_source.splitlines()) > 380 or "ToolPanelFactory" not in tool_panels_source:
        raise SystemExit("UIToolPanelsLayer should stay a shell over ToolPanelFactory")
    for snippet in ("class ToolPanelFactory", "def build_stack", "def build_panel", "panel_joint_tool", "panel_texture_projection_tool"):
        if snippet not in tool_panel_factory_source:
            raise SystemExit(f"ToolPanelFactory is missing expected panel builder snippet: {snippet}")
    for snippet in ("class ToolPanelSpec", "TOOL_PANEL_SPECS", "TOOL_TEXTURE_PROJECTION", "TOOL_MOD_REPAIR"):
        if snippet not in tool_panel_catalog_source:
            raise SystemExit(f"tool_panel_catalog.py is missing declarative panel catalog snippet: {snippet}")
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    context_source = (STUDIO / "app_context.py").read_text(encoding="utf-8")
    if "class AppContext" not in context_source or "def from_window" not in context_source or "def mesh_store" not in context_source:
        raise SystemExit("app_context.py must expose AppContext.from_window and a dynamic mesh_store property")
    operation_result_source = (STUDIO / "geometry_ops" / "result.py").read_text(encoding="utf-8")
    for snippet in ("class OperationResult", "def ok", "def success", "def failure"):
        if snippet not in operation_result_source:
            raise SystemExit(f"geometry_ops.result must expose a standard operation result contract: missing {snippet}")
    if "def initialize_runtime_state" not in runtime_source:
        raise SystemExit("runtime_state.py must expose initialize_runtime_state")
    if "initialize_runtime_state(self)" not in source:
        raise SystemExit("window.py must delegate mutable state setup to initialize_runtime_state(self)")
    vent_model_source = (STUDIO / "planar_tools" / "vent_model.py").read_text(encoding="utf-8")
    vent_constraints_source = (STUDIO / "planar_tools" / "vent_constraints.py").read_text(encoding="utf-8")
    path_sampling_source = (STUDIO / "planar_tools" / "path_sampling.py").read_text(encoding="utf-8")
    tool_panel_factory_source_for_vent = (STUDIO / "tooling" / "vent_generator" / "panel.py").read_text(encoding="utf-8")
    for snippet in ("class VentGeometryMetrics", "def metrics", "target_length"):
        if snippet not in vent_model_source:
            raise SystemExit(f"VentPathDraft is missing polished metrics contract snippet: {snippet}")
    for snippet in ("validate_vent_waypoints_and_curve", "adjacency_window"):
        if snippet not in vent_constraints_source:
            raise SystemExit(f"vent_constraints.py is missing combined path/curve validation snippet: {snippet}")
    for snippet in ("def smooth_path_points", "non-overshooting rounded corners", "def polyline_length"):
        if snippet not in path_sampling_source:
            raise SystemExit(f"path_sampling.py is missing shared vent sampling snippet: {snippet}")
    for snippet in ("target_length", "Target length"):
        if snippet not in tool_panel_factory_source_for_vent:
            raise SystemExit(f"Vent Creator panel is missing target length UI snippet: {snippet}")

    for state_attr in ("selection_state", "transform_state", "tool_state", "preview_state", "ui_layout_state", "render_state", "scene_renderer", "clipboard_state", "app_context", "context", "layout_controller", "tool_lifecycle_controller", "texture_projection_controller", "texture_gizmo_controller", "texture_gizmo_state", "planar_tool_state", "planar_tool_controller"):
        if state_attr not in runtime_source:
            raise SystemExit(f"runtime_state.py must initialize structured state attr {state_attr}")

    texture_tool_facade = (STUDIO / "controllers" / "texture_projection_tool.py").read_text(encoding="utf-8")
    texture_gizmo_source = (STUDIO / "application" / "texture_gizmo_controller.py").read_text(encoding="utf-8")
    texture_gizmo_state_source = (STUDIO / "state" / "texture_gizmo_state.py").read_text(encoding="utf-8")
    if len(texture_tool_facade.splitlines()) > 240 or "TextureGizmoController" not in texture_tool_facade:
        raise SystemExit("TextureProjectionToolLayer should stay a thin facade over texture projection/gizmo controllers")
    for snippet in ("class TextureGizmoController", "def update_texture_rotation_gizmo", "def _start_texture_rotation_gizmo_drag", "def _finish_texture_rotation_gizmo_drag"):
        if snippet not in texture_gizmo_source:
            raise SystemExit(f"TextureGizmoController is missing expected gizmo workflow snippet: {snippet}")
    if len(texture_gizmo_source.splitlines()) > 230:
        raise SystemExit("TextureGizmoController should stay a thin facade over focused texture gizmo services")
    texture_gizmo_service_checks = {
        "texture_gizmo_target_service.py": ("class TextureGizmoTargetService", "def _texture_rotation_target", "def _pick_texture_rotation_gizmo_from_qt_pos"),
        "texture_gizmo_live_update_service.py": ("class TextureGizmoLiveUpdateService", "def _texture_projection_live_update_current_target"),
        "texture_gizmo_event_service.py": ("class TextureGizmoEventService", "def _install_texture_rotation_vtk_observers", "app.installEventFilter(self.owner)", "_qtimer()(self.owner)"),
        "texture_gizmo_render_service.py": ("class TextureGizmoRenderService", "def update_texture_rotation_gizmo"),
        "texture_gizmo_drag_service.py": ("class TextureGizmoDragService", "def _start_texture_rotation_gizmo_drag", "def _finish_texture_rotation_gizmo_drag"),
    }
    for module_name, snippets in texture_gizmo_service_checks.items():
        module_source = (STUDIO / "application" / module_name).read_text(encoding="utf-8")
        if len(module_source.splitlines()) > 520:
            raise SystemExit(f"{module_name} should stay focused after the texture gizmo split")
        if "from .._window_deps import *" in module_source:
            raise SystemExit(f"{module_name} must not import the old _window_deps bundle")
        for snippet in snippets:
            if snippet not in module_source:
                raise SystemExit(f"{module_name} is missing expected snippet: {snippet}")
    if "from .._window_deps import *" in texture_gizmo_source:
        raise SystemExit("TextureGizmoController must not import the old _window_deps bundle")
    for snippet in ("class TextureGizmoState", "def apply_to_window", "_texture_rotation_gizmo_pressed", "_texture_rotation_gizmo_vtk_observer_ids"):
        if snippet not in texture_gizmo_state_source:
            raise SystemExit(f"TextureGizmoState is missing expected window state mapping: {snippet}")

    texture_projection_facade_source = (STUDIO / "geometry_ops" / "texture_projection.py").read_text(encoding="utf-8")
    if len(texture_projection_facade_source.splitlines()) > 100 or "Stable aggregate import" not in texture_projection_facade_source:
        raise SystemExit("geometry_ops.texture_projection should stay a small forwarding facade after Pass 12")
    texture_geometry_modules = {
        "texture_projection_types.py": ("class TextureProjectionParams", "@dataclass"),
        "texture_projection_vector.py": ("def _uv_from_plane_coords", "def _apply_uv_transform"),
        "texture_projection_faces.py": ("def _selected_face_ids_for_anchor", "def _store_texture_edit_frame"),
        "texture_projection_uv.py": ("def compute_projected_uvs", "def _uvs_from_projected_coords"),
        "texture_projection_decal.py": ("def _make_anchor_texture_decal", "def _clear_mesh_texture_metadata"),
        "texture_projection_operations.py": ("def apply_texture_projection_to_mesh", "def clear_texture_projection"),
    }
    for module_name, snippets in texture_geometry_modules.items():
        module_source = (STUDIO / "geometry_ops" / module_name).read_text(encoding="utf-8")
        if len(module_source.splitlines()) > 400:
            raise SystemExit(f"{module_name} should stay focused after the texture projection split")
        for snippet in snippets:
            if snippet not in module_source:
                raise SystemExit(f"{module_name} is missing expected snippet: {snippet}")

    # Pass 13: clean private texture imports and prepare the locked-plane tool foundation.
    for module_name in ("texture_gizmo_target_service.py", "texture_gizmo_live_update_service.py"):
        module_source = (STUDIO / "application" / module_name).read_text(encoding="utf-8")
        if "from laserprog_studio.geometry_ops.texture_projection import _" in module_source:
            raise SystemExit(f"{module_name} must import focused texture modules, not private helpers from the facade")
    planar_modules = {
        "contracts.py": ("class PlanarEditMode", "class LockedPlaneSpec", "class VentSectionKind"),
        "orientation.py": ("def nearest_locked_view_from_forward", "def plane_from_first_hit", "def plane_to_world"),
        "draft_model.py": ("class PlanarPolygonDraft", "def close_polygon", "def is_ready_for_extrusion", "def validation_result"),
        "vent_model.py": ("class VentPathDraft", "def estimated_centerline_length", "class VentSectionSpec", "def validation_result"),
        "validation.py": ("class PlanarValidationResult", "def validate_polygon_for_extrusion", "def validate_vent_path", "def polygon_self_intersections"),
    }
    for module_name, snippets in planar_modules.items():
        module_source = (STUDIO / "planar_tools" / module_name).read_text(encoding="utf-8")
        line_limit = 320 if module_name == "vent_model.py" else 260
        if len(module_source.splitlines()) > line_limit:
            raise SystemExit(f"planar_tools/{module_name} should stay focused")
        for snippet in snippets:
            if snippet not in module_source:
                raise SystemExit(f"planar_tools/{module_name} is missing expected contract snippet: {snippet}")
    planar_controller_source = "\n".join(
        (STUDIO / "application" / name).read_text(encoding="utf-8")
        for name in (
            "planar_tool_controller.py",
            "planar_tool_lifecycle.py",
            "planar_tool_snap.py",
            "planar_tool_payload.py",
            "planar_tool_interaction.py",
            "planar_tool_preview.py",
        )
    )
    for snippet in ("class PlanarToolController", "def begin_locked_planar_tool", "def end_locked_planar_tool", "nearest_locked_view_from_forward"):
        if snippet not in planar_controller_source:
            raise SystemExit(f"PlanarToolController split is missing expected snippet: {snippet}")
    planar_blueprints_source = (STUDIO / "tooling" / "planar_tool_blueprints.py").read_text(encoding="utf-8")
    for snippet in ("PLAN_TRACE_BLUEPRINT", "VENT_GENERATOR_BLUEPRINT", "default_visible=True", "expected_panel_builder"):
        if snippet not in planar_blueprints_source:
            raise SystemExit(f"Planar tool reference blueprints missing snippet: {snippet}")

    scene_renderer_source = (STUDIO / "rendering" / "scene_renderer.py").read_text(encoding="utf-8")
    for snippet in ("class SceneRenderer", "def set_display_mode", "def clear_tool_overlays", "def refresh_transform_gizmo"):
        if snippet not in scene_renderer_source:
            raise SystemExit(f"SceneRenderer must expose a future rendering facade: missing {snippet}")

    state_bridge_source = (STUDIO / "controllers" / "state_bridge.py").read_text(encoding="utf-8")
    for snippet in ("class StateBridge", "def selected_indices", "def active_tool", "def transform_mode", "def scale_ratio_locked", "def _copy_buffer_meshes"):
        if snippet not in state_bridge_source:
            raise SystemExit(f"StateBridge must keep window-style attributes synchronized with state dataclasses: missing {snippet}")

    tooling_base_source = (STUDIO / "tooling" / "base.py").read_text(encoding="utf-8")
    for snippet in ("parameters: tuple[ParameterSpec, ...]", "def default_parameters", "def validate_parameters"):
        if snippet not in tooling_base_source:
            raise SystemExit(f"ToolSpec must expose future parameter contracts: missing {snippet}")
    parameter_factory_source = (STUDIO / "parameters" / "panel_factory.py").read_text(encoding="utf-8")
    for snippet in ("class ParameterPanelFactory", "def create_panel", "from PySide6.QtCore import Qt", "return ParameterPanel"):
        if snippet not in parameter_factory_source:
            raise SystemExit(f"ParameterPanelFactory is missing expected lazy Qt form-builder snippet: {snippet}")

    registry_source = (STUDIO / "tooling" / "registry.py").read_text(encoding="utf-8")
    for tool_id in ("TOOL_PRIMITIVE", "TOOL_BOX", "TOOL_LAYFLAT", "TOOL_JOINT", "TOOL_ENGRAVING", "TOOL_MOD_SPLIT"):
        if tool_id not in registry_source:
            raise SystemExit(f"Tool registry is missing {tool_id}")
    lifecycle_source = (STUDIO / "application" / "tool_lifecycle_controller.py").read_text(encoding="utf-8")
    policy_source = (STUDIO / "controllers" / "tool_selection_policy.py").read_text(encoding="utf-8")
    for snippet in ("get_tool_spec", "iter_studio_tools", "_invoke_tool_hook", "_tool_meets_selection_policy"):
        if snippet not in lifecycle_source:
            raise SystemExit(f"ToolLifecycleController must use registry-driven helper {snippet}")
    if "def _apply_tool_selection_policy" not in policy_source:
        raise SystemExit("ToolSelectionPolicyLayer must own _apply_tool_selection_policy")

    # Primitives create new objects, Lay flat can arrange the whole scene, and
    # Engraving roles can paint all parts, so none of those tools may require a
    # selected target before opening.
    for tool_id in ("TOOL_PRIMITIVE", "TOOL_LAYFLAT", "TOOL_ENGRAVING"):
        idx = registry_source.find(f"id={tool_id}")
        if idx < 0:
            raise SystemExit(f"Tool registry is missing {tool_id}")
        block = registry_source[idx:registry_source.find("),", idx) + 2]
        if 'selection_policy="none"' not in block:
            raise SystemExit(f"{tool_id} must not require an existing selection")

    light_ui_root = STUDIO / "ui" / "light_transform"
    light_ui_files = [STUDIO / "ui" / "light_transform_overlay.py", *sorted(light_ui_root.glob("*.py"))]
    light_ui_source = "\n".join(path.read_text(encoding="utf-8") for path in light_ui_files)
    layout_source = (STUDIO / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    lifecycle_source = (STUDIO / "application" / "tool_lifecycle_controller.py").read_text(encoding="utf-8")
    layout_restore_source = (STUDIO / "controllers" / "layout_restore.py").read_text(encoding="utf-8")
    for snippet in ("root.setCollapsible(0, True)", "root.setCollapsible(2, True)"):
        if snippet not in layout_source:
            raise SystemExit(f"Light UI must allow both side panes to collapse: missing {snippet}")
    for snippet in (
        "def _sync_ui_layout_state_from_splitter",
        "left_size <= threshold and right_size <= threshold",
        "def _is_full_light_ui_mode",
        "target = [0, max(total, 420), 0]",
        "_set_side_panel_compact_minimums(True)",
    ):
        if snippet not in light_ui_source:
            raise SystemExit(f"Light UI must collapse/detect both side panes: missing {snippet}")
    for snippet in (
        "def _is_right_inspector_collapsed",
        "def _is_transform_overlay_mode",
        "return bool(self._is_right_inspector_collapsed())",
        "visible = bool(self._is_transform_overlay_mode())",
        "full_light = bool(self._is_full_light_ui_mode())",
    ):
        if snippet not in light_ui_source:
            raise SystemExit(f"Transform overlay must depend on the right inspector only: missing {snippet}")
    for snippet in (
        "def _schedule_light_transform_overlay_sync",
        "QTimer.singleShot(45, self._run_scheduled_light_transform_overlay_sync)",
        "def _run_scheduled_light_transform_overlay_sync",
        "def _set_main_splitter_sizes_coalesced",
        "_layout_transition_in_progress",
        "sync_fields = bool(visible) and (force or visibility_changed)",
        "_light_overlay_geometry_signature",
    ):
        if snippet not in light_ui_source:
            raise SystemExit(f"Inspector resize sync must be debounced/lightweight: missing {snippet}")
    moved_start = light_ui_source.find("def _on_main_splitter_moved")
    schedule_start = light_ui_source.find("def _schedule_light_transform_overlay_sync")
    moved_block = light_ui_source[moved_start:schedule_start] if moved_start >= 0 and schedule_start > moved_start else ""
    if "_sync_light_transform_fields" in moved_block or "_sync_light_transform_overlay()" in moved_block:
        raise SystemExit("Inspector splitterMoved must not refresh transform fields or full overlay directly per pixel")
    position_start = light_ui_source.find("def _position_light_transform_overlay")
    hover_start = light_ui_source.find("def _set_light_transform_overlay_hover")
    position_block = light_ui_source[position_start:hover_start] if position_start >= 0 and hover_start > position_start else ""
    if "adjustSize()" in position_block:
        raise SystemExit("Overlay positioning must not call adjustSize() during inspector resize")
    layout_controller_source = (STUDIO / "application" / "layout_controller.py").read_text(encoding="utf-8")
    for snippet in (
        "class LayoutController",
        "InspectorRestoreSnapshot = InspectorLayoutState",
        "compact_overlay",
        "target = [int(saved[0]), max(int(saved[1]), 420), int(saved[2])]",
        "_set_side_panel_compact_minimums(False)",
        "note_user_splitter_drag",
    ):
        if snippet not in layout_controller_source:
            raise SystemExit(f"LayoutController must restore compact panel state around tools: missing {snippet}")
    if "LayoutController" not in layout_restore_source or "QSplitter" in layout_restore_source:
        raise SystemExit("LayoutRestoreLayer should stay a thin facade over LayoutController")

    split_source = (STUDIO / "controllers" / "split_plane_tool.py").read_text(encoding="utf-8")
    for snippet in (
        "def _split_plane_handle_dimensions",
        "_gizmo_length_at(origin",
        "split_handle_dimensions_from_gizmo_length(gizmo_len)",
        "make_arrow_handle_mesh(origin, forward, handle_dims)",
    ):
        if snippet not in split_source:
            raise SystemExit(f"Split plane arrow must use thin transform-gizmo camera scaling: missing {snippet}")
    handles_source = (STUDIO / "rendering" / "handles.py").read_text(encoding="utf-8")
    for snippet in (
        "SPLIT_HANDLE_SHAFT_RADIUS_RATIO = 0.0105",
        "SPLIT_HANDLE_TIP_RADIUS_RATIO = 0.0360",
        "def make_arrow_handle_mesh",
        "Do not use ``pyvista.Arrow(scale=",
    ):
        if snippet not in handles_source:
            raise SystemExit(f"Split handle rendering helper is missing expected snippet: {snippet}")
    if "def _make_split_plane_handle_mesh" in split_source:
        raise SystemExit("SplitPlaneToolLayer should delegate low-level arrow mesh construction to rendering.handles")
    for forbidden in (
        "handle_len = max(size * 0.26",
        "shaft_radius = max(float(size) * 0.0030",
        "tip_radius = max(float(size) * 0.0100",
        "pv.Arrow(start=origin, direction=forward, scale=handle_len",
    ):
        if forbidden in split_source:
            raise SystemExit(f"Split plane arrow still uses the old oversized scaling path: {forbidden}")
    refresh_source = (STUDIO / "controllers" / "interaction_gizmo_refresh.py").read_text(encoding="utf-8")
    camera_source = (STUDIO / "controllers" / "camera.py").read_text(encoding="utf-8")
    interaction_source = (STUDIO / "controllers" / "interaction.py").read_text(encoding="utf-8")
    for snippet in ("def _refresh_camera_scaled_overlays", "_sync_modifier_plane_actor(render=False)"):
        if snippet not in refresh_source:
            raise SystemExit(f"Camera-scaled overlay refresh must include split handle: missing {snippet}")
    if "_refresh_camera_scaled_overlays(render=False)" not in camera_source:
        raise SystemExit("Camera focus must rebuild adaptive gizmos/handles before rendering")
    if "_refresh_camera_scaled_overlays(render=True)" not in interaction_source:
        raise SystemExit("Mouse camera interaction must refresh adaptive gizmos/handles")

    fallback_sources = {
        STUDIO / "controllers" / "interaction.py": [
            "QMainWindow.keyPressEvent(self, event)",
            "QMainWindow.keyReleaseEvent(self, event)",
            "Qt.Key_T: self.TRANSFORM_TRANSLATE",
        ],
        STUDIO / "controllers" / "camera.py": [
            "QMainWindow.closeEvent(self, event)",
        ],
        STUDIO / "controllers" / "gizmo_overlay.py": [
            "def _make_gizmo_actor",
            "def _add_actor_to_main_renderer",
            "SetUseBounds(True)",
            "ren_win.SetNumberOfLayers(2)",
            "__overlay",
            "__main",
        ],
    }
    for path, snippets in fallback_sources.items():
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                raise SystemExit(f"Missing safe Qt fallback in {path.name}: {snippet}")
        if "super().keyPressEvent" in text or "super().keyReleaseEvent" in text or "super().closeEvent" in text:
            raise SystemExit(f"Unsafe zero-argument super() Qt fallback remains in {path.name}")

    extracted: list[str] = []
    for folder in (STUDIO / "ui", STUDIO / "controllers"):
        for path in folder.glob("*.py"):
            if path.name in {"__init__.py", "panels.py", "gizmo_transform.py", "state_bridge.py"}:
                continue
            extracted.extend(name for name in _class_methods(path) if not (name.startswith("__") and name.endswith("__")))

    allowed_duplicate_helpers = {"_combo"}
    duplicates = sorted({name for name in extracted if extracted.count(name) > 1 and name not in allowed_duplicate_helpers})
    if duplicates:
        raise SystemExit("Duplicate extracted methods: " + ", ".join(duplicates))
    if len(extracted) < MIN_EXTRACTED_METHODS:
        raise SystemExit(f"Expected at least {MIN_EXTRACTED_METHODS} extracted methods, got {len(extracted)}")



    # Regression guard from Gizmo Diagnostic Fix: this helper was a static
    # method in the original monolithic window.py. Losing @staticmethod breaks
    # every call through self._bounds_from_vertices_list(vertices), which in turn
    # disables gizmos and copy/paste/duplicate with a TypeError.
    scene_tree = ast.parse((STUDIO / "controllers" / "scene.py").read_text(encoding="utf-8"), filename="scene.py")
    bounds_fn = None
    for node in scene_tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SceneStateLayer":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_bounds_from_vertices_list":
                    bounds_fn = item
                    break
    if bounds_fn is None:
        raise SystemExit("SceneStateLayer is missing _bounds_from_vertices_list")
    decorators = {getattr(dec, "id", getattr(dec, "attr", "")) for dec in bounds_fn.decorator_list}
    if "staticmethod" not in decorators:
        raise SystemExit("SceneStateLayer._bounds_from_vertices_list must remain @staticmethod")


    def _require_staticmethod(path: Path, class_name: str, method_name: str) -> None:
        tree_local = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        fn = None
        for node in tree_local.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == method_name:
                        fn = item
                        break
        if fn is None:
            raise SystemExit(f"{class_name} is missing {method_name}")
        decs = {getattr(dec, "id", getattr(dec, "attr", "")) for dec in fn.decorator_list}
        if "staticmethod" not in decs:
            raise SystemExit(f"{class_name}.{method_name} must remain @staticmethod")

    # Regression guard from Clipboard Fix: static helpers migrated from
    # window.py must stay static. If a decorator is lost, bound-method injection
    # shifts arguments and breaks duplicate/paste/rotation math at runtime.
    _require_staticmethod(STUDIO / "controllers" / "clipboard_actions.py", "ClipboardActionsLayer", "_bounds_axis_size")
    for _method in (
        "_normalize_angle_deg",
        "_quat_normalize",
        "_quat_multiply",
        "_quat_inverse",
        "_quat_to_matrix",
    ):
        _require_staticmethod(STUDIO / "controllers" / "transform_math.py", "TransformMathLayer", _method)

    # The former mixed controller is intentionally kept only as a thin
    # aggregate wrapper. Operational methods must stay in focused modules.
    aggregate_source = (STUDIO / "controllers" / "booleans_clipboard_history.py").read_text(encoding="utf-8")
    if len(aggregate_source.splitlines()) > 45:
        raise SystemExit("booleans_clipboard_history.py should remain a small aggregate wrapper")
    for forbidden in (
        "def boolean_subtract_touching",
        "def copy_selected",
        "def duplicate_selected",
        "def undo_scene",
        "def delete_selected",
    ):
        if forbidden in aggregate_source:
            raise SystemExit(f"Aggregate wrapper still contains operational method: {forbidden}")

    controllers_init = (STUDIO / "controllers" / "__init__.py").read_text(encoding="utf-8")
    for focused_layer in ("PreviewControllerLayer", "ToolLifecycleLayer", "BooleanActionsLayer", "ClipboardActionsLayer", "SceneEditActionsLayer", "HistoryActionsLayer"):
        if focused_layer not in controllers_init:
            raise SystemExit(f"StudioControllers must import/use focused action layer {focused_layer}")

    boolean_controller_source = (STUDIO / "application" / "boolean_controller.py").read_text(encoding="utf-8")
    boolean_facade_source = (STUDIO / "controllers" / "boolean_actions.py").read_text(encoding="utf-8")
    if "class BooleanController" not in boolean_controller_source:
        raise SystemExit("BooleanController must own boolean application workflows")
    for snippet in ("def subtract_touching", "def union_selected", "def separate_selected", "def _qmessagebox"):
        if snippet not in boolean_controller_source:
            raise SystemExit(f"BooleanController missing expected workflow/helper: {snippet}")
    if "from .._window_deps import *" in boolean_controller_source:
        raise SystemExit("BooleanController must keep Qt/window imports lazy")
    if len(boolean_facade_source.splitlines()) > 90:
        raise SystemExit("boolean_actions.py should remain a small facade after Pass 7")
    for forbidden in ("from .._window_deps import *", "boolean_difference(", "boolean_union(", "split_disconnected_mesh("):
        if forbidden in boolean_facade_source:
            raise SystemExit(f"boolean_actions.py facade still contains operational dependency: {forbidden}")

    texture_projection_controller_source = (STUDIO / "application" / "texture_projection_controller.py").read_text(encoding="utf-8")
    texture_projection_layer_source = (STUDIO / "controllers" / "texture_projection_tool.py").read_text(encoding="utf-8")
    for snippet in ("class TextureProjectionController", "def generate_texture_projection_preview", "def clear_texture_projection_selected", "def _qfiledialog"):
        if snippet not in texture_projection_controller_source:
            raise SystemExit(f"TextureProjectionController missing expected workflow/helper: {snippet}")
    if "from .._window_deps import *" in texture_projection_controller_source:
        raise SystemExit("TextureProjectionController must keep Qt/window imports lazy")
    if len(texture_projection_layer_source.splitlines()) > 1550 or "TextureProjectionController" not in texture_projection_layer_source:
        raise SystemExit("TextureProjectionToolLayer should delegate selected TEX workflows to TextureProjectionController")
    for snippet in ("def _clear_button_group_checks", "group.setExclusive(False)", "self._clear_all_tool_button_checks()"):
        if snippet not in lifecycle_source:
            raise SystemExit(f"ToolLifecycleController must clear exclusive toolbox checks on tool close: missing {snippet}")

    required_diag_snippets = {
        STUDIO / "controllers" / "gizmo_view.py": ["[GIZMO_TRACE] update#", "hidden_reason=", "branch=translate", "branch=rotate", "branch=scale"],
        STUDIO / "controllers" / "gizmo_overlay.py": ["[GIZMO_DIAG]", "make_actor", "add_mesh_actor begin", "clear_actors begin"],
        STUDIO / "controllers" / "clipboard_actions.py": ["[CLIPBOARD_DIAG] copy_offset", "duplicate_selected begin", "paste_selection begin", "blocked_check action="],
        STUDIO / "controllers" / "interaction.py": ["[KEY_DIAG]", "[PICKING_DIAG]"],
        STUDIO / "controllers" / "scene.py": ["[SELECTION_DIAG]", "[BOUNDS] selection"],
    }
    for path, snippets in required_diag_snippets.items():
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                raise SystemExit(f"Missing diagnostic log snippet in {path.name}: {snippet}")

    gizmo_view_source = (STUDIO / "controllers" / "gizmo_view.py").read_text(encoding="utf-8")
    if "self.active_index is None or not self._transform_tools_available()" in gizmo_view_source:
        raise SystemExit("update_gizmo must use selected_transform_indices as source of truth, not active_index as a hard gate")
    if "_log_gizmo_state_once" not in gizmo_view_source:
        raise SystemExit("update_gizmo must emit diagnostic state logs for hidden/no_actor cases")

    tooling_tool_source = (STUDIO / "tooling" / "tool.py").read_text(encoding="utf-8")
    for snippet in ("class StudioTool", "class HookToolAdapter", "def on_open", "def on_close", "def can_open"):
        if snippet not in tooling_tool_source:
            raise SystemExit(f"tooling.tool must expose runtime tool contract: missing {snippet}")
    tooling_registry_source = (STUDIO / "tooling" / "registry.py").read_text(encoding="utf-8")
    for snippet in ("def get_studio_tool", "def iter_studio_tools", "def register_tool_spec", "def unregister_tool_spec", "HookToolAdapter"):
        if snippet not in tooling_registry_source:
            raise SystemExit(f"tooling.registry must expose runtime tool adapters: missing {snippet}")
    tooling_extension_source = (STUDIO / "tooling" / "extension_api.py").read_text(encoding="utf-8")
    for snippet in ("class ToolExtensionSpec", "def register_tool_extension", "def unregister_tool_extension"):
        if snippet not in tooling_extension_source:
            raise SystemExit(f"tooling.extension_api must expose the tool/toolbar extension bundle: missing {snippet}")
    if 'iter_studio_tools(category="tool")' not in lifecycle_source or "tool.on_open(self.context)" not in lifecycle_source or "tool.on_close(self.context" not in lifecycle_source:
        raise SystemExit("ToolLifecycleController must use runtime StudioTool objects for tool sync/open/close")
    preview_controller_source = (STUDIO / "controllers" / "preview_controller.py").read_text(encoding="utf-8")
    if "def update_preview_state" not in preview_controller_source:
        raise SystemExit("PreviewControllerLayer must own update_preview_state")
    if "def update_preview_state" in lifecycle_source:
        raise SystemExit("ToolLifecycleLayer should not own update_preview_state")
    modifier_source = (STUDIO / "modifiers" / "modifier.py").read_text(encoding="utf-8")
    for snippet in ("class MeshModifier", "class ToolHostedModifier", "def preview", "OperationResult"):
        if snippet not in modifier_source:
            raise SystemExit(f"modifiers.modifier must expose runtime modifier contract: missing {snippet}")
    modifier_registry_source = (STUDIO / "modifiers" / "registry.py").read_text(encoding="utf-8")
    for snippet in ("def get_mesh_modifier", "def get_mesh_modifier_for_tool", "def iter_mesh_modifiers"):
        if snippet not in modifier_registry_source:
            raise SystemExit(f"modifier registry must expose runtime modifier adapters: missing {snippet}")
    parameter_factory_source = (STUDIO / "parameters" / "panel_factory.py").read_text(encoding="utf-8")
    for snippet in ("def set_values", "def reset", "validate_values"):
        if snippet not in parameter_factory_source:
            raise SystemExit(f"ParameterPanel must support reusable tool parameter editing: missing {snippet}")

    # Pass 17: professional extension architecture. Primitive creation is the
    # first concrete runtime tool, mesh metadata has a V2 payload ready for future exporters,
    # and texture/layer/export contracts exist before texture/gravity features are
    # implemented in the UI.
    work_model_source = (STUDIO / "domain" / "work_model.py").read_text(encoding="utf-8")
    for snippet in ("material: Any | None", "engraving: Any | None", "uvs: list[tuple[float, float]] | None", "texture_projections: list[Any]"):
        if snippet not in work_model_source:
            raise SystemExit(f"WorkMesh must expose V2 metadata field for future material/texture/layer workflows: missing {snippet}")
    domain_source = (STUDIO / "domain" / "material.py").read_text(encoding="utf-8")
    for snippet in ("class MeshMaterial", "class EngravingSettings", "class TextureProjection", "class MeshDomainData"):
        if snippet not in domain_source:
            raise SystemExit(f"domain.material must define future mesh metadata contract: missing {snippet}")
    primitive_registry_source = (STUDIO / "primitives" / "registry.py").read_text(encoding="utf-8")
    primitive_generators_source = (STUDIO / "primitives" / "generators.py").read_text(encoding="utf-8")
    for snippet in ("PRIMITIVE_TOOL_PARAMETERS", "PRIMITIVE_SPECS", "def build_primitive_mesh", "ParameterSpec"):
        if snippet not in primitive_registry_source:
            raise SystemExit(f"Primitive registry is missing professional primitive contract: {snippet}")
    for snippet in ("def build_box", "def build_cylinder", "def build_sphere", "def build_cone"):
        if snippet not in primitive_generators_source:
            raise SystemExit(f"Primitive generators must be isolated from ExportingLayer: missing {snippet}")
    exporting_source = (STUDIO / "controllers" / "exporting.py").read_text(encoding="utf-8")
    if "import pyvista as pv" in exporting_source or "pv.Cylinder" in exporting_source:
        raise SystemExit("ExportingLayer must not own primitive mesh generation or direct PyVista primitive construction")
    primitive_tool_source = (STUDIO / "tooling" / "primitive_tool.py").read_text(encoding="utf-8")
    for snippet in ("class PrimitiveCreatorTool", "CreatorTool", "ctx.operations.primitive_generate", "inspector.panel", "validate_primitive_tool_values"):
        if snippet not in primitive_tool_source:
            raise SystemExit(f"Primitive tool must be migrated to the Creator API: missing {snippet}")
    if "PrimitiveTool" not in tooling_registry_source or "PRIMITIVE_TOOL_PARAMETERS" not in tooling_registry_source:
        raise SystemExit("Tool registry must register PrimitiveTool with declarative primitive parameters")
    rendering_materials_source = (STUDIO / "rendering" / "materials.py").read_text(encoding="utf-8")
    scene_renderer_source = (STUDIO / "rendering" / "scene_renderer.py").read_text(encoding="utf-8")
    for snippet in ("class ActorStyle", "def actor_style_for_mesh", "def apply_actor_style"):
        if snippet not in rendering_materials_source:
            raise SystemExit(f"rendering.materials must provide display/material styling contract: missing {snippet}")
    if "def apply_display_mode" not in scene_renderer_source or "actor_style_for_mesh" not in scene_renderer_source:
        raise SystemExit("SceneRenderer must be able to apply display modes to existing actors")
    engraving_layers_source = (STUDIO / "engraving" / "layers.py").read_text(encoding="utf-8")
    for snippet in ("class EngravingLayerSpec", "cut", "engrave", "def iter_export_layers"):
        if snippet not in engraving_layers_source:
            raise SystemExit(f"Layer-aware engraving export contract missing snippet: {snippet}")
    texture_assets_source = (STUDIO / "assets" / "texture_assets.py").read_text(encoding="utf-8")
    if "class RecentTextureStore" not in texture_assets_source or "limit: int = 5" not in texture_assets_source:
        raise SystemExit("Texture tooling needs a five-recent-images asset store contract")
    three_mf_contracts_source = (STUDIO / "io" / "three_mf" / "contracts.py").read_text(encoding="utf-8")
    for snippet in ("class ThreeMfExportPlan", "class TextureExportRecord", "class MaterialExportRecord"):
        if snippet not in three_mf_contracts_source:
            raise SystemExit(f"3MF V2 export contract missing snippet: {snippet}")

    # Pass 18: selection and transform UX must stay feature-complete without
    # regressing the professional direction. Ctrl+A and transparent selection-box selection
    # select in one batched update; scale ratio lock is a state-backed transform
    # feature shared by inspector fields, compact overlay fields, and scale gizmo
    # drags; controlled layout transitions are coalesced to avoid Light UI/tool
    # open/close lag after long editing sessions.
    selection_box_source = (STUDIO / "controllers" / "selection_box.py").read_text(encoding="utf-8")
    interaction_source = (STUDIO / "controllers" / "interaction.py").read_text(encoding="utf-8")
    scene_source = (STUDIO / "controllers" / "scene.py").read_text(encoding="utf-8")
    action_source = (STUDIO / "ui" / "actions_menus.py").read_text(encoding="utf-8")
    configurable_toolbar_source = (STUDIO / "ui" / "configurable_toolbar.py").read_text(encoding="utf-8")
    toolbar_controller_source = (STUDIO / "application" / "toolbar_controller.py").read_text(encoding="utf-8")
    for snippet in ("class UIConfigurableToolbarLayer", "ConfigurableToolbarController", "def _setup_configurable_toolbar", "def _set_toolbar_remove_mode"):
        if snippet not in configurable_toolbar_source:
            raise SystemExit(f"Configurable toolbar layer must stay as a thin facade: missing {snippet}")
    for snippet in ("class ConfigurableToolbarController", "TOOLBAR_REMOVABLE_ITEM_STYLE", "def setup", "def set_remove_mode", "def rebuild", "def add_item", "def remove_item"):
        if snippet not in toolbar_controller_source:
            raise SystemExit(f"ConfigurableToolbarController must own toolbar edit behavior: missing {snippet}")

    selection_overlay_source = (STUDIO / "ui" / "selection_box_overlay.py").read_text(encoding="utf-8")
    for snippet in ("class SelectionBoxOverlay", "WA_TranslucentBackground", "fillRect", "drawRect"):
        if snippet not in selection_overlay_source:
            raise SystemExit(f"SelectionBoxOverlay must provide a transparent visual rectangle: missing {snippet}")
    transform_state_source = (STUDIO / "state" / "transform_state.py").read_text(encoding="utf-8")
    transform_inspector_source = (STUDIO / "controllers" / "transform_inspector.py").read_text(encoding="utf-8")
    transform_drag_source = (STUDIO / "controllers" / "transform_drag.py").read_text(encoding="utf-8")
    for snippet in ("class SelectionBoxLayer", "SelectionBoxOverlay", "def _display_to_qt_xy", "def _indices_intersecting_selection_box", "def _finish_selection_box"):
        if snippet not in selection_box_source:
            raise SystemExit(f"SelectionBoxLayer must provide rectangle selection contract: missing {snippet}")
    for snippet in ("SelectionBoxLayer", "Qt.Key_A", "self.select_all_parts()", "_begin_selection_box_candidate", "_finish_selection_box"):
        if snippet not in interaction_source:
            raise SystemExit(f"InteractionLayer must wire Ctrl+A and rectangle selection: missing {snippet}")
    for snippet in ("def set_selection_indices", "def select_all_parts", "reason=\"select all\""):
        if snippet not in scene_source:
            raise SystemExit(f"SceneStateLayer must batch selection updates: missing {snippet}")
    for snippet in ("act_select_all", "Ctrl+A", "Select all parts"):
        if snippet not in action_source:
            raise SystemExit(f"Edit menu must expose Ctrl+A select-all: missing {snippet}")
    for snippet in ("scale_ratio_locked: bool",):
        if snippet not in transform_state_source:
            raise SystemExit(f"TransformState must own scale ratio lock: missing {snippet}")
    for snippet in ("def _set_scale_ratio_locked", "def _propagate_locked_scale_change_from_widgets", "scale_ratio_lock_check"):
        if snippet not in transform_inspector_source + (STUDIO / "ui" / "tool_panels.py").read_text(encoding="utf-8"):
            raise SystemExit(f"Scale ratio lock must be shared by inspector fields: missing {snippet}")
    if "light_scale_ratio_lock" not in light_ui_source or "_propagate_locked_scale_change_from_widgets([self.light_x, self.light_y, self.light_z])" not in light_ui_source:
        raise SystemExit("Compact transform overlay must expose and apply scale ratio lock")
    for snippet in ('locked = bool(getattr(self, "scale_ratio_locked", False))', 'for logical in ("x", "y", "z")', "_drag_scale_axes"):
        if snippet not in transform_drag_source:
            raise SystemExit(f"Scale gizmo drags must support ratio lock: missing {snippet}")
    for snippet in ("def _set_main_splitter_sizes_coalesced", "splitter.blockSignals(True)", "_layout_transition_in_progress"):
        if snippet not in light_ui_source:
            raise SystemExit(f"Layout transitions must be coalesced to avoid Light UI/tool lag: missing {snippet}")
    layout_restore_source = (STUDIO / "controllers" / "layout_restore.py").read_text(encoding="utf-8")
    layout_controller_source = (STUDIO / "application" / "layout_controller.py").read_text(encoding="utf-8")
    if "LayoutController" not in layout_restore_source:
        raise SystemExit("LayoutRestoreLayer must delegate to LayoutController")
    splitter_policy_source = (STUDIO / "application" / "splitter_layout_policy.py").read_text(encoding="utf-8")
    for snippet in ("class SplitterLayoutPolicy", "def plan_open_inspector", "already-visible"):
        if snippet not in splitter_policy_source:
            raise SystemExit(f"SplitterLayoutPolicy must own deterministic side-pane layout decisions: missing {snippet}")
    if "_set_main_splitter_sizes_coalesced" not in layout_controller_source or "plan_open_inspector" not in layout_controller_source:
        raise SystemExit("Tool layout controller must use coalesced splitter size updates and SplitterLayoutPolicy")
    layout_panels_source = (STUDIO / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    for snippet in ("self.top_toolbar_scroll = QScrollArea(panel)", "setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)", "root.setStretchFactor(1, 1)"):
        if snippet not in layout_panels_source:
            raise SystemExit(f"Center toolbar must not force the main splitter minimum width: missing {snippet}")

    controllers_init = (STUDIO / "controllers" / "__init__.py").read_text(encoding="utf-8")
    required_gizmo_layers = [
        "GizmoOverlayLayer",
        "GizmoHighlightLayer",
        "GizmoViewLayer",
        "TransformDragLayer",
        "TransformGeometryLayer",
        "TransformMathLayer",
    ]
    missing_gizmo_layers = [name for name in required_gizmo_layers if name not in controllers_init]
    if missing_gizmo_layers:
        raise SystemExit("Missing gizmo/transform layers in StudioControllers: " + ", ".join(missing_gizmo_layers))

    print(
        f"Refactor structure OK: bases={base_names}, "
        f"window methods={sorted(window_methods)}, extracted methods={len(extracted)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
