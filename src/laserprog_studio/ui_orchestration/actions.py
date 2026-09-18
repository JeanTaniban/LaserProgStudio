# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .diagnostics import UIOrchestrationDiagnostics


class UIActionService:
    """Restricted, reversible UI-only actions.

    This service deliberately has no generic callback execution API. It may
    reveal/focus/scroll UI components, but it cannot apply tools, modify the
    project or send machine commands.
    """

    def __init__(self, owner: Any, anchors: Any, layouts: Any, diagnostics: UIOrchestrationDiagnostics | None = None) -> None:
        self.owner = owner
        self.anchors = anchors
        self.layouts = layouts
        self.diagnostics = diagnostics

    def ensure_visible(self, anchor_id: str) -> bool:
        resolved = self.anchors.resolve(anchor_id)
        obj = resolved.source_object
        if obj is None:
            return False
        try:
            obj.show()
        except Exception:
            pass
        try:
            parent = obj.parentWidget()
            while parent is not None:
                parent.show()
                parent = parent.parentWidget()
        except Exception:
            pass
        try:
            obj.raise_()
        except Exception:
            pass
        return bool(self.anchors.resolve(anchor_id).available)

    def focus_anchor(self, anchor_id: str) -> bool:
        if not self.ensure_visible(anchor_id):
            return False
        obj = self.anchors.resolve(anchor_id).source_object
        try:
            obj.setFocus()
            return True
        except Exception:
            return False

    def scroll_to_anchor(self, anchor_id: str) -> bool:
        resolved = self.anchors.resolve(anchor_id)
        obj = resolved.source_object
        if obj is None:
            return False
        current = obj
        for _ in range(12):
            try:
                parent = current.parentWidget()
            except Exception:
                parent = None
            if parent is None:
                break
            ensure = getattr(parent, "ensureWidgetVisible", None)
            if callable(ensure):
                try:
                    ensure(obj)
                    return True
                except Exception:
                    pass
            current = parent
        return False

    def set_anchor_visible(self, anchor_id: str, visible: bool) -> bool:
        resolved = self.anchors.resolve(anchor_id)
        obj = resolved.source_object
        if obj is None:
            return False
        try:
            obj.setVisible(bool(visible))
            return True
        except Exception:
            return False

    def apply_layout(self, layout_id: str, **kwargs: Any) -> bool:
        return bool(self.layouts.apply(layout_id, kwargs.get("options")))
