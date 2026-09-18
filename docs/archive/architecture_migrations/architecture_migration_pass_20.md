# Architecture Migration Pass 20 — Integrated planar tools

This pass activates the first two tools prepared by the planar foundation work.

## Tools registered

- `plan_trace` / **Traceur de plan**
- `vent_generator` / **Générateur d'évent**

Both tools are registered in the normal tool registry and toolbar registry, so they are available from the configurable toolbox.

## Shared workflow

Both tools use `PlanarToolController`:

1. detect the current camera direction;
2. lock the closest orthographic view (`top`, `bottom`, `front`, `back`, `left`, `right`);
3. keep all interactions on one constant-depth plane;
4. use grid/smart planar snapping;
5. draw lightweight overlay previews;
6. create a normal preview mesh;
7. commit through the existing Apply/Cancel workflow.

## Traceur de plan

The tool uses `PlanarPolygonDraft`.

- `ADD`: press/drag/release to place a point; the pending point follows the mouse.
- `MOD`: select the nearest point and edit it by drag or by the right-inspector position fields.
- `SUPP`: remove the nearest point.
- `RST`: clear the draft and return to ADD.
- double-click closes the polygon.
- Apply commits an extruded mesh using the configured depth.

The first point uses depth `0` unless the first click hits an existing part, in which case the locked plane is moved to the hit depth.

## Générateur d'évent

The tool uses `VentPathDraft`.

- waypoints are edited with the same ADD/MOD/SUPP/RST modes;
- the preview shows a smoothed centerline and the approximate duct corridor;
- the report shows the estimated centerline length;
- Apply commits a hollow swept duct mesh from section area and wall thickness.

## Files added/changed

- `planar_tools/mesh_generation.py`
- `application/planar_tool_controller.py`
- `controllers/interaction.py`
- `controllers/transform_inspector.py`
- `application/tool_lifecycle_controller.py`
- `tooling/registry.py`
- `ui/toolbar_catalog.py`
- `ui/tool_panel_factory.py`
- `tests/test_architecture_migration_pass20.py`

## Validation

The full test suite and static architecture checks pass after this migration.
