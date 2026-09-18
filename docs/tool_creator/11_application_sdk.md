# Application SDK services

Use these services when a tool needs to work on the real Studio document rather than only temporary viewport actors.

## When to use each service

| Service | Use it for |
|---|---|
| `ctx.document` | add, replace, remove and preview meshes |
| `ctx.scene_selection` | selected real scene objects |
| `ctx.pick` | object/face/edge/vertex picking |
| `ctx.preview_session` | preview/apply/cancel workflows |
| `ctx.operations` | modifiers and generators |
| `ctx.jobs` | long operations and progress |
| `ctx.status` | info/warning/error/progress reports |
| `ctx.materials` | mesh material metadata |
| `ctx.assets` | texture/image assets |
| `ctx.engraving` | manufacturing roles/layers |
| `ctx.planar` | workplane/sketch/region helpers |

## Minimal modifier flow

```python
selected = ctx.scene_selection.require_single()
result = ctx.operations.simplify(
    inputs=[selected.mesh],
    params={"ratio": 0.5},
    preview=True,
    owner_tool=self.id,
)

if result.ok:
    ctx.preview_session.apply(label="Apply simplify")
```

## Minimal planar flow

```python
ctx.planar.set_plane(origin=(0, 0, 0), normal=(0, 0, 1))
p1 = ctx.planar.add_point(plane_pos=(0, 0))
p2 = ctx.planar.add_point(plane_pos=(10, 0))
p3 = ctx.planar.add_point(plane_pos=(10, 5))
p4 = ctx.planar.add_point(plane_pos=(0, 5))
ctx.planar.add_line(p1.id, p2.id)
ctx.planar.add_line(p2.id, p3.id)
ctx.planar.add_line(p3.id, p4.id)
ctx.planar.add_line(p4.id, p1.id)
mesh = ctx.planar.generate_mesh(name="Panel")
ctx.document.add_mesh(mesh)
```

## Rule for external creators

Do not import internal controllers for these domains. Prefer:

```python
ctx.materials
ctx.assets
ctx.engraving
ctx.planar
ctx.operations
```
