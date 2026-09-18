# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable
import time
import uuid

from .enums import (
    AnchorFallback,
    CalloutPlacement,
    ExitConditionKind,
    ExitMatchMode,
    InteractionMode,
    LayoutCategory,
    LayoutValidationLevel,
    SceneCloseReason,
    ScenePriority,
    SceneState,
    Severity,
    SpotlightShape,
)


def new_id(prefix: str) -> str:
    return f"{prefix}.{uuid.uuid4().hex[:12]}"


@dataclass(slots=True)
class UIEvent:
    name: str
    source_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    severity: str = "info"
    correlation_id: str | None = None
    event_id: str = field(default_factory=lambda: new_id("event"))
    timestamp: float = field(default_factory=time.time)
    consumed: bool = False


@dataclass(slots=True)
class EventFilter:
    event_name: str
    source_id: str | None = None
    required_value: Any = None
    payload_filter: dict[str, Any] = field(default_factory=dict)
    once: bool = False

    def matches(self, event: UIEvent) -> bool:
        if str(event.name) != str(self.event_name):
            return False
        if self.source_id is not None and str(event.source_id) != str(self.source_id):
            return False
        if self.required_value is not None:
            value = event.payload.get("value", event.result)
            if value != self.required_value:
                return False
        for key, expected in self.payload_filter.items():
            if event.payload.get(key) != expected:
                return False
        return True


@dataclass(slots=True)
class ResolvedAnchor:
    anchor_id: str
    global_rect: tuple[int, int, int, int] | None = None
    local_rect: tuple[int, int, int, int] | None = None
    polygon: list[tuple[int, int]] = field(default_factory=list)
    visible: bool = False
    enabled: bool = False
    interactive: bool = False
    source_type: str = "unknown"
    source_object: Any = None
    window: Any = None
    unavailable_reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.visible and self.global_rect is not None)


@dataclass(slots=True)
class Dimming:
    enabled: bool = True
    opacity: float = 0.62
    color: tuple[int, int, int] = (0, 0, 0)
    blur_enabled: bool = False
    blur_radius: int = 0
    animate_in: bool = True
    animate_out: bool = True
    animation_duration_ms: int = 160
    cover_scope: str = "main_window"
    exclude_protected_areas: bool = True


@dataclass(slots=True)
class Spotlight:
    anchor_id: str
    id: str = field(default_factory=lambda: new_id("spotlight"))
    shape: SpotlightShape = SpotlightShape.ROUNDED_RECTANGLE
    padding: int = 8
    corner_radius: int = 8
    border_enabled: bool = True
    border_width: int = 3
    pulse_enabled: bool = True
    pulse_period_ms: int = 1000
    fill_enabled: bool = False
    fill_opacity: float = 0.0
    allow_interaction: bool = True
    follow_anchor: bool = True
    visibility_required: bool = True
    fallback_behavior: AnchorFallback = AnchorFallback.WAIT
    fallback_anchor_id: str | None = None
    z_priority: int = 0


@dataclass(slots=True)
class CalloutAction:
    id: str
    label: str
    role: str = "secondary"
    closes_scene: bool = False


@dataclass(slots=True)
class Callout:
    anchor_id: str | None
    title: str
    body: str
    id: str = field(default_factory=lambda: new_id("callout"))
    icon: str | None = None
    severity: Severity = Severity.HELP
    shortcut_hint: str | None = None
    step_label: str | None = None
    image_resource: str | None = None
    actions: list[CalloutAction] = field(default_factory=list)
    placement: CalloutPlacement = CalloutPlacement.AUTO
    preferred_placements: list[CalloutPlacement] = field(default_factory=list)
    offset_x: int = 0
    offset_y: int = 0
    max_width: int = 420
    min_width: int = 250
    keep_on_screen: bool = True
    follow_anchor: bool = True
    show_pointer: bool = True
    show_border: bool = True
    show_shadow: bool = True
    opacity: float = 1.0
    show_close_button: bool = True


@dataclass(slots=True)
class InteractionPolicy:
    mode: InteractionMode = InteractionMode.OBSERVE_AND_WARN
    allowed_anchors: list[str] = field(default_factory=list)
    blocked_anchors: list[str] = field(default_factory=list)
    always_accessible_anchors: list[str] = field(default_factory=list)
    warn_on_invalid_click: bool = True
    invalid_click_message: str = "Utilisez l’élément mis en évidence pour continuer."
    invalid_click_feedback: str = "pulse_target"
    max_invalid_clicks: int = 0
    invalid_click_cooldown_ms: int = 500


@dataclass(slots=True)
class SceneLifetime:
    min_lifetime_ms: int = 0
    max_lifetime_ms: int = 0
    idle_timeout_ms: int = 0
    anchor_wait_timeout_ms: int = 5000
    exit_animation_ms: int = 120
    reset_idle_timeout_on_interaction: bool = True


@dataclass(slots=True)
class ExitCondition:
    kind: ExitConditionKind
    id: str = field(default_factory=lambda: new_id("exit"))
    anchor_id: str | None = None
    event_filter: EventFilter | None = None
    consume_click: bool = False
    include_other_windows: bool = False
    required: bool = True


@dataclass(slots=True)
class GuidanceScene:
    id: str
    scope: str = "default"
    priority: ScenePriority = ScenePriority.CONTEXTUAL_HELP
    dimming: Dimming = field(default_factory=Dimming)
    spotlights: list[Spotlight] = field(default_factory=list)
    callouts: list[Callout] = field(default_factory=list)
    interaction_policy: InteractionPolicy = field(default_factory=InteractionPolicy)
    lifetime: SceneLifetime = field(default_factory=SceneLifetime)
    exit_conditions: list[ExitCondition] = field(default_factory=list)
    exit_match_mode: ExitMatchMode = ExitMatchMode.ANY
    state: SceneState = SceneState.CREATED
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    on_closed: Callable[[str, SceneCloseReason], None] | None = None

    def all_anchor_ids(self) -> list[str]:
        ids = [s.anchor_id for s in self.spotlights]
        ids.extend(c.anchor_id for c in self.callouts if c.anchor_id)
        ids.extend(c.anchor_id for c in self.exit_conditions if c.anchor_id)
        return list(dict.fromkeys(str(v) for v in ids if v))


@dataclass(slots=True)
class SceneRuntime:
    scene: GuidanceScene
    activated_monotonic: float = field(default_factory=time.monotonic)
    met_exit_ids: set[str] = field(default_factory=set)
    event_subscription_ids: list[str] = field(default_factory=list)
    invalid_clicks: int = 0
    paused: bool = False
    sequence_index: int = 0

    def mark_exit(self, condition_id: str) -> bool:
        self.met_exit_ids.add(str(condition_id))
        required = [condition.id for condition in self.scene.exit_conditions if condition.required]
        if self.scene.exit_match_mode == ExitMatchMode.ALL:
            return all(condition_id in self.met_exit_ids for condition_id in required)
        if self.scene.exit_match_mode == ExitMatchMode.SEQUENCE:
            if not required:
                return True
            expected = required[self.sequence_index] if self.sequence_index < len(required) else None
            if condition_id != expected:
                return False
            self.sequence_index += 1
            return self.sequence_index >= len(required)
        return True


@dataclass(slots=True)
class UILayoutDefinition:
    id: str
    name: str
    category: LayoutCategory
    immutable: bool = False
    schema_version: int = 1
    application_version: str = "18.0"
    main_splitter_sizes: list[int] = field(default_factory=list)
    toolbar_item_ids: list[str] = field(default_factory=list)
    center_page_index: int | None = None
    panel_visibility: dict[str, bool] = field(default_factory=dict)
    required_anchors: list[str] = field(default_factory=list)
    min_viewport_size: tuple[int, int] = (480, 320)
    qt_geometry_b64: str | None = None
    qt_state_b64: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["category"] = self.category.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UILayoutDefinition":
        data = dict(payload)
        data["category"] = LayoutCategory(str(data.get("category", LayoutCategory.USER.value)))
        min_size = data.get("min_viewport_size")
        if isinstance(min_size, list):
            data["min_viewport_size"] = tuple(int(v) for v in min_size[:2])
        return cls(**data)


@dataclass(slots=True)
class UILayoutSnapshot:
    main_splitter_sizes: list[int] = field(default_factory=list)
    toolbar_item_ids: list[str] = field(default_factory=list)
    center_page_index: int | None = None
    panel_visibility: dict[str, bool] = field(default_factory=dict)
    qt_geometry_b64: str | None = None
    qt_state_b64: str | None = None
    focus_anchor_id: str | None = None


@dataclass(slots=True)
class LayoutApplyOptions:
    temporary: bool = False
    restore_on_exit: bool = False
    allow_partial: bool = True
    rollback_on_failure: bool = True
    screen_adaptation: bool = True
    dpi_adaptation: bool = True
    animation: bool = False
    persist: bool = False
    validation_level: LayoutValidationLevel = LayoutValidationLevel.BASIC
