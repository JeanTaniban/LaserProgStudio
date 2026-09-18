"""Headless workflow and mode services for creator tools.

These managers give future tools a common way to model multi-step interactions
(pick A, pick B, preview, apply) and internal tool modes without scattering
state machines across Qt controllers.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Literal

WorkflowRequirement = Literal["none", "scene_object", "scene_objects", "tool_actor", "point", "face", "file"]


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    id: str
    label: str
    requirement: WorkflowRequirement = "none"
    help: str = ""
    optional: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(self.id).strip())
        object.__setattr__(self, "label", str(self.label).strip())
        object.__setattr__(self, "requirement", str(self.requirement).strip() or "none")
        object.__setattr__(self, "help", str(self.help))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if not self.id:
            raise ValueError("Workflow step id must be non-empty.")
        if not self.label:
            raise ValueError(f"Workflow step {self.id!r} must have a non-empty label.")


@dataclass(frozen=True, slots=True)
class WorkflowState:
    owner_tool: str
    steps: tuple[WorkflowStep, ...]
    active_index: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    completed: bool = False

    @property
    def active_step(self) -> WorkflowStep | None:
        if not self.steps or self.completed:
            return None
        index = min(max(0, self.active_index), len(self.steps) - 1)
        return self.steps[index]

    @property
    def active_id(self) -> str | None:
        step = self.active_step
        return None if step is None else step.id

    @property
    def progress(self) -> tuple[int, int]:
        if not self.steps:
            return (0, 0)
        return (min(self.active_index + 1, len(self.steps)), len(self.steps))


class ToolWorkflowManager:
    """Small state machine for multi-step creator tools."""

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._state: WorkflowState | None = None

    def bind_context(self, ctx: Any) -> "ToolWorkflowManager":
        self._ctx = ctx
        return self

    @property
    def state(self) -> WorkflowState | None:
        return self._state

    @property
    def active_step(self) -> WorkflowStep | None:
        return None if self._state is None else self._state.active_step

    def start(self, owner_tool: str, steps: Iterable[WorkflowStep], *, data: dict[str, Any] | None = None) -> WorkflowState:
        normalized = tuple(steps)
        if not normalized:
            raise ValueError("A workflow needs at least one step.")
        self._state = WorkflowState(owner_tool=str(owner_tool), steps=normalized, data=dict(data or {}))
        self._announce()
        return self._state

    def step(
        self,
        id: str,
        label: str,
        *,
        requirement: WorkflowRequirement = "none",
        help: str = "",
        optional: bool = False,
        **metadata: Any,
    ) -> WorkflowStep:
        return WorkflowStep(id=id, label=label, requirement=requirement, help=help, optional=optional, metadata=dict(metadata))

    def require_scene_object(self, id: str, label: str, *, help: str = "", optional: bool = False, **metadata: Any) -> WorkflowStep:
        return self.step(id, label, requirement="scene_object", help=help, optional=optional, **metadata)

    def require_scene_objects(self, id: str, label: str, *, help: str = "", optional: bool = False, **metadata: Any) -> WorkflowStep:
        return self.step(id, label, requirement="scene_objects", help=help, optional=optional, **metadata)

    def require_tool_actor(self, id: str, label: str, *, help: str = "", optional: bool = False, **metadata: Any) -> WorkflowStep:
        return self.step(id, label, requirement="tool_actor", help=help, optional=optional, **metadata)

    def require_face(self, id: str, label: str, *, help: str = "", optional: bool = False, **metadata: Any) -> WorkflowStep:
        return self.step(id, label, requirement="face", help=help, optional=optional, **metadata)

    def record(self, key: str, value: Any, *, advance: bool = False) -> WorkflowState:
        state = self._require_state()
        data = dict(state.data)
        data[str(key)] = value
        self._state = replace(state, data=data)
        if advance:
            return self.advance()
        return self._state

    def record_active(self, value: Any, *, advance: bool = True) -> WorkflowState:
        step = self.active_step
        if step is None:
            raise RuntimeError("No active workflow step.")
        return self.record(step.id, value, advance=advance)

    def advance(self) -> WorkflowState:
        state = self._require_state()
        next_index = state.active_index + 1
        completed = next_index >= len(state.steps)
        self._state = replace(state, active_index=min(next_index, max(0, len(state.steps) - 1)), completed=completed)
        self._announce()
        return self._state

    def back(self) -> WorkflowState:
        state = self._require_state()
        self._state = replace(state, active_index=max(0, state.active_index - 1), completed=False)
        self._announce()
        return self._state

    def goto(self, step_id: str) -> WorkflowState:
        state = self._require_state()
        cleaned = str(step_id).strip()
        for index, step in enumerate(state.steps):
            if step.id == cleaned:
                self._state = replace(state, active_index=index, completed=False)
                self._announce()
                return self._state
        raise KeyError(f"Unknown workflow step: {step_id!r}")

    def complete(self) -> WorkflowState:
        state = self._require_state()
        self._state = replace(state, completed=True)
        self._announce("Workflow complete.")
        return self._state

    def clear(self, owner_tool: str | None = None) -> None:
        if owner_tool is None or self._state is None or self._state.owner_tool == str(owner_tool):
            self._state = None

    def describe(self) -> dict[str, Any]:
        state = self._state
        if state is None:
            return {"active": False}
        active = state.active_step
        return {
            "active": True,
            "owner_tool": state.owner_tool,
            "active_step": None if active is None else active.id,
            "progress": state.progress,
            "completed": state.completed,
            "data_keys": sorted(state.data),
            "steps": [
                {
                    "id": step.id,
                    "label": step.label,
                    "requirement": step.requirement,
                    "optional": step.optional,
                    "help": step.help,
                }
                for step in state.steps
            ],
        }

    def _require_state(self) -> WorkflowState:
        if self._state is None:
            raise RuntimeError("No workflow is active.")
        return self._state

    def _announce(self, message: str | None = None) -> None:
        ctx = self._ctx
        if ctx is None or getattr(ctx, "status", None) is None:
            return
        if message is None:
            step = self.active_step
            if step is None:
                message = "Workflow complete."
            else:
                message = step.help or step.label
        try:
            ctx.status.info(message)
        except Exception:
            pass


@dataclass(frozen=True, slots=True)
class ToolModeSpec:
    id: str
    label: str
    cursor: str = ""
    shortcut: str = ""
    help: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(self.id).strip())
        object.__setattr__(self, "label", str(self.label).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))
        if not self.id:
            raise ValueError("Tool mode id must be non-empty.")
        if not self.label:
            raise ValueError(f"Tool mode {self.id!r} must have a non-empty label.")


@dataclass(frozen=True, slots=True)
class ToolModeState:
    owner_tool: str
    modes: tuple[ToolModeSpec, ...]
    active_id: str

    @property
    def active(self) -> ToolModeSpec:
        for mode in self.modes:
            if mode.id == self.active_id:
                return mode
        return self.modes[0]


class ToolModeManager:
    """Owner-scoped mode registry for tools with Add/Edit/Delete-style modes."""

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._states: dict[str, ToolModeState] = {}

    def bind_context(self, ctx: Any) -> "ToolModeManager":
        self._ctx = ctx
        return self

    def define(self, id: str, label: str, *, cursor: str = "", shortcut: str = "", help: str = "", **metadata: Any) -> ToolModeSpec:
        return ToolModeSpec(id=id, label=label, cursor=cursor, shortcut=shortcut, help=help, metadata=dict(metadata))

    def register(self, owner_tool: str, modes: Iterable[ToolModeSpec], *, active: str | None = None) -> ToolModeState:
        normalized = tuple(modes)
        if not normalized:
            raise ValueError("A tool mode group needs at least one mode.")
        active_id = str(active or normalized[0].id)
        if active_id not in {mode.id for mode in normalized}:
            raise KeyError(f"Unknown active mode: {active_id!r}")
        state = ToolModeState(owner_tool=str(owner_tool), modes=normalized, active_id=active_id)
        self._states[str(owner_tool)] = state
        self._announce(state)
        return state

    def set(self, owner_tool: str, mode_id: str) -> ToolModeState:
        state = self._require(owner_tool)
        cleaned = str(mode_id).strip()
        if cleaned not in {mode.id for mode in state.modes}:
            raise KeyError(f"Unknown mode for {owner_tool!r}: {mode_id!r}")
        state = replace(state, active_id=cleaned)
        self._states[str(owner_tool)] = state
        self._announce(state)
        return state

    def active(self, owner_tool: str) -> ToolModeSpec | None:
        state = self._states.get(str(owner_tool))
        return None if state is None else state.active

    def clear(self, owner_tool: str | None = None) -> None:
        if owner_tool is None:
            self._states.clear()
        else:
            self._states.pop(str(owner_tool), None)

    def describe(self, owner_tool: str | None = None) -> dict[str, Any]:
        if owner_tool is not None:
            states = [self._states[str(owner_tool)]] if str(owner_tool) in self._states else []
        else:
            states = list(self._states.values())
        return {
            "tools": [
                {
                    "owner_tool": state.owner_tool,
                    "active": state.active_id,
                    "modes": [mode.id for mode in state.modes],
                }
                for state in states
            ]
        }

    def _require(self, owner_tool: str) -> ToolModeState:
        key = str(owner_tool)
        if key not in self._states:
            raise RuntimeError(f"No modes registered for {key!r}.")
        return self._states[key]

    def _announce(self, state: ToolModeState) -> None:
        ctx = self._ctx
        if ctx is None or getattr(ctx, "status", None) is None:
            return
        mode = state.active
        try:
            ctx.status.info(mode.help or f"Mode: {mode.label}")
        except Exception:
            pass


__all__ = [
    "ToolModeManager",
    "ToolModeSpec",
    "ToolModeState",
    "ToolWorkflowManager",
    "WorkflowRequirement",
    "WorkflowState",
    "WorkflowStep",
]
