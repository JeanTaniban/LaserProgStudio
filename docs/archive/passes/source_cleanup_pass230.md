# Source cleanup pass 230 — Tool Core diagnostic scene split

`application/tool_core_diag_scene.py` is now a public facade instead of the full
PyVista diagnostic renderer.

Runtime ownership is split into private modules:

- `application/tool_core_diag_scene.py`: stable public imports for diagnostic and Creator UI callers.
- `application/_tool_core_diag_scene_state.py`: persistent actor cache, actor-name tracking and scene cleanup.
- `application/_tool_core_diag_scene_painter.py`: PyVista rendering, batched guides, labels and fast point-array updates.
- `tests/_tool_core_diag_scene_sources.py`: test helper that validates the complete runtime source instead of pinning checks to the facade file.

Old source-shape assertions were updated to inspect the full runtime surface.
This keeps behavioral guardrails while allowing the public module to stay small.

Next cleanup should split `tool_api/_ui_motif_builder.py`, now the only Python
runtime file above the 800-line architecture-health threshold.
