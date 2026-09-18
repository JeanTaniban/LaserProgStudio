# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from typing import Any

from .enums import (
    AnchorFallback,
    CalloutPlacement,
    ExitConditionKind,
    ExitMatchMode,
    InteractionMode,
    ScenePriority,
    Severity,
    SpotlightShape,
)
from .models import (
    Callout,
    CalloutAction,
    Dimming,
    EventFilter,
    ExitCondition,
    GuidanceScene,
    InteractionPolicy,
    SceneLifetime,
    Spotlight,
)


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    return value


def guidance_scene_to_dict(scene: GuidanceScene) -> dict[str, Any]:
    payload = asdict(scene)
    payload.pop("on_closed", None)
    return _plain(payload)


def _priority(value: Any) -> ScenePriority:
    if isinstance(value, ScenePriority):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.upper() in ScenePriority.__members__:
            return ScenePriority[text.upper()]
        try:
            return ScenePriority(int(text))
        except Exception:
            return ScenePriority.CONTEXTUAL_HELP
    try:
        return ScenePriority(int(value))
    except Exception:
        return ScenePriority.CONTEXTUAL_HELP


def guidance_scene_from_dict(payload: dict[str, Any]) -> GuidanceScene:
    data = dict(payload)
    dimming = Dimming(**dict(data.get("dimming") or {}))

    spotlights: list[Spotlight] = []
    for raw in data.get("spotlights", []) or []:
        row = dict(raw)
        row["shape"] = SpotlightShape(str(row.get("shape", SpotlightShape.ROUNDED_RECTANGLE.value)))
        row["fallback_behavior"] = AnchorFallback(str(row.get("fallback_behavior", AnchorFallback.WAIT.value)))
        spotlights.append(Spotlight(**row))

    callouts: list[Callout] = []
    for raw in data.get("callouts", []) or []:
        row = dict(raw)
        row["severity"] = Severity(str(row.get("severity", Severity.HELP.value)))
        row["placement"] = CalloutPlacement(str(row.get("placement", CalloutPlacement.AUTO.value)))
        row["preferred_placements"] = [CalloutPlacement(str(value)) for value in row.get("preferred_placements", []) or []]
        row["actions"] = [CalloutAction(**dict(action)) for action in row.get("actions", []) or []]
        callouts.append(Callout(**row))

    policy_data = dict(data.get("interaction_policy") or {})
    policy_data["mode"] = InteractionMode(str(policy_data.get("mode", InteractionMode.OBSERVE_AND_WARN.value)))
    interaction_policy = InteractionPolicy(**policy_data)

    lifetime = SceneLifetime(**dict(data.get("lifetime") or {}))

    exit_conditions: list[ExitCondition] = []
    for raw in data.get("exit_conditions", []) or []:
        row = dict(raw)
        row["kind"] = ExitConditionKind(str(row.get("kind")))
        event_filter = row.get("event_filter")
        row["event_filter"] = EventFilter(**dict(event_filter)) if isinstance(event_filter, dict) else None
        exit_conditions.append(ExitCondition(**row))

    return GuidanceScene(
        id=str(data["id"]),
        scope=str(data.get("scope", "default")),
        priority=_priority(data.get("priority", ScenePriority.CONTEXTUAL_HELP)),
        dimming=dimming,
        spotlights=spotlights,
        callouts=callouts,
        interaction_policy=interaction_policy,
        lifetime=lifetime,
        exit_conditions=exit_conditions,
        exit_match_mode=ExitMatchMode(str(data.get("exit_match_mode", ExitMatchMode.ANY.value))),
        correlation_id=data.get("correlation_id"),
        metadata=dict(data.get("metadata") or {}),
    )
