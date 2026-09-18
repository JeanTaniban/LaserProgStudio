# -*- coding: utf-8 -*-
from __future__ import annotations

from .laser_3mf_core import *  # type: ignore  # noqa: F401,F403
from .image_panel import ImagePanel  # type: ignore  # noqa: F401

class Laser3MFAppLifecycleLayer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("3MF Laser Preview - large laser view + mouse wheel zoom")
        self.root.geometry("1320x860")
        self.root.minsize(1050, 700)

        self.config = RenderConfig()
        self.input_path: Optional[Path] = None
        self.images: Dict[str, Image.Image] = {}
        self.render_after_id: Optional[str] = None
        self.is_rendering = False
        self.last_instances_count = 0
        self.last_instances: List[Instance2D] = []

        # Variables UI
        self.input_var = tk.StringVar(value="")
        self.output_root_var = tk.StringVar(value=str(Path.cwd()))
        self.status_var = tk.StringVar(value="Select a 3MF file to start.")
        self.preset_var = tk.StringVar(value="")
        self.available_presets: List[str] = []

        self._updating_from_slider = False
        self._updating_from_entry = False
        self._loading_preset = False
        self.param_widgets = {}

        self.dpi_var = tk.StringVar(value=str(self.config.dpi))
        self.contour_width_var = tk.StringVar(value=str(self.config.contour_width_mm))
        self.contour_margin_var = tk.StringVar(value=str(self.config.contour_margin_mm))
        self.fill_margin_var = tk.StringVar(value=str(self.config.fill_margin_mm))
        self.fill_edge_width_var = tk.StringVar(value=str(self.config.fill_edge_width_mm))
        self.normal_threshold_var = tk.StringVar(value=str(self.config.normal_z_threshold))
        self.page_margin_var = tk.StringVar(value=str(self.config.page_margin_ratio))
        self.label_size_var = tk.StringVar(value=str(self.config.label_font_size_px))
        self.min_px_var = tk.StringVar(value=str(self.config.min_output_px))
        # Display-only grid: it is not baked into exported PNGs.
        self.grid_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._bind_live_updates()
        self.refresh_preset_list()
        self.load_startup_preset()

    def run(self):
        self.root.mainloop()
