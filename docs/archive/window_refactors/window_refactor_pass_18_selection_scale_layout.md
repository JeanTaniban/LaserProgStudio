# Window Refactor Pass 18 - Selection, Scale Lock, and Layout Performance

## Goals

This pass keeps the professional architecture direction while adding user-facing transform and selection features:

- scale ratio lock shared by the right inspector, compact transform overlay, and scale gizmo drags;
- Ctrl+A select-all for mesh parts;
- rubber-band selection without breaking the existing VTK orbit interaction;
- coalesced Light UI/tool layout transitions to avoid lag after long sessions.

## Scale ratio lock

The state is owned by `TransformState.scale_ratio_locked` and bridged through `StateBridgeMixin.scale_ratio_locked` for legacy controllers.

The UI exposes the same state in two places:

- right inspector: `scale_ratio_lock_check`;
- compact transform overlay: `light_scale_ratio_lock`.

`TransformInspectorMixin._propagate_locked_scale_change_from_widgets()` keeps size fields proportional. `TransformDragMixin` applies the same ratio lock to scale-gizmo drags by uniformly scaling along all local axes when the lock is enabled.

## Group selection

`SceneStateMixin.set_selection_indices()` batches selection changes in one pass. It is used by:

- `select_all_parts()` for Ctrl+A;
- `SelectionBoxMixin` for rectangle selection.

Rectangle selection uses a `QRubberBand` and projected actor bounds. In free 3D camera mode it starts with Shift+Left drag so normal left-drag orbit is preserved. In fixed orthographic views, left-drag can start the selection rectangle directly.

## Layout performance

Programmatic Light UI/tool layout transitions now go through `_set_main_splitter_sizes_coalesced()`. It temporarily blocks splitter signals and schedules one overlay refresh instead of running the heavy inspector/overlay synchronization repeatedly during `setSizes()`.

This complements the previous splitter resize debounce and targets lag that appears after many tool open/close or Light UI transitions.
