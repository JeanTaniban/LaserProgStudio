# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.mesh_ops import workmesh_to_polydata


def _diag(stage: str, owner: Any = None, ctx: Any = None, owner_tool: str = "", **payload: Any) -> None:
    try:
        from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

        record_projected_overlay_event(f"creator_ui.{stage}", owner=owner, ctx=ctx, owner_tool=str(owner_tool or ""), **payload)
    except Exception:
        pass


def _actor_prefix(owner_tool: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(owner_tool))
    return f"creator_ui_{safe}_"


def _state_attr(owner_tool: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(owner_tool))
    return f"_creator_ui_scene_state_{safe}"


def _actor_names_attr(owner_tool: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(owner_tool))
    return f"_creator_ui_actor_names_{safe}"


def _rgba_hex(color: tuple[float, float, float, float] | tuple[float, float, float] | Any) -> str:
    try:
        r, g, b = tuple(float(v) for v in tuple(color)[:3])
        return "#%02X%02X%02X" % (max(0, min(255, int(r * 255))), max(0, min(255, int(g * 255))), max(0, min(255, int(b * 255))))
    except Exception:
        return "#42A5F5"


def _clear_prefixed(owner: Any, prefix: str, *, render: bool = False) -> None:
    actors = getattr(owner, "gizmo_actors", None)
    plotter = getattr(owner, "plotter", None)
    if not isinstance(actors, dict):
        return
    for key, actor in list(actors.items()):
        if not str(key).startswith(prefix):
            continue
        try:
            if plotter is not None and actor is not None:
                plotter.remove_actor(actor, render=False)
        except Exception:
            pass
        actors.pop(key, None)
    if render and plotter is not None:
        try:
            plotter.render()
        except Exception:
            pass


def clear_creator_viewport_ui(owner: Any, owner_tool: str, *, render: bool = False) -> None:
    prefix = _actor_prefix(owner_tool)
    _diag("clear.start", owner=owner, owner_tool=owner_tool, prefix=prefix, render=bool(render))
    try:
        from laserprog_studio.application.tool_core_diag_scene import clear_tool_core_ui_scene

        clear_tool_core_ui_scene(
            owner,
            actor_prefix=prefix,
            state_attr=_state_attr(owner_tool),
            actor_names_attr=_actor_names_attr(owner_tool),
            render=False,
        )
    except Exception:
        pass
    _clear_prefixed(owner, prefix, render=render)
    _diag("clear.after_prefixed", owner=owner, owner_tool=owner_tool, prefix=prefix, render=bool(render))
    try:
        ctx = getattr(owner, "tool_context", None)
        overlay = getattr(ctx, "overlay", None)
        if overlay is not None:
            from laserprog_studio.tool_core.overlay import sync_qt_overlay_windows

            count = sync_qt_overlay_windows(owner, overlay)
            _diag("clear.qt_overlay_synced", owner=owner, ctx=ctx, owner_tool=owner_tool, count=count)
    except Exception as exc:
        _diag("clear.exception", owner=owner, owner_tool=owner_tool, error_type=type(exc).__name__, message=str(exc)[:300])


def sync_creator_overlay_windows(owner: Any, ctx: Any) -> int:
    """Synchronise the declarative Creator overlay layer with the Qt desktop UI."""

    try:
        overlay = getattr(ctx, "overlay", None)
        owner_tool = getattr(getattr(ctx, "workflow", None), "active_tool_id", "") or ""
        if overlay is None:
            _diag("qt_overlay.no_overlay", owner=owner, ctx=ctx, owner_tool=str(owner_tool))
            return 0
        from laserprog_studio.tool_core.overlay import sync_qt_overlay_windows

        count = int(sync_qt_overlay_windows(owner, overlay) or 0)
        _diag("qt_overlay.synced", owner=owner, ctx=ctx, owner_tool=str(owner_tool), count=count)
        return count
    except Exception as exc:
        _diag("qt_overlay.exception", owner=owner, ctx=ctx, error_type=type(exc).__name__, message=str(exc)[:300])
        return 0


def _line_mesh(points: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]], *, closed: bool = False):
    import numpy as np
    import pyvista as pv

    pts = list(points or [])
    if len(pts) < 2:
        return None
    if closed and pts[0] != pts[-1]:
        pts.append(pts[0])
    mesh = pv.PolyData(np.asarray(pts, dtype=float))
    mesh.lines = np.asarray([len(pts), *range(len(pts))], dtype=np.int64)
    try:
        return mesh.tube(radius=max(_span(pts) * 0.0025, 0.025), n_sides=10)
    except Exception:
        return mesh


def _span(points: list[tuple[float, float, float]]) -> float:
    if not points:
        return 1.0
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    zs = [float(p[2]) for p in points]
    return max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)


def _world_radius(owner: Any, center: tuple[float, float, float], radius_px: int) -> float:
    try:
        from laserprog_studio.utils.viewport import plotter_pixel_radius_to_world

        value = plotter_pixel_radius_to_world(getattr(owner, "plotter", None), center, radius_px)
        if value and value > 0:
            return float(value)
    except Exception:
        pass
    return max(float(radius_px) * 0.03, 0.18)


def _handle_mesh(owner: Any, handle: Any):
    import pyvista as pv

    center = tuple(float(v) for v in handle.position)
    radius = _world_radius(owner, center, int(getattr(handle, "radius_px", 13) or 13))
    kind = str(getattr(handle, "kind", ""))
    if "scale" in kind:
        try:
            return pv.Cube(center=center, x_length=radius * 1.8, y_length=radius * 1.8, z_length=radius * 1.8)
        except Exception:
            pass
    return pv.Sphere(radius=radius, center=center, theta_resolution=24, phi_resolution=12)


def _axis_for_handle(handle: Any) -> str:
    kind = str(getattr(handle, "kind", "")).lower()
    if "move" in kind:
        return "texmove"
    if "scale" in kind:
        return "texscale"
    if "rotate" in kind:
        return "texrot"
    return "tool"


def _preview_color(item: Any) -> str:
    payload = getattr(item, "payload", None)
    style = ""
    if isinstance(payload, dict):
        style = str(payload.get("line_style", ""))
    if "rotation" in style:
        return "#FFB23F"
    if "frame" in style:
        return "#46A6FF"
    return "#91E085"


def render_creator_viewport_ui(owner: Any, ctx: Any, owner_tool: str, *, render: bool = True, sync_overlays: bool = True) -> None:
    """Render Creator preview/gizmo declarations in the existing PyVista view.

    Creator tools now use the same persistent, style-aware painter as the Tool
    Core analysis scene.  This preserves the optimized motifs validated there:
    style guide rings/crosses/arrows, minimal-dot geometry, batched lines,
    labels and faces.  The overlay bridge below remains as a fallback
    for tests or very small host objects that only expose ``_add_overlay_mesh_actor``.
    """
    plotter = getattr(owner, "plotter", None)
    _diag("render.start", owner=owner, ctx=ctx, owner_tool=owner_tool, render=bool(render), sync_overlays=bool(sync_overlays), has_plotter=plotter is not None)
    if plotter is None:
        _diag("render.no_plotter", owner=owner, ctx=ctx, owner_tool=owner_tool)
        if sync_overlays:
            sync_creator_overlay_windows(owner, ctx)
        return
    prefix = _actor_prefix(owner_tool)
    if callable(getattr(plotter, "add_mesh", None)):
        try:
            from laserprog_studio.application.tool_core_diag_scene import ToolCoreDiagScenePainter

            result = ToolCoreDiagScenePainter(
                owner,
                owner_tool=owner_tool,
                actor_prefix=prefix,
                state_attr=_state_attr(owner_tool),
                actor_names_attr=_actor_names_attr(owner_tool),
                draw_guides_for_all=True,
            ).render_context(ctx, render=render)
            _diag("render.persistent_result", owner=owner, ctx=ctx, owner_tool=owner_tool, result=result, prefix=prefix)
            if sync_overlays:
                sync_creator_overlay_windows(owner, ctx)
            return
        except Exception as exc:
            _diag("render.persistent_exception", owner=owner, ctx=ctx, owner_tool=owner_tool, error_type=type(exc).__name__, message=str(exc)[:500], prefix=prefix)
            try:
                from laserprog_studio.studio_log import log_exception

                log_exception("creator_viewport_ui_style_painter")
            except Exception:
                pass
    _diag("render.fallback.begin", owner=owner, ctx=ctx, owner_tool=owner_tool, prefix=prefix)
    _clear_prefixed(owner, prefix, render=False)
    add_overlay = getattr(owner, "_add_overlay_mesh_actor", None)
    if not callable(add_overlay):
        _diag("render.fallback.no_add_overlay", owner=owner, ctx=ctx, owner_tool=owner_tool)
        if sync_overlays:
            sync_creator_overlay_windows(owner, ctx)
        return
    # Preview lines/meshes first, handles on top.
    for item in ctx.preview.items(owner_tool=owner_tool):
        try:
            if not getattr(item, "visible", True):
                continue
            kind = str(getattr(item, "kind", ""))
            if "text" in kind.lower():
                continue
            if "mesh" in kind.lower():
                payload = getattr(item, "payload", None)
                if payload is None:
                    continue
                mesh = workmesh_to_polydata(payload)
                meta = getattr(payload, "metadata", {}) or {}
                visual = meta.get("tool_core_preview") if isinstance(meta, dict) else None
                visual = visual if isinstance(visual, dict) else {}
                color = str(visual.get("color") or getattr(payload, "color", "#FFD54F") or "#FFD54F")
                add_overlay(mesh, key=f"{prefix}preview_{item.id}", axis=None, color=color, pickable=False)
                continue
            if not getattr(item, "points", ()): 
                continue
            mesh = _line_mesh(tuple(item.points), closed=("circle" in kind.lower() or "polyline" in kind.lower()))
            if mesh is None:
                continue
            add_overlay(mesh, key=f"{prefix}preview_{item.id}", axis=None, color=_preview_color(item), pickable=False)
        except Exception:
            continue
    for handle in ctx.gizmos.handles(owner_tool=owner_tool):
        try:
            if not getattr(handle, "visible", True):
                continue
            mesh = _handle_mesh(owner, handle)
            add_overlay(mesh, key=f"{prefix}handle_{handle.id}", axis=_axis_for_handle(handle), color=_rgba_hex(getattr(handle, "color", (0.2, 0.6, 1.0, 1.0))), pickable=True)
        except Exception:
            continue
    _diag("render.fallback.done", owner=owner, ctx=ctx, owner_tool=owner_tool, prefix=prefix)
    if sync_overlays:
        sync_creator_overlay_windows(owner, ctx)
    if render:
        try:
            plotter.render()
        except Exception as exc:
            _diag("render.fallback.render_exception", owner=owner, ctx=ctx, owner_tool=owner_tool, error_type=type(exc).__name__)


def fast_update_creator_viewport_ui(
    owner: Any,
    ctx: Any,
    owner_tool: str,
    *,
    handle_ids: tuple[str, ...] = (),
    preview_ids: tuple[str, ...] = (),
    render: bool = True,
) -> bool:
    """Fast live update for Creator UI drag events.

    The normal renderer is persistent but still sweeps all handles/previews to
    rebuild batched arrays.  Tool Core Analysis has a more specific drag path:
    move handle -> update dependent primitive -> mutate existing mesh ranges.
    This function exposes that path to Creator API tools, so a catalogue with
    many motifs does not repaint every motif on each mouse move.
    """

    plotter = getattr(owner, "plotter", None)
    _diag("fast_update.start", owner=owner, ctx=ctx, owner_tool=owner_tool, handle_ids=tuple(str(value) for value in handle_ids), preview_ids=tuple(str(value) for value in preview_ids), render=bool(render), has_plotter=plotter is not None)
    if plotter is None:
        _diag("fast_update.no_plotter", owner=owner, ctx=ctx, owner_tool=owner_tool)
        return False
    try:
        from laserprog_studio.application.tool_core_diag_scene import ToolCoreDiagScenePainter

        result = bool(
            ToolCoreDiagScenePainter(
                owner,
                owner_tool=owner_tool,
                actor_prefix=_actor_prefix(owner_tool),
                state_attr=_state_attr(owner_tool),
                actor_names_attr=_actor_names_attr(owner_tool),
                draw_guides_for_all=True,
            ).fast_update_context(
                ctx,
                handle_ids=tuple(str(value) for value in handle_ids),
                preview_ids=tuple(str(value) for value in preview_ids),
                render=render,
            )
        )
        _diag("fast_update.result", owner=owner, ctx=ctx, owner_tool=owner_tool, result=bool(result))
        return result
    except Exception as exc:
        _diag("fast_update.exception", owner=owner, ctx=ctx, owner_tool=owner_tool, error_type=type(exc).__name__, message=str(exc)[:500])
        try:
            from laserprog_studio.studio_log import log_exception

            log_exception("creator_viewport_ui_fast_update")
        except Exception:
            pass
        return False


__all__ = ["clear_creator_viewport_ui", "fast_update_creator_viewport_ui", "render_creator_viewport_ui", "sync_creator_overlay_windows"]
