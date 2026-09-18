# Cloth workflow diagnostics

- Export reason: `cloth_apply_blocked`
- Captured events: **69**
- Dropped events: **0**
- Errors captured: **0**

## Stage counts

| Stage | Count |
|---|---:|
| `action.overlay_button` | 1 |
| `action.route` | 1 |
| `apply.pipeline.end` | 1 |
| `apply.pipeline.start` | 1 |
| `apply.request.end` | 1 |
| `apply.request.feedback_visible` | 1 |
| `apply.request.start` | 1 |
| `apply.request.validation.end` | 1 |
| `apply.request.validation.start` | 1 |
| `overlay.sync.end` | 8 |
| `overlay.sync.start` | 8 |
| `overlay.sync.workflow_window_shown` | 8 |
| `pick.frontmost` | 4 |
| `session.export` | 1 |
| `session.start` | 1 |
| `ui.sync.end` | 8 |
| `ui.sync.overlay_synced` | 8 |
| `ui.sync.renderer_synced` | 6 |
| `ui.sync.start` | 8 |

## Latest state

```json
{
  "apply": {
    "can_apply": false,
    "can_apply_error": "",
    "editing_existing": false,
    "pending_draw_points": 0,
    "source_flat_scene_id": null,
    "source_mesh_id": null,
    "validation_can_apply": false,
    "validation_error": "",
    "validation_errors": [],
    "validation_present": false,
    "validation_warnings": []
  },
  "document": {
    "curves": 0,
    "layers": 0,
    "patches": 0,
    "points": 0,
    "revision": 0
  },
  "interaction": {
    "hovered_patch_group_ids": [],
    "hovered_patch_id": null,
    "proposal_count": 0,
    "proposal_index": 0,
    "stage": "main"
  },
  "overlay": {
    "accent_color": "#38BDF8",
    "available": true,
    "buttons": [
      {
        "enabled": false,
        "id": "cloth.workflow.action.take_face",
        "label": "Take face",
        "style": "ghost"
      },
      {
        "enabled": false,
        "id": "cloth.workflow.action.open_closure",
        "label": "Close",
        "style": "secondary"
      },
      {
        "enabled": true,
        "id": "cloth.workflow.action.open_draw",
        "label": "Draw",
        "style": "secondary"
      },
      {
        "enabled": true,
        "id": "cloth.workflow.action.open_properties",
        "label": "Properties",
        "style": "secondary"
      },
      {
        "enabled": false,
        "id": "cloth.workflow.action.apply_output",
        "label": "Apply",
        "style": "secondary"
      }
    ],
    "persistent": true,
    "present": true,
    "title": "Cloth",
    "window_id": "cloth.workflow"
  },
  "selection": {
    "persistent_textile_groups": [],
    "smart_selected_meshes": 0,
    "smart_selected_regions": 0,
    "tracked_textile_groups": []
  },
  "session": {
    "dirty": false,
    "edit_mode": "mesh_trace",
    "phase": "editing",
    "selected_curve_ids": [],
    "selected_patch_ids": [],
    "selected_point_ids": []
  },
  "workspace": {
    "can_apply_close": false,
    "can_close": false,
    "can_take_face": false,
    "close_proposal_count": 0,
    "close_proposal_index": 0,
    "message": "Cloth needs at least one textile face before Apply.",
    "overlay_mode": "main",
    "phase": "selecting",
    "selected_source_meshes": 0,
    "selected_source_regions": 0,
    "selected_textile_edges": 0,
    "selected_textile_faces": 0
  }
}
```

## Latest Apply events

```json
[
  {
    "at_ms": 3.1502,
    "can_apply": false,
    "operation_id": 13,
    "pending_draw_points": 0,
    "seq": 50,
    "source": "creator_apply",
    "stage": "apply.request.start",
    "state": {
      "apply": {
        "can_apply": false,
        "can_apply_error": "",
        "editing_existing": false,
        "pending_draw_points": 0,
        "source_flat_scene_id": null,
        "source_mesh_id": null,
        "validation_can_apply": false,
        "validation_error": "",
        "validation_errors": [],
        "validation_present": false,
        "validation_warnings": []
      },
      "document": {
        "curves": 0,
        "layers": 0,
        "patches": 0,
        "points": 0,
        "revision": 0
      },
      "interaction": {
        "hovered_patch_group_ids": [],
        "hovered_patch_id": null,
        "proposal_count": 0,
        "proposal_index": 0,
        "stage": "main"
      },
      "overlay": {
        "accent_color": "#38BDF8",
        "available": true,
        "buttons": [
          {
            "enabled": false,
            "id": "cloth.workflow.action.take_face",
            "label": "Take face",
            "style": "ghost"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.open_closure",
            "label": "Close",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_draw",
            "label": "Draw",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_properties",
            "label": "Properties",
            "style": "secondary"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.apply_output",
            "label": "Apply",
            "style": "secondary"
          }
        ],
        "persistent": true,
        "present": true,
        "title": "Cloth",
        "window_id": "cloth.workflow"
      },
      "selection": {
        "persistent_textile_groups": [],
        "smart_selected_meshes": 0,
        "smart_selected_regions": 0,
        "tracked_textile_groups": []
      },
      "session": {
        "dirty": false,
        "edit_mode": "mesh_trace",
        "phase": "editing",
        "selected_curve_ids": [],
        "selected_patch_ids": [],
        "selected_point_ids": []
      },
      "workspace": {
        "can_apply_close": false,
        "can_close": false,
        "can_take_face": false,
        "close_proposal_count": 0,
        "close_proposal_index": 0,
        "message": "Selection cleared.",
        "overlay_mode": "main",
        "phase": "selecting",
        "selected_source_meshes": 0,
        "selected_source_regions": 0,
        "selected_textile_edges": 0,
        "selected_textile_faces": 0
      }
    }
  },
  {
    "at_ms": 3.3675,
    "operation_id": 13,
    "seq": 57,
    "stage": "apply.request.feedback_visible",
    "state": {
      "apply": {
        "can_apply": false,
        "can_apply_error": "",
        "editing_existing": false,
        "pending_draw_points": 0,
        "source_flat_scene_id": null,
        "source_mesh_id": null,
        "validation_can_apply": false,
        "validation_error": "",
        "validation_errors": [],
        "validation_present": false,
        "validation_warnings": []
      },
      "document": {
        "curves": 0,
        "layers": 0,
        "patches": 0,
        "points": 0,
        "revision": 0
      },
      "interaction": {
        "hovered_patch_group_ids": [],
        "hovered_patch_id": null,
        "proposal_count": 0,
        "proposal_index": 0,
        "stage": "main"
      },
      "overlay": {
        "accent_color": "#38BDF8",
        "available": true,
        "buttons": [
          {
            "enabled": false,
            "id": "cloth.workflow.action.take_face",
            "label": "Take face",
            "style": "ghost"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.open_closure",
            "label": "Close",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_draw",
            "label": "Draw",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_properties",
            "label": "Properties",
            "style": "secondary"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.apply_output",
            "label": "Apply",
            "style": "secondary"
          }
        ],
        "persistent": true,
        "present": true,
        "title": "Cloth",
        "window_id": "cloth.workflow"
      },
      "selection": {
        "persistent_textile_groups": [],
        "smart_selected_meshes": 0,
        "smart_selected_regions": 0,
        "tracked_textile_groups": []
      },
      "session": {
        "dirty": false,
        "edit_mode": "mesh_trace",
        "phase": "editing",
        "selected_curve_ids": [],
        "selected_patch_ids": [],
        "selected_point_ids": []
      },
      "workspace": {
        "can_apply_close": false,
        "can_close": false,
        "can_take_face": false,
        "close_proposal_count": 0,
        "close_proposal_index": 0,
        "message": "Applying Cloth and regenerating the flat preview…",
        "overlay_mode": "main",
        "phase": "selecting",
        "selected_source_meshes": 0,
        "selected_source_regions": 0,
        "selected_textile_edges": 0,
        "selected_textile_faces": 0
      }
    }
  },
  {
    "at_ms": 3.3775,
    "operation_id": 13,
    "seq": 58,
    "stage": "apply.request.validation.start",
    "state": {
      "apply": {
        "can_apply": false,
        "can_apply_error": "",
        "editing_existing": false,
        "pending_draw_points": 0,
        "source_flat_scene_id": null,
        "source_mesh_id": null,
        "validation_can_apply": false,
        "validation_error": "",
        "validation_errors": [],
        "validation_present": false,
        "validation_warnings": []
      },
      "document": {
        "curves": 0,
        "layers": 0,
        "patches": 0,
        "points": 0,
        "revision": 0
      },
      "interaction": {
        "hovered_patch_group_ids": [],
        "hovered_patch_id": null,
        "proposal_count": 0,
        "proposal_index": 0,
        "stage": "main"
      },
      "overlay": {
        "accent_color": "#38BDF8",
        "available": true,
        "buttons": [
          {
            "enabled": false,
            "id": "cloth.workflow.action.take_face",
            "label": "Take face",
            "style": "ghost"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.open_closure",
            "label": "Close",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_draw",
            "label": "Draw",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_properties",
            "label": "Properties",
            "style": "secondary"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.apply_output",
            "label": "Apply",
            "style": "secondary"
          }
        ],
        "persistent": true,
        "present": true,
        "title": "Cloth",
        "window_id": "cloth.workflow"
      },
      "selection": {
        "persistent_textile_groups": [],
        "smart_selected_meshes": 0,
        "smart_selected_regions": 0,
        "tracked_textile_groups": []
      },
      "session": {
        "dirty": false,
        "edit_mode": "mesh_trace",
        "phase": "editing",
        "selected_curve_ids": [],
        "selected_patch_ids": [],
        "selected_point_ids": []
      },
      "workspace": {
        "can_apply_close": false,
        "can_close": false,
        "can_take_face": false,
        "close_proposal_count": 0,
        "close_proposal_index": 0,
        "message": "Applying Cloth and regenerating the flat preview…",
        "overlay_mode": "main",
        "phase": "selecting",
        "selected_source_meshes": 0,
        "selected_source_regions": 0,
        "selected_textile_edges": 0,
        "selected_textile_faces": 0
      }
    }
  },
  {
    "at_ms": 3.4078,
    "can_apply": false,
    "elapsed_ms": 0.025198000003001653,
    "errors": [
      "Cloth needs at least one generated face before Apply."
    ],
    "operation_id": 13,
    "seq": 59,
    "stage": "apply.request.validation.end",
    "state": {
      "apply": {
        "can_apply": false,
        "can_apply_error": "",
        "editing_existing": false,
        "pending_draw_points": 0,
        "source_flat_scene_id": null,
        "source_mesh_id": null,
        "validation_can_apply": false,
        "validation_error": "",
        "validation_errors": [],
        "validation_present": false,
        "validation_warnings": []
      },
      "document": {
        "curves": 0,
        "layers": 0,
        "patches": 0,
        "points": 0,
        "revision": 0
      },
      "interaction": {
        "hovered_patch_group_ids": [],
        "hovered_patch_id": null,
        "proposal_count": 0,
        "proposal_index": 0,
        "stage": "main"
      },
      "overlay": {
        "accent_color": "#38BDF8",
        "available": true,
        "buttons": [
          {
            "enabled": false,
            "id": "cloth.workflow.action.take_face",
            "label": "Take face",
            "style": "ghost"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.open_closure",
            "label": "Close",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_draw",
            "label": "Draw",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_properties",
            "label": "Properties",
            "style": "secondary"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.apply_output",
            "label": "Apply",
            "style": "secondary"
          }
        ],
        "persistent": true,
        "present": true,
        "title": "Cloth",
        "window_id": "cloth.workflow"
      },
      "selection": {
        "persistent_textile_groups": [],
        "smart_selected_meshes": 0,
        "smart_selected_regions": 0,
        "tracked_textile_groups": []
      },
      "session": {
        "dirty": false,
        "edit_mode": "mesh_trace",
        "phase": "editing",
        "selected_curve_ids": [],
        "selected_patch_ids": [],
        "selected_point_ids": []
      },
      "workspace": {
        "can_apply_close": false,
        "can_close": false,
        "can_take_face": false,
        "close_proposal_count": 0,
        "close_proposal_index": 0,
        "message": "Applying Cloth and regenerating the flat preview…",
        "overlay_mode": "main",
        "phase": "selecting",
        "selected_source_meshes": 0,
        "selected_source_regions": 0,
        "selected_textile_edges": 0,
        "selected_textile_faces": 0
      }
    }
  },
  {
    "at_ms": 3.4751,
    "context": {
      "apply_linked_surface_outputs_callable": true,
      "context_type": "ToolContext",
      "owner_type": "SimpleNamespace",
      "project_scenes_present": true,
      "project_scenes_type": "ProjectScenesFacade"
    },
    "operation_id": 16,
    "output_name": "Cloth",
    "pending_draw_points": 0,
    "seq": 60,
    "stage": "apply.pipeline.start",
    "state": {
      "apply": {
        "can_apply": false,
        "can_apply_error": "",
        "editing_existing": false,
        "pending_draw_points": 0,
        "source_flat_scene_id": null,
        "source_mesh_id": null,
        "validation_can_apply": false,
        "validation_error": "",
        "validation_errors": [],
        "validation_present": false,
        "validation_warnings": []
      },
      "document": {
        "curves": 0,
        "layers": 0,
        "patches": 0,
        "points": 0,
        "revision": 0
      },
      "interaction": {
        "hovered_patch_group_ids": [],
        "hovered_patch_id": null,
        "proposal_count": 0,
        "proposal_index": 0,
        "stage": "main"
      },
      "overlay": {
        "accent_color": "#38BDF8",
        "available": true,
        "buttons": [
          {
            "enabled": false,
            "id": "cloth.workflow.action.take_face",
            "label": "Take face",
            "style": "ghost"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.open_closure",
            "label": "Close",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_draw",
            "label": "Draw",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_properties",
            "label": "Properties",
            "style": "secondary"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.apply_output",
            "label": "Apply",
            "style": "secondary"
          }
        ],
        "persistent": true,
        "present": true,
        "title": "Cloth",
        "window_id": "cloth.workflow"
      },
      "selection": {
        "persistent_textile_groups": [],
        "smart_selected_meshes": 0,
        "smart_selected_regions": 0,
        "tracked_textile_groups": []
      },
      "session": {
        "dirty": false,
        "edit_mode": "mesh_trace",
        "phase": "editing",
        "selected_curve_ids": [],
        "selected_patch_ids": [],
        "selected_point_ids": []
      },
      "workspace": {
        "can_apply_close": false,
        "can_close": false,
        "can_take_face": false,
        "close_proposal_count": 0,
        "close_proposal_index": 0,
        "message": "Applying Cloth and regenerating the flat preview…",
        "overlay_mode": "main",
        "phase": "selecting",
        "selected_source_meshes": 0,
        "selected_source_regions": 0,
        "selected_textile_edges": 0,
        "selected_textile_faces": 0
      }
    },
    "validation_can_apply": false,
    "validation_errors": [
      "Cloth needs at least one generated face before Apply."
    ]
  },
  {
    "at_ms": 3.4981,
    "elapsed_ms": 0.02369499998167157,
    "operation_id": 16,
    "outcome": "blocked",
    "result": {
      "flat_scene_id": null,
      "flat_scene_name": "",
      "folded_object_id": null,
      "message": "Cloth needs at least one textile face before Apply.",
      "stage": "preflight.no_faces",
      "success": false
    },
    "seq": 61,
    "stage": "apply.pipeline.end",
    "state": {
      "apply": {
        "can_apply": false,
        "can_apply_error": "",
        "editing_existing": false,
        "pending_draw_points": 0,
        "source_flat_scene_id": null,
        "source_mesh_id": null,
        "validation_can_apply": false,
        "validation_error": "",
        "validation_errors": [],
        "validation_present": false,
        "validation_warnings": []
      },
      "document": {
        "curves": 0,
        "layers": 0,
        "patches": 0,
        "points": 0,
        "revision": 0
      },
      "interaction": {
        "hovered_patch_group_ids": [],
        "hovered_patch_id": null,
        "proposal_count": 0,
        "proposal_index": 0,
        "stage": "main"
      },
      "overlay": {
        "accent_color": "#38BDF8",
        "available": true,
        "buttons": [
          {
            "enabled": false,
            "id": "cloth.workflow.action.take_face",
            "label": "Take face",
            "style": "ghost"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.open_closure",
            "label": "Close",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_draw",
            "label": "Draw",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_properties",
            "label": "Properties",
            "style": "secondary"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.apply_output",
            "label": "Apply",
            "style": "secondary"
          }
        ],
        "persistent": true,
        "present": true,
        "title": "Cloth",
        "window_id": "cloth.workflow"
      },
      "selection": {
        "persistent_textile_groups": [],
        "smart_selected_meshes": 0,
        "smart_selected_regions": 0,
        "tracked_textile_groups": []
      },
      "session": {
        "dirty": false,
        "edit_mode": "mesh_trace",
        "phase": "editing",
        "selected_curve_ids": [],
        "selected_patch_ids": [],
        "selected_point_ids": []
      },
      "workspace": {
        "can_apply_close": false,
        "can_close": false,
        "can_take_face": false,
        "close_proposal_count": 0,
        "close_proposal_index": 0,
        "message": "Applying Cloth and regenerating the flat preview…",
        "overlay_mode": "main",
        "phase": "selecting",
        "selected_source_meshes": 0,
        "selected_source_regions": 0,
        "selected_textile_edges": 0,
        "selected_textile_faces": 0
      }
    }
  },
  {
    "at_ms": 3.8214,
    "elapsed_ms": 0.6717189999108086,
    "message": "Cloth needs at least one textile face before Apply.",
    "operation_id": 13,
    "outcome": "blocked",
    "pipeline_stage": "preflight.no_faces",
    "seq": 68,
    "stage": "apply.request.end",
    "state": {
      "apply": {
        "can_apply": false,
        "can_apply_error": "",
        "editing_existing": false,
        "pending_draw_points": 0,
        "source_flat_scene_id": null,
        "source_mesh_id": null,
        "validation_can_apply": false,
        "validation_error": "",
        "validation_errors": [],
        "validation_present": false,
        "validation_warnings": []
      },
      "document": {
        "curves": 0,
        "layers": 0,
        "patches": 0,
        "points": 0,
        "revision": 0
      },
      "interaction": {
        "hovered_patch_group_ids": [],
        "hovered_patch_id": null,
        "proposal_count": 0,
        "proposal_index": 0,
        "stage": "main"
      },
      "overlay": {
        "accent_color": "#38BDF8",
        "available": true,
        "buttons": [
          {
            "enabled": false,
            "id": "cloth.workflow.action.take_face",
            "label": "Take face",
            "style": "ghost"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.open_closure",
            "label": "Close",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_draw",
            "label": "Draw",
            "style": "secondary"
          },
          {
            "enabled": true,
            "id": "cloth.workflow.action.open_properties",
            "label": "Properties",
            "style": "secondary"
          },
          {
            "enabled": false,
            "id": "cloth.workflow.action.apply_output",
            "label": "Apply",
            "style": "secondary"
          }
        ],
        "persistent": true,
        "present": true,
        "title": "Cloth",
        "window_id": "cloth.workflow"
      },
      "selection": {
        "persistent_textile_groups": [],
        "smart_selected_meshes": 0,
        "smart_selected_regions": 0,
        "tracked_textile_groups": []
      },
      "session": {
        "dirty": false,
        "edit_mode": "mesh_trace",
        "phase": "editing",
        "selected_curve_ids": [],
        "selected_patch_ids": [],
        "selected_point_ids": []
      },
      "workspace": {
        "can_apply_close": false,
        "can_close": false,
        "can_take_face": false,
        "close_proposal_count": 0,
        "close_proposal_index": 0,
        "message": "Cloth needs at least one textile face before Apply.",
        "overlay_mode": "main",
        "phase": "selecting",
        "selected_source_meshes": 0,
        "selected_source_regions": 0,
        "selected_textile_edges": 0,
        "selected_textile_faces": 0
      }
    }
  }
]
```

## Files to send

- `diagnostics/cloth_workflow_debug.jsonl`
- `diagnostics/cloth_workflow_debug.json`
- `diagnostics/cloth_workflow_debug.md`
- the normal LaserProg application log from the same session
