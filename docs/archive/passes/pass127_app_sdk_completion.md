# Pass127 – Application SDK completion

Pass127 extends the creator API beyond viewport-only tools. The goal is to make current Studio tools migratable without importing historical controllers or Qt/PyVista internals.

## Added public services

The creator context now exposes:

```python
ctx.materials
ctx.assets
ctx.engraving
ctx.planar
```

Together with the Pass126 services:

```python
ctx.document
ctx.scene_selection
ctx.pick
ctx.preview_session
ctx.operations
ctx.jobs
ctx.status
```

## Materials

```python
material = ctx.materials.create("Birch", base_color="#D8B16A")
ctx.materials.assign(object_id, material)
ctx.materials.assign_selected(material)
ctx.materials.get(object_id)
ctx.materials.list()
```

## Texture assets

```python
texture = ctx.assets.import_image("texture.png", usage="engrave")
ctx.assets.attach_to_material(object_id, texture.id)
ctx.assets.list_textures()
ctx.assets.get_texture(texture.id)
```

## Engraving roles

```python
ctx.engraving.roles()
ctx.engraving.assign_role(object_id, "outline")
ctx.engraving.assign_selected("fill")
ctx.engraving.role_for(object_id)
```

## Planar SDK

```python
ctx.planar.set_plane(origin=(0, 0, 0), normal=(0, 0, 1))
p1 = ctx.planar.add_point(plane_pos=(0, 0))
p2 = ctx.planar.add_point(plane_pos=(10, 0))
line = ctx.planar.add_line(p1.id, p2.id)
regions = ctx.planar.solve_regions()
mesh = ctx.planar.generate_mesh(regions[0])
```

This is the first public workplane layer for Plan Tracer and Vent Generator migration.

## High-level gizmos

`ctx.gizmos` now exposes manipulator factories:

```python
ctx.gizmos.translate(id="move", owner_tool=tool_id)
ctx.gizmos.rotate(id="rot", owner_tool=tool_id)
ctx.gizmos.scale(id="scale", owner_tool=tool_id)
ctx.gizmos.plane(id="split", owner_tool=tool_id, origin=origin, normal=normal)
ctx.gizmos.box_bounds(id="bounds", owner_tool=tool_id, bounds=bounds)
```

They are built from persistent handles, so tools do not need to rebuild VTK actors on every hover/drag update.

## Standard operation helpers

`ctx.operations` now includes standard modifier names:

```python
ctx.operations.repair(...)
ctx.operations.simplify(...)
ctx.operations.hollow(...)
ctx.operations.split(...)
ctx.operations.extrude_down(...)
ctx.operations.boolean_union(...)
ctx.operations.boolean_subtract(...)
ctx.operations.relief(...)
```

Each helper can delegate to a registered operation or to a bound backend method such as `operation_simplify(...)`. They support `preview=True` to automatically open a preview session.

## API version

The creator API is now `0.10.0`.
