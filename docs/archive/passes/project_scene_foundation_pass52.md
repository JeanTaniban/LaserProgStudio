# Pass52 — Project/scene foundation

This pass prepares the project/scenes/history/autosave work without forcing the
legacy UI controllers to migrate in one large step.

## Added

- Stable `WorkMesh.mesh_id` values with helpers to ensure or regenerate ids.
- `laserprog_studio.project` package:
  - `ProjectStore`
  - `SceneDocument`
  - `SceneModificationHistoryEntry`
  - `AutosavePolicy`
  - runtime bridge helpers for the legacy `self.mesh_store` alias.
- A default in-memory project with a `main` scene during runtime initialization.
- A semantic scene history model that deliberately excludes small transforms.
- Restore-from-history foundation: snapshots can create a new independent scene.
- Autosave timing policy with soft idle saves and forced deferred saves.

## Compatibility

The active scene `ModelStore` remains exposed as `window.mesh_store`, so existing
controllers keep working while project-aware UI tabs, project files, and the full
History restore UI are added in later passes.

## Decisions kept

- Ctrl+Z stays in RAM only.
- Ctrl+Z remains technical and includes transforms.
- Visible scene history is semantic only.
- Restoring a history entry creates a new scene instead of replacing the current one.

## Project file groundwork

A first `.lpsproj` reader/writer was also added in `laserprog_studio.io.project_file`.
It writes a ZIP container with:

- `manifest.json`
- `project.json`
- one `scene.json` per scene
- compressed NumPy mesh payloads (`.npz`)
- semantic history entries
- restorable scene snapshots

The writer has an atomic variant: it writes a temporary sibling file first, then
replaces the destination once the archive is complete. This is the mechanism that
future manual saves and autosaves should share.
