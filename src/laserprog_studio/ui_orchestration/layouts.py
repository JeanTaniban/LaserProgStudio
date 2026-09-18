# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from ..bootstrap import compute_paths
from ..ui.toolbar_catalog import default_toolbar_item_ids, sanitized_toolbar_item_ids
from .diagnostics import UIOrchestrationDiagnostics
from .enums import LayoutCategory, LayoutValidationLevel
from .models import LayoutApplyOptions, UILayoutDefinition, UILayoutSnapshot


def _bytes_to_b64(value: Any) -> str | None:
    try:
        return base64.b64encode(bytes(value)).decode("ascii")
    except Exception:
        return None


def _b64_to_bytes(value: str | None) -> Any:
    if not value:
        return None
    try:
        raw = base64.b64decode(value.encode("ascii"))
        try:
            from PySide6.QtCore import QByteArray
            return QByteArray(raw)
        except Exception:
            return raw
    except Exception:
        return None


class UILayoutService:
    def __init__(self, owner: Any, anchors: Any, diagnostics: UIOrchestrationDiagnostics | None = None) -> None:
        self.owner = owner
        self.anchors = anchors
        self.diagnostics = diagnostics
        self._definitions: dict[str, UILayoutDefinition] = {}
        self._temporary_snapshots: list[UILayoutSnapshot] = []
        self.user_path = compute_paths().root / "settings" / "ui_layouts" / "user_layouts.json"
        self._register_system_layouts()
        self._load_user_layouts()

    def _register_system_layouts(self) -> None:
        default_toolbar = default_toolbar_item_ids()
        layouts = (
            UILayoutDefinition(
                id="layout.system.general",
                name="Général",
                category=LayoutCategory.SYSTEM,
                immutable=True,
                main_splitter_sizes=[220, 1120, 260],
                toolbar_item_ids=default_toolbar,
                required_anchors=["panel.left", "viewport.main", "panel.right", "toolbar.main"],
            ),
            UILayoutDefinition(
                id="layout.system.modeling",
                name="Modélisation",
                category=LayoutCategory.SYSTEM,
                immutable=True,
                main_splitter_sizes=[220, 1080, 300],
                toolbar_item_ids=[
                    "tool:box", "tool:joint", "tool:layflat", "modifier:split",
                    "boolean:subtract", "boolean:union", "boolean:separate",
                ],
                required_anchors=["viewport.main", "panel.right", "toolbar.main"],
            ),
            UILayoutDefinition(
                id="layout.system.plan_tracer",
                name="Plan Tracer 2D",
                category=LayoutCategory.SYSTEM,
                immutable=True,
                main_splitter_sizes=[180, 1010, 330],
                toolbar_item_ids=[
                    "tool:plan_trace", "tool:box", "tool:joint", "tool:texture_projection",
                    "tool:layflat", "modifier:split", "boolean:subtract", "boolean:union", "boolean:separate",
                ],
                required_anchors=["toolbar.plan_tracer", "viewport.main", "panel.right"],
                min_viewport_size=(640, 420),
            ),
            UILayoutDefinition(
                id="layout.system.machine",
                name="Préparation laser",
                category=LayoutCategory.SYSTEM,
                immutable=True,
                main_splitter_sizes=[250, 1000, 270],
                toolbar_item_ids=["tool:layflat", "tool:engraving", "tool:plan_trace", "tool:texture_projection"],
                required_anchors=["viewport.main", "panel.left"],
            ),
            UILayoutDefinition(
                id="layout.tutorial.getting_started",
                name="Tutoriel — Découverte",
                category=LayoutCategory.TUTORIAL,
                immutable=True,
                main_splitter_sizes=[220, 1050, 290],
                toolbar_item_ids=default_toolbar,
                required_anchors=["panel.left", "viewport.main", "panel.right", "toolbar.main"],
                min_viewport_size=(640, 420),
            ),
            UILayoutDefinition(
                id="layout.tutorial.plan_tracer",
                name="Tutoriel — Plan Tracer",
                category=LayoutCategory.TUTORIAL,
                immutable=True,
                main_splitter_sizes=[180, 1000, 340],
                toolbar_item_ids=["tool:plan_trace", "tool:box", "tool:texture_projection", "tool:layflat"],
                required_anchors=["toolbar.plan_tracer", "viewport.main", "panel.right", "tool.current.apply", "tool.current.cancel"],
                min_viewport_size=(680, 440),
            ),
        )
        for layout in layouts:
            self.register(layout, replace=True)

    def register(self, definition: UILayoutDefinition, *, replace: bool = False) -> None:
        if definition.id in self._definitions and not replace:
            raise ValueError(f"Layout already registered: {definition.id}")
        definition.toolbar_item_ids = sanitized_toolbar_item_ids(definition.toolbar_item_ids)
        self._definitions[definition.id] = definition

    def definitions(self, *, include_tutorial: bool = True) -> tuple[UILayoutDefinition, ...]:
        values = list(self._definitions.values())
        if not include_tutorial:
            values = [v for v in values if v.category != LayoutCategory.TUTORIAL]
        order = {LayoutCategory.SYSTEM: 0, LayoutCategory.TUTORIAL: 1, LayoutCategory.USER: 2, LayoutCategory.TEMPORARY: 3, LayoutCategory.RECOVERY: 4}
        return tuple(sorted(values, key=lambda item: (order.get(item.category, 9), item.name.lower(), item.id)))

    def get(self, layout_id: str) -> UILayoutDefinition | None:
        return self._definitions.get(str(layout_id))

    def capture(self) -> UILayoutSnapshot:
        owner = self.owner
        snapshot = UILayoutSnapshot()
        try:
            snapshot.main_splitter_sizes = [int(v) for v in owner.main_splitter.sizes()]
        except Exception:
            pass
        snapshot.toolbar_item_ids = [str(v) for v in list(getattr(owner, "toolbar_item_ids", []) or [])]
        try:
            snapshot.center_page_index = int(owner.center_stack.currentIndex())
        except Exception:
            pass
        for name in ("left_panel", "center_panel", "right_panel", "top_toolbar_scroll"):
            try:
                snapshot.panel_visibility[name] = bool(getattr(owner, name).isVisible())
            except Exception:
                pass
        try:
            snapshot.qt_geometry_b64 = _bytes_to_b64(owner.saveGeometry())
        except Exception:
            pass
        try:
            snapshot.qt_state_b64 = _bytes_to_b64(owner.saveState())
        except Exception:
            pass
        if self.diagnostics is not None:
            self.diagnostics.record("layout.capture.completed", splitter=snapshot.main_splitter_sizes, toolbar=snapshot.toolbar_item_ids)
        return snapshot

    def definition_from_current(self, layout_id: str, name: str, *, category: LayoutCategory = LayoutCategory.USER) -> UILayoutDefinition:
        snapshot = self.capture()
        return UILayoutDefinition(
            id=str(layout_id),
            name=str(name),
            category=category,
            immutable=category != LayoutCategory.USER,
            main_splitter_sizes=snapshot.main_splitter_sizes,
            toolbar_item_ids=snapshot.toolbar_item_ids,
            center_page_index=snapshot.center_page_index,
            panel_visibility=snapshot.panel_visibility,
            qt_geometry_b64=snapshot.qt_geometry_b64,
            qt_state_b64=snapshot.qt_state_b64,
        )

    def apply(self, layout_id: str, options: LayoutApplyOptions | None = None) -> bool:
        options = options or LayoutApplyOptions()
        definition = self.get(layout_id)
        if definition is None:
            return False
        previous = self.capture()
        if self.diagnostics is not None:
            self.diagnostics.record("layout.apply.started", layout_id=layout_id, temporary=options.temporary)
        try:
            self._apply_definition(definition, options)
            valid, reason = self.validate(definition, options.validation_level)
            if not valid:
                raise RuntimeError(reason)
            if options.temporary or options.restore_on_exit:
                self._temporary_snapshots.append(previous)
            if options.persist:
                self._persist_current_layout_state()
            if self.diagnostics is not None:
                self.diagnostics.record("layout.apply.completed", layout_id=layout_id)
            return True
        except Exception as exc:
            if options.rollback_on_failure:
                try:
                    self.restore(previous, LayoutApplyOptions(allow_partial=True, rollback_on_failure=False, persist=False))
                    if self.diagnostics is not None:
                        self.diagnostics.record("layout.rollback.completed", layout_id=layout_id)
                except Exception:
                    pass
            if self.diagnostics is not None:
                self.diagnostics.record("layout.validation.failed", layout_id=layout_id, error=repr(exc))
            return False

    def _apply_definition(self, definition: UILayoutDefinition, options: LayoutApplyOptions) -> None:
        owner = self.owner
        geometry = _b64_to_bytes(definition.qt_geometry_b64)
        state = _b64_to_bytes(definition.qt_state_b64)
        if geometry and not options.screen_adaptation:
            try:
                owner.restoreGeometry(geometry)
            except Exception:
                pass
        if state:
            try:
                owner.restoreState(state)
            except Exception:
                pass
        for name, visible in definition.panel_visibility.items():
            widget = getattr(owner, name, None)
            if widget is not None:
                try:
                    widget.setVisible(bool(visible))
                except Exception:
                    pass
        if definition.main_splitter_sizes:
            owner.main_splitter.setSizes([int(v) for v in definition.main_splitter_sizes[:3]])
        if definition.center_page_index is not None:
            try:
                owner.center_stack.setCurrentIndex(int(definition.center_page_index))
            except Exception:
                pass
        if definition.toolbar_item_ids:
            owner.toolbar_item_ids = sanitized_toolbar_item_ids(definition.toolbar_item_ids)
            controller = getattr(owner, "toolbar_controller", None)
            if controller is not None:
                controller.rebuild(save=False)
            elif hasattr(owner, "_rebuild_configurable_toolbar"):
                owner._rebuild_configurable_toolbar(save=False)
        self._adapt_to_available_screen()
        try:
            orchestrator = getattr(owner, "ui_orchestration", None)
            if orchestrator is not None:
                orchestrator.register_standard_anchors()
                orchestrator.register_dynamic_toolbar_anchors()
                orchestrator.guidance.refresh_geometry()
        except Exception:
            pass

    def restore(self, snapshot: UILayoutSnapshot | None = None, options: LayoutApplyOptions | None = None) -> bool:
        options = options or LayoutApplyOptions()
        if snapshot is None:
            if not self._temporary_snapshots:
                return False
            snapshot = self._temporary_snapshots.pop()
        owner = self.owner
        try:
            geometry = _b64_to_bytes(snapshot.qt_geometry_b64)
            state = _b64_to_bytes(snapshot.qt_state_b64)
            if geometry:
                try:
                    owner.restoreGeometry(geometry)
                except Exception:
                    pass
            if state:
                try:
                    owner.restoreState(state)
                except Exception:
                    pass
            for name, visible in snapshot.panel_visibility.items():
                widget = getattr(owner, name, None)
                if widget is not None:
                    widget.setVisible(bool(visible))
            if snapshot.main_splitter_sizes:
                owner.main_splitter.setSizes([int(v) for v in snapshot.main_splitter_sizes[:3]])
            if snapshot.center_page_index is not None:
                owner.center_stack.setCurrentIndex(int(snapshot.center_page_index))
            if snapshot.toolbar_item_ids:
                owner.toolbar_item_ids = sanitized_toolbar_item_ids(snapshot.toolbar_item_ids)
                controller = getattr(owner, "toolbar_controller", None)
                if controller is not None:
                    controller.rebuild(save=False)
            self._adapt_to_available_screen()
            if options.persist:
                self._persist_current_layout_state()
            if self.diagnostics is not None:
                self.diagnostics.record("layout.restore.completed")
            return True
        except Exception as exc:
            if self.diagnostics is not None:
                self.diagnostics.record("layout.restore.failed", error=repr(exc))
            return False

    def validate(self, definition: UILayoutDefinition, level: LayoutValidationLevel = LayoutValidationLevel.BASIC) -> tuple[bool, str]:
        if level == LayoutValidationLevel.NONE:
            return True, ""
        try:
            sizes = [int(v) for v in self.owner.main_splitter.sizes()]
            if len(sizes) < 3 or sum(sizes) <= 0:
                return False, "invalid splitter geometry"
        except Exception:
            if not definition.main_splitter_sizes:
                return False, "main splitter unavailable"
        if level in {LayoutValidationLevel.STRICT, LayoutValidationLevel.TUTORIAL_STRICT}:
            for anchor_id in definition.required_anchors:
                resolved = self.anchors.resolve(anchor_id)
                if not resolved.available:
                    return False, f"required anchor unavailable: {anchor_id}"
        if level == LayoutValidationLevel.TUTORIAL_STRICT:
            try:
                viewport = self.anchors.resolve("viewport.main")
                if viewport.global_rect is None:
                    return False, "viewport unavailable"
                _, _, width, height = viewport.global_rect
                min_width, min_height = definition.min_viewport_size
                if width < int(min_width) or height < int(min_height):
                    return False, f"viewport too small: {width}x{height}"
            except Exception:
                return False, "viewport validation failed"
        return True, ""

    def save_user_layout(self, name: str, *, layout_id: str | None = None) -> UILayoutDefinition:
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("Layout name cannot be empty")
        if layout_id is None:
            slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in clean_name).strip("_") or "layout"
            base = f"layout.user.{slug}"
            layout_id = base
            suffix = 2
            while layout_id in self._definitions:
                layout_id = f"{base}_{suffix}"
                suffix += 1
        existing = self.get(layout_id)
        if existing is not None and existing.immutable:
            raise ValueError("System and tutorial layouts are read-only")
        definition = self.definition_from_current(layout_id, clean_name, category=LayoutCategory.USER)
        self.register(definition, replace=True)
        self._save_user_layouts()
        return definition

    def update_user_layout(self, layout_id: str) -> UILayoutDefinition:
        existing = self.get(layout_id)
        if existing is None or existing.category != LayoutCategory.USER or existing.immutable:
            raise ValueError("Only user layouts can be updated")
        return self.save_user_layout(existing.name, layout_id=existing.id)

    def duplicate(self, layout_id: str, new_name: str) -> UILayoutDefinition:
        existing = self.get(layout_id)
        if existing is None:
            raise ValueError("Unknown layout")
        snapshot = self.capture()
        try:
            self._apply_definition(existing, LayoutApplyOptions(allow_partial=True))
            return self.save_user_layout(new_name)
        finally:
            self.restore(snapshot)

    def delete_user_layout(self, layout_id: str) -> bool:
        existing = self.get(layout_id)
        if existing is None or existing.category != LayoutCategory.USER or existing.immutable:
            return False
        self._definitions.pop(layout_id, None)
        self._save_user_layouts()
        return True

    def _load_user_layouts(self) -> None:
        try:
            if not self.user_path.exists():
                return
            payload = json.loads(self.user_path.read_text(encoding="utf-8"))
            rows = payload.get("layouts", []) if isinstance(payload, dict) else []
            for row in rows:
                definition = UILayoutDefinition.from_dict(row)
                if definition.category == LayoutCategory.USER:
                    definition.immutable = False
                    self.register(definition, replace=True)
        except Exception:
            pass

    def _save_user_layouts(self) -> None:
        try:
            rows = [item.to_dict() for item in self.definitions() if item.category == LayoutCategory.USER]
            payload = {"schema_version": 1, "layouts": rows}
            self.user_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.user_path.with_suffix(self.user_path.suffix + ".tmp")
            temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            temp.replace(self.user_path)
        except Exception:
            pass

    def _persist_current_layout_state(self) -> None:
        owner = self.owner
        try:
            controller = getattr(owner, "toolbar_controller", None)
            if controller is not None:
                controller.save_toolbar_preferences_now()
        except Exception:
            pass
        try:
            owner._save_ui_layout_preferences_now()
        except Exception:
            pass

    def _adapt_to_available_screen(self) -> None:
        owner = self.owner
        try:
            screen = owner.screen()
            available = screen.availableGeometry()
            geometry = owner.frameGeometry()
            if not available.intersects(geometry):
                geometry.moveCenter(available.center())
                owner.move(geometry.topLeft())
            if owner.width() > available.width() or owner.height() > available.height():
                owner.resize(min(owner.width(), available.width()), min(owner.height(), available.height()))
        except Exception:
            pass
