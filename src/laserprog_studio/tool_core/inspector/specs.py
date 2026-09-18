"""Pure-Python inspector panel contracts.

This module deliberately contains no Qt import.  It is the stable data layer
that a Qt adapter can render inside the right Tool inspector, while tests and
external tools can import it in a headless environment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal
import weakref

InspectorFieldKind = Literal["float", "int", "text", "bool", "choice", "button", "slider", "vector2", "vector3", "readonly", "file", "font", "color", "object", "separator", "title", "help", "button_row"]
ChangeCallback = Callable[[str, Any], None]
ActionCallback = Callable[["InspectorActionEvent"], None]


@dataclass(frozen=True, slots=True)
class AutoPreviewConfig:
    """Native debounced preview policy for declarative tool panels.

    Tool authors opt in by declaring this config on the inspector panel.  The
    Qt/runtime layer then triggers the existing preview action after user value
    changes settle.  This keeps light tools responsive without making each tool
    hand-roll timers, stale-value guards or preview button callbacks.
    """

    enabled: bool = True
    action_id: str = "preview"
    debounce_ms: int = 250
    include_fields: tuple[str, ...] = ()
    exclude_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "action_id", str(self.action_id).strip() or "preview")
        object.__setattr__(self, "debounce_ms", max(0, int(self.debounce_ms)))
        object.__setattr__(self, "include_fields", tuple(str(value).strip() for value in self.include_fields if str(value).strip()))
        object.__setattr__(self, "exclude_fields", tuple(str(value).strip() for value in self.exclude_fields if str(value).strip()))

    def accepts_field(self, field_id: str) -> bool:
        field_id = str(field_id)
        if not self.enabled:
            return False
        if self.include_fields and field_id not in set(self.include_fields):
            return False
        if field_id in set(self.exclude_fields):
            return False
        return True


@dataclass(frozen=True, slots=True)
class InspectorActionEvent:
    """Event emitted when a declarative inspector button is triggered."""

    action_id: str
    panel_id: str
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InspectorFieldState:
    """Mutable UI state associated with one inspector field."""

    enabled: bool = True
    visible: bool = True
    readonly: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Field:
    id: str
    label: str
    kind: InspectorFieldKind
    default: Any = None
    min_value: float | int | None = None
    max_value: float | int | None = None
    step: float | int | None = None
    unit: str = ""
    choices: tuple[tuple[str, str], ...] = ()
    tooltip: str | None = None
    on_change: ChangeCallback | None = field(default=None, compare=False, repr=False)
    on_click: ActionCallback | None = field(default=None, compare=False, repr=False)
    enabled: bool = True
    visible: bool = True
    readonly: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(self.id).strip())
        object.__setattr__(self, "label", str(self.label).strip())
        object.__setattr__(self, "choices", tuple((str(choice_id), str(choice_label)) for choice_id, choice_label in self.choices))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if not self.id:
            raise ValueError("Inspector field id must be non-empty.")
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "visible", bool(self.visible))
        object.__setattr__(self, "readonly", bool(self.readonly))
        if not self.label:
            raise ValueError(f"Inspector field {self.id!r} must have a non-empty label.")

    def validate(self, value: Any) -> Any:
        if self.kind in {"button", "button_row", "separator", "title", "help"}:
            return None
        if self.kind == "bool":
            return bool(value)
        if self.kind == "int":
            value = int(value)
            if self.min_value is not None:
                value = max(value, int(self.min_value))
            if self.max_value is not None:
                value = min(value, int(self.max_value))
            return value
        if self.kind == "float":
            value = float(value)
            if self.min_value is not None:
                value = max(value, float(self.min_value))
            if self.max_value is not None:
                value = min(value, float(self.max_value))
            return value
        if self.kind == "choice":
            allowed = {choice_id for choice_id, _label in self.choices}
            if value in allowed:
                return value
            return self.default
        if self.kind == "slider":
            value = float(value)
            if self.min_value is not None:
                value = max(value, float(self.min_value))
            if self.max_value is not None:
                value = min(value, float(self.max_value))
            return value
        if self.kind == "vector2":
            if isinstance(value, str):
                parts = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
                if len(parts) == 2:
                    return (float(parts[0]), float(parts[1]))
            x, y = tuple(value)
            return (float(x), float(y))
        if self.kind == "vector3":
            if isinstance(value, str):
                parts = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
                if len(parts) == 3:
                    return (float(parts[0]), float(parts[1]), float(parts[2]))
            x, y, z = tuple(value)
            return (float(x), float(y), float(z))
        if self.kind in {"readonly", "file", "font", "color", "object"}:
            return "" if value is None else str(value)
        return "" if value is None else str(value)


@dataclass(frozen=True, slots=True)
class InspectorSection:
    title: str
    fields: tuple[Field, ...] = ()
    collapsed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", str(self.title).strip())
        object.__setattr__(self, "fields", tuple(self.fields))
        if not self.title:
            raise ValueError("Inspector section title must be non-empty.")


@dataclass(frozen=True, slots=True)
class InspectorPanel:
    title: str
    sections: tuple[InspectorSection, ...] = ()
    id: str = "tool"
    owner_tool: str | None = None
    description: str | None = None
    auto_preview: AutoPreviewConfig | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(self.id).strip())
        object.__setattr__(self, "title", str(self.title).strip())
        object.__setattr__(self, "sections", tuple(self.sections))
        auto_preview = self.auto_preview
        if auto_preview is True:  # type: ignore[comparison-overlap]
            auto_preview = AutoPreviewConfig()
        elif isinstance(auto_preview, dict):
            auto_preview = AutoPreviewConfig(**auto_preview)
        elif auto_preview is False:  # type: ignore[comparison-overlap]
            auto_preview = None
        object.__setattr__(self, "auto_preview", auto_preview)
        if not self.id:
            raise ValueError("Inspector panel id must be non-empty.")
        if not self.title:
            raise ValueError("Inspector panel title must be non-empty.")
        seen: set[str] = set()
        duplicates: list[str] = []
        for field in self.fields():
            if field.id in seen:
                duplicates.append(field.id)
            seen.add(field.id)
        if duplicates:
            raise ValueError(f"Inspector panel {self.id!r} has duplicate field ids: {', '.join(sorted(set(duplicates)))}")

    def fields(self) -> tuple[Field, ...]:
        return tuple(field for section in self.sections for field in section.fields)

    def field_ids(self) -> tuple[str, ...]:
        return tuple(field.id for field in self.fields())

    def defaults(self) -> dict[str, Any]:
        return {field.id: field.default for field in self.fields() if field.kind not in {"button", "button_row", "separator", "title", "help"}}

    def validate_values(self, values: dict[str, Any] | None = None) -> dict[str, Any]:
        raw = dict(self.defaults())
        raw.update(values or {})
        return {field.id: field.validate(raw.get(field.id, field.default)) for field in self.fields() if field.kind not in {"button", "button_row", "separator", "title", "help"}}


class InspectorManager:
    """Headless state holder for the right Tool inspector.

    A Qt adapter can subscribe to this object later, but tool authors can already
    call ``ctx.inspector.set_panel(...)`` and read/write validated values without
    touching Qt widgets.
    """

    def __init__(self) -> None:
        self._panel: InspectorPanel | None = None
        self._values: dict[str, Any] = {}
        self._field_states: dict[str, InspectorFieldState] = {}
        # ``revision`` is kept as the broad diagnostic counter.  The Qt live
        # panel uses the more precise counters below: value changes must update
        # existing editors in place, not rebuild and detach the whole panel.
        self._revision = 0
        self._layout_revision = 0
        self._value_revision = 0
        self._state_revision = 0
        self._persist_tool_key: str | None = None
        # Lightweight UI observers. Programmatic display updates (for example
        # read-only measurements) must wake the Qt adapter without invoking
        # field ``on_change`` callbacks or polling at a fixed frequency.
        self._change_listeners: dict[int, Callable[[], Callable[[], None] | None]] = {}
        self._next_change_listener_id = 1

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def layout_revision(self) -> int:
        """Revision for panel structure / field-state changes."""

        return self._layout_revision

    @property
    def value_revision(self) -> int:
        """Revision for inspector values only."""

        return self._value_revision

    @property
    def state_revision(self) -> int:
        """Revision for field enabled/visible/readonly/error state only."""

        return self._state_revision

    @property
    def panel(self) -> InspectorPanel | None:
        return self._panel

    def subscribe_changes(self, callback: Callable[[], None]) -> int:
        """Subscribe to any inspector layout, value or field-state change.

        The callback is held weakly whenever Python allows it, so a destroyed Qt
        panel cannot be kept alive by the headless manager.  This notification
        channel is deliberately separate from field ``on_change`` handlers:
        it refreshes presentation only and never re-runs tool business logic.
        """

        if not callable(callback):
            raise TypeError("Inspector change callback must be callable.")
        token = int(self._next_change_listener_id)
        self._next_change_listener_id += 1
        try:
            reference = weakref.WeakMethod(callback)
        except TypeError:
            try:
                reference = weakref.ref(callback)
            except TypeError:
                reference = lambda callback=callback: callback
        self._change_listeners[token] = reference
        return token

    def unsubscribe_changes(self, token: int) -> None:
        self._change_listeners.pop(int(token), None)

    def _emit_change(self) -> None:
        dead_tokens: list[int] = []
        for token, resolve in tuple(self._change_listeners.items()):
            try:
                callback = resolve()
            except Exception:
                callback = None
            if callback is None:
                dead_tokens.append(token)
                continue
            try:
                callback()
            except Exception:
                # Presentation listeners must never make a tool update fail.
                pass
        for token in dead_tokens:
            self._change_listeners.pop(token, None)

    def set_panel(self, panel: InspectorPanel) -> InspectorPanel:
        self._panel = panel
        self._persist_tool_key = str(panel.owner_tool or "").strip() or None
        values = panel.defaults()
        if self._persist_tool_key:
            try:
                from laserprog_studio.services.tool_parameter_preferences import load_tool_parameters

                saved_values = load_tool_parameters(self._persist_tool_key)
                if saved_values:
                    values.update({field_id: value for field_id, value in saved_values.items() if field_id in panel.field_ids()})
            except Exception:
                pass
        self._values = panel.validate_values(values)
        self._field_states = {
            field.id: InspectorFieldState(enabled=field.enabled, visible=field.visible, readonly=field.readonly)
            for field in panel.fields()
        }
        self._revision += 1
        self._layout_revision += 1
        self._value_revision += 1
        self._state_revision += 1
        self._emit_change()
        return panel

    def clear(self) -> None:
        self._panel = None
        self._persist_tool_key = None
        self._values.clear()
        self._field_states.clear()
        self._revision += 1
        self._layout_revision += 1
        self._value_revision += 1
        self._state_revision += 1
        self._emit_change()

    def values(self) -> dict[str, Any]:
        if self._panel is None:
            return {}
        return self._panel.validate_values(self._values)

    def value(self, field_id: str, default: Any = None) -> Any:
        return self.values().get(field_id, default)

    def update_values(self, values: dict[str, Any], *, notify: bool = True) -> dict[str, Any]:
        return {field_id: self.update_value(field_id, value, notify=notify) for field_id, value in values.items()}

    def update_value(self, field_id: str, value: Any, *, notify: bool = True) -> Any:
        return self._set_field_value(field_id, value, notify=notify, allow_readonly=False)

    def set_display_value(self, field_id: str, value: Any) -> Any:
        """Update a read-only/display field from tool code.

        Creator tools often need computed labels such as triangle counts or
        validation reports. ``update_value`` intentionally protects read-only
        user fields, while this method lets the owning tool refresh those
        derived values without pretending they are editable input.
        """

        # ``notify=False`` suppresses the field's business ``on_change``
        # callback. UI observers are still notified when the value changes.
        return self._set_field_value(field_id, value, notify=False, allow_readonly=True)

    def _set_field_value(self, field_id: str, value: Any, *, notify: bool, allow_readonly: bool) -> Any:
        if self._panel is None:
            raise RuntimeError("No inspector panel is active.")
        field_by_id = {field.id: field for field in self._panel.fields()}
        if field_id not in field_by_id:
            raise KeyError(f"Unknown inspector field: {field_id!r}")
        field = field_by_id[field_id]
        if field.kind in {"button", "button_row", "separator", "title", "help"}:
            raise ValueError(f"Inspector field {field_id!r} does not hold a value.")
        state = self._field_states.get(field_id, InspectorFieldState())
        if state.readonly and not allow_readonly:
            raise ValueError(f"Inspector field {field_id!r} is read-only.")
        validated = field.validate(value)
        previous = self._values.get(field_id, object())
        revision_before = self._revision
        value_revision_before = self._value_revision
        self._values[field_id] = validated
        if previous != validated:
            self._revision += 1
            self._value_revision += 1
            if not allow_readonly:
                self._persist_user_values()
        if field_id == "plan_trace_2d.selection_length":
            try:
                from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                record_selection_length_event(
                    "inspector.manager.write",
                    panel_id=str(getattr(self._panel, "id", "") or ""),
                    panel_owner_tool=str(getattr(self._panel, "owner_tool", "") or ""),
                    field_id=field_id,
                    requested=value,
                    validated=validated,
                    previous=("<unset>" if type(previous) is object else previous),
                    changed=previous != validated,
                    allow_readonly=bool(allow_readonly),
                    notify=bool(notify),
                    revision_before=revision_before,
                    revision_after=self._revision,
                    value_revision_before=value_revision_before,
                    value_revision_after=self._value_revision,
                )
            except Exception:
                pass
        if previous != validated:
            self._emit_change()
        if notify and field.on_change is not None:
            field.on_change(field_id, validated)
        return validated

    def trigger(self, action_id: str) -> InspectorActionEvent:
        if self._panel is None:
            raise RuntimeError("No inspector panel is active.")
        field_by_id = {field.id: field for field in self._panel.fields()}
        field = field_by_id.get(action_id)
        state_id = action_id
        if field is None:
            for candidate in self._panel.fields():
                if candidate.kind == "button_row" and action_id in {choice_id for choice_id, _label in candidate.choices}:
                    field = candidate
                    state_id = candidate.id
                    break
        if field is None:
            raise KeyError(f"Unknown inspector action: {action_id!r}")
        if field.kind not in {"button", "button_row"}:
            raise ValueError(f"Inspector field {action_id!r} is not an action.")
        state = self._field_states.get(state_id, InspectorFieldState())
        if not state.enabled:
            raise ValueError(f"Inspector action {action_id!r} is disabled.")
        event = InspectorActionEvent(action_id=action_id, panel_id=self._panel.id, values=self.values())
        callback = field.on_click
        per_button = field.metadata.get("callbacks", {}) if isinstance(field.metadata, dict) else {}
        if action_id in per_button and callable(per_button[action_id]):
            per_button[action_id](event)
        elif callback is not None:
            callback(event)
        return event


    def field_state(self, field_id: str) -> InspectorFieldState:
        self._require_field(field_id)
        return self._field_states.get(str(field_id), InspectorFieldState())

    def update_field_state(
        self,
        field_id: str,
        *,
        enabled: bool | None = None,
        visible: bool | None = None,
        readonly: bool | None = None,
        error: str | None | object = ...,
    ) -> InspectorFieldState:
        field_id = self._require_field(field_id)
        current = self._field_states.get(field_id, InspectorFieldState())
        next_state = InspectorFieldState(
            enabled=current.enabled if enabled is None else bool(enabled),
            visible=current.visible if visible is None else bool(visible),
            readonly=current.readonly if readonly is None else bool(readonly),
            error=current.error if error is ... else (None if error is None else str(error)),
        )
        if next_state == current:
            return current
        self._field_states[field_id] = next_state
        self._revision += 1
        self._state_revision += 1
        self._emit_change()
        return next_state

    def set_enabled(self, field_id: str, enabled: bool) -> InspectorFieldState:
        return self.update_field_state(field_id, enabled=enabled)

    def set_visible(self, field_id: str, visible: bool) -> InspectorFieldState:
        return self.update_field_state(field_id, visible=visible)

    def set_readonly(self, field_id: str, readonly: bool) -> InspectorFieldState:
        return self.update_field_state(field_id, readonly=readonly)

    def set_error(self, field_id: str, message: str) -> InspectorFieldState:
        return self.update_field_state(field_id, error=message)

    def clear_error(self, field_id: str) -> InspectorFieldState:
        return self.update_field_state(field_id, error=None)

    def _persist_user_values(self) -> None:
        if self._panel is None or not self._persist_tool_key:
            return
        try:
            from laserprog_studio.services.tool_parameter_preferences import save_tool_parameters

            persistable = {}
            for field in self._panel.fields():
                if field.kind in {"button", "button_row", "separator", "title", "help", "readonly"}:
                    continue
                if bool(field.metadata.get("persist", True) is False):
                    continue
                state = self._field_states.get(field.id, InspectorFieldState(enabled=field.enabled, visible=field.visible, readonly=field.readonly))
                # Persist user-facing parameters, not hidden bookkeeping fields
                # such as selected target indices or cached face anchors.  When
                # a tool reveals an advanced field and the user edits it, its
                # current state is visible and it becomes persistable.
                if not bool(getattr(state, "visible", True)):
                    continue
                persistable[field.id] = self._values.get(field.id, field.default)
            save_tool_parameters(self._persist_tool_key, persistable)
        except Exception:
            pass

    def _require_field(self, field_id: str) -> str:
        if self._panel is None:
            raise RuntimeError("No inspector panel is active.")
        cleaned = str(field_id)
        if cleaned not in {field.id for field in self._panel.fields()}:
            raise KeyError(f"Unknown inspector field: {field_id!r}")
        return cleaned

    def describe(self) -> dict[str, Any]:
        """Return a serialisable summary useful for diagnostics and docs."""

        if self._panel is None:
            return {"active": False, "revision": self._revision, "layout_revision": self._layout_revision, "value_revision": self._value_revision, "state_revision": self._state_revision, "fields": []}
        return {
            "active": True,
            "revision": self._revision,
            "layout_revision": self._layout_revision,
            "value_revision": self._value_revision,
            "state_revision": self._state_revision,
            "panel_id": self._panel.id,
            "title": self._panel.title,
            "auto_preview": None
            if self._panel.auto_preview is None
            else {
                "enabled": self._panel.auto_preview.enabled,
                "action_id": self._panel.auto_preview.action_id,
                "debounce_ms": self._panel.auto_preview.debounce_ms,
                "include_fields": self._panel.auto_preview.include_fields,
                "exclude_fields": self._panel.auto_preview.exclude_fields,
            },
            "fields": [field.id for field in self._panel.fields()],
            "values": self.values(),
            "field_states": {
                field_id: {
                    "enabled": state.enabled,
                    "visible": state.visible,
                    "readonly": state.readonly,
                    "error": state.error,
                }
                for field_id, state in sorted(self._field_states.items())
            },
        }


def Section(title: str, fields: Iterable[Field] = (), *, collapsed: bool = False) -> InspectorSection:
    return InspectorSection(title=title, fields=tuple(fields), collapsed=collapsed)


def Panel(
    title: str,
    sections: Iterable[InspectorSection] = (),
    *,
    id: str = "tool",
    owner_tool: str | None = None,
    description: str | None = None,
    auto_preview: AutoPreviewConfig | bool | dict[str, Any] | None = None,
) -> InspectorPanel:
    return InspectorPanel(title=title, sections=tuple(sections), id=id, owner_tool=owner_tool, description=description, auto_preview=auto_preview)


def AutoPreview(
    *,
    enabled: bool = True,
    action_id: str = "preview",
    debounce_ms: int = 250,
    include_fields: Iterable[str] = (),
    exclude_fields: Iterable[str] = (),
) -> AutoPreviewConfig:
    """Declare native debounced auto-preview for a tool inspector panel."""

    return AutoPreviewConfig(
        enabled=enabled,
        action_id=action_id,
        debounce_ms=debounce_ms,
        include_fields=tuple(include_fields),
        exclude_fields=tuple(exclude_fields),
    )


def FloatField(
    id: str,
    label: str,
    *,
    default: float = 0.0,
    min_value: float | None = None,
    max_value: float | None = None,
    step: float | None = None,
    unit: str = "",
    tooltip: str | None = None,
    on_change: ChangeCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
    readonly: bool = False,
) -> Field:
    return Field(id, label, "float", float(default), min_value, max_value, step, unit, tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def IntField(
    id: str,
    label: str,
    *,
    default: int = 0,
    min_value: int | None = None,
    max_value: int | None = None,
    step: int | None = None,
    unit: str = "",
    tooltip: str | None = None,
    on_change: ChangeCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
    readonly: bool = False,
) -> Field:
    return Field(id, label, "int", int(default), min_value, max_value, step, unit, tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def TextField(
    id: str,
    label: str,
    *,
    default: str = "",
    tooltip: str | None = None,
    on_change: ChangeCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
    readonly: bool = False,
) -> Field:
    return Field(id, label, "text", str(default), tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def BoolField(
    id: str,
    label: str,
    *,
    default: bool = False,
    tooltip: str | None = None,
    on_change: ChangeCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
    readonly: bool = False,
) -> Field:
    return Field(id, label, "bool", bool(default), tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def ChoiceField(
    id: str,
    label: str,
    *,
    default: str,
    choices: Iterable[tuple[str, str]],
    tooltip: str | None = None,
    on_change: ChangeCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
    readonly: bool = False,
) -> Field:
    return Field(id, label, "choice", default, choices=tuple(choices), tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def SliderField(
    id: str,
    label: str,
    *,
    default: float = 0.0,
    min_value: float = 0.0,
    max_value: float = 1.0,
    step: float | None = None,
    unit: str = "",
    tooltip: str | None = None,
    on_change: ChangeCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
    readonly: bool = False,
) -> Field:
    return Field(id, label, "slider", float(default), min_value, max_value, step, unit, tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def Vector3Field(
    id: str,
    label: str,
    *,
    default: tuple[float, float, float] = (0.0, 0.0, 0.0),
    unit: str = "",
    tooltip: str | None = None,
    on_change: ChangeCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
    readonly: bool = False,
) -> Field:
    return Field(id, label, "vector3", tuple(float(v) for v in default), unit=unit, tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def Vector2Field(
    id: str,
    label: str,
    *,
    default: tuple[float, float] = (0.0, 0.0),
    unit: str = "",
    tooltip: str | None = None,
    on_change: ChangeCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
    readonly: bool = False,
) -> Field:
    return Field(id, label, "vector2", tuple(float(v) for v in default), unit=unit, tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def FontField(id: str, label: str, *, default: str = "", tooltip: str | None = None, on_change: ChangeCallback | None = None, enabled: bool = True, visible: bool = True, readonly: bool = False) -> Field:
    return Field(id, label, "font", str(default), tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def Separator(id: str = "separator", label: str = "—", *, visible: bool = True) -> Field:
    return Field(id, label, "separator", None, enabled=False, visible=visible, readonly=True)


def Title(id: str, label: str, *, tooltip: str | None = None, visible: bool = True) -> Field:
    return Field(id, label, "title", None, tooltip=tooltip, enabled=False, visible=visible, readonly=True)


def HelpText(id: str, text: str, *, label: str = "Help", visible: bool = True) -> Field:
    return Field(id, label, "help", None, tooltip=str(text), enabled=False, visible=visible, readonly=True, metadata={"text": str(text)})


def ButtonRow(
    id: str,
    label: str,
    *,
    buttons: Iterable[tuple[str, str]],
    tooltip: str | None = None,
    on_click: ActionCallback | None = None,
    callbacks: dict[str, ActionCallback] | None = None,
    enabled: bool = True,
    visible: bool = True,
    columns: int | None = None,
) -> Field:
    metadata = {"callbacks": dict(callbacks or {})}
    try:
        if columns is not None:
            metadata["columns"] = max(1, int(columns))
    except Exception:
        pass
    return Field(id, label, "button_row", None, choices=tuple(buttons), tooltip=tooltip, on_click=on_click, enabled=enabled, visible=visible, metadata=metadata)


def ReadonlyField(id: str, label: str, *, default: str = "", tooltip: str | None = None, visible: bool = True) -> Field:
    return Field(id, label, "readonly", str(default), tooltip=tooltip, enabled=False, visible=visible, readonly=True)


def FileField(id: str, label: str, *, default: str = "", tooltip: str | None = None, on_change: ChangeCallback | None = None, enabled: bool = True, visible: bool = True, readonly: bool = False) -> Field:
    return Field(id, label, "file", str(default), tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def ColorField(id: str, label: str, *, default: str = "#B8B8B8", tooltip: str | None = None, on_change: ChangeCallback | None = None, enabled: bool = True, visible: bool = True, readonly: bool = False) -> Field:
    return Field(id, label, "color", str(default), tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def ObjectPickerField(id: str, label: str, *, default: str = "", tooltip: str | None = None, on_change: ChangeCallback | None = None, enabled: bool = True, visible: bool = True, readonly: bool = False) -> Field:
    return Field(id, label, "object", str(default), tooltip=tooltip, on_change=on_change, enabled=enabled, visible=visible, readonly=readonly)


def Button(
    id: str,
    label: str,
    *,
    tooltip: str | None = None,
    on_click: ActionCallback | None = None,
    enabled: bool = True,
    visible: bool = True,
) -> Field:
    return Field(id, label, "button", None, tooltip=tooltip, on_click=on_click, enabled=enabled, visible=visible)


__all__ = [
    "ActionCallback",
    "AutoPreview",
    "AutoPreviewConfig",
    "BoolField",
    "Button",
    "ChangeCallback",
    "ChoiceField",
    "Field",
    "FloatField",
    "InspectorActionEvent",
    "InspectorFieldKind",
    "InspectorFieldState",
    "InspectorManager",
    "InspectorPanel",
    "InspectorSection",
    "IntField",
    "Panel",
    "Section",
    "SliderField",
    "Vector2Field",
    "FontField",
    "Separator",
    "Title",
    "HelpText",
    "ButtonRow",
    "Vector3Field",
    "ReadonlyField",
    "FileField",
    "ColorField",
    "ObjectPickerField",
    "TextField",
]
