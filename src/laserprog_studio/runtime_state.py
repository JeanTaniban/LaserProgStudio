# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .app_context import AppContext
from .application import StudioActionController
from .application.export_controller import ExportController
from .application.render_output_controller import RenderOutputController
from .application.preview_controller import PreviewController
from .application.tool_preview_controller import ToolPreviewController
from .application.tool_lifecycle_controller import ToolLifecycleController
from .application.boolean_controller import BooleanController
from .application.texture_projection_controller import TextureProjectionController
from .application.texture_gizmo_controller import TextureGizmoController
from .application.planar_tool_controller import PlanarToolController
from .application.tool_help_controller import ToolHelpController
from .application.background_tasks import BackgroundTaskManager
from .application.scene_history_controller import SceneHistoryController
from .application.layout_controller import LayoutController
from .application.toolbar_controller import ConfigurableToolbarController
from .assets import RecentTextureStore
from .bootstrap import compute_paths
from .rendering import SceneRenderer
from .project import AutosavePolicy, ProjectStore
from .state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, TextureGizmoState, PlanarToolState, UiLayoutState


def initialize_runtime_state(self: Any) -> None:
    """Initialise LaserProgStudioV18 mutable runtime state.

    Keeping these assignments outside window.py makes the Qt main window a
    composition root instead of a second monolith. Controller layers read the
    runtime services from the concrete window object.
    """
    self.project_store = ProjectStore.new_empty(scene_name="main")
    # Active scene ModelStore exposed on the window for controller layers that
    # still operate directly on the Qt root object.
    self.mesh_store = self.project_store.active_model_store
    self.scene_modification_history = self.project_store.active_scene.history
    self.autosave_policy = AutosavePolicy()
    self.autosave_pending = False
    self.autosave_in_progress = False
    self._last_autosave_monotonic = None
    self._last_project_activity_monotonic = None
    self._project_dirty_since_monotonic = None
    # Structured runtime state objects are the primary controller API. Direct
    # attributes below mirror high-traffic state for the Qt root object.
    self.selection_state = SelectionState()
    self.transform_state = TransformState()
    self.tool_state = ToolState(active_tool=self.TOOL_NONE)
    self.preview_state = PreviewState()
    self.ui_layout_state = UiLayoutState()
    self.render_state = RenderState()
    self.render_scheduler = None
    self.scene_renderer = SceneRenderer(self)
    self.clipboard_state = ClipboardState()
    self.app_context = AppContext.from_window(self)
    self.context = self.app_context
    self.action_controller = StudioActionController.create(self.app_context)
    self.layout_controller = LayoutController.create(self.app_context)
    self.toolbar_controller = ConfigurableToolbarController.create(self.app_context)
    self.export_controller = ExportController.create(self.app_context)
    self.render_output_controller = RenderOutputController.create(self.app_context)
    self.preview_controller = PreviewController.create(self.app_context)
    self.tool_preview_controller = ToolPreviewController.create(self.app_context)
    self.tool_lifecycle_controller = ToolLifecycleController.create(self.app_context)
    self.boolean_controller = BooleanController.create(self.app_context)
    self.texture_projection_controller = TextureProjectionController.create(self.app_context)
    self.texture_gizmo_controller = TextureGizmoController.create(self.app_context)
    self.planar_tool_controller = PlanarToolController.create(self.app_context)
    self.tool_core_diag_controller = None
    self.tool_help_controller = ToolHelpController.create(self.app_context)
    self.scene_history_controller = SceneHistoryController.create(self.app_context)
    self.background_task_manager = BackgroundTaskManager(self, max_workers=1, poll_ms=35)
    try:
        from .ui_orchestration import UIOrchestrationService
        self.ui_orchestration = UIOrchestrationService(self)
    except Exception:
        self.ui_orchestration = None
    try:
        from .services.project_preferences import load_project_preferences

        self.project_preferences = load_project_preferences()
    except Exception:
        self.project_preferences = None

    self.actors_by_index: dict[int, Any] = self.render_state.actors_by_index
    self.polydata_by_index: dict[int, Any] = self.render_state.polydata_by_index
    self.actor_key_by_vtk: dict[int, int] = {}
    self.actor_key_by_addr: dict[str, int] = {}
    self.gizmo_key_by_addr: dict[str, str] = {}
    self.gizmo_actors: dict[str, Any] = {}
    self.gizmo_overlay_renderer = None
    self.gizmo_actor_ids: dict[int, str] = {}
    self.selected_indices: list[int] = self.selection_state.selected_indices
    self.active_index: int | None = self.selection_state.active_index
    self.active_tool = self.tool_state.active_tool
    self.transform_mode = self.transform_state.mode
    self.scale_ratio_locked = self.transform_state.scale_ratio_locked
    self._scale_lock_last_values: tuple[float, float, float] | None = None
    self._updating_scale_ratio_lock_fields = False
    self.show_edges = True
    self.show_ghost = False
    self.show_floor_grid = True
    self.floor_grid_actor = self.render_state.floor_grid_actor
    self.material_floor_actor = None
    self._material_floor_signature = None
    self.material_shadow_actors = {}
    self._material_shadow_signature = None
    self._material_shadow_pass_enabled = False
    self._material_scene_syncing = False
    self._material_key_light = None
    try:
        _pref_grid_step = float(getattr(getattr(self, "project_preferences", None), "default_floor_grid_step_mm", 10.0))
    except Exception:
        _pref_grid_step = 10.0
    self.floor_grid_step = _pref_grid_step if _pref_grid_step > 0 else 10.0
    self.laser_area_actor = None
    self._left_down_pos: tuple[int, int] | None = None
    self._drag_axis: str | None = None
    self._drag_start_pos: tuple[int, int] | None = None
    # Camera interaction: we rely on VTK/PyVista interaction styles (no manual orbit).
    self._left_down_pos: tuple[int, int] | None = None
    self._left_down_time: float = 0.0
    self._last_mouse_pos: tuple[int, int] | None = None
    self._qt_click_pos: tuple[float, float] | None = None
    self._qt_click_time: float = 0.0
    self._camera_style_name = "terrain"
    self._right_pan_active = False
    self._right_pan_last: tuple[float, float] | None = None
    self._pan_sensitivity = 1.08  # Screen->world pan sensitivity factor.
    self._camera_view_mode = "free"  # "free" or one of the fixed orthographic views.
    self._suppress_next_left_release = False
    self._selection_box_candidate = False
    self._selection_box_active = False
    self._selection_box_start = None
    self._selection_box_last = None
    self._selection_box_additive = False
    self._selection_box_band = None
    self._drag_axis: str | None = None
    self._drag_start_qpos: tuple[float, float] | None = None
    self._drag_start_vertices: list[tuple[float, float, float]] | None = None
    self._drag_mesh_indices: list[int] = []
    self._drag_start_vertices_by_index: dict[int, list[tuple[float, float, float]]] = {}
    self._drag_start_rotation_state_by_index: dict[int, tuple[tuple[float, float, float, float], tuple[float, float, float]]] = {}
    self._drag_axis_origin: tuple[float, float, float] | None = None
    self._drag_axis_vector: tuple[float, float, float] | None = None
    self._drag_axis_screen: tuple[float, float, float] | None = None
    self._drag_translation_moving_profile = None
    self._drag_translation_start_center: tuple[float, float, float] | None = None
    self._drag_live_translation_offset: tuple[float, float, float] | None = None
    self._drag_mesh_index: int | None = None
    self._drag_transform_mode: str | None = None
    self._drag_rotation_center: tuple[float, float, float] | None = None
    self._drag_rotation_last_vector: tuple[float, float, float] | None = None
    self._drag_rotation_accum_angle: float = 0.0
    self._drag_scale_bounds: tuple[float, float, float, float, float, float] | None = None
    self._drag_scale_pivot: tuple[float, float, float] | None = None
    self._drag_scale_factor: float = 1.0
    self._drag_scale_axes = None
    self._drag_start_rotation_quat: tuple[float, float, float, float] | None = None
    self._drag_start_rotation_euler: tuple[float, float, float] | None = None
    # Transform gizmo: axis click = persistent highlight, drag = translation.
    self._gizmo_pressed_axis: str | None = None
    self._gizmo_press_pos: tuple[float, float] | None = None
    self.planar_tool_state = PlanarToolState()
    self.texture_gizmo_state = TextureGizmoState()
    self.texture_gizmo_state.apply_to_window(self)
    # Performance profiles:
    #   optimized (default): no high-volume diagnostics, no app-wide profiler,
    #   debug: detailed logs/JSONL/timings for bug hunting.  Debug mode is
    #   persisted through services.debug_mode and can be toggled from View > Performance.
    try:
        from .services.debug_mode import is_debug_mode_enabled
        _debug_mode_enabled = bool(is_debug_mode_enabled())
    except Exception:
        _perf_env = str(os.environ.get("LPS_PERF_MODE", os.environ.get("LPS_MODE", "optimized"))).lower().strip()
        _debug_env = str(os.environ.get("LPS_VERBOSE_DIAG", "0")).lower() in {"1", "true", "yes", "on"}
        _debug_mode_enabled = bool(_debug_env or _perf_env in {"debug", "diag", "diagnostic", "verbose"})
    self._performance_mode: str = "debug" if _debug_mode_enabled else "optimized"
    self._diagnostic_verbose: bool = self._performance_mode == "debug"
    self._ui_log_max_blocks: int = int(os.environ.get("LPS_UI_LOG_MAX_BLOCKS", "600" if self._performance_mode == "optimized" else "1400") or 600)
    self._optimized_log_file_echo: bool = str(os.environ.get("LPS_OPTIMIZED_FILE_LOG", "0")).lower() in {"1", "true", "yes", "on"}
    # Native Transform picking is now pure screen-space math.  A 120 ms hover
    # throttle made the visible gizmo feel disconnected from the cursor and
    # caused presses to race against stale hover state.  Keep it responsive
    # while still coalescing duplicate mouse events.
    self._gizmo_hover_min_interval_ms: float = 24.0 if self._performance_mode == "optimized" else 16.0
    self._display_lod_threshold_triangles: int = int(os.environ.get("LPS_LOD_THRESHOLD_TRIANGLES", "80000") or 80000)
    self._display_lod_target_triangles: int = int(os.environ.get("LPS_LOD_TARGET_TRIANGLES", "55000") or 55000)
    self._texture_drag_min_px: float = 1.0 if self._performance_mode == "optimized" else 0.35
    self._texture_poll_interval_ms: int = 50 if self._performance_mode == "optimized" else 33
    self._layout_overlay_sync_delay_ms: int = 90 if self._performance_mode == "optimized" else 45
    self._gizmo_main_actor_names: set[str] = set()
    self._highlighted_transform_axis: str | None = None
    self._hovered_transform_axis: str | None = None
    self._last_gizmo_hover_probe_time: float = 0.0
    self._last_gizmo_hover_probe_pos: tuple[float, float] | None = None
    self._gizmo_actor_base_colors: dict[int, tuple[float, float, float]] = {}
    # Camera-scaled Transform gizmos use a lightweight in-place point update.
    # Raw camera ModifiedEvent observers remain avoided, but wheel zoom events can
    # now refresh the gizmo at the interactive frame cadence without rebuilding
    # heavy actors.
    self._gizmo_wheel_refresh_pending = False
    self._gizmo_zoom_live_pulse_pending = False
    self._gizmo_zoom_live_serial = 0
    self._gizmo_live_refresh_pending = False
    self._gizmo_live_refresh_fast_transform = False
    self._last_gizmo_live_refresh_time = 0.0
    self._gizmo_live_refresh_interval_ms = 16.0 if self._performance_mode == "optimized" else 12.0
    self._camera_zoom_burst_until = 0.0
    self._engrave_images: dict[str, Any] = {}
    self.texture_assets_by_id: dict[str, Any] = {}
    try:
        _paths = compute_paths()
        self.recent_texture_store = RecentTextureStore(storage_path=_paths.toolbox_dir / "settings" / "recent_textures.json")
    except Exception:
        self.recent_texture_store = RecentTextureStore()
    self._engrave_source_path: Path | None = None
    self.grid_snap_enabled = False
    self.smart_snap_enabled = True
    self.grid_snap_step = 5.0
    self.smart_snap_tolerance = 2.0
    self.rotation_snap_enabled = True
    self.rotation_snap_step_deg = 45.0
    self.rotation_snap_tolerance_deg = 5.0
    self._last_snap_label: str | None = None
    self._drag_rotation_applied_angle: float = 0.0
    self._gizmo_delta_display_signature: tuple[str, int, tuple[float, float, float], tuple[float, float, float]] | None = None
    self._updating_transform_fields = False
    self._live_transform_update_active = False
    self._drag_undo_snapshot = None
    self._history_limit = 30
    self._light_transform_mode = "position"
    self._updating_light_transform_fields = False
    self._updating_light_transform_mode = False
    # Light transform mode is activated only when both side panes are collapsed.
    # The splitter sizes are the source of truth because QWidget.width() may
    # still report a panel minimum width even when the splitter pane is at 0.
    self._layout_light_collapse_threshold = 12
    self._right_panel_light_threshold = 12
    self._left_panel_min_visible_width = 160
    self._right_panel_min_visible_width = 200
    self._right_panel_tool_min_width = 240
    self._center_panel_auto_min_width = 360
    self._light_overlay_is_hovered = False
    self._last_inspector_light_mode: bool | None = None
    self._last_light_overlay_visible: bool | None = None
    self._copy_buffer_meshes: list[Any] = self.clipboard_state.meshes
    self.split_plane_actor = None
    self.split_plane_edge_actor = None
    self.split_plane_handle_actor = None
    self.render_camera_state: dict[str, Any] | None = None
    self.render_camera_actor_names: list[str] = []
    self.render_preview_dialog = None
    self._split_handle_pressed = False
    self._split_handle_press_pos: tuple[float, float] | None = None
    self._split_drag_active = False
    self._split_drag_start_offset: float | None = None
    self._split_drag_axis_vector: tuple[float, float, float] | None = None
    self._split_drag_axis_screen: tuple[float, float, float] | None = None
    self._updating_split_plane_fields = False

