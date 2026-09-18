# -*- coding: utf-8 -*-
"""Open every shipped Creator tool in a headless context and audit its product contract."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from laserprog_studio.tool_core import ToolContext  # noqa: E402
from laserprog_studio.tool_core.app_services.operations import OperationManager  # noqa: E402
from laserprog_studio.tooling.creator_runtime import CreatorTool  # noqa: E402
from laserprog_studio.tooling.registry import iter_tool_specs, get_studio_tool  # noqa: E402


@contextlib.contextmanager
def _tool_parameter_persistence_disabled():
    """Temporarily isolate product-audit field mutations from user prefs."""

    key = "LASERPROG_DISABLE_TOOL_PARAMETER_PERSISTENCE"
    previous = os.environ.get(key)
    os.environ[key] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


@dataclass(frozen=True)
class ToolProductRecord:
    id: str
    label: str
    category: str
    runtime: str
    creator: str
    panel_id: str | None = None
    panel_title: str | None = None
    panel_description: str | None = None
    field_count: int = 0
    action_ids: tuple[str, ...] = ()
    workflow_steps: tuple[str, ...] = ()
    workflow_requirements: tuple[str, ...] = ()
    modes: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    overlay_button_ids: tuple[str, ...] = ()
    operation_facade_issues: tuple[str, ...] = ()
    field_change_issues: tuple[str, ...] = ()
    nested_action_issues: tuple[str, ...] = ()
    auto_preview_issues: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and not self.issues


def _action_ids(panel: Any) -> tuple[str, ...]:
    actions: list[str] = []
    for field_item in panel.fields():
        if field_item.kind == "button":
            actions.append(str(field_item.id))
        elif field_item.kind == "button_row":
            actions.extend(str(action_id) for action_id, _label in field_item.choices)
    return tuple(actions)


def _operations(ctx: ToolContext) -> tuple[str, ...]:
    return tuple(sorted(getattr(ctx.operations, "_operations", {}).keys()))



def _operation_facade_issues(creator: CreatorTool) -> tuple[str, ...]:
    """Return registered/used operations that lack a public OperationManager helper.

    Built-in Creator tools may call ``ctx.operations.<name>(...)`` from inspector
    callbacks. If the tool registers ``<name>`` but OperationManager does not
    expose a same-named façade, the panel action will crash at runtime even
    though the operation exists in the registry.
    """

    try:
        import inspect

        module = sys.modules.get(type(creator).__module__)
        source = inspect.getsource(module if module is not None else type(creator))
    except Exception:
        source = ""
    used = set(re.findall(r"ctx\.operations\.([A-Za-z_]\w*)\s*\(", source))
    used.discard("register")
    helpers = {name for name in dir(OperationManager) if not name.startswith("_") and callable(getattr(OperationManager, name, None))}
    missing = sorted(name for name in used if name not in helpers)
    return tuple(f"operation facade missing: ctx.operations.{name}(...)" for name in missing)


def _overlay_button_ids(ctx: ToolContext) -> tuple[str, ...]:
    ids: list[str] = []
    for window in getattr(ctx.overlay, "windows", {}).values():
        if not bool(getattr(window, "visible", True)):
            continue
        ids.extend(str(button.id) for button in getattr(window, "buttons", ()) or ())
    return tuple(ids)


def _action_field_state_id(panel: Any, action_id: str) -> str | None:
    for field_item in panel.fields():
        if field_item.id == action_id:
            return str(field_item.id)
        if field_item.kind == "button_row" and action_id in {choice_id for choice_id, _label in field_item.choices}:
            return str(field_item.id)
    return None


def _editable_field_test_value(field_item: Any) -> Any:
    """Return a safe alternate value for field-change smoke tests."""

    kind = str(getattr(field_item, "kind", ""))
    default = getattr(field_item, "default", None)
    if kind == "choice":
        choices = tuple(choice_id for choice_id, _label in getattr(field_item, "choices", ()) or ())
        if not choices:
            return default
        if default in choices and len(choices) > 1:
            return choices[-1] if choices[-1] != default else choices[0]
        return choices[0]
    if kind == "bool":
        return not bool(default)
    if kind in {"float", "slider"}:
        if getattr(field_item, "max_value", None) is not None:
            return float(field_item.max_value)
        return float(default or 0.0) + 1.0
    if kind == "int":
        if getattr(field_item, "max_value", None) is not None:
            return int(field_item.max_value)
        return int(default or 0) + 1
    if kind == "vector2":
        return (1.0, 2.0)
    if kind == "vector3":
        return (1.0, 2.0, 3.0)
    if kind == "color":
        return "#112233"
    if kind in {"text", "file", "font", "object"}:
        return "creator audit"
    return default


def _editable_field_ids(panel: Any) -> tuple[str, ...]:
    blocked = {"button", "button_row", "separator", "title", "help", "readonly"}
    return tuple(str(field_item.id) for field_item in panel.fields() if field_item.kind not in blocked)


def _field_change_smoke_issues(spec: Any) -> tuple[str, ...]:
    """Ensure enabled editable panel fields can notify their owner tool safely.

    Changing a declarative field is as much part of the Creator API contract as
    clicking a button: preset dropdowns, sliders and checkboxes often refresh
    reports, overlay state or preview guardrails immediately.  A migrated tool
    must therefore degrade to a guided status/error state instead of leaking a
    raw exception from an ``on_change`` callback.
    """

    issues: list[str] = []
    initial_runtime = get_studio_tool(spec.id)
    initial_creator = getattr(initial_runtime, "creator", None)
    initial_ctx = ToolContext()
    try:
        initial_creator.open(initial_ctx)
    except Exception as exc:  # pragma: no cover - record tool handles open errors
        return (f"field change smoke skipped: open failed: {type(exc).__name__}: {exc}",)
    panel = initial_ctx.inspector.panel
    if panel is None:
        return ()
    for field_id in _editable_field_ids(panel):
        runtime = get_studio_tool(spec.id)
        creator = getattr(runtime, "creator", None)
        ctx = ToolContext()
        try:
            creator.open(ctx)
            active_panel = ctx.inspector.panel
            if active_panel is None:
                continue
            field_by_id = {field_item.id: field_item for field_item in active_panel.fields()}
            field_item = field_by_id.get(field_id)
            if field_item is None:
                issues.append(f"field change smoke failed: {field_id} missing after open")
                continue
            if not ctx.inspector.field_state(field_id).enabled:
                continue
            ctx.inspector.update_value(field_id, _editable_field_test_value(field_item), notify=True)
        except Exception as exc:  # pragma: no cover - exercised by audit tests
            issues.append(f"field change smoke failed: {field_id}: {type(exc).__name__}: {exc}")
    return tuple(issues)


def _trigger_action_on_fresh_context(spec: Any, path: tuple[str, ...], action_id: str | None = None) -> tuple[ToolContext, Any | None]:
    runtime = get_studio_tool(spec.id)
    creator = getattr(runtime, "creator", None)
    ctx = ToolContext()
    creator.open(ctx)
    for path_action in path:
        ctx.inspector.trigger(path_action)
    if action_id is not None:
        event = ctx.inspector.trigger(action_id)
        return ctx, event
    return ctx, None


def _nested_action_smoke_issues(spec: Any) -> tuple[str, ...]:
    """Smoke actions from every panel reachable through panel-changing actions."""

    issues: list[str] = []
    try:
        ctx, _event = _trigger_action_on_fresh_context(spec, ())
    except Exception as exc:  # pragma: no cover - record tool handles open errors
        return (f"nested action smoke skipped: open failed: {type(exc).__name__}: {exc}",)
    panel = ctx.inspector.panel
    if panel is None:
        return ()
    seen: dict[str, tuple[str, ...]] = {str(panel.id): ()}
    queue: list[tuple[str, ...]] = [()]
    while queue:
        path = queue.pop(0)
        try:
            ctx, _event = _trigger_action_on_fresh_context(spec, path)
        except Exception as exc:
            issues.append(f"nested action smoke failed: path {' > '.join(path) or '<open>'}: {type(exc).__name__}: {exc}")
            continue
        active_panel = ctx.inspector.panel
        if active_panel is None:
            continue
        for action_id in _action_ids(active_panel):
            try:
                state_id = _action_field_state_id(active_panel, action_id)
                if state_id is not None and not ctx.inspector.field_state(state_id).enabled:
                    continue
                next_ctx, _event = _trigger_action_on_fresh_context(spec, path, action_id)
                next_panel = next_ctx.inspector.panel
                if next_panel is not None and str(next_panel.id) not in seen:
                    next_path = (*path, action_id)
                    seen[str(next_panel.id)] = next_path
                    queue.append(next_path)
            except Exception as exc:  # pragma: no cover - exercised by audit tests
                location = " > ".join((*path, action_id)) or action_id
                issues.append(f"nested action smoke failed: {location}: {type(exc).__name__}: {exc}")
    return tuple(issues)


def _auto_preview_issues(panel: Any | None, actions: tuple[str, ...]) -> tuple[str, ...]:
    if panel is None or getattr(panel, "auto_preview", None) is None:
        return ()
    config = panel.auto_preview
    if not bool(getattr(config, "enabled", False)):
        return ()
    action_id = str(getattr(config, "action_id", "")).strip()
    if not action_id:
        return ("auto-preview has an empty action id",)
    if action_id not in set(actions):
        return (f"auto-preview action missing from panel actions: {action_id}",)
    return ()


def _action_smoke_issues(spec: Any, action_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Ensure visible Creator-panel actions do not throw in a bare context.

    Product tools may return ``False`` or report a status error when a document,
    selection or mesh is missing. They must not leak raw service exceptions from
    an enabled inspector button, because the Qt panel would expose that as a
    broken control rather than a guided product state.
    """

    issues: list[str] = []
    for action_id in action_ids:
        runtime = get_studio_tool(spec.id)
        creator = getattr(runtime, "creator", None)
        ctx = ToolContext()
        try:
            creator.open(ctx)
            panel = ctx.inspector.panel
            if panel is None:
                continue
            state_id = _action_field_state_id(panel, action_id)
            if state_id is None:
                issues.append(f"action smoke failed: {action_id} missing after open")
                continue
            if not ctx.inspector.field_state(state_id).enabled:
                continue
            ctx.inspector.trigger(action_id)
        except Exception as exc:  # pragma: no cover - exercised by audit tests
            issues.append(f"action smoke failed: {action_id}: {type(exc).__name__}: {exc}")
    return tuple(issues)


def _record_tool(spec: Any) -> ToolProductRecord:
    runtime = get_studio_tool(spec.id)
    creator = getattr(runtime, "creator", None)
    ctx = ToolContext()
    issues: list[str] = []
    try:
        if creator is None:
            raise RuntimeError("runtime has no CreatorTool instance")
        creator.open(ctx)
        panel = ctx.inspector.panel
        workflow = ctx.workflow.describe()
        mode_summary = ctx.modes.describe(owner_tool=spec.id)
        if panel is None:
            issues.append("missing declarative panel")
            panel_id = panel_title = panel_description = None
            field_count = 0
            actions = ()
        else:
            panel_id = panel.id
            panel_title = panel.title
            panel_description = panel.description or ""
            field_count = len(panel.fields())
            actions = _action_ids(panel)
            if panel.owner_tool != spec.id:
                issues.append(f"panel owner mismatch: {panel.owner_tool!r}")
            if not panel.description:
                issues.append("panel has no product description")
            if field_count < 2:
                issues.append("panel is too sparse")
        if not workflow.get("active"):
            issues.append("missing workflow state")
            step_ids: tuple[str, ...] = ()
            requirements: tuple[str, ...] = ()
        else:
            steps = tuple(workflow.get("steps") or ())
            step_ids = tuple(str(step.get("id")) for step in steps)
            requirements = tuple(str(step.get("requirement")) for step in steps)
        if spec.selection_policy in {"single", "multi"} and not ({"scene_object", "scene_objects"} & set(requirements)):
            issues.append("selection workflow does not declare scene-object requirement")
        modes = tuple(mode for tool in mode_summary.get("tools", ()) for mode in tool.get("modes", ()))
        operations = _operations(ctx)
        operation_facade_issues = _operation_facade_issues(creator)
        field_change_issues = _field_change_smoke_issues(spec)
        nested_action_issues = _nested_action_smoke_issues(spec)
        auto_preview_issues = _auto_preview_issues(panel, actions)
        issues.extend(operation_facade_issues)
        issues.extend(field_change_issues)
        issues.extend(nested_action_issues)
        issues.extend(auto_preview_issues)
        overlay_buttons = _overlay_button_ids(ctx)
        if overlay_buttons and type(creator).on_overlay_button_clicked is CreatorTool.on_overlay_button_clicked:
            issues.append("overlay buttons are not routed to the tool")
        issues.extend(_action_smoke_issues(spec, actions))
        return ToolProductRecord(
            id=spec.id,
            label=spec.label,
            category=spec.category,
            runtime=type(runtime).__name__,
            creator=type(creator).__name__,
            panel_id=panel_id,
            panel_title=panel_title,
            panel_description=panel_description,
            field_count=field_count,
            action_ids=actions,
            workflow_steps=step_ids,
            workflow_requirements=requirements,
            modes=modes,
            operations=operations,
            overlay_button_ids=overlay_buttons,
            operation_facade_issues=operation_facade_issues,
            field_change_issues=field_change_issues,
            nested_action_issues=nested_action_issues,
            auto_preview_issues=auto_preview_issues,
            issues=tuple(issues),
        )
    except Exception as exc:
        return ToolProductRecord(
            id=spec.id,
            label=spec.label,
            category=spec.category,
            runtime=type(runtime).__name__,
            creator=type(creator).__name__ if creator is not None else "",
            issues=tuple(issues),
            error=f"{type(exc).__name__}: {exc}",
        )


def collect_tool_product_records() -> tuple[ToolProductRecord, ...]:
    # The audit deliberately mutates every editable field to stress callbacks.
    # Keep those artificial values out of the packaged/local tool preferences.
    with _tool_parameter_persistence_disabled():
        return tuple(_record_tool(spec) for spec in iter_tool_specs())


def _print_text(records: tuple[ToolProductRecord, ...]) -> None:
    print("LaserProg Studio tool product audit")
    print("===================================")
    print(f"Tools checked: {len(records)}")
    print(f"OK           : {sum(1 for record in records if record.ok)}")
    print(f"Issues       : {sum(1 for record in records if not record.ok)}")
    print()
    for record in records:
        status = "OK" if record.ok else "CHECK"
        workflow = ",".join(record.workflow_steps) or "-"
        modes = ",".join(record.modes) or "-"
        actions = ",".join(record.action_ids) or "-"
        overlay = ",".join(record.overlay_button_ids) or "-"
        print(f"- {status:5s} {record.id:24s} panel={record.panel_id or '-':34s} fields={record.field_count:2d} workflow={workflow} modes={modes} actions={actions} overlay={overlay}")
        for issue in record.issues:
            print(f"        issue: {issue}")
        if record.error:
            print(f"        error: {record.error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--strict", action="store_true", help="Fail when any tool violates the product contract.")
    args = parser.parse_args(argv)

    records = collect_tool_product_records()
    if args.json:
        print(json.dumps([asdict(record) for record in records], indent=2, sort_keys=True))
    else:
        _print_text(records)
    failing = [record for record in records if not record.ok]
    if args.strict and failing:
        raise SystemExit("Tool product audit failed: " + ", ".join(record.id for record in failing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
