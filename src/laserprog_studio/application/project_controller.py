# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import time

from ..app_context import AppContext
from ..studio_log import log_exception
try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None
from .action_controller import WindowController


def _qt_widgets():
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    return QFileDialog, QMessageBox


class ProjectController(WindowController):
    """User-facing project commands for the native .lpsproj workflow."""

    @classmethod
    def create(cls, context: AppContext) -> "ProjectController":
        return cls(context)

    def _sync_after_project_change(self, *, keep_camera: bool = False, message: str | None = None) -> None:
        start = time.perf_counter()
        try:
            return self._sync_after_project_change_measured(keep_camera=keep_camera, message=message)
        finally:
            if _APP_AUDIT is not None:
                _APP_AUDIT.record_timing("project.sync_after_change.total", (time.perf_counter() - start) * 1000.0, details={"keep_camera": keep_camera})

    def _sync_after_project_change_measured(self, *, keep_camera: bool = False, message: str | None = None) -> None:
        w = self.owner
        try:
            from ..project import sync_window_to_active_scene

            sync_window_to_active_scene(w)
        except Exception:
            pass
        try:
            w.selected_indices = []
            w.active_index = None
            w.render_camera_state = None
        except Exception:
            pass
        try:
            w._remove_render_camera_helper(render=False)
        except Exception:
            pass
        try:
            w.close_active_tool(log_it=False, ask_preview=False)
        except Exception:
            pass
        try:
            w.rebuild_scene(keep_camera=keep_camera)
        except Exception:
            pass
        try:
            w._sync_history_buttons()
        except Exception:
            pass
        try:
            w.sync_scene_tabs()
        except Exception:
            pass
        try:
            w.update_project_title()
        except Exception:
            pass
        if message:
            try:
                w.ui_log(message)
            except Exception:
                pass

    def confirm_discard_if_dirty(self, action: str) -> bool:
        """Ask before losing unsaved project changes.

        The dialog intentionally offers Save / Discard / Cancel instead of a
        bare yes/no prompt: deleting a project, opening another file or quitting
        must not let the user lose work by accident.
        """
        w = self.owner
        project = getattr(w, "project_store", None)
        if project is None or not bool(getattr(project, "dirty", False)):
            return True
        QFileDialog, QMessageBox = _qt_widgets()
        try:
            box = QMessageBox(w)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Unsaved project")
            box.setText("The current project has unsaved changes.")
            box.setInformativeText(f"Save before {action}?")
            save_button = box.addButton(QMessageBox.StandardButton.Save)
            discard_button = box.addButton(QMessageBox.StandardButton.Discard)
            cancel_button = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(save_button)
            box.exec()
            clicked = box.clickedButton()
            if clicked == save_button:
                return bool(self.save_project(save_as=False))
            if clicked == discard_button:
                return True
            return False
        except Exception:
            return False

    def confirm_close_scene(self, scene_id: str) -> bool:
        """Ask before deleting a scene with unsaved scene-level changes."""
        w = self.owner
        project = getattr(w, "project_store", None)
        scene = getattr(project, "scenes", {}).get(str(scene_id)) if project is not None else None
        if scene is None or not bool(getattr(scene, "dirty", False)):
            return True
        _QFileDialog, QMessageBox = _qt_widgets()
        try:
            answer = QMessageBox.warning(
                w,
                "Delete unsaved scene",
                f"The scene '{getattr(scene, 'name', 'Scene')}' contains unsaved changes. Delete it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return answer == QMessageBox.StandardButton.Yes
        except Exception:
            return False

    def new_project(self) -> None:
        if not self.confirm_discard_if_dirty("New Project"):
            return
        try:
            from ..project import reset_project

            reset_project(self.owner, scene_name="main")
            self._sync_after_project_change(keep_camera=False, message="[PROJECT] New project")
        except Exception:
            log_exception("new_project")

    def open_project_dialog(self) -> None:
        QFileDialog, QMessageBox = _qt_widgets()
        if not self.confirm_discard_if_dirty("Open Project"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self.owner,
            "Open LaserProg project",
            str(Path.home()),
            "LaserProg project (*.lpsproj);;All files (*.*)",
        )
        if not path:
            return
        self.open_project(Path(path))

    def open_project(self, path: str | Path) -> bool:
        start = time.perf_counter()
        try:
            return self._open_project_measured(path)
        finally:
            if _APP_AUDIT is not None:
                _APP_AUDIT.record_timing("project.open.total", (time.perf_counter() - start) * 1000.0, details={"path": str(path)})

    def _open_project_measured(self, path: str | Path) -> bool:
        try:
            from ..io.project_file import load_project
            from ..project import sync_window_to_active_scene

            project = load_project(path)
            self.owner.project_store = project
            sync_window_to_active_scene(self.owner)
            self._sync_after_project_change(keep_camera=False, message=f"[PROJECT] Opened: {path}")
            return True
        except Exception as exc:
            log_exception("open_project")
            try:
                _qt_widgets()[1].warning(self.owner, "Open project", str(exc))
            except Exception:
                pass
            return False

    def save_project(self, *, save_as: bool = False) -> bool:
        start = time.perf_counter()
        try:
            return self._save_project_measured(save_as=save_as)
        finally:
            if _APP_AUDIT is not None:
                _APP_AUDIT.record_timing("project.save.total", (time.perf_counter() - start) * 1000.0, details={"save_as": save_as})

    def _save_project_measured(self, *, save_as: bool = False) -> bool:
        QFileDialog, QMessageBox = _qt_widgets()
        try:
            from ..io.project_file import PROJECT_EXTENSION, save_project_atomic
            from ..project import ensure_project_store

            project = ensure_project_store(self.owner)
            path = getattr(project, "project_path", None)
            if save_as or path is None:
                default_dir = Path.home()
                if path is not None:
                    default_dir = Path(path).parent
                default_name = Path(path).name if path is not None else "laserprog_project.lpsproj"
                chosen, _ = QFileDialog.getSaveFileName(
                    self.owner,
                    "Save LaserProg project",
                    str(default_dir / default_name),
                    "LaserProg project (*.lpsproj);;All files (*.*)",
                )
                if not chosen:
                    return False
                path = Path(chosen)
                if path.suffix.lower() != PROJECT_EXTENSION:
                    path = path.with_suffix(PROJECT_EXTENSION)
            save_project_atomic(project, path)
            try:
                self.owner._project_dirty_since_monotonic = None
                self.owner._last_autosave_monotonic = None
                self.owner.autosave_pending = False
            except Exception:
                pass
            try:
                self.owner.update_project_title()
                self.owner.sync_scene_tabs()
            except Exception:
                pass
            try:
                self.owner.ui_log(f"[PROJECT] Saved: {path}")
            except Exception:
                pass
            return True
        except Exception as exc:
            log_exception("save_project")
            try:
                QMessageBox.warning(self.owner, "Save project", str(exc))
            except Exception:
                pass
            return False

    def save_project_as(self) -> bool:
        return bool(self.save_project(save_as=True))


    def _autosave_path(self) -> Path:
        project = getattr(self.owner, "project_store", None)
        canonical = getattr(project, "project_path", None) if project is not None else None
        if canonical is not None:
            canonical = Path(canonical)
            return canonical.with_name(canonical.stem + ".autosave.lpsproj")
        try:
            from ..bootstrap import compute_paths

            autosave_dir = compute_paths().diagnostics_dir / "autosaves"
        except Exception:
            autosave_dir = Path.home() / ".laserprog_studio" / "autosaves"
        project_id = str(getattr(project, "project_id", "untitled") or "untitled")
        return autosave_dir / f"{project_id}.autosave.lpsproj"

    def _critical_operation_active(self) -> bool:
        w = self.owner
        try:
            if bool(getattr(w, "autosave_in_progress", False)):
                return True
            if getattr(w, "active_tool", getattr(w, "TOOL_NONE", None)) != getattr(w, "TOOL_NONE", None):
                return True
            if callable(getattr(w, "has_preview", None)) and bool(w.has_preview()):
                return True
            if getattr(w, "_drag_axis", None) is not None or getattr(w, "_gizmo_pressed_axis", None) is not None:
                return True
        except Exception:
            return True
        return False

    def _schedule_background_autosave(self, project: Any, path: Path, *, due: str, scheduled_at: float) -> bool:
        """Start one recovery save without blocking the Qt thread.

        The worker snapshots and writes in a background thread.  The UI thread
        only schedules work and receives a small completion callback.  A newer
        autosave request with the same key marks older callbacks stale through
        ``BackgroundTaskManager``; ``autosave_in_progress`` prevents concurrent
        writes from piling up.
        """

        w = self.owner
        if bool(getattr(w, "autosave_in_progress", False)):
            w.autosave_pending = True
            return False
        try:
            from .background_tasks import task_manager_for
        except Exception:
            task_manager_for = None
        w.autosave_in_progress = True
        w.autosave_pending = False
        started = time.monotonic()

        def _worker() -> dict[str, Any]:
            from ..io.project_file import save_project_atomic

            # Copy in the worker, not in the Qt event handler.  Autosave runs
            # only after the idle/critical-operation checks, so this avoids UI
            # freezes while keeping a coherent recovery snapshot for the writer.
            snapshot_started = time.monotonic()
            project_snapshot = copy.deepcopy(project)
            write_started = time.monotonic()
            save_project_atomic(project_snapshot, path, mark_clean=False, autosave_fast=True)
            finished = time.monotonic()
            try:
                size_bytes = int(path.stat().st_size)
            except Exception:
                size_bytes = 0
            return {
                "path": str(path),
                "due": str(due),
                "scheduled_at": float(scheduled_at),
                "snapshot_ms": (write_started - snapshot_started) * 1000.0,
                "write_ms": (finished - write_started) * 1000.0,
                "total_ms": (finished - snapshot_started) * 1000.0,
                "size_bytes": size_bytes,
            }

        def _success(result: dict[str, Any]) -> None:
            try:
                w._last_autosave_monotonic = float(result.get("scheduled_at", scheduled_at))
                if getattr(w, "_project_dirty_since_monotonic", None) is None:
                    w._project_dirty_since_monotonic = float(result.get("scheduled_at", scheduled_at))
                w.autosave_pending = False
                w._last_autosave_duration_ms = float(result.get("total_ms", 0.0))
                w._last_autosave_size_bytes = int(result.get("size_bytes", 0))
                w._last_autosave_path = str(result.get("path", path))
                if _APP_AUDIT is not None:
                    _APP_AUDIT.record_timing("project.autosave.worker_total", float(result.get("total_ms", 0.0)), details={"due": str(result.get("due", due)), "size_bytes": int(result.get("size_bytes", 0))})
                    _APP_AUDIT.record_timing("project.autosave.snapshot", float(result.get("snapshot_ms", 0.0)))
                    _APP_AUDIT.record_timing("project.autosave.write", float(result.get("write_ms", 0.0)))
                    _APP_AUDIT.set_value("project.autosave.last_size_bytes", int(result.get("size_bytes", 0)))
                    _APP_AUDIT.set_value("project.autosave.last_path", str(result.get("path", path)))
                try:
                    w.ui_log(
                        f"[AUTOSAVE] Recovery project saved ({due}, "
                        f"{w._last_autosave_duration_ms:.0f} ms worker)"
                    )
                except Exception:
                    pass
            except Exception:
                pass

        def _error(exc: BaseException) -> None:
            try:
                w.autosave_pending = True
                w._last_autosave_error = str(exc)
            except Exception:
                pass
            log_exception("autosave_background")

        def _finished() -> None:
            try:
                w.autosave_in_progress = False
                w._last_autosave_schedule_ms = (time.monotonic() - started) * 1000.0
            except Exception:
                pass

        if task_manager_for is None:
            try:
                _success(_worker())
                return True
            except BaseException as exc:  # noqa: BLE001 - fallback boundary
                _error(exc)
                return False
            finally:
                _finished()
        manager = task_manager_for(w)
        manager.run(
            "project.autosave",
            _worker,
            on_success=_success,
            on_error=_error,
            on_finished=_finished,
            description="Project autosave",
        )
        return True

    def autosave_tick(self) -> bool:
        start = time.perf_counter()
        try:
            return self._autosave_tick_measured()
        finally:
            if _APP_AUDIT is not None:
                _APP_AUDIT.record_timing("project.autosave.tick", (time.perf_counter() - start) * 1000.0)

    def _autosave_tick_measured(self) -> bool:
        """Run one autosave policy tick.

        Returns True when a recovery save has been scheduled.  In headless tests
        the background manager falls back to synchronous execution, so existing
        tests can still assert that the file exists immediately.
        """
        try:
            from ..project import ensure_project_store

            w = self.owner
            project = ensure_project_store(w)
            policy = getattr(w, "autosave_policy", None)
            if policy is None:
                return False
            now = time.monotonic()
            last_autosave = getattr(w, "_last_autosave_monotonic", None)
            if last_autosave is None:
                last_autosave = getattr(w, "_project_dirty_since_monotonic", None)
            last_activity = getattr(w, "_last_project_activity_monotonic", None)
            critical = self._critical_operation_active()
            in_progress = bool(getattr(w, "autosave_in_progress", False))
            due = policy.due_kind(
                dirty=bool(getattr(project, "dirty", False)),
                now_s=now,
                last_autosave_s=last_autosave,
                last_activity_s=last_activity,
                critical_operation_active=critical,
                save_in_progress=in_progress,
            )
            if due is None:
                # If a forced save was due during a critical operation or while a
                # previous worker was writing, keep a pending flag so the next
                # quiet tick writes immediately instead of silently skipping.
                if (critical or in_progress) and bool(getattr(project, "dirty", False)):
                    forced_due = policy.due_kind(
                        dirty=True,
                        now_s=now,
                        last_autosave_s=last_autosave,
                        last_activity_s=last_activity,
                        critical_operation_active=False,
                        save_in_progress=False,
                    )
                    if forced_due == "forced":
                        w.autosave_pending = True
                return False
            if critical or in_progress:
                w.autosave_pending = True
                return False
            return self._schedule_background_autosave(project, self._autosave_path(), due=due, scheduled_at=now)
        except Exception:
            log_exception("autosave_tick")
            try:
                self.owner.autosave_in_progress = False
            except Exception:
                pass
            return False

    def mark_dirty(self) -> None:
        try:
            import time
            project = getattr(self.owner, "project_store", None)
            was_dirty = bool(getattr(project, "dirty", False)) if project is not None else False
            now = time.monotonic()
            if project is not None:
                project.mark_dirty()
            self.owner._last_project_activity_monotonic = now
            if not was_dirty or getattr(self.owner, "_project_dirty_since_monotonic", None) is None:
                self.owner._project_dirty_since_monotonic = now
        except Exception:
            pass
        try:
            self.owner.update_project_title()
        except Exception:
            pass
        try:
            self.owner.sync_scene_tabs()
        except Exception:
            pass
