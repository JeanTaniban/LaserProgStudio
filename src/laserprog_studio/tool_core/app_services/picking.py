"""Picking facade and result types for creator tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from .common import ToolServiceError

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class PickResult:
    kind: Literal["none", "object", "face", "edge", "vertex", "ray", "point"]
    screen_pos: Point2 | None = None
    world_pos: Point3 | None = None
    object_id: str | None = None
    object_index: int | None = None
    element_index: int | None = None
    normal: Point3 | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def hit(self) -> bool:
        return self.kind != "none"

    @classmethod
    def none(cls, screen_pos: Point2 | None = None) -> "PickResult":
        return cls("none", screen_pos=screen_pos)


class PickingFacade:
    """Stable picking entry point with capability discovery.

    The facade delegates to whichever backend is available: ``ctx.scene`` first,
    then ``ctx.viewport``.  Headless tests can provide simple ``pick_object_at``
    methods without importing Qt, VTK or PyVista.
    """

    def __init__(self) -> None:
        self._ctx: Any | None = None

    def bind_context(self, ctx: Any) -> "PickingFacade":
        self._ctx = ctx
        return self

    def object_at(self, screen_pos: Point2, **filters: Any) -> PickResult:
        return self._call_pick("pick_object_at", screen_pos, **filters)

    def face_at(self, screen_pos: Point2, **filters: Any) -> PickResult:
        return self._call_pick("pick_face_at", screen_pos, **filters)

    def edge_at(self, screen_pos: Point2, **filters: Any) -> PickResult:
        return self._call_pick("pick_edge_at", screen_pos, **filters)

    def vertex_at(self, screen_pos: Point2, **filters: Any) -> PickResult:
        return self._call_pick("pick_vertex_at", screen_pos, **filters)

    def ray(self, screen_pos: Point2) -> PickResult:
        ctx = self._require_ctx()
        viewport = getattr(ctx, "viewport", None)
        ray_method = getattr(viewport, "screen_to_ray", None)
        if callable(ray_method):
            data = ray_method(screen_pos)
            return _pick_result_from_backend(data, "ray", screen_pos)
        return PickResult.none(screen_pos)

    def plane_intersection(self, screen_pos: Point2, plane: Any) -> PickResult:
        ctx = self._require_ctx()
        viewport = getattr(ctx, "viewport", None)
        method = getattr(viewport, "screen_to_world_on_plane", None)
        if callable(method):
            try:
                world = method(screen_pos, plane)
            except TypeError:
                world = method(screen_pos)
            if world is not None:
                return PickResult("point", screen_pos=screen_pos, world_pos=_point3(world))
        return PickResult.none(screen_pos)

    def _call_pick(self, method_name: str, screen_pos: Point2, **filters: Any) -> PickResult:
        ctx = self._require_ctx()
        for backend in (getattr(ctx, "scene", None), getattr(ctx, "viewport", None)):
            method = getattr(backend, method_name, None)
            if callable(method):
                try:
                    data = method(screen_pos, **filters)
                except TypeError:
                    data = method(screen_pos)
                result = _pick_result_from_backend(
                    data,
                    method_name.replace("pick_", "").replace("_at", ""),
                    screen_pos,
                )
                if result.hit:
                    return result
        if method_name == "pick_object_at":
            active = ctx.scene_selection.active_object()
            if active is not None:
                return PickResult("object", screen_pos=screen_pos, object_id=active.id, object_index=active.index, metadata={"fallback": "active_selection"})
        return PickResult.none(screen_pos)

    def _require_ctx(self) -> Any:
        if self._ctx is None:
            raise ToolServiceError("PickingFacade is not bound to a ToolContext.")
        return self._ctx


def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))


def _pick_result_from_backend(data: Any, kind: str, screen_pos: Point2) -> PickResult:
    if data is None or data is False:
        return PickResult.none(screen_pos)
    if isinstance(data, PickResult):
        return data
    if isinstance(data, dict):
        result_kind = str(data.get("kind") or kind)
        return PickResult(
            result_kind if result_kind in {"none", "object", "face", "edge", "vertex", "ray", "point"} else "point",  # type: ignore[arg-type]
            screen_pos=screen_pos,
            world_pos=_point3(data["world_pos"]) if data.get("world_pos") is not None else None,
            object_id=str(data["object_id"]) if data.get("object_id") is not None else None,
            object_index=int(data["object_index"]) if data.get("object_index") is not None else None,
            element_index=int(data["element_index"]) if data.get("element_index") is not None else None,
            normal=_point3(data["normal"]) if data.get("normal") is not None else None,
            metadata=dict(data.get("metadata") or {}),
        )
    if isinstance(data, tuple) and len(data) >= 3 and all(isinstance(v, (int, float)) for v in data[:3]):
        return PickResult("point", screen_pos=screen_pos, world_pos=_point3(data[:3]))
    return PickResult(str(kind) if kind in {"object", "face", "edge", "vertex", "ray", "point"} else "point", screen_pos=screen_pos, metadata={"raw": data})
