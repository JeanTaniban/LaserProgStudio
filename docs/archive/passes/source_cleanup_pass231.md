# Source cleanup pass 231 — UI motif builder split

## Goal

Finish the large-file cleanup started by the public `tool_api.ui_motifs` facade.
The previous private builder was still a runtime blob even though it was no
longer public API.

## Changes

- Reduced `tool_api/_ui_motif_builder.py` from 832 lines to an orchestration
  layer under 260 lines.
- Extracted focused private modules:
  - `_ui_motif_runtime.py` for actor/handle registration and synchronization.
  - `_ui_motif_actor_rows.py` for actor-kind and interaction catalogue rows.
  - `_ui_motif_style_rows.py` for visual, point and line style rows.
  - `_ui_motif_showcase_rows.py` for manipulators, previews and overlays.
- Preserved `CreatorUiMotifBuilder` and the public `tool_api.ui_motifs` exports.
- Added `tests/test_pass231_ui_motif_builder_split.py` as a source guardrail.

## Validation

- `python scripts/quality_gate.py`
- Focused UI motif tests, including passes 172, 174, 175, 176, 177, 178, 180,
  228 and 231.

## Result

The architecture health report now shows zero runtime files above the 800-line
large-file threshold. Future cleanup should target compatibility/mixin debt,
not another single oversized runtime file.
