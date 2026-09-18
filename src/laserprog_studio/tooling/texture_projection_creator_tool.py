# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any
from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams
from laserprog_studio.geometry_ops.texture_projection_vector import _normalize_rotation_deg
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.inspector import InspectorActionEvent, Panel
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool, MouseButton, ToolEventType

from ._texture_projection_geometry import (
    basis_from_normal as _basis_from_normal,
    display_to_world_at_depth as _display_to_world_at_depth,
    mesh_center as _mesh_center,
    mesh_span as _mesh_span,
    screen_pos as _screen_pos,
    vadd as _vadd,
    vcross as _vcross,
    vdot as _vdot,
    vlen as _vlen,
    vnorm as _vnorm,
    vscale as _vscale,
    vsub as _vsub,
    vec3_or_none as _vec3_or_none,
)
from ._texture_projection_operations import selected_indices as _selected
from ._texture_projection_operations import texture_clear_operation, texture_project_operation
from ._texture_projection_panel import build_texture_projection_panel
from ._texture_projection_params import as_bool as _as_bool
from ._texture_projection_params import stable_texture_id as _stable_texture_id
from ._texture_projection_params import texture_image_size as _texture_image_size
from ._texture_projection_params import texture_params_from_values
from ._texture_projection_projector import TextureProjectorRuntime
from .base import ToolSpec
from .ids import TOOL_TEXTURE_PROJECTION


class TextureProjectionCreatorTool(CreatorTool):
    """Texture projection implemented at the Creator API boundary.

    The public tool remains intentionally small: it owns lifecycle, inspector
    actions and preview staging, while parameters, operations and viewport
    projector interaction live in focused private modules.
    """

    id = TOOL_TEXTURE_PROJECTION
    label = "Texture projection"

    def __init__(self) -> None:
        self._projector = TextureProjectorRuntime(self)

    @property
    def _projector_drag(self) -> dict[str, Any] | None:
        """Stable view of the projector drag state."""
        return self._projector._drag

    @_projector_drag.setter
    def _projector_drag(self, value: dict[str, Any] | None) -> None:
        self._projector._drag = value

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.document.ensure()
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_objects("select", "Select parts", help="Select target meshes or click a face.", optional=True),
                ctx.workflow.step("preview", "Preview projection", help="Stage UV/texture metadata before applying it.", optional=True),
            ),
        )
        ctx.operations.register("texture_project", self._operation_texture_project, replace=True)
        ctx.operations.register("texture_clear", self._operation_texture_clear, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_report(ctx, default="Select parts, choose an image, then preview.")
        ctx.status.info("Texture projection ready. Select target parts or click a face.")

    def on_close(self, ctx: Any) -> None:
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import clear_creator_viewport_ui

                clear_creator_viewport_ui(owner, self.id, render=True)
            except Exception:
                pass

    def on_cancel(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.cancel())

    def on_apply(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.apply(label="Texture projection applied", operation_type="texture_projection"))

    def on_scene_selection_changed(self, ctx: Any) -> None:
        selected = tuple(ctx.scene_selection.selected_indices())
        if selected and ctx.inspector.panel is not None:
            try:
                ctx.inspector.update_value("target_index", int(selected[-1]), notify=False)
            except Exception:
                pass
        self._sync_report(ctx)

    def on_event(self, event: Any, ctx: Any) -> bool:
        try:
            if getattr(event, "type", None) != ToolEventType.MOUSE_RELEASE or getattr(event, "button", None) != MouseButton.LEFT:
                return False
            screen = getattr(event, "screen_pos", None)
            if screen is None:
                return False
            start = getattr(ctx.selection.state, "empty_press_start", None)
            if start is not None and max(abs(float(screen[0]) - float(start[0])), abs(float(screen[1]) - float(start[1]))) > 5.0:
                return False
            owner = getattr(ctx, "owner", None)
            picker = getattr(owner, "_pick_texture_projection_anchor_from_qt_pos", None) if owner is not None else None
            anchor = picker(float(screen[0]), float(screen[1])) if callable(picker) else None
            if anchor is None:
                return False
            idx, point, normal, cell_id = anchor
            return bool(self.preview_index(ctx, int(idx), seed_face_index=int(cell_id), projection_origin=tuple(float(v) for v in point), projection_normal=tuple(float(v) for v in normal)))
        except Exception:
            return False

    def _panel(self, ctx: Any) -> Panel:
        refresh = lambda field, value: self._on_panel_value_changed(ctx, field, value)
        return build_texture_projection_panel(
            owner_tool=self.id,
            refresh=refresh,
            preview=lambda event: self._preview_action(ctx, event),
            clear=lambda event: self._clear_action(ctx, event),
        )

    def _on_panel_value_changed(self, ctx: Any, field_id: Any = None, value: Any = None) -> None:  # noqa: ARG002
        self._sync_report(ctx)
        if ctx.inspector.panel is None:
            return
        refresh_fields = {
            "scale",
            "stretch_u",
            "stretch_v",
            "rotation_deg",
            "offset_u",
            "offset_v",
            "coverage_angle_deg",
            "repeat",
            "attach_to_mesh",
            "preserve_aspect",
            "projection_mode",
            "texture_path",
        }
        field_name = str(field_id or "")
        if field_name == "rotation_deg":
            try:
                normalized = _normalize_rotation_deg(float(value if value is not None else ctx.inspector.value("rotation_deg", 0.0)))
                current = float(ctx.inspector.value("rotation_deg", 0.0))
                if abs(current - normalized) > 1.0e-9:
                    ctx.inspector.update_value("rotation_deg", normalized, notify=False)
            except Exception:
                pass
        if field_name == "repeat" and self._refresh_current_preview_after_texture_toggle(ctx):
            return
        if field_name in refresh_fields:
            try:
                self.render_projector_ui(ctx, render=True)
            except Exception:
                pass

    def _refresh_current_preview_after_texture_toggle(self, ctx: Any) -> bool:
        """Retrace the staged texture immediately when Repeat is toggled."""

        if self._projector_drag is not None or ctx.inspector.panel is None:
            return False
        values = dict(ctx.inspector.values())
        if not str(values.get("texture_path", "") or "").strip():
            return False
        selected = tuple(ctx.scene_selection.selected_indices())
        has_anchor = values.get("seed_face_index", -1) not in (-1, "-1", None, "")
        if has_anchor:
            try:
                target = int(values.get("target_index", -1))
            except Exception:
                target = -1
            if target < 0 and selected:
                target = int(selected[-1])
                values["target_index"] = target
                try:
                    ctx.inspector.update_value("target_index", target, notify=False)
                except Exception:
                    pass
            if target < 0:
                return False
        else:
            # Multi-selection preview path: do not let a stale hidden face target
            # silently collapse the operation to one object.
            values["target_index"] = -1
            if not selected:
                return False
        return self._stage_operation_result(
            ctx,
            ctx.operations.texture_project(inputs=(), params=values, preview=False, owner_tool=self.id),
            label="Texture projection preview",
        )

    def _operation_texture_project(self, inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        return texture_project_operation(inputs, params, ctx)

    def _operation_texture_clear(self, inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        return texture_clear_operation(inputs, params, ctx)

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = dict(event.values if event is not None else ctx.inspector.values())
        selected = tuple(ctx.scene_selection.selected_indices())
        has_anchor = values.get("seed_face_index", -1) not in (-1, "-1", None, "")
        if has_anchor:
            if values.get("target_index", -1) in (-1, "-1", None, "") and selected:
                values["target_index"] = int(selected[-1])
                try:
                    ctx.inspector.update_value("target_index", int(selected[-1]), notify=False)
                except Exception:
                    pass
        else:
            # Preview selected must remain a multi-selection operation. The
            # hidden target_index is reserved for face-anchored previews.
            values["target_index"] = -1
        return self._stage_operation_result(ctx, ctx.operations.texture_project(inputs=(), params=values, preview=False, owner_tool=self.id), label="Texture projection preview")

    def preview_selected(self, ctx: Any, **overrides: Any) -> bool:
        values = dict(ctx.inspector.values()) if ctx.inspector.panel is not None else {}
        values.update({key: value for key, value in overrides.items() if value is not None})
        if "projection_origin" in overrides and overrides.get("projection_origin") is not None:
            values["projection_origin_active"] = True
        if values.get("seed_face_index", -1) in (-1, "-1", None, ""):
            values["target_index"] = -1
        return self._stage_operation_result(ctx, ctx.operations.texture_project(inputs=(), params=values, preview=False, owner_tool=self.id), label="Texture projection preview")

    def _clear_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = dict(event.values if event is not None else ctx.inspector.values())
        return self._stage_operation_result(ctx, ctx.operations.texture_clear(inputs=(), params=values, preview=False, owner_tool=self.id), label="Texture clear preview")

    def preview_index(self, ctx: Any, index: int, *, seed_face_index: int | None = None, projection_origin=None, projection_normal=None) -> bool:
        anchor_changed = False
        if seed_face_index is not None or projection_origin is not None:
            try:
                old_target = int(ctx.inspector.value("target_index", -1)) if ctx.inspector.panel is not None else -1
                old_seed = ctx.inspector.value("seed_face_index", -1) if ctx.inspector.panel is not None else -1
                old_seed_int = None if old_seed in (-1, "-1", None, "") else int(old_seed)
                anchor_changed = (old_target != int(index)) or (seed_face_index is not None and old_seed_int != int(seed_face_index))
            except Exception:
                anchor_changed = True
            try: self._projector.reset_for_new_anchor(ctx)
            except Exception: pass
        update = {"target_index": int(index)}
        if seed_face_index is not None or projection_origin is not None:
            update["projection_mode"] = "planar"
        if anchor_changed:
            # A new face click starts from a clean, clamped placement: no stale
            # huge scale, offset, stretch or 99840° rotation carried from a
            # previous image/face.
            update.update({"scale": 1.0, "stretch_u": 1.0, "stretch_v": 1.0, "offset_u": 0.0, "offset_v": 0.0, "rotation_deg": 0.0})
        if seed_face_index is not None:
            update["seed_face_index"] = int(seed_face_index)
            update["projection_origin_active"] = True
        if projection_origin is not None:
            update["projection_origin"] = tuple(float(v) for v in projection_origin)
            update["projection_origin_active"] = True
        if projection_normal is not None:
            update["projection_normal"] = tuple(float(v) for v in projection_normal)
        if ctx.inspector.panel is not None:
            try:
                ctx.inspector.update_values(update, notify=False)
            except Exception:
                pass
        ctx.scene_selection.select_indices((int(index),), active_index=int(index))
        values = dict(ctx.inspector.values()) if ctx.inspector.panel is not None else dict(update)
        values.update(update)
        return self._stage_operation_result(ctx, ctx.operations.texture_project(inputs=(), params=values, preview=False, owner_tool=self.id), label="Texture projection preview")

    def clear_selected(self, ctx: Any) -> bool:
        values = dict(ctx.inspector.values()) if ctx.inspector.panel is not None else {}
        return self._stage_operation_result(ctx, ctx.operations.texture_clear(inputs=(), params=values, preview=False, owner_tool=self.id), label="Texture clear preview")

    def params_from_context(self, ctx: Any, **overrides: Any) -> TextureProjectionParams:
        values = dict(ctx.inspector.values()) if ctx.inspector.panel is not None else {}
        for key, value in overrides.items():
            if value is not None:
                values[key] = value
        target = values.get("target_index", None)
        if values.get("seed_face_index", -1) in (-1, "-1", None, ""):
            # Keep the last face anchor from the declarative inspector. This is
            # what lets Preview selected and gizmo live-updates reuse a prior click.
            try:
                stored_target = ctx.inspector.value("target_index", -1)
                if target in (None, "", -1, "-1") or int(stored_target) == int(target):
                    for field in ("seed_face_index", "projection_origin", "projection_normal", "projection_origin_active"):
                        values[field] = ctx.inspector.value(field, values.get(field))
            except Exception:
                pass
        return texture_params_from_values(values, ctx=ctx)

    def _stage_operation_result(self, ctx: Any, result: OperationResult, *, label: str) -> bool:
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Texture operation finished."), ok=result.ok)
        if not result.ok or not result.meshes:
            ctx.status.error("; ".join(result.errors) or "Texture operation failed.")
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label=label)
        session.show_meshes(result.meshes)
        selected = tuple(int(i) for i in result.metadata.get("selected_indices", ()) if isinstance(i, int) or str(i).isdigit())
        if selected:
            ctx.scene_selection.select_indices(tuple(i for i in selected if 0 <= i < len(result.meshes)), active_index=selected[-1])
        self._sync_report(ctx, update_report=False)
        self._refresh_texture_view(ctx)
        ctx.workflow.goto("preview")
        ctx.status.info(f"{label} ready. Use Apply to keep it or Cancel to discard it.")
        return True

    def _refresh_texture_view(self, ctx: Any) -> None:
        try:
            ctx.view.set_display_mode("material", render=False)
        except Exception:
            try:
                ctx.view.refresh(full=False)
            except Exception:
                pass
        self.render_projector_ui(ctx, render=False)
        owner = getattr(ctx, "owner", None)
        if owner is None:
            return
        for method_name, kwargs in (
            ("refresh_actor_styles", {"render": False}),
            ("update_inspector", {}),
            ("update_gizmo", {"render": False}),
        ):
            method = getattr(owner, method_name, None)
            if callable(method):
                try:
                    method(**kwargs)
                except TypeError:
                    try:
                        method()
                    except Exception:
                        pass
                except Exception:
                    pass
        plotter = getattr(owner, "plotter", None)
        render = getattr(plotter, "render", None)
        if callable(render):
            try:
                render()
            except Exception:
                pass

    def _projector_state(self, ctx: Any) -> dict[str, Any] | None:
        return self._projector.state(ctx)

    def _projector_points(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._projector.points(state)

    def _render_projector_declarations(self, ctx: Any) -> dict[str, Any] | None:
        return self._projector.render_declarations(ctx)

    def render_projector_ui(self, ctx: Any, *, render: bool = True) -> None:
        return self._projector.render(ctx, render=render)

    def _handle_from_kind(self, kind: str | None) -> str:
        return self._projector.handle_from_kind(kind)

    def _axis_from_handle_id(self, handle_id: str) -> str:
        return self._projector.axis_from_handle_id(handle_id)

    def _projector_handle_screen_positions(self, ctx: Any) -> dict[str, tuple[float, float, float]]:
        return self._projector.handle_screen_positions(ctx)

    def pick_projector_handle(self, ctx: Any, qx: float, qy: float) -> tuple[str, str] | None:
        return self._projector.pick_handle(ctx, qx, qy)

    def hover_projector_handle(self, ctx: Any, qx: float, qy: float) -> bool:
        return bool(self._projector.hover_handle(ctx, qx, qy))

    def start_projector_drag(self, ctx: Any, qx: float, qy: float, *, kind: str = "texrot") -> bool:
        return bool(self._projector.start_drag(ctx, qx, qy, kind=kind))

    def update_projector_drag(self, ctx: Any, qx: float, qy: float, *, source: str = "direct") -> bool:
        return bool(self._projector.update_drag(ctx, qx, qy, source=source))

    def finish_projector_drag(self, ctx: Any) -> bool:
        return bool(self._projector.finish_drag(ctx))

    def resolve_drag_positions(self, event: Any, ctx: Any) -> dict[str, Any] | None:
        return self._projector.resolve_drag_positions(ctx, event)

    def on_native_interaction_result(self, event: Any, ctx: Any, result: Any) -> None:
        self._projector.on_native_interaction_result(ctx, event, result)


    def wants_pointer_press_passthrough(self, event: Any, ctx: Any) -> bool:
        """Let camera navigation own empty left-presses while TEX stays grab-able."""

        try:
            if getattr(event, "type", None) != ToolEventType.MOUSE_PRESS:
                return False
            if getattr(event, "button", None) != MouseButton.LEFT:
                return False
            screen = getattr(event, "screen_pos", None)
            if screen is None:
                return False
            # If a TEX handle is under the pointer, the tool must keep the press
            # so drag/rotate/stretch starts immediately. Otherwise the host camera
            # gets the event and pan/orbit is never blocked by this tool.
            picked = self.pick_projector_handle(ctx, float(screen[0]), float(screen[1]))
            return picked is None
        except Exception:
            return False

    def _sync_report(self, ctx: Any, *, default: str | None = None, update_report: bool = True) -> None:
        selected = tuple(ctx.scene_selection.selected_indices())
        summary = ", ".join(f"{int(i):02d}" for i in selected) if selected else "No mesh selected."
        ctx.inspector.set_display_value("selection_summary", summary)
        if update_report:
            ctx.inspector.set_display_value("texture_report", default or f"Selected parts: {len(selected)}\nClick a face or Preview selected.")

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("texture_report", text)
        if ok:
            ctx.inspector.clear_error("texture_report")
        else:
            ctx.inspector.set_error("texture_report", text)


class TextureProjectionTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=TextureProjectionCreatorTool())

    def preview_index(self, context: Any, index: int, **kwargs: Any) -> bool:
        return bool(self.creator.preview_index(self.tool_context(context), int(index), **kwargs))

    def preview_selected(self, context: Any, **kwargs: Any) -> bool:
        return bool(self.creator.preview_selected(self.tool_context(context), **kwargs))

    def clear_selected(self, context: Any) -> bool:
        return bool(self.creator.clear_selected(self.tool_context(context)))

    def params_from_context(self, context: Any, **overrides: Any) -> TextureProjectionParams:
        return self.creator.params_from_context(self.tool_context(context), **overrides)

    def render_projector_ui(self, context: Any, *, render: bool = True) -> None:
        return self.creator.render_projector_ui(self.tool_context(context), render=render)

    def pick_projector_handle(self, context: Any, qx: float, qy: float):
        return self.creator.pick_projector_handle(self.tool_context(context), qx, qy)

    def hover_projector_handle(self, context: Any, qx: float, qy: float) -> bool:
        return bool(self.creator.hover_projector_handle(self.tool_context(context), qx, qy))

    def start_projector_drag(self, context: Any, qx: float, qy: float, *, kind: str = "texrot") -> bool:
        return bool(self.creator.start_projector_drag(self.tool_context(context), qx, qy, kind=kind))

    def update_projector_drag(self, context: Any, qx: float, qy: float, *, source: str = "direct") -> bool:
        return bool(self.creator.update_projector_drag(self.tool_context(context), qx, qy, source=source))

    def finish_projector_drag(self, context: Any) -> bool:
        return bool(self.creator.finish_projector_drag(self.tool_context(context)))

__all__ = ["TextureProjectionCreatorTool", "TextureProjectionTool", "texture_params_from_values"]
