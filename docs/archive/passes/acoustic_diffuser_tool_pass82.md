# Pass 82 — Native acoustic diffuser tool

LaserProg Studio now includes a first native **Acoustic diffuser** tool inspired by the OpenSCAD V17 prototype, without importing or depending on SCAD/BOSL code.

## Scope

The tool is intentionally compact:

- Target frequency
- Outer diameter
- Speaker diameter
- Skirt wall thickness
- Vent style
- Vent count
- Vent size

It generates a preview containing two native meshes:

1. `acoustic_diffuser_skirt`
2. `acoustic_diffuser_core`

The side vents are generated directly as cylindrical mesh openings, not as OpenSCAD booleans. The geometry module also computes a simple report with cavity volume, Helmholtz estimate, exit gap, air-conductance split and coarse Q/bandwidth estimate.

## Architecture

- Math and mesh generation: `geometry_ops/acoustic_diffuser.py`
- UI panel: `ui/tool_panel_factory.py`
- Tool registration: `tooling/registry.py`
- Toolbar item: `ui/toolbar_catalog.py`
- Help text: `tooling/help_docs.py`
- Preview workflow: `application/fabrication_preview_controller.py`

The toolbar entry is available from **+ Tools** but is not added to the default toolbar, keeping the existing 18-item limit intact.
