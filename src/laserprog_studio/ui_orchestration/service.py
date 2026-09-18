# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..tooling.registry import get_tool_spec
from ..ui.toolbar_catalog import iter_toolbar_item_specs
from .anchors import UIAnchorRegistry
from .actions import UIActionService
from .diagnostics import UIOrchestrationDiagnostics
from .enums import (
    CalloutPlacement,
    ExitConditionKind,
    InteractionMode,
    LayoutValidationLevel,
    ScenePriority,
    Severity,
    SceneCloseReason,
)
from .events import UIEventBus
from .guidance import GuidanceService, PROTECTED_ANCHORS
from .layouts import UILayoutService
from .sessions import UISessionService
from .models import (
    Callout,
    Dimming,
    EventFilter,
    ExitCondition,
    GuidanceScene,
    InteractionPolicy,
    LayoutApplyOptions,
    SceneLifetime,
    Spotlight,
)


class UIOrchestrationService:
    """Single public entry point for layout, guidance, anchors and semantic UI events.

    The service is intentionally independent from tutorial code. Tutorials,
    contextual errors and workflow ambiguity helpers are clients of the same API.
    """

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.diagnostics = UIOrchestrationDiagnostics(owner)
        self.anchors = UIAnchorRegistry(owner, self.diagnostics)
        self.events = UIEventBus(self.diagnostics)
        self.layouts = UILayoutService(owner, self.anchors, self.diagnostics)
        self.actions = UIActionService(owner, self.anchors, self.layouts, self.diagnostics)
        self.sessions = UISessionService(self.layouts)
        self.guidance = GuidanceService(owner, self.anchors, self.events, self.diagnostics)
        self._installed = False

    def install(self) -> None:
        if self._installed:
            self.register_standard_anchors()
            self.register_dynamic_toolbar_anchors()
            return
        self._installed = True
        self.guidance.install()
        self.register_standard_anchors()
        self.register_dynamic_toolbar_anchors()
        self.diagnostics.record("orchestration.installed")

    def register_standard_anchors(self) -> None:
        owner = self.owner
        mappings = {
            "application.main_window": owner,
            "panel.left": getattr(owner, "left_panel", None),
            "panel.center": getattr(owner, "center_panel", None),
            "panel.right": getattr(owner, "right_panel", None),
            "viewport.main": getattr(owner, "plotter_area", None),
            "toolbar.main": getattr(owner, "top_toolbar_scroll", None),
            "toolbar.palette": getattr(owner, "btn_toolbar_palette", None),
            "toolbar.remove": getattr(owner, "btn_toolbar_remove", None),
            "tool.current.apply": getattr(owner, "btn_apply_preview", None),
            "tool.current.cancel": getattr(owner, "btn_cancel_preview", None),
            "project.parts": getattr(owner, "mesh_list", None),
            "project.undo": getattr(owner, "btn_project_undo", None),
            "project.redo": getattr(owner, "btn_project_redo", None),
        }
        for anchor_id, widget in mappings.items():
            if widget is not None:
                self.anchors.register_widget(anchor_id, widget)
        for protected_id in PROTECTED_ANCHORS:
            if protected_id not in self.anchors.registered_ids():
                self.anchors.register_provider(protected_id, lambda aid=protected_id: None)

    def register_dynamic_toolbar_anchors(self) -> None:
        owner = self.owner
        buttons = dict(getattr(owner, "toolbar_dynamic_buttons", {}) or {})
        for spec in iter_toolbar_item_specs():
            button = buttons.get(spec.id)
            if button is None and spec.button_attr:
                button = getattr(owner, spec.button_attr, None)
            if button is None:
                continue
            self.anchors.register_widget(f"toolbar.item.{spec.id}", button)
            if spec.tool_id:
                semantic = str(spec.tool_id).replace("_2d", "").replace("tool_", "")
                self.anchors.register_widget(f"toolbar.{semantic}", button)
                if spec.id == "tool:plan_trace":
                    self.anchors.register_widget("toolbar.plan_tracer", button)

    def publish(self, event_name: str, *, source_id: str | None = None, payload: dict[str, Any] | None = None, result: Any = None, correlation_id: str | None = None):
        return self.events.publish(event_name, source_id=source_id, payload=payload, result=result, correlation_id=correlation_id)

    def show_scene(self, scene: GuidanceScene) -> bool:
        return self.guidance.apply_scene(scene)

    def close_scene(self, scene_id: str | None = None) -> bool:
        return self.guidance.close_scene(scene_id)

    def apply_layout(self, layout_id: str, *, temporary: bool = False, tutorial_strict: bool = False, persist: bool = False) -> bool:
        return self.layouts.apply(
            layout_id,
            LayoutApplyOptions(
                temporary=temporary,
                restore_on_exit=temporary,
                persist=persist,
                validation_level=LayoutValidationLevel.TUTORIAL_STRICT if tutorial_strict else LayoutValidationLevel.BASIC,
            ),
        )

    def toolbar_anchor_for_tool(self, tool_id: str | None) -> str | None:
        if not tool_id:
            return None
        for spec in iter_toolbar_item_specs():
            if spec.tool_id == tool_id:
                if spec.id == "tool:plan_trace":
                    return "toolbar.plan_tracer"
                return f"toolbar.item.{spec.id}"
        return None

    def show_active_tool_conflict(self, *, requested_tool_id: str | None = None) -> bool:
        current_tool = str(getattr(self.owner, "active_tool", "") or "")
        current_spec = get_tool_spec(current_tool)
        requested_spec = get_tool_spec(requested_tool_id) if requested_tool_id else None
        current_label = getattr(current_spec, "label", None) or current_tool or "L’outil actuel"
        requested_label = getattr(requested_spec, "label", None) or requested_tool_id or "un autre outil"
        scene = GuidanceScene(
            id="workflow.active_tool_conflict",
            scope="workflow.active_tool",
            priority=ScenePriority.WORKFLOW_CONFLICT,
            dimming=Dimming(enabled=True, opacity=0.42),
            spotlights=[
                Spotlight(anchor_id="tool.current.apply", padding=7),
                Spotlight(anchor_id="tool.current.cancel", padding=7),
            ],
            callouts=[
                Callout(
                    anchor_id="tool.current.apply",
                    title="Terminez l’outil actuel",
                    body=f"{current_label} est encore actif. Appliquez ou annulez cet outil avant d’ouvrir {requested_label}.",
                    severity=Severity.WARNING,
                    placement=CalloutPlacement.TOP,
                    show_close_button=True,
                )
            ],
            interaction_policy=InteractionPolicy(
                mode=InteractionMode.OBSERVE_AND_WARN,
                allowed_anchors=["tool.current.apply", "tool.current.cancel"],
                always_accessible_anchors=list(PROTECTED_ANCHORS),
                invalid_click_message="Appliquez ou annulez d’abord l’outil actuel.",
            ),
            lifetime=SceneLifetime(min_lifetime_ms=500, max_lifetime_ms=60000, anchor_wait_timeout_ms=2500),
            exit_conditions=[
                ExitCondition(kind=ExitConditionKind.EVENT, event_filter=EventFilter("tool.applied")),
                ExitCondition(kind=ExitConditionKind.EVENT, event_filter=EventFilter("tool.cancelled")),
                ExitCondition(kind=ExitConditionKind.EVENT, event_filter=EventFilter("tool.closed")),
                ExitCondition(kind=ExitConditionKind.ESCAPE),
            ],
            metadata={"requested_tool_id": requested_tool_id, "current_tool_id": current_tool},
        )
        return self.show_scene(scene)

    def show_contextual_error(
        self,
        *,
        scene_id: str,
        anchor_id: str | None,
        title: str,
        body: str,
        max_lifetime_ms: int = 12000,
        priority: ScenePriority = ScenePriority.BLOCKING_ERROR,
        exit_on_any_click: bool = True,
    ) -> bool:
        spotlights = [Spotlight(anchor_id=anchor_id, padding=7)] if anchor_id else []
        conditions = [ExitCondition(kind=ExitConditionKind.ESCAPE)]
        if exit_on_any_click:
            conditions.append(ExitCondition(kind=ExitConditionKind.ANY_CLICK))
        scene = GuidanceScene(
            id=str(scene_id),
            scope="contextual.error",
            priority=priority,
            dimming=Dimming(enabled=priority >= ScenePriority.BLOCKING_ERROR, opacity=0.34),
            spotlights=spotlights,
            callouts=[
                Callout(
                    anchor_id=anchor_id,
                    title=title,
                    body=body,
                    severity=Severity.ERROR,
                    placement=CalloutPlacement.AUTO,
                )
            ],
            interaction_policy=InteractionPolicy(mode=InteractionMode.ALLOW_ALL, always_accessible_anchors=list(PROTECTED_ANCHORS)),
            lifetime=SceneLifetime(max_lifetime_ms=max_lifetime_ms),
            exit_conditions=conditions,
        )
        return self.show_scene(scene)

    def shutdown(self) -> None:
        try:
            self.guidance.close_scene(callout_close_reason=SceneCloseReason.APPLICATION_SHUTDOWN)
        except Exception:
            pass
        self.events.clear()


__all__ = ["UIOrchestrationService"]
