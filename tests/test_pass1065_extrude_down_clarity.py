# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.extrude_down_tool import ExtrudeDownCreatorTool
from laserprog_studio.tooling.ids import TOOL_MOD_EXTRUDE_DOWN
from laserprog_studio.tooling.mesh_extrude_down import EXTRUDE_DOWN_FEEDBACK_WINDOW_ID


def _box_mesh(*, x: float = 30.0, y: float = 10.0, z: float = 8.0) -> WorkMesh:
    vertices = [
        (0.0, 0.0, 0.0),
        (x, 0.0, 0.0),
        (x, y, 0.0),
        (0.0, y, 0.0),
        (0.0, 0.0, z),
        (x, 0.0, z),
        (x, y, z),
        (0.0, y, z),
    ]
    triangles = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    ]
    return WorkMesh(name="extrude_box", vertices=vertices, triangles=triangles, color="#AABBCC")


def _ctx() -> ToolContext:
    ctx = ToolContext(document=SceneDocument.from_meshes("main", [_box_mesh()]))
    ctx.scene_selection.set_selected([0])
    ctx.viewport.world_to_screen = lambda p: (float(p[0]) * 10.0, float(p[2]) * 10.0)
    return ctx


def test_extrude_down_handle_is_attached_to_horizontal_plane_center_and_cut_line_is_visible() -> None:
    ctx = _ctx()
    tool = ExtrudeDownCreatorTool()
    tool.on_open(ctx)

    snapshot = ctx.projected_drawing.snapshot(TOOL_MOD_EXTRUDE_DOWN)
    primitives = {primitive.id: primitive for primitive in snapshot.primitives}
    assert "modifier_extrude_down:plane_handle" in primitives
    assert "modifier_extrude_down:plane_center" in primitives
    assert "modifier_extrude_down:cut_line" in primitives
    assert "modifier_extrude_down:plane_label" in primitives

    handle = primitives["modifier_extrude_down:plane_handle"]
    center = primitives["modifier_extrude_down:plane_center"]
    assert tuple(handle.position) == tuple(center.position)
    assert dict(handle.metadata).get("attached_to_plane_center") is True
    assert dict(handle.metadata).get("vertical_only") is True
    assert dict(primitives["modifier_extrude_down:plane_face"].metadata).get("horizontal_only") is True
    cut = primitives["modifier_extrude_down:cut_line"]
    assert len(cut.segments) >= 4
    assert cut.style.width_px >= 4.0


def test_extrude_down_panel_is_z_only_and_exposes_clear_nudges() -> None:
    ctx = _ctx()
    tool = ExtrudeDownCreatorTool()
    tool.on_open(ctx)

    panel = ctx.inspector.panel
    assert panel is not None
    fields = {field.id: field for field in panel.fields()}
    assert "plane_z" in fields
    assert "ground_z" in fields
    assert "support_plane_size" in fields
    assert "rx_deg" not in fields
    assert "ry_deg" not in fields
    assert "rz_deg" not in fields
    assert ctx.inspector.trigger("plane_z_plus")
    assert ctx.inspector.value("extrude_down_preset") == "custom"
    assert float(ctx.inspector.value("plane_z")) > 0.0


def test_extrude_down_feedback_overlay_is_compact_metrics_plus_buttons() -> None:
    ctx = _ctx()
    tool = ExtrudeDownCreatorTool()
    tool.on_open(ctx)

    window = ctx.overlay.window(EXTRUDE_DOWN_FEEDBACK_WINDOW_ID)
    assert window is not None
    assert window.width_px <= 560
    assert len(window.fields) == 1
    assert "Horizontal Z" in window.fields[0].value
    assert "triangles" in window.fields[0].value
    assert [button.id for button in window.buttons] == [
        "extrude_down_overlay_preview",
        "extrude_down_overlay_apply",
        "extrude_down_overlay_cancel",
    ]


def test_extrude_down_drag_updates_plane_z_ratio_and_requests_inspector_refresh() -> None:
    class Owner:
        def __init__(self) -> None:
            self.count = 0
            self.selected_indices = [0]
            self.active_index = 0

        def update_inspector(self) -> None:
            self.count += 1

    ctx = _ctx()
    owner = Owner()
    ctx.owner = owner
    tool = ExtrudeDownCreatorTool()
    tool.on_open(ctx)
    handle = ctx.selection.actor("modifier_extrude_down:plane_handle")
    assert handle is not None
    start_z = float(ctx.inspector.value("plane_z"))

    ctx.selection.select("modifier_extrude_down:plane_handle")
    ctx.selection.begin_grab("modifier_extrude_down:plane_handle", (0.0, 0.0), handle.points[0])
    ctx.selection.update_grab_screen((0.0, 1000.0))
    moved = tool.resolve_drag_positions(object(), ctx)

    assert moved and "modifier_extrude_down:plane_handle" in moved
    assert float(ctx.inspector.value("plane_z")) > start_z
    assert float(ctx.inspector.value("plane_z")) <= 8.0
    assert float(ctx.inspector.value("plane_ratio")) > 33.0
    assert owner.count >= 1


def test_extrude_down_apply_button_auto_previews_commits_and_closes_tool(monkeypatch) -> None:
    import laserprog_studio.tooling.extrude_down_tool as extrude_module

    def fake_extrude(meshes, selected, *, plane_z, ground_z, tolerance):
        out = list(meshes)
        mesh = _box_mesh()
        mesh.name = f"{out[selected[0]].name} extruded down"
        # Make the fake visibly different without depending on Shapely internals.
        mesh.triangles = list(mesh.triangles) + [(0, 1, 4)]
        out[selected[0]] = mesh
        return SimpleNamespace(ok=True, meshes=tuple(out), warnings=())

    class Owner:
        TOOL_NONE = "none"

        def __init__(self) -> None:
            self.closed = 0
            self.active_tool = TOOL_MOD_EXTRUDE_DOWN
            self.selected_indices = [0]
            self.active_index = 0

        def close_active_tool(self, *, log_it: bool = False, ask_preview: bool = False) -> None:
            assert ask_preview is False
            self.closed += 1
            self.active_tool = self.TOOL_NONE

    monkeypatch.setattr(extrude_module, "extrude_selected_meshes_down", fake_extrude)
    ctx = _ctx()
    owner = Owner()
    ctx.owner = owner
    tool = ExtrudeDownCreatorTool()
    tool.on_open(ctx)
    store = ctx.document.raw.model_store
    assert not store.has_preview

    ctx.inspector.trigger("apply_extrude_down")

    assert owner.closed == 1
    assert owner.active_tool == owner.TOOL_NONE
    assert not store.has_preview
    assert store.committed_meshes[0].name.endswith("extruded down")
