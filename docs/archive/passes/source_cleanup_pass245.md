# Pass 245 — Tool Core Diagnostic declarative Creator UI

- Migrated Tool Core Diagnostic to the shared `panel_declarative_creator_tool` host.
- Removed the dedicated Qt panel file `ui/tool_panel_diagnostic_panel.py`.
- Expanded the Creator inspector panel so the diagnostic tool still exposes actor setup, visual styles, box selection, validation and showcase actions.
- Updated old source-shape tests to inspect the Creator runtime contract instead of a deleted Qt panel builder.
