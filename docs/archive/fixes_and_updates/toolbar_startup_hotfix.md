# Toolbar startup hotfix

Fixed a startup crash introduced by the configurable toolbar pass 2.

Cause:
- Dynamic toolbar items were rebuilt before `tool_group` / `modifier_group` existed.

Fix:
- `_setup_configurable_toolbar()` now creates both button groups defensively before it builds dynamic buttons.
