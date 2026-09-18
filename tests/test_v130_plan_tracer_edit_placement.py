from __future__ import annotations

import math

from laserprog_studio.tooling.plan_trace_2d.editable_source import (
    PLACEMENT_REFERENCE_KEY,
    editable_source_from_mesh,
    mesh_bounds_3d,
)
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _EditableScene:
    def __init__(self) -> None:
        self.meshes = []
        self.normal = (0.0, 0.0, 1.0)

    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        if self.meshes:
            mesh = self.meshes[0]
            return PickResult(
                "face",
                screen_pos=screen_pos,
                world_pos=(float(x), float(y), 0.0),
                object_id=getattr(mesh, "mesh_id", ""),
                object_index=0,
                normal=self.normal,
            )
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 0.0),
            object_id="seed_face",
            object_index=0,
            normal=self.normal,
        )


class _BasicOwner:
    def __init__(self) -> None:
        self.align_calls = []
        self.rebuild_calls = 0

    def align_camera_to_plan_surface(self, *, origin, normal, up_axis=None) -> None:
        self.align_calls.append({"origin": origin, "normal": normal, "up_axis": up_axis})

    def rebuild_scene(self, *_, **__) -> None:
        self.rebuild_calls += 1


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _EditableScene()
    ctx.owner = _BasicOwner()
    ctx.pick.bind_context(ctx)
    ctx.document.bind(ctx.scene)
    return ctx


def _press(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> bool:
    event = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT)
    return bool(tool.on_event(event, ctx))


def _draw_rectangle_volume(ctx: ToolContext):
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    tool._services.mode_state._set_active_tool(ctx, "rectangle", reason="test", render=False)
    assert _press(tool, ctx, 10.0, 10.0)
    assert _press(tool, ctx, 60.0, 40.0)
    assert tool._state.sketch.faces
    assert tool.on_apply(ctx) is True
    return ctx.scene.meshes[0]


class _FocusOwner:
    def __init__(self) -> None:
        self.align_calls: list[dict] = []
        self.rebuild_calls = 0

    def align_camera_to_plan_surface(self, *, origin, normal, up_axis=None, focus_bounds=None) -> None:
        self.align_calls.append(
            {
                "origin": tuple(float(value) for value in origin),
                "normal": tuple(float(value) for value in normal),
                "up_axis": None if up_axis is None else tuple(float(value) for value in up_axis),
                "focus_bounds": None if focus_bounds is None else tuple(float(value) for value in focus_bounds),
            }
        )

    def rebuild_scene(self, *_, **__) -> None:
        self.rebuild_calls += 1


def _assert_bounds_close(actual, expected, tol: float = 1.0e-6) -> None:
    assert actual is not None and expected is not None
    assert len(actual) == len(expected) == 6
    for a, b in zip(actual, expected):
        assert math.isclose(float(a), float(b), abs_tol=tol), (actual, expected)


def _sorted_vertices(mesh) -> list[tuple[float, float, float]]:
    return sorted(tuple(round(float(value), 7) for value in point[:3]) for point in mesh.vertices)


def test_v130_editable_source_stores_compact_placement_landmarks() -> None:
    ctx = _ctx()
    mesh = _draw_rectangle_volume(ctx)
    source = editable_source_from_mesh(mesh)

    assert source is not None
    placement = source.get(PLACEMENT_REFERENCE_KEY)
    assert isinstance(placement, dict)
    assert placement["vertex_count"] == len(mesh.vertices)
    assert 4 <= len(placement["indices"]) <= 24
    assert len(placement["indices"]) == len(placement["positions"])
    assert placement["bounds"] == list(mesh_bounds_3d(mesh)) or tuple(placement["bounds"]) == mesh_bounds_3d(mesh)


def test_v130_translated_plan_tracer_edits_and_applies_at_current_world_position() -> None:
    ctx = _ctx()
    ctx.owner = _FocusOwner()
    original = _draw_rectangle_volume(ctx)
    object_id = original.mesh_id
    delta = (128.0, -47.5, 19.0)
    original.vertices = [
        (float(x) + delta[0], float(y) + delta[1], float(z) + delta[2])
        for x, y, z in original.vertices
    ]
    expected_bounds = mesh_bounds_3d(original)
    ctx.owner.align_calls.clear()

    editor = PlanTrace2DCreatorTool()
    editor.on_open(ctx)
    assert _press(editor, ctx, 3.0, 3.0)

    assert editor._state.editing_source_object_id == object_id
    assert editor._state.editing_source_placement_mode == "affine"
    assert editor._state.anchor_world is not None
    assert math.isclose(editor._state.anchor_world[0], delta[0], abs_tol=1.0e-6)
    assert math.isclose(editor._state.anchor_world[1], delta[1], abs_tol=1.0e-6)
    assert math.isclose(editor._state.plane.depth, delta[2], abs_tol=1.0e-6)
    assert ctx.owner.align_calls
    _assert_bounds_close(ctx.owner.align_calls[-1]["focus_bounds"], expected_bounds)

    assert editor.on_apply(ctx) is True
    assert len(ctx.scene.meshes) == 1
    replacement = ctx.scene.meshes[0]
    assert replacement.mesh_id == object_id
    _assert_bounds_close(mesh_bounds_3d(replacement), expected_bounds)


def test_v130_legacy_source_without_landmarks_preserves_translation() -> None:
    ctx = _ctx()
    original = _draw_rectangle_volume(ctx)
    source = editable_source_from_mesh(original)
    assert source is not None
    source.pop(PLACEMENT_REFERENCE_KEY, None)

    delta = (73.0, -26.0, 11.5)
    original.vertices = [
        (float(x) + delta[0], float(y) + delta[1], float(z) + delta[2])
        for x, y, z in original.vertices
    ]
    expected_bounds = mesh_bounds_3d(original)

    editor = PlanTrace2DCreatorTool()
    editor.on_open(ctx)
    assert _press(editor, ctx, 3.0, 3.0)
    assert editor._state.editing_source_placement_mode == "affine"
    assert editor._state.editing_source_placement_reference == "legacy_rebuild"
    assert editor.on_apply(ctx) is True
    _assert_bounds_close(mesh_bounds_3d(ctx.scene.meshes[0]), expected_bounds)


def test_v130_rotated_and_scaled_plan_tracer_roundtrips_without_position_reset() -> None:
    ctx = _ctx()
    original = _draw_rectangle_volume(ctx)
    original_id = original.mesh_id
    source_vertices = list(original.vertices)

    angle_x = math.radians(31.0)
    angle_z = math.radians(-24.0)
    cx, sx = math.cos(angle_x), math.sin(angle_x)
    cz, sz = math.cos(angle_z), math.sin(angle_z)
    pivot = (31.25, 18.75, 1.5)
    translation = (54.0, -16.0, 27.0)
    scale = (1.35, 0.8, 1.7)

    def transform(point):
        x = (float(point[0]) - pivot[0]) * scale[0]
        y = (float(point[1]) - pivot[1]) * scale[1]
        z = (float(point[2]) - pivot[2]) * scale[2]
        # X rotation, then Z rotation.
        y2 = y * cx - z * sx
        z2 = y * sx + z * cx
        x3 = x * cz - y2 * sz
        y3 = x * sz + y2 * cz
        return (
            x3 + pivot[0] + translation[0],
            y3 + pivot[1] + translation[1],
            z2 + pivot[2] + translation[2],
        )

    original.vertices = [transform(point) for point in source_vertices]
    expected_vertices = _sorted_vertices(original)
    expected_bounds = mesh_bounds_3d(original)

    editor = PlanTrace2DCreatorTool()
    editor.on_open(ctx)
    assert _press(editor, ctx, 3.0, 3.0)
    assert editor._state.editing_source_placement_mode == "affine"
    assert math.isclose(editor._state.extrusion_depth, 3.0 * scale[2], rel_tol=1.0e-6)
    assert editor.on_apply(ctx) is True

    replacement = ctx.scene.meshes[0]
    assert replacement.mesh_id == original_id
    _assert_bounds_close(mesh_bounds_3d(replacement), expected_bounds, tol=1.0e-5)
    actual_vertices = _sorted_vertices(replacement)
    assert len(actual_vertices) == len(expected_vertices)
    for actual, expected in zip(actual_vertices, expected_vertices):
        for a, b in zip(actual, expected):
            assert math.isclose(a, b, abs_tol=2.0e-7), (actual, expected)


def test_v130_editing_translated_sketch_changes_geometry_without_returning_to_origin() -> None:
    ctx = _ctx()
    original = _draw_rectangle_volume(ctx)
    delta = (210.0, 85.0, 14.0)
    original.vertices = [
        (float(x) + delta[0], float(y) + delta[1], float(z) + delta[2])
        for x, y, z in original.vertices
    ]
    before = mesh_bounds_3d(original)
    assert before is not None

    editor = PlanTrace2DCreatorTool()
    editor.on_open(ctx)
    assert _press(editor, ctx, 3.0, 3.0)

    # Simulate a real edit in the rebased sketch: move the complete profile by
    # 7 mm along its current local U axis before applying it again.
    for point in editor._state.sketch.points.values():
        point.position = (float(point.position[0]) + 7.0, float(point.position[1]))
    editor._state.sketch.compile()

    assert editor.on_apply(ctx) is True
    after = mesh_bounds_3d(ctx.scene.meshes[0])
    assert after is not None
    assert math.isclose(after[0], before[0] + 7.0, abs_tol=1.0e-6)
    assert math.isclose(after[1], before[1] + 7.0, abs_tol=1.0e-6)
    assert math.isclose(after[2], before[2], abs_tol=1.0e-6)
    assert math.isclose(after[3], before[3], abs_tol=1.0e-6)
    assert after[0] > 150.0  # Explicit regression guard against a reset near origin.
