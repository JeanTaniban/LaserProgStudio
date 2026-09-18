# -*- coding: utf-8 -*-
"""Plan Tracer 2D Pattern editor.

This module is a full rewrite of the former Pattern overlay.  The editor now
uses the same declarative overlay contract as the placement validation UI:
fields are tool-owned API fields, text edits are captured as pending values,
and Apply collects the current window state before touching geometry.  The Qt
widget is therefore only a renderer; the Plan Tracer state remains the single
source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from laserprog_studio.tool_api.core import ToolEvent

from .constants import (
    _MOTIF_BUTTON_APPLY,
    _MOTIF_BUTTON_CLOSE,
    _MOTIF_BUTTON_NEXT,
    _MOTIF_BUTTON_KEEP_FORM,
    _MOTIF_BUTTON_PREV,
    _MOTIF_BUTTON_PRESET_DELETE,
    _MOTIF_BUTTON_PRESET_SAVE,
    _MOTIF_FIELD_ANGLE,
    _MOTIF_FIELD_ASPECT,
    _MOTIF_FIELD_CELL_SIZE,
    _MOTIF_FIELD_FACE,
    _MOTIF_FIELD_KIND,
    _MOTIF_FIELD_MARGIN,
    _MOTIF_FIELD_PRESET,
    _MOTIF_FIELD_PRESET_NAME,
    _MOTIF_FIELD_OFFSET_X,
    _MOTIF_FIELD_OFFSET_Y,
    _MOTIF_FIELD_SEED,
    _MOTIF_FIELD_STATUS,
    _MOTIF_FIELD_WALL,
    _MOTIF_OVERLAY_ID,
)
from .motif_diagnostics import collect_qt_widget_values, record_motif_overlay_event
from .motif_presets import (
    CUSTOM_PRESET_ID,
    delete_motif_preset,
    load_motif_presets,
    save_motif_preset,
)
from .patterns import PATTERN_APPLY_SEGMENT_BUDGET, PATTERN_KIND_CHOICES, PATTERN_PREVIEW_SEGMENT_BUDGET
from .services import _PlanTrace2DService


_OFFSET_GIZMO_PREFIX = "plan_trace_2d.motif.offset_handle"
_OFFSET_GIZMO_CENTER = f"{_OFFSET_GIZMO_PREFIX}:center"
_OFFSET_GIZMO_X = f"{_OFFSET_GIZMO_PREFIX}:x"
_OFFSET_GIZMO_Y = f"{_OFFSET_GIZMO_PREFIX}:y"
_OFFSET_GIZMO_HANDLES = (_OFFSET_GIZMO_CENTER, _OFFSET_GIZMO_X, _OFFSET_GIZMO_Y)
_OFFSET_HANDLES = frozenset(_OFFSET_GIZMO_HANDLES)
_OFFSET_AXIS_BY_HANDLE = {
    _OFFSET_GIZMO_CENTER: "free",
    _OFFSET_GIZMO_X: "x",
    _OFFSET_GIZMO_Y: "y",
}
_OFFSET_ACTOR_ROLE = "motif_offset"

_ASPECT_KINDS: frozenset[str] = frozenset(
    {
        "diamond",
        "brick",
        "cross",
        "star",
        "wave",
        "organic",
        "hinge_straight",
        "hinge_lattice",
        "hinge_wave",
    }
)
_SEED_KINDS: frozenset[str] = frozenset({"organic"})


@dataclass(frozen=True)
class _MotifField:
    id: str
    attr: str
    value_type: type
    label: str
    tooltip: str
    fmt: str = "{:.2f}"
    minimum: float | int | None = None
    visible_for: frozenset[str] | None = None

    def visible(self, kind: str) -> bool:
        return self.visible_for is None or str(kind) in self.visible_for


_FIELDS: tuple[_MotifField, ...] = (
    _MotifField(
        _MOTIF_FIELD_CELL_SIZE,
        "motif_cell_size",
        float,
        "Pitch / size",
        "Distance between two pattern cells, in mm.",
        minimum=0.5,
    ),
    _MotifField(
        _MOTIF_FIELD_WALL,
        "motif_wall",
        float,
        "Wall / kerf",
        "Material left between openings, in mm.",
        minimum=0.1,
    ),
    _MotifField(
        _MOTIF_FIELD_MARGIN,
        "motif_margin",
        float,
        "Edge margin",
        "Safety margin kept from the face boundary, in mm.",
        minimum=0.0,
    ),
    _MotifField(
        _MOTIF_FIELD_ANGLE,
        "motif_angle",
        float,
        "Rotation",
        "Pattern rotation around the face centre, in degrees.",
        fmt="{:.1f}",
    ),
    _MotifField(
        _MOTIF_FIELD_ASPECT,
        "motif_aspect",
        float,
        "Ratio",
        "Secondary parameter for the active pattern: length, flattening, or intensity.",
        minimum=0.05,
        visible_for=_ASPECT_KINDS,
    ),
    _MotifField(
        _MOTIF_FIELD_OFFSET_X,
        "motif_offset_x",
        float,
        "Offset X",
        "Horizontal pattern offset on the face, in mm.",
    ),
    _MotifField(
        _MOTIF_FIELD_OFFSET_Y,
        "motif_offset_y",
        float,
        "Offset Y",
        "Vertical pattern offset on the face, in mm.",
    ),
    _MotifField(
        _MOTIF_FIELD_SEED,
        "motif_seed",
        int,
        "Seed",
        "Pseudo-random seed for organic cells.",
        fmt="{:d}",
        minimum=0,
        visible_for=_SEED_KINDS,
    ),
)
_FIELDS_BY_ID: dict[str, _MotifField] = {field.id: field for field in _FIELDS}
_FIELD_ALIASES: dict[str, str] = {
    field.id: field.id for field in _FIELDS
} | {
    field.id.rsplit(".", 1)[-1]: field.id for field in _FIELDS
}

_SPECIAL_MOTIF_FIELDS = frozenset({_MOTIF_FIELD_KIND, _MOTIF_FIELD_PRESET, _MOTIF_FIELD_PRESET_NAME})

_INSPECTOR_FIELD_TO_STATE: dict[str, tuple[str, type]] = {
    "plan_trace_2d.pattern_kind": ("motif_kind", str),
    "plan_trace_2d.pattern_cell_size": ("motif_cell_size", float),
    "plan_trace_2d.pattern_wall": ("motif_wall", float),
    "plan_trace_2d.pattern_margin": ("motif_margin", float),
    "plan_trace_2d.pattern_keep_form": ("motif_keep_form", bool),
    "plan_trace_2d.pattern_angle": ("motif_angle", float),
    "plan_trace_2d.pattern_aspect": ("motif_aspect", float),
    "plan_trace_2d.pattern_seed": ("motif_seed", int),
}


def _kind_index(kind: str) -> int:
    for index, (key, _label) in enumerate(PATTERN_KIND_CHOICES):
        if key == kind:
            return index
    return 0


def _kind_label(kind: str) -> str:
    for key, label in PATTERN_KIND_CHOICES:
        if key == kind:
            return label
    return str(kind)


class PlanTrace2DMotifOverlayService(_PlanTrace2DService):
    """Dedicated Pattern editor service."""

    def _diag(
        self,
        ctx: Any,
        event: str,
        *,
        field_id: str | None = None,
        raw_value: Any | None = None,
        button_id: str | None = None,
        source: str = "tool",
        extra: dict[str, Any] | None = None,
    ) -> None:
        record_motif_overlay_event(
            ctx,
            self._state,
            event,
            window_id=_MOTIF_OVERLAY_ID,
            field_id=field_id,
            raw_value=raw_value,
            button_id=button_id,
            source=source,
            extra=extra,
        )

    # ------------------------------------------------------------------ public lifecycle

    def is_open(self) -> bool:
        return bool(getattr(self._state, "motif_overlay_visible", False))

    def has_eligible_face(self, ctx: Any) -> bool:
        if self._state.plane is None:
            return False
        return bool(self._face_ids_from_selection(ctx))

    def toggle(self, ctx: Any) -> None:
        if self.is_open():
            self.close(ctx, restore=True)
        else:
            self.open(ctx)

    def open(self, ctx: Any) -> None:
        if self._state.plane is None:
            self._status(ctx, "Pattern: lock a drawing plane first.")
            return
        face_ids = self._face_ids_from_selection(ctx)
        if not face_ids:
            self._status(ctx, "Pattern: select a face with Modify before opening the window.")
            self._sync_toolbox(ctx)
            return

        face_id = face_ids[0]

        self._state.pattern_face_id = face_id
        self._state.pattern_face_ids = face_ids
        self._state.motif_preview_face_id = face_id
        self._state.motif_preview_face_ids = face_ids
        self._state.motif_preview_baseline = self.services.history._snapshot_state()
        self._state.motif_overlay_visible = True
        self._state.motif_pending_field_values.clear()
        self._state.motif_last_status = ""

        self._diag(ctx, "open.begin", extra={"face_id": face_id, "face_ids": face_ids, "face_count": len(face_ids)})
        self._pull_inspector_values(ctx)
        self._load_existing_assignment(face_ids)
        self._push_state_to_inspector(ctx)
        self._show_window(ctx)
        self._install_offset_gizmo(ctx)
        self._preview_from_state(ctx)
        self.refresh(ctx)
        self._sync_toolbox(ctx)
        self._diag(ctx, "open.end", extra={"face_id": face_id, "face_ids": face_ids, "face_count": len(face_ids)})

    def close(self, ctx: Any, *, restore: bool = True) -> None:
        self._diag(ctx, "close.begin", extra={"restore": bool(restore)})
        baseline = getattr(self._state, "motif_preview_baseline", None)
        # Invalidate delayed preview callbacks *before* restoring the baseline.
        # Otherwise a QTimer created by a field edit can fire after Back/Close
        # and re-inject the motif the user explicitly cancelled.
        self._state.motif_overlay_visible = False
        self._state.motif_preview_generation = int(getattr(self._state, "motif_preview_generation", 0) or 0) + 1
        self._state.motif_preview_pending = False
        self._state.motif_preview_pending_reason = ""
        if restore and baseline is not None:
            self.services.history._restore_snapshot_state(ctx, baseline, render=True)
        self._clear_transients(ctx)
        try:
            ctx.overlay.hide_window(_MOTIF_OVERLAY_ID)
        except Exception:
            pass
        self._sync_toolbox(ctx)
        try:
            self.services.overlay._sync_reports(ctx)
            self.services.rendering._render(ctx, sync_overlays=True, render=True)
        except Exception:
            pass
        self._diag(ctx, "close.end", extra={"restore": bool(restore)})

    def apply(self, ctx: Any) -> None:
        """Apply the motif using the freshest overlay/window values."""

        self._diag(ctx, "apply.begin", button_id=_MOTIF_BUTTON_APPLY)
        baseline = getattr(self._state, "motif_preview_baseline", None)
        face_ids = tuple(
            str(value)
            for value in tuple(getattr(self._state, "motif_preview_face_ids", ()) or ())
            if str(value)
        )
        if not face_ids:
            face_id = str(getattr(self._state, "motif_preview_face_id", "") or "")
            face_ids = (face_id,) if face_id else ()
        if baseline is None or not face_ids:
            self.close(ctx, restore=False)
            return
        if not self._apply_window_values(ctx):
            self._diag(ctx, "apply.rejected_values", button_id=_MOTIF_BUTTON_APPLY)
            self.refresh(ctx)
            return

        # Commit through the high-performance face-hole path, not by expanding
        # every opening into sketch points/lines.  This keeps the sketch light
        # and the final face is already perforated before the global Apply.
        self.services.history._load_snapshot_contents(baseline)
        self._state.pattern_face_id = face_ids[0]
        self._state.pattern_face_ids = face_ids
        committed = self._preview_from_state(
            ctx,
            max_segments=int(getattr(self._state, "motif_apply_segment_budget", PATTERN_APPLY_SEGMENT_BUDGET) or PATTERN_APPLY_SEGMENT_BUDGET),
            persistent=True,
            reason="apply",
        )
        if not committed:
            self.services.history._restore_snapshot_state(ctx, baseline, render=True)
            self._state.motif_last_status = "Pattern not applied: no valid opening could be generated."
            self._diag(ctx, "apply.rejected_geometry", button_id=_MOTIF_BUTTON_APPLY)
            self.refresh(ctx)
            return
        self.services.history._record_snapshot_command(
            ctx, f"Pattern {_kind_label(self._state.motif_kind)}", baseline
        )
        count = int(getattr(self._state, "pattern_generated_count", 0) or 0)
        self._diag(
            ctx,
            "apply.end",
            button_id=_MOTIF_BUTTON_APPLY,
            extra={"count": count, "face_ids": face_ids, "face_count": len(face_ids)},
        )
        self._status(ctx, f"Pattern applied : {count} opening(s).")
        self._clear_transients(ctx)
        try:
            ctx.overlay.hide_window(_MOTIF_OVERLAY_ID)
        except Exception:
            pass
        self._sync_toolbox(ctx)
        try:
            self.services.overlay._sync_reports(ctx)
            self.services.rendering._render(ctx, sync_overlays=True, render=True)
        except Exception:
            pass

    def _commit_preview_geometry(self, ctx: Any) -> None:
        """Materialise the current motif preview as selectable Plan2D actors."""

        try:
            ctx.selection.clear_selection(owner_tool=self.id)
        except Exception:
            try:
                ctx.selection.clear()
            except Exception:
                pass
        try:
            from laserprog_studio.tool_api import plan2d

            changed: list[str] = []
            for line_id, line in tuple(self._state.sketch.lines.items()):
                if not bool(getattr(line, "metadata", {}).get("plan_trace_2d.pattern")):
                    continue
                start = self._state.sketch.points.get(line.start_point_id)
                end = self._state.sketch.points.get(line.end_point_id)
                if start is None or end is None:
                    continue
                actor_id = self.services.sketch_sync._line_actor_id(str(line_id))
                plan2d.register_plan_line(
                    ctx,
                    owner_tool=self.id,
                    line_id=actor_id,
                    start_world_pos=self.services.coordinates.sketch_xy_to_display_world(start.position),
                    end_world_pos=self.services.coordinates.sketch_xy_to_display_world(end.position),
                    selectable=True,
                    sketch_line_id=str(line_id),
                )
                changed.append(actor_id)
            if changed:
                plan2d.sync_plan_actor_visuals(
                    ctx,
                    owner_tool=self.id,
                    changed_actor_ids=tuple(changed),
                    position_only=False,
                    render=False,
                )
            self._state.lines = [
                (self.services.sketch_sync._line_actor_id(line_id), line_id)
                for line_id in self._state.sketch.lines
            ]
        except Exception:
            pass

    # ------------------------------------------------------------------ dispatch

    def is_motif_button(self, button_id: str) -> bool:
        return str(button_id).startswith("plan_trace_2d.motif.")

    def handle_button(self, ctx: Any, button_id: str) -> bool:
        bid = str(button_id)
        self._diag(ctx, "button", button_id=bid)
        if bid == _MOTIF_BUTTON_PREV:
            self._cycle_kind(ctx, -1)
            return True
        if bid == _MOTIF_BUTTON_NEXT:
            self._cycle_kind(ctx, +1)
            return True
        if bid == _MOTIF_BUTTON_PRESET_SAVE:
            self._save_current_preset(ctx)
            return True
        if bid == _MOTIF_BUTTON_PRESET_DELETE:
            self._delete_current_preset(ctx)
            return True
        if bid == _MOTIF_BUTTON_KEEP_FORM:
            # v177: motifs are always owned by the host face.  Keep the legacy
            # control accepted for old presets/UI bindings, but never switch to
            # the former destructive material-boundary linework mode.
            self._state.motif_keep_form = True
            self._mark_preset_modified()
            self._push_state_to_inspector(ctx)
            self._show_window(ctx)
            self._state.motif_last_status = "Pattern stays inside the selected face."
            self.refresh(ctx)
            return True
        if bid == _MOTIF_BUTTON_APPLY:
            self.apply(ctx)
            return True
        if bid == _MOTIF_BUTTON_CLOSE:
            self.close(ctx, restore=True)
            return True
        return False

    def is_motif_field(self, field_id: str) -> bool:
        fid = self._normalise_field_id(field_id)
        return fid in _FIELDS_BY_ID or fid in _SPECIAL_MOTIF_FIELDS

    def handle_field_change(self, ctx: Any, field_id: str, value: str) -> bool:
        fid = self._normalise_field_id(field_id)
        self._diag(ctx, "field.begin", field_id=fid, raw_value=value, extra={"raw_field_id": str(field_id)})
        if fid == _MOTIF_FIELD_KIND:
            return self._change_kind_from_select(ctx, value)
        if fid == _MOTIF_FIELD_PRESET:
            return self._load_selected_preset(ctx, value)
        if fid == _MOTIF_FIELD_PRESET_NAME:
            self._state.motif_preset_name = " ".join(str(value).strip().split())[:80]
            self._diag(ctx, "preset.name", field_id=fid, raw_value=value)
            return True
        field = _FIELDS_BY_ID.get(fid)
        if field is None:
            self._diag(ctx, "field.ignored", field_id=fid, raw_value=value)
            return False
        self._state.motif_pending_field_values[fid] = str(value)
        parsed = self._parse_field_value(field, value)
        if parsed is None:
            self._state.motif_last_status = f"Valeur invalide pour {field.label}: {value!r}"
            self._diag(ctx, "field.invalid", field_id=fid, raw_value=value)
            self.refresh(ctx)
            return True
        self._set_field_value(field, parsed)
        self._mark_preset_modified()
        self._state.motif_last_status = ""
        self._push_state_to_inspector(ctx)
        self._schedule_preview(ctx, reason=f"field:{fid}")
        self.refresh(ctx, update_number_fields=False)
        self._diag(ctx, "field.end", field_id=fid, raw_value=value, extra={"parsed": parsed, "preview_scheduled": True})
        return True

    def apply_inspector_change(self, ctx: Any, field_id: str, value: Any) -> None:
        mapping = _INSPECTOR_FIELD_TO_STATE.get(str(field_id))
        if mapping is None:
            return
        attr, kind = mapping
        parsed = str(value) if kind is str else self._parse_value(value, kind)
        if parsed is None:
            return
        setattr(self._state, attr, parsed)
        self._mark_preset_modified()
        if self.is_open():
            if str(field_id) == "plan_trace_2d.pattern_kind":
                self._show_window(ctx)
                self._preview_from_state(ctx, reason="inspector.kind")
                self.refresh(ctx)
            else:
                self._schedule_preview(ctx, reason=f"inspector:{field_id}")
                self.refresh(ctx, update_number_fields=False)

    # ------------------------------------------------------------------ value handling

    def _normalise_field_id(self, field_id: str) -> str:
        raw = str(field_id)
        if raw in _FIELD_ALIASES:
            return _FIELD_ALIASES[raw]
        for special in _SPECIAL_MOTIF_FIELDS:
            if raw == special or raw.endswith(special) or raw.endswith(special.rsplit(".", 1)[-1]):
                return special
        # Be deliberately tolerant of future overlay renderers that may prefix
        # fields with a window namespace.
        for known in _FIELDS_BY_ID:
            if raw.endswith(known) or raw.endswith(known.rsplit(".", 1)[-1]):
                return known
        return raw

    @staticmethod
    def _normalise_number_text(value: Any) -> str:
        text = str(value).strip().replace("\u00a0", " ").replace(",", ".")
        lowered = text.lower()
        for suffix in (" millimeters", " millimetres", " millimeter", " millimetre", " mm"):
            if lowered.endswith(suffix):
                text = text[: -len(suffix)].strip()
                break
        return text

    @classmethod
    def _parse_value(cls, value: Any, kind: type) -> Any | None:
        try:
            if kind is int:
                return int(float(cls._normalise_number_text(value)))
            if kind is float:
                return float(cls._normalise_number_text(value))
            if kind is bool:
                if isinstance(value, bool):
                    return value
                text = str(value).strip().lower()
                if text in {"1", "true", "yes", "on", "checked", "coché", "coche", "oui"}:
                    return True
                if text in {"0", "false", "no", "off", "unchecked", "décoché", "decoche", "non"}:
                    return False
                return bool(value)
            return str(value)
        except Exception:
            return None

    def _parse_field_value(self, field: _MotifField, value: Any) -> Any | None:
        parsed = self._parse_value(value, field.value_type)
        if parsed is None:
            return None
        if field.minimum is not None:
            try:
                parsed = max(parsed, field.value_type(field.minimum))
            except Exception:
                pass
        return parsed

    def _set_field_value(self, field: _MotifField, value: Any) -> None:
        try:
            if field.value_type is int:
                value = int(value)
            elif field.value_type is float:
                value = float(value)
        except Exception:
            return
        setattr(self._state, field.attr, value)

    def _apply_window_values(self, ctx: Any) -> bool:
        """Collect the current overlay values like the metric validation bar.

        Priority is deliberate:
        1. overlay-manager values,
        2. tool callback pending values,
        3. live Qt QLineEdit texts read directly from the rendered window.

        The third layer is a diagnostic safety net inspired by the validation
        overlay flush path.  If a Qt signal is broken, Apply still sees what the
        user can see in the field, and the diagnostic log will prove which layer
        diverged.
        """

        values: dict[str, str] = {}
        sources: dict[str, str] = {}
        try:
            window = ctx.overlay.window(_MOTIF_OVERLAY_ID)
        except Exception:
            window = None
        if window is not None:
            for item in tuple(getattr(window, "fields", ()) or ()):  # manager values
                fid = self._normalise_field_id(str(getattr(item, "id", "") or ""))
                if fid in _FIELDS_BY_ID:
                    values[fid] = str(getattr(item, "value", "") or "")
                    sources[fid] = "manager"
        for fid, raw in dict(getattr(self._state, "motif_pending_field_values", {}) or {}).items():
            nf = self._normalise_field_id(str(fid))
            if nf in _FIELDS_BY_ID:
                values[nf] = str(raw)
                sources[nf] = "pending"
        qt_values, qt_focus = collect_qt_widget_values(ctx, _MOTIF_OVERLAY_ID)
        for fid, raw in qt_values.items():
            nf = self._normalise_field_id(str(fid))
            if nf in _FIELDS_BY_ID:
                values[nf] = str(raw)
                sources[nf] = "qt_widget"
        self._diag(
            ctx,
            "apply.collect_values",
            button_id=_MOTIF_BUTTON_APPLY,
            extra={"collected_values": dict(values), "sources": dict(sources), "qt_focus": dict(qt_focus)},
        )
        ok = True
        parsed_values: dict[str, Any] = {}
        for fid, raw in values.items():
            field = _FIELDS_BY_ID.get(fid)
            if field is None:
                continue
            parsed = self._parse_field_value(field, raw)
            if parsed is None:
                self._state.motif_last_status = f"Valeur invalide pour {field.label}: {raw!r}"
                ok = False
                self._diag(ctx, "apply.invalid_value", field_id=fid, raw_value=raw, extra={"source": sources.get(fid, "")})
                continue
            self._set_field_value(field, parsed)
            parsed_values[fid] = parsed
        if ok:
            self._state.motif_last_status = ""
            self._push_state_to_inspector(ctx)
            self._diag(ctx, "apply.values_ok", button_id=_MOTIF_BUTTON_APPLY, extra={"parsed_values": parsed_values})
        return ok

    def _display_value(self, field: _MotifField) -> str:
        raw = getattr(self._state, field.attr, 0)
        try:
            if field.value_type is int:
                return field.fmt.format(int(raw))
            return field.fmt.format(float(raw))
        except Exception:
            return str(raw)

    # ------------------------------------------------------------------ preview

    def _schedule_preview(self, ctx: Any, *, reason: str) -> None:
        """Debounce expensive motif preview rebuilds while the user types."""

        self._state.motif_preview_generation = int(getattr(self._state, "motif_preview_generation", 0) or 0) + 1
        generation = int(self._state.motif_preview_generation)
        self._state.motif_preview_pending = True
        self._state.motif_preview_pending_reason = str(reason)
        self._diag(ctx, "preview.scheduled", extra={"generation": generation, "reason": str(reason), "delay_ms": int(getattr(self._state, "motif_preview_debounce_ms", 1000) or 1000)})
        try:
            self._update_offset_gizmo_positions(ctx)
        except Exception:
            pass
        delay_ms = max(0, int(getattr(self._state, "motif_preview_debounce_ms", 1000) or 1000))
        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(delay_ms, lambda g=generation, c=ctx: self._run_scheduled_preview(c, g))
        except Exception:
            # Headless tests may not have a running Qt event loop.  The scheduled
            # state is still observable and Apply always rebuilds from current
            # values, so skipping the timer is safer than doing expensive work on
            # every keystroke.
            pass

    def _run_scheduled_preview(self, ctx: Any, generation: int) -> bool:
        if not self.is_open():
            return False
        if int(generation) != int(getattr(self._state, "motif_preview_generation", 0) or 0):
            self._diag(ctx, "preview.skip_stale", extra={"generation": int(generation), "current_generation": int(getattr(self._state, "motif_preview_generation", 0) or 0)})
            return False
        self._state.motif_preview_pending = False
        reason = str(getattr(self._state, "motif_preview_pending_reason", "") or "scheduled")
        ok = self._preview_from_state(ctx, reason=reason)
        self.refresh(ctx)
        return bool(ok)

    def _preview_from_state(
        self,
        ctx: Any,
        *,
        max_segments: int | None = None,
        persistent: bool = False,
        reason: str = "preview",
    ) -> bool:
        baseline = getattr(self._state, "motif_preview_baseline", None)
        face_ids = tuple(
            str(value)
            for value in tuple(getattr(self._state, "motif_preview_face_ids", ()) or ())
            if str(value)
        )
        if not face_ids:
            face_id = str(getattr(self._state, "motif_preview_face_id", "") or "")
            face_ids = (face_id,) if face_id else ()
        if baseline is None or not face_ids:
            return False
        self.services.history._load_snapshot_contents(baseline)
        face_ids = tuple(face_id for face_id in face_ids if face_id in self._state.sketch.faces)
        if not face_ids:
            self._state.motif_last_status = "Les faces cibles n'existent plus."
            return False
        self._state.pattern_face_id = face_ids[0]
        self._state.pattern_face_ids = face_ids
        self._state.motif_preview_face_id = face_ids[0]
        self._state.motif_preview_face_ids = face_ids
        budget = int(max_segments if max_segments is not None else getattr(self._state, "motif_preview_segment_budget", PATTERN_PREVIEW_SEGMENT_BUDGET) or PATTERN_PREVIEW_SEGMENT_BUDGET)
        self._diag(
            ctx,
            "preview.begin",
            extra={
                "face_id": face_ids[0],
                "face_ids": face_ids,
                "face_count": len(face_ids),
                "reason": str(reason),
                "budget": budget,
                "persistent": bool(persistent),
                "keep_form": bool(getattr(self._state, "motif_keep_form", True)),
            },
        )
        ok = self.services.patterns.apply_as_union_face_holes(
            ctx,
            face_ids,
            kind=str(self._state.motif_kind),
            cell_size=max(0.5, float(self._state.motif_cell_size)),
            wall=max(0.1, float(self._state.motif_wall)),
            margin=max(0.0, float(self._state.motif_margin)),
            keep_form=bool(getattr(self._state, "motif_keep_form", True)),
            angle=float(self._state.motif_angle),
            aspect=max(0.05, float(self._state.motif_aspect)),
            seed=max(0, int(self._state.motif_seed)),
            offset_x=float(self._state.motif_offset_x),
            offset_y=float(self._state.motif_offset_y),
            max_segments=budget,
            persistent=bool(persistent),
            render=True,
        )
        self._state.pattern_face_id = face_ids[0]
        self._state.pattern_face_ids = face_ids
        if bool(getattr(self._state, "motif_segment_limit_hit", False)):
            estimated = int(getattr(self._state, "motif_estimated_segments", 0) or 0)
            used = int(getattr(self._state, "motif_segment_budget_used", 0) or 0)
            self._state.motif_last_status = f"Pattern too dense : ~{estimated} estimated segments, limit {used}. Increase the pitch or margin."
        elif ok:
            self._state.motif_last_status = ""
        self._diag(
            ctx,
            "preview.end",
            extra={
                "face_id": face_ids[0],
                "face_ids": face_ids,
                "face_count": len(face_ids),
                "ok": bool(ok),
                "count": int(getattr(self._state, "pattern_generated_count", 0) or 0),
                "limit_hit": bool(getattr(self._state, "motif_segment_limit_hit", False)),
            },
        )
        return bool(ok)

    # ------------------------------------------------------------------ overlay spec

    @staticmethod
    def _visual_api():
        from laserprog_studio.tool_api import visual

        return visual

    @staticmethod
    def _tool_button_cls() -> Any:
        from laserprog_studio.tool_api.visual import ToolButtonSpec

        return ToolButtonSpec

    def _show_window(self, ctx: Any) -> None:
        try:
            spec = self._build_window_spec()
            ctx.overlay.show_window(spec)
            self.services.overlay._last_ctx = ctx
            self._diag(ctx, "window.show", extra={"field_ids": [str(getattr(f, "id", "")) for f in getattr(spec, "fields", ())], "button_ids": [str(getattr(b, "id", "")) for b in getattr(spec, "buttons", ())]})
        except Exception as exc:
            self._diag(ctx, "window.show_error", extra={"error": repr(exc)})

    def _build_window_spec(self) -> Any:
        v = self._visual_api()
        kind = str(self._state.motif_kind)
        fields: list[Any] = [
            v.OverlayFieldSpec(
                _MOTIF_FIELD_PRESET,
                "Preset",
                str(getattr(self._state, "motif_preset_id", CUSTOM_PRESET_ID) or CUSTOM_PRESET_ID),
                kind="select",
                options=self._preset_choices(),
                tooltip="Load a named preset. Manual changes switch back to Custom / modified.",
            ),
            v.OverlayFieldSpec(
                _MOTIF_FIELD_PRESET_NAME,
                "Preset name",
                str(getattr(self._state, "motif_preset_name", "") or ""),
                kind="text",
                enabled=True,
                tooltip="Name used by Save preset. Saving an existing name updates it.",
                live=False,
            ),
            v.OverlayFieldSpec(
                _MOTIF_FIELD_KIND,
                "Pattern",
                kind,
                kind="select",
                options=tuple(PATTERN_KIND_CHOICES),
                tooltip="Choose the pattern type directly.",
            ),
            v.OverlayFieldSpec(
                _MOTIF_FIELD_FACE,
                "Target face",
                self.services.patterns.selected_face_text(),
                kind="info",
                tooltip="Face selected with Modify.",
            ),
        ]
        for field in _FIELDS:
            if not field.visible(kind):
                continue
            fields.append(
                v.OverlayFieldSpec(
                    field.id,
                    field.label,
                    self._display_value(field),
                    kind="number",
                    enabled=True,
                    tooltip=field.tooltip,
                    live=True,
                )
            )
        fields.append(
            v.OverlayFieldSpec(
                _MOTIF_FIELD_STATUS,
                "Status",
                self._status_text(),
                kind="info",
            )
        )

        ToolButton = self._tool_button_cls()
        selected_preset = str(getattr(self._state, "motif_preset_id", CUSTOM_PRESET_ID) or CUSTOM_PRESET_ID)
        buttons = [
            ToolButton(_MOTIF_BUTTON_PRESET_SAVE, "Save preset", tooltip="Save or update the named preset with the current pattern and parameters.", style="secondary"),
            ToolButton(_MOTIF_BUTTON_PRESET_DELETE, "Delete preset", tooltip="Delete the selected user preset.", style="danger", enabled=selected_preset != CUSTOM_PRESET_ID),
            ToolButton(
                _MOTIF_BUTTON_KEEP_FORM,
                "Keep forme",
                tooltip="ON: preserve the selected face outer contour. OFF: motif cuts define the resulting contour.",
                style="secondary" if bool(getattr(self._state, "motif_keep_form", True)) else "ghost",
                checkable=True,
                checked=bool(getattr(self._state, "motif_keep_form", True)),
                display_label="Keep forme ON" if bool(getattr(self._state, "motif_keep_form", True)) else "Keep forme OFF",
            ),
            ToolButton(_MOTIF_BUTTON_APPLY, "Apply", tooltip="Apply the current pattern", style="primary"),
            ToolButton(_MOTIF_BUTTON_CLOSE, "Back", tooltip="Cancel and restore the face", style="secondary"),
        ]
        return v.OverlayWindowSpec(
            id=_MOTIF_OVERLAY_ID,
            title="Pattern · face editor",
            owner_tool=self.id,
            overlay_kind="palette",
            anchor="viewport_top_right",
            width_px=500,
            movable=True,
            persistent=False,
            close_on_click_outside=False,
            fields=fields,
            buttons=buttons,
        )

    def refresh(self, ctx: Any, *, update_number_fields: bool = True) -> None:
        if not self.is_open():
            return
        try:
            window = ctx.overlay.window(_MOTIF_OVERLAY_ID)
        except Exception:
            window = None
        if window is None or not bool(getattr(window, "visible", True)):
            self._show_window(ctx)
            return
        kind = str(self._state.motif_kind)
        visible_ids = {
            field.id for field in _FIELDS if field.visible(kind)
        }
        current_ids = {
            str(getattr(field, "id", "") or "")
            for field in tuple(getattr(window, "fields", ()) or ())
            if str(getattr(field, "kind", "") or "") == "number"
        }
        if current_ids != visible_ids:
            self._show_window(ctx)
        update = getattr(ctx.overlay, "update_field", None)
        if callable(update):
            pushes: list[tuple[str, str]] = [
                (_MOTIF_FIELD_PRESET, str(getattr(self._state, "motif_preset_id", CUSTOM_PRESET_ID) or CUSTOM_PRESET_ID)),
                (_MOTIF_FIELD_PRESET_NAME, str(getattr(self._state, "motif_preset_name", "") or "")),
                (_MOTIF_FIELD_KIND, kind),
                (_MOTIF_FIELD_FACE, self.services.patterns.selected_face_text()),
            ]
            if update_number_fields:
                for field in _FIELDS:
                    if field.visible(kind):
                        pushes.append((field.id, self._display_value(field)))
            pushes.append((_MOTIF_FIELD_STATUS, self._status_text()))
            for fid, value in pushes:
                try:
                    update(_MOTIF_OVERLAY_ID, fid, value)
                except Exception:
                    pass
        try:
            ctx.overlay.set_button_enabled(
                _MOTIF_BUTTON_PRESET_DELETE,
                str(getattr(self._state, "motif_preset_id", CUSTOM_PRESET_ID) or CUSTOM_PRESET_ID) != CUSTOM_PRESET_ID,
            )
        except Exception:
            pass
        self._update_offset_gizmo_positions(ctx)
        self._diag(ctx, "refresh", extra={"visible_number_fields": sorted(visible_ids)})

    def _status_text(self) -> str:
        explicit = str(getattr(self._state, "motif_last_status", "") or "")
        if explicit:
            return explicit
        if self._state.plane is None:
            return "Lock a plane before using Pattern."
        face_ids = tuple(
            str(value)
            for value in tuple(
                getattr(self._state, "motif_preview_face_ids", ())
                or getattr(self._state, "pattern_face_ids", ())
                or ()
            )
            if str(value)
        )
        if not face_ids:
            face_id = str(getattr(self._state, "motif_preview_face_id", "") or getattr(self._state, "pattern_face_id", "") or "")
            face_ids = (face_id,) if face_id else ()
        if not face_ids:
            return "Select a face in Modify mode to enable Pattern."
        count = int(getattr(self._state, "pattern_generated_count", 0) or 0)
        if bool(getattr(self._state, "motif_preview_pending", False)):
            return "Preview pending… recalculating after 1 s without changes."
        if count <= 0:
            return "No opening fits: reduce pitch, margin, or wall."
        estimated = int(getattr(self._state, "motif_estimated_segments", 0) or 0)
        budget = int(getattr(self._state, "motif_segment_budget_used", 0) or 0)
        suffix = f" · {estimated}/{budget} segments" if budget > 0 else ""
        target = f" sur l'union de {len(face_ids)} faces" if len(face_ids) > 1 else ""
        return f"Preview : {count} opening(s){target}{suffix}. Apply to commit."

    # ------------------------------------------------------------------ selection / sync helpers

    def _face_ids_from_selection(self, ctx: Any) -> tuple[str, ...]:
        face_ids: list[str] = []
        try:
            ids = tuple(ctx.selection.ids())
        except Exception:
            ids = ()
        for actor_id in ids:
            try:
                actor = ctx.selection.actor(str(actor_id))
            except Exception:
                actor = None
            metadata = getattr(actor, "metadata", {}) if actor is not None else {}
            if str(metadata.get("plan_trace_role") or "") != "face":
                continue
            face_id = str(metadata.get("plan_trace_sketch_face_id") or "")
            if face_id and face_id in self._state.sketch.faces and face_id not in face_ids:
                face_ids.append(face_id)
        if face_ids:
            return tuple(face_ids)
        # Defensive fallback for native-click paths where the face selection state
        # has been captured semantically but the ToolCore selection registry has
        # not exposed the actor yet during the same refresh cycle.  The Pattern
        # button must become clickable immediately after selecting a valid face.
        try:
            stored_ids = tuple(str(value) for value in tuple(getattr(self._state, "pattern_face_ids", ()) or ()) if str(value))
            stored_ids = tuple(value for value in stored_ids if value in self._state.sketch.faces)
            if stored_ids:
                return stored_ids
            face_id = str(getattr(self._state, "pattern_face_id", "") or "")
            if face_id and face_id in self._state.sketch.faces:
                return (face_id,)
        except Exception:
            pass
        return ()

    def _face_id_from_selection(self, ctx: Any) -> str | None:
        """Compatibility helper for older callers/tests expecting one face."""

        face_ids = self._face_ids_from_selection(ctx)
        return face_ids[0] if face_ids else None

    def _load_existing_assignment(self, face_ids: tuple[str, ...]) -> None:
        """Load the unique compact Pattern definition already owned by a face.

        Reopening Pattern must edit/replace the existing definition, not start a
        second independent motif from stale inspector defaults.
        """

        for face_id in face_ids:
            face = self._state.sketch.faces.get(str(face_id))
            if face is None:
                continue
            assignment = self.services.patterns.assignment_for_face(face)
            if not assignment:
                continue
            mapping = {
                "kind": ("motif_kind", str),
                "cell_size": ("motif_cell_size", float),
                "wall": ("motif_wall", float),
                "margin": ("motif_margin", float),
                "angle": ("motif_angle", float),
                "aspect": ("motif_aspect", float),
                "seed": ("motif_seed", int),
                "offset_x": ("motif_offset_x", float),
                "offset_y": ("motif_offset_y", float),
            }
            for key, (attr, caster) in mapping.items():
                if key not in assignment:
                    continue
                try:
                    setattr(self._state, attr, caster(assignment[key]))
                except Exception:
                    pass
            self._state.motif_keep_form = True
            return
        # New motifs also use the face-owned representation exclusively.
        self._state.motif_keep_form = True

    def _pull_inspector_values(self, ctx: Any) -> None:
        try:
            values = ctx.inspector.values()
        except Exception:
            values = {}
        for field_id, (attr, kind) in _INSPECTOR_FIELD_TO_STATE.items():
            if field_id not in values:
                continue
            parsed = str(values[field_id]) if kind is str else self._parse_value(values[field_id], kind)
            if parsed is not None:
                setattr(self._state, attr, parsed)

    def _push_state_to_inspector(self, ctx: Any) -> None:
        inspector = getattr(ctx, "inspector", None)
        update_value = getattr(inspector, "update_value", None)
        if not callable(update_value):
            return
        for field_id, (attr, _kind) in _INSPECTOR_FIELD_TO_STATE.items():
            try:
                update_value(field_id, getattr(self._state, attr), notify=False)
            except TypeError:
                try:
                    update_value(field_id, getattr(self._state, attr))
                except Exception:
                    pass
            except Exception:
                pass

    def _preset_choices(self) -> tuple[tuple[str, str], ...]:
        choices: list[tuple[str, str]] = [(CUSTOM_PRESET_ID, "Custom / modified")]
        choices.extend((preset.id, preset.name) for preset in load_motif_presets())
        return tuple(choices)

    def _current_preset_parameters(self) -> dict[str, float | int | bool]:
        return {
            "cell_size": float(self._state.motif_cell_size),
            "wall": float(self._state.motif_wall),
            "margin": float(self._state.motif_margin),
            "keep_form": bool(self._state.motif_keep_form),
            "angle": float(self._state.motif_angle),
            "aspect": float(self._state.motif_aspect),
            "seed": int(self._state.motif_seed),
            "offset_x": float(self._state.motif_offset_x),
            "offset_y": float(self._state.motif_offset_y),
        }

    def _mark_preset_modified(self) -> None:
        self._state.motif_preset_id = CUSTOM_PRESET_ID

    def _change_kind_from_select(self, ctx: Any, value: Any) -> bool:
        kind = str(value or "").strip()
        allowed = {key for key, _label in PATTERN_KIND_CHOICES}
        if kind not in allowed:
            self._state.motif_last_status = f"Unknown pattern type: {kind!r}"
            self.refresh(ctx)
            return True
        if kind == str(self._state.motif_kind):
            return True
        self._state.motif_kind = kind
        self._mark_preset_modified()
        self._state.motif_pending_field_values.clear()
        self._state.motif_last_status = ""
        self._push_state_to_inspector(ctx)
        self._show_window(ctx)
        self._state.motif_preview_pending = False
        self._preview_from_state(ctx, reason="select_kind")
        self.refresh(ctx)
        self._diag(ctx, "kind.select", field_id=_MOTIF_FIELD_KIND, raw_value=kind)
        return True

    def _load_selected_preset(self, ctx: Any, value: Any) -> bool:
        preset_id = str(value or CUSTOM_PRESET_ID)
        if preset_id == CUSTOM_PRESET_ID:
            self._state.motif_preset_id = CUSTOM_PRESET_ID
            self.refresh(ctx, update_number_fields=False)
            return True
        preset = next((item for item in load_motif_presets() if item.id == preset_id), None)
        if preset is None:
            self._state.motif_preset_id = CUSTOM_PRESET_ID
            self._state.motif_last_status = "Preset not found. It may have been deleted."
            self._show_window(ctx)
            self.refresh(ctx)
            return True
        allowed = {key for key, _label in PATTERN_KIND_CHOICES}
        if preset.kind not in allowed:
            self._state.motif_last_status = f"Preset {preset.name!r} uses an unavailable pattern type."
            self.refresh(ctx)
            return True
        self._state.motif_kind = preset.kind
        parameter_map = {
            "cell_size": "motif_cell_size",
            "wall": "motif_wall",
            "margin": "motif_margin",
            "keep_form": "motif_keep_form",
            "angle": "motif_angle",
            "aspect": "motif_aspect",
            "seed": "motif_seed",
            "offset_x": "motif_offset_x",
            "offset_y": "motif_offset_y",
        }
        for key, attr in parameter_map.items():
            if key in preset.parameters:
                setattr(self._state, attr, preset.parameters[key])
        self._state.motif_preset_id = preset.id
        self._state.motif_preset_name = preset.name
        self._state.motif_pending_field_values.clear()
        self._state.motif_last_status = f"Preset loaded: {preset.name}."
        self._push_state_to_inspector(ctx)
        self._show_window(ctx)
        self._state.motif_preview_pending = False
        self._preview_from_state(ctx, reason="preset.load")
        self.refresh(ctx)
        self._diag(ctx, "preset.load", field_id=_MOTIF_FIELD_PRESET, raw_value=preset.id, extra={"name": preset.name})
        return True

    def _save_current_preset(self, ctx: Any) -> None:
        # Collect pending numeric edits before serialising, exactly like Apply.
        if not self._apply_window_values(ctx):
            self.refresh(ctx)
            return
        name = " ".join(str(getattr(self._state, "motif_preset_name", "") or "").strip().split())[:80]
        if not name:
            self._state.motif_last_status = "Enter a preset name before saving."
            self.refresh(ctx)
            return
        try:
            preset = save_motif_preset(
                name,
                kind=str(self._state.motif_kind),
                parameters=self._current_preset_parameters(),
            )
        except Exception as exc:
            self._state.motif_last_status = f"Unable to save preset: {exc}"
            self._diag(ctx, "preset.save_error", button_id=_MOTIF_BUTTON_PRESET_SAVE, extra={"error": repr(exc)})
            self.refresh(ctx)
            return
        self._state.motif_preset_id = preset.id
        self._state.motif_preset_name = preset.name
        self._state.motif_last_status = f"Preset saved: {preset.name}."
        self._show_window(ctx)
        self.refresh(ctx)
        self._diag(ctx, "preset.save", button_id=_MOTIF_BUTTON_PRESET_SAVE, extra={"preset_id": preset.id, "name": preset.name})

    def _delete_current_preset(self, ctx: Any) -> None:
        preset_id = str(getattr(self._state, "motif_preset_id", CUSTOM_PRESET_ID) or CUSTOM_PRESET_ID)
        if preset_id == CUSTOM_PRESET_ID:
            self._state.motif_last_status = "Select a saved preset before deleting it."
            self.refresh(ctx)
            return
        name = str(getattr(self._state, "motif_preset_name", "") or "")
        try:
            deleted = delete_motif_preset(preset_id)
        except Exception as exc:
            deleted = False
            self._diag(ctx, "preset.delete_error", button_id=_MOTIF_BUTTON_PRESET_DELETE, extra={"error": repr(exc)})
        self._state.motif_preset_id = CUSTOM_PRESET_ID
        self._state.motif_last_status = f"Preset deleted: {name}." if deleted else "Preset was already absent."
        self._show_window(ctx)
        self.refresh(ctx)
        self._diag(ctx, "preset.delete", button_id=_MOTIF_BUTTON_PRESET_DELETE, extra={"preset_id": preset_id, "deleted": bool(deleted)})

    def _cycle_kind(self, ctx: Any, delta: int) -> None:
        if not PATTERN_KIND_CHOICES:
            return
        index = (_kind_index(str(self._state.motif_kind)) + int(delta)) % len(PATTERN_KIND_CHOICES)
        self._state.motif_kind = PATTERN_KIND_CHOICES[index][0]
        self._mark_preset_modified()
        self._state.motif_pending_field_values.clear()
        self._push_state_to_inspector(ctx)
        self._show_window(ctx)
        self._state.motif_preview_pending = False
        self._preview_from_state(ctx, reason="cycle_kind")
        self.refresh(ctx)

    def _clear_transients(self, ctx: Any) -> None:
        self._state.motif_overlay_visible = False
        self._state.motif_preview_generation = int(getattr(self._state, "motif_preview_generation", 0) or 0) + 1
        self._state.motif_preview_pending = False
        self._state.motif_preview_pending_reason = ""
        try:
            self.services.patterns._clear_preview_linework(ctx)
        except Exception:
            pass
        self._state.motif_overlay_visible = False
        self._state.motif_preview_baseline = None
        self._state.motif_preview_face_id = None
        self._state.motif_preview_face_ids = ()
        self._state.motif_pending_field_values.clear()
        self._state.motif_last_status = ""
        self._cancel_offset_drag()
        self._remove_offset_gizmo(ctx)

    def _sync_toolbox(self, ctx: Any) -> None:
        try:
            self.services.overlay._sync_reports(ctx)
        except Exception:
            pass

    @staticmethod
    def _status(ctx: Any, text: str) -> None:
        try:
            ctx.status.info(text)
        except Exception:
            pass

    # ------------------------------------------------------------------ offset gizmo

    def _face_centroid_uv(self) -> tuple[float, float] | None:
        face_ids = tuple(
            str(value)
            for value in tuple(
                getattr(self._state, "motif_preview_face_ids", ())
                or getattr(self._state, "pattern_face_ids", ())
                or ()
            )
            if str(value)
        )
        if not face_ids:
            face_id = str(getattr(self._state, "motif_preview_face_id", "") or getattr(self._state, "pattern_face_id", "") or "")
            face_ids = (face_id,) if face_id else ()
        if not face_ids:
            return None
        baseline = getattr(self._state, "motif_preview_baseline", None)
        sketch = baseline.sketch if baseline is not None else self._state.sketch
        faces = tuple(sketch.faces[face_id] for face_id in face_ids if face_id in sketch.faces)
        if not faces:
            return None
        try:
            footprint = self.services.patterns._union_face_footprint(
                faces,
                ignore_existing_pattern_holes=True,
            )
            if footprint is not None and not getattr(footprint, "is_empty", False):
                centroid = footprint.centroid
                return (float(centroid.x), float(centroid.y))
        except Exception:
            pass

        weighted_x = 0.0
        weighted_y = 0.0
        total_area = 0.0
        fallback_points: list[tuple[float, float]] = []
        for face in faces:
            points = tuple((float(x), float(y)) for x, y in tuple(getattr(face, "polygon_points", ()) or ()))
            if len(points) < 3:
                fallback_points.extend(points)
                continue
            area_acc = 0.0
            cx = 0.0
            cy = 0.0
            for index, (x0, y0) in enumerate(points):
                x1, y1 = points[(index + 1) % len(points)]
                cross = x0 * y1 - x1 * y0
                area_acc += cross
                cx += (x0 + x1) * cross
                cy += (y0 + y1) * cross
            signed_area = area_acc * 0.5
            if abs(signed_area) <= 1.0e-9:
                fallback_points.extend(points)
                continue
            centroid_x = cx / (6.0 * signed_area)
            centroid_y = cy / (6.0 * signed_area)
            area = abs(signed_area)
            weighted_x += centroid_x * area
            weighted_y += centroid_y * area
            total_area += area
        if total_area > 1.0e-9:
            return (weighted_x / total_area, weighted_y / total_area)
        if fallback_points:
            return (
                sum(x for x, _ in fallback_points) / len(fallback_points),
                sum(y for _, y in fallback_points) / len(fallback_points),
            )
        return None

    def _gizmo_positions_world(self) -> dict[str, tuple[float, float, float]] | None:
        centroid = self._face_centroid_uv()
        if centroid is None:
            return None
        ox = float(self._state.motif_offset_x)
        oy = float(self._state.motif_offset_y)
        step = max(float(self._state.motif_cell_size) * 0.85, 4.0)
        try:
            center = self.services.coordinates.sketch_xy_to_display_world((centroid[0] + ox, centroid[1] + oy))
            arrow_x = self.services.coordinates.sketch_xy_to_display_world((centroid[0] + ox + step, centroid[1] + oy))
            arrow_y = self.services.coordinates.sketch_xy_to_display_world((centroid[0] + ox, centroid[1] + oy + step))
        except Exception:
            return None
        return {
            _OFFSET_GIZMO_CENTER: tuple(center),
            _OFFSET_GIZMO_X: tuple(arrow_x),
            _OFFSET_GIZMO_Y: tuple(arrow_y),
        }

    def _offset_actor_metadata(self, handle_id: str) -> dict[str, Any]:
        axis = _OFFSET_AXIS_BY_HANDLE.get(str(handle_id), "free")
        try:
            from laserprog_studio.tool_api.styles import InteractionVisualState, LineStyleId, PointStyleId
            from laserprog_studio.tool_api.ui_motifs import API_UI_VISIBLE_METADATA_KEY
        except Exception:
            return {
                "motif_family": "plan_trace_2d",
                "motif_kind": "handle",
                "plan_trace_role": _OFFSET_ACTOR_ROLE,
                "motif_offset_axis": axis,
                "selection_priority": 220,
                "api_ui_visible": True,
            }
        point_style = PointStyleId.SOLID.value if axis == "free" else PointStyleId.TRANSLATE_ARROW.value
        return {
            "motif_family": "plan_trace_2d",
            "motif_kind": "handle",
            "plan_trace_role": _OFFSET_ACTOR_ROLE,
            "motif_offset_axis": axis,
            "point_style": point_style,
            "line_style": LineStyleId.GRABBABLE.value,
            "visual_state": InteractionVisualState.AUTO.value,
            "base_radius_px": 15 if axis == "free" else 13,
            "kind_suffix": f"motif_offset_{axis}",
            "selection_priority": 220,
            API_UI_VISIBLE_METADATA_KEY: True,
        }

    def _register_offset_actor(self, ctx: Any, handle_id: str, position: tuple[float, float, float]) -> None:
        try:
            from laserprog_studio.tool_api import projected_drawing as draw2d
            from laserprog_studio.tool_api.styles import PointStyleId

            axis = _OFFSET_AXIS_BY_HANDLE.get(str(handle_id), "free")
            point_style = PointStyleId.SOLID.value if axis == "free" else PointStyleId.TRANSLATE_ARROW.value
            display_plane = self._state.display_plane or self._state.plane
            if axis == "x" and display_plane is not None:
                direction = tuple(float(v) for v in display_plane.u_axis)
            elif axis == "y" and display_plane is not None:
                direction = tuple(float(v) for v in display_plane.v_axis)
            else:
                direction = (1.0, 0.0, 0.0)
            primitive = draw2d.handle(
                str(handle_id),
                tuple(float(v) for v in position),
                shape=point_style,
                direction=direction,
                size_px=30.0 if axis == "free" else 26.0,
                interaction="grabbable",
                hit_radius_px=22.0 if axis == "free" else 20.0,
                metadata=self._offset_actor_metadata(str(handle_id)),
            )
            ctx.projected_drawing.for_tool(self.id).add(primitive, replace=True, render=False)
        except Exception:
            pass

    def _sync_offset_gizmo_visuals(
        self,
        ctx: Any,
        *,
        changed_actor_ids: tuple[str, ...] = _OFFSET_GIZMO_HANDLES,
        position_only: bool = False,
        render: bool = False,
    ) -> None:
        try:
            from laserprog_studio.tool_api.plan2d.actors import sync_plan_actor_visuals

            sync_plan_actor_visuals(
                ctx,
                owner_tool=self.id,
                changed_actor_ids=changed_actor_ids,
                position_only=position_only,
                render=render,
            )
        except Exception:
            try:
                if render:
                    ctx.request_light_render()
            except Exception:
                pass

    def _install_offset_gizmo(self, ctx: Any) -> None:
        positions = self._gizmo_positions_world()
        if positions is None:
            return
        for handle_id, position in positions.items():
            self._register_offset_actor(ctx, handle_id, position)
        self._sync_offset_gizmo_visuals(ctx, position_only=False, render=False)

    def _update_offset_gizmo_positions(self, ctx: Any) -> None:
        positions = self._gizmo_positions_world()
        if positions is None:
            return
        registry = ctx.projected_drawing.for_tool(self.id)
        changed: list[str] = []
        updates: dict[str, tuple[float, float, float]] = {}
        for handle_id, position in positions.items():
            if registry.get(handle_id) is None:
                self._register_offset_actor(ctx, handle_id, position)
                changed.append(handle_id)
            else:
                updates[handle_id] = tuple(float(v) for v in position)
        if updates:
            registry.update_positions(updates, render=False)
            changed.extend(updates)
        if changed:
            self._sync_offset_gizmo_visuals(ctx, changed_actor_ids=tuple(changed), position_only=True, render=False)

    def _remove_offset_gizmo(self, ctx: Any) -> None:
        try:
            ctx.projected_drawing.for_tool(self.id).remove_many(_OFFSET_GIZMO_HANDLES, render=False)
        except Exception:
            pass

    def _cancel_offset_drag(self) -> None:
        self._state.motif_offset_drag_axis = None
        self._state.motif_offset_drag_start_offset = None
        self._state.motif_offset_drag_start_uv = None

    # ------------------------------------------------------------------ native offset interaction

    def is_offset_actor_id(self, actor_id: str) -> bool:
        return str(actor_id) in _OFFSET_HANDLES

    def _event_uv(self, ctx: Any, event: ToolEvent) -> tuple[float, float] | None:
        world_pos = getattr(event, "world_pos", None)
        if world_pos is not None:
            try:
                return self.services.coordinates.semantic_world_to_sketch_xy(world_pos)
            except Exception:
                pass
        screen_pos = getattr(event, "screen_pos", None)
        if screen_pos is not None:
            return self._screen_to_uv(ctx, screen_pos)
        return None

    def _grabbed_offset_ids(self, ctx: Any, result: Any | None = None) -> tuple[str, ...]:
        values: tuple[Any, ...] = ()
        if result is not None:
            values = tuple(getattr(result, "grabbed_ids", ()) or ())
        if not values:
            try:
                values = tuple(ctx.selection.state.grabbed_ids or ())
            except Exception:
                values = ()
        return tuple(str(value) for value in values if str(value) in _OFFSET_HANDLES)

    def handle_event(self, ctx: Any, event: ToolEvent) -> bool:
        if not self.is_open():
            return False
        try:
            if not any(self.is_offset_actor_id(actor.id) for actor in ctx.selection.actors(owner_tool=self.id)):
                return False
            from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event

            result = handle_native_creator_ui_event(
                event,
                ctx,
                owner_tool=self.id,
                world_to_screen=getattr(ctx.viewport, "world_to_screen", None),
                render=False,
                drag_position_resolver=self.resolve_drag_positions,
            )
            self.handle_native_interaction_result(ctx, event, result)
            if getattr(result, "action", "") == "hover":
                return False
            return bool(getattr(result, "handled", False) or getattr(result, "selection_cleared", False))
        except Exception:
            return False

    def begin_offset_drag_from_native(self, ctx: Any, event: ToolEvent, grabbed_ids: tuple[str, ...]) -> bool:
        if not grabbed_ids:
            return False
        handle_id = str(grabbed_ids[0])
        axis = _OFFSET_AXIS_BY_HANDLE.get(handle_id, "free")
        start_uv = self._event_uv(ctx, event)
        if start_uv is None:
            center = self._face_centroid_uv()
            if center is None:
                return False
            start_uv = (center[0] + float(self._state.motif_offset_x), center[1] + float(self._state.motif_offset_y))
        self._state.motif_offset_drag_axis = axis
        self._state.motif_offset_drag_start_offset = (float(self._state.motif_offset_x), float(self._state.motif_offset_y))
        self._state.motif_offset_drag_start_uv = start_uv
        return True

    def resolve_drag_positions(self, event: ToolEvent, ctx: Any) -> Mapping[str, tuple[float, float, float]] | None:
        if not self.is_open():
            return None
        grabbed_ids = self._grabbed_offset_ids(ctx)
        if not grabbed_ids:
            return None
        if getattr(self._state, "motif_offset_drag_axis", None) is None:
            self.begin_offset_drag_from_native(ctx, event, grabbed_ids)
        axis = getattr(self._state, "motif_offset_drag_axis", None) or _OFFSET_AXIS_BY_HANDLE.get(grabbed_ids[0], "free")
        start_uv = getattr(self._state, "motif_offset_drag_start_uv", None)
        start_offset = getattr(self._state, "motif_offset_drag_start_offset", None)
        cursor_uv = self._event_uv(ctx, event)
        if cursor_uv is None or start_uv is None or start_offset is None:
            return None
        du = float(cursor_uv[0]) - float(start_uv[0])
        dv = float(cursor_uv[1]) - float(start_uv[1])
        new_x = float(start_offset[0]) + (du if axis in {"x", "free"} else 0.0)
        new_y = float(start_offset[1]) + (dv if axis in {"y", "free"} else 0.0)
        self._state.motif_offset_x = new_x
        self._state.motif_offset_y = new_y
        self._mark_preset_modified()
        self._state.motif_pending_field_values[_MOTIF_FIELD_OFFSET_X] = f"{new_x:.3f}"
        self._state.motif_pending_field_values[_MOTIF_FIELD_OFFSET_Y] = f"{new_y:.3f}"
        self._push_state_to_inspector(ctx)
        return self._gizmo_positions_world()

    def handle_native_interaction_result(self, ctx: Any, event: ToolEvent, result: Any) -> bool:
        if not self.is_open():
            return False
        action = str(getattr(result, "action", "") or "")
        grabbed_ids = self._grabbed_offset_ids(ctx, result)
        hit = getattr(result, "hit", None)
        hit_id = str(getattr(hit, "actor_id", "") or "")
        if hit_id not in _OFFSET_HANDLES and not grabbed_ids:
            return False
        if action == "grab":
            self.begin_offset_drag_from_native(ctx, event, grabbed_ids or (hit_id,))
            return True
        if action == "drag":
            self.refresh(ctx)
            return True
        if action == "release":
            self._cancel_offset_drag()
            self._state.motif_preview_pending = False
            self._preview_from_state(ctx, reason="offset.release")
            self.refresh(ctx)
            return True
        if action in {"select", "hover"}:
            self.refresh(ctx)
            return True
        return False

    def _screen_to_uv(self, ctx: Any, screen_pos: tuple[float, float]) -> tuple[float, float] | None:
        snap = getattr(self.services, "snap", None)
        update = getattr(snap, "_update_cursor", None)
        if callable(update):
            try:
                from laserprog_studio.tool_api.core import ToolEventType

                update(ctx, ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=tuple(screen_pos)), render=False)
            except Exception:
                pass
        cursor_world = getattr(self._state, "cursor_world", None)
        if cursor_world is None:
            return None
        try:
            return self.services.coordinates.semantic_world_to_sketch_xy(cursor_world)
        except Exception:
            return None


__all__ = ["PlanTrace2DMotifOverlayService"]
