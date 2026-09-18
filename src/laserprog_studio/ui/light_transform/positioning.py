# -*- coding: utf-8 -*-
from __future__ import annotations

from ..._window_deps import *



class LightTransformOverlayPositioningLayer:
    """Focused Light UI overlay behavior extracted from the original mixin."""

    def _schedule_light_overlay_position(self, *, force: bool = False) -> None:
        """Coalesce resize-driven overlay positioning.

        Window resize can emit dozens of QEvent.Resize events.  Recomputing and
        raising the Qt overlay on each one is visible as stutter.  Optimized mode
        schedules one geometry update after the resize burst.
        """
        try:
            if force or str(getattr(self, "_performance_mode", "optimized")) == "debug":
                self._position_light_transform_overlay(force=force)
                return
            if bool(getattr(self, "_light_overlay_position_pending", False)):
                return
            self._light_overlay_position_pending = True
            QTimer.singleShot(50, self._run_scheduled_light_overlay_position)
        except Exception:
            self._position_light_transform_overlay(force=force)

    def _run_scheduled_light_overlay_position(self) -> None:
        try:
            self._light_overlay_position_pending = False
            self._position_light_transform_overlay(force=False)
        except Exception:
            log_exception("run_scheduled_light_overlay_position")

    def _invalidate_light_overlay_backing(self, rect=None) -> None:
        """Refresh the overlay/viewport without alpha-paint accumulation.

        The compact controls are now a floating tool window, not a transparent
        QWidget painted inside the VTK surface.  For floating overlays the OS
        compositor removes old pixels when the window moves/hides, so a broad
        viewport update is safer than trying to repaint a stale child-geometry
        rectangle in the OpenGL widget.
        """
        try:
            overlay = getattr(self, "light_transform_overlay", None)
            area = getattr(self, "plotter", None)
            if overlay is None or area is None:
                return
            if bool(overlay.isWindow()):
                try:
                    area.update()
                except Exception:
                    pass
                try:
                    overlay.update()
                except Exception:
                    pass
                return
            target = rect if rect is not None else overlay.geometry()
            try:
                target = target.adjusted(-4, -4, 4, 4)
            except Exception:
                pass
            try:
                area.update(target)
            except TypeError:
                area.update()
            try:
                overlay.update()
            except Exception:
                pass
        except Exception:
            pass

    def _position_light_transform_overlay(self, *, force: bool = False) -> None:
        overlay = getattr(self, "light_transform_overlay", None)
        area = getattr(self, "plotter", None)
        if overlay is None or area is None:
            return
        try:
            from PySide6.QtCore import QPoint, QRect

            margin = 18
            aw = max(int(area.width()), 1)
            ah = max(int(area.height()), 1)
            hint = overlay.sizeHint()
            # Prefer a stable width so the fixed left icon cluster does not move
            # when the right side changes between position/rotation/scale.
            preferred_width = int(getattr(self, "_light_overlay_preferred_width", 760))
            width = min(max(preferred_width, int(hint.width()), 620), max(aw - 2 * margin, 300))
            height = max(int(hint.height()), 60)
            x = max((aw - width) // 2, margin)
            y = max(ah - height - margin, margin)
            if bool(overlay.isWindow()):
                top_left = area.mapToGlobal(QPoint(int(x), int(y)))
                target_geometry = QRect(int(top_left.x()), int(top_left.y()), int(width), int(height))
                geometry_signature = (aw, ah, int(hint.width()), int(hint.height()), int(top_left.x()), int(top_left.y()), width, height, "floating")
            else:
                target_geometry = QRect(int(x), int(y), int(width), int(height))
                geometry_signature = (aw, ah, int(hint.width()), int(hint.height()), x, y, width, height, "child")
            if force or getattr(self, "_light_overlay_geometry_signature", None) != geometry_signature:
                old_geometry = overlay.geometry()
                overlay.setGeometry(target_geometry)
                self._light_overlay_geometry_signature = geometry_signature
                if not bool(overlay.isWindow()):
                    try:
                        self._invalidate_light_overlay_backing(old_geometry.united(overlay.geometry()))
                    except Exception:
                        self._invalidate_light_overlay_backing()
                else:
                    overlay.update()
            overlay.raise_()
        except Exception:
            log_exception("position_light_transform_overlay")

    def _set_light_transform_overlay_hover(self, hovered: bool) -> None:
        if bool(getattr(self, "_light_overlay_is_hovered", False)) == bool(hovered):
            return
        self._light_overlay_is_hovered = bool(hovered)
        overlay = getattr(self, "light_transform_overlay", None)
        if overlay is None:
            return
        # Qt stylesheets handle :hover, but repolishing makes the opacity change
        # immediate on all supported Qt/PySide versions.
        try:
            overlay.style().unpolish(overlay)
            overlay.style().polish(overlay)
            overlay.update()
        except Exception:
            pass
