# -*- coding: utf-8 -*-
from __future__ import annotations

from ..application.machine_controller import MachineController


class MachineLayer:
    """Window-facing facade for machine/G-code actions."""

    def _machine_controller(self) -> MachineController:
        controller = getattr(self, "machine_controller", None)
        if controller is None:
            controller = MachineController(self.app_context)
            self.machine_controller = controller
        return controller

    def open_machine_engraving_dialog(self, *args, **kwargs):
        return self._machine_controller().open_machine_engraving_dialog(*args, **kwargs)
