# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.snap import SnapKind, SnapResult, SnapSource
from laserprog_studio.tooling.cloth.free_space import resolve_cloth_point
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX, CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool
from laserprog_studio.tooling.ids import TOOL_CLOTH


def _context() -> ToolContext:
    ctx = ToolContext()
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    return ctx


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float, *, z: float = 0.0) -> bool:
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), world_pos=(x, y, z), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, z), button=MouseButton.LEFT)
    assert tool.on_event(press, ctx) is False
    return bool(tool.on_event(release, ctx))


def test_first_click_starts_polyline_without_a_plane_selection_stage() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    assert tool.interaction.stage.value == "opening"
    assert tool.session.edit_mode.value == "polyline"

    assert _click(tool, ctx, 12.0, 8.0)
    assert tool.interaction.stage.value == "draw"
    assert tool.session.edit_mode.value == "polyline"
    assert tool._drawing.pending_world_points == ((12.0, 8.0, 0.0),)
    assert all(step.id != "plane" for step in ctx.workflow.state.steps)


def test_free_space_resolver_prefers_scene_edge_smart_snap(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _context()

    def snapped(_self, _world, _screen, _ctx, **_kwargs):
        return SnapResult(
            True,
            (10.0, 20.0, 30.0),
            source=SnapSource.MESH_EDGE,
            source_id="mesh:edge:7",
            distance_px=2.0,
            kind=SnapKind.EDGE,
            label="Edge",
        )

    monkeypatch.setattr(type(ctx.snap), "smart", snapped)
    placement = resolve_cloth_point(
        ctx,
        (10.0, 20.0),
        document=ClothDocument(),
        owner_tool=TOOL_CLOTH,
        event_world_pos=(10.0, 20.0, 0.0),
    )
    assert placement.valid
    assert placement.position == (10.0, 20.0, 30.0)
    assert placement.source == SnapSource.MESH_EDGE.value
    assert placement.label == "Edge"


def test_line_tool_uses_real_surface_depth_without_locking_a_workplane() -> None:
    ctx = _context()
    world_by_screen = {
        (10.0, 10.0): (1.0, 2.0, 3.0),
        (30.0, 20.0): (8.0, 5.0, -4.0),
    }

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            world = world_by_screen.get(tuple(screen_pos))
            return None if world is None else {"kind": "face", "world_pos": world, "object_id": "reference"}

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_line", ctx)
    assert _click(tool, ctx, 10.0, 10.0)
    assert _click(tool, ctx, 30.0, 20.0)

    positions = {point.position for point in tool.session.document.points.values()}
    assert positions == {(1.0, 2.0, 3.0), (8.0, 5.0, -4.0)}
    assert len(tool.session.document.curves) == 1
    # Surface picks use their real 3D depth directly; no persistent workplane
    # is introduced into the Cloth document or UX.
    assert tool.interaction.active_plane is None
    assert tool.interaction.active_plane_label == "Free 3D"


def test_closed_non_planar_polyline_becomes_exact_planar_triangle_faces() -> None:
    ctx = _context()
    positions = {
        (0.0, 0.0): (0.0, 0.0, 0.0),
        (30.0, 0.0): (30.0, 0.0, 0.0),
        (30.0, 20.0): (30.0, 20.0, 10.0),
        (0.0, 20.0): (0.0, 20.0, -5.0),
    }

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            world = positions.get(tuple(screen_pos))
            return None if world is None else {"kind": "face", "world_pos": world, "object_id": "reference"}

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    for screen in positions:
        assert _click(tool, ctx, *screen)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}close_polyline", ctx)

    assert len(tool.session.document.patches) == 2
    assert all(len(patch.outer_curve_ids) == 3 for patch in tool.session.document.patches.values())
    assert len(tool.session.document.folds) == 1
    assert tool.can_apply(ctx)


def test_individual_lines_automatically_create_a_non_planar_textile_surface() -> None:
    ctx = _context()
    points = {
        (0.0, 0.0): (0.0, 0.0, 0.0),
        (20.0, 0.0): (20.0, 0.0, 0.0),
        (20.0, 20.0): (20.0, 20.0, 8.0),
        (0.0, 20.0): (0.0, 20.0, -4.0),
    }

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            world = points.get(tuple(screen_pos))
            return None if world is None else {"kind": "face", "world_pos": world, "object_id": "reference"}

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_line", ctx)
    loop = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    for first, second in zip(loop, loop[1:] + loop[:1]):
        assert _click(tool, ctx, *first)
        assert _click(tool, ctx, *second)

    # The fourth line closes the loop: Cloth creates the textile faces
    # immediately, including the internal diagonal/fold required by a non-planar
    # four-point loop. No Face-mode selection pass is needed.
    assert len(tool.session.document.patches) == 2
    assert len(tool.session.document.folds) == 1
    assert len(tool.session.document.curves) == 5
    assert tool.can_apply(ctx)


def test_command_deck_stays_compact_and_contains_no_workplane_controls() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert window is not None
    assert window.overlay_kind == "command_deck"
    assert len(window.fields) == 2
    assert all(len(str(field.value)) <= 76 for field in window.fields)
    ids = {button.id for button in window.buttons}
    assert not any("plane" in value for value in ids)
    assert f"{CLOTH_ACTION_PREFIX}draw_create_from_mesh" in ids
    assert f"{CLOTH_ACTION_PREFIX}draw_join_textile_faces" in ids
    assert f"{CLOTH_ACTION_PREFIX}draw_polyline" in ids
