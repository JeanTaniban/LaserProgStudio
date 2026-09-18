# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from pathlib import Path

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tool_core.projected_drawing import ProjectedSegmentBatch
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.patterns import _PATTERN_PREVIEW_BATCH_ID
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / "src" / "laserprog_studio" / "tooling"


def _attribute_chain(node: ast.Attribute) -> str:
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _plane() -> LockedPlaneSpec:
    return LockedPlaneSpec(
        view=FixedPlanarView.TOP,
        normal=(0.0, 0.0, 1.0),
        u_axis=(1.0, 0.0, 0.0),
        v_axis=(0.0, 1.0, 0.0),
        depth=0.0,
    )


def _rectangle_sketch(width: float = 160.0, height: float = 100.0) -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0)).id
    p2 = sketch.add_point((width, 0.0)).id
    p3 = sketch.add_point((width, height)).id
    p4 = sketch.add_point((0.0, height)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )
    return sketch


def test_builtin_tools_do_not_call_legacy_viewport_gizmo_api_directly() -> None:
    forbidden: list[tuple[str, int, str]] = []
    for path in sorted(TOOLING.rglob("*.py")):
        if path.name == "creator_runtime.py":
            # Compatibility facade kept for external CreatorTool subclasses.
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            chain = _attribute_chain(node)
            if chain.startswith(("ctx.preview", "ctx.gizmos", "ctx.actor_registry")):
                if chain.startswith("ctx.preview_session"):
                    continue
                forbidden.append((str(path.relative_to(ROOT)), int(node.lineno), chain))
    assert forbidden == []


def test_plan_tracer_motif_preview_linework_uses_projected_drawing_batch() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _rectangle_sketch()
    tool._state.pattern_face_id = next(iter(tool._state.sketch.faces))

    ok = tool._services.patterns.generate(
        ctx,
        kind="square",
        cell_size=36.0,
        wall=5.0,
        margin=3.0,
        preview_only=True,
        record_history=False,
        max_segments=2000,
    )

    assert ok is True
    registry = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE)
    batch = registry.get(_PATTERN_PREVIEW_BATCH_ID)
    assert isinstance(batch, ProjectedSegmentBatch)
    assert batch.segments
    assert len(batch.item_ids) == len(batch.segments)
    assert not ctx.preview.items(owner_tool=TOOL_PLAN_TRACE)
    assert not ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE)

    tool._services.patterns._clear_preview_linework(ctx)
    assert registry.get(_PATTERN_PREVIEW_BATCH_ID) is None


def test_texture_projection_tool_uses_public_projected_drawing_api_only() -> None:
    texture_paths = (
        TOOLING / "texture_projection_creator_tool.py",
        TOOLING / "_texture_projection_projector.py",
    )
    forbidden: list[tuple[str, int, str]] = []
    for path in texture_paths:
        source = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(source.splitlines(), start=1):
            if "laserprog_studio.tool_core" in line:
                forbidden.append((str(path.relative_to(ROOT)), line_no, line.strip()))
    assert forbidden == []


def test_texture_projection_camera_sizing_uses_public_projected_drawing_helper() -> None:
    source = (TOOLING / "_texture_projection_projector.py").read_text(encoding="utf-8")
    assert "draw2d.world_radius_for_screen_pixels" in source
    assert "plotter_pixel_radius_to_world" not in source

    from laserprog_studio.tool_api import projected_drawing as draw2d

    radius = draw2d.world_radius_for_screen_pixels(
        None,
        (0.0, 0.0, 0.0),
        82.0,
        fallback_world_per_px=0.05,
    )
    assert radius == 4.1000000000000005


def test_vent_generator_snap_uses_public_tool_api_only() -> None:
    vent_paths = (
        TOOLING / "vent_generator_tool.py",
        TOOLING / "vent_generator" / "snap.py",
    )
    forbidden: list[tuple[str, int, str]] = []
    for path in vent_paths:
        source = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(source.splitlines(), start=1):
            if "laserprog_studio.tool_core.snap" in line:
                forbidden.append((str(path.relative_to(ROOT)), line_no, line.strip()))
    assert forbidden == []


def test_vent_generator_alignment_targets_are_declared_through_public_snap_api() -> None:
    source = (TOOLING / "vent_generator" / "snap.py").read_text(encoding="utf-8")
    assert "from laserprog_studio.tool_api import snap as snap_api" in source
    assert "snap_api.segment(" in source
    assert "SnapTarget.segment(" not in source
