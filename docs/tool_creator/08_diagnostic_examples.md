# 08 - Diagnostic examples

Every public creator API should have a small diagnostic or contract test.

Current checks cover:

- the public `laserprog_studio.tool_api` import path;
- actor factories and fixed/selectable/grabbable semantics;
- right-inspector declarative specs, validation, callbacks and duplicate-id rejection;
- `SceneCache` collection from actors and refresh/exclusion behavior;
- `ctx.snap.smart(...)` with scene-cache, custom world targets and UI snap targets;
- the minimal point-line example;
- the complete `creator_api_demo_tool.py` example.

The Tool Core Diagnostic panel includes a **Creator API** button. It exercises the creator-facing path visually and headlessly:

- declares a right-inspector panel;
- registers fixed/selectable/grabbable actors;
- rebuilds `SceneCache` with exclusions;
- runs smart snap with a custom midpoint and a UI snap point;
- draws a preview;
- triggers an inspector action;
- executes an undoable command.

When a new public capability is added, add either:

- a visual diagnostic button when the behavior is UI-visible;
- a contract test when the behavior is pure API/data.
