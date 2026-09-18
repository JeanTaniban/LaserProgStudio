# LaserProg v111 — Integrated Cloth Creator

Cloth is now available as a complete, deliberately restricted Creator tool.

## User workflow

- permanent viewport guide and declarative inspector from the first frame;
- reopen an existing Cloth through yellow edge hover, or start from a mesh/world plane;
- draw Line, Polyline and three-point Arc boundaries in 3D local planes;
- close a polyline or select a connected loop to create a face-only textile panel;
- smart-snap new geometry to Cloth points and edges;
- drag free panel vertices without rebuilding the scene;
- create/edit straight folds shared by two panels;
- preview a rigid flat pattern beside the folded surface;
- Apply linked 3D and flat meshes into the current and a dedicated project scene;
- reopen and replace both linked outputs without duplication.

## Deliberate V1 restrictions

No gravity, stretch, collision simulation, arbitrary double curvature, curved hinges, seam allowance or pattern nesting. Shared hinge vertices are locked until a multi-plane constraint solver exists.

## Architecture

The tool is split into domain model, topology, validation, flattening, mesh generation, serialization, state machines, drawing, folds, picking, rendering, point editing, inspector and workflow overlay. Multi-scene output is exposed through the public `ProjectScenesFacade`; Cloth does not import the application window or project store.

## Plan Tracer 2D safety

No Plan Tracer source file changed in v111. A 76-test representative cluster produces the same 68 passes and the same 8 historical failures in v110 and v111.

## Validation

- 23 dedicated Cloth foundation/integration tests pass;
- 30 Cloth/API/help/icon tests pass;
- strict quality gate passes;
- tool migration and product audits list all 20 built-in tools as valid Creator runtimes.
