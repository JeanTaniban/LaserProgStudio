# Plan tracer 2D

`Plan tracer` has been rebuilt as a Creator API tool.  The old hook-driven plan-trace implementation is no longer the reference path for this tool.

The direction is deliberately narrow for this first pass.  Early notes called this the **Point placement only** pass; the current implementation has grown into the full sketch-kernel path while keeping the same API-owned cursor/point contract:

1. when the tool opens, it chooses the nearest locked drawing view from the current camera orientation (`top`, `bottom`, `front`, `back`, `left`, `right`) and immediately moves the camera to that orthographic view;
2. the first overlay is an anchor prompt only: it contains no drawing-mode buttons and asks the user to click the anchor height point;
3. the first click selects the constant semantic drawing-plane depth by raycast only;
4. if the raycast does not hit a face/object, the semantic depth falls back to `0` for the locked view;
5. the API creates a second display plane slightly toward the camera so UI motifs stay visible and do not z-fight with the part surface;
6. a fixed official `target` motif is placed at the visible anchor reference while the semantic anchor depth remains the real construction depth;
7. only after the anchor is selected does the real toolbox overlay appear as a compact bottom-center CAD toolbar;
8. the toolbar is built through `build_mode_toolbar_window(...)`, so the API owns grouping, active state, button styles and the `Drawing: ...` badge;
9. the toolbox exposes English modes/actions in this order: `Modify`, `Point`, `Line`, `Rectangle`, `Circle`, `Half-circle`, `Arc`, `Dimension`, `Delete`;
10. the overlay is the only drawing-mode source: these buttons behave as an exclusive enum and exactly one mode is active at a time;
11. `Escape` switches back to `Modify`;
12. while a drawing tool is active, the cursor uses API-owned snap styles (`free`, `vertex`, `edge`, `midpoint`, `intersection`, `center`, `quadrant`, `angle`, ...);
13. `Point`, `Line`, `Rectangle`, `Circle`, `Arc` and `Half-circle` are implemented on top of the sketch kernel;
14. each placed point is an official grabbable actor displayed as a `minimal dot`;
15. smart snap is owned by the API and uses the scene cache plus the topology already placed by the tool;
16. the inspector exposes an `Active part only` snap scope.  The default is scene-wide snapping; when enabled, scene smart-snaps are filtered to the object that owns the picked face while live sketch targets remain available.


## Internal service structure

The built-in Plan Tracer is implemented as a small `CreatorTool` event shell plus
explicit services under `laserprog_studio.tooling.plan_trace_2d`.  New Plan
Tracer code should not add mixins and should not reintroduce a shell-level
delegate dump.  When one service needs another service, the dependency must be
visible at the call site through `self.services.<service>`.

`PlanTrace2DCreatorTool` is intentionally small: new code should call the relevant service directly instead of adding private shell methods.

## Public API boundary

The tool now uses the public `tool_api.plan2d` domain:

```python
from laserprog_studio.tool_api import plan2d
```

The important helpers are:

```python
plan2d.nearest_plan_view(ctx)
plan2d.lock_camera_to_plan_view(ctx, view)
plan2d.pick_plan_anchor_by_raycast(ctx, screen_pos, view=view)
plan2d.project_screen_to_locked_plane(ctx, screen_pos, display_plane, event_world_pos=event.world_pos)
plan2d.semantic_point_for_display_world(semantic_plane, display_plane, display_world)
plan2d.display_point_for_plan_world(semantic_plane, display_plane, semantic_world)
plan2d.world_to_plan_xy(semantic_plane, semantic_world)
plan2d.plan_xy_to_world(semantic_plane, xy)
plan2d.smart_snap_on_plan(ctx, owner_tool=self.id, plane=plane, candidate_world=world, screen_pos=event.screen_pos)
plan2d.register_plan_anchor_target(ctx, owner_tool=self.id, target_id="...", world_pos=anchor_world)
plan2d.register_plan_cursor(ctx, owner_tool=self.id, cursor_id="...", world_pos=world)
plan2d.register_plan_point(ctx, owner_tool=self.id, point_id="...", world_pos=world)
plan2d.register_plan_line(ctx, owner_tool=self.id, line_id="...", start_world_pos=a, end_world_pos=b)
plan2d.register_plan_circle(ctx, owner_tool=self.id, circle_id="...", center_world_pos=c, radius_world_pos=r)
plan2d.register_plan_arc(ctx, owner_tool=self.id, arc_id="...", start_world_pos=a, end_world_pos=b, control_world_pos=c)
plan2d.register_plan_face(ctx, owner_tool=self.id, face_id="...", polygon_world_points=outer_points, hole_world_polygons=(hole_points,))
plan2d.register_plan_dimension(ctx, owner_tool=self.id, dimension_id="...", dimension_world_line=(a, b), label_world_pos=label_pos, label="120 mm")
plan2d.sync_plan_actor_visuals(ctx, owner_tool=self.id, changed_actor_ids=(actor_id,))
```

A tool author should not reimplement these pieces locally.  In particular, they should not create custom PyVista dots, Qt widgets or their own snap/raycast/camera-orientation code for Plan tracer-like tools.

## Anchor-depth contract

The anchor click is raycast-based.  `pick_plan_anchor_by_raycast(...)` first tries the native all-parts VTK cell picker against every visible scene mesh actor (`actors_by_index`), then falls back to the public `ctx.pick.face_at(..., all_parts=True, only_selected=False)` / `ctx.pick.object_at(...)` facade for headless tests or alternate hosts.  It intentionally ignores `event.world_pos` as a height source because that value may come from a generic viewport fallback instead of a real surface.

The resulting `Plan2DAnchorPick` contains two planes plus a diagnostics dictionary:

- `plane`: the semantic construction plane. Every generated geometry point must be clamped to this depth.
- `display_plane`: the official UI plane, moved slightly toward the camera to keep handles, targets and dots visible.
- `diagnostics`: backend used, attempted VTK/Qt coordinate candidates, pick-list count, final depth and fallback reason.  The tool logs a compact `[PLAN_TRACE_RAYCAST]` line on the anchor click so a broken hit can be diagnosed without guessing.

That split is important: the user sees comfortable UI motifs, but the hidden depth axis remains fixed to the anchor height.

## Visual contract

The visual contract comes from Tool Core Analysis and is exposed through the API:

| Element | Official visual |
|---|---|
| Semantic construction plane | locked to the raycast hit depth; fallback depth `0` if no hit |
| Display plane | same 2D plane, offset toward the camera for visible UI motifs |
| Height anchor reference | `target` point style, fixed actor, placed on the display plane |
| Active drawing cursor | API-owned snap cursor; free placement uses a light `diamond`, snapped placement changes motif by snap type |
| Placed 2D point | semantic point stored on the construction plane, visible actor shown as a `minimal dot` on the display plane |
| Editable point interaction | `grabbable` actor |
| Runtime selected/grabbed colors | handled by the native Creator UI runtime |
| Cursor/point refresh | handled through the persistent Creator UI fast path |

The `minimal dot` state colors are not decided by the Plan tracer tool.  The runtime applies the official state colors: idle blue, selected yellow/orange, grabbed orange.

## Overlay toolbox contract

The toolbox is declared with the API helper `build_mode_toolbar_window(...)`, then submitted through `ctx.overlay.show_window(...)`.  The tool does not create any PySide widget directly and does not hand-write checked state, badge fields or action-button policies.

Grouped toolbox buttons are exclusive: clicking a mode selects it and never leaves the palette with no active tool.  The overlay manager updates both its global button table and the stored `OverlayWindowSpec.buttons`, so the checked/highlighted state changes immediately on click.  The Qt adapter also notifies the active Creator tool through `on_overlay_button_clicked(...)`, which lets Plan tracer refresh its mode text without waiting for the next viewport hover.

The selected mode must be visibly highlighted in the overlay.  The native Qt adapter renders the professional glass toolbar, vector sketch icons, the `Drawing: ...` badge, active cyan underline and checked-button highlight, so a Plan tracer-like tool must not invent custom button widgets to get mode highlighting.

The inspector must not contain alternative `Modify`, `Point`, `Line`, etc. mode buttons.  It may expose draft actions such as `Reset`, but drawing mode selection belongs to the overlay palette only.  This keeps Plan tracer mode state deterministic and makes the palette behave like a single enum value.

Before the anchor is selected, the only visible overlay is the anchor prompt. It must not show `Modify`, `Point`, `Line`, or any other drawing mode. The prompt text is:

```text
Click the anchor height point to use for the 2D plan.
```

After the anchor is selected, this prompt is hidden and replaced by the real bottom-center toolbox.

## Interaction/performance contract

The tool declares official actors and motifs.  The Creator runtime handles:

- hover/select/grab;
- point drag fast path;
- empty-click selection clearing;
- camera gestures when no actor is grabbed;
- overlay drag/collision/cleanup;
- viewport redraw and persistent motif updates.

Hover remains non-exclusive: the runtime can update actor hover state, but the tool still receives mouse moves so it can update the drawing cursor and smart-snap result.

## Current limitations

The current implementation has the core drawing modes for `Point`, `Line`, `Rectangle`, `Circle`, `Arc`, `Half-circle` and a passive `Dimension` mode.  The sketch compiler normalizes duplicate points, splits line intersections, splits point-on-arc cases, inserts line/curve and curve/curve intersection vertices, rebuilds polylines and generates selectable faces for closed loops.  Closed loops contained inside another closed loop are now classified as `Face.holes[]` instead of becoming independent filled faces; nested islands inside holes become their own filled faces again.  The API-owned face actor stores hole polygons in metadata, so selection hit-testing ignores the empty hole area while keeping the outer face selectable.

Passive dimensions are stored as semantic references in the sketch document and rendered through the API; the Plan tracer does not own unit formatting, label layout, reference picking or dimension actor metadata.  Dimension mode supports point-to-point aligned measurements, direct edge-length measurements, `Alt` circle radius measurements, normal circle diameter measurements and `Shift` edge-to-edge angle measurements.

Undo/redo is available through snapshot commands (`Ctrl+Z`, `Ctrl+Y`, `Ctrl+Shift+Z`) and is committed once per user action, including Modify drags.  The curve-topology kernel now supports point-on-arc split, line-circle, line-arc, circle-circle, circle-arc and arc-arc intersections, and snap can expose those intersections as typed `SnapKind.INTERSECTION` results.  The next limitations to tackle are dimension editing / driving constraints, visual triangulation quality for curved holes and developer diagnostics.  Those features must stay in the API/sketch-kernel layer so individual Creator tools do not copy topology or snap logic.


## P216 — Metric edit placement base

The Plan Tracer now starts a temporary metric-edit transaction for precise placement.
For Line and Circle, the user still places geometry visually with snap first. After
the second click, the tool compiles the provisional geometry and opens a compact
metric overlay at the top of the viewport below the drawing toolbar.

The overlay currently exposes:

- Line: `Length` and `Angle`;
- Circle: `Radius` and `Diameter`;
- `Validate` to commit the provisional geometry as one undoable command;
- `Cancel` / Escape to restore the snapshot from before the second click.

This is deliberately not a persistent constraint system yet. Temporary metrics,
persistent dimensions and future driving constraints stay separate.

## Implementation structure after service split

The Plan Tracer Creator tool is intentionally no longer implemented as a long
mixin inheritance chain.  `tooling/plan_trace_2d_tool.py` is the CreatorTool
shell: it owns lifecycle hooks, viewport events, overlay callbacks and the
adapter-facing methods such as `resolve_drag_positions(...)`.

Feature behavior is composed through `PlanTrace2DServices`:

- `overlay.py` declares the anchor prompt, toolbox and inspector reporting;
- `selection.py` owns Modify-mode selection and deletion policy;
- `snap.py` owns plan projection, smart-snap cursor updates and drag resolving;
- `sketch_sync.py` owns sketch compilation and actor synchronization;
- `drawing.py` owns primitive placement handlers;
- `metrics.py` owns temporary metric placement transactions;
- `dimensions.py` owns passive dimension placement;
- `history.py` owns snapshot undo/redo;
- `mode_state.py` owns mode transitions and transient-state clearing;
- `rendering.py` owns viewport refresh routing.

This structure keeps the public CreatorTool runtime contract at the shell level
while keeping each feature area testable and readable.  Future Plan Tracer work
should add behavior to an existing service or create a new focused service,
rather than adding new mixins or growing the shell into another monolith.

## P220 — Final structure verification pass

The final cleanup pass keeps Plan Tracer as a composed service graph, not a
mixin chain.  The UI-facing service now imports overlay declarations through the
public `tool_api.visual` domain, while plan coordinate conversion goes through
`tool_api.plan2d.world_to_plan_xy(...)` and
`plan2d.plan_xy_to_world(...)`.  The public API surface now treats
`tool_api.plan2d` as the recommended locked-plane drawing domain; the older
`planar_drawing`, `dimensions` and `metrics` modules are stable aggregate imports.

State-machine checks added in this pass cover the main interaction contract:
anchor prompt before plane lock, exclusive bottom toolbox after plane lock,
mode-switch transient cleanup, Escape back to Modify, and metric-field rollback
when an invalid numeric edit would otherwise desynchronise the UI session from
the rebuilt geometry.


## Pass221 coordinate and snap-target split

The Plan Tracer now has a dedicated `PlanTrace2DCoordinateMapper` service.  Code
that needs to move between display-world, semantic-world and sketch-XY spaces
should use `self.services.coordinates` instead of borrowing helpers from the snap
service.  This keeps plane-depth handling in one place and avoids subtle z-depth
regressions between drawing, dimensions, actor sync and drag.

Live construction snap targets are also isolated in `PlanTrace2DSnapTargetsService`.
`PlanTrace2DSnapService` should stay focused on cursor/constraint/drag interaction
and should not grow back into the owner of line, circle, arc and face target
export.


## Pass 223 — Curve intent boundary

Plan Tracer curve placement now keeps arc and half-circle intent explicit instead
of hiding it inside drawing or metric rebuild helpers.

- `curve_intent.py` owns chord side, major/minor arc interpretation and control-point reconstruction.
- Arc metric angle input is treated as a sweep value, not as a normalized signed line angle.
- Drawing services record intent metadata on generated arcs.
- Metric rebuilders preserve that intent while radius/angle fields are edited.

This keeps future controls such as flip-side, major/minor arc, and curve-direction editing out of the generic overlay/session code.


## Pass225 — Plan 2D API ownership

The Plan 2D package is no longer only a lazy facade over the older modules.
Ownership moved into the focused submodules:

- `tool_api.plan2d.plane` owns plane picking, raycast anchoring, coordinate conversion and `Plan2DCoordinateMapper`;
- `tool_api.plan2d.snap` owns snap cursor semantics, smart snap wrapping and angle/square constraints;
- `tool_api.plan2d.actors` owns official Plan 2D actor declarations and visual metadata;
- `tool_api.plan2d.dimensions` and `tool_api.plan2d.metrics` own the public dimension and temporary metric-edit facades.

`tool_api.planar_drawing`, `tool_api.dimensions` and `tool_api.metrics` remain
small aggregate modules that re-export the new owners.  Plan Tracer code now
uses `tool_api.plan2d.metrics` and `tool_api.plan2d.dimensions` directly, so new
tools have a clear example to copy without importing historical facades.

## Build patterns inside a face

Plan Tracer 2D exposes a Build sub-tool for generated structural motifs.  The
workflow is intentionally explicit so future motif generators do not overload the
normal drawing modes:

1. lock the Plan Tracer plane;
2. press **Pattern** in the Build section or **Select face for pattern** in the inspector;
3. click the existing sketch face to receive the motif;
4. choose the pattern enum (`honeycomb`, `square`, `grid`) and tune cell size,
   wall thickness and margin;
5. press **Generate pattern**.

Pattern generation is not a separate document mesh.  It rewrites the selected
sketch face by adding generated closed loops and suppressing the filled inner
island regions, leaving holes in the selected face.  The resulting sketch still
uses the normal Plan Tracer face solver, undo history and Apply path, so boolean
readiness remains covered by the same manifold extrusion tests as hand-drawn
holes.

Generated pattern entities carry `plan_trace_2d.pattern` metadata.  Regenerating
a motif first removes the previous generated entities, then creates the new
motif.  User-authored points and edges outside that metadata tag are preserved.

## v122 — Boolean-ready output boundary

Plan Tracer must not emit a mesh that relies on a later Boolean repair. The
Apply path now converts solved sketch regions through
`geometry_ops.planar_boolean_solid.extrude_planar_regions_boolean_ready(...)`.

The service owns 2D validity repair, precision normalization, region union,
zero-clearance regularization, extrusion, indexed topology checks, welded
vertex-link checks and Manifold-kernel verification. The Creator tool remains
responsible only for collecting solved face regions, preserving editable-source
metadata and committing the validated WorkMesh.

The preferred production path is `manifold3d.CrossSection.extrude`. The shared
`geometry_ops.manifold_contract` module is also used by `boolean_ops.py`, so the
producer and consumer follow the same Mesh/merge/status rules.

Contract rule for future changes: a Plan Tracer Apply operation either returns
a closed, positively oriented, boolean-accepted 2-manifold, or it fails before
adding anything to the document. Do not reintroduce independent cap and wall
builders in the Creator tool.


## v123 — Apply validation result contract

The v122 boolean-ready service must not export a successful native
`CrossSection.extrude()` solid and import it into Manifold again. The native
CrossSection result is already the kernel-validated canonical solid; a second
conversion can lose coordinate precision and create a false rejection.

Fallback indexed output continues through the shared Manifold contract and
prefers `Mesh64`/`to_mesh64()` where available. Explicit invalid statuses remain
blocking. Optional binding compatibility failures are recorded but do not
invalidate a solid that passed the complete local closed-manifold checks.

The Creator apply callback must always report its result in the Plan Tracer UI:
commit and close on success, or keep the editable sketch open and display the
exact validation error. Never catch a validation exception only in a generic
application status channel, because that makes Apply/Add look inactive.

## v133 — Smart Mesh trace projection

The bottom toolbox now includes **Mesh trace**. This subtool reuses the shared
mesh selection/prediction engine introduced for Cloth, while keeping Plan
Tracer materialisation strictly planar.

Users may select source faces or source edges from another scene part. The
secondary contextual overlay exposes `Coplanar`, `Boundary`, `Continue` and
`Connected` only when those predictions are supported by the current source
selection. The selected geometry is previewed in green after orthogonal
projection onto the active semantic sketch plane.

Projection always uses the locked plane's `u_axis`, `v_axis` and `normal`.
Consequently, geometry from another depth, another principal view or an
inclined part is converted into the correct local 2D coordinates instead of
being copied in global XY. Degenerate projected edges are ignored, nearly
coincident endpoints are merged and duplicate lines are removed before the
sketch compiler solves faces.

`Trace` records one undoable snapshot command, clears temporary source
highlights, hides the Mesh trace overlay and returns to `Modify`. Mesh-derived
curves remain tessellated polylines; analytic circle/arc reconstruction is not
part of this pass.
