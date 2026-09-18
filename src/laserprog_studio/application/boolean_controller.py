# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable
import time
try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None

from ..app_context import AppContext
from ..mesh_ops import mesh_bounds
from ..studio_log import log_exception
from .action_controller import WindowController
from .background_tasks import task_manager_for


def _qmessagebox() -> Any:
    from PySide6.QtWidgets import QMessageBox

    return QMessageBox


@dataclass(slots=True)
class BooleanJobResult:
    meshes: list[Any]
    selected_indices: list[int]
    active_index: int | None
    reason: str
    semantic_operation_type: str
    failures: list[str]
    user_warning_title: str | None = None
    user_warning_text: str | None = None
    no_change_title: str | None = None
    no_change_text: str | None = None


class BooleanController(WindowController):
    """Boolean mesh commands as an explicit application controller.

    Heavy boolean operations run in a background worker.  The worker receives
    deep-copied meshes and never touches Qt/VTK; scene mutation happens only in
    the main-thread success callback.
    """

    @classmethod
    def create(cls, context: AppContext) -> "BooleanController":
        return cls(context)

    def active_boolean_cutter_index(self) -> int | None:
        w = self.owner
        indices = w._selected_transform_indices()
        if not indices:
            return None
        if w.active_index in indices:
            return int(w.active_index)
        return int(indices[-1])

    def blocked_message(self) -> bool:
        w = self.owner
        if bool(getattr(w, "_boolean_job_active", False)):
            _qmessagebox().information(
                w,
                "Boolean operation running",
                "A boolean operation is already running. Wait for it to finish before starting another one.",
            )
            return True
        if w.active_tool != w.TOOL_NONE or w.has_preview():
            _qmessagebox().information(
                w,
                "Boolean tools unavailable",
                "Close or apply/cancel the active tool before running a boolean operation.",
            )
            return True
        return False

    def _set_boolean_busy(self, busy: bool, message: str | None = None) -> None:
        w = self.owner
        try:
            setattr(w, "_boolean_job_active", bool(busy))
            if message:
                self.status_message(message, 0 if busy else 2400)
            elif not busy:
                try:
                    w.statusBar().clearMessage()
                except Exception:
                    pass
            sync = getattr(w, "_sync_boolean_buttons", None)
            if callable(sync):
                sync()
        except Exception:
            pass

    def _run_boolean_job(self, *, key: str, description: str, worker: Callable[[], BooleanJobResult]) -> None:
        w = self.owner
        manager = task_manager_for(w)
        if _APP_AUDIT is not None:
            _APP_AUDIT.increment(f"boolean.{key}.requested")
            _APP_AUDIT.increment("boolean.requested.total")
        self._set_boolean_busy(True, f"{description}…")
        w.ui_log(f"[BOOLEAN][WORKER] {description} started")

        def _measured_worker() -> BooleanJobResult:
            start = time.perf_counter()
            try:
                return worker()
            finally:
                if _APP_AUDIT is not None:
                    _APP_AUDIT.record_timing(f"boolean.{key}.worker", (time.perf_counter() - start) * 1000.0, details={"description": description})

        def _success(result: BooleanJobResult) -> None:
            callback_start = time.perf_counter()
            try:
                if _APP_AUDIT is not None:
                    _APP_AUDIT.set_value(f"boolean.{key}.result_meshes", len(result.meshes))
                    _APP_AUDIT.set_value(f"boolean.{key}.failures", len(result.failures))
                if result.no_change_title:
                    _qmessagebox().information(w, result.no_change_title, result.no_change_text or "No change was made.")
                    w.ui_log(f"[BOOLEAN] {description}: no change")
                    return
                w.selected_indices = list(result.selected_indices)
                w.active_index = result.active_index
                w.push_meshes(result.meshes, result.reason, semantic_operation_type=result.semantic_operation_type)
                if result.failures and result.user_warning_title:
                    _qmessagebox().warning(w, result.user_warning_title, result.user_warning_text or "Some targets failed.")
                    for line in result.failures[:10]:
                        w.ui_log(f"[BOOLEAN] partial failure: {line}")
                w.ui_log(f"[BOOLEAN][WORKER] {description} finished")
            except Exception as exc:
                log_exception(f"boolean_worker_apply:{key}")
                _qmessagebox().critical(w, f"{description} failed", str(exc))
            finally:
                if _APP_AUDIT is not None:
                    _APP_AUDIT.record_timing(f"boolean.{key}.success_callback", (time.perf_counter() - callback_start) * 1000.0, details={"description": description})

        def _error(exc: BaseException) -> None:
            log_exception(f"boolean_worker:{key}")
            detail = str(exc) or type(exc).__name__
            lower = detail.lower()
            if any(token in lower for token in ("manifold", "boundary_edges", "nonmanifold", "indexed_closed")):
                detail += "\n\nThe diagnostic above identifies which input is geometrically invalid."
            _qmessagebox().critical(
                w,
                f"{description} failed",
                detail,
            )

        def _finished() -> None:
            self._set_boolean_busy(False)

        manager.run(
            f"boolean.{key}",
            _measured_worker,
            on_success=_success,
            on_error=_error,
            on_finished=_finished,
            description=description,
        )


    def subtract_margin_mm(self) -> float:
        """Return the user clearance for Boolean Subtract in millimetres.

        Positive values make holes larger; negative values make the cutter
        smaller before subtraction.  The value is intentionally read before the
        worker starts so background jobs remain detached from Qt/window state.
        """

        try:
            prefs = getattr(self.owner, "project_preferences", None)
            if prefs is None:
                from ..services.project_preferences import load_project_preferences

                prefs = load_project_preferences()
            laser = getattr(prefs, "laser", None)
            return float(getattr(laser, "boolean_subtract_margin_mm", 0.0))
        except Exception:
            return 0.0

    def touching_mesh_indices(self, cutter_index: int, meshes: list[Any]) -> list[int]:
        try:
            from ..boolean_ops import bounds_touch_or_overlap

            cutter_bounds = mesh_bounds(meshes[cutter_index])
            out: list[int] = []
            for i, mesh in enumerate(meshes):
                if i == cutter_index:
                    continue
                try:
                    if bounds_touch_or_overlap(mesh_bounds(mesh), cutter_bounds, tolerance=0.05):
                        out.append(i)
                except Exception:
                    pass
            return out
        except Exception:
            log_exception("touching_mesh_indices")
            return []

    def subtract_touching(self) -> None:
        """Subtract the active selected part from every touching part.

        The cutter remains in the scene. Every target that touches or overlaps
        the cutter by bounds is replaced by target - cutter.
        """
        w = self.owner
        QMessageBox = _qmessagebox()
        if self.blocked_message():
            return
        cutter_index = self.active_boolean_cutter_index()
        if cutter_index is None:
            QMessageBox.information(w, "Subtract touching", "Select one cutter part first.")
            return
        try:
            meshes = [copy.deepcopy(m) for m in w.current_meshes()]
            if not (0 <= cutter_index < len(meshes)):
                return
            target_indices = self.touching_mesh_indices(cutter_index, meshes)
            subtract_margin_mm = self.subtract_margin_mm()
            if not target_indices:
                QMessageBox.information(
                    w,
                    "Subtract touching",
                    "No touching part was found around the selected cutter.",
                )
                w.ui_log("[BOOLEAN] Subtract touching: no touching target")
                return

            def _worker() -> BooleanJobResult:
                from ..boolean_ops import BooleanEmptyResult, boolean_difference

                local_meshes = [copy.deepcopy(m) for m in meshes]
                cutter = copy.deepcopy(local_meshes[cutter_index])
                changed = 0
                removed_targets: set[int] = set()
                failures: list[str] = []
                for target_index in target_indices:
                    try:
                        result = boolean_difference(local_meshes[target_index], cutter, cutter_margin_mm=subtract_margin_mm)
                        result.name = str(getattr(local_meshes[target_index], "name", f"part_{target_index}"))
                        result.color = str(getattr(local_meshes[target_index], "color", "#B8B8B8") or "#B8B8B8")
                        local_meshes[target_index] = result
                        changed += 1
                    except BooleanEmptyResult:
                        # A mathematically valid subtraction can consume the whole
                        # target.  This is common with Plan Tracer pieces sharing
                        # the same extrusion depth.  Removing the target is the
                        # correct scene result; it is not an open-volume failure.
                        removed_targets.add(int(target_index))
                        changed += 1
                    except Exception as exc:
                        failures.append(f"target {target_index} ({getattr(local_meshes[target_index], 'name', 'part')}): {exc}")
                if changed <= 0:
                    details = "\n".join(f"- {line}" for line in failures[:8])
                    raise RuntimeError(
                        "No part could be subtracted."
                        + (f"\n\nFailure details:\n{details}" if details else "")
                    )

                adjusted_cutter_index = int(cutter_index)
                if removed_targets:
                    adjusted_cutter_index -= sum(1 for idx in removed_targets if idx < cutter_index)
                    local_meshes = [mesh for idx, mesh in enumerate(local_meshes) if idx not in removed_targets]

                return BooleanJobResult(
                    meshes=local_meshes,
                    selected_indices=[adjusted_cutter_index],
                    active_index=adjusted_cutter_index,
                    reason=(
                        f"Boolean subtract: cutter={cutter_index}, targets={target_indices}, changed={changed}, "
                        f"removed={sorted(removed_targets)}, margin_mm={subtract_margin_mm:g}"
                    ),
                    semantic_operation_type="boolean",
                    failures=failures,
                    user_warning_title="Subtract touching partial result" if failures else None,
                    user_warning_text=(
                        f"Subtracted {changed} part(s), but {len(failures)} target(s) failed.\n"
                        "The detailed geometric reason is available in the error log."
                        if failures else None
                    ),
                )

            self._run_boolean_job(key="subtract_touching", description="Subtract touching", worker=_worker)
        except Exception as exc:
            log_exception("boolean_subtract_touching")
            QMessageBox.critical(w, "Subtract touching failed", str(exc))

    def union_selected(self) -> None:
        """Union all selected parts into one mesh."""
        w = self.owner
        QMessageBox = _qmessagebox()
        if self.blocked_message():
            return
        indices = w._selected_transform_indices()
        if len(indices) < 2:
            QMessageBox.information(w, "Union selected", "Select at least two parts first.")
            return
        try:
            meshes = [copy.deepcopy(m) for m in w.current_meshes()]
            valid = [i for i in indices if 0 <= i < len(meshes)]
            if len(valid) < 2:
                return
            selected_set = set(valid)
            base_index = int(w.active_index) if w.active_index in selected_set else valid[0]
            order = [base_index] + [i for i in valid if i != base_index]

            def _worker() -> BooleanJobResult:
                from ..boolean_ops import boolean_union

                local_meshes = [copy.deepcopy(m) for m in meshes]
                result = copy.deepcopy(local_meshes[base_index])
                failures: list[str] = []
                for idx in order[1:]:
                    try:
                        result = boolean_union(result, local_meshes[idx])
                    except Exception as exc:
                        failures.append(f"{idx}: {exc}")
                        raise

                result.name = f"union_{len(valid)}_parts"
                result.color = str(getattr(local_meshes[base_index], "color", "#B8B8B8") or "#B8B8B8")

                insert_at = min(valid)
                new_meshes = []
                new_index = None
                for i, mesh in enumerate(local_meshes):
                    if i == insert_at:
                        new_index = len(new_meshes)
                        new_meshes.append(result)
                    if i not in selected_set:
                        new_meshes.append(mesh)
                if new_index is None:
                    new_index = len(new_meshes)
                    new_meshes.append(result)
                return BooleanJobResult(
                    meshes=new_meshes,
                    selected_indices=[int(new_index)],
                    active_index=int(new_index),
                    reason=f"Boolean union: selected={valid} -> index={new_index}",
                    semantic_operation_type="boolean",
                    failures=failures,
                )

            self._run_boolean_job(key="union", description="Union selected", worker=_worker)
        except Exception as exc:
            log_exception("boolean_union_selected")
            QMessageBox.critical(
                w,
                "Union selected failed",
                f"{exc}\n\nBoolean union requires closed manifold solids.",
            )

    def separate_selected(self) -> None:
        """Split selected meshes into disconnected mesh islands."""
        w = self.owner
        QMessageBox = _qmessagebox()
        if self.blocked_message():
            return
        indices = w._selected_transform_indices()
        if not indices:
            QMessageBox.information(w, "Separate mesh", "Select at least one part first.")
            return
        try:
            meshes = [copy.deepcopy(m) for m in w.current_meshes()]
            valid = sorted({int(i) for i in indices if 0 <= int(i) < len(meshes)})
            if not valid:
                return

            def _worker() -> BooleanJobResult:
                from ..boolean_ops import split_disconnected_mesh

                local_meshes = [copy.deepcopy(m) for m in meshes]
                selected_set = set(valid)
                new_meshes = []
                new_selection: list[int] = []
                split_count = 0
                added_count = 0
                for old_index, mesh in enumerate(local_meshes):
                    if old_index not in selected_set:
                        new_meshes.append(mesh)
                        continue
                    parts = split_disconnected_mesh(mesh)
                    if len(parts) > 1:
                        split_count += 1
                        added_count += len(parts)
                    start = len(new_meshes)
                    new_meshes.extend(parts)
                    new_selection.extend(range(start, start + len(parts)))
                if split_count <= 0:
                    return BooleanJobResult(
                        meshes=[],
                        selected_indices=[],
                        active_index=None,
                        reason="Boolean separate: no disconnected island found",
                        semantic_operation_type="split",
                        failures=[],
                        no_change_title="Separate mesh",
                        no_change_text="The selected mesh(es) already contain a single connected island.",
                    )
                return BooleanJobResult(
                    meshes=new_meshes,
                    selected_indices=new_selection,
                    active_index=new_selection[-1] if new_selection else None,
                    reason=f"Boolean separate: selected={valid}, split_meshes={split_count}, parts={added_count}",
                    semantic_operation_type="split",
                    failures=[],
                )

            self._run_boolean_job(key="separate", description="Separate mesh", worker=_worker)
        except ValueError as exc:
            QMessageBox.information(w, "Separate mesh", str(exc))
            w.ui_log("[BOOLEAN] Separate: no disconnected island found")
        except Exception as exc:
            log_exception("boolean_separate_selected")
            QMessageBox.critical(w, "Separate mesh failed", str(exc))
