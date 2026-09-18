# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import QHBoxLayout
from ..application.toolbar_controller import ConfigurableToolbarController


class UIConfigurableToolbarLayer:
    """Window-facing facade for the configurable top toolbar.

    The implementation has moved to ``application.toolbar_controller`` so the
    main window no longer receives toolbar behavior through inheritance.  These
    methods remain because older signals/controllers still call the window by
    these names during the migration.
    """

    def _toolbar_controller(self) -> ConfigurableToolbarController:
        controller = getattr(self, "toolbar_controller", None)
        if controller is None:
            controller = ConfigurableToolbarController.create(self.app_context)
            self.toolbar_controller = controller
        return controller

    def _setup_configurable_toolbar(self, top_l: QHBoxLayout) -> None:
        self._toolbar_controller().setup(top_l)

    def _toolbar_max_items(self) -> int:
        return self._toolbar_controller().max_items()

    def _all_toolbar_button_attrs(self) -> tuple[str, ...]:
        return self._toolbar_controller().all_button_attrs()

    def _set_toolbar_remove_mode(self, checked: bool) -> None:
        self._toolbar_controller().set_remove_mode(checked)

    def _apply_toolbar_remove_mode_visuals(self) -> None:
        self._toolbar_controller().apply_remove_mode_visuals()

    def _rebuild_configurable_toolbar(self, *, save: bool = True) -> None:
        self._toolbar_controller().rebuild(save=save)

    def _activate_toolbar_item(self, item_id: str) -> None:
        self._toolbar_controller().activate_item(item_id)

    def add_toolbar_item(self, item_id: str) -> bool:
        return self._toolbar_controller().add_item(item_id)

    def remove_toolbar_item(self, item_id: str) -> bool:
        return self._toolbar_controller().remove_item(item_id)

    def _toolbar_palette_match_specs(self, query: str):
        return self._toolbar_controller().match_palette_specs(query)

    def open_toolbar_palette(self) -> None:
        self._toolbar_controller().open_palette()
