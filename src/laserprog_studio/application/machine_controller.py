# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import replace

from ..bootstrap import compute_paths
from ..studio_log import log_exception
from .action_controller import WindowController


class MachineController(WindowController):
    """Application-level entry points for guarded machine/G-code workflows."""

    def open_machine_engraving_dialog(self) -> None:
        owner = self.owner
        try:
            from PySide6.QtWidgets import QMessageBox

            if getattr(owner, "mesh_store", None) is None or not owner.current_meshes():
                QMessageBox.information(owner, "Machine / engraving", "The scene is empty. Create or open a model first.")
                return
            # Reuse the existing engraving renderer as the stable 3D -> 2D seam.
            if not getattr(owner, "_engrave_images", None) or not getattr(owner, "_engrave_instances", None):
                owner.render_engrave_current()
            instances = getattr(owner, "_engrave_instances", None)
            cfg = getattr(owner, "_engrave_config", None)
            if not instances or cfg is None:
                QMessageBox.warning(owner, "Machine / engraving", "No vector engraving geometry is available yet.")
                return
            from laserprog_studio.machine.profiles import FALCON_A1_PRO_PROFILE
            from laserprog_studio.machine.ui import MachineEngravingDialog

            profile = FALCON_A1_PRO_PROFILE
            laser_prefs = getattr(getattr(owner, "project_preferences", None), "laser", None)
            if laser_prefs is not None:
                profile = replace(
                    profile,
                    work_area_x_mm=float(getattr(laser_prefs, "machine_area_x_mm", profile.work_area_x_mm)),
                    work_area_y_mm=float(getattr(laser_prefs, "machine_area_y_mm", profile.work_area_y_mm)),
                    notes=(
                        profile.notes
                        + " Machine travel limits are taken from Preferences > Laser engraving for preflight validation."
                    ),
                )
            paths = compute_paths()
            dialog = MachineEngravingDialog(owner, instances=instances, cfg=cfg, default_dir=paths.root, profile=profile)
            dialog.exec()
        except Exception as exc:
            log_exception("open_machine_engraving_dialog")
            try:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.critical(
                    owner,
                    "Machine tool failed to open",
                    "The laser machine dialog could not be started.\n\n"
                    f"{type(exc).__name__}: {exc}\n\n"
                    "The full traceback was written to the LaserProg log.",
                )
            except Exception:
                pass
