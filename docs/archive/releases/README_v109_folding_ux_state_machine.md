# LaserProg v109 — Folding UX state machine repair

## Root cause

Folding intentionally passed the left mouse press to the viewport so a user could orbit before choosing a mesh, face or point. The application bridge can classify a very small pointer movement as camera navigation. Folding did not implement the matching release-passthrough contract, so the release was suppressed and the state machine never received the click. The tool therefore appeared open but inert.

## Interaction contract

Folding now implements both halves of the Creator camera contract:

- `wants_pointer_press_passthrough()` records the click candidate and leaves the press to VTK;
- `wants_pointer_release_passthrough()` requests the release even after camera navigation started;
- movement under 6 px is treated as a click;
- a larger movement remains an orbit/pan gesture and performs no Folding transition;
- host scene-selection changes during the press cannot consume the same release as the next Folding step.

## Visible five-step workflow

A persistent viewport inspector is visible from the moment Folding opens:

1. Select the mesh.
2. Select the drawing face.
3. Place the start point.
4. Place the end point.
5. Adjust the curve and Apply.

The window shows the active step, exact instruction, selected mesh, face status, edit/new mode, current status and navigation reminder. It exposes Previous step, Straighten, Invert, Apply, Start over and Cancel only when they are relevant.

## Viewport feedback

- Every valid selectable mesh receives yellow edge hover feedback.
- The chosen target stays outlined in blue through the following steps.
- The hovered face is yellow and the validated face is blue.
- Start/end placement shows a projected cursor and provisional interval line.
- Existing folded meshes still reopen directly into curve editing.

## Architecture

The implementation remains Creator API-only and is split into:

- `folding/models.py` — persistent and transient session state;
- `folding/state_machine.py` — guarded transitions plus phase descriptors;
- `folding/workflow_overlay.py` — persistent phase-aware viewport window;
- `folding/rendering.py` — target, face, cursor, interval and curve visuals;
- `folding/geometry.py` — deformation kernel;
- `folding/serialization.py` — editable source persistence;
- `folding/panel.py` — declarative right inspector;
- `folding_tool.py` — lifecycle, picking and preview coordination.

No Folding module imports Qt, VTK or PyVista.

## Validation

- 18 Folding/hover/UX regression tests pass.
- Click-like release after camera passthrough selects correctly.
- True left drag remains camera navigation.
- The persistent workflow window and every phase transition are tested.
- Static quality gate passes, including architecture, API boundaries, Creator migration and product audit.
