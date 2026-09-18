"""Optimized shared gizmo manager.

The manager owns handle state and delegates drawing to a backend. Backends are
expected to reuse actors/glyph mappers and update positions in place. This is the
central rule that avoids slow remove/add actor loops during drags.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from .styles import get_point_style, visual_state_for_flags

Point3 = tuple[float, float, float]
Color = tuple[float, float, float, float]




@dataclass(frozen=True, slots=True)
class GizmoManipulator:
    """High-level gizmo created from one or more persistent handles."""

    id: str
    owner_tool: str
    kind: str
    handle_ids: tuple[str, ...]
    origin: Point3
    metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class GizmoHandle:
    id: str
    owner_tool: str
    position: Point3
    radius_px: int = 13
    color: Color = (0.1, 0.65, 1.0, 1.0)
    selected: bool = False
    hover: bool = False
    grabbed: bool = False
    visible: bool = True
    selectable: bool = True
    kind: str = "point"
    style_id: str = "solid"
    base_radius_px: int | None = None
    screen_locked: bool = True


class GizmoBackend(Protocol):
    def create_or_update(self, handle: GizmoHandle) -> None: ...

    def update_position(self, handle_id: str, position: Point3) -> None: ...

    def set_visible(self, handle_id: str, visible: bool) -> None: ...

    def remove(self, handle_id: str) -> None: ...

    def render_light(self) -> None: ...

    def render_full(self) -> None: ...


class MemoryGizmoBackend:
    """Test backend that records operations and proves we avoid actor churn."""

    def __init__(self) -> None:
        self.handles: dict[str, GizmoHandle] = {}
        self.created = 0
        self.position_updates = 0
        self.visibility_updates = 0
        self.removed = 0
        self.light_renders = 0
        self.full_renders = 0

    def create_or_update(self, handle: GizmoHandle) -> None:
        if handle.id not in self.handles:
            self.created += 1
        self.handles[handle.id] = handle

    def update_position(self, handle_id: str, position: Point3) -> None:
        if handle_id not in self.handles:
            return
        self.position_updates += 1
        self.handles[handle_id] = replace(self.handles[handle_id], position=position)

    def set_visible(self, handle_id: str, visible: bool) -> None:
        if handle_id not in self.handles:
            return
        self.visibility_updates += 1
        self.handles[handle_id] = replace(self.handles[handle_id], visible=visible)

    def remove(self, handle_id: str) -> None:
        if handle_id in self.handles:
            self.removed += 1
            self.handles.pop(handle_id, None)

    def render_light(self) -> None:
        self.light_renders += 1

    def render_full(self) -> None:
        self.full_renders += 1


class GizmoManager:
    def __init__(self, backend: GizmoBackend | None = None) -> None:
        self.backend: GizmoBackend = backend or MemoryGizmoBackend()
        self._handles: dict[str, GizmoHandle] = {}
        self._interactive_depth = 0
        # Minimal dots are rendered as real tiny geometry in production views,
        # not as driver-dependent GL point sprites.  The manager owns their
        # screen-space size policy so tools do not hard-code hover/grab sizes.
        self.minimal_dot_normal_radius_px = 2
        self.minimal_dot_active_radius_px = 3

    def set_minimal_dot_radii(self, *, normal_px: int | None = None, active_px: int | None = None) -> None:
        if normal_px is not None:
            self.minimal_dot_normal_radius_px = max(1, int(normal_px))
        if active_px is not None:
            self.minimal_dot_active_radius_px = max(1, int(active_px))

    def radius_for_style(self, style_id: str | None, base_radius_px: int, state) -> int:
        style = get_point_style(style_id)
        if style.id == "minimal":
            state_value = getattr(state, "value", str(state))
            if state_value in {"hover", "grabbed", "selected"}:
                return max(1, int(self.minimal_dot_active_radius_px))
            return max(1, int(self.minimal_dot_normal_radius_px))
        return style.radius_for(base_radius_px, state)

    def update_style_metrics(self, *, owner_tool: str | None = None, style_id: str | None = None, kind_prefix: str | None = None) -> int:
        """Recompute style-driven radii/colors without rebuilding handles.

        Sliders and theme changes should call this path.  It preserves the
        persistent-actor contract: only existing handle records are updated and
        the backend decides how to mutate actors in place.
        """
        changed = 0
        self.begin_interactive_update()
        try:
            for handle in tuple(self._handles.values()):
                if owner_tool is not None and handle.owner_tool != owner_tool:
                    continue
                if style_id is not None and handle.style_id != style_id:
                    continue
                if kind_prefix and not str(handle.kind).startswith(str(kind_prefix)):
                    continue
                state = visual_state_for_flags(
                    selectable=handle.selectable,
                    hover=handle.hover,
                    grabbed=handle.grabbed,
                    selected=handle.selected,
                    visible=handle.visible,
                )
                style = get_point_style(handle.style_id)
                base_radius = int(handle.base_radius_px or handle.radius_px)
                next_radius = self.radius_for_style(handle.style_id, base_radius, state)
                next_color = style.color_for(state)
                if int(handle.radius_px) == int(next_radius) and tuple(handle.color) == tuple(next_color):
                    continue
                if self.update_handle(
                    handle.id,
                    radius_px=next_radius,
                    color=next_color,
                    base_radius_px=base_radius,
                ):
                    changed += 1
        finally:
            self.end_interactive_update()
        return changed

    def create_handle(self, handle: GizmoHandle) -> None:
        self._handles[handle.id] = handle
        self.backend.create_or_update(handle)

    def upsert_handle(self, **kwargs) -> GizmoHandle:
        handle = GizmoHandle(**kwargs)
        self.create_handle(handle)
        return handle

    def update_handle(self, handle_id: str, **changes) -> bool:
        handle = self._handles.get(handle_id)
        if handle is None:
            return False
        updated = replace(handle, **changes)
        self._handles[handle_id] = updated
        if set(changes) == {"position"}:
            self.backend.update_position(handle_id, updated.position)
        else:
            self.backend.create_or_update(updated)
        self._render_for_update()
        return True

    def update_positions_only(self, updates: dict[str, Point3]) -> int:
        changed = 0
        for handle_id, position in updates.items():
            handle = self._handles.get(handle_id)
            if handle is None:
                continue
            self._handles[handle_id] = replace(handle, position=position)
            self.backend.update_position(handle_id, position)
            changed += 1
        if changed:
            self._render_for_update()
        return changed


    def update_visual_state(self, handle_id: str, *, hover: bool | None = None, grabbed: bool | None = None, selected: bool | None = None) -> bool:
        """Update semantic visual state without asking tools to rebuild actors.

        This is the preferred API for hover/grab/selection changes. It resolves
        the official style color and radius in one place, then delegates to the
        backend as a normal create_or_update. Persistent backends must update
        existing actors in place.
        """
        handle = self._handles.get(handle_id)
        if handle is None:
            return False
        next_hover = handle.hover if hover is None else bool(hover)
        next_grabbed = handle.grabbed if grabbed is None else bool(grabbed)
        next_selected = handle.selected if selected is None else bool(selected)
        style = get_point_style(handle.style_id)
        state = visual_state_for_flags(
            selectable=handle.selectable,
            hover=next_hover,
            grabbed=next_grabbed,
            selected=next_selected,
            visible=handle.visible,
        )
        base_radius = int(handle.base_radius_px or handle.radius_px)
        return self.update_handle(
            handle_id,
            hover=next_hover,
            grabbed=next_grabbed,
            selected=next_selected,
            color=style.color_for(state),
            radius_px=self.radius_for_style(handle.style_id, base_radius, state),
            base_radius_px=base_radius,
        )

    def update_interaction_state(self, owner_tool: str, *, hover_id: str | None = None, grabbed_id: str | None = None, kind_prefix: str | None = None) -> int:
        """Apply hover/grab state to a tool's handles using persistent updates.

        Tools should use this instead of clearing/rebuilding gizmos when the
        cursor enters, leaves or grabs a handle. The method only touches changed
        handles and returns how many were updated.
        """
        changed = 0
        self.begin_interactive_update()
        try:
            for handle in tuple(self._handles.values()):
                if handle.owner_tool != owner_tool:
                    continue
                if kind_prefix and not str(handle.kind).startswith(str(kind_prefix)):
                    continue
                is_hover = handle.id == hover_id
                is_grabbed = handle.id == grabbed_id
                if handle.hover == is_hover and handle.grabbed == is_grabbed:
                    continue
                if self.update_visual_state(handle.id, hover=is_hover, grabbed=is_grabbed):
                    changed += 1
        finally:
            self.end_interactive_update()
        return changed

    def set_visible(self, handle_id: str, visible: bool) -> bool:
        handle = self._handles.get(handle_id)
        if handle is None:
            return False
        self._handles[handle_id] = replace(handle, visible=visible)
        self.backend.set_visible(handle_id, visible)
        self._render_for_update()
        return True

    def remove(self, handle_id: str) -> bool:
        """Remove one persistent handle by id.

        Tool actors and gizmo handles intentionally live in separate managers.
        When a topology actor disappears, tools need a precise way to remove the
        corresponding handle without clearing the whole tool.
        """

        if handle_id not in self._handles:
            return False
        self._handles.pop(handle_id, None)
        self.backend.remove(handle_id)
        self._render_for_update()
        return True

    def translate(
        self,
        *,
        id: str,
        owner_tool: str,
        origin: Point3 = (0.0, 0.0, 0.0),
        axes: tuple[str, ...] = ("x", "y", "z"),
        radius_px: int = 14,
    ) -> GizmoManipulator:
        """Create a standard translate manipulator from axis handles."""

        handle_ids: list[str] = []
        offsets = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
        for axis in axes:
            axis_key = str(axis).lower()
            dx, dy, dz = offsets.get(axis_key, (0.0, 0.0, 0.0))
            handle_id = f"{id}:{axis_key}"
            self.upsert_handle(
                id=handle_id,
                owner_tool=owner_tool,
                position=(float(origin[0]) + dx, float(origin[1]) + dy, float(origin[2]) + dz),
                radius_px=radius_px,
                base_radius_px=radius_px,
                kind=f"translate:{axis_key}",
                style_id="translate_arrow",
            )
            handle_ids.append(handle_id)
        center_id = f"{id}:center"
        self.upsert_handle(
            id=center_id,
            owner_tool=owner_tool,
            position=origin,
            radius_px=radius_px,
            base_radius_px=radius_px,
            kind="translate:center",
            style_id="solid",
        )
        handle_ids.append(center_id)
        return GizmoManipulator(id=id, owner_tool=owner_tool, kind="translate", handle_ids=tuple(handle_ids), origin=origin)

    def rotate(
        self,
        *,
        id: str,
        owner_tool: str,
        origin: Point3 = (0.0, 0.0, 0.0),
        axes: tuple[str, ...] = ("x", "y", "z"),
        radius_px: int = 13,
    ) -> GizmoManipulator:
        """Create a standard rotate manipulator with ring-style handles."""

        handle_ids: list[str] = []
        offsets = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
        for axis in axes:
            axis_key = str(axis).lower()
            dx, dy, dz = offsets.get(axis_key, (0.0, 0.0, 0.0))
            handle_id = f"{id}:rotate:{axis_key}"
            self.upsert_handle(
                id=handle_id,
                owner_tool=owner_tool,
                position=(float(origin[0]) + dx, float(origin[1]) + dy, float(origin[2]) + dz),
                radius_px=radius_px,
                base_radius_px=radius_px,
                kind=f"rotate:{axis_key}",
                style_id="ring",
            )
            handle_ids.append(handle_id)
        return GizmoManipulator(id=id, owner_tool=owner_tool, kind="rotate", handle_ids=tuple(handle_ids), origin=origin)

    def scale(
        self,
        *,
        id: str,
        owner_tool: str,
        origin: Point3 = (0.0, 0.0, 0.0),
        axes: tuple[str, ...] = ("x", "y", "z", "uniform"),
        radius_px: int = 13,
    ) -> GizmoManipulator:
        """Create a standard scale manipulator."""

        handle_ids: list[str] = []
        offsets = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0), "uniform": (0.75, 0.75, 0.75)}
        for axis in axes:
            axis_key = str(axis).lower()
            dx, dy, dz = offsets.get(axis_key, (0.0, 0.0, 0.0))
            handle_id = f"{id}:scale:{axis_key}"
            self.upsert_handle(
                id=handle_id,
                owner_tool=owner_tool,
                position=(float(origin[0]) + dx, float(origin[1]) + dy, float(origin[2]) + dz),
                radius_px=radius_px,
                base_radius_px=radius_px,
                kind=f"scale:{axis_key}",
                style_id="square",
            )
            handle_ids.append(handle_id)
        return GizmoManipulator(id=id, owner_tool=owner_tool, kind="scale", handle_ids=tuple(handle_ids), origin=origin)

    def plane(
        self,
        *,
        id: str,
        owner_tool: str,
        origin: Point3 = (0.0, 0.0, 0.0),
        normal: Point3 = (0.0, 0.0, 1.0),
        radius_px: int = 15,
    ) -> GizmoManipulator:
        """Create a plane manipulator with origin and normal handles."""

        normal_end = (float(origin[0]) + float(normal[0]), float(origin[1]) + float(normal[1]), float(origin[2]) + float(normal[2]))
        origin_id = f"{id}:origin"
        normal_id = f"{id}:normal"
        self.upsert_handle(id=origin_id, owner_tool=owner_tool, position=origin, radius_px=radius_px, base_radius_px=radius_px, kind="plane:origin", style_id="target")
        self.upsert_handle(id=normal_id, owner_tool=owner_tool, position=normal_end, radius_px=radius_px, base_radius_px=radius_px, kind="plane:normal", style_id="axis")
        return GizmoManipulator(id=id, owner_tool=owner_tool, kind="plane", handle_ids=(origin_id, normal_id), origin=origin, metadata={"normal": normal})

    def triad(self, *, id: str, owner_tool: str, origin: Point3 = (0.0, 0.0, 0.0), radius_px: int = 13) -> GizmoManipulator:
        """Create a triad manipulator for local axes."""

        return self.translate(id=id, owner_tool=owner_tool, origin=origin, axes=("x", "y", "z"), radius_px=radius_px)

    def box_bounds(
        self,
        *,
        id: str,
        owner_tool: str,
        bounds: tuple[float, float, float, float, float, float],
        radius_px: int = 11,
    ) -> GizmoManipulator:
        """Create corner handles for an axis-aligned bounding box."""

        xmin, xmax, ymin, ymax, zmin, zmax = (float(v) for v in bounds)
        corners = (
            (xmin, ymin, zmin), (xmax, ymin, zmin), (xmin, ymax, zmin), (xmax, ymax, zmin),
            (xmin, ymin, zmax), (xmax, ymin, zmax), (xmin, ymax, zmax), (xmax, ymax, zmax),
        )
        handle_ids: list[str] = []
        for i, position in enumerate(corners):
            handle_id = f"{id}:corner:{i}"
            self.upsert_handle(id=handle_id, owner_tool=owner_tool, position=position, radius_px=radius_px, base_radius_px=radius_px, kind="box_bounds:corner", style_id="diamond")
            handle_ids.append(handle_id)
        origin = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0)
        return GizmoManipulator(id=id, owner_tool=owner_tool, kind="box_bounds", handle_ids=tuple(handle_ids), origin=origin, metadata={"bounds": bounds})

    def clear_tool(self, owner_tool: str) -> None:
        for handle_id, handle in list(self._handles.items()):
            if handle.owner_tool == owner_tool:
                self.backend.set_visible(handle_id, False)
                self._handles.pop(handle_id, None)
        self.backend.render_full()

    def begin_interactive_update(self) -> None:
        self._interactive_depth += 1

    def end_interactive_update(self) -> None:
        self._interactive_depth = max(0, self._interactive_depth - 1)
        if self._interactive_depth == 0:
            self.backend.render_full()

    def handle(self, handle_id: str, *, owner_tool: str | None = None) -> GizmoHandle | None:
        """Return one handle without walking the full owner handle list.

        Cursor and drag fast paths often know the exact handle id that moved.
        Using this lookup avoids an O(N) scan on every mouse event in dense
        tools such as Plan Tracer, while preserving the existing
        ``handles(owner_tool=...)`` iterator for bulk operations.
        """

        handle = self._handles.get(str(handle_id))
        if handle is None:
            return None
        if owner_tool is not None and handle.owner_tool != str(owner_tool):
            return None
        return handle

    def handles(self, *, owner_tool: str | None = None) -> tuple[GizmoHandle, ...]:
        values = self._handles.values()
        if owner_tool is not None:
            values = [handle for handle in values if handle.owner_tool == owner_tool]
        return tuple(values)

    def _render_for_update(self) -> None:
        if self._interactive_depth:
            self.backend.render_light()
        else:
            self.backend.render_full()
