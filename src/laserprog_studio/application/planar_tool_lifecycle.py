# -*- coding: utf-8 -*-
from __future__ import annotations

from .planar_tool_deps import *  # noqa: F401,F403

class PlanarToolLifecycleLayer:

    @property
    def state(self):
        return getattr(self.owner, "planar_tool_state", None)

    def detect_locked_view_from_camera(self) -> FixedPlanarView:
        w = self.owner
        try:
            forward_fn = getattr(w, "_camera_forward_vector", None)
            if callable(forward_fn):
                forward = forward_fn()
                return nearest_locked_view_from_forward(tuple(float(v) for v in forward))
            cam = getattr(getattr(w, "plotter", None), "camera", None)
            if cam is not None:
                return nearest_locked_view_from_camera(tuple(cam.GetPosition()), tuple(cam.GetFocalPoint()))
        except Exception:
            log_exception("detect_locked_planar_view")
        try:
            mode = str(getattr(w, "_camera_view_mode", "top"))
            return FixedPlanarView(mode) if mode in {v.value for v in FixedPlanarView} else FixedPlanarView.TOP
        except Exception:
            return FixedPlanarView.TOP

    def _camera_snapshot(self):
        try:
            cam = getattr(getattr(self.owner, "plotter", None), "camera", None)
            if cam is None:
                return None
            scale = float(cam.GetParallelScale()) if hasattr(cam, "GetParallelScale") else 0.0
            return (
                tuple(float(v) for v in cam.GetPosition()),
                tuple(float(v) for v in cam.GetFocalPoint()),
                tuple(float(v) for v in cam.GetViewUp()),
                scale,
            )
        except Exception:
            return None

    def _restore_camera_snapshot(self, snapshot) -> bool:
        if snapshot is None:
            return False
        try:
            cam = getattr(getattr(self.owner, "plotter", None), "camera", None)
            if cam is None:
                return False
            pos, focal, up, scale = snapshot
            cam.SetPosition(*pos)
            cam.SetFocalPoint(*focal)
            cam.SetViewUp(*up)
            try:
                cam.SetParallelScale(float(scale))
            except Exception:
                pass
            try:
                self.owner.plotter.render()
            except Exception:
                pass
            return True
        except Exception:
            log_exception("restore_planar_camera_snapshot")
            return False

    def begin_locked_planar_tool(
        self,
        tool_id: str,
        *,
        first_hit_point: tuple[float, float, float] | None = None,
    ) -> LockedPlaneSpec:
        """Lock the camera and return the drawing plane for a planar tool."""

        view = self.detect_locked_view_from_camera()
        plane = plane_from_first_hit(view, first_hit_point)
        previous_mode = str(getattr(self.owner, "_camera_view_mode", "free") or "free")
        previous_snapshot = self._camera_snapshot()
        state = self.state
        if state is not None:
            state.begin(
                tool_id=str(tool_id),
                view=view,
                plane=plane,
                previous_camera_view_mode=previous_mode,
                previous_camera_snapshot=previous_snapshot,
            )
        try:
            setter = getattr(self.owner, "_set_fixed_orthographic_view", None)
            if callable(setter):
                setter(view.value)
            else:
                method = getattr(self.owner, f"view_{view.value}", None)
                if callable(method):
                    method()
        except Exception:
            log_exception("begin_locked_planar_tool_camera")
        self.ui_log(f"[PLANAR] Locked {tool_id} on {view.value} plane depth={plane.depth:.3f}")
        return plane

    def end_locked_planar_tool(self, *, restore_previous_view: bool = False) -> None:
        """Release a locked planar workflow and clear any planar selection payload."""

        state = self.state
        previous_mode = str(getattr(state, "previous_camera_view_mode", "free") or "free")
        previous_snapshot = getattr(state, "previous_camera_snapshot", None)
        active_tool = getattr(state, "active_tool_id", None)
        self.clear_preview_actors(render=False)
        if state is not None:
            state.end()
        if restore_previous_view:
            restored = self._restore_camera_snapshot(previous_snapshot)
            if not restored:
                try:
                    if previous_mode in {v.value for v in FixedPlanarView}:
                        self.owner._set_fixed_orthographic_view(previous_mode)
                    elif callable(getattr(self.owner, "view_iso", None)):
                        self.owner.view_iso()
                except Exception:
                    log_exception("end_locked_planar_tool_restore_view")
        self.ui_log(f"[PLANAR] Released locked plane for {active_tool or 'tool'}")

    def is_planar_view_locked(self) -> bool:
        return bool(getattr(self.state, "active", False))

    def is_active_planar_tool(self) -> bool:
        state = self.state
        return bool(getattr(state, "active", False) and getattr(state, "active_tool_id", None) in {TOOL_PLAN_TRACE, TOOL_VENT_GENERATOR})

    def clamp_world_point_to_active_plane(self, point: tuple[float, float, float]) -> tuple[float, float, float]:
        plane = getattr(self.state, "locked_plane", None)
        if plane is None:
            return tuple(float(v) for v in point)
        return clamp_world_point_to_plane(plane, point)

    def set_payload(self, payload: Any) -> None:
        state = self.state
        if state is not None:
            state.payload = payload

    def _update_preview_button_state(self) -> None:
        try:
            self.owner.update_preview_state()
        except Exception:
            pass

    def clear_planar_tool_state(self, *, restore_previous_view: bool = False) -> None:
        payload = getattr(self.state, "payload", None)
        try:
            if hasattr(payload, "clear_selection"):
                payload.clear_selection()
        except Exception:
            pass
        self.end_locked_planar_tool(restore_previous_view=restore_previous_view)
        self.update_planar_tool_report()

    def handle_lifecycle_hook(self, hook_name: str, *, render: bool | None = None) -> bool:

        if hook_name == "_initialize_plan_trace_tool":
            self.initialize_plan_trace_tool()
            return True
        if hook_name == "_initialize_vent_generator_tool":
            self.initialize_vent_generator_tool()
            return True
        if hook_name == "_clear_planar_tool_state":
            self.clear_planar_tool_state(restore_previous_view=True)
            return True
        return False

# Transitional import alias; the concrete implementation is a Layer, not a mixin class.
PlanarToolLifecycleLayer = PlanarToolLifecycleLayer

