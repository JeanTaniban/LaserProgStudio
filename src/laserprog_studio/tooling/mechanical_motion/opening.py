# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable

from .models import MechanicalAssembly
from .plane import MechanicalWorkPlane
from .serialization import assembly_from_mesh


@dataclass(frozen=True, slots=True)
class MechanicalOpenResolution:
    """Resolved startup behaviour when an existing assembly is selected."""

    decision: str
    edit_meshes: tuple[Any, ...] = ()
    inherited_plane: MechanicalWorkPlane | None = None
    source_assembly: MechanicalAssembly | None = None

    @property
    def cancelled(self) -> bool:
        return self.decision == "cancel"


class MechanicalOpenService:
    """Small UI boundary for Edit / New assembly / Cancel startup choices.

    The domain/session remains Qt-free. Desktop prompting is isolated here and
    headless contexts keep the historical deterministic default: edit.
    """

    _VALID_DECISIONS = {"edit", "new", "cancel"}

    def resolve(self, ctx: Any, selected_meshes: Iterable[Any]) -> MechanicalOpenResolution:
        meshes = tuple(selected_meshes)
        source_mesh = None
        source_assembly = None
        for mesh in meshes:
            candidate = assembly_from_mesh(mesh)
            if candidate is not None:
                source_mesh = mesh
                source_assembly = candidate
                break
        if source_assembly is None:
            return MechanicalOpenResolution("new")

        decision = self._ask(ctx, source_mesh, source_assembly)
        if decision == "edit":
            return MechanicalOpenResolution("edit", edit_meshes=meshes, source_assembly=source_assembly)
        if decision == "new":
            plane = source_assembly.work_plane
            inherited = copy.deepcopy(plane) if isinstance(plane, MechanicalWorkPlane) else None
            return MechanicalOpenResolution("new", inherited_plane=inherited, source_assembly=source_assembly)
        return MechanicalOpenResolution("cancel", source_assembly=source_assembly)

    def _ask(self, ctx: Any, mesh: Any, assembly: MechanicalAssembly) -> str:
        owner = getattr(ctx, "owner", None)
        chooser = getattr(owner, "ask_mechanical_edit_or_new", None) if owner is not None else None
        if callable(chooser):
            try:
                value = str(chooser(mesh, assembly) or "edit").strip().lower()
                if value in self._VALID_DECISIONS:
                    return value
            except Exception:
                pass

        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is None:
                return "edit"
            box = QMessageBox(owner)
            box.setWindowTitle("Mechanical motion")
            name = str(getattr(mesh, "name", "") or assembly.name or "this mechanical assembly")
            kind = "recoverable draft" if bool(assembly.draft) else "mechanical assembly"
            box.setText(f"An existing {kind} is selected: {name}.")
            box.setInformativeText(
                "Edit it, create a separate assembly on the same construction plane, or cancel opening the tool?"
            )
            edit_button = box.addButton("Edit", QMessageBox.AcceptRole)
            new_button = box.addButton("New assembly", QMessageBox.ActionRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.setDefaultButton(edit_button)
            box.exec()
            clicked = box.clickedButton()
            if clicked is edit_button:
                return "edit"
            if clicked is new_button:
                return "new"
            return "cancel"
        except Exception:
            return "edit"

    @staticmethod
    def close_cancelled_open(ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        close = getattr(owner, "close_active_tool", None) if owner is not None else None
        if not callable(close):
            return

        def _close() -> None:
            try:
                close(log_it=False, ask_preview=False)
            except TypeError:
                close()
            except Exception:
                pass

        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, _close)
        except Exception:
            _close()


__all__ = ["MechanicalOpenResolution", "MechanicalOpenService"]
