# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any


class UIOrchestrationLayer:
    def _orchestration(self):
        service = getattr(self, "ui_orchestration", None)
        if service is None:
            from ..ui_orchestration import UIOrchestrationService
            service = UIOrchestrationService(self)
            self.ui_orchestration = service
            service.install()
        return service

    def apply_ui_layout(self, layout_id: str, *, persist: bool = True) -> bool:
        ok = bool(self._orchestration().apply_layout(layout_id, persist=persist))
        try:
            definition = self._orchestration().layouts.get(layout_id)
            label = definition.name if definition is not None else layout_id
            self.statusBar().showMessage(("Disposition appliquée : " if ok else "Échec de la disposition : ") + label, 2200)
        except Exception:
            pass
        return ok

    def save_current_ui_layout(self) -> None:
        try:
            from PySide6.QtWidgets import QInputDialog
            name, accepted = QInputDialog.getText(self, "Enregistrer la disposition", "Nom de la disposition :")
            if not accepted or not str(name).strip():
                return
            definition = self._orchestration().layouts.save_user_layout(str(name).strip())
            self.statusBar().showMessage(f"Disposition enregistrée : {definition.name}", 2200)
        except Exception as exc:
            try:
                self.statusBar().showMessage(f"Impossible d’enregistrer la disposition : {exc}", 2600)
            except Exception:
                pass

    def _rebuild_ui_layout_menu(self) -> None:
        menu = getattr(self, "menu_ui_layouts", None)
        if menu is None:
            return
        menu.clear()
        service = self._orchestration().layouts
        from ..ui_orchestration.enums import LayoutCategory
        for definition in service.definitions(include_tutorial=False):
            if definition.category == LayoutCategory.USER:
                continue
            action = menu.addAction(definition.name)
            action.setData(definition.id)
            action.triggered.connect(lambda _checked=False, layout_id=definition.id: self.apply_ui_layout(layout_id, persist=True))
        user_defs = [item for item in service.definitions() if item.category == LayoutCategory.USER]
        if user_defs:
            menu.addSeparator()
            user_menu = menu.addMenu("Mes dispositions")
            for definition in user_defs:
                action = user_menu.addAction(definition.name)
                action.setData(definition.id)
                action.triggered.connect(lambda _checked=False, layout_id=definition.id: self.apply_ui_layout(layout_id, persist=True))
        menu.addSeparator()
        menu.addAction(self.act_layout_save_current)
        menu.addAction(self.act_layout_manage)

    def open_ui_layout_manager(self) -> None:
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import (
                QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLabel,
                QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
            )
            from ..ui_orchestration.enums import LayoutCategory

            dialog = QDialog(self)
            dialog.setWindowTitle("Gestionnaire de dispositions")
            dialog.resize(620, 430)
            root = QVBoxLayout(dialog)
            root.addWidget(QLabel("Les dispositions système sont en lecture seule. Dupliquez-les pour les personnaliser."))
            listing = QListWidget(dialog)
            root.addWidget(listing, 1)
            buttons = QHBoxLayout()
            b_apply = QPushButton("Appliquer")
            b_save = QPushButton("Enregistrer l’actuelle")
            b_update = QPushButton("Mettre à jour")
            b_duplicate = QPushButton("Dupliquer")
            b_delete = QPushButton("Supprimer")
            for button in (b_apply, b_save, b_update, b_duplicate, b_delete):
                buttons.addWidget(button)
            root.addLayout(buttons)
            close_box = QDialogButtonBox(QDialogButtonBox.Close)
            close_box.rejected.connect(dialog.reject)
            close_box.button(QDialogButtonBox.Close).clicked.connect(dialog.accept)
            root.addWidget(close_box)

            def refresh() -> None:
                listing.clear()
                for definition in self._orchestration().layouts.definitions():
                    if definition.category == LayoutCategory.TUTORIAL:
                        continue
                    suffix = "Système" if definition.category == LayoutCategory.SYSTEM else "Utilisateur"
                    item = QListWidgetItem(f"{definition.name}    [{suffix}]")
                    item.setData(Qt.UserRole, definition.id)
                    listing.addItem(item)

            def current_definition() -> Any:
                item = listing.currentItem()
                return self._orchestration().layouts.get(item.data(Qt.UserRole)) if item is not None else None

            b_apply.clicked.connect(lambda: self.apply_ui_layout(current_definition().id, persist=True) if current_definition() is not None else None)
            b_save.clicked.connect(self.save_current_ui_layout)

            def update_current() -> None:
                definition = current_definition()
                if definition is None or definition.category != LayoutCategory.USER:
                    QMessageBox.information(dialog, "Disposition protégée", "Seules les dispositions utilisateur peuvent être mises à jour.")
                    return
                self._orchestration().layouts.update_user_layout(definition.id)
                refresh()

            def duplicate_current() -> None:
                definition = current_definition()
                if definition is None:
                    return
                name, accepted = QInputDialog.getText(dialog, "Dupliquer", "Nom de la copie :", text=f"{definition.name} — copie")
                if accepted and str(name).strip():
                    self._orchestration().layouts.duplicate(definition.id, str(name).strip())
                    refresh()

            def delete_current() -> None:
                definition = current_definition()
                if definition is None or definition.category != LayoutCategory.USER:
                    QMessageBox.information(dialog, "Disposition protégée", "Cette disposition ne peut pas être supprimée.")
                    return
                if QMessageBox.question(dialog, "Supprimer", f"Supprimer « {definition.name} » ?") == QMessageBox.Yes:
                    self._orchestration().layouts.delete_user_layout(definition.id)
                    refresh()

            b_update.clicked.connect(update_current)
            b_duplicate.clicked.connect(duplicate_current)
            b_delete.clicked.connect(delete_current)
            refresh()
            dialog.exec()
        except Exception as exc:
            try:
                self.statusBar().showMessage(f"Impossible d’ouvrir le gestionnaire de dispositions : {exc}", 3000)
            except Exception:
                pass
