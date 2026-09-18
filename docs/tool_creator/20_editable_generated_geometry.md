# 20 - Editable generated geometry

Some tools create meshes that should be reopened later by the same tool instead
of being treated as anonymous triangles. The stable contract is an editable
source stored in `WorkMesh.metadata["editable_source"]`.

## Required metadata

```python
mesh.metadata["editable_source"] = {
    "schema_version": 1,
    "tool_id": "tool:plan_trace_2d",
    "kind": "plan_trace_2d_extrusion",
    "plane": {...},
    "display_plane": {...},
    "anchor_world": (x, y, z),
    "extrusion_depth_mm": 10.0,
    "sketch": {...},
}
```

Keep a small top-level signature as well:

```python
mesh.metadata["source_tool"] = tool_id
mesh.metadata["editable_tool_id"] = tool_id
mesh.metadata["editable_kind"] = kind
```

Hover/pick code may inspect only the small signature first. It must not fully
deserialize a large sketch on every mouse move.

## Reopen flow

A tool in its initial pick phase may accept either a normal face or a compatible
editable object:

1. pick a scene face/object;
2. check `editable_source.tool_id` and `editable_source.kind`;
3. highlight the object as editable;
4. on click, deserialize the source;
5. restore plane, sketch, depth and camera;
6. enter edit mode;
7. on Apply, replace the original object rather than adding a second mesh.

## Replacement rule

Use `ctx.document.replace_mesh(object_id, mesh, label=..., push_undo=True)` for
editable geometry. Preserve the original object identity, name, material and the
stored extrusion depth unless the tool explicitly exposes a depth edit.

## Performance rule

Editable hover is a UI affordance. It must not invalidate the scene snap cache
and must not rebuild the whole tool. Use a cheap preview/outline and update it
only when the hovered editable object changes.


## Recoverable drafts / cancelled sketches

A drawing tool may also store an unfinished but recoverable sketch as a visible
placeholder object. Plan Tracer uses the same `editable_source` envelope with a
different kind:

```python
mesh.metadata["editable_source"]["kind"] = "plan_trace_2d_draft"
mesh.metadata["plan_trace_placeholder"] = True
mesh.metadata["plan_trace_placeholder_kind"] = "draft_bounds"
```

The placeholder mesh is deliberately cheap: a red bounding box/cuboid around the
current sketch bounds. It is not a generated final part; it is a resume handle.
When the user clicks it from the tool's initial pick phase, the tool restores the
stored sketch and plane just like a normal editable extrusion.

Apply must promote the draft placeholder by replacing the placeholder object with
the generated final mesh:

```python
ctx.document.replace_mesh(draft_object_id, final_mesh, label="Promote ...", push_undo=True)
```

This keeps the scene clean: Cancel preserves work as one red recoverable object,
and Apply replaces that object instead of creating a duplicate.

## Edit-source visibility rule

When an editable mesh or recoverable draft is reopened, the source object must
not remain as normal scene geometry during the edit.  Leaving it visible creates
ambiguous picking and feeds the old vertices/edges back into smart snap, so the
user ends up drawing inside the previous volume.

Recommended behavior:

1. keep a deep copy of the source mesh in the tool state;
2. remove or hide the source object before the sketch is restored;
3. rebuild only the scene/snap cache needed for editing;
4. on Apply, restore the source object just before `replace_mesh(...)` if the
   document API needs it, then replace it atomically with the new generated mesh;
5. on Cancel, replace the hidden source with a red recoverable draft placeholder.

This gives clean snapping while preserving object identity and undo semantics.
Do not keep the source mesh visible and try to filter it only in the snap code:
that still leaves confusing visual overlap and host-specific pick targets.
