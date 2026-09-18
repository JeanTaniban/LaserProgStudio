# Source restructure - pass 1

## Goal

This pass keeps the validated application behavior unchanged while making the Python sources easier to read and navigate.

The main target was `src/laserprog_studio/window.py`, which had grown to about 5869 lines and mixed many unrelated responsibilities:

- UI construction
- inspector and light overlay management
- mouse and keyboard interaction
- scene state and preview handling
- fixed camera views and navigation
- transform gizmo rendering and transform math
- engraving roles
- boolean tools
- clipboard / duplicate logic
- undo / redo history
- export and rendering actions

## Strategy

This is a non-destructive restructuring pass. The methods were moved into thematic mixins without changing their logic.

`LaserProgStudioV18` still exists in `src/laserprog_studio/window.py`, but it now inherits focused mixins.

## New layout

```text
src/laserprog_studio/
  window.py                         # main application class, constants, initialization
  _window_deps.py                   # shared imports for legacy window mixins
  ui/
    panels.py                       # UI construction, toolbar, inspector, light overlay
  controllers/
    interaction.py                  # Qt/VTK events, picking, selection probes
    scene.py                        # scene storage, preview, selection, tool open/close
    tool_previews.py                # box, layflat, joint preview workflows
    camera.py                       # camera modes, pan/zoom, fixed views
    gizmo_transform.py              # transform gizmos, transform inspector, math helpers
    engraving_roles.py              # engraving role painting and material colors
    booleans_clipboard_history.py   # booleans, copy/paste/duplicate, undo/redo, delete
    exporting.py                    # primitive creation, 3MF export, engraving export
```

## Line count impact

Before:

```text
src/laserprog_studio/window.py      ~5869 lines
```

After:

```text
src/laserprog_studio/window.py       ~159 lines
src/laserprog_studio/ui/panels.py   ~1598 lines
src/laserprog_studio/controllers/gizmo_transform.py ~1492 lines
```

No `laserprog_studio` file is above 1600 lines after this pass.

## Compatibility notes

The refactor intentionally keeps method names and public behavior stable.

Examples kept stable:

- transform modes and gizmos
- multi-selection
- copy / paste / duplicate
- booleans
- undo / redo
- preview tools
- light transform overlay
- fixed orthographic camera views
- floor grid toggle

## Next recommended passes

1. Split `controllers/gizmo_transform.py` further into:
   - `gizmo_rendering.py`
   - `transform_drag.py`
   - `rotation_math.py`
   - `scale_handles.py`

2. Split `ui/panels.py` further into:
   - `toolbar.py`
   - `inspector.py`
   - `tool_panels.py`
   - `light_overlay.py`

3. Refactor `src/laser_toolbox/tools/joint_builder.py`, currently still the largest file, into:
   - joint detection
   - tab/slot geometry
   - preview generation
   - validation/reporting

4. Move the engraving generator GUI into a cleaner package structure.

## Validation

- Python syntax compilation: OK
- All original `LaserProgStudioV18` methods are still present after the split: OK
- No generated `__pycache__` included in the archive
- ASCII-only text/code files preserved
