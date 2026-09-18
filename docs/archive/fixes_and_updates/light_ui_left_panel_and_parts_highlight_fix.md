# Light UI left panel and Parts highlight fix

This update keeps Light UI limited to the right inspector pane only.

Changes:
- The left project/parts panel is now non-collapsible in the main splitter.
- Light UI size changes explicitly preserve the left panel width.
- The Parts list now mirrors the current scene selection after selection, clearing, and scene rebuilds.
- The Parts list selected rows now have explicit selected-row styling so they stay visible even when the list does not have keyboard focus.
