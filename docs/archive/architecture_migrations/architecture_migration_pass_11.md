# Architecture Migration Pass 11 — Texture gizmo service split

## Goal

Pass 10 moved TEX rotation/move behaviour out of the legacy `TextureProjectionToolMixin`, but the new `TextureGizmoController` was still too large. It carried picking, screen math, live UV updates, Qt/VTK event routing, gizmo rendering and drag orchestration in one file.

Pass 11 keeps the public controller API stable and splits the implementation into small services.

## New split

```text
application/texture_gizmo_controller.py
    Thin facade owned by runtime_state. Keeps the legacy method names.

application/texture_gizmo_target_service.py
    Active target selection, screen projection, ring picking, movement basis.

application/texture_gizmo_live_update_service.py
    Fast UV/TCoords updates and projection metadata synchronization.

application/texture_gizmo_event_service.py
    Global Qt event filter installation, VTK observers and drag polling timer.

application/texture_gizmo_render_service.py
    Ring / center-handle mesh creation and overlay actor refresh.

application/texture_gizmo_drag_service.py
    Start/update/finish workflows for rotation and center-move drags.

application/texture_gizmo_math.py
    Pure vector and screen-distance helpers.

application/texture_gizmo_qt.py
    Lazy Qt imports used by the event service.
```

## Behaviour compatibility

`TextureProjectionToolMixin` still calls `self._texture_gizmo_controller().<legacy_method>()`.
`TextureGizmoController` still exposes the same legacy methods, but now delegates to the specialized services.

The services remain `OwnerDelegatingController` adapters during the migration, so they still read/write legacy window attributes. This is intentional: it avoids changing runtime behaviour while making ownership clearer.

## Important Qt detail

The event filter and QTimer now use the real Qt owner window as QObject parent/filter target. The service objects are not QObjects.

```text
app.installEventFilter(self.owner)
QTimer(self.owner)
```

This preserves the previous event routing while allowing the implementation to live outside `MainWindow`.

## Result

Before Pass 11:

```text
application/texture_gizmo_controller.py  ~1485 lines
```

After Pass 11:

```text
application/texture_gizmo_controller.py             ~176 lines
application/texture_gizmo_target_service.py         ~348 lines
application/texture_gizmo_live_update_service.py    ~280 lines
application/texture_gizmo_event_service.py          ~346 lines
application/texture_gizmo_render_service.py          ~73 lines
application/texture_gizmo_drag_service.py           ~429 lines
```

The only large file remaining is now the geometry-level texture projection implementation.
