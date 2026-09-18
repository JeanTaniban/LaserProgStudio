# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .display_modes import get_display_mode
from .materials import actor_style_for_mesh, apply_actor_style
from .textures import apply_texture_to_actor
from .material_scene import renderer_actor_count
from .render_scheduler import request_render_for, render_now_for


@dataclass(slots=True)
class SceneRenderer:
    """Thin rendering facade around the current PyVista-backed main window.

    Existing controllers still call ``plotter`` directly in many places. This
    bridge gives future tools/modifiers a small, stable rendering contract while
    the old direct calls are migrated progressively.
    """

    owner: Any

    def render(self) -> None:
        request_render_for(self.owner, reason="scene_renderer.render")

    def render_now(self) -> None:
        render_now_for(self.owner, reason="scene_renderer.render_now")

    def rebuild_scene(self, *, keep_camera: bool = True) -> None:
        rebuild = getattr(self.owner, "rebuild_scene", None)
        if callable(rebuild):
            rebuild(keep_camera=keep_camera)

    def refresh_selection_style(self, *, render: bool = False) -> None:
        refresh = getattr(self.owner, "refresh_actor_styles", None)
        if callable(refresh):
            refresh(render=render)

    def refresh_transform_gizmo(self, *, render: bool = False) -> None:
        update = getattr(self.owner, "update_gizmo", None)
        if callable(update):
            update(render=render)

    def clear_tool_overlays(self, *, render: bool = False) -> None:
        for name in ("_clear_gizmo_actors", "_clear_split_plane_actor"):
            fn = getattr(self.owner, name, None)
            if not callable(fn):
                continue
            try:
                fn(render=render)
            except TypeError:
                fn()

    def set_display_mode(self, mode_id: str, *, render: bool = True) -> str:
        spec = get_display_mode(mode_id)
        render_state = getattr(self.owner, "render_state", None)
        old_mode = getattr(render_state, "display_mode", None) if render_state is not None else None
        if render_state is not None:
            render_state.display_mode = spec.id
        logger = getattr(self.owner, "ui_log", None)
        if callable(logger):
            logger(f"[DISPLAY_PIPELINE] set_display_mode old={old_mode} new={spec.id} props={renderer_actor_count(getattr(self.owner, 'plotter', None))}")
        # Keep display flags in sync until scene rebuild is fully owned
        # by this facade. Wireframe defaults to edged surface; other modes keep
        # the current user edge toggle instead of forcing it off.
        try:
            self.owner.show_edges = bool(spec.default_show_edges)
            if hasattr(self.owner, "edges_check"):
                self.owner.edges_check.blockSignals(True)
                self.owner.edges_check.setChecked(bool(spec.default_show_edges))
                self.owner.edges_check.blockSignals(False)
            if render_state is not None:
                render_state.show_edges_overlay = bool(spec.default_show_edges)
        except Exception:
            pass
        self.apply_display_mode(render=render)
        return spec.id

    def apply_display_mode(self, *, render: bool = False) -> None:
        meshes_fn = getattr(self.owner, "current_meshes", None)
        if not callable(meshes_fn):
            return
        try:
            meshes = list(meshes_fn())
        except Exception:
            return
        actors = getattr(self.owner, "actors_by_index", {}) or {}
        render_state = getattr(self.owner, "render_state", None)
        mode = getattr(render_state, "display_mode", "wireframe")
        edge_toggle = bool(getattr(render_state, "show_edges_overlay", getattr(self.owner, "show_edges", True)))
        for index, actor in list(actors.items()):
            if not (0 <= int(index) < len(meshes)):
                continue
            try:
                mesh = meshes[int(index)]
                apply_actor_style(actor, actor_style_for_mesh(mesh, mode, show_edges=edge_toggle))
                if str(mode) == "material":
                    apply_texture_to_actor(self.owner, actor, mesh, reason="scene_renderer.apply_display_mode")
            except Exception:
                # Rendering style failures must not break the editor; detailed
                # renderer diagnostics are handled by the owner logger when available.
                logger = getattr(self.owner, "ui_log", None)
                if callable(logger):
                    logger(f"[RENDER] Could not apply display mode to actor {index}")
        sync_material = getattr(self.owner, "_sync_material_scene_rendering", None)
        if callable(sync_material):
            sync_material(render=False)
        logger = getattr(self.owner, "ui_log", None)
        if callable(logger):
            logger(f"[DISPLAY_PIPELINE] apply_display_mode mode={mode} edges={edge_toggle} props={renderer_actor_count(getattr(self.owner, 'plotter', None))}")
        if render:
            self.render()
