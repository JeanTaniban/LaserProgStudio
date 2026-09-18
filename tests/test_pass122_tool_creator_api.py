# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_example_tool():
    path = Path("examples/tool_creator/minimal_point_line_tool.py")
    spec = importlib.util.spec_from_file_location("minimal_point_line_tool", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
from laserprog_studio.tool_api import ToolContext, actors, inspector, snap
from laserprog_studio.tool_core import ActorInteraction, ActorKind
from laserprog_studio.tool_core.snap import SnapSource


def _screen(point):
    return (float(point[0]), float(point[1]))


def test_pass122_public_tool_api_import_path_exposes_creator_blocks() -> None:
    import laserprog_studio.tool_api as tool_api

    assert tool_api.ToolContext is ToolContext
    assert hasattr(tool_api, "register_tool")
    assert hasattr(tool_api, "actors")
    assert hasattr(tool_api, "inspector")
    assert hasattr(tool_api, "snap")


def test_pass122_actor_factories_keep_interaction_contract_readable() -> None:
    fixed = actors.point("guide", (0, 20, 0), interaction="fixed")
    selectable = actors.line("edge", (0, 0, 0), (10, 0, 0), interaction="selectable")
    grabbable = actors.point("handle", (20, 0, 0), interaction="grabbable")

    assert fixed.kind == ActorKind.POINT
    assert fixed.interaction_mode == ActorInteraction.FIXED
    assert not fixed.selectable
    assert selectable.selectable and not selectable.grabbable
    assert grabbable.selectable and grabbable.grabbable

    ctx = ToolContext()
    for actor in (fixed, selectable, grabbable):
        ctx.selection.register_actor(actor)

    assert ctx.selection.select_at((0, 20), _screen) is None
    assert ctx.selection.select_at((10, 0), _screen).actor_id == "edge"
    assert ctx.selection.select_at((20, 0), _screen).actor_id == "handle"
    assert ctx.selection.begin_grab("handle", (20, 0)) == ("handle",)


def test_pass122_inspector_panel_is_declarative_validated_and_actionable() -> None:
    changed: list[tuple[str, float]] = []
    clicked: list[dict[str, object]] = []

    ctx = ToolContext()
    ctx.inspector.set_panel(
        inspector.Panel(
            id="demo",
            title="Demo Tool",
            sections=(
                inspector.Section(
                    "Geometry",
                    (
                        inspector.FloatField("width", "Width", default=20.0, min_value=1.0, max_value=100.0, on_change=lambda field, value: changed.append((field, value))),
                        inspector.IntField("count", "Count", default=2, min_value=1),
                        inspector.ChoiceField("mode", "Mode", default="a", choices=(("a", "A"), ("b", "B"))),
                    ),
                ),
                inspector.Section("Actions", (inspector.Button("apply", "Apply", on_click=lambda event: clicked.append(event.values)),)),
            ),
        )
    )

    assert ctx.inspector.values() == {"width": 20.0, "count": 2, "mode": "a"}
    assert ctx.inspector.update_value("width", 500.0) == 100.0
    assert changed == [("width", 100.0)]
    assert ctx.inspector.update_value("mode", "missing") == "a"
    event = ctx.inspector.trigger("apply")
    assert event.action_id == "apply"
    assert clicked == [{"width": 100.0, "count": 2, "mode": "a"}]


def test_pass122_scene_cache_collects_actors_and_feeds_smart_snap() -> None:
    ctx = ToolContext()
    ctx.selection.register_actor(actors.point("p1", (0, 0, 0), interaction="grabbable"))
    ctx.selection.register_actor(actors.line("l1", (10, 0, 0), (20, 0, 0), interaction="selectable"))

    ctx.scene_cache.rebuild(ctx, scope="snap")

    point_ids = {point.id for point in ctx.scene_cache.points()}
    segment_ids = {segment.id for segment in ctx.scene_cache.segments()}
    assert "p1" in point_ids
    assert "l1:0" in segment_ids

    result = ctx.snap.smart((0, 0, 0), (0, 0), ctx)
    assert result.snapped
    assert result.source == SnapSource.TOOL_ACTOR_POINT
    assert result.source_id == "p1"


def test_pass122_smart_snap_accepts_temporary_custom_targets() -> None:
    ctx = ToolContext()
    result = ctx.snap.smart(
        (9.9, 0.0, 0.0),
        (10.0, 0.0),
        ctx,
        extra_targets=[snap.point("custom.origin", (10.0, 0.0, 0.0), priority=5)],
    )

    assert result.snapped
    assert result.source_id == "custom.origin"
    assert result.position == (10.0, 0.0, 0.0)


def test_pass122_minimal_point_line_example_is_headless_and_complete() -> None:
    ctx = ToolContext()
    tool = _load_example_tool().create_tool()
    tool.on_open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.title == "Minimal Point Line"
    assert {actor.id for actor in ctx.selection.actors(owner_tool=tool.id)} == {"demo.p1", "demo.p2", "demo.edge"}

    result = tool.smart_snap(ctx, (25.0, 0.0, 0.0), (25.0, 0.0))
    assert result.snapped
    assert result.source_id == "demo.midpoint"

    ctx.inspector.update_value("length", 80.0)
    tool.reset(ctx)
    assert ctx.selection.actor("demo.p2").points[0] == (80.0, 0.0, 0.0)


def test_pass122_qt_inspector_adapter_imports_without_forcing_qt() -> None:
    from laserprog_studio.ui.inspector_panel_adapter import InspectorPanelQtAdapter

    assert hasattr(InspectorPanelQtAdapter, "create_widget")
