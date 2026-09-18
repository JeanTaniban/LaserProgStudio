# Scene tabs reorder pass 62

- Added arbitrary scene tab reordering through the project model with `ProjectStore.move_scene_to_index()`.
- Improved visible footer tabs drag-and-drop: dropping on the left half inserts before a tab, dropping on the right half inserts after it.
- Added a flexible end drop zone so a scene can be moved after the last tab.
- Kept the active scene unchanged while only the tab order/project metadata changes.
- Added regression tests for arbitrary ordering and the updated drag/drop controller path.
