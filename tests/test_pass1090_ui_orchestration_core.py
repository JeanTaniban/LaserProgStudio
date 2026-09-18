# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.ui_orchestration.anchors import UIAnchorRegistry
from laserprog_studio.ui_orchestration.enums import (
    ExitConditionKind,
    ExitMatchMode,
    LayoutCategory,
    LayoutValidationLevel,
)
from laserprog_studio.ui_orchestration.events import UIEventBus
from laserprog_studio.ui_orchestration.layouts import UILayoutService
from laserprog_studio.ui_orchestration.models import (
    EventFilter,
    ExitCondition,
    GuidanceScene,
    LayoutApplyOptions,
    SceneRuntime,
    UILayoutDefinition,
)


class _FakeSplitter:
    def __init__(self, sizes=(220, 1120, 260)):
        self._sizes = list(sizes)

    def sizes(self):
        return list(self._sizes)

    def setSizes(self, values):
        self._sizes = [int(v) for v in values]


class _FakeStack:
    def __init__(self):
        self.index = 0

    def currentIndex(self):
        return self.index

    def setCurrentIndex(self, value):
        self.index = int(value)


class _FakeWidget:
    def __init__(self, visible=True):
        self.visible = visible

    def isVisible(self):
        return self.visible

    def setVisible(self, value):
        self.visible = bool(value)


class _FakeToolbarController:
    def __init__(self, owner):
        self.owner = owner
        self.rebuild_count = 0
        self.save_count = 0

    def rebuild(self, save=False):
        self.rebuild_count += 1

    def save_toolbar_preferences_now(self):
        self.save_count += 1


class _FakeOwner:
    def __init__(self):
        self.main_splitter = _FakeSplitter()
        self.center_stack = _FakeStack()
        self.left_panel = _FakeWidget()
        self.center_panel = _FakeWidget()
        self.right_panel = _FakeWidget()
        self.top_toolbar_scroll = _FakeWidget()
        self.toolbar_item_ids = ["tool:box", "tool:plan_trace"]
        self.toolbar_controller = _FakeToolbarController(self)
        self.saved = 0

    def saveGeometry(self):
        return b"geometry"

    def saveState(self):
        return b"state"

    def restoreGeometry(self, _value):
        return True

    def restoreState(self, _value):
        return True

    def _save_ui_layout_preferences_now(self):
        self.saved += 1

    def screen(self):
        raise RuntimeError("headless")



def test_event_bus_filters_payload_and_once_subscription():
    bus = UIEventBus()
    received = []
    subscription = bus.subscribe(
        EventFilter("tool.opened", required_value="plan_trace", payload_filter={"source": "toolbar"}, once=True),
        received.append,
    )
    bus.publish("tool.opened", payload={"value": "box", "source": "toolbar"})
    bus.publish("tool.opened", payload={"value": "plan_trace", "source": "menu"})
    bus.publish("tool.opened", payload={"value": "plan_trace", "source": "toolbar"})
    bus.publish("tool.opened", payload={"value": "plan_trace", "source": "toolbar"})
    assert len(received) == 1
    assert received[0].payload["value"] == "plan_trace"
    assert bus.subscription_count() == 0
    bus.unsubscribe(subscription)



def test_scene_runtime_supports_all_exit_conditions():
    first = ExitCondition(kind=ExitConditionKind.ANCHOR_CLICK, anchor_id="tool.current.apply")
    second = ExitCondition(kind=ExitConditionKind.EVENT, event_filter=EventFilter("tool.applied"))
    scene = GuidanceScene(id="test.all", exit_conditions=[first, second], exit_match_mode=ExitMatchMode.ALL)
    runtime = SceneRuntime(scene)
    assert runtime.mark_exit(first.id) is False
    assert runtime.mark_exit(second.id) is True



def test_anchor_registry_accepts_headless_provider_rectangles():
    registry = UIAnchorRegistry()
    registry.register_provider("viewport.main", lambda: (10, 20, 640, 480))
    result = registry.resolve("viewport.main")
    assert result.available is True
    assert result.global_rect == (10, 20, 640, 480)
    assert registry.resolve("missing").available is False



def test_layout_service_applies_and_restores_toolbar_and_splitter(tmp_path: Path):
    owner = _FakeOwner()
    anchors = UIAnchorRegistry(owner)
    service = UILayoutService(owner, anchors)
    service.user_path = tmp_path / "user_layouts.json"
    service.register(
        UILayoutDefinition(
            id="layout.user.test",
            name="Test",
            category=LayoutCategory.USER,
            main_splitter_sizes=[180, 980, 340],
            toolbar_item_ids=["tool:plan_trace", "tool:texture_projection"],
        ),
        replace=True,
    )
    before = service.capture()
    assert service.apply(
        "layout.user.test",
        LayoutApplyOptions(temporary=True, validation_level=LayoutValidationLevel.BASIC),
    ) is True
    assert owner.main_splitter.sizes() == [180, 980, 340]
    assert owner.toolbar_item_ids == ["tool:plan_trace", "tool:texture_projection"]
    assert owner.toolbar_controller.rebuild_count == 1
    assert service.restore() is True
    assert owner.main_splitter.sizes() == before.main_splitter_sizes
    assert owner.toolbar_item_ids == before.toolbar_item_ids



def test_system_layouts_are_read_only_and_user_layouts_are_atomic(tmp_path: Path):
    owner = _FakeOwner()
    service = UILayoutService(owner, UIAnchorRegistry(owner))
    service.user_path = tmp_path / "user_layouts.json"
    system = service.get("layout.system.general")
    assert system is not None and system.immutable is True
    created = service.save_user_layout("Mon espace")
    assert created.category == LayoutCategory.USER
    assert service.user_path.exists()
    updated = service.update_user_layout(created.id)
    assert updated.id == created.id
    assert service.delete_user_layout(created.id) is True


def test_guidance_scene_json_contract_round_trip():
    from laserprog_studio.ui_orchestration.enums import InteractionMode, ScenePriority
    from laserprog_studio.ui_orchestration.models import Callout, Dimming, InteractionPolicy, SceneLifetime, Spotlight
    from laserprog_studio.ui_orchestration.serialization import guidance_scene_from_dict, guidance_scene_to_dict

    scene = GuidanceScene(
        id="tutorial.open_plan_tracer",
        priority=ScenePriority.TUTORIAL,
        dimming=Dimming(opacity=0.55),
        spotlights=[Spotlight(anchor_id="toolbar.plan_tracer")],
        callouts=[Callout(anchor_id="toolbar.plan_tracer", title="Plan Tracer", body="Cliquez ici")],
        interaction_policy=InteractionPolicy(mode=InteractionMode.ALLOW_SPOTLIGHTS_ONLY),
        lifetime=SceneLifetime(max_lifetime_ms=20000),
        exit_conditions=[ExitCondition(kind=ExitConditionKind.EVENT, event_filter=EventFilter("tool.opened", required_value="plan_trace"))],
    )
    payload = guidance_scene_to_dict(scene)
    restored = guidance_scene_from_dict(payload)
    assert restored.id == scene.id
    assert restored.priority == ScenePriority.TUTORIAL
    assert restored.spotlights[0].anchor_id == "toolbar.plan_tracer"
    assert restored.exit_conditions[0].event_filter.required_value == "plan_trace"
