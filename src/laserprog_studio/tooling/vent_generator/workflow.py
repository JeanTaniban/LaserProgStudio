# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from laserprog_studio.planar_tools import PlanarEditMode, VentPathDraft, plane_to_world, world_to_plane


@dataclass(frozen=True, slots=True)
class VentRouteResult:
    """Result returned by the Vent Generator route state machine."""

    handled: bool
    changed: bool = False
    message: str = ""
    selected_index: int | None = None


class VentRouteMachine:
    """Small state machine for user route edits.

    It is deliberately independent from Qt and from the planar controller.  The
    Qt viewport may still provide richer picking/snap, but the tool itself now
    owns the canonical ADD/MOD/SUPP/RST behavior and can be tested headlessly.
    """

    def __init__(self, payload: VentPathDraft, *, tolerance: float = 3.0) -> None:
        self.payload = payload
        self.tolerance = max(float(tolerance), 1e-9)

    @staticmethod
    def normalize_mode(value: Any) -> PlanarEditMode:
        if isinstance(value, PlanarEditMode):
            return value
        raw = str(getattr(value, "value", value or PlanarEditMode.ADD.value)).strip().upper()
        aliases = {
            "DELETE": PlanarEditMode.SUPP,
            "DEL": PlanarEditMode.SUPP,
            "REMOVE": PlanarEditMode.SUPP,
            "RESET": PlanarEditMode.RST,
            "CLEAR": PlanarEditMode.RST,
            "MOVE": PlanarEditMode.MOD,
            "EDIT": PlanarEditMode.MOD,
            "DRAW": PlanarEditMode.ADD,
        }
        if raw in aliases:
            return aliases[raw]
        try:
            return PlanarEditMode(raw)
        except Exception:
            return PlanarEditMode.ADD

    @property
    def mode(self) -> PlanarEditMode:
        mode = getattr(self.payload, "mode", PlanarEditMode.ADD)
        return mode if isinstance(mode, PlanarEditMode) else self.normalize_mode(mode)

    def set_mode(self, value: Any) -> VentRouteResult:
        mode = self.normalize_mode(value)
        if mode is PlanarEditMode.RST:
            self.payload.reset()
            self.payload.set_mode(PlanarEditMode.ADD)
            return VentRouteResult(True, True, "Route reset.")
        self.payload.set_mode(mode)
        return VentRouteResult(True, True, f"Mode: {mode.value}", selected_index=getattr(self.payload, "selected_index", None))

    def add_point(self, point: tuple[float, float]) -> VentRouteResult:
        candidate = (float(point[0]), float(point[1]))
        check = self.payload.clamp_waypoint_candidate(candidate)
        if not check.valid:
            return VentRouteResult(True, False, check.message or "Point rejected.", selected_index=getattr(self.payload, "selected_index", None))
        index = self.payload.add_waypoint_plane(check.point, min_spacing=max(self.tolerance * 0.05, 1e-6))
        return VentRouteResult(True, True, f"Waypoint {index + 1} added.", selected_index=index)

    def select_point(self, point: tuple[float, float]) -> VentRouteResult:
        selected = self.payload.select_nearest_plane((float(point[0]), float(point[1])), max_distance=self.tolerance)
        if selected is None:
            return VentRouteResult(True, False, "No waypoint near the cursor.")
        return VentRouteResult(True, True, f"Waypoint {selected + 1} selected.", selected_index=selected)

    def move_selected(self, point: tuple[float, float]) -> VentRouteResult:
        selected = getattr(self.payload, "selected_index", None)
        if selected is None:
            return VentRouteResult(True, False, "Select a waypoint before moving it.")
        anchor = None
        try:
            if 0 <= int(selected) < len(self.payload.waypoints):
                anchor = self.payload.waypoints[int(selected)]
        except Exception:
            anchor = None
        check = self.payload.clamp_waypoint_candidate((float(point[0]), float(point[1])), index=selected, anchor=anchor)
        if not check.valid:
            return VentRouteResult(True, False, check.message or "Move rejected.", selected_index=selected)
        self.payload.update_selected_plane(check.point)
        return VentRouteResult(True, True, f"Waypoint {int(selected) + 1} moved.", selected_index=int(selected))

    def delete_point(self, point: tuple[float, float]) -> VentRouteResult:
        deleted = self.payload.delete_nearest_plane((float(point[0]), float(point[1])), max_distance=self.tolerance)
        if deleted is None:
            return VentRouteResult(True, False, "No waypoint near the cursor.")
        return VentRouteResult(True, True, f"Waypoint {deleted + 1} deleted.")

    def click_plane(self, point: tuple[float, float]) -> VentRouteResult:
        mode = self.mode
        if mode is PlanarEditMode.ADD:
            return self.add_point(point)
        if mode is PlanarEditMode.MOD:
            return self.select_point(point)
        if mode is PlanarEditMode.SUPP:
            return self.delete_point(point)
        if mode is PlanarEditMode.RST:
            return self.set_mode(PlanarEditMode.RST)
        return VentRouteResult(False)

    def world_to_plane(self, point: tuple[float, float, float]) -> tuple[float, float]:
        return world_to_plane(self.payload.plane, (float(point[0]), float(point[1]), float(point[2])))

    def plane_to_world(self, point: tuple[float, float]) -> tuple[float, float, float]:
        return plane_to_world(self.payload.plane, float(point[0]), float(point[1]))


def vent_route_summary(payload: VentPathDraft | None) -> str:
    if not isinstance(payload, VentPathDraft):
        return "No route active."
    count = len(payload.waypoints)
    if count == 0:
        return "0 waypoint — click Add to start the route."
    if count == 1:
        x, y = payload.waypoints[0]
        return f"1 waypoint at {x:.1f}, {y:.1f} mm — add an outlet point."
    try:
        metrics = payload.metrics()
        ready = payload.validation_result().ok
        suffix = "ready" if ready else "needs adjustment"
        return f"{count} waypoints · {metrics.centerline_length:.1f} mm centerline · {suffix}."
    except Exception:
        return f"{count} waypoints."


def vent_selected_point_text(payload: VentPathDraft | None) -> str:
    if not isinstance(payload, VentPathDraft):
        return "No selected waypoint."
    selected = getattr(payload, "selected_index", None)
    if selected is None:
        return "No selected waypoint."
    try:
        point = payload.waypoints[int(selected)]
    except Exception:
        return "No selected waypoint."
    return f"Waypoint {int(selected) + 1}: {float(point[0]):.1f}, {float(point[1]):.1f} mm"


__all__ = ["VentRouteMachine", "VentRouteResult", "vent_route_summary", "vent_selected_point_text"]
