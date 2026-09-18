# Source restructure - pass 2

This pass continues the non-destructive cleanup started in pass 1.

Goal: reduce large Python files, isolate responsibilities, and keep the current application behavior unchanged.

## Main application UI split

`src/laserprog_studio/ui/panels.py` is now only a compatibility/composite mixin.

New focused UI modules:

- `ui/actions_menus.py`: actions, shortcuts, menus, global stylesheet.
- `ui/layout_panels.py`: main layout, left panel, center panel, 3D and engraving workspaces, right inspector shell.
- `ui/floor_grid.py`: floor grid toggle, grid actor creation/removal.
- `ui/transform_controls.py`: transform buttons, snap controls, history/boolean button syncing.
- `ui/tool_panels.py`: per-tool inspector panels.
- `ui/light_transform_overlay.py`: compact transform overlay and inspector light-mode detection.
- `ui/status_startup.py`: status bar and post-start initialization.

## Transform/gizmo split

`src/laserprog_studio/controllers/gizmo_transform.py` is now only a compatibility/composite mixin.

New focused modules:

- `controllers/gizmo_overlay.py`: foreground renderer and overlay actor registration.
- `controllers/transform_geometry.py`: axes, bounds, scale frame geometry, visible-size helpers.
- `controllers/transform_math.py`: quaternion, Euler, ray, angle and point-update math.
- `controllers/transform_drag.py`: drag start/update/finish for translation, rotation and scale.
- `controllers/gizmo_highlight.py`: hover and selected-axis highlighting.
- `controllers/gizmo_view.py`: gizmo rebuild and display toggles.
- `controllers/transform_inspector.py`: live transform fields and inspector synchronization.

## Toolbox split

Large legacy toolbox modules were split while keeping their original public entry points.

### Joint builder

`tools/joint_builder.py` is now a small compatibility wrapper containing the Tk `ToolFrame`.
The computation is split into:

- `tools/joint_builder_basis.py`: settings, basis estimation, polygon extrusion and low-level helpers.
- `tools/joint_builder_contact_points.py`: contact-point and seam-point helpers.
- `tools/joint_builder_contact_faces.py`: planar face extraction, contact patch and oriented boolean tool geometry.
- `tools/joint_builder_rays.py`: ray tests, boolean bridge and diagnostics.
- `tools/joint_builder_depth.py`: local thickness/depth probes and seam interval helpers.
- `tools/joint_builder_core.py`: high-level `apply_tab_slot_simple` workflow.

The legacy imports still work:

- `from tools.joint_builder import apply_tab_slot_simple`
- `from tools.joint_builder import PlankBasis`
- `from tools.joint_builder import ToolFrame`

### Lay-flat arranger

`tools/layflat_arranger.py` is now a compatibility wrapper containing the Tk `ToolFrame`.
The computation is in:

- `tools/layflat_core.py`

Legacy imports still work:

- `from tools.layflat_arranger import read_3mf_meshes`
- `from tools.layflat_arranger import process_3mf`
- `from tools.layflat_arranger import ToolFrame`

## Engraving generator split

`src/engraving_generator/laser_3mf_gui.py` is now a small compatibility entry point.

New modules:

- `laser_3mf_core.py`: 3MF parsing, color role detection, geometry and rendering helpers.
- `image_panel.py`: zoomable image panel.
- `laser_3mf_app_lifecycle.py`: application startup/run lifecycle.
- `laser_3mf_app_ui.py`: Tk layout and parameter controls.
- `laser_3mf_app_presets.py`: preset file management.
- `laser_3mf_app_render_export.py`: rendering and PNG/JSON export.

Legacy imports still work:

- `from laser_3mf_gui import Laser3MFSingleWindowApp`
- `from laser_3mf_gui import read_3mf_model`
- `from laser_3mf_gui import RenderConfig`

## Validation performed

- Full Python syntax compilation completed successfully.
- Legacy import checks completed successfully for:
  - `tools.joint_builder`
  - `tools.layflat_arranger`
  - `laser_3mf_gui`
- Example 3MF read checks completed successfully:
  - `examples/box.3mf`: 6 meshes read by the lay-flat parser.
  - `examples/layflat_parts.3mf`: 6 laser instances read by the engraving parser.
- No functional algorithms were intentionally changed in this pass.

## Recommended pass 3

Recommended next cleanup targets:

1. Split `controllers/interaction.py`, especially the large `eventFilter` method.
2. Split `controllers/scene.py` into scene rebuild, selection state, preview lifecycle and tool lifecycle modules.
3. Convert the legacy toolbox import style to package-relative imports once all entry points are stable.
4. Add small unit tests for:
   - snapping math;
   - quaternion/rotation inspector state;
   - copy/paste delta placement;
   - joint builder core workflow with minimal meshes.
