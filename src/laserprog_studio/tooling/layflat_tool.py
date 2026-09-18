# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.engraving.roles import apply_default_outline_to_unassigned
from laserprog_studio.fabrication.layflat_arranger import MeshObject, WorkMesh, group_objects, merge_group, orient_piece_flat, pack_pieces
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.inspector import BoolField, ButtonRow, ChoiceField, FloatField, HelpText, InspectorActionEvent, Panel, ReadonlyField, Section
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .ids import TOOL_LAYFLAT
from .preview_staleness import cancel_tool_preview_if_active


def _fusion_mode(value: Any) -> str:
    value = str(value or "overlap").lower()
    if value in {"none", "noe", "free", "no_merge", "no merge"}:
        return "none"
    if value in {"touch", "contact"}:
        return "touch"
    return "overlap"


def _packing_constraint(value: Any) -> str:
    value = str(value or "max_length").lower()
    if value in {"max_depth", "depth", "y"}:
        return "max_depth"
    if value in {"none", "noe", "free", "no_merge", "no merge"}:
        return "none"
    return "max_length"


def _scene_bounds_2d(meshes: tuple[Any, ...]) -> tuple[float, float]:
    xs = [float(x) for mesh in meshes for x, _y, _z in getattr(mesh, "vertices", []) or []]
    ys = [float(y) for mesh in meshes for _x, y, _z in getattr(mesh, "vertices", []) or []]
    if not xs or not ys:
        return (0.0, 0.0)
    return (max(xs) - min(xs), max(ys) - min(ys))


class LayflatCreatorTool(CreatorTool):
    """Lay-flat fabrication workflow implemented through the Creator API."""

    id = TOOL_LAYFLAT
    label = "Lay flat"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.document.ensure()
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("configure", "Configure packing", help="Choose merge and packing options."),
                ctx.workflow.step("preview", "Preview lay-flat", help="Stage the flattened scene before applying it.", optional=True),
            ),
        )
        ctx.operations.register("layflat", self._operation_layflat, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_dynamic_fields(ctx)
        self._sync_report(ctx, default="Ready. Preview flattening to stage the current scene.")
        ctx.status.info("Lay flat ready. Configure packing, then preview.")

    def on_close(self, ctx: Any) -> None:
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.cancel())

    def on_apply(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.apply(label="Lay flat applied", operation_type="layflat"))

    def _panel(self, ctx: Any) -> Panel:
        refresh = lambda _field, _value: self._on_values_changed(ctx)
        return Panel(
            "Lay flat",
            id="layflat.generator",
            owner_tool=self.id,
            description="Flatten and pack the current document using Creator API operations.",
            sections=(
                Section(
                    "Packing",
                    fields=(
                        HelpText("layflat_help", "Transforms every committed scene mesh into a flat packed board layout."),
                        FloatField("spacing_mm", "Spacing", default=5.0, min_value=0.0, max_value=1000.0, step=1.0, unit="mm", on_change=refresh),
                        ChoiceField(
                            "fusion_mode",
                            "Merging",
                            default="overlap",
                            choices=(("overlap", "Overlap only"), ("none", "No merge"), ("touch", "Touch/contact")),
                            on_change=refresh,
                        ),
                        FloatField("minimum_overlap_mm", "Minimum overlap", default=0.01, min_value=0.0, max_value=10.0, step=0.01, unit="mm", on_change=refresh),
                        FloatField("touch_tolerance_mm", "Contact tolerance", default=0.05, min_value=0.0, max_value=10.0, step=0.01, unit="mm", on_change=refresh),
                        ChoiceField(
                            "packing_constraint",
                            "Constraint",
                            default="max_length",
                            choices=(("max_length", "Max length X"), ("max_depth", "Max depth Y"), ("none", "Free")),
                            on_change=refresh,
                        ),
                        FloatField("max_length_mm", "Max X", default=300.0, min_value=1.0, max_value=10000.0, step=10.0, unit="mm", on_change=refresh),
                        FloatField("max_depth_mm", "Max Y", default=200.0, min_value=1.0, max_value=10000.0, step=10.0, unit="mm", on_change=refresh),
                        BoolField("allow_xy_rotation", "Allow XY 90° rotation", default=True, on_change=refresh),
                    ),
                ),
                Section(
                    "Preview",
                    fields=(
                        ButtonRow("layflat_actions", "Actions", buttons=(("preview", "Preview lay flat"),), callbacks={"preview": lambda event: self._preview_action(ctx, event)}),
                        ReadonlyField("layflat_report", "Report", default="Ready."),
                    ),
                ),
            ),
        )

    def _operation_layflat(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        base = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
        if not base:
            return OperationResult.failure("No mesh in the current scene.")
        src = [
            MeshObject(
                name=str(getattr(mesh, "name", f"Part {index + 1}")),
                vertices=list(getattr(mesh, "vertices", []) or []),
                triangles=list(getattr(mesh, "triangles", []) or []),
                color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
                source_object_id=str(index),
            )
            for index, mesh in enumerate(base)
        ]
        fusion = _fusion_mode(params.get("fusion_mode"))
        packing = _packing_constraint(params.get("packing_constraint"))
        spacing = max(0.0, float(params.get("spacing_mm", 5.0)))
        minimum_overlap = max(0.0, float(params.get("minimum_overlap_mm", 0.01)))
        touch_tolerance = max(0.0, float(params.get("touch_tolerance_mm", 0.05)))
        max_length = max(1.0, float(params.get("max_length_mm", 300.0)))
        max_depth = max(1.0, float(params.get("max_depth_mm", 200.0)))
        allow_rotation = bool(params.get("allow_xy_rotation", True))

        groups = group_objects(src, fusion, touch_tolerance, minimum_overlap)
        pieces = [merge_group(group, i + 1) for i, group in enumerate(groups)]
        for piece in pieces:
            orient_piece_flat(piece)
        pieces = pack_pieces(pieces, spacing, packing, max_length, max_depth, allow_rotation)
        out = tuple(WorkMesh(name=p.name, vertices=list(p.vertices), triangles=list(p.triangles), color=p.color) for p in pieces)
        changed_roles = apply_default_outline_to_unassigned(out)
        width, depth = _scene_bounds_2d(out)
        report = (
            "Lay-flat preview ready.\n"
            f"Source objects: {len(src)}\n"
            f"Parts after merge: {len(out)}\n"
            f"Mode: {fusion}\n"
            f"Packing: {packing}\n"
            f"Bounds: {width:.3f} x {depth:.3f} mm\n"
            f"Default outline roles assigned: {changed_roles}"
        )
        return OperationResult.success(
            out,
            report=report,
            metadata={"source_count": len(src), "piece_count": len(out), "bounds_2d_mm": (width, depth), "fusion_mode": fusion, "packing_constraint": packing},
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = event.values if event is not None else ctx.inspector.values()
        result = ctx.operations.layflat(inputs=(), params=values, preview=False, owner_tool=self.id)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Lay-flat operation finished."), ok=result.ok)
        if not result.ok or not result.meshes:
            ctx.status.error("; ".join(result.errors) or "Lay-flat failed.")
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label="Lay-flat preview")
        session.show_meshes(result.meshes)
        ctx.scene_selection.select_range(0, len(result.meshes))
        ctx.workflow.goto("preview")
        ctx.status.info("Lay-flat preview ready. Use Apply to keep it or Cancel to discard it.")
        return True

    def _on_values_changed(self, ctx: Any) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Lay-flat preview discarded because packing settings changed.")
        self._sync_dynamic_fields(ctx)
        self._sync_report(ctx)

    def _sync_dynamic_fields(self, ctx: Any) -> None:
        values = ctx.inspector.values()
        fusion = _fusion_mode(values.get("fusion_mode"))
        packing = _packing_constraint(values.get("packing_constraint"))
        relevant = {
            "minimum_overlap_mm": fusion == "overlap",
            "touch_tolerance_mm": fusion == "touch",
            "max_length_mm": packing == "max_length",
            "max_depth_mm": packing == "max_depth",
        }
        for field_id, active in relevant.items():
            try:
                ctx.inspector.update_field_state(field_id, enabled=active, visible=active)
            except Exception:
                pass

    def _sync_report(self, ctx: Any, *, default: str | None = None) -> None:
        try:
            count = len(ctx.document.meshes(include_preview=False)) if ctx.document.ensure() else 0
        except Exception:
            count = 0
        values = ctx.inspector.values()
        fusion = _fusion_mode(values.get("fusion_mode"))
        packing = _packing_constraint(values.get("packing_constraint"))
        mode_hint = f"Merging={fusion}; packing={packing}."
        ctx.inspector.set_display_value("layflat_report", default or f"Scene objects: {count}. {mode_hint} Click Preview lay flat to stage a packed layout.")

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("layflat_report", text)
        if ok:
            ctx.inspector.clear_error("layflat_report")
        else:
            ctx.inspector.set_error("layflat_report", text)


class LayflatTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=LayflatCreatorTool())


__all__ = ["LayflatCreatorTool", "LayflatTool"]
