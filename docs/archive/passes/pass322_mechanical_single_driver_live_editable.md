# Pass 322 — Mechanical single driver, live actor motion, editable persistence

This pass aligns Mechanical Motion persistence with the Plan Tracer CAD lifecycle and removes the expensive per-frame scene rebuild from Test mode.

## Single driver contract

A mechanical assembly owns at most one rotary driver. Assigning a new generated gear or scene part clears the previous driver and its transient angle. Older serialized assemblies containing several drivers are normalized to their newest driver when loaded.

Projected gear and shaft actors now carry the exact `mechanical_gear_id` selected by the user. Driver creation consumes that identifier instead of falling back to the first gear in a chain.

## Fast Test mode

`live_motion.py` captures neutral VTK user matrices only for actors that can actually move:

- generated shaft meshes;
- the external driver part;
- attached moving parts.

Animation ticks update those actor matrices and the single manual rotation handle. They do not rebuild meshes, the scene, the inspector, or the complete projected overlay registry. Angles are normalized to one revolution and the neutral matrices are restored on Apply, Cancel, Test exit, or preview regeneration.

## Editable Apply and visible Cancel

Every applied shaft mesh and draft placeholder now advertises:

- `source_tool = mechanical_motion`;
- `editable_tool_id = mechanical_motion`;
- an applied or draft `editable_kind`;
- the complete serialized assembly payload.

Cancel writes the draft to the committed document, rebuilds the scene immediately, and selects the red placeholder. Apply detection compares only persistent mechanical data, ignoring transient UI selection, so a successful generic host Apply is never rewritten as a draft during tool cleanup.
