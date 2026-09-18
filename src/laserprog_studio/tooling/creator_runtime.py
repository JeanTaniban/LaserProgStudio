# -*- coding: utf-8 -*-
"""Creator-tool lifecycle/runtime bridge shared by tool_api and built-ins.

This module intentionally lives outside ``tool_api`` so built-in tools can use
Creator API mechanics without creating an import cycle through the tool registry.
The public API re-exports these classes from ``laserprog_studio.tool_api``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from laserprog_studio.tool_core import ToolContext, ToolEvent

from .base import ToolSpec

if TYPE_CHECKING:  # pragma: no cover
    from laserprog_studio.tool_core.context import ToolContext as _ToolContext


class CreatorTool:
    """Small base class for Creator API tools.

    Native Creator UI actors are handled by :class:`CreatorStudioToolAdapter`
    before ``on_event`` is called.  Tool implementations should register
    official actors/motifs and keep ``on_event`` for domain-specific actions;
    they do not own hover/select/grab rendering, drag fast paths or camera UI
    refresh policy.
    """

    id = "creator_tool"
    label = "Creator Tool"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        tool_id = str(getattr(cls, "id", "")).strip()
        if not tool_id:
            raise ValueError(f"{cls.__name__}.id must be non-empty.")

    @property
    def owner_id(self) -> str:
        return str(self.id)

    def registry(self, ctx: ToolContext):
        from laserprog_studio.tool_api import actors

        return actors.registry(ctx, self.owner_id)

    def open(self, ctx: ToolContext) -> None:
        self.on_open(ctx)

    def close(self, ctx: ToolContext) -> None:
        try:
            self.on_close(ctx)
        finally:
            ctx.cleanup_tool(self.id)

    def cancel(self, ctx: ToolContext) -> bool:
        handled = self.on_cancel(ctx)
        ctx.cleanup_tool(self.id)
        return handled

    def apply(self, ctx: ToolContext) -> bool:
        return self.on_apply(ctx)

    def on_open(self, ctx: ToolContext) -> None:  # noqa: ARG002
        return None

    def on_close(self, ctx: ToolContext) -> None:  # noqa: ARG002
        return None

    def on_event(self, event: ToolEvent, ctx: ToolContext) -> bool:  # noqa: ARG002
        return False

    def on_cancel(self, ctx: ToolContext) -> bool:  # noqa: ARG002
        return False

    def on_apply(self, ctx: ToolContext) -> bool:  # noqa: ARG002
        return False

    def on_scene_selection_changed(self, ctx: ToolContext) -> None:  # noqa: ARG002
        """Called when the host scene selection changes while the tool is open."""
        return None

    def on_overlay_button_clicked(self, button_id: str, ctx: ToolContext) -> None:  # noqa: ARG002
        """Called when a declarative overlay button owned by the active tool changes.

        This keeps overlay palettes reactive without making tools depend on Qt
        widgets.  The overlay manager still owns checked/exclusive state; tools
        can mirror the selected enum into their own domain state and reports.
        """

        return None

    def on_overlay_field_changed(
        self,
        window_id: str,
        field_id: str,
        value: str,
        ctx: ToolContext,  # noqa: ARG002
    ) -> bool:
        """Called when an editable declarative overlay field changes.

        The Qt overlay layer already owns the widget and manager value.  Creator
        tools that need live previews or pending-value tracking can consume this
        callback and return ``True`` to keep the focused QLineEdit stable instead
        of letting the generic adapter resync/rebuild after focus-out.
        """

        return False

    def wants_native_actor_interaction(self, event: ToolEvent, ctx: ToolContext) -> bool:  # noqa: ARG002
        """Whether the Creator actor runtime may consume this event.

        Most Creator tools can leave this enabled at all times.  CAD-like tools
        with explicit draw/modify modes can return ``False`` while drawing so a
        click on an existing actor becomes a geometric snap/input instead of a
        selection/grab gesture.
        """

        return True

    def on_native_interaction_result(self, event: ToolEvent, ctx: ToolContext, result: Any) -> None:  # noqa: ARG002
        """Observe native selection/grab events after the API has processed them."""

        return None


@dataclass(slots=True)
class CreatorStudioToolAdapter:
    """Wrap a :class:`CreatorTool` as a runtime ``StudioTool``."""

    spec: ToolSpec
    creator: CreatorTool

    def can_open(self, context: Any, selected_count: int) -> bool:
        count = int(selected_count)
        if not self.spec.requires_selection:
            return True
        if count == 0 and self.spec.open_without_initial_selection and context is not None:
            # Creator tools can open into an explicit pick workflow even before
            # the first scene object is selected. A ``None`` context is kept as a
            # pure registry validation path for static registry tests.
            return True
        if self.spec.selection_policy == "single":
            return count == 1 or (count >= 1 and self.spec.allows_multi_selection)
        return count >= 1

    def selection_error_message(self, context: Any) -> str:  # noqa: ARG002
        if self.spec.selection_policy == "single":
            return f"Select one target part before opening {self.spec.label}."
        if self.spec.selection_policy == "multi":
            return f"Select at least one target part before opening {self.spec.label}."
        return ""

    def default_parameters(self) -> dict[str, Any]:
        return self.spec.default_parameters()

    def validate_parameters(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.spec.validate_parameters(values)

    def tool_context(self, context: Any) -> ToolContext:
        ctx = getattr(context, "tool_context", None)
        if not isinstance(ctx, ToolContext):
            ctx = ToolContext()
        try:
            setattr(context, "tool_context", ctx)
        except Exception:
            pass
        scene = getattr(context, "active_scene", None)
        if scene is None:
            scene = getattr(context, "scene", None)
        if scene is not None:
            ctx.document.bind(scene)
            ctx.scene = scene
        owner = getattr(context, "owner", None)
        if owner is not None:
            try:
                attach_owner = getattr(ctx, "attach_owner", None)
                if callable(attach_owner):
                    attach_owner(owner)
                else:
                    setattr(ctx, "owner", owner)
            except Exception:
                pass
            # The right-side declarative panel is built by the Qt window, not by
            # AppContext. Keep the active ToolContext visible from both objects
            # so panels created before tool activation can refresh after on_open.
            try:
                setattr(owner, "tool_context", ctx)
            except Exception:
                pass
            try:
                # Do not allocate and install fresh projection closures on every
                # mouse event.  The scene snap screen-index cache keys include the
                # viewport projection identity; replacing these functions per event
                # makes the whole tool chain look unstable even when the camera and
                # scene are unchanged.  Keep one adapter per owner and refresh only
                # when the host owner object changes.
                if getattr(ctx.viewport, "_creator_projection_owner", None) is not owner:
                    def _creator_world_to_screen(world_pos):
                        try:
                            x, y_vtk, _z = owner._world_to_display(tuple(float(v) for v in world_pos))
                            h = float(owner.plotter.height())
                            return (float(x), float(h) - float(y_vtk))
                        except Exception:
                            return (float(world_pos[0]), float(world_pos[1]))

                    def _creator_screen_to_world_on_plane(screen_pos, plane_or_depth=0.0):
                        qx, qy = float(screen_pos[0]), float(screen_pos[1])
                        h = float(owner.plotter.height())
                        vtk_y = h - qy
                        if hasattr(plane_or_depth, "depth"):
                            try:
                                from laserprog_studio.planar_tools import plane_to_world, clamp_world_point_to_plane

                                plane = plane_or_depth
                                origin = plane_to_world(plane, 0.0, 0.0)
                                _sx, _sy, display_depth = owner._world_to_display(tuple(float(v) for v in origin))
                                world = owner._display_to_world_at_depth(qx, vtk_y, float(display_depth))
                                return clamp_world_point_to_plane(plane, tuple(float(v) for v in world))
                            except Exception:
                                pass
                            depth = float(getattr(plane_or_depth, "depth", 0.0))
                        else:
                            depth = float(plane_or_depth)
                        try:
                            world = owner._display_to_world_at_depth(qx, vtk_y, depth)
                            return tuple(float(v) for v in world)
                        except Exception:
                            return (qx, qy, depth)

                    ctx.viewport.world_to_screen = _creator_world_to_screen
                    ctx.viewport.screen_to_world_on_plane = _creator_screen_to_world_on_plane
                    ctx.viewport._creator_projection_owner = owner
                    _increment_perf(ctx, "creator.viewport_projection.install")
                else:
                    _increment_perf(ctx, "creator.viewport_projection.reuse")
                try:
                    ctx.viewport.plotter = owner.plotter
                except Exception:
                    pass
                try:
                    from laserprog_studio.application.creator_scene_picking import bind_creator_scene_picking

                    bind_creator_scene_picking(ctx, owner)
                except Exception:
                    pass
            except Exception:
                pass
            selection_state = getattr(context, "selection", None)
            if selection_state is not None:
                try:
                    setattr(ctx, "selection_state", selection_state)
                except Exception:
                    pass
        return ctx

    def on_open(self, context: Any) -> None:
        self.creator.open(self.tool_context(context))

    def on_close(self, context: Any, *, render: bool = False) -> None:  # noqa: ARG002
        self.creator.close(self.tool_context(context))

    def _handle_native_creator_ui_event(self, event: Any, ctx: ToolContext) -> bool:
        """Run the mandatory Creator API actor runtime before tool code.

        This makes hover/select/grab, drag fast-path rendering and empty-click
        selection clearing native to the API.  A tool author cannot accidentally
        replace the optimized interaction path by forgetting which refresh helper
        to call from ``on_event``.
        """
        try:
            owner_tool = self.creator.owner_id
            if not ctx.selection.actors(owner_tool=owner_tool):
                return False
            wants_native = getattr(self.creator, "wants_native_actor_interaction", None)
            if callable(wants_native) and not bool(wants_native(event, ctx)):
                return False
            from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event

            drag_resolver = getattr(self.creator, "resolve_drag_positions", None)
            result = handle_native_creator_ui_event(
                event,
                ctx,
                owner_tool=owner_tool,
                world_to_screen=getattr(ctx.viewport, "world_to_screen", None),
                render=True,
                drag_position_resolver=drag_resolver if callable(drag_resolver) else None,
            )
            native_hook = getattr(self.creator, "on_native_interaction_result", None)
            if callable(native_hook):
                try:
                    native_hook(event, ctx, result)
                except Exception:
                    pass
            # Hover is a native visual update, not an exclusive gesture.
            # Domain tools such as Plan tracer still need the same mouse-move
            # event to update their cursor/snap position.
            if getattr(result, "action", "") == "hover":
                return False
            return bool(result.handled or result.selection_cleared)
        except Exception:
            return False

    def on_event(self, event: Any, context: Any) -> bool:
        ctx = self.tool_context(context)
        if self._handle_native_creator_ui_event(event, ctx):
            return True
        return bool(self.creator.on_event(event, ctx))


    def can_apply(self, context: Any) -> bool:
        callback = getattr(self.creator, "can_apply", None)
        if not callable(callback):
            return False
        try:
            return bool(callback(self.tool_context(context)))
        except Exception:
            return False

    def apply(self, context: Any) -> bool:
        return bool(self.creator.apply(self.tool_context(context)))

    def cancel(self, context: Any) -> bool:
        return bool(self.creator.cancel(self.tool_context(context)))

    def on_scene_selection_changed(self, context: Any) -> None:
        self.creator.on_scene_selection_changed(self.tool_context(context))

    def on_overlay_button_clicked(self, button_id: str, context: Any) -> None:
        self.creator.on_overlay_button_clicked(str(button_id), self.tool_context(context))

    def on_overlay_field_changed(self, window_id: str, field_id: str, value: str, context: Any) -> bool:
        """Forward declarative overlay text edits to the wrapped Creator tool.

        Without this bridge, Qt ``textChanged`` and ``editingFinished`` signals
        update only the generic overlay manager.  Metric validation can still
        collect manager values on Validate, but live tool-owned editors such as
        Plan Tracer Pattern never see edits, so the next refresh rewrites the
        QLineEdit with stale state.
        """

        callback = getattr(self.creator, "on_overlay_field_changed", None)
        if not callable(callback):
            return False
        return bool(callback(str(window_id), str(field_id), str(value), self.tool_context(context)))


def _increment_perf(ctx: Any, name: str, value: int = 1) -> None:
    profiler = getattr(ctx, "profiler", None)
    increment = getattr(profiler, "increment", None)
    if not callable(increment):
        return
    try:
        increment(str(name), int(value))
    except Exception:
        pass


__all__ = ["CreatorTool", "CreatorStudioToolAdapter"]
