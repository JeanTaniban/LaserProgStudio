# Pass 331 — Cloth Creator integration

## Goal

Turn the v110 headless Cloth foundation into a complete, usable Creator tool while keeping Plan Tracer 2D behavior isolated.

## Main implementation

- `cloth_tool.py`: lifecycle and state routing only;
- `cloth/interaction.py`: viewport UX stages;
- `cloth/drawing.py`: shared trace draft materialisation;
- `cloth/point_edit.py`: lightweight free-vertex drag;
- `cloth/fold_ops.py`: fold angle propagation;
- `cloth/rendering.py`: Projected Drawing overlays;
- `cloth/panel.py` and `workflow_overlay.py`: permanent user guidance;
- `tool_core/app_services/project_scenes.py`: linked multi-scene Apply/rollback.

## UX contract

Yellow means selectable, blue means committed Cloth geometry and green means flat preview. Short clicks draw/select. Dragging empty space orbits. Move point captures only a press on a free Cloth point. Escape unwinds the local action before cancelling the tool.

## Safety boundaries

- surface meshes only;
- locally planar panels;
- straight folds only;
- shared hinge points locked;
- no physical cloth solver;
- no direct Qt, VTK, MainWindow or ProjectStore dependency in the Cloth domain.

## Regression evidence

The Plan Tracer implementation directory and adapter are byte-for-byte unchanged from v110. The selected 76-test regression set has identical results in both versions: 68 passed and 8 baseline failures.
