"""Shared temporary preview layer for viewport tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


class PreviewKind(str, Enum):
    LINE = "line"
    POLYLINE = "polyline"
    ARC = "arc"
    CIRCLE = "circle"
    FACE = "face"
    MESH = "mesh"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class TextLabel:
    text: str
    position: Point3
    size_px: int = 14
    anchor: str = "center"


@dataclass(slots=True)
class PreviewItem:
    id: str
    owner_tool: str
    kind: PreviewKind
    points: tuple[Point3, ...] = ()
    payload: Any | None = None
    visible: bool = True
    dirty: bool = True


class PreviewManager:
    def __init__(self) -> None:
        self._items: dict[str, PreviewItem] = {}
        self.dirty_count = 0

    def show_line(self, item_id: str, owner_tool: str, p1: Point3, p2: Point3, *, payload: Any | None = None) -> PreviewItem:
        return self._upsert(PreviewItem(item_id, owner_tool, PreviewKind.LINE, (p1, p2), payload=payload))

    def show_polyline(self, item_id: str, owner_tool: str, points: list[Point3] | tuple[Point3, ...], *, payload: Any | None = None) -> PreviewItem:
        return self._upsert(PreviewItem(item_id, owner_tool, PreviewKind.POLYLINE, tuple(points), payload=payload))

    def show_arc(self, item_id: str, owner_tool: str, points: list[Point3] | tuple[Point3, ...], *, payload: Any | None = None) -> PreviewItem:
        return self._upsert(PreviewItem(item_id, owner_tool, PreviewKind.ARC, tuple(points), payload=payload))

    def show_circle(self, item_id: str, owner_tool: str, points: list[Point3] | tuple[Point3, ...], *, payload: Any | None = None) -> PreviewItem:
        return self._upsert(PreviewItem(item_id, owner_tool, PreviewKind.CIRCLE, tuple(points), payload=payload))

    def show_face(
        self,
        item_id: str,
        owner_tool: str,
        points: list[Point3] | tuple[Point3, ...],
        *,
        holes: tuple[tuple[Point3, ...], ...] | list[tuple[Point3, ...]] = (),
        payload: Any | None = None,
    ) -> PreviewItem:
        merged_payload: dict[str, Any] = dict(payload) if isinstance(payload, dict) else {}
        if holes:
            merged_payload["holes"] = tuple(tuple(point for point in polygon) for polygon in holes)
        return self._upsert(PreviewItem(item_id, owner_tool, PreviewKind.FACE, tuple(points), payload=merged_payload or None))

    def show_text(self, item_id: str, owner_tool: str, text: str, position: Point3, *, size_px: int = 14, anchor: str = "center") -> PreviewItem:
        label = TextLabel(str(text), position, int(size_px), str(anchor))
        return self._upsert(PreviewItem(item_id, owner_tool, PreviewKind.TEXT, (position,), payload=label))

    def show_mesh(self, item_id: str, owner_tool: str, mesh: Any) -> PreviewItem:
        return self._upsert(PreviewItem(item_id, owner_tool, PreviewKind.MESH, payload=mesh))

    def hide(self, item_id: str) -> bool:
        item = self._items.get(item_id)
        if item is None:
            return False
        item.visible = False
        item.dirty = True
        self.dirty_count += 1
        return True

    def clear_tool(self, owner_tool: str) -> None:
        for item_id, item in list(self._items.items()):
            if item.owner_tool == owner_tool:
                self._items.pop(item_id, None)
                self.dirty_count += 1

    def clear(self) -> None:
        if self._items:
            self.dirty_count += len(self._items)
        self._items.clear()

    def items(self, *, owner_tool: str | None = None) -> tuple[PreviewItem, ...]:
        values = self._items.values()
        if owner_tool is not None:
            values = [item for item in values if item.owner_tool == owner_tool]
        return tuple(values)

    def mark_clean(self) -> None:
        for item in self._items.values():
            item.dirty = False

    def _upsert(self, item: PreviewItem) -> PreviewItem:
        self._items[item.id] = item
        self.dirty_count += 1
        return item
