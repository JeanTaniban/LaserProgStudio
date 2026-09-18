# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .curve_intent import ArcIntent, HalfCircleIntent

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_api.sketch import SketchDocument

from .constants import _MODE_POINT, _PHASE_PICK_HEIGHT


@dataclass(slots=True)
class _PlanTrace2DSnapshot:
    sketch: SketchDocument
    next_point_index: int
    pending_line_start_id: str | None = None
    pending_polyline_last_id: str | None = None
    pending_rectangle_corner_id: str | None = None
    pending_circle_center_id: str | None = None
    pending_arc_start_id: str | None = None
    pending_arc_end_id: str | None = None
    pending_bezier_start_id: str | None = None
    pending_bezier_end_id: str | None = None
    pending_bezier_control_1_id: str | None = None
    pending_half_circle_start_id: str | None = None
    pending_dimension_start_id: str | None = None
    pending_dimension_line_id: str | None = None
    motif_face_holes_by_outer_signature: dict[str, tuple[tuple[tuple[float, float], ...], ...]] = field(default_factory=dict)
    motif_face_hole_kinds: dict[str, str] = field(default_factory=dict)
    motif_assignments_by_outer_signature: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class _PlacementMetricDraft:
    """Tool-local handle for an API-owned metric edit session.

    The generic metric API owns field definitions and overlay construction.
    Plan tracer stores only the sketch reconstruction data needed to reapply a
    draft element from a clean snapshot during later editable-metric passes.
    """

    mode: str
    base_snapshot: _PlanTrace2DSnapshot
    session_id: str
    session: Any
    start_xy: tuple[float, float] | None = None
    end_xy: tuple[float, float] | None = None
    center_xy: tuple[float, float] | None = None
    radius_xy: tuple[float, float] | None = None
    first_xy: tuple[float, float] | None = None
    opposite_xy: tuple[float, float] | None = None
    control_xy: tuple[float, float] | None = None
    entity_ids: tuple[str, ...] = ()
    arc_intent: ArcIntent | None = None
    half_circle_intent: HalfCircleIntent | None = None
    pending_field_values: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class _PlanTrace2DState:
    phase: str = _PHASE_PICK_HEIGHT
    active_tool: str = _MODE_POINT
    view: FixedPlanarView = FixedPlanarView.TOP
    plane: LockedPlaneSpec | None = None
    display_plane: LockedPlaneSpec | None = None
    points: list[tuple[str, tuple[float, float, float]]] = field(default_factory=list)
    lines: list[tuple[str, str]] = field(default_factory=list)
    sketch: SketchDocument = field(default_factory=SketchDocument)
    pending_line_start_id: str | None = None
    pending_polyline_last_id: str | None = None
    pending_rectangle_corner_id: str | None = None
    pending_circle_center_id: str | None = None
    pending_arc_start_id: str | None = None
    pending_arc_end_id: str | None = None
    pending_bezier_start_id: str | None = None
    pending_bezier_end_id: str | None = None
    pending_bezier_control_1_id: str | None = None
    pending_half_circle_start_id: str | None = None
    pending_dimension_start_id: str | None = None
    pending_dimension_line_id: str | None = None
    next_point_index: int = 1
    anchor_world: tuple[float, float, float] | None = None
    hover_object_id: str | None = None
    hover_world: tuple[float, float, float] | None = None
    # Snap scope selected by the user.  By default Plan Tracer can snap to the
    # whole scene.  When enabled, scene smart-snap targets are limited to the
    # object that owns the picked face/editable source; live sketch targets are
    # always kept.
    snap_active_object_only: bool = False
    active_snap_object_ids: tuple[str, ...] = ()
    active_snap_object_indices: tuple[int, ...] = ()
    active_snap_object_label: str = ""
    active_snap_object_source: str = ""
    cursor_world: tuple[float, float, float] | None = None
    last_snap_label: str = "none"
    last_snap_kind: str = "free"
    last_constraint_label: str = "none"
    active_drag_snapshot: _PlanTrace2DSnapshot | None = None
    active_drag_changed: bool = False
    active_drag_detached_count: int = 0
    # Explicit selection as it existed before support-point promotion.  A
    # click on a grabbable point enters the native grab path even when the
    # pointer never moves; preserving this tuple lets a no-op release keep the
    # point selected instead of restoring a snapshot that clears selection.
    active_drag_selection_before_ids: tuple[str, ...] = ()
    # Explicit translation/rotation gesture state. Kept separate from the
    # native SelectionManager so Plan Tracer can rotate semantic sketch points
    # while the generic runtime continues to own pointer capture and repaint.
    active_transform_session: Any = None
    # Sketch-local clipboard. It intentionally lives in the active Plan Tracer
    # session instead of the application mesh clipboard.
    sketch_clipboard_payload: Any = None
    sketch_clipboard_paste_index: int = 0
    metric_draft: _PlacementMetricDraft | None = None
    pending_preview_ids: tuple[str, ...] = ()
    pending_preview_signature: tuple[Any, ...] | None = None
    surface_pick_press_screen_pos: tuple[float, float] | None = None
    extrusion_depth: float = 10.0
    editable_hover_object_id: str | None = None
    editable_hover_label: str = ""
    # Object whose face was chosen with "New sketch". The object is only a
    # geometric support: its existing Plan Tracer history remains untouched.
    # Subtract still uses its *current visible mesh* as the new base rather than
    # resurrecting an older intact mesh stored by a previous subtraction.
    new_sketch_support_object_id: str | None = None
    editing_source_object_id: str | None = None
    editing_source_label: str = ""
    editing_source_extrusion_depth: float | None = None
    editing_source_kind: str = ""
    # "add" is the historical green extruded-board result. "subtract" is
    # a boolean cut that stores the intact target mesh so Plan Tracer can
    # reopen, edit the sketch and reapply the cut non-destructively.
    editing_source_operation: str = "add"
    # Placement reconciliation performed when reopening an object whose mesh
    # vertices were translated/rotated/scaled after its editable source was
    # created.  The focus bounds are captured before the source is hidden so the
    # camera can frame the object's real current location.
    editing_source_placement_mode: str = "identity"
    editing_source_placement_reference: str = "none"
    editing_source_focus_bounds: tuple[float, float, float, float, float, float] | None = None
    # During edit/resume the source mesh is removed from the document so it
    # cannot visually obscure the sketch and cannot contribute snap targets.
    # It is kept here only as a fallback for attribute preservation or restore.
    editing_source_removed_mesh: Any | None = None
    editing_source_removed_index: int | None = None
    applied_since_open: bool = False
    # Explicit validation feedback for Apply/Add/Subtract.  The status manager
    # is not necessarily visible while a viewport tool is active, so failures
    # must also appear inside Plan Tracer's own status field.
    apply_last_error: str = ""
    pattern_pick_face_active: bool = False
    pattern_face_id: str | None = None
    pattern_face_ids: tuple[str, ...] = ()
    pattern_generated_count: int = 0
    # Pattern overlay: the dedicated viewport window for browsing motifs and
    # editing every parameter.  The state below mirrors the overlay fields and
    # the inspector panel so all three views stay in sync via a single source
    # of truth (this state object).
    motif_overlay_visible: bool = False
    motif_kind: str = "honeycomb"
    motif_preset_id: str = "__custom__"
    motif_preset_name: str = ""
    motif_cell_size: float = 12.0
    motif_wall: float = 2.0
    motif_margin: float = 2.0
    motif_keep_form: bool = True
    motif_angle: float = 0.0
    motif_aspect: float = 1.0
    motif_seed: int = 7
    motif_offset_x: float = 0.0
    motif_offset_y: float = 0.0
    # Debounced preview scheduling.  Text edits update the state immediately,
    # but the expensive motif preview is rebuilt only after the value has been
    # stable for a short delay.  ``generation`` invalidates older QTimer jobs.
    motif_preview_generation: int = 0
    motif_preview_pending: bool = False
    motif_preview_pending_reason: str = ""
    motif_preview_debounce_ms: int = 1000
    motif_preview_segment_budget: int = 120000
    motif_apply_segment_budget: int = 120000
    # Last motif generation budget status, shared by the overlay and the
    # generator service so the UI can explain why a preview was skipped.
    motif_segment_limit_hit: bool = False
    motif_estimated_segments: int = 0
    motif_segment_budget_used: int = 0
    # Persistent direct motif holes keyed by the stable outer-face signature.
    # Pattern holes are attached to the face instead of expanding into hundreds of
    # independent sketch lines, so compile/sync must restore them after topology
    # regeneration.
    motif_face_holes_by_outer_signature: dict[str, tuple[tuple[tuple[float, float], ...], ...]] = field(default_factory=dict)
    motif_face_hole_kinds: dict[str, str] = field(default_factory=dict)
    # Compact parametric Pattern ownership.  One host outer-face signature maps
    # to exactly one assignment; generated hole polygons are derived cache, not
    # authored sketch linework and are intentionally regenerated when needed.
    motif_assignments_by_outer_signature: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Raw text recently received from the Pattern overlay.  This mirrors the
    # metric overlay contract: button commits collect these values atomically
    # instead of trusting only formatted fields.
    motif_pending_field_values: dict[str, str] = field(default_factory=dict)
    motif_last_status: str = ""
    # Live preview baseline: snapshot taken on open so every parameter change
    # can rebuild the perforation from a clean sketch.  ``Apply`` records this
    # baseline as the undo "before" state; ``Close`` simply restores it.  The
    # face id is captured separately because snapshots do not include the
    # currently targeted face.
    motif_preview_baseline: Any = None
    motif_preview_face_id: str | None = None
    motif_preview_face_ids: tuple[str, ...] = ()
    # Offset gizmo: when the user grabs the on-scene translate handle we store
    # the drag origin so MOUSE_MOVE can compute a relative delta in the face
    # plane.  ``axis`` is "free", "x" or "y".
    motif_offset_drag_axis: str | None = None
    motif_offset_drag_start_offset: tuple[float, float] | None = None
    motif_offset_drag_start_uv: tuple[float, float] | None = None
    # Pattern diagnostics: monotonic sequence + last event summary written by
    # motif_diagnostics.py.  Keeping only metadata in state avoids coupling the
    # editor logic to files or Qt widgets.
    motif_diag_sequence: int = 0
    motif_diag_last_event: str = ""

    # Performance caches for dense sketches.  The topology compiler and the
    # Creator UI renderer are the expensive paths once many motif holes/regions
    # exist.  These fields let services skip redundant compiles and throttle
    # high-frequency cursor rendering without hiding real geometry changes.
    plan_trace_last_compile_signature: tuple[Any, ...] | None = None
    # Geometry signatures of already-registered Projected Drawing actors.
    # Full topology compiles still run when required, but unchanged points,
    # edges, curves and faces are not re-added to the projected registry on
    # every edit.  This avoids dirtying/reprojecting the complete sketch after
    # each newly placed segment.
    plan_trace_actor_visual_signatures: dict[str, tuple[Any, ...]] = field(default_factory=dict)
    # Camera-exclusive navigation state. While true the Qt bridge suppresses
    # Plan Tracer hover, hit-test and snap events; the projected renderer only
    # reprojects its existing batches. One cursor/snap catch-up runs on release.
    camera_interaction_active: bool = False
    camera_interaction_mode: str = "static"
    camera_interaction_screen_pos: tuple[float, float] | None = None

    plan_trace_last_cursor_screen_pos: tuple[float, float] | None = None
    plan_trace_last_cursor_world: tuple[float, float, float] | None = None
    plan_trace_last_cursor_sync_time: float = 0.0
    plan_trace_last_cursor_render_time: float = 0.0
    plan_trace_cursor_min_screen_delta_px: float = 0.75
    plan_trace_cursor_render_interval_s: float = 1.0 / 30.0


__all__ = ["_PlanTrace2DSnapshot", "_PlacementMetricDraft", "_PlanTrace2DState"]
