# LaserProg v100 — Mechanical single driver, live test and editable assemblies

This build makes mechanical testing substantially lighter by animating only the actors that are actually driven, through cached actor matrices, without rebuilding meshes, the document scene, the inspector or the complete overlay on every frame.

It also enforces one driver per assembly: assigning a new gear or scene part replaces the previous driver. Gear selection now preserves the exact clicked gear identifier, so the visible driver overlay and the actual driver always refer to the same pinion.

Mechanical assemblies now follow the same editable-object lifecycle as Plan Tracer 2D. Applied and cancelled outputs carry the generic editable-tool metadata on every generated mesh. A cancelled draft is rebuilt, displayed and selected immediately; an applied assembly can be hovered, selected and reopened from any of its generated shafts, then edited in place without duplicating its persistent assembly record.

See `docs/archive/passes/pass322_mechanical_single_driver_live_editable.md` for the implementation and validation details.
