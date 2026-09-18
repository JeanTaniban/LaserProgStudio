# Source cleanup pass 228 — UI motifs public facade

`tool_api/ui_motifs.py` is now a small public API facade instead of owning the
full motif runtime. Existing imports stay valid, but implementation ownership is
split into private modules:

- `tool_api/ui_motifs.py`: public functions, backward-compatible aliases and `__all__`.
- `tool_api/_ui_motif_contract.py`: snapshot type, family ids and visibility metadata key.
- `tool_api/_ui_motif_builder.py`: runtime builder for actors, handles, previews and overlays.
- `tool_api/_ui_motif_visibility.py`: show/hide semantics for catalog motif families.

The next cleanup should split `_ui_motif_builder.py` by motif family/specification,
then remove the remaining large builder blob without changing the public facade.
