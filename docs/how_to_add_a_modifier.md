# How to add a mesh modifier - current extension direction

Modifiers are tools that transform selected meshes through preview/apply/cancel.

## 1. Add a modifier operation

The pure geometry operation should eventually live in:

```text
src/laserprog_studio/geometry_ops/
```

Examples:

```text
simplify.py
extrude_down.py
hollow.py
text_relief.py
```

Keep this code independent from Qt/PyVista whenever possible.

## 2. Register the modifier

Add a `ModifierSpec` in:

```text
src/laserprog_studio/modifiers/registry.py
```

Example:

```python
ModifierSpec(
    id="simplify",
    label="Simplify mesh",
    tool_id=TOOL_MOD_SIMPLIFY,
    requires_selection=True,
    interactive=False,
    operation_module="laserprog_studio.geometry_ops.simplify",
)
```

## 3. If it is interactive, reuse manipulators

Split Plane and future Extrude Down should share a future plane/arrow manipulator rather than duplicating VTK actor code.

## 4. Use ParameterSpec for settings

Examples:

- Simplify: ratio, target face count, preserve boundaries.
- Hollow: wall thickness, tolerance, opening mode.
- Extrude Down: plane height, floor height, merge mode.
- Relief: text, font, depth, placement.
