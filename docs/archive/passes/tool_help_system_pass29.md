# Tool Help System - Pass 29

LaserProg Studio now exposes contextual Help from the right inspector Tool area.

## User behavior

When a tool or modifier is active, the **Help** button opens a non-modal documentation window. The document explains the tool purpose, important parameters, recommended workflow and practical notes in English. When no tool is active, the Help button stays disabled.

## Architecture

- `tooling/help_docs.py` stores concise Markdown documentation by tool id.
- `application/tool_help_controller.py` owns the Qt help dialog and imports Qt lazily.
- `ui/tool_panels.py` owns only the inspector button placement.
- `application/preview_controller.py` synchronizes button enabled state with the active tool state.

This keeps tool documentation independent from panel layout code, which makes future tools easier to document and review.
