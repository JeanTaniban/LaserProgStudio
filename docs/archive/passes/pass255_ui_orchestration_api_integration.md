# Pass 255 — UI Orchestration API integration

## Goal

Introduce the reusable UI layer described in the tutorial/guidance specification without coupling tutorial scenarios to LaserProg tools.

The new service is available from:

```python
window.ui_orchestration
context.ui_orchestration
```

It is composed of:

- `UIAnchorRegistry`: semantic anchors instead of screen coordinates;
- `UIEventBus`: semantic UI/workflow events;
- `GuidanceService`: dimming, spotlights, callouts, input policies and exit conditions;
- `UILayoutService`: immutable system/tutorial layouts and editable user layouts;
- `UIActionService`: restricted UI-only actions (`focus`, `ensure_visible`, `scroll_to_anchor`);
- `UISessionService`: temporary layout snapshots;
- debug-gated `UIOrchestrationDiagnostics`.

## Runtime integration

The service is created during runtime-state initialization and installed only after the main widgets exist.

Standard anchors include:

```text
application.main_window
panel.left
panel.center
panel.right
viewport.main
toolbar.main
toolbar.palette
toolbar.remove
tool.current.apply
tool.current.cancel
project.parts
project.undo
project.redo
```

Every configurable toolbar item receives a stable anchor:

```text
toolbar.item.tool:plan_trace
toolbar.plan_tracer
```

Toolbar anchors are rebuilt whenever the user changes the toolbar.

## Guidance scene lifecycle

Supported lifecycle and exit controls:

- minimum lifetime;
- maximum lifetime;
- idle timeout;
- missing-anchor timeout;
- exit on any click;
- exit on semantic anchor click;
- exit on semantic event;
- exit on Escape;
- `ANY`, `ALL`, and ordered `SEQUENCE` matching;
- priority queue;
- temporary suspension and resumption by higher-priority scenes.

Interaction policies:

```text
ALLOW_ALL
OBSERVE_AND_WARN
ALLOW_SPOTLIGHTS_ONLY
ALLOW_LIST
BLOCK_ALL_EXCEPT_PROTECTED
VISUAL_ONLY
```

Protected anchors cannot be removed by a scene. The registry reserves machine emergency stop/disconnect and critical-dialog anchors for later machine-window registration.

## Layout presets

Available built-in immutable presets:

```text
Général
Modélisation
Plan Tracer 2D
Préparation laser
Tutoriel — Découverte
Tutoriel — Plan Tracer
```

The View menu exposes:

```text
View
└── Dispositions de l’interface
    ├── Général
    ├── Modélisation
    ├── Plan Tracer 2D
    ├── Préparation laser
    ├── Mes dispositions
    ├── Enregistrer la disposition actuelle…
    └── Gérer les dispositions…
```

System and tutorial layouts are immutable. The manager allows users to duplicate a system preset, save the current interface, update and delete user presets.

User layouts are stored atomically in:

```text
settings/ui_layouts/user_layouts.json
```

A layout captures UI presentation only: splitter sizes, toolbar items, page/panel visibility and Qt geometry/state. It does not contain project, selection, active tool or machine state.

## First application workflow

Tool lifecycle now publishes:

```text
tool.open.requested
tool.opened
tool.reopened
tool.open.blocked
tool.open.blocked_by_active_tool
tool.applied
tool.cancelled
tool.closed
```

When the user refuses a tool change because the current tool still has unapplied changes, LaserProg shows a workflow-conflict guidance scene around Apply and Cancel. Selection-policy errors can also show an anchored contextual explanation.

## Safety

The orchestration API does not expose arbitrary callback execution. UI actions may reveal, focus or arrange widgets, but cannot:

- apply a tool;
- edit the document;
- start engraving;
- send machine commands;
- disable emergency-stop access.

If guidance fails, the application keeps normal interaction. Diagnostics are written only when debug mode is enabled:

```text
diagnostics/ui_orchestration_debug.jsonl
```

## JSON contract

`guidance_scene_from_dict()` and `guidance_scene_to_dict()` provide a stable declarative contract for future tutorial files.

See:

```text
examples/ui_orchestration/active_tool_conflict_scene.json
```

## Validation

- new orchestration core/integration tests: 9 passed;
- toolbar/layout/tool-lifecycle regression selection: 39 passed;
- compileall: passed;
- architecture and product quality gate: passed.

A pre-existing unrelated toolbar test (`test_toolbar_is_limited_to_18_visible_items`) still expects 18 items from a ten-item input and fails on the unmodified v89 toolbar catalog as well; it was not changed in this pass.
