# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
import weakref
from typing import Any, Callable

from .diagnostics import UIOrchestrationDiagnostics
from .models import ResolvedAnchor


@dataclass(slots=True)
class _AnchorEntry:
    anchor_id: str
    kind: str
    object_ref: Callable[[], Any] | None = None
    provider: Callable[[], Any] | None = None


class UIAnchorRegistry:
    def __init__(self, owner: Any = None, diagnostics: UIOrchestrationDiagnostics | None = None) -> None:
        self.owner = owner
        self._entries: dict[str, _AnchorEntry] = {}
        self._object_to_anchor: dict[int, str] = {}
        self.diagnostics = diagnostics

    def register_widget(self, anchor_id: str, widget: Any) -> None:
        self._register_object(anchor_id, widget, kind="widget")

    def register_action(self, anchor_id: str, action: Any, widget: Any | None = None) -> None:
        target = widget if widget is not None else action
        self._register_object(anchor_id, target, kind="action")

    def register_provider(self, anchor_id: str, provider: Callable[[], Any]) -> None:
        self._entries[str(anchor_id)] = _AnchorEntry(str(anchor_id), "provider", provider=provider)
        if self.diagnostics is not None:
            self.diagnostics.record("anchor.registered", anchor_id=anchor_id, kind="provider")

    def _register_object(self, anchor_id: str, obj: Any, *, kind: str) -> None:
        anchor_id = str(anchor_id)
        try:
            ref = weakref.ref(obj, lambda _ref, aid=anchor_id: self.unregister(aid))
        except TypeError:
            ref = lambda obj=obj: obj
        self._entries[anchor_id] = _AnchorEntry(anchor_id, kind, object_ref=ref)
        self._object_to_anchor[id(obj)] = anchor_id
        try:
            obj.setProperty("laserprogAnchorId", anchor_id)
        except Exception:
            pass
        if self.diagnostics is not None:
            self.diagnostics.record("anchor.registered", anchor_id=anchor_id, kind=kind)

    def unregister(self, anchor_id: str) -> None:
        entry = self._entries.pop(str(anchor_id), None)
        if entry is not None and entry.object_ref is not None:
            obj = entry.object_ref()
            if obj is not None:
                self._object_to_anchor.pop(id(obj), None)
        if self.diagnostics is not None:
            self.diagnostics.record("anchor.destroyed", anchor_id=anchor_id)

    def resolve(self, anchor_id: str) -> ResolvedAnchor:
        anchor_id = str(anchor_id)
        entry = self._entries.get(anchor_id)
        if entry is None:
            result = ResolvedAnchor(anchor_id=anchor_id, unavailable_reason="unregistered")
            if self.diagnostics is not None:
                self.diagnostics.record("anchor.missing", anchor_id=anchor_id, reason="unregistered")
            return result
        try:
            if entry.provider is not None:
                value = entry.provider()
                result = self._coerce_provider_result(anchor_id, value)
            else:
                obj = entry.object_ref() if entry.object_ref is not None else None
                result = self._resolve_qt_object(anchor_id, obj, entry.kind)
        except Exception as exc:
            result = ResolvedAnchor(anchor_id=anchor_id, unavailable_reason=f"resolve_error:{exc!r}")
        if self.diagnostics is not None:
            self.diagnostics.record(
                "anchor.resolved" if result.available else "anchor.missing",
                anchor_id=anchor_id,
                visible=result.visible,
                enabled=result.enabled,
                reason=result.unavailable_reason,
                rect=result.global_rect,
            )
        return result

    def _coerce_provider_result(self, anchor_id: str, value: Any) -> ResolvedAnchor:
        if isinstance(value, ResolvedAnchor):
            return value
        if value is None:
            return ResolvedAnchor(anchor_id=anchor_id, unavailable_reason="provider_returned_none")
        if isinstance(value, dict):
            payload = dict(value)
            payload.setdefault("anchor_id", anchor_id)
            return ResolvedAnchor(**payload)
        if isinstance(value, (tuple, list)) and len(value) >= 4:
            rect = tuple(int(v) for v in value[:4])
            return ResolvedAnchor(anchor_id=anchor_id, global_rect=rect, visible=True, enabled=True, interactive=True, source_type="provider")
        return self._resolve_qt_object(anchor_id, value, "provider_object")

    def _resolve_qt_object(self, anchor_id: str, obj: Any, kind: str) -> ResolvedAnchor:
        if obj is None:
            return ResolvedAnchor(anchor_id=anchor_id, unavailable_reason="object_destroyed")
        try:
            visible = bool(obj.isVisible())
        except Exception:
            visible = True
        try:
            enabled = bool(obj.isEnabled())
        except Exception:
            enabled = True
        try:
            rect = obj.rect()
            top_left = obj.mapToGlobal(rect.topLeft())
            global_rect = (int(top_left.x()), int(top_left.y()), int(rect.width()), int(rect.height()))
            local_rect = (0, 0, int(rect.width()), int(rect.height()))
        except Exception:
            return ResolvedAnchor(anchor_id=anchor_id, visible=visible, enabled=enabled, source_object=obj, source_type=kind, unavailable_reason="no_widget_geometry")
        try:
            window = obj.window()
        except Exception:
            window = None
        return ResolvedAnchor(
            anchor_id=anchor_id,
            global_rect=global_rect,
            local_rect=local_rect,
            visible=visible,
            enabled=enabled,
            interactive=bool(visible and enabled),
            source_type=kind,
            source_object=obj,
            window=window,
        )

    def anchor_for_object(self, obj: Any) -> str | None:
        current = obj
        for _ in range(12):
            if current is None:
                break
            anchor = self._object_to_anchor.get(id(current))
            if anchor:
                return anchor
            try:
                property_anchor = current.property("laserprogAnchorId")
                if property_anchor:
                    return str(property_anchor)
            except Exception:
                pass
            try:
                current = current.parentWidget()
            except Exception:
                break
        return None

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))
