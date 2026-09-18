# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class InteractionGizmoRefreshLayer:

    def _mark_camera_zoom_interaction(self, *, duration_s: float = 0.22) -> None:
        """Expose a short zoom burst to the central render scheduler."""

        try:
            import time

            self._camera_zoom_burst_until = max(
                float(getattr(self, "_camera_zoom_burst_until", 0.0) or 0.0),
                time.monotonic() + max(float(duration_s), 0.05),
            )
        except Exception:
            pass

    def _resize_transform_gizmo_for_camera(self, *, render: bool = False) -> bool:
        """Resize the lightweight Transform gizmo without rebuilding actors."""

        try:
            if getattr(self, "_drag_axis", None) is not None:
                # A translate drag already moves the persistent assembly. Resizing
                # it concurrently would apply the live offset twice.
                return True
            if (
                self.active_index is None
                or not self._transform_tools_available()
                or self.transform_mode not in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}
                or not bool(getattr(self, "_native_transform_gizmo_active", False))
            ):
                return False
            snapshot = getattr(self, "_native_transform_gizmo_snapshot", None)
            if snapshot is None:
                return False
            center = tuple(float(v) for v in snapshot.center)
            length = self._gizmo_length_at(center, self.current_meshes())
            from laserprog_studio.application.transform_gizmo_api import resize_native_transform_gizmo_live

            return bool(resize_native_transform_gizmo_live(self, length=length, render=bool(render)))
        except Exception:
            log_exception("resize_transform_gizmo_for_camera")
            return False

    def _active_creator_context_for_camera_ui(self):
        try:
            active = getattr(self, "active_tool", getattr(self, "TOOL_NONE", "none"))
            if active == getattr(self, "TOOL_NONE", "none"):
                return None, None
            from ..tooling.registry import get_studio_tool

            tool = get_studio_tool(active)
            if tool is None or not callable(getattr(tool, "tool_context", None)):
                return None, None
            ctx = tool.tool_context(self.context)
            has_legacy_gizmos = bool(ctx.gizmos.handles(owner_tool=active))
            has_legacy_previews = bool(ctx.preview.items(owner_tool=active))
            # Projected Drawing 2D actors reproject themselves in the renderer
            # StartEvent.  Treating them as legacy camera-sized Creator UI starts
            # an unnecessary second zoom render loop and produces visible jitter.
            has_legacy_actors = any(
                not bool((getattr(actor, "metadata", {}) or {}).get("projected_drawing_id"))
                for actor in ctx.selection.actors(owner_tool=active)
            )
            has_ui = bool(has_legacy_gizmos or has_legacy_previews or has_legacy_actors)
            return (active, ctx) if has_ui else (None, None)
        except Exception:
            return None, None

    def _refresh_camera_scaled_overlays(
        self,
        *,
        render: bool = True,
        fast_transform_resize: bool = False,
    ) -> bool:
        """Refresh overlays whose world size depends on the current camera.

        Zoom events resize the lightweight Transform geometry in place. Camera
        orientation changes may still request a full rebuild for adaptive frames.
        """
        refreshed = False
        try:
            if (
                self.active_index is not None
                and self._transform_tools_available()
                and self.transform_mode in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}
            ):
                if fast_transform_resize:
                    if not self._resize_transform_gizmo_for_camera(render=False):
                        self.update_gizmo(render=False)
                else:
                    # Camera orientation changes (orbit/view change) must rebuild
                    # the adaptive Scale frame. Zoom-only paths opt into the
                    # in-place resize above.
                    self.update_gizmo(render=False)
                refreshed = True
        except Exception:
            log_exception("refresh_camera_scaled_transform_gizmo")
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) == self.TOOL_MOD_SPLIT:
                self._sync_modifier_plane_actor(render=False)
                refreshed = True
        except Exception:
            log_exception("refresh_camera_scaled_split_plane")
        try:
            if (
                getattr(self, "active_tool", self.TOOL_NONE) == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection")
                and self.has_preview()
            ):
                self.update_texture_rotation_gizmo(render=False)
                refreshed = True
        except Exception:
            log_exception("refresh_camera_scaled_texture_rotation_gizmo")
        try:
            diag_controller = getattr(self, "tool_core_diag_controller", None)
            diag_active = getattr(self, "active_tool", getattr(self, "TOOL_NONE", "none")) == getattr(self, "TOOL_CORE_DIAGNOSTIC", "tool_core_diagnostic")
            if diag_active and diag_controller is not None:
                if callable(getattr(diag_controller, "refresh_camera_size_after_move", None)):
                    diag_controller.refresh_camera_size_after_move()
                    refreshed = True
        except Exception:
            log_exception("refresh_camera_scaled_tool_core_diag")
        try:
            active_creator, creator_ctx = self._active_creator_context_for_camera_ui()
            if active_creator is not None and creator_ctx is not None:
                from ..tool_api.gizmos import refresh_creator_ui_camera

                if refresh_creator_ui_camera(creator_ctx, owner_tool=active_creator, render=False):
                    refreshed = True
        except Exception:
            log_exception("refresh_camera_scaled_creator_ui")
        try:
            if refreshed and render:
                self.plotter.render()
        except Exception:
            log_exception("refresh_camera_scaled_overlays_render")
        return refreshed

    def _schedule_gizmo_wheel_refresh(self) -> None:
        """Guarantee one exact refresh after the last event of a zoom burst."""

        try:
            serial = int(getattr(self, "_gizmo_wheel_refresh_serial", 0)) + 1
            self._gizmo_wheel_refresh_serial = serial
            self._gizmo_wheel_refresh_pending = True
            QTimer.singleShot(140, lambda token=serial: self._refresh_gizmo_after_wheel(token))
        except Exception:
            self._gizmo_wheel_refresh_pending = False

    def _refresh_gizmo_after_wheel(self, serial: int | None = None) -> None:
        try:
            if serial is not None and int(serial) != int(getattr(self, "_gizmo_wheel_refresh_serial", serial)):
                return
            self._gizmo_wheel_refresh_pending = False
            if self._drag_axis is not None:
                return
            self._refresh_camera_scaled_overlays(render=True)
        except Exception:
            self._gizmo_wheel_refresh_pending = False
            log_exception("refresh_gizmo_after_wheel")

    def _schedule_zoom_live_pulse(self, *, after_camera_event: bool = True) -> None:
        """Keep camera-sized overlays synchronized throughout a wheel burst.

        The Qt wheel filter runs before VTK has necessarily applied the camera
        zoom.  A single ``singleShot(0)`` can therefore observe the old camera
        and leave the gizmo unchanged until the final burst refresh.  The pulse
        samples the camera again at the interactive cadence for the short zoom
        window, while the normal live-refresh coalescer prevents excess renders.
        """

        try:
            serial = int(getattr(self, "_gizmo_zoom_live_serial", 0)) + 1
            self._gizmo_zoom_live_serial = serial
            if bool(getattr(self, "_gizmo_zoom_live_pulse_pending", False)):
                return
            self._gizmo_zoom_live_pulse_pending = True
            delay_ms = 0 if after_camera_event else 1
            QTimer.singleShot(delay_ms, lambda token=serial: self._run_zoom_live_pulse(token))
        except Exception:
            self._gizmo_zoom_live_pulse_pending = False
            self._request_live_gizmo_refresh(render=True, fast_transform_resize=True)

    def _run_zoom_live_pulse(self, serial: int | None = None) -> None:
        try:
            # A newer wheel event extends the same pulse.  Do not discard this
            # callback merely because its token is older: it is the sole active
            # runner and reads the latest burst deadline below.
            self._gizmo_zoom_live_pulse_pending = False
            self._request_live_gizmo_refresh(render=True, fast_transform_resize=True)

            import time

            if time.monotonic() >= float(getattr(self, "_camera_zoom_burst_until", 0.0) or 0.0):
                return
            self._gizmo_zoom_live_pulse_pending = True
            interval_ms = max(int(round(float(getattr(self, "_gizmo_live_refresh_interval_ms", 16.0)))), 1)
            latest = int(getattr(self, "_gizmo_zoom_live_serial", serial or 0))
            QTimer.singleShot(interval_ms, lambda token=latest: self._run_zoom_live_pulse(token))
        except Exception:
            self._gizmo_zoom_live_pulse_pending = False
            log_exception("run_zoom_live_pulse")

    def _request_zoom_gizmo_refresh(self, *, after_camera_event: bool = True) -> None:
        """Refresh camera-sized overlays without competing with VTK rendering.

        The Transform 2D backend projects from the current camera in the
        renderer ``StartEvent``.  Every native wheel render therefore already
        updates it at the correct instant.  Starting a second 16 ms render loop
        here creates beat-frequency jitter and asymmetric zoom/dezoom lag.
        Keep the pulse only when another camera-sized overlay actually needs it.
        """

        self._mark_camera_zoom_interaction()
        self._schedule_gizmo_wheel_refresh()
        needs_auxiliary_pulse = False
        try:
            active_tool = getattr(self, "active_tool", self.TOOL_NONE)
            needs_auxiliary_pulse = bool(
                active_tool in {self.TOOL_MOD_SPLIT, getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down")}
                or (
                    active_tool == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection")
                    and self.has_preview()
                )
                or self._active_creator_context_for_camera_ui()[0] is not None
            )
            renderer = getattr(self, "_transform_gizmo_renderer", None)
            transform_is_2d = bool(renderer is not None and getattr(renderer, "screen_space_overlay", False))
            if not transform_is_2d:
                needs_auxiliary_pulse = True
        except Exception:
            needs_auxiliary_pulse = True
        if needs_auxiliary_pulse:
            self._schedule_zoom_live_pulse(after_camera_event=after_camera_event)

    def _request_live_gizmo_refresh(
        self,
        *,
        render: bool = True,
        fast_transform_resize: bool = False,
    ) -> None:
        """Schedule a throttled gizmo rebuild during active user interactions.

        This replaces the old heavy camera observer approach. We refresh only
        while the user is actually orbiting/panning/transforming, and we coalesce
        bursts so Qt/VTK does not rebuild overlay actors on every raw event.
        """
        try:
            if fast_transform_resize:
                self._gizmo_live_refresh_fast_transform = True
            if self._gizmo_live_refresh_pending:
                return
            has_transform_gizmo = (
                self.active_index is not None
                and self._transform_tools_available()
                and self.transform_mode in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}
            )
            has_split_handle = getattr(self, "active_tool", self.TOOL_NONE) in {self.TOOL_MOD_SPLIT, getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down")}
            has_texture_rotation_gizmo = (
                getattr(self, "active_tool", self.TOOL_NONE) == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection")
                and self.has_preview()
            )
            has_tool_core_diag_live = False
            try:
                diag_controller = getattr(self, "tool_core_diag_controller", None)
                diag_active = getattr(self, "active_tool", getattr(self, "TOOL_NONE", "none")) == getattr(self, "TOOL_CORE_DIAGNOSTIC", "tool_core_diagnostic")
                has_tool_core_diag_live = bool(
                    diag_active
                    and diag_controller is not None
                    and getattr(diag_controller, "camera_size_update_mode", "end") == "live"
                )
            except Exception:
                has_tool_core_diag_live = False
            if not (has_transform_gizmo or has_split_handle or has_texture_rotation_gizmo or has_tool_core_diag_live):
                self._gizmo_live_refresh_fast_transform = False
                return
            import time
            now = time.monotonic()
            interval_s = max(float(getattr(self, "_gizmo_live_refresh_interval_ms", 24.0)), 1.0) / 1000.0
            elapsed = now - float(getattr(self, "_last_gizmo_live_refresh_time", 0.0))
            delay_ms = 0 if elapsed >= interval_s else int(max((interval_s - elapsed) * 1000.0, 1.0))
            self._gizmo_live_refresh_pending = True
            QTimer.singleShot(delay_ms, lambda r=bool(render): self._refresh_live_gizmo(r))
        except Exception:
            self._gizmo_live_refresh_pending = False

    def _refresh_live_gizmo(self, render: bool = True) -> None:
        try:
            self._gizmo_live_refresh_pending = False
            import time
            self._last_gizmo_live_refresh_time = time.monotonic()
            diag_controller = getattr(self, "tool_core_diag_controller", None)
            diag_active = getattr(self, "active_tool", getattr(self, "TOOL_NONE", "none")) == getattr(self, "TOOL_CORE_DIAGNOSTIC", "tool_core_diagnostic")
            fast_transform_resize = bool(getattr(self, "_gizmo_live_refresh_fast_transform", False))
            self._gizmo_live_refresh_fast_transform = False
            if diag_active and diag_controller is not None and getattr(diag_controller, "camera_size_update_mode", "end") == "live":
                diag_controller.refresh_camera_size_live_if_enabled()
            else:
                self._refresh_camera_scaled_overlays(
                    render=render,
                    fast_transform_resize=fast_transform_resize,
                )
        except Exception:
            self._gizmo_live_refresh_pending = False
            self._gizmo_live_refresh_fast_transform = False
            log_exception("refresh_live_gizmo")

    def _refresh_gizmo_during_drag_if_due(self) -> bool:
        """Refresh the overlay immediately during a transform drag when due.

        Returns True when it already rendered the scene. Callers can skip their
        extra render in that case.
        """
        try:
            if self.active_index is None or not self._transform_tools_available():
                return False
            if self.transform_mode not in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}:
                return False
            import time
            now = time.monotonic()
            interval_s = max(float(getattr(self, "_gizmo_live_refresh_interval_ms", 24.0)), 1.0) / 1000.0
            if (now - float(getattr(self, "_last_gizmo_live_refresh_time", 0.0))) < interval_s:
                return False
            self._last_gizmo_live_refresh_time = now
            self.update_gizmo(render=False)
            self.plotter.render()
            return True
        except Exception:
            log_exception("refresh_gizmo_during_drag_if_due")
            return False

