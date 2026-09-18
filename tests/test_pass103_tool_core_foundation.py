# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core import FunctionCommand, ToolContext
from laserprog_studio.tool_core.events import MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_core.gizmos import GizmoHandle, GizmoManager, MemoryGizmoBackend
from laserprog_studio.tool_core.overlay import ToolButtonSpec, ToolPanelSpec
from laserprog_studio.tool_core.sketch import FaceSolveOptions, FaceSolver, SketchDocument
from laserprog_studio.tool_core.snap import PointSnapProvider, SnapManager, SnapSource
from laserprog_studio.tool_core.tools import ToolBase, ToolModeBase


def test_pass103_tool_core_package_layers_exist_and_stay_short() -> None:
    root = Path("src/laserprog_studio/tool_core")
    expected = [
        "context.py",
        "tools.py",
        "events.py",
        "selection.py",
        "commands.py",
        "gizmos/manager.py",
        "snap/manager.py",
        "preview/manager.py",
        "overlay/manager.py",
        "rendering/adapter.py",
        "sketch/document.py",
        "sketch/face_solver.py",
        "perf/profiler.py",
    ]
    for rel_path in expected:
        assert (root / rel_path).exists(), rel_path
        assert len(str(root / rel_path)) < 100


def test_pass103_gizmo_manager_updates_positions_without_recreating_handles() -> None:
    backend = MemoryGizmoBackend()
    manager = GizmoManager(backend)
    manager.create_handle(GizmoHandle("p1", "plan", (0.0, 0.0, 0.0)))

    manager.begin_interactive_update()
    changed = manager.update_positions_only({"p1": (10.0, 2.0, 0.0)})
    manager.end_interactive_update()

    assert changed == 1
    assert backend.created == 1
    assert backend.position_updates == 1
    assert backend.light_renders == 1
    assert backend.full_renders == 1
    assert backend.handles["p1"].position == (10.0, 2.0, 0.0)


def test_pass103_snap_manager_prioritizes_smart_snap_over_grid_snap() -> None:
    ctx = ToolContext()
    ctx.sketch.add_point((10.0, 10.0), point_id="corner")
    snap = SnapManager(smart_enabled=True, grid_enabled=True)
    snap.grid_provider.grid_size = 5.0
    snap.add_provider(
        PointSnapProvider(
            SnapSource.SKETCH_POINT,
            lambda context: context.sketch.sketch_points_for_snap(),
            radius_px=20,
            priority=10,
        )
    )
    snap.rebuild_cache(ctx)

    result = snap.query((11.7, 9.2, 0.0), (10.0, 10.0), ctx)

    assert result.snapped
    assert result.source == SnapSource.SKETCH_POINT
    assert result.position == (10.0, 10.0, 0.0)


def test_pass103_overlay_exclusive_groups_and_disabled_buttons() -> None:
    ctx = ToolContext()
    ctx.overlay.show_panel(
        ToolPanelSpec(
            "plan",
            "Plan",
            [
                ToolButtonSpec("modify", "Modify", checkable=True, group="plan.modes", checked=True),
                ToolButtonSpec("line", "Line", checkable=True, group="plan.modes"),
                ToolButtonSpec("delete", "Delete", enabled=False),
            ],
        )
    )

    ctx.overlay.toggle_button("line")
    delete_toggled = ctx.overlay.toggle_button("delete")

    assert ctx.overlay.button("modify").checked is False
    assert ctx.overlay.button("line").checked is True
    assert delete_toggled is False


def test_pass103_face_solver_closes_four_independent_lines_with_small_gaps() -> None:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0), point_id="p1")
    p2 = sketch.add_point((10.0, 0.0), point_id="p2")
    p3 = sketch.add_point((10.08, 0.03), point_id="p3")
    p4 = sketch.add_point((10.0, 8.0), point_id="p4")
    p5 = sketch.add_point((9.94, 8.04), point_id="p5")
    p6 = sketch.add_point((0.0, 8.0), point_id="p6")
    p7 = sketch.add_point((-0.07, 7.96), point_id="p7")
    p8 = sketch.add_point((0.02, -0.05), point_id="p8")
    sketch.add_line(p1.id, p2.id)
    sketch.add_line(p3.id, p4.id)
    sketch.add_line(p5.id, p6.id)
    sketch.add_line(p7.id, p8.id)

    created = FaceSolver(FaceSolveOptions(join_tolerance=0.2)).solve(sketch)

    assert len(created) == 1
    face = sketch.faces[created[0]]
    assert len(face.boundary_entity_ids) == 4
    assert len(face.polygon_points) == 4


def test_pass103_face_solver_supports_mixed_line_and_arc_loop() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="a")
    b = sketch.add_point((10.0, 0.0), point_id="b")
    c = sketch.add_point((10.0, 6.0), point_id="c")
    d = sketch.add_point((0.0, 6.0), point_id="d")
    ctrl = sketch.add_point((5.0, 9.0), point_id="ctrl")
    sketch.add_line(a.id, b.id)
    sketch.add_line(b.id, c.id)
    sketch.add_arc(c.id, d.id, ctrl.id)
    sketch.add_line(d.id, a.id)

    created = FaceSolver(FaceSolveOptions(join_tolerance=0.1, arc_segments=8)).solve(sketch)

    assert len(created) == 1
    face = sketch.faces[created[0]]
    assert len(face.boundary_entity_ids) == 4
    assert len(face.polygon_points) > 4


def test_pass103_command_stack_supports_undo_redo() -> None:
    ctx = ToolContext()
    values: list[str] = []
    ctx.commands.execute(FunctionCommand("add", lambda: values.append("x"), lambda: values.pop()))

    assert values == ["x"]
    assert ctx.commands.undo() is True
    assert values == []
    assert ctx.commands.redo() is True
    assert values == ["x"]


class _ModifyMode(ToolModeBase):
    id = "modify"
    label = "Modify"


class _DrawMode(ToolModeBase):
    id = "line"
    label = "Line"

    def on_event(self, event: ToolEvent, ctx: ToolContext) -> bool:  # noqa: ARG002
        return event.type == ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT


class _Tool(ToolBase):
    id = "sample"
    default_mode_id = "modify"

    def __init__(self) -> None:
        super().__init__()
        self.register_mode(_ModifyMode())
        self.register_mode(_DrawMode())


def test_pass103_tool_base_escape_returns_to_default_mode() -> None:
    ctx = ToolContext()
    tool = _Tool()
    tool.activate(ctx)
    assert tool.set_mode("line", ctx)

    handled = tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="Escape"), ctx)

    assert handled is True
    assert tool.active_mode_id == "modify"
