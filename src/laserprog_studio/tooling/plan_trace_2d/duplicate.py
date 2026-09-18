# -*- coding: utf-8 -*-
"""Plan Tracer Duplicate: persistent prefabs and intelligent 2D placement.

The service is intentionally isolated from selection, history and rendering.
Selection graph extraction/paste lives in :mod:`selection_edit`; persistence in
:mod:`prefabs`; this module only owns the Duplicate workflow and overlay.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from laserprog_studio.tool_api import plan2d, projected_drawing as draw2d
from laserprog_studio.tool_api import visual
from laserprog_studio.tool_api.core import MouseButton, ToolEventType
from laserprog_studio.tool_api.plan2d.curves import (
    sample_circle,
    sample_circular_arc_through_points,
    sample_cubic_bezier,
)

from .constants import _MODE_MODIFY
from .duplicate_state import DuplicateStage, DuplicateWorkflow
from .prefabs import PlanTracePrefab, delete_prefab, load_prefabs, rename_prefab, save_prefab
from .selection_edit import SketchPayload, SketchSelection
from .services import _PlanTrace2DService

DUPLICATE_WINDOW_ID = "plan_trace_2d.duplicate"
DUPLICATE_LIBRARY_WINDOW_ID = "plan_trace_2d.duplicate.library"
DUPLICATE_NAME_WINDOW_ID = "plan_trace_2d.duplicate.name"
DUPLICATE_OPTIONS_WINDOW_ID = "plan_trace_2d.duplicate.options"
DUPLICATE_ACTION_PREFIX = "plan_trace_2d.duplicate.action."
DUPLICATE_FIELD_PREFIX = "plan_trace_2d.duplicate.field."
DUPLICATE_GROUP = "plan_trace_2d.duplicate.stage"
DUPLICATE_VISUAL_PREFIX = "plan_trace_2d:duplicate:"
_DUPLICATE_PREVIEW_BATCH_ID = DUPLICATE_VISUAL_PREFIX + "preview:segments"
_DUPLICATE_PREVIEW_PIVOT_ID = DUPLICATE_VISUAL_PREFIX + "preview:pivot"
_DUPLICATE_PREVIEW_POINTS_ID = DUPLICATE_VISUAL_PREFIX + "preview:points"

_FIELD_PREFAB = DUPLICATE_FIELD_PREFIX + "prefab"
_FIELD_NAME = DUPLICATE_FIELD_PREFIX + "name"
_FIELD_COUNT = DUPLICATE_FIELD_PREFIX + "count"
_FIELD_SPACING = DUPLICATE_FIELD_PREFIX + "spacing"
_FIELD_EDGE_START_MARGIN = DUPLICATE_FIELD_PREFIX + "edge_start_margin"
_FIELD_EDGE_END_MARGIN = DUPLICATE_FIELD_PREFIX + "edge_end_margin"
_FIELD_EDGE_OFFSET = DUPLICATE_FIELD_PREFIX + "edge_offset"
_FIELD_FOLLOW = DUPLICATE_FIELD_PREFIX + "follow_rotation"
_FIELD_MIRROR = DUPLICATE_FIELD_PREFIX + "mirror"
_FIELD_FLIP = DUPLICATE_FIELD_PREFIX + "flip"
_FIELD_INFO = DUPLICATE_FIELD_PREFIX + "info"
_FIELD_STORAGE = DUPLICATE_FIELD_PREFIX + "storage"

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class _PathSample:
    point: Point2
    tangent_angle: float


@dataclass(frozen=True, slots=True)
class _CurveFragment:
    """One selected open sketch curve with stable topology endpoints."""

    entity_id: str
    start_point_id: str
    end_point_id: str
    points: tuple[Point2, ...]


def _point_in_loop(point: Point2, loop: Iterable[Point2]) -> bool:
    values = list(loop)
    if len(values) < 3:
        return False
    x, y = float(point[0]), float(point[1])
    inside = False
    j = len(values) - 1
    for i in range(len(values)):
        xi, yi = values[i]
        xj, yj = values[j]
        if ((yi > y) != (yj > y)):
            denom = (yj - yi) if abs(yj - yi) > 1.0e-15 else 1.0e-15
            cross_x = (xj - xi) * (y - yi) / denom + xi
            if x < cross_x:
                inside = not inside
        j = i
    return inside


def _point_in_or_on_loop(point: Point2, loop: Iterable[Point2], *, tolerance: float = 1.0e-7) -> bool:
    values = list(loop)
    if len(values) < 3:
        return False
    px, py = point
    tolerance_sq = tolerance * tolerance
    for a, b in zip(values, values[1:] + values[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length_sq = dx * dx + dy * dy
        if length_sq <= 1.0e-24:
            if (px - a[0]) ** 2 + (py - a[1]) ** 2 <= tolerance_sq:
                return True
            continue
        t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / length_sq))
        qx, qy = a[0] + t * dx, a[1] + t * dy
        if (px - qx) ** 2 + (py - qy) ** 2 <= tolerance_sq:
            return True
    return _point_in_loop(point, values)


def _polyline_lengths(points: list[Point2]) -> tuple[list[float], float]:
    cumulative = [0.0]
    for a, b in zip(points, points[1:]):
        cumulative.append(cumulative[-1] + math.dist(a, b))
    return cumulative, cumulative[-1] if cumulative else 0.0


def _sample_polyline_at(points: list[Point2], cumulative: list[float], target: float) -> _PathSample:
    if len(points) < 2:
        return _PathSample(points[0] if points else (0.0, 0.0), 0.0)
    target = max(0.0, min(float(target), cumulative[-1]))
    index = 0
    while index + 1 < len(cumulative) and cumulative[index + 1] < target:
        index += 1
    index = min(index, len(points) - 2)
    a, b = points[index], points[index + 1]
    length = max(1.0e-15, cumulative[index + 1] - cumulative[index])
    t = (target - cumulative[index]) / length
    point = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return _PathSample(point, math.atan2(b[1] - a[1], b[0] - a[0]))


class PlanTrace2DDuplicateOverlay:
    """Compact, contextual Duplicate UI.

    The permanent surface is deliberately small.  Naming, prefab selection and
    placement parameters appear only when the current user step needs them.
    """

    @staticmethod
    def action_from_button(button_id: str | None) -> str | None:
        value = str(button_id or "")
        if value.startswith(DUPLICATE_ACTION_PREFIX):
            return value[len(DUPLICATE_ACTION_PREFIX):]
        return None

    @staticmethod
    def is_field(field_id: str | None) -> bool:
        return str(field_id or "").startswith(DUPLICATE_FIELD_PREFIX)

    @staticmethod
    def _action(action: str, label: str, icon: str, tooltip: str, *, enabled: bool = True, style: str = "ghost") -> visual.OverlayActionSpec:
        return visual.OverlayActionSpec(
            id=DUPLICATE_ACTION_PREFIX + action,
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=bool(enabled),
            style=style,  # type: ignore[arg-type]
            display_label=label,
            slot_width_px=max(64, min(104, len(label) * 8 + 24)),
        )

    @staticmethod
    def _button(
        action: str,
        label: str,
        icon: str,
        tooltip: str,
        *,
        enabled: bool = True,
        style: str = "secondary",
        checkable: bool = False,
        checked: bool = False,
    ) -> visual.ToolButtonSpec:
        return visual.ToolButtonSpec(
            id=DUPLICATE_ACTION_PREFIX + action,
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=bool(enabled),
            style=style,  # type: ignore[arg-type]
            checkable=bool(checkable),
            checked=bool(checked),
        )

    @staticmethod
    def _prefab_option_label(item: PlanTracePrefab) -> str:
        payload = item.payload
        curve_count = len(payload.lines) + len(payload.arcs) + len(payload.beziers) + len(payload.circles)
        return f"{item.name}  ·  {len(payload.points)} pts / {curve_count} curves"

    @staticmethod
    def _prefab_summary(item: PlanTracePrefab | None) -> str:
        if item is None:
            return "No prefab saved"
        payload = item.payload
        min_x, max_x, min_y, max_y = payload.bounds
        return f"{max_x - min_x:.3g} × {max_y - min_y:.3g} mm · pivot ({payload.pivot[0]:.3g}, {payload.pivot[1]:.3g})"

    def _picker_window(
        self,
        service: "PlanTrace2DDuplicateService",
        prefabs: tuple[PlanTracePrefab, ...],
        selected: PlanTracePrefab | None,
    ) -> visual.OverlayWindowSpec:
        options = tuple((item.id, self._prefab_option_label(item)) for item in prefabs) or (("", "No saved prefab"),)
        return visual.OverlayWindowSpec(
            id=DUPLICATE_LIBRARY_WINDOW_ID,
            title="Select prefab",
            owner_tool=service.id,
            fields=[
                visual.OverlayFieldSpec(
                    _FIELD_PREFAB,
                    "Prefab",
                    selected.id if selected is not None else "",
                    kind="select",
                    enabled=bool(prefabs),
                    options=options,
                    tooltip="Choose the prefab used by Place, Along and Fill.",
                ),
                visual.OverlayFieldSpec(
                    _FIELD_INFO,
                    "",
                    self._prefab_summary(selected),
                    kind="info",
                ),
            ],
            buttons=[
                self._button("choose_prefab", "Use", "tool.apply", "Use this prefab and close the picker.", enabled=selected is not None, style="primary"),
                self._button("rename_prompt", "Rename", "tool.edit", "Rename the selected prefab.", enabled=selected is not None),
                self._button("delete_prefab", "Delete", "sketch.delete", "Delete the selected prefab.", enabled=selected is not None, style="danger"),
                self._button("close_picker", "Cancel", "tool.close", "Close the prefab picker."),
            ],
            anchor="viewport_top_right",
            overlay_kind="popover",
            width_px=330,
            movable=True,
            persistent=False,
            close_on_click_outside=False,
            cursor_offset_px=(0, 84),
        )

    def _name_window(self, service: "PlanTrace2DDuplicateService") -> visual.OverlayWindowSpec:
        rename = service.name_prompt_mode == "rename"
        return visual.OverlayWindowSpec(
            id=DUPLICATE_NAME_WINDOW_ID,
            title="Rename prefab" if rename else "Name prefab",
            owner_tool=service.id,
            fields=[
                visual.OverlayFieldSpec(
                    _FIELD_NAME,
                    "Name",
                    service.prefab_name,
                    kind="text",
                    enabled=True,
                    live=True,
                    tooltip="Persistent name shown in the prefab picker.",
                )
            ],
            buttons=[
                self._button(
                    "confirm_rename" if rename else "save_prefab",
                    "Rename" if rename else "Save",
                    "tool.apply",
                    "Confirm the prefab name.",
                    enabled=bool(service.prefab_name.strip()) and (rename or service.capture_payload is not None),
                    style="primary",
                ),
                self._button("cancel_name", "Cancel", "tool.close", "Cancel without changing the library."),
            ],
            anchor="center",
            overlay_kind="modal",
            width_px=300,
            modal=True,
            movable=False,
            persistent=False,
            close_on_click_outside=False,
        )

    def _options_window(self, service: "PlanTrace2DDuplicateService", selected: PlanTracePrefab | None) -> visual.OverlayWindowSpec:
        if service.stage == "edge":
            can_build_along = bool(
                selected is not None
                and service._last_ctx is not None
                and service._along_samples(service._last_ctx, preview_limit=2)
            )
            return visual.OverlayWindowSpec(
                id=DUPLICATE_OPTIONS_WINDOW_ID,
                title="Place along",
                owner_tool=service.id,
                fields=[
                    visual.OverlayFieldSpec(_FIELD_INFO, "Prefab", selected.name if selected is not None else "None", kind="info"),
                    visual.OverlayFieldSpec(
                        _FIELD_COUNT,
                        "Copies",
                        str(service.copy_count),
                        kind="number",
                        enabled=True,
                        live=True,
                        tooltip="Total copies distributed along the selected path.",
                    ),
                    visual.OverlayFieldSpec(
                        _FIELD_EDGE_START_MARGIN,
                        "Start margin (mm)",
                        f"{service.edge_start_margin:.3g}",
                        kind="number",
                        enabled=True,
                        live=True,
                        tooltip="Clearance between the path start and the first prefab pivot.",
                    ),
                    visual.OverlayFieldSpec(
                        _FIELD_EDGE_END_MARGIN,
                        "End margin (mm)",
                        f"{service.edge_end_margin:.3g}",
                        kind="number",
                        enabled=True,
                        live=True,
                        tooltip="Clearance between the last prefab pivot and the path end.",
                    ),
                    visual.OverlayFieldSpec(
                        _FIELD_EDGE_OFFSET,
                        "Offset (mm)",
                        f"{service.edge_normal_offset:.3g}",
                        kind="number",
                        enabled=True,
                        live=True,
                        tooltip=(
                            "Signed perpendicular distance from the path to each prefab pivot. "
                            "Mirror automatically places the same offset on the opposite side."
                        ),
                    ),
                ],
                buttons=[
                    self._button("toggle_follow", "Follow", "tool.rotate", "Follow the path tangent.", style="toggle", checkable=True, checked=service.follow_rotation),
                    self._button("toggle_mirror", "Mirror", "tool.mirror", "Reflect the prefab across the path tangent to place it on the other side.", style="toggle", checkable=True, checked=service.mirror_along),
                    self._button("toggle_flip", "Flip", "tool.mirror", "Reflect the prefab on its other local axis, reversing its direction along the path.", style="toggle", checkable=True, checked=service.flip_along),
                    self._button("build_along", "Build", "tool.apply", "Create the previewed copies.", enabled=can_build_along, style="primary"),
                    self._button("back", "Cancel", "tool.close", "Cancel Along placement."),
                ],
                anchor="viewport_top_right",
                overlay_kind="popover",
                width_px=310,
                movable=True,
                persistent=True,
                cursor_offset_px=(0, 84),
            )
        return visual.OverlayWindowSpec(
            id=DUPLICATE_OPTIONS_WINDOW_ID,
            title="Fill face",
            owner_tool=service.id,
            fields=[
                visual.OverlayFieldSpec(_FIELD_INFO, "Prefab", selected.name if selected is not None else "None", kind="info"),
                visual.OverlayFieldSpec(
                    _FIELD_SPACING,
                    "Pitch (mm)",
                    f"{service.face_spacing:.3g}",
                    kind="number",
                    enabled=True,
                    live=True,
                    tooltip="Distance between prefab pivots.",
                ),
            ],
            buttons=[
                self._button("build_fill", "Build", "tool.apply", "Fill the selected face.", enabled=selected is not None and service._last_ctx is not None and service._selected_face(service._last_ctx) is not None, style="primary"),
                self._button("back", "Cancel", "tool.close", "Cancel face filling."),
            ],
            anchor="viewport_top_right",
            overlay_kind="popover",
            width_px=270,
            movable=True,
            persistent=True,
            cursor_offset_px=(0, 84),
        )

    @staticmethod
    def _hide_window(ctx: Any, window_id: str) -> None:
        try:
            ctx.overlay.hide_window(window_id)
        except Exception:
            pass

    def sync(self, ctx: Any, service: "PlanTrace2DDuplicateService") -> None:
        prefabs = service.prefabs
        selected = service.selected_prefab
        stage = service.stage
        has_selection = service.services.selection_edit.selected_entities(ctx).entity_count > 0
        can_place = selected is not None

        # Pivot capture is a direct viewport instruction, not a validation
        # step.  In particular, do not expose Back/Done/Apply-like buttons here:
        # the only valid forward action is clicking the pivot in the viewport.
        if stage == "pivot":
            ctx.overlay.show_window(
                visual.OverlayWindowSpec(
                    id=DUPLICATE_WINDOW_ID,
                    title="Choose prefab pivot",
                    owner_tool=service.id,
                    fields=[
                        visual.OverlayFieldSpec(
                            "plan_trace_2d.duplicate.pivot_instruction",
                            "",
                            "Click the point that will be used as the prefab pivot. Smart Snap is active.",
                            kind="info",
                        )
                    ],
                    buttons=[],
                    anchor="viewport_top_right",
                    overlay_kind="prompt",
                    width_px=350,
                    movable=False,
                    persistent=True,
                    close_on_click_outside=False,
                )
            )
            self._hide_window(ctx, DUPLICATE_LIBRARY_WINDOW_ID)
            self._hide_window(ctx, DUPLICATE_NAME_WINDOW_ID)
            self._hide_window(ctx, DUPLICATE_OPTIONS_WINDOW_ID)
            return

        # Once the pivot exists, the dedicated modal is the complete UI for
        # naming the prefab.  Hiding the command deck prevents unrelated
        # Duplicate actions from appearing behind the modal.
        if stage == "pivot_ready" and service.name_prompt_mode == "create":
            self._hide_window(ctx, DUPLICATE_WINDOW_ID)
            self._hide_window(ctx, DUPLICATE_LIBRARY_WINDOW_ID)
            ctx.overlay.show_window(self._name_window(service))
            self._hide_window(ctx, DUPLICATE_OPTIONS_WINDOW_ID)
            return

        if stage == "library":
            sections = (
                visual.OverlayToolbarSectionSpec(
                    "prefab",
                    "Prefab",
                    actions=(
                        self._action("create", "New", "tool.add", "Create a prefab from the current selection.", style="primary"),
                        self._action("select_prefab", "Select", "tool.library", "Open the prefab picker.", enabled=bool(prefabs)),
                        self._action("place_one", "Place", "sketch.point", "Place the active prefab by its pivot.", enabled=can_place, style="primary"),
                    ),
                ),
                visual.OverlayToolbarSectionSpec(
                    "placement",
                    "Placement",
                    actions=(
                        self._action("along_edge", "Along", "sketch.line", "Distribute the active prefab along selected curves.", enabled=can_place),
                        self._action("fill_face", "Fill", "sketch.face", "Fill one selected face with the active prefab.", enabled=can_place),
                    ),
                ),
                visual.OverlayToolbarSectionSpec(
                    "finish",
                    "Finish",
                    actions=(self._action("done", "Done", "tool.close", "Return to Modify."),),
                ),
            )
        elif stage == "capture":
            sections = (
                visual.OverlayToolbarSectionSpec(
                    "capture",
                    "Create prefab",
                    actions=(
                        self._action("selection_ready", "Selection ready", "tool.apply", "Continue to pivot selection.", enabled=has_selection, style="primary"),
                        self._action("clear_selection", "Clear", "tool.reset", "Clear the current selection.", enabled=has_selection),
                    ),
                ),
                visual.OverlayToolbarSectionSpec("finish", "Finish", actions=(
                    self._action("back", "Back", "tool.reset", "Cancel prefab creation."),
                    self._action("done", "Done", "tool.close", "Return to Modify."),
                )),
            )
        else:
            sections = (
                visual.OverlayToolbarSectionSpec(
                    "finish",
                    "Duplicate",
                    actions=(
                        self._action("back", "Back", "tool.reset", "Cancel the current step.", enabled=stage != "library"),
                        self._action("done", "Done", "tool.close", "Return to Modify."),
                    ),
                ),
            )

        badge_value = selected.name if stage == "library" and selected is not None else service.stage_label
        deck_width = 620 if stage == "library" else (430 if stage == "capture" else 270)
        window = visual.build_command_deck_window(
            window_id=DUPLICATE_WINDOW_ID,
            owner_tool=service.id,
            group_id=DUPLICATE_GROUP,
            sections=sections,
            active_mode_id="",
            badge_id="plan_trace_2d.duplicate.stage",
            badge_label="Duplicate",
            badge_value=badge_value,
            badge_tooltip="Active prefab or current Duplicate step.",
            status_id="plan_trace_2d.duplicate.status",
            status_label="",
            status_value=service.status_text(ctx),
            title="Plan Tracer · Duplicate",
            anchor="viewport_top_right",
            width_px=deck_width,
            persistent=True,
        )
        ctx.overlay.show_window(window)

        if service.picker_open and stage == "library" and service.name_prompt_mode is None:
            ctx.overlay.show_window(self._picker_window(service, prefabs, selected))
        else:
            self._hide_window(ctx, DUPLICATE_LIBRARY_WINDOW_ID)

        if service.name_prompt_mode is not None:
            ctx.overlay.show_window(self._name_window(service))
        else:
            self._hide_window(ctx, DUPLICATE_NAME_WINDOW_ID)

        if stage in {"edge", "face"}:
            ctx.overlay.show_window(self._options_window(service, selected))
        else:
            self._hide_window(ctx, DUPLICATE_OPTIONS_WINDOW_ID)

    @staticmethod
    def hide(ctx: Any) -> None:
        for window_id in (DUPLICATE_WINDOW_ID, DUPLICATE_LIBRARY_WINDOW_ID, DUPLICATE_NAME_WINDOW_ID, DUPLICATE_OPTIONS_WINDOW_ID):
            try:
                ctx.overlay.hide_window(window_id)
            except Exception:
                pass


class PlanTrace2DDuplicateService(_PlanTrace2DService):
    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.overlay = PlanTrace2DDuplicateOverlay()
        self.workflow = DuplicateWorkflow()
        self.prefab_name = ""
        self.selected_prefab_id = ""
        self.copy_count = 5
        self.face_spacing = 20.0
        self.edge_start_margin = 0.0
        self.edge_end_margin = 0.0
        self.edge_normal_offset = 0.0
        self.follow_rotation = True
        self.mirror_along = False
        self.flip_along = False
        self.picker_open = False
        self.name_prompt_mode: str | None = None
        self.capture_selection: SketchSelection | None = None
        self.capture_payload: SketchPayload | None = None
        self.pivot_xy: Point2 | None = None
        self.hover_xy: Point2 | None = None
        self._last_screen_pos: Point2 | None = None
        self._visual_ids: tuple[str, ...] = ()
        self._last_ctx: Any | None = None

    @property
    def stage(self) -> str:
        """Compatibility view used by existing tests and overlay code."""

        return self.workflow.stage.value

    @stage.setter
    def stage(self, value: str | DuplicateStage) -> None:
        self.workflow.force(value, reason="legacy_assignment")

    def _transition(self, target: str | DuplicateStage, *, reason: str) -> None:
        self.workflow.transition(target, reason=reason)

    @property
    def modify_extension_active(self) -> bool:
        return self.workflow.uses_modify_selection

    @property
    def selection_interaction_active(self) -> bool:
        return self.workflow.uses_selection_box

    @property
    def pointer_preview_active(self) -> bool:
        return self.workflow.uses_pointer_preview

    @property
    def prefabs(self) -> tuple[PlanTracePrefab, ...]:
        return load_prefabs()

    @property
    def selected_prefab(self) -> PlanTracePrefab | None:
        items = self.prefabs
        selected = next((item for item in items if item.id == self.selected_prefab_id), None)
        if selected is None and items:
            selected = items[0]
            self.selected_prefab_id = selected.id
        return selected

    def _suggest_prefab_name(self) -> str:
        existing = {item.name.casefold() for item in self.prefabs}
        index = 1
        while f"prefab {index}".casefold() in existing:
            index += 1
        return f"Prefab {index}"

    def _sync_name_from_selected(self) -> None:
        selected = self.selected_prefab
        self.prefab_name = selected.name if selected is not None else self._suggest_prefab_name()

    @property
    def stage_label(self) -> str:
        return {
            "library": "Library",
            "capture": "Select geometry",
            "pivot": "Pick pivot",
            "pivot_ready": "Confirm prefab",
            "place": "Place prefab",
            "edge": "Along edges",
            "face": "Fill face",
        }.get(self.stage, self.stage)

    def activate(self, ctx: Any) -> None:
        self._last_ctx = ctx
        self.workflow.force(DuplicateStage.LIBRARY, reason="activate")
        self.capture_selection = None
        self.capture_payload = None
        self.pivot_xy = None
        self.hover_xy = None
        self.picker_open = False
        self.name_prompt_mode = None
        self._clear_preview(ctx, render=False)
        self._sync_name_from_selected()
        self._sync(ctx, render=True)
        ctx.status.info(
            "Duplicate extends Modify: select, Shift-select, box-select or safely move sketch elements, "
            "then create or place a prefab."
        )

    def deactivate(self, ctx: Any, *, render: bool = True) -> None:
        self._last_ctx = ctx
        self.overlay.hide(ctx)
        self._clear_preview(ctx, render=False)
        self.workflow.force(DuplicateStage.LIBRARY, reason="deactivate")
        self.capture_selection = None
        self.capture_payload = None
        self.pivot_xy = None
        self.hover_xy = None
        self.picker_open = False
        self.name_prompt_mode = None
        if render:
            self.services.rendering._render(ctx, sync_overlays=True, render=True)

    def _reset_to_library(self, ctx: Any, *, reason: str, render: bool = True, clear_selection: bool = False) -> None:
        target = self.workflow.back_target
        if target is None:
            target = DuplicateStage.LIBRARY
        if self.workflow.stage is not target:
            self._transition(target, reason=reason)
        self.capture_selection = None
        self.capture_payload = None
        self.pivot_xy = None
        self.hover_xy = None
        self.picker_open = False
        self.name_prompt_mode = None
        self._clear_preview(ctx, render=False)
        if target is DuplicateStage.LIBRARY:
            self._sync_name_from_selected()
        if clear_selection:
            self._clear_plan_selection(ctx)
        self._sync(ctx, render=render)

    def handle_escape(self, ctx: Any) -> bool:
        """Escape backs out one Duplicate step before leaving the tool."""

        if self.workflow.stage is DuplicateStage.LIBRARY:
            return False
        self._reset_to_library(ctx, reason="escape", render=True)
        ctx.status.info("Duplicate step cancelled. Library and Modify-style selection remain active.")
        return True

    def handle_field_change(self, ctx: Any, field_id: str, value: str) -> bool:
        self._last_ctx = ctx
        field_id = str(field_id)
        if field_id == _FIELD_PREFAB:
            selected = next((item for item in self.prefabs if item.id == str(value)), None)
            if selected is not None:
                self.selected_prefab_id = selected.id
                self.prefab_name = selected.name
                min_x, max_x, min_y, max_y = selected.payload.bounds
                self.face_spacing = float(max(max_x - min_x, max_y - min_y, 1.0))
            self._sync(ctx, render=False)
            return True
        if field_id == _FIELD_NAME:
            self.prefab_name = " ".join(str(value).strip().split())[:80]
            self._sync(ctx, render=False)
            return True
        if field_id == _FIELD_COUNT:
            try:
                self.copy_count = max(1, min(5000, int(float(value))))
            except Exception:
                pass
            self._sync(ctx, render=True)
            return True
        if field_id == _FIELD_SPACING:
            try:
                self.face_spacing = max(0.01, min(100000.0, float(value)))
            except Exception:
                pass
            self._sync(ctx, render=False)
            return True
        if field_id == _FIELD_EDGE_START_MARGIN:
            try:
                self.edge_start_margin = max(0.0, min(100000.0, float(value)))
            except Exception:
                pass
            self._sync(ctx, render=True)
            return True
        if field_id == _FIELD_EDGE_END_MARGIN:
            try:
                self.edge_end_margin = max(0.0, min(100000.0, float(value)))
            except Exception:
                pass
            self._sync(ctx, render=True)
            return True
        if field_id == _FIELD_EDGE_OFFSET:
            try:
                self.edge_normal_offset = max(-100000.0, min(100000.0, float(value)))
            except Exception:
                pass
            self._sync(ctx, render=True)
            return True
        if field_id == _FIELD_FOLLOW:
            self.follow_rotation = str(value).strip().lower() in {"1", "true", "yes", "on"}
            self._sync(ctx, render=True)
            return True
        if field_id == _FIELD_MIRROR:
            self.mirror_along = str(value).strip().lower() in {"1", "true", "yes", "on"}
            self._sync(ctx, render=True)
            return True
        if field_id == _FIELD_FLIP:
            self.flip_along = str(value).strip().lower() in {"1", "true", "yes", "on"}
            self._sync(ctx, render=True)
            return True
        return False

    def _open_name_prompt(self, ctx: Any, *, mode: str) -> None:
        self.picker_open = False
        self.name_prompt_mode = str(mode)
        self._sync(ctx, render=False)

    def handle_button(self, ctx: Any, button_id: str) -> bool:
        self._last_ctx = ctx
        action = self.overlay.action_from_button(button_id)
        if action is None:
            return False
        if action == "done":
            self.services.mode_state._set_active_tool(ctx, _MODE_MODIFY, reason="duplicate_done", render=True)
            return True
        if action == "back":
            self._reset_to_library(ctx, reason="back", render=True)
            return True
        if action == "select_prefab":
            self.picker_open = True
            self.name_prompt_mode = None
            self._sync(ctx, render=False)
            return True
        if action in {"choose_prefab", "close_picker"}:
            self.picker_open = False
            self._sync(ctx, render=False)
            return True
        if action == "rename_prompt":
            selected = self.selected_prefab
            if selected is None:
                return True
            self.prefab_name = selected.name
            self._open_name_prompt(ctx, mode="rename")
            return True
        if action == "cancel_name":
            self.name_prompt_mode = None
            if self.workflow.stage is DuplicateStage.PIVOT_READY:
                self._reset_to_library(ctx, reason="cancel_name", render=True)
            else:
                self._sync_name_from_selected()
                self._sync(ctx, render=False)
            return True
        if action == "create":
            self.picker_open = False
            self.name_prompt_mode = None
            self._transition(DuplicateStage.CAPTURE, reason="create_prefab")
            self.prefab_name = self._suggest_prefab_name()
            self.capture_selection = None
            self.capture_payload = None
            self.pivot_xy = None
            self._sync(ctx, render=True)
            ctx.status.info("Create prefab: select points, edges or faces, then click Selection ready.")
            return True
        if action == "selection_ready":
            selection = self.services.selection_edit.selected_entities(ctx, expand_faces=True)
            if not selection.entity_count:
                ctx.status.info("Select at least one Plan Tracer element before choosing the pivot.")
                return True
            self.capture_selection = selection
            self.capture_payload = None
            self._transition(DuplicateStage.PIVOT, reason="selection_ready")
            self.hover_xy = self._current_cursor_xy(ctx)
            self._sync_preview(ctx, render=False)
            self._sync(ctx, render=True)
            ctx.status.info("Click the prefab pivot. Smart Snap is active.")
            return True
        if action == "save_prefab":
            if self.capture_payload is None:
                ctx.status.info("Pick a prefab pivot first.")
                return True
            clean_name = " ".join(self.prefab_name.strip().split())
            if any(item.name.casefold() == clean_name.casefold() for item in self.prefabs):
                ctx.status.info(f"A prefab named '{clean_name}' already exists.")
                return True
            try:
                saved = save_prefab(clean_name, self.capture_payload)
            except ValueError as exc:
                ctx.status.info(str(exc))
                return True
            self.selected_prefab_id = saved.id
            self.prefab_name = saved.name
            self.name_prompt_mode = None
            self._transition(DuplicateStage.LIBRARY, reason="prefab_saved")
            self.capture_selection = None
            self.capture_payload = None
            self.pivot_xy = None
            self._clear_preview(ctx, render=False)
            self._sync(ctx, render=True)
            ctx.status.info(f"Prefab '{saved.name}' saved.")
            return True
        if action in {"confirm_rename", "rename_prefab"}:
            selected = self.selected_prefab
            if selected is None:
                return True
            try:
                renamed = rename_prefab(selected.id, self.prefab_name)
            except ValueError as exc:
                ctx.status.info(str(exc))
                return True
            self.selected_prefab_id = renamed.id
            self.prefab_name = renamed.name
            self.name_prompt_mode = None
            self._sync(ctx, render=False)
            ctx.status.info(f"Prefab renamed to '{renamed.name}'.")
            return True
        if action == "clear_selection":
            changed = tuple(ctx.selection.ids())
            self._clear_plan_selection(ctx)
            self._sync_selection_feedback(ctx, changed)
            self._sync(ctx, render=True)
            return True
        if action == "toggle_follow":
            self.follow_rotation = not self.follow_rotation
            self._sync(ctx, render=True)
            return True
        if action == "toggle_mirror":
            self.mirror_along = not self.mirror_along
            self._sync(ctx, render=True)
            return True
        if action == "toggle_flip":
            self.flip_along = not self.flip_along
            self._sync(ctx, render=True)
            return True
        if action == "delete_prefab":
            selected = self.selected_prefab
            if selected is not None and delete_prefab(selected.id):
                self.selected_prefab_id = ""
                self._sync_name_from_selected()
                if not self.prefabs:
                    self.picker_open = False
                self._sync(ctx, render=False)
                ctx.status.info(f"Prefab '{selected.name}' deleted.")
            return True
        if action == "place_one":
            if self.selected_prefab is None:
                return True
            self.picker_open = False
            self._transition(DuplicateStage.PLACE, reason="place_one")
            self.hover_xy = self._current_cursor_xy(ctx)
            self._clear_plan_selection(ctx)
            self._sync_preview(ctx, render=False)
            self._sync(ctx, render=True)
            ctx.status.info("Prefab ghost follows the cursor. Click repeatedly; Back ends placement.")
            return True
        if action == "along_edge":
            self.picker_open = False
            self._transition(DuplicateStage.EDGE, reason="along_edge")
            self._clear_plan_selection(ctx)
            self._sync(ctx, render=True)
            ctx.status.info("Select lines, arcs or curves. The orange/blue highlight and green preview update immediately.")
            return True
        if action == "fill_face":
            self.picker_open = False
            self._transition(DuplicateStage.FACE, reason="fill_face")
            self._clear_plan_selection(ctx)
            self._sync(ctx, render=True)
            ctx.status.info("Select one face, set the pitch, then Build.")
            return True
        if action == "build_along":
            self._build_along_selected(ctx)
            return True
        if action == "build_fill":
            self._build_face_fill(ctx)
            return True
        return True

    def wants_native_actor_interaction(self, ctx: Any, event: Any) -> bool:
        """Inherit Modify hover/select/grab in library and capture stages."""

        if not self.modify_extension_active or event.screen_pos is None:
            return False
        self._remember_pointer(event)
        # Shift-click/drag belongs to the shared rectangle/toggle selector.
        return not bool(getattr(event, "shift", False))

    def handle_native_interaction_result(self, ctx: Any, event: Any, result: Any) -> bool:
        if not self.modify_extension_active:
            return False
        self._remember_pointer(event)
        action = str(getattr(result, "action", "") or "")
        if action in {"select", "grab", "release", "clear"}:
            self.services.overlay._sync_reports(ctx)
            self._sync(ctx, render=False)
        return True

    def _remember_pointer(self, event: Any) -> None:
        if getattr(event, "screen_pos", None) is not None:
            self._last_screen_pos = (float(event.screen_pos[0]), float(event.screen_pos[1]))

    def _role_allowed_for_stage(self, role: str) -> bool:
        if self.workflow.selection_kind == "all":
            return role in {"point", "edge", "arc", "circle", "face"}
        if self.workflow.selection_kind == "curve":
            return role in {"edge", "arc", "circle"}
        if self.workflow.selection_kind == "face":
            return role == "face"
        return False

    def _sync_selection_feedback(self, ctx: Any, actor_ids: Iterable[str] = ()) -> None:
        """Refresh only actors whose hover/selection state may have changed."""

        changed = {str(value) for value in actor_ids if value}
        changed.update(str(value) for value in ctx.selection.ids())
        hover_id = str(getattr(ctx.selection.state, "hover_id", "") or "")
        if hover_id:
            changed.add(hover_id)
        if not changed:
            return
        try:
            plan2d.sync_plan_actor_visuals(
                ctx,
                owner_tool=self.id,
                changed_actor_ids=tuple(sorted(changed)),
                position_only=False,
                render=False,
            )
        except Exception:
            pass

    def handle_event(self, ctx: Any, event: Any) -> bool:
        if event.screen_pos is None:
            return False
        self._remember_pointer(event)

        if self.workflow.uses_selection_box and event.shift:
            if self.services.selection._handle_modify_selection_api_event(ctx, event):
                removed = self._filter_stage_selection(ctx)
                self._sync_selection_feedback(ctx, removed)
                self._sync(ctx, render=self.workflow.uses_filtered_selection)
                if not self.workflow.uses_filtered_selection:
                    self.services.rendering._sync_overlays(ctx)
                return True

        # Library and capture are genuine Modify extensions. Normal hover, click
        # selection and safe point/group dragging are owned by the native API.
        if self.modify_extension_active:
            return False

        # Path/face placement uses filtered selection. Keep disallowed geometry
        # visible but do not let it enter the semantic selection.
        if self.workflow.uses_filtered_selection:
            if event.type is ToolEventType.MOUSE_MOVE and event.button == MouseButton.NONE:
                hit = ctx.selection.hit_test(event.screen_pos, ctx.viewport.world_to_screen, owner_tool=self.id, selectable_only=True)
                actor_id = None
                if hit is not None:
                    actor = ctx.selection.actor(hit.actor_id)
                    role = str((getattr(actor, "metadata", {}) or {}).get("plan_trace_role") or "") if actor is not None else ""
                    if self._role_allowed_for_stage(role):
                        actor_id = hit.actor_id
                old_hover = str(getattr(ctx.selection.state, "hover_id", "") or "")
                if actor_id != old_hover:
                    ctx.selection.set_hover(actor_id)
                    self._sync_selection_feedback(ctx, (old_hover, str(actor_id or "")))
                    self.services.rendering._render(ctx, sync_overlays=False, render=True)
                return bool(actor_id)
            if event.type is ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT:
                before_ids = tuple(str(value) for value in ctx.selection.ids())
                hit = ctx.selection.hit_test(event.screen_pos, ctx.viewport.world_to_screen, owner_tool=self.id, selectable_only=True)
                changed_ids = list(before_ids)
                if hit is None:
                    self._clear_plan_selection(ctx)
                else:
                    actor = ctx.selection.actor(hit.actor_id)
                    role = str((getattr(actor, "metadata", {}) or {}).get("plan_trace_role") or "") if actor is not None else ""
                    if self._role_allowed_for_stage(role):
                        ctx.selection.select(hit.actor_id, replace=True)
                        changed_ids.append(str(hit.actor_id))
                    else:
                        ctx.status.info(
                            "Along accepts lines/arcs/curves; Fill accepts one face. "
                            "Use Back for unrestricted Modify-style selection."
                        )
                changed_ids.extend(self._filter_stage_selection(ctx))
                self._sync_selection_feedback(ctx, changed_ids)
                self.services.overlay._sync_reports(ctx)
                self._sync(ctx, render=True)
                return True
            return event.type is ToolEventType.MOUSE_RELEASE

        if self.pointer_preview_active:
            if event.type is ToolEventType.MOUSE_MOVE:
                self.hover_xy = self._snapped_xy(ctx, event)
                self._sync_preview(ctx, render=True)
                return True
            if event.type is ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT:
                xy = self._snapped_xy(ctx, event)
                self.hover_xy = xy
                if self.workflow.stage is DuplicateStage.PIVOT:
                    self.pivot_xy = xy
                    selection = self.capture_selection or self.services.selection_edit.selected_entities(ctx, expand_faces=True)
                    self.capture_payload = self.services.selection_edit.payload_from_entity_selection(
                        selection, pivot=xy, source_name=self.prefab_name
                    )
                    self._transition(DuplicateStage.PIVOT_READY, reason="pivot_picked")
                    self.name_prompt_mode = "create"
                    self._clear_preview(ctx, render=False)
                    self._sync(ctx, render=True)
                    ctx.status.info("Pivot selected. Name the prefab in the small dialog.")
                    return True

                prefab = self.selected_prefab
                if prefab is None:
                    return True
                before = self.services.history._snapshot_state()
                result = self.services.selection_edit.paste_payload(
                    ctx, prefab.payload, target=xy, compile_after=True, select_created=False
                )
                if result.created_count:
                    self.services.history._record_snapshot_command(ctx, f"Place prefab {prefab.name}", before)
                    # Sketch compilation refreshes the owner's projected drawing
                    # and can remove auxiliary primitives. Restore the live ghost
                    # immediately at the same snapped pointer location.
                    self._sync_preview(ctx, render=False)
                    self.services.overlay._sync_reports(ctx)
                    self.services.rendering._render(ctx, sync_overlays=False, render=True)
                    ctx.status.info(f"Placed prefab '{prefab.name}'. The ghost remains attached for another placement.")
                return True
            return True
        return False

    def status_text(self, ctx: Any) -> str:
        selected = self.selected_prefab
        if self.stage == "capture":
            count = self.services.selection_edit.selected_entities(ctx).entity_count
            return f"Select source geometry · {count} semantic element(s) selected"
        if self.stage == "pivot":
            return "Pick the prefab relative center/pivot in the viewport · Smart Snap enabled"
        if self.stage == "pivot_ready":
            return "Pivot captured · save the prefab to the software library"
        if self.stage == "place":
            return f"Place '{selected.name if selected else 'prefab'}' by its pivot · repeated click placement"
        if self.stage == "edge":
            samples = self._along_samples(ctx, preview_limit=2)
            margin_text = f"margins {self.edge_start_margin:.3g}/{self.edge_end_margin:.3g} mm"
            offset_text = f"offset {self.edge_normal_offset:.3g} mm"
            if self._selected_curve_ids(ctx) and not samples:
                return f"Margins exceed the selected path · {margin_text} · {offset_text}"
            return (
                f"{len(self._selected_curve_ids(ctx))} curve(s) selected · {self.copy_count} copies · "
                f"{margin_text} · {offset_text}"
            )
        if self.stage == "face":
            face = self._selected_face(ctx)
            return f"{'1 face selected' if face else 'Select one face'} · grid spacing {self.face_spacing:.3g} mm"
        selection_count = self.services.selection_edit.selected_entities(ctx).entity_count
        return (
            f"{len(self.prefabs)} persistent prefab(s) · Modify selection active · "
            f"{selection_count} semantic element(s) selected"
        )

    def _sync(self, ctx: Any, *, render: bool) -> None:
        self._last_ctx = ctx
        if self.workflow.stage is DuplicateStage.EDGE:
            self._sync_preview(ctx, render=False)
        self.overlay.sync(ctx, self)
        self.services.overlay._sync_reports(ctx)
        if render:
            self.services.rendering._render(ctx, sync_overlays=True, render=True)

    def _snapped_xy(self, ctx: Any, event: Any) -> Point2:
        display_world = self.services.snap._update_cursor(ctx, event, render=False)
        semantic = self.services.coordinates.display_world_to_semantic(display_world)
        return self.services.coordinates.semantic_world_to_sketch_xy(semantic)

    def _current_cursor_xy(self, ctx: Any) -> Point2 | None:
        """Resolve the last pointer onto the active drawing plane."""

        display_plane = self._state.display_plane or self._state.plane
        if self._last_screen_pos is not None and display_plane is not None:
            try:
                display_world = plan2d.project_screen_to_locked_plane(
                    ctx, self._last_screen_pos, display_plane, event_world_pos=None
                )
                semantic = self.services.coordinates.display_world_to_semantic(display_world)
                return self.services.coordinates.semantic_world_to_sketch_xy(semantic)
            except Exception:
                pass
        display_world = getattr(self._state, "cursor_world", None)
        if display_world is not None:
            try:
                semantic = self.services.coordinates.display_world_to_semantic(display_world)
                return self.services.coordinates.semantic_world_to_sketch_xy(semantic)
            except Exception:
                pass
        return None

    def _replace_preview_primitives(self, ctx: Any, primitives: list[Any], *, render: bool) -> None:
        registry = ctx.projected_drawing.for_tool(self.id)
        next_ids = tuple(str(item.id) for item in primitives)
        next_id_set = set(next_ids)
        stale = tuple(value for value in self._visual_ids if value not in next_id_set)
        with registry.batch():
            if stale:
                registry.remove_many(stale, render=False)
            if primitives:
                registry.add_many(primitives, replace=True, render=False)
        self._visual_ids = next_ids
        if render:
            self.services.rendering._render(ctx, sync_overlays=False, render=True)

    def _along_samples(self, ctx: Any, *, preview_limit: int | None = None) -> list[_PathSample]:
        paths = self._curve_polylines(ctx)
        if not paths:
            return []
        lengths = [_polyline_lengths(path) for path in paths]
        total = sum(value[1] for value in lengths)
        if total <= 1.0e-9:
            return []
        requested = max(1, int(self.copy_count))
        start = max(0.0, float(self.edge_start_margin))
        end = total - max(0.0, float(self.edge_end_margin))
        if end < start - 1.0e-9:
            return []
        if requested > 1 and end - start <= 1.0e-9:
            return []
        if requested == 1:
            all_targets = [(start + end) * 0.5]
        else:
            span = max(0.0, end - start)
            all_targets = [start + span * index / (requested - 1) for index in range(requested)]
        if preview_limit is None or requested <= max(1, int(preview_limit)):
            targets = all_targets
        else:
            display_count = max(1, int(preview_limit))
            if display_count == 1:
                indices = [requested // 2]
            else:
                indices = sorted({round(index * (requested - 1) / (display_count - 1)) for index in range(display_count)})
            targets = [all_targets[index] for index in indices]
        samples: list[_PathSample] = []
        for target_distance in targets:
            remaining = target_distance
            for path_index, (path, (cumulative, path_length)) in enumerate(zip(paths, lengths)):
                if remaining <= path_length or path_index == len(paths) - 1:
                    samples.append(_sample_polyline_at(path, cumulative, remaining))
                    break
                remaining -= path_length
        return samples

    def _along_target(self, sample: _PathSample) -> Point2:
        """Return the final pivot target for one path sample.

        Offset is measured on the local path normal, independently from Follow.
        Mirror changes both the prefab local normal and the side of the path so
        the same positive offset remains visually attached to the mirrored side.
        """

        distance = float(self.edge_normal_offset)
        if self.mirror_along:
            distance = -distance
        if abs(distance) <= 1.0e-12:
            return sample.point
        normal_x = -math.sin(sample.tangent_angle)
        normal_y = math.cos(sample.tangent_angle)
        return (
            sample.point[0] + normal_x * distance,
            sample.point[1] + normal_y * distance,
        )

    def _sync_along_preview(self, ctx: Any, *, render: bool) -> None:
        prefab = self.selected_prefab
        samples = self._along_samples(ctx, preview_limit=160)
        if prefab is None or not samples:
            self._clear_preview(ctx, render=render)
            return
        segments: list[tuple[Point2, Point2]] = []
        pivots: list[Point2] = []
        for sample in samples:
            rotation = sample.tangent_angle if self.follow_rotation else 0.0
            target = self._along_target(sample)
            segments.extend(self._payload_preview_segments(
                prefab.payload,
                target=target,
                rotation=rotation,
                mirror_x=self.flip_along,
                mirror_y=self.mirror_along,
            ))
            pivots.append(target)
        primitives: list[Any] = []
        if segments:
            primitives.append(draw2d.segment_batch(
                _DUPLICATE_PREVIEW_BATCH_ID,
                tuple((
                    self.services.coordinates.sketch_xy_to_display_world(a),
                    self.services.coordinates.sketch_xy_to_display_world(b),
                ) for a, b in segments),
                color="#10B981",
                width_px=2.4,
                opacity=0.88,
                layer=96,
            ))
        if pivots:
            primitives.append(draw2d.point_cloud(
                _DUPLICATE_PREVIEW_POINTS_ID,
                tuple(self.services.coordinates.sketch_xy_to_display_world(point) for point in pivots),
                color="#047857",
                size_px=4.5,
                opacity=0.9,
                layer=97,
            ))
        self._replace_preview_primitives(ctx, primitives, render=render)

    def _sync_preview(self, ctx: Any, *, render: bool) -> None:
        if self.workflow.stage is DuplicateStage.EDGE:
            self._sync_along_preview(ctx, render=render)
            return
        payload: SketchPayload | None = None
        if self.workflow.stage is DuplicateStage.PLACE and self.selected_prefab is not None:
            payload = self.selected_prefab.payload
        elif self.workflow.stage is DuplicateStage.PIVOT and self.capture_selection is not None:
            payload = self.services.selection_edit.payload_from_entity_selection(
                self.capture_selection,
                pivot=self.hover_xy or (0.0, 0.0),
                source_name=self.prefab_name,
            )
        if payload is None or self.hover_xy is None:
            self._clear_preview(ctx, render=render)
            return

        preview_segments = self._payload_preview_segments(payload, target=self.hover_xy)
        primitives: list[Any] = []
        if preview_segments:
            primitives.append(draw2d.segment_batch(
                _DUPLICATE_PREVIEW_BATCH_ID,
                tuple((
                    self.services.coordinates.sketch_xy_to_display_world(a),
                    self.services.coordinates.sketch_xy_to_display_world(b),
                ) for a, b in preview_segments),
                color="#10B981",
                width_px=2.8,
                opacity=0.96,
                layer=96,
            ))
        preview_points = self._payload_preview_points(payload, target=self.hover_xy)
        if preview_points:
            primitives.append(draw2d.point_cloud(
                _DUPLICATE_PREVIEW_POINTS_ID,
                tuple(self.services.coordinates.sketch_xy_to_display_world(point) for point in preview_points),
                color="#6EE7B7",
                size_px=5.0,
                opacity=0.92,
                layer=97,
            ))
        primitives.append(draw2d.point(
            _DUPLICATE_PREVIEW_PIVOT_ID,
            self.services.coordinates.sketch_xy_to_display_world(self.hover_xy),
            color="#047857",
            size_px=9.0,
            opacity=1.0,
            layer=98,
            interaction="fixed",
            metadata={"plan_trace_role": "duplicate_preview", "projected_no_selection_actor": True},
        ))
        self._replace_preview_primitives(ctx, primitives, render=render)

    def _clear_preview(self, ctx: Any, *, render: bool) -> None:
        if self._visual_ids:
            try:
                ctx.projected_drawing.for_tool(self.id).remove_many(self._visual_ids, render=False)
            except Exception:
                pass
        self._visual_ids = ()
        if render:
            self.services.rendering._render(ctx, sync_overlays=False, render=True)

    @staticmethod
    def _payload_preview_points(
        payload: SketchPayload,
        *,
        target: Point2,
        rotation: float = 0.0,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> tuple[Point2, ...]:
        cos_a, sin_a = math.cos(rotation), math.sin(rotation)
        return tuple(
            (
                target[0] + ((-local[0]) if mirror_x else local[0]) * cos_a - ((-local[1]) if mirror_y else local[1]) * sin_a,
                target[1] + ((-local[0]) if mirror_x else local[0]) * sin_a + ((-local[1]) if mirror_y else local[1]) * cos_a,
            )
            for local in payload.points.values()
        )

    @staticmethod
    def _payload_preview_segments(
        payload: SketchPayload,
        *,
        target: Point2,
        rotation: float = 0.0,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> list[tuple[Point2, Point2]]:
        cos_a, sin_a = math.cos(rotation), math.sin(rotation)

        def transform(local: Point2) -> Point2:
            ly = -float(local[1]) if mirror_y else float(local[1])
            lx = -float(local[0]) if mirror_x else float(local[0])
            return (
                target[0] + lx * cos_a - ly * sin_a,
                target[1] + lx * sin_a + ly * cos_a,
            )

        points = {key: transform(value) for key, value in payload.points.items()}
        segments: list[tuple[Point2, Point2]] = []
        for row in payload.lines:
            if row.get("start") in points and row.get("end") in points:
                segments.append((points[row["start"]], points[row["end"]]))
        for row in payload.arcs:
            try:
                samples = sample_circular_arc_through_points(points[row["start"]], points[row["end"]], points[row["control"]], segments=24)
            except Exception:
                continue
            segments.extend(zip(samples, samples[1:]))
        for row in payload.beziers:
            try:
                samples = sample_cubic_bezier(points[row["start"]], points[row["control_1"]], points[row["control_2"]], points[row["end"]], segments=32)
            except Exception:
                continue
            segments.extend(zip(samples, samples[1:]))
        for row in payload.circles:
            try:
                center, radius_point = points[row["center"]], points[row["radius"]]
                samples = sample_circle(center, math.dist(center, radius_point), segments=48)
            except Exception:
                continue
            if samples:
                segments.extend(zip(samples, samples[1:] + samples[:1]))
        return list(segments)

    def _selected_curve_ids(self, ctx: Any) -> tuple[tuple[str, str], ...]:
        selection = self.services.selection_edit.selected_entities(ctx, expand_faces=False)
        values: list[tuple[str, str]] = []
        values.extend(("line", value) for value in selection.line_ids)
        values.extend(("arc", value) for value in selection.arc_ids)
        values.extend(("bezier", value) for value in selection.bezier_ids)
        values.extend(("circle", value) for value in selection.circle_ids)
        return tuple(values)

    def _selected_face(self, ctx: Any) -> Any | None:
        selection = self.services.selection_edit.selected_entities(ctx, expand_faces=False)
        if len(selection.face_ids) != 1:
            return None
        return self._state.sketch.faces.get(next(iter(selection.face_ids)))

    def _filter_stage_selection(self, ctx: Any) -> tuple[str, ...]:
        if self.workflow.selection_kind == "all":
            return ()
        removed: list[str] = []
        for actor_id in tuple(ctx.selection.ids()):
            actor = ctx.selection.actor(actor_id)
            role = str((getattr(actor, "metadata", {}) or {}).get("plan_trace_role") or "") if actor is not None else ""
            if self.stage == "edge" and role not in {"edge", "arc", "circle"}:
                ctx.selection.deselect(actor_id)
                removed.append(str(actor_id))
            elif self.stage == "face" and role != "face":
                ctx.selection.deselect(actor_id)
                removed.append(str(actor_id))
        return tuple(removed)

    def _clear_plan_selection(self, ctx: Any) -> None:
        try:
            ctx.selection.clear_selection(owner_tool=self.id)
        except Exception:
            pass

    def _curve_polylines(self, ctx: Any) -> list[list[Point2]]:
        """Return selected curves as ordered, connected paths.

        Selection actor order is intentionally ignored.  Array placement must
        follow sketch topology, otherwise selecting an arc chain in a different
        click order makes prefab distances jump between unrelated fragments.
        Open line/arc/Bezier fragments are stitched by authored endpoint ids;
        circles remain independent closed paths. Branches are split into
        deterministic simple paths instead of inventing an arbitrary tour.
        """

        sketch = self._state.sketch
        fragments: list[_CurveFragment] = []
        closed_paths: list[list[Point2]] = []
        for kind, entity_id in self._selected_curve_ids(ctx):
            try:
                if kind == "line" and (entity := sketch.lines.get(entity_id)) is not None:
                    samples = (
                        sketch.points[entity.start_point_id].position,
                        sketch.points[entity.end_point_id].position,
                    )
                    fragments.append(_CurveFragment(entity_id, entity.start_point_id, entity.end_point_id, tuple(samples)))
                elif kind == "arc" and (entity := sketch.arcs.get(entity_id)) is not None:
                    samples = sample_circular_arc_through_points(
                        sketch.points[entity.start_point_id].position,
                        sketch.points[entity.end_point_id].position,
                        sketch.points[entity.control_point_id].position,
                        segments=96,
                    )
                    fragments.append(_CurveFragment(entity_id, entity.start_point_id, entity.end_point_id, tuple(samples)))
                elif kind == "bezier" and (entity := sketch.beziers.get(entity_id)) is not None:
                    samples = sample_cubic_bezier(
                        sketch.points[entity.start_point_id].position,
                        sketch.points[entity.control_1_point_id].position,
                        sketch.points[entity.control_2_point_id].position,
                        sketch.points[entity.end_point_id].position,
                        segments=128,
                    )
                    fragments.append(_CurveFragment(entity_id, entity.start_point_id, entity.end_point_id, tuple(samples)))
                elif kind == "circle" and (entity := sketch.circles.get(entity_id)) is not None:
                    center = sketch.points[entity.center_point_id].position
                    radius_point = sketch.points[entity.radius_point_id].position
                    samples = list(sample_circle(center, math.dist(center, radius_point), segments=144))
                    if samples:
                        samples.append(samples[0])
                        closed_paths.append(samples)
            except Exception:
                continue

        if not fragments:
            return closed_paths

        adjacency: dict[str, list[int]] = {}
        for index, fragment in enumerate(fragments):
            adjacency.setdefault(fragment.start_point_id, []).append(index)
            adjacency.setdefault(fragment.end_point_id, []).append(index)
        for values in adjacency.values():
            values.sort(key=lambda index: fragments[index].entity_id)

        unused = set(range(len(fragments)))
        paths: list[list[Point2]] = []
        while unused:
            # Prefer an exposed endpoint so open chains have a stable direction.
            endpoint_candidates: list[tuple[str, int]] = []
            for index in unused:
                fragment = fragments[index]
                for endpoint in (fragment.start_point_id, fragment.end_point_id):
                    degree = sum(1 for candidate in adjacency.get(endpoint, ()) if candidate in unused)
                    if degree == 1:
                        endpoint_candidates.append((endpoint, index))
            if endpoint_candidates:
                current_endpoint, current_index = min(
                    endpoint_candidates,
                    key=lambda item: (item[0], fragments[item[1]].entity_id),
                )
            else:
                current_index = min(unused, key=lambda index: fragments[index].entity_id)
                current_endpoint = fragments[current_index].start_point_id

            path: list[Point2] = []
            while current_index in unused:
                fragment = fragments[current_index]
                forward = current_endpoint == fragment.start_point_id
                samples = list(fragment.points if forward else tuple(reversed(fragment.points)))
                if path and samples and math.dist(path[-1], samples[0]) <= 1.0e-8:
                    path.extend(samples[1:])
                else:
                    path.extend(samples)
                unused.remove(current_index)
                current_endpoint = fragment.end_point_id if forward else fragment.start_point_id
                candidates = [index for index in adjacency.get(current_endpoint, ()) if index in unused]
                if not candidates:
                    break
                # At a branch, end this simple path. Remaining branches are
                # emitted separately, avoiding a discontinuous artificial tour.
                if len(candidates) > 1:
                    break
                current_index = candidates[0]
            if len(path) >= 2:
                paths.append(path)

        return paths + closed_paths

    @classmethod
    def _payload_footprint_points(cls, payload: SketchPayload) -> tuple[Point2, ...]:
        """Dense local footprint used to keep face-filled prefabs inside."""

        points: list[Point2] = list(payload.points.values())
        for a, b in cls._payload_preview_segments(payload, target=(0.0, 0.0)):
            points.extend((a, b))
        # Rounded hashing keeps the footprint compact without losing boundary
        # safety for sampled arcs/circles.
        unique: dict[tuple[int, int], Point2] = {}
        for point in points:
            unique[(round(point[0] * 1.0e7), round(point[1] * 1.0e7))] = point
        return tuple(unique.values())

    def _build_along_selected(self, ctx: Any) -> bool:
        prefab = self.selected_prefab
        samples = self._along_samples(ctx)
        if prefab is None or not samples:
            if self._selected_curve_ids(ctx):
                ctx.status.info("The start/end margins leave no usable path length for the requested copies.")
            else:
                ctx.status.info("Select at least one usable edge or curve before Build.")
            return False
        before = self.services.history._snapshot_state()
        created = 0
        for sample in samples:
            rotation = sample.tangent_angle if self.follow_rotation else 0.0
            target = self._along_target(sample)
            result = self.services.selection_edit.paste_payload(
                ctx,
                prefab.payload,
                target=target,
                rotation_rad=rotation,
                mirror_x=self.flip_along,
                mirror_y=self.mirror_along,
                compile_after=False,
                select_created=False,
            )
            created += result.created_count
        if not created:
            return False
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
        self.services.history._record_snapshot_command(ctx, f"Duplicate {prefab.name} along edge", before)
        self._transition(DuplicateStage.LIBRARY, reason="build_along_complete")
        changed = tuple(ctx.selection.ids())
        self._clear_plan_selection(ctx)
        self._sync_selection_feedback(ctx, changed)
        self._clear_preview(ctx, render=False)
        self._sync(ctx, render=True)
        orientation = []
        if self.mirror_along:
            orientation.append("mirrored")
        if self.flip_along:
            orientation.append("flipped")
        orientation_text = ", ".join(orientation) if orientation else "normal"
        ctx.status.info(
            f"Created {len(samples)} '{prefab.name}' instance(s) along the path "
            f"({orientation_text}; margins {self.edge_start_margin:.3g}/{self.edge_end_margin:.3g} mm; "
            f"offset {self.edge_normal_offset:.3g} mm)."
        )
        return True

    def _build_face_fill(self, ctx: Any) -> bool:
        prefab = self.selected_prefab
        face = self._selected_face(ctx)
        if prefab is None or face is None:
            ctx.status.info("Select exactly one Plan Tracer face before Build fill.")
            return False
        outer = list(face.polygon_points)
        if len(outer) < 3:
            return False
        holes = [list(loop) for loop in tuple(face.hole_polygons or ())]
        footprint = self._payload_footprint_points(prefab.payload)
        if not footprint:
            return False

        outer_x = [point[0] for point in outer]
        outer_y = [point[1] for point in outer]
        local_x = [point[0] for point in footprint]
        local_y = [point[1] for point in footprint]
        min_pivot_x = min(outer_x) - min(local_x)
        max_pivot_x = max(outer_x) - max(local_x)
        min_pivot_y = min(outer_y) - min(local_y)
        max_pivot_y = max(outer_y) - max(local_y)
        if min_pivot_x > max_pivot_x or min_pivot_y > max_pivot_y:
            ctx.status.info("The selected prefab is larger than this face.")
            return False

        spacing = max(0.01, float(self.face_spacing))

        def centered_axis(start: float, stop: float) -> list[float]:
            extent = max(0.0, stop - start)
            count = max(1, int(math.floor(extent / spacing)) + 1)
            used = spacing * (count - 1)
            first = start + (extent - used) * 0.5
            return [first + index * spacing for index in range(count)]

        xs = centered_axis(min_pivot_x, max_pivot_x)
        ys = centered_axis(min_pivot_y, max_pivot_y)

        def fits(candidate: Point2) -> bool:
            for local in footprint:
                point = (candidate[0] + local[0], candidate[1] + local[1])
                if not _point_in_or_on_loop(point, outer):
                    return False
                if any(_point_in_loop(point, hole) for hole in holes):
                    return False
            return True

        positions: list[Point2] = []
        for y in ys:
            for x in xs:
                candidate = (x, y)
                if fits(candidate):
                    positions.append(candidate)
                    if len(positions) >= 5000:
                        break
            if len(positions) >= 5000:
                break
        if not positions:
            ctx.status.info("No complete prefab fits inside this face with the current spacing.")
            return False
        before = self.services.history._snapshot_state()
        created = 0
        for position in positions:
            result = self.services.selection_edit.paste_payload(ctx, prefab.payload, target=position, compile_after=False, select_created=False)
            created += result.created_count
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
        self.services.history._record_snapshot_command(ctx, f"Fill face with prefab {prefab.name}", before)
        self._transition(DuplicateStage.LIBRARY, reason="build_fill_complete")
        self._clear_plan_selection(ctx)
        self._sync(ctx, render=True)
        ctx.status.info(f"Filled the face with {len(positions)} complete '{prefab.name}' prefab instance(s).")
        return bool(created)


__all__ = [
    "DUPLICATE_WINDOW_ID",
    "PlanTrace2DDuplicateService",
]
