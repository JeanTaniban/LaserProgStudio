# -*- coding: utf-8 -*-
from __future__ import annotations

from ..application.export_controller import ExportController


class ExportingLayer:
    """Window-facing facade for code still calling ExportingLayer methods."""

    def _export_controller(self) -> ExportController:
        controller = getattr(self, "export_controller", None)
        if controller is None:
            controller = ExportController.create(self.app_context)
            self.export_controller = controller
        return controller

    def _polydata_to_workmesh(self, *args, **kwargs):
        return self._export_controller()._polydata_to_workmesh(*args, **kwargs)

    def _make_manual_workmesh(self, *args, **kwargs):
        return self._export_controller()._make_manual_workmesh(*args, **kwargs)



    def export_3mf_dialog(self, *args, **kwargs):
        return self._export_controller().export_3mf_dialog(*args, **kwargs)

    def open_engrave_workspace(self, *args, **kwargs):
        return self._export_controller().open_engrave_workspace(*args, **kwargs)

    def close_engrave_workspace(self, *args, **kwargs):
        return self._export_controller().close_engrave_workspace(*args, **kwargs)

    def _engrave_config_from_ui(self, *args, **kwargs):
        return self._export_controller()._engrave_config_from_ui(*args, **kwargs)

    def _render_current_model_to_engrave_images(self, *args, **kwargs):
        return self._export_controller()._render_current_model_to_engrave_images(*args, **kwargs)

    def render_engrave_current(self, *args, **kwargs):
        return self._export_controller().render_engrave_current(*args, **kwargs)

    def _engrave_dimension_metadata(self, *args, **kwargs):
        return self._export_controller()._engrave_dimension_metadata(*args, **kwargs)

    def _save_png_with_dimensions(self, *args, **kwargs):
        return self._export_controller()._save_png_with_dimensions(*args, **kwargs)

    def save_engrave_all(self, *args, **kwargs):
        return self._export_controller().save_engrave_all(*args, **kwargs)

    def save_engrave_falcon_svg(self, *args, **kwargs):
        return self._export_controller().save_engrave_falcon_svg(*args, **kwargs)

    def save_engrave_dimensions_json(self, *args, **kwargs):
        return self._export_controller().save_engrave_dimensions_json(*args, **kwargs)

    def export_gravure_dialog(self, *args, **kwargs):
        return self._export_controller().export_gravure_dialog(*args, **kwargs)

    def open_3mf_dialog(self, *args, **kwargs):
        return self._export_controller().open_3mf_dialog(*args, **kwargs)

    def load_default_2d_preview(self, *args, **kwargs):
        return self._export_controller().load_default_2d_preview(*args, **kwargs)

    def load_2d_image(self, *args, **kwargs):
        return self._export_controller().load_2d_image(*args, **kwargs)
