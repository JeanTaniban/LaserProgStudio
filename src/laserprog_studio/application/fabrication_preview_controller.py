# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from ..app_context import AppContext
from ..bootstrap import compute_paths
from ..studio_log import log_exception
from ..engraving.roles import apply_default_outline_to_unassigned

from .owner_delegating_controller import OwnerDelegatingController


def _qmessagebox():
    from PySide6.QtWidgets import QMessageBox
    return QMessageBox


def _qtimer():
    from PySide6.QtCore import QTimer
    return QTimer


TOOLBOX_DIR = compute_paths().toolbox_dir


class FabricationPreviewController(OwnerDelegatingController):
    """Preview workflows for fabrication tools: box, lay-flat and joints."""

    @classmethod
    def create(cls, context: AppContext) -> "FabricationPreviewController":
        return cls(context)

    def _lay_fusion_code(self) -> str:
        text = self.lay_fusion_combo.currentText()
        if text.startswith("noe"):
            return "noe"
        if text.startswith("touch"):
            return "touch"
        return "overlap"

    def _lay_pack_code(self) -> str:
        text = self.lay_pack_combo.currentText()
        if text.startswith("Max depth"):
            return "max_depth"
        if text.startswith("Free"):
            return "noe"
        return "max_length"

    def generate_layflat_preview(self) -> None:
        try:
            from laserprog_studio.fabrication.layflat_arranger import MeshObject, WorkMesh, group_objects, merge_group, orient_piece_flat, pack_pieces
            base = [copy.deepcopy(m) for m in self.committed_meshes()]
            if not base:
                self.ui_log("[LAYFLAT] No mesh")
                return
            src = [MeshObject(name=m.name, vertices=list(m.vertices), triangles=list(m.triangles), color=getattr(m, "color", "#B8B8B8"), source_object_id=str(i)) for i, m in enumerate(base)]
            fusion_mode = self._lay_fusion_code()
            minimum_overlap = float(self.lay_min_overlap.value())
            touch_tol = float(self.lay_touch_tol.value())
            spacing = float(self.lay_spacing.value())
            packing_constraint = self._lay_pack_code()
            max_length = float(self.lay_max_length.value())
            max_depth = float(self.lay_max_depth.value())
            allow_rotation = bool(self.lay_allow_rot.isChecked())

            groups = group_objects(src, fusion_mode, touch_tol, minimum_overlap)
            pieces = [merge_group(group, i + 1) for i, group in enumerate(groups)]
            for piece in pieces:
                orient_piece_flat(piece)
            pieces = pack_pieces(pieces, spacing, packing_constraint, max_length, max_depth, allow_rotation)
            out = [WorkMesh(name=p.name, vertices=list(p.vertices), triangles=list(p.triangles), color=p.color) for p in pieces]
            changed_roles = apply_default_outline_to_unassigned(out)
            self.set_preview_meshes(out, "Lay flat")
            total_w = total_d = 0.0
            if pieces:
                xs = [x for p in pieces for x, _, _ in p.vertices]
                ys = [y for p in pieces for _, y, _ in p.vertices]
                total_w = max(xs) - min(xs)
                total_d = max(ys) - min(ys)
            report = (
                f"Source objects: {len(src)}\n"
                f"Parts after merge: {len(pieces)}\n"
                f"Mode: {fusion_mode}\n"
                f"Packing: {packing_constraint}\n"
                f"Bounds: {total_w:.3f} x {total_d:.3f} mm\n"
                f"Default outline roles assigned: {changed_roles}"
            )
            self.lay_report.setText(report)
            self.ui_log("[LAYFLAT] Preview OK | " + report.replace("\n", " | "))
        except Exception as exc:
            log_exception("generate_layflat_preview")
            _qmessagebox().warning(self.owner, "Lay flat", str(exc))

    def generate_joint_preview(self) -> None:
        debug_cb = None
        try:
            if len(self.selected_indices) != 2:
                self.ui_log("[JOINT] Select exactly two parts: A then B")
                return
            from laserprog_studio.fabrication.joint_builder import apply_tab_slot_to_scene, DEBUG_LOG_VERSION
            a, b = self.selected_indices
            base_meshes = [copy.deepcopy(m) for m in self.current_meshes()]
            if not (0 <= a < len(base_meshes) and 0 <= b < len(base_meshes)):
                raise ValueError("Invalid selection.")
            touch_tol = float(self.joint_touch_tol.value())
            clearance = float(self.joint_clearance.value())
            joint_size = float(self.joint_size.value())
            joint_count = int(self.joint_count.value())
            joint_edge_margin = float(self.joint_edge_margin.value())
            single_probe = bool(self.joint_single_probe.isChecked())
            subtract_all = bool(self.joint_subtract_all.isChecked())

            try:
                from laserprog_studio.services.debug_mode import should_record_diagnostics
                _global_debug = should_record_diagnostics(self)
            except Exception:
                _global_debug = False
            if self.joint_debug.isChecked() and _global_debug:
                log_path = TOOLBOX_DIR / "settings" / "joint_builder_debug.log"
                def _dbg(tag: str, payload: dict) -> None:
                    import json
                    record = {
                        "ts": _dt.datetime.now().isoformat(timespec="seconds"),
                        "tag": tag,
                        "tool": "joint_builder_qt",
                        "a": int(a),
                        "b": int(b),
                        "payload": payload,
                    }
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    with log_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                debug_cb = _dbg
                debug_cb("start", {"touch_tol": touch_tol, "clearance": clearance, "joint_size": joint_size, "joint_count": joint_count, "joint_edge_margin": joint_edge_margin, "single_depth_probe": single_probe, "subtract_all": subtract_all, "debug_log_version": int(DEBUG_LOG_VERSION), "preview_input": bool(self.has_preview())})

            base_meshes, changed_indices = apply_tab_slot_to_scene(
                base_meshes,
                index_a=a,
                index_b=b,
                touch_tolerance=touch_tol,
                clearance=clearance,
                joint_size=joint_size,
                joint_count=joint_count,
                joint_edge_margin=joint_edge_margin,
                single_depth_probe=single_probe,
                subtract_all=subtract_all,
                debug=debug_cb,
            )
            was_already_previewing = bool(self.has_preview())
            self.set_preview_meshes(base_meshes, f"Joint added A={a} B={b}")

            # Batch-joint UX: once a joint is staged, the two source parts are no
            # longer considered selected. This makes the next A/B pick explicit and
            # prevents accidentally adding the same joint again. The active joint tool
            # stays open; only the selection is cleared.
            self.clear_selection(reason="joint added to preview")

            if debug_cb:
                debug_cb("done", {"status": "ok"})
            pending = "batch preview" if was_already_previewing else "preview"
            scope = "all intersecting parts" if subtract_all else "B only"
            self.ui_log(f"[JOINT] Added to {pending}: A={a} B={b} changed={list(changed_indices)} count={joint_count} edge_margin={joint_edge_margin:.2f}mm female cut={scope}. Select another pair or Apply when finished.")
        except Exception as exc:
            if debug_cb:
                try:
                    debug_cb("error", {"error": str(exc)})
                except Exception:
                    pass
            log_exception("generate_joint_preview")
            _qmessagebox().warning(self.owner, "Joint builder", str(exc))

    def _clear_joint_selection_state(self) -> None:
        """Clear A/B joint selections when leaving or suspending the joint tool."""
        try:
            self.selected_indices = []
            self.active_index = None
            self._gizmo_delta_display_signature = None
            self._gizmo_pressed_axis = None
            self._gizmo_press_pos = None
            self._hovered_transform_axis = None
            self._highlighted_transform_axis = None
            try:
                self.mesh_list.clearSelection()
            except Exception:
                pass
            self._clear_gizmo_interaction(clear_highlight=True)
            self._clear_gizmo_actors()
        except Exception:
            log_exception("clear_joint_selection_state")

    def update_joint_info(self) -> None:
        try:
            if hasattr(self, "joint_info"):
                labels = []
                for idx in list(getattr(self, "selected_indices", []) or [])[:2]:
                    try:
                        labels.append(f"{int(idx):02d}")
                    except Exception:
                        labels.append(str(idx))
                pair = " / ".join(labels) if labels else "—"
                mode = "active" if self.active_tool == self.TOOL_JOINT else "inactive"
                preview = "yes" if self.has_preview() else "no"
                self.joint_info.setText(f"A/B: {pair} | Mode: {mode} | Preview : {preview}")
        except Exception:
            pass
