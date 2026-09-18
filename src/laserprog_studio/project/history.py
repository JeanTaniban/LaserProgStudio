# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .ids import make_history_entry_id

# The visible scene history is deliberately narrower than Ctrl+Z.  Ctrl+Z keeps
# every technical change in RAM; this list records only user-significant scene
# operations that deserve a restore point in the future floating History window.
SEMANTIC_OPERATION_TYPES: frozenset[str] = frozenset(
    {
        "boolean",
        "modifier",
        "tool_apply",
        "layflat",
        "split",
        "merge",
        "import",
        "restore",
        "scene_generated",
        "scene_edit",
        "delete",
        "paste",
        "duplicate",
        "object_add",
    }
)
TRANSIENT_OPERATION_TYPES: frozenset[str] = frozenset(
    {
        "transform",
        "translate",
        "rotate",
        "scale",
        "selection",
        "camera",
        "hover",
        "preview",
    }
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_semantic_operation(operation_type: str | None) -> bool:
    value = str(operation_type or "").strip().lower()
    if not value:
        return False
    if value in TRANSIENT_OPERATION_TYPES:
        return False
    return value in SEMANTIC_OPERATION_TYPES


@dataclass(slots=True)
class SceneModificationHistoryEntry:
    """One visible, restorable modification in a scene history."""

    description: str
    operation_type: str
    timestamp: str = field(default_factory=utc_now_iso)
    entry_id: str = field(default_factory=make_history_entry_id)
    snapshot_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        description: str,
        operation_type: str,
        *,
        snapshot_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "SceneModificationHistoryEntry":
        return cls(
            description=str(description or operation_type or "Scene modification"),
            operation_type=str(operation_type or "tool_apply"),
            snapshot_id=snapshot_id,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "description": self.description,
            "operation_type": self.operation_type,
            "snapshot_id": self.snapshot_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneModificationHistoryEntry":
        return cls(
            entry_id=str(data.get("entry_id") or make_history_entry_id()),
            timestamp=str(data.get("timestamp") or utc_now_iso()),
            description=str(data.get("description") or "Scene modification"),
            operation_type=str(data.get("operation_type") or "tool_apply"),
            snapshot_id=(str(data.get("snapshot_id")) if data.get("snapshot_id") else None),
            metadata=dict(data.get("metadata") or {}),
        )
