# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.application.creator_viewport_ui import clear_creator_viewport_ui, render_creator_viewport_ui
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.gizmos import GizmoHandle


class _RealisticPlotter:
    def __init__(self) -> None:
        self.actors = {}
        self.render_count = 0
        self.removed: list[tuple[str, bool]] = []

    def add_mesh(self, *args, **kwargs):  # pragma: no cover - monkeypatched painter prevents use
        actor = SimpleNamespace(args=args, kwargs=kwargs)
        name = kwargs.get("name", f"actor_{len(self.actors)}")
        self.actors[name] = actor
        return actor

    def remove_actor(self, name, render: bool = False):
        self.removed.append((str(name), bool(render)))
        self.actors.pop(str(name), None)

    def render(self):
        self.render_count += 1


def test_creator_viewport_uses_core_analysis_style_painter_for_real_plotters(monkeypatch) -> None:
    import laserprog_studio.application.tool_core_diag_scene as scene

    captured: dict[str, object] = {}

    class FakePainter:
        def __init__(self, owner, **kwargs):
            captured["owner"] = owner
            captured.update(kwargs)

        def render_context(self, ctx, *, render: bool = True):
            captured["ctx"] = ctx
            captured["render"] = render
            return {"status": "rendered_persistent"}

    monkeypatch.setattr(scene, "ToolCoreDiagScenePainter", FakePainter)

    owner = SimpleNamespace(plotter=_RealisticPlotter(), overlay_calls=[])
    ctx = ToolContext(owner=owner)
    ctx.gizmos.create_handle(
        GizmoHandle(
            id="style:target",
            owner_tool="gizmo_catalog",
            position=(0.0, 0.0, 0.0),
            radius_px=12,
            color=(0.0, 0.45, 0.82, 1.0),
            kind="catalog:point_styles:target",
            style_id="target",
            selectable=True,
        )
    )

    render_creator_viewport_ui(owner, ctx, "gizmo_catalog", render=True)

    assert captured["owner"] is owner
    assert captured["ctx"] is ctx
    assert captured["owner_tool"] == "gizmo_catalog"
    assert str(captured["actor_prefix"]).startswith("creator_ui_gizmo_catalog_")
    assert captured["draw_guides_for_all"] is True
    assert captured["render"] is True


def test_creator_viewport_clear_removes_generic_core_analysis_painter_actors() -> None:
    owner = SimpleNamespace(plotter=_RealisticPlotter(), gizmo_actors={})
    owner.plotter.actors["creator_ui_gizmo_catalog_handles_target_grabbable"] = object()
    clear_creator_viewport_ui(owner, "gizmo_catalog", render=True)

    assert owner.plotter.removed
    assert owner.plotter.render_count == 1
