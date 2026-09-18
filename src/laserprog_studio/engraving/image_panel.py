# -*- coding: utf-8 -*-
from __future__ import annotations

from .laser_3mf_core import *  # type: ignore  # noqa: F401,F403


class ImagePanel(ttk.LabelFrame):
    """Embedded image panel with mouse-wheel zoom toward the cursor."""

    def __init__(self, master, app: "Laser3MFSingleWindowApp", title: str, key: str, filename: str):
        super().__init__(master, text=title)
        self.app = app
        self.key = key
        self.filename = filename
        self.photo = None
        self.original_size = ""
        self.source_img: Optional[Image.Image] = None
        self.zoom = 1.0
        self.offset_x: Optional[float] = None
        self.offset_y: Optional[float] = None
        self.display_scale = 1.0
        self._redraw_after_id: Optional[str] = None
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_start_offset_x = 0.0
        self.pan_start_offset_y = 0.0

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, background="white", highlightthickness=0, cursor="crosshair")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.canvas.create_text(10, 10, anchor="nw", text="No image", fill="#555")

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)       # Windows / macOS
        self.canvas.bind("<Button-4>", self._on_mousewheel_linux)   # Linux wheel up
        self.canvas.bind("<Button-5>", self._on_mousewheel_linux)   # Linux wheel down
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        # Pan: hold middle mouse button and move.
        self.canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)

        bottom = ttk.Frame(self)
        bottom.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        bottom.columnconfigure(0, weight=1)

        self.info_label = ttk.Label(bottom, text="", foreground="#555")
        self.info_label.grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Save", command=self.save).grid(row=0, column=1, sticky="e")

    def set_image(self, img: Image.Image):
        self.source_img = img.copy()
        self.zoom = 1.0
        self.offset_x = None
        self.offset_y = None
        self.original_size = f"{img.width} x {img.height} px"
        self.info_label.configure(text=self.original_size)
        self.redraw()

    def _canvas_size(self) -> Tuple[int, int]:
        self.update_idletasks()
        return max(20, self.canvas.winfo_width()), max(20, self.canvas.winfo_height())

    def _fit_scale(self) -> float:
        if self.source_img is None:
            return 1.0
        cw, ch = self._canvas_size()
        return max(1e-6, min(cw / self.source_img.width, ch / self.source_img.height))

    def _center_offsets(self, scale: float) -> Tuple[float, float]:
        if self.source_img is None:
            return 0.0, 0.0
        cw, ch = self._canvas_size()
        dw = self.source_img.width * scale
        dh = self.source_img.height * scale
        return (cw - dw) / 2.0, (ch - dh) / 2.0

    def _clamp_offsets(self):
        if self.source_img is None:
            return
        cw, ch = self._canvas_size()
        scale = self._fit_scale() * self.zoom
        dw = self.source_img.width * scale
        dh = self.source_img.height * scale

        if self.offset_x is None or self.offset_y is None:
            self.offset_x, self.offset_y = self._center_offsets(scale)

        if dw <= cw:
            self.offset_x = (cw - dw) / 2.0
        else:
            self.offset_x = min(0.0, max(cw - dw, self.offset_x))

        if dh <= ch:
            self.offset_y = (ch - dh) / 2.0
        else:
            self.offset_y = min(0.0, max(ch - dh, self.offset_y))

    def _draw_grid_overlay(self, display: Image.Image, panel_scale: float, offset_x: float, offset_y: float):
        """Draw a 10 mm overlay grid without modifying the source image."""
        if not hasattr(self.app, "grid_var") or not self.app.grid_var.get():
            return
        if self.source_img is None or not getattr(self.app, "last_instances", None):
            return
        try:
            metadata = self.app.current_dimension_metadata()
            canvas = metadata.get("image_canvas_mm", {})
            ppm = float(metadata.get("pixels_per_mm", 0.0))
            if ppm <= 0:
                return
            min_x = float(canvas["min_x"])
            max_x = float(canvas["max_x"])
            min_y = float(canvas["min_y"])
            max_y = float(canvas["max_y"])
        except Exception:
            return

        draw = ImageDraw.Draw(display)
        cw, ch = display.size
        step_mm = 10.0
        light = (220, 220, 220)
        axis = (185, 185, 185)

        start_x = np.floor(min_x / step_mm) * step_mm
        x = start_x
        while x <= max_x + 1e-9:
            src_px = (x - min_x) * ppm
            dx = int(round(offset_x + src_px * panel_scale))
            if 0 <= dx <= cw:
                draw.line([(dx, 0), (dx, ch)], fill=axis if abs(x) < 1e-9 else light, width=1)
            x += step_mm

        start_y = np.floor(min_y / step_mm) * step_mm
        y = start_y
        while y <= max_y + 1e-9:
            src_py = (max_y - y) * ppm
            dy = int(round(offset_y + src_py * panel_scale))
            if 0 <= dy <= ch:
                draw.line([(0, dy), (cw, dy)], fill=axis if abs(y) < 1e-9 else light, width=1)
            y += step_mm

    def redraw(self):
        if self.source_img is None:
            self.canvas.delete("all")
            self.canvas.create_text(10, 10, anchor="nw", text="No image", fill="#555")
            return

        cw, ch = self._canvas_size()
        scale = self._fit_scale() * self.zoom
        self.display_scale = scale
        self._clamp_offsets()
        ox = float(self.offset_x or 0.0)
        oy = float(self.offset_y or 0.0)

        # Optimisation importante : on ne redimensionne jamais l'image complete en x10/x20.
        # Crop only the visible portion of the source image, then resize
        # this portion has the visible canvas size.
        src = self.source_img
        x0 = max(0.0, -ox / max(scale, 1e-9))
        y0 = max(0.0, -oy / max(scale, 1e-9))
        x1 = min(float(src.width), (cw - ox) / max(scale, 1e-9))
        y1 = min(float(src.height), (ch - oy) / max(scale, 1e-9))

        display = Image.new("RGB", (cw, ch), "white")
        if x1 > x0 and y1 > y0:
            crop_box = (
                int(max(0, np.floor(x0))),
                int(max(0, np.floor(y0))),
                int(min(src.width, np.ceil(x1))),
                int(min(src.height, np.ceil(y1))),
            )
            crop = src.crop(crop_box)
            dest_x = int(round(ox + crop_box[0] * scale))
            dest_y = int(round(oy + crop_box[1] * scale))
            dest_w = max(1, int(round(crop.width * scale)))
            dest_h = max(1, int(round(crop.height * scale)))
            crop = crop.resize((dest_w, dest_h), Image.Resampling.LANCZOS)
            display.paste(crop, (dest_x, dest_y))

        self._draw_grid_overlay(display, scale, ox, oy)

        self.photo = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

        if self.zoom > 1.01:
            self.canvas.create_text(
                8,
                8,
                anchor="nw",
                text=f"zoom x{self.zoom:.2f}",
                fill="#111",
            )

    def _schedule_redraw(self):
        if self._redraw_after_id:
            self.after_cancel(self._redraw_after_id)
        self._redraw_after_id = self.after(30, self.redraw)

    def _on_canvas_resize(self, _event=None):
        if self.source_img is not None:
            self._schedule_redraw()

    def _zoom_at(self, cursor_x: int, cursor_y: int, direction: int):
        if self.source_img is None:
            return

        old_scale = self._fit_scale() * self.zoom
        self._clamp_offsets()
        ox = self.offset_x or 0.0
        oy = self.offset_y or 0.0

        # Image coordinate under the cursor before the zoom change.
        src_x = (cursor_x - ox) / max(old_scale, 1e-6)
        src_y = (cursor_y - oy) / max(old_scale, 1e-6)

        factor = 1.18 if direction > 0 else 1.0 / 1.18
        self.zoom = max(1.0, min(30.0, self.zoom * factor))
        new_scale = self._fit_scale() * self.zoom

        if self.zoom <= 1.001:
            self.zoom = 1.0
            self.offset_x, self.offset_y = self._center_offsets(new_scale)
        else:
            # New position: the same source point remains under the cursor.
            self.offset_x = cursor_x - src_x * new_scale
            self.offset_y = cursor_y - src_y * new_scale

        self._clamp_offsets()
        self.redraw()

    def _on_mousewheel(self, event):
        direction = 1 if event.delta > 0 else -1
        self._zoom_at(event.x, event.y, direction)
        return "break"

    def _on_mousewheel_linux(self, event):
        direction = 1 if event.num == 4 else -1
        self._zoom_at(event.x, event.y, direction)
        return "break"

    def _on_pan_start(self, event):
        if self.source_img is None:
            return "break"
        self._clamp_offsets()
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.pan_start_offset_x = float(self.offset_x or 0.0)
        self.pan_start_offset_y = float(self.offset_y or 0.0)
        self.canvas.configure(cursor="fleur")
        try:
            self.canvas.focus_set()
            self.canvas.grab_set()
        except tk.TclError:
            pass
        return "break"

    def _on_pan_move(self, event):
        if not self.is_panning or self.source_img is None:
            return "break"
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.offset_x = self.pan_start_offset_x + dx
        self.offset_y = self.pan_start_offset_y + dy
        self._clamp_offsets()
        self.redraw()
        return "break"

    def _on_pan_end(self, _event=None):
        self.is_panning = False
        self.canvas.configure(cursor="crosshair")
        try:
            self.canvas.grab_release()
        except tk.TclError:
            pass
        return "break"

    def _on_leave(self, _event=None):
        # As soon as the mouse leaves the panel, return to the normal display.
        self.is_panning = False
        self.canvas.configure(cursor="crosshair")
        try:
            self.canvas.grab_release()
        except tk.TclError:
            pass
        if self.source_img is not None and (self.zoom != 1.0 or self.offset_x is not None or self.offset_y is not None):
            self.zoom = 1.0
            self.offset_x = None
            self.offset_y = None
            self.redraw()

    def save(self):
        self.app.save_image(self.key, self.filename)
