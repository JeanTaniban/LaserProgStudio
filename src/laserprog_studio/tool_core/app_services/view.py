"""Creator-facing viewport/camera facade.

The historical application still owns concrete Qt/PyVista camera helpers.  This
facade is the public Creator API boundary: tools ask for view actions here and
never reach into the main window directly.
"""
from __future__ import annotations

from typing import Any, Iterable

from laserprog_studio.mesh_ops import mesh_bounds, scene_bounds


class ViewFacade:
    """Camera and render helpers exposed as ``ctx.view``.

    The methods are intentionally tolerant: in headless tests they degrade to
    render requests instead of requiring a real Qt window.
    """

    def __init__(self) -> None:
        self._ctx: Any | None = None

    def bind_context(self, ctx: Any) -> "ViewFacade":
        self._ctx = ctx
        return self

    def focus_index(self, index: int, *, label: str | None = None) -> bool:
        ctx = self._require_ctx()
        owner = getattr(ctx, "owner", None)
        focus = getattr(owner, "focus_camera_on_index", None)
        if callable(focus):
            try:
                focus(int(index))
                return True
            except Exception:
                pass
        try:
            obj = ctx.document.objects()[int(index)]
            return self.focus_bounds(mesh_bounds(obj.mesh), label=label or f"part {int(index):02d}")
        except Exception:
            self.refresh(full=True)
            return False

    def focus_bounds(self, bounds: tuple[float, float, float, float, float, float], *, label: str = "zone") -> bool:
        ctx = self._require_ctx()
        owner = getattr(ctx, "owner", None)
        focus = getattr(owner, "focus_camera_on_bounds", None)
        if callable(focus):
            try:
                focus(tuple(float(v) for v in bounds), str(label))
                return True
            except Exception:
                pass
        self.refresh(full=True)
        return False

    def focus_meshes(self, meshes: Iterable[Any], *, label: str = "meshes") -> bool:
        mesh_list = list(meshes)
        if not mesh_list:
            self.refresh(full=True)
            return False
        return self.focus_bounds(scene_bounds(mesh_list), label=label)

    def focus_scene(self, *, include_preview: bool = True, label: str = "full scene") -> bool:
        ctx = self._require_ctx()
        try:
            meshes = list(ctx.document.meshes(include_preview=include_preview))
        except Exception:
            meshes = []
        return self.focus_meshes(meshes, label=label)


    def set_display_mode(self, mode: str, *, render: bool = False) -> bool:
        """Request a display-mode switch through the Creator API boundary.

        Texture and material tools need this without reaching directly into the
        historical Qt widgets. In headless tests this degrades to a render
        request and returns whether a concrete host state was changed.
        """

        ctx = self._require_ctx()
        owner = getattr(ctx, "owner", None)
        mode_id = str(mode or "").strip()
        changed = False
        if owner is not None:
            renderer = getattr(owner, "scene_renderer", None)
            set_mode = getattr(renderer, "set_display_mode", None)
            if callable(set_mode):
                try:
                    set_mode(mode_id, render=False)
                    changed = True
                except Exception:
                    pass
            combo = getattr(owner, "display_mode_combo", None)
            if combo is not None and hasattr(combo, "findData") and hasattr(combo, "setCurrentIndex"):
                try:
                    index = combo.findData(mode_id)
                    if int(index) >= 0:
                        combo.setCurrentIndex(index)
                        changed = True
                except Exception:
                    pass
            render_state = getattr(owner, "render_state", None)
            if render_state is not None:
                try:
                    setattr(render_state, "display_mode", mode_id)
                    changed = True
                except Exception:
                    pass
        self.refresh(full=bool(render))
        return changed

    def refresh(self, *, full: bool = True) -> None:
        ctx = self._require_ctx()
        if full:
            ctx.request_full_render()
        else:
            ctx.request_light_render()

    def _require_ctx(self) -> Any:
        if self._ctx is None:
            raise RuntimeError("ViewFacade is not bound to a ToolContext.")
        return self._ctx


__all__ = ["ViewFacade"]
