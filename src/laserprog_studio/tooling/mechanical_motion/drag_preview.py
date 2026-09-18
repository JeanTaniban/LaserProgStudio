# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .live_motion import _compose, _copy_vtk_matrix, _motion_affine, _vtk_matrix
from .models import GearSpec, Point3


@dataclass(slots=True)
class _GearActorBaseline:
    gear_id: str
    shaft_id: str
    actor: Any
    actor_index: int
    user_matrix: Any | None
    visible: bool
    center: Point3
    phase_deg: float


class MechanicalGearDragPreview:
    """Move one standalone gear actor without rebuilding document geometry.

    The neutral document preview remains untouched. During drag, the existing
    actor receives one affine matrix. If the host actor cannot accept matrices,
    it is hidden and the projected outline rendered by MechanicalRenderer is the
    visual fallback. Release restores the actor before the one real mesh rebuild.
    """

    def __init__(self) -> None:
        self._baseline: _GearActorBaseline | None = None
        self._generation: int | None = None
        self._matrix_failed = False

    @property
    def active_gear_id(self) -> str | None:
        return self._baseline.gear_id if self._baseline is not None else None

    @property
    def actor_visible_during_drag(self) -> bool:
        baseline = self._baseline
        return bool(baseline is not None and not self._matrix_failed)

    def _scene_is_current(self, ctx: Any) -> bool:
        baseline = self._baseline
        owner = getattr(ctx, "owner", None)
        actors = getattr(owner, "actors_by_index", None) if owner is not None else None
        if baseline is None or not isinstance(actors, dict):
            return False
        generation = int(getattr(owner, "_scene_rebuild_generation", 0) or 0)
        return generation == self._generation and actors.get(baseline.actor_index) is baseline.actor

    @staticmethod
    def _visibility(actor: Any) -> bool:
        getter = getattr(actor, "GetVisibility", None)
        if callable(getter):
            try:
                return bool(getter())
            except Exception:
                pass
        return bool(getattr(actor, "visibility", True))

    @staticmethod
    def _set_visibility(actor: Any, visible: bool) -> None:
        setter = getattr(actor, "SetVisibility", None)
        if callable(setter):
            try:
                setter(bool(visible))
                return
            except Exception:
                pass
        try:
            actor.visibility = bool(visible)
        except Exception:
            pass

    def begin(
        self,
        ctx: Any,
        gear: GearSpec,
        *,
        baseline_center: Point3 | None = None,
        baseline_phase_deg: float | None = None,
    ) -> bool:
        if self._scene_is_current(ctx) and self.active_gear_id == gear.id:
            return True
        self.end(ctx, render=False)
        owner = getattr(ctx, "owner", None)
        actors = getattr(owner, "actors_by_index", None) if owner is not None else None
        if not isinstance(actors, dict):
            return False
        try:
            objects = tuple(ctx.document.objects(include_preview=True))
        except Exception:
            objects = ()
        shaft_id = str(gear.shaft_id or gear.id)
        for raw_index, actor in actors.items():
            index = int(raw_index)
            if actor is None or not (0 <= index < len(objects)):
                continue
            mesh = getattr(objects[index], "mesh", None)
            metadata = getattr(mesh, "metadata", None)
            metadata = metadata if isinstance(metadata, dict) else {}
            mesh_shaft = str(metadata.get("mechanical_shaft_id") or "")
            mesh_gear = str(metadata.get("mechanical_gear_id") or "")
            mesh_gears = tuple(str(value) for value in (metadata.get("mechanical_gear_ids") or ()))
            if mesh_shaft != shaft_id:
                continue
            if mesh_gear != gear.id and mesh_gears != (gear.id,):
                continue
            getter = getattr(actor, "GetUserMatrix", None)
            try:
                matrix = getter() if callable(getter) else None
            except Exception:
                matrix = None
            self._baseline = _GearActorBaseline(
                gear_id=gear.id,
                shaft_id=shaft_id,
                actor=actor,
                actor_index=index,
                user_matrix=_copy_vtk_matrix(matrix),
                visible=self._visibility(actor),
                center=tuple(baseline_center or gear.center),
                phase_deg=float(gear.phase_deg if baseline_phase_deg is None else baseline_phase_deg),
            )
            self._generation = int(getattr(owner, "_scene_rebuild_generation", 0) or 0)
            self._matrix_failed = not callable(getattr(actor, "SetUserMatrix", None))
            if self._matrix_failed:
                self._set_visibility(actor, False)
            return True
        return False

    def update(
        self,
        ctx: Any,
        gear: GearSpec,
        *,
        axis: Point3,
        baseline_center: Point3 | None = None,
        baseline_phase_deg: float | None = None,
        render: bool = False,
    ) -> bool:
        if (not self._scene_is_current(ctx) or self.active_gear_id != gear.id) and not self.begin(
            ctx,
            gear,
            baseline_center=baseline_center,
            baseline_phase_deg=baseline_phase_deg,
        ):
            return False
        baseline = self._baseline
        if baseline is None:
            return False
        if not self._matrix_failed:
            translation = tuple(float(gear.center[index]) - float(baseline.center[index]) for index in range(3))
            angle = float(gear.phase_deg) - float(baseline.phase_deg)
            delta = _vtk_matrix(_motion_affine(baseline.center, tuple(axis), angle, translation))
            if delta is None:
                self._matrix_failed = True
                self._set_visibility(baseline.actor, False)
            else:
                try:
                    baseline.actor.SetUserMatrix(_compose(delta, baseline.user_matrix))
                    self._set_visibility(baseline.actor, baseline.visible)
                except Exception:
                    self._matrix_failed = True
                    self._set_visibility(baseline.actor, False)
        if render:
            self._render(ctx)
        return True

    def end(self, ctx: Any, *, render: bool = False) -> None:
        baseline = self._baseline
        if baseline is not None and self._scene_is_current(ctx):
            try:
                setter = getattr(baseline.actor, "SetUserMatrix", None)
                if callable(setter):
                    setter(baseline.user_matrix)
            except Exception:
                pass
            self._set_visibility(baseline.actor, baseline.visible)
        self._baseline = None
        self._generation = None
        self._matrix_failed = False
        if render:
            self._render(ctx)

    @staticmethod
    def _render(ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        plotter = getattr(owner, "plotter", None) if owner is not None else None
        callback = getattr(plotter, "render", None)
        if callable(callback):
            try:
                callback()
            except Exception:
                pass


__all__ = ["MechanicalGearDragPreview"]
