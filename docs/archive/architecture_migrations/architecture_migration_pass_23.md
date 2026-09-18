# Architecture migration pass 23 — Vent Only walls

## Goal

Add a production-ready **Only walls** option to the audio vent generator without weakening the planar-tools architecture.

## Behaviour

- The option is exposed in the vent tool panel as **Only walls : sans sol ni toit**.
- It is valid only for square/rectangular vents.
- Round vents ignore the flag and keep their closed tube geometry.
- For rectangular vents, the generated duct keeps the two lateral wall strips and omits the roof/floor strips that face the locked camera plane.
- Existing compact/shared-wall constraints still apply before mesh generation.

## Implementation

Updated modules:

- `planar_tools/vent_model.py`
  - adds `VentPathDraft.only_walls`;
  - adds `VentPathDraft.uses_only_walls()` so the rectangle-only rule lives in the pure model.

- `planar_tools/mesh_generation.py`
  - adds a small cross-section edge filter;
  - rectangular Only walls keeps only ring edges `1` and `3`;
  - full rectangle and round vents continue to generate all edges.

- `ui/tool_panel_factory.py`
  - adds the checkbox to the vent panel;
  - keeps it disabled for round vents.

- `application/planar_tool_controller.py`
  - synchronizes the option from UI to model;
  - automatically clears/disables it when the vent type is round;
  - reports the active Only walls state.

## Tests

`tests/test_vent_only_walls_pass23.py` verifies:

- the option is effective only for rectangular sections;
- a rectangular Only walls mesh omits exactly half of the rectangular edge strips;
- round vents ignore the flag and keep their closed geometry.
