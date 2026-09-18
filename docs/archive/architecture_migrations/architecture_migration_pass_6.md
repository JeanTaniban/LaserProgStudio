# Architecture Migration Pass 6 - Tool lifecycle controller

Pass 6 moves the tool open/close/apply/cancel workflow out of the MainWindow
mixin inheritance chain.

## Migrated controller

`ToolLifecycleController` now owns the operational tool lifecycle:

- syncing tool and modifier buttons;
- confirming unapplied preview changes before tool switches;
- opening tools through `ToolSpec` / runtime `StudioTool` metadata;
- closing runtime tool resources;
- applying preview results and returning to neutral editor state;
- discarding/cancelling preview state before closing a tool.

The controller is composed from `AppContext` in `runtime_state.py` as
`window.tool_lifecycle_controller`.

## Compatibility facade

`controllers/tool_lifecycle.py` remains for the historical `StudioControllersMixin`
order and Qt signal callbacks, but it is now a thin facade over
`ToolLifecycleController`. It should stay small and should not regain tool
workflow logic.

## Why this matters

Tool lifecycle is the central seam between the toolbar, selection policy, preview
session, layout restoration, runtime tool hooks and the 3D scene. Moving it to a
composed controller makes future tools easier to reason about because the window
is no longer the implementation owner for tool orchestration.

## Current migration boundary

The controller still uses `OwnerDelegatingController` to call legacy window
methods such as `_clear_gizmo_actors`, `update_preview_state` and
`_apply_tool_selection_policy`. This is intentional for this pass: the goal is to
move ownership without rewriting gizmo, selection and panel internals at the same
time.

Future passes should reduce those owner calls by moving more behaviours into
explicit services and runtime `StudioTool` classes.

## Next target

A good next target is the boolean/action area or the first true runtime tool
conversion:

- convert one smaller tool hook into a real `StudioTool` implementation; or
- migrate `controllers/boolean_actions.py` into an application controller.

Both options continue moving responsibilities out of inherited mixins while
keeping the riskiest texture/gizmo code for later.
