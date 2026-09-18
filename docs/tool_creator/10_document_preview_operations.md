# 10 - Document, preview sessions and operations

Pass126 adds the application-facing layer needed to migrate the current built-in tools to the creator API.

## Document facade

`ctx.document` is the public way to read and mutate the active scene. It wraps the real `SceneDocument` / `ModelStore` without exposing those internals to external tools.

```python
ctx.document.bind(active_scene)
objects = ctx.document.objects()
meshes = ctx.document.meshes(include_preview=False)

created = ctx.document.add_mesh(mesh, label="Add generated mesh")
ctx.document.replace_mesh(created.id, updated_mesh, label="Update generated mesh")
ctx.document.remove_object(created.id, label="Remove generated mesh")
```

Use it instead of importing the main window, `mesh_store`, or project internals.

## Scene selection

Tool actors and scene objects are separate. Use `ctx.selection` for viewport handles created by the tool, and `ctx.scene_selection` for real meshes/objects.

```python
selected = ctx.scene_selection.selected_objects()
active = ctx.scene_selection.active_object()
mesh = ctx.scene_selection.require_single().mesh
ctx.scene_selection.set_selected([0, 2])
```

## Preview sessions

Generators and modifiers should not directly overwrite the scene during parameter edits. Use a preview session:

```python
session = ctx.preview_session.start(owner_tool=self.id, label="Simplify preview")
session.replace_object_preview(object_id, preview_mesh)

# Apply button
session.apply(label="Simplify applied")

# Cancel/close
session.cancel()
```

The session uses the document preview layer and keeps apply/cancel logic in one place.

## Operation manager

`ctx.operations` is a small registry for previewable mesh operations. It allows tools to separate UI/event code from geometry code.

```python
def simplify(inputs, params, ctx):
    meshes = run_simplify(inputs, ratio=params["ratio"])
    return OperationResult.success(meshes, report="Simplify preview ready")

ctx.operations.register("simplify", simplify)
result = ctx.operations.run_preview(
    "simplify",
    inputs=ctx.scene_selection.selected_meshes(),
    params={"ratio": 0.5},
    owner_tool=self.id,
)
```

A failed operation returns `OperationResult.failure(...)` instead of crashing the UI path.

## Picking

`ctx.pick` delegates to the active scene/viewport backend when available:

```python
hit = ctx.pick.object_at(event.screen_pos)
face = ctx.pick.face_at(event.screen_pos, only_selected=True)
point = ctx.pick.plane_intersection(event.screen_pos, plane)
```

This is the public façade that future face/edge/vertex tools should use.

## Jobs and status

Longer tasks should report progress/status without touching Qt widgets:

```python
job = ctx.jobs.start("Repair mesh", lambda progress: repair_mesh(progress))
ctx.status.warning("Mesh is open; hollow may fail")
ctx.status.error("Boolean failed")
```

The current job manager runs deterministically in-process. Its API shape is designed so the backend can later become threaded without changing creator tools.
