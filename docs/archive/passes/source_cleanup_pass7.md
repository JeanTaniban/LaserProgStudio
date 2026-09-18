# Source cleanup pass 7

Goal: continue the aggressive cleanup started in pass 4-6 by splitting the remaining large source files into focused modules without changing the public imports used by the application.

## Main extractions

### Scene tabs

`src/laserprog_studio/controllers/scene_tabs.py` is now a small aggregate. The implementation is split into:

- `scene_tabs_frame.py` — draggable tab frame/widget behavior.
- `scene_tabs_sync.py` — visible footer synchronization with the project store and hidden compatibility `QTabBar`.
- `scene_tabs_actions.py` — scene creation, switching and closing actions.
- `scene_tabs_drag.py` — drag preview, ghost widget and reorder-on-release behavior.

Public API kept stable:

```python
from laserprog_studio.controllers.scene_tabs import SceneTabsMixin, DraggableSceneTabFrame
```

### Tool Core app services

`src/laserprog_studio/tool_core/app_services.py` was replaced by the package `src/laserprog_studio/tool_core/app_services/`. Services are now separated by role:

- `common.py` — shared `ToolServiceError`.
- `document.py` — `DocumentFacade` and `DocumentObject`.
- `selection.py` — `SceneSelectionFacade`.
- `picking.py` — `PickingFacade` and `PickResult`.
- `preview.py` — `PreviewSession` and `PreviewSessionManager`.
- `operations.py` — `OperationManager` and `OperationResult`.
- `jobs.py` — `JobManager`, `Job`, `JobState`.
- `status.py` — `StatusManager`, `StatusMessage`.

The package `__init__.py` re-exports the same public symbols, so existing imports from `laserprog_studio.tool_core.app_services` keep working.

### Image mask relief

`geometry_ops/image_mask_relief.py` is now a public API wrapper. The implementation is split into:

- `image_mask_relief_types.py` — result/stat dataclasses.
- `image_mask_relief_loading.py` — image loading, thresholding and binary mask helpers.
- `image_mask_relief_preview.py` — preview rendering.
- `image_mask_relief_heightfield.py` — grayscale heightfield mesh builder.
- `image_mask_relief_vector.py` — binary/vector extrusion pipeline.

### Joint builder depth

`fabrication/joint_builder_depth.py` now aggregates focused modules:

- `joint_builder_depth_measure.py` — thickness/depth measurement helpers.
- `joint_builder_depth_seam.py` — seam and depth-aware joint construction.

## Test updates

Some tests were intentionally static and previously read monolithic files directly. They now use helper readers that concatenate the split module families:

- `tests/_scene_tabs_source.py`
- `tests/_image_mask_relief_source.py`

This keeps the architectural tests meaningful after the source split.

## Validation

Validated with:

```bash
python -m compileall -q src tests scripts run.py
python scripts/verify_refactor_structure.py
python scripts/audit_architecture_health.py
timeout 420s pytest -q
```

Result:

```text
569 passed, 3 skipped, 81 warnings
```

Architecture audit after this pass:

```text
Python files        : 364
Mixin classes       : 68
Large files >=800 L : 0
```

The remaining warnings are existing Pillow/Shapely deprecations.
