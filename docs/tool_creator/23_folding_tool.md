# Folding Creator tool

`Folding` previews and applies a fold around a flexible strip such as a laser-cut living hinge. It keeps camera navigation available and does not own Qt, VTK or PyVista widgets.

## Current scope

New Folding sessions use the **living-hinge** mode:

- one or more selected meshes form one temporary Folding group;
- the meshes are never geometrically fused: each one keeps its own object identity, name, material and mesh ID;
- the selected face can belong to any member of the group and defines the shared strip plane and normal;
- two points define the limits of the flexible strip;
- one outer region stays fixed;
- the opposite outer region moves with one rigid transform;
- the flexible strip follows an editable smooth centerline;
- the neutral line keeps its original length for every curve profile;
- the terminal fold angle supports multi-turn values from `-720° … 720°`;
- values beyond `|180°|` are intentionally allowed but may create self-intersections; Folding preserves the requested neutral-line path and does not run collision resolution;
- the profile can use 1, 3, 5 or 7 shape handles;
- internal geometry can use a structure-preserving local-rigidity solve or a uniform continuous material deformation.

This is a geometric preview for flexures and laser-cut living hinges. It is not a stress, collision or material-failure simulation. Folding now performs bounded adaptive strip refinement so smoothness no longer depends entirely on the source tessellation.

Projects created by v107-v113 reopen in a hidden legacy free-curve mode. Projects created by v114 reopen as living hinges with a uniform profile, reproducing their circular-arc behavior.

## UX state machine

The tool has five explicit phases:

1. `SELECT_MESH` — preselect one or more meshes, or hover for yellow edges and choose one mesh.
2. `SELECT_FACE` — choose the face containing the hinge strip.
3. `PLACE_START` — place the first strip limit.
4. `PLACE_END` — place the second strip limit.
5. `ADJUST_CURVE` — shape the centerline, set the terminal angle and choose the fixed side.

Both placement phases use `tool_api.plan2d.smart_snap_on_plan(...)` on the
selected face plane. The viewport cursor is the official API-owned Plan 2D
cursor, so its motif and label report the active semantic snap type instead of
using a Folding-specific yellow dot. During `PLACE_END`, holding Shift applies
`tool_api.plan2d.constrain_angle_step_on_plan(...)` with a 45-degree step. The
same constrained point drives the pending interval and the committed endpoint.

When several meshes are selected before Folding starts, they share the same
curve and deformation frame. Preview and Apply replace every selected object in
one atomic transaction. They remain separate scene meshes after Apply and are
reselected together. Clicking one member of an applied Folding group reopens
all persisted members of that group.

The viewport card contains only the current step, one instruction, an optional short status and contextual actions. Detailed numeric controls appear in the inspector only during step 5.

The camera stays free in all picking phases. Pointer movement below 6 px remains a click; a larger movement is camera navigation. `Back` and Escape return to the previous state. Apply and Cancel use the normal Creator lifecycle.

## Editable curve

The blue polyline is the neutral centerline of the flexible band.

- The **blue diamond** controls the final tangent and therefore the rigid rotation of the moving part.
- The **purple ring handles** redistribute curvature inside the band.
- `Shape handles` in the inspector selects 1, 3, 5 or 7 controls.
- `Reset shape` returns the profile to the uniform circular distribution without changing the terminal angle.
- `Reverse` mirrors both the terminal angle and all profile offsets.

With all purple offsets at zero, the tangent angle varies linearly along the strip and the result is the circular arc used by v114. Positive and negative local offsets can create progressive curves, locally concentrated bends, inflection points and S-curves.

## Arc-length-preserving geometry

Let `s` be distance along the original neutral line, `L` the hinge width and `α(s)` the editable tangent-angle profile. The centerline is integrated from a unit tangent:

```text
C'(s) = cos(α(s)) X + sin(α(s)) N
```

where `X` is the original longitudinal axis and `N` is the selected face normal. Because `|C'(s)| = 1`, the generated centerline always has length `L`, independently of its shape.

Each source cross-section at longitudinal coordinate `s` is transported to `C(s)` using the local tangent frame. Consequently:

- the fixed outer region is unchanged;
- pairwise distances inside the moving outer region are unchanged;
- transverse dimensions of the flexible strip are retained;
- the selected neutral surface keeps its longitudinal length;
- the moving region follows the exact terminal tangent;
- choosing the second side as fixed applies the inverse terminal frame.

The neutral line is preserved geometrically. A thick solid still represents the expected inner compression and outer extension of a physical fold.

## Deferred mesh preview

Continuous angle and profile edits never rebuild the 3D mesh:

1. the curve, handles, limits and fixed/moving labels update immediately;
2. the static target-mesh overlay is not resubmitted during the drag;
3. a single-shot timer is restarted after every edit;
4. the expensive mesh replacement runs once after **1.5 seconds without input**;
5. Apply flushes the current result immediately when required.

Projected Drawing uses incremental updates for the lightweight curve actors. Changing the number of profile handles performs one controlled overlay rebuild, but still does not deform the mesh until the idle delay.

## Visual feedback

- selectable old/new mesh: yellow edge hover;
- accepted target: blue outline;
- first strip limit: green;
- second strip limit: orange;
- start/end placement cursor: API-owned Smart Snap motif;
- Shift during second-limit placement: 45° axis constraint;
- fixed and moving sides: short labels;
- terminal-angle adjustment: blue diamond;
- local curve shaping: purple ring handles and faint guide lines.

## Editable persistence

Applied meshes store version-5 `folding_source` metadata containing:

- the undeformed source mesh;
- selected plane;
- strip limits;
- terminal fold angle;
- fixed side;
- shape-angle offsets;
- deformation mode and internal-geometry behaviour.
- the persistent Folding group ID, ordered member IDs and member index.

Each output stores only its own undeformed source mesh. Reopening one member
discovers the other members through the shared group ID, then rebuilds each
object from its own source. Folding therefore remains reversible, does not
accumulate deformation after repeated edits, and never merges the selected
meshes.

## Module boundaries

- `folding/models.py` — domain/session state and profile controls.
- `folding/state_machine.py` — guarded UX transitions.
- `folding/geometry.py` — arc-length centerline integration, rigid transport and legacy kernel.
- `folding/preview_debounce.py` — single-shot idle scheduling.
- `folding/serialization.py` — versioned persistence and migration.
- `folding/rendering.py` — Projected Drawing feedback and incremental curve updates.
- `folding/workflow_overlay.py` — concise viewport card.
- `folding/panel.py` — minimal declarative inspector.
- `folding_tool.py` — Creator event and preview orchestration.
