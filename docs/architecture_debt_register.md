# Architecture debt register

This register tracks accepted technical debt that still deserves focused cleanup.
It is intentionally short; detailed pass histories live under `docs/archive/`.

## Current hard targets

1. Keep the source architecture gate green through `scripts/quality_gate.py`.
2. Keep both built-in tool audits green:
   `scripts/audit_tool_migration.py --strict` and
   `scripts/audit_tool_product_quality.py --strict`.
3. Continue reducing owner forwarding calls where controllers still need
   `context.owner` because no focused service exists yet.
4. Keep built-in tools on the public Creator API. If a tool needs a private
   import, extend `tool_api` instead.
5. Watchlist modules split recently, but currently acceptable:
   - `src/laserprog_studio/tool_api/_ui_motif_builder.py` and private
     `_ui_motif_*` modules;
   - `src/laserprog_studio/application/_tool_core_diag_scene_painter.py`;
   - `src/laserprog_studio/tooling/_texture_projection_projector.py`;
   - `src/laserprog_studio/tool_core/overlay/qt_adapter.py`.

## Guardrails before each destructive pass

Run the static gate from the repository root:

```bat
py -3.12 scripts\quality_gate.py
```

Then run the relevant focused pytest files for the area being touched. For full
validation, use:

```bat
py -3.12 scripts\quality_gate.py --with-tests --pytest-args -q
```

## Current status

The runtime has no `*Mixin` classes, no `*Mixin` aliases, no oversized runtime
files, no retired source wording and no built-in hook-only tools. All shipped
tools have explicit `CreatorTool` runtimes. They are checked one by one for both
runtime/API entry and user-facing product contract. Vent Generator now uses the
shared declarative Creator panel, owns a pure route state machine for ADD,
MOD, SUPP and RST interactions, and publishes Creator API viewport feedback
through shared preview items plus a route toolbar/status overlay.


## Pass 243 update

Vent Generator now has Creator API quick-start presets, distinct Start over vs Reset route actions, and tests covering preset/custom transitions. Remaining useful work is live desktop verification of the Qt viewport drag path on real models.
- Pass 244: Plan Tracer now uses a richer declarative Creator inspector; the old dedicated Qt Plan Tracer panel is removed from active runtime.

### Pass 246 — Material Painter

Material Painter no longer uses a hand-built Qt tool panel. It is now a Creator declarative tool with presets, target preflight, a viewport feedback overlay and tests for selected/all-part material previews.

### Pass 247 — Gizmo Catalog

Gizmo Catalog now has product-facing view presets and compact reports, so tool authors can review all motifs, author essentials, interaction feedback or viewport feedback without manually hunting through every family toggle. Manual toggle edits correctly enter Custom mode while keeping the motif scene alive.


### Pass 248 — Repair Mesh

Repair Mesh now has presets, preflight checks, auto-preview, explicit Apply/Cancel actions and a viewport feedback overlay. It is aligned with the Creator API product pattern used by Material Painter, Vent Generator and Gizmo Catalog.

### Pass 250 — Hollow Mesh

Hollow Mesh now follows the same product pattern as Repair and Simplify: quick presets, preflight checks, auto-preview, explicit Apply/Cancel actions and a viewport feedback overlay. Wall thickness settings move through a dedicated `mesh_hollow` package so the tool file stays focused on Creator API orchestration.

### Pass 251 — Split Mesh

Split Mesh now follows the same product pattern as Repair, Simplify and Hollow: quick plane presets, dedicated preflight checks, auto-preview, explicit Apply/Cancel actions and a viewport feedback overlay. Plane math and target validation live in a focused `mesh_split` package while `split_tool.py` stays focused on Creator API orchestration.
