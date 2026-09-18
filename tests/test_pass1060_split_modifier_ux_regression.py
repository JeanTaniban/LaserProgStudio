# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_MOD_SPLIT
from laserprog_studio.tooling.mesh_split import SPLIT_FEEDBACK_WINDOW_ID
from laserprog_studio.tooling.split_tool import SplitPlaneCreatorTool


def _box_mesh(*, x: float = 30.0, y: float = 10.0, z: float = 6.0) -> WorkMesh:
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
    return WorkMesh(name="rect_box", vertices=vertices, triangles=triangles, color="#AABBCC")


def _ctx() -> ToolContext:
    ctx = ToolContext(document=SceneDocument.from_meshes("main", [_box_mesh()]))
    ctx.scene_selection.set_selected([0])
    ctx.viewport.world_to_screen = lambda p: (float(p[0]) * 10.0, float(p[2]) * 10.0)
    return ctx


def test_split_drag_is_clamped_to_selected_model_bounds_and_updates_inspector() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)
    handle = ctx.selection.actor("modifier_split:plane_handle")
    assert handle is not None

    ctx.selection.select("modifier_split:plane_handle")
    ctx.selection.begin_grab("modifier_split:plane_handle", (0.0, 0.0), handle.points[0])
    ctx.selection.update_grab_screen((0.0, 10000.0))
    moved = tool.resolve_drag_positions(object(), ctx)

    assert moved and "modifier_split:plane_handle" in moved
    assert float(ctx.inspector.value("offset_mm")) <= 3.0 + 1.0e-6
    assert float(ctx.inspector.value("offset_mm")) == 3.0
    assert ctx.inspector.value("split_preset") == "custom"


def test_split_handle_is_attached_to_plane_center_and_cut_line_is_visible() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    snapshot = ctx.projected_drawing.snapshot(TOOL_MOD_SPLIT)
    primitives = {primitive.id: primitive for primitive in snapshot.primitives}
    assert "modifier_split:plane_handle" in primitives
    assert "modifier_split:plane_center" in primitives
    assert "modifier_split:cut_line" in primitives

    handle = primitives["modifier_split:plane_handle"]
    center = primitives["modifier_split:plane_center"]
    assert tuple(handle.position) == tuple(center.position)
    assert dict(handle.metadata).get("attached_to_plane_center") is True
    cut = primitives["modifier_split:cut_line"]
    assert len(cut.segments) >= 4
    assert cut.style.width_px >= 4.0


def test_split_plane_size_is_derived_from_model_extent_not_old_diagonal() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    # Horizontal center cut: the displayed plane covers the X/Y footprint with a
    # small margin, not the old full 3D diagonal multiplier.
    assert float(ctx.inspector.value("plane_size_mm")) == 34.0

    ctx.inspector.update_value("split_preset", "center_x")
    # YZ cut: the scalar inspector size mirrors the larger in-plane extent.
    assert float(ctx.inspector.value("plane_size_mm")) == 20.0


def test_split_feedback_overlay_is_compact_metrics_plus_buttons() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    window = ctx.overlay.window(SPLIT_FEEDBACK_WINDOW_ID)
    assert window is not None
    assert window.width_px <= 560
    assert len(window.fields) == 1
    assert "Offset" in window.fields[0].value
    assert "triangles" in window.fields[0].value
    assert [button.id for button in window.buttons] == [
        "split_overlay_reset",
        "split_overlay_orient_xy",
        "split_overlay_orient_yz",
        "split_overlay_orient_xz",
        "split_overlay_preview",
        "split_overlay_apply",
        "split_overlay_cancel",
    ]
    assert "snap 5" in window.fields[0].value


def test_tool_lifecycle_syncs_creator_overlay_immediately_after_open() -> None:
    source = Path("src/laserprog_studio/application/tool_lifecycle_controller.py").read_text(encoding="utf-8")
    assert "sync_creator_overlay_windows(self.owner, tool.tool_context(self.context))" in source
    assert "sync_creator_overlay_windows(self.owner, ctx)" in source


def test_split_drag_requests_visible_inspector_refresh_for_programmatic_values() -> None:
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
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)
    owner.count = 0
    handle = ctx.selection.actor("modifier_split:plane_handle")
    assert handle is not None

    ctx.selection.select("modifier_split:plane_handle")
    ctx.selection.begin_grab("modifier_split:plane_handle", (0.0, 0.0), handle.points[0])
    ctx.selection.update_grab_screen((0.0, 1000.0))
    tool.resolve_drag_positions(object(), ctx)

    assert owner.count >= 1


def test_split_two_relative_tilt_handles_are_projected_and_grabbable() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    snapshot = ctx.projected_drawing.snapshot(TOOL_MOD_SPLIT)
    ids = {primitive.id for primitive in snapshot.primitives}
    assert {"modifier_split:rotate_x", "modifier_split:rotate_y"}.issubset(ids)
    assert "modifier_split:rotate_z" not in ids
    for handle_id, field_id in (
        ("modifier_split:rotate_x", "rx_deg"),
        ("modifier_split:rotate_y", "ry_deg"),
    ):
        actor = ctx.selection.actor(handle_id)
        assert actor is not None
        assert actor.grabbable
        assert (actor.metadata or {}).get("rotation_field") == field_id
        assert (actor.metadata or {}).get("stable_handle") is True


def test_split_rotation_handles_expose_two_axis_snap_labels_and_metadata() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    snapshot = ctx.projected_drawing.snapshot(TOOL_MOD_SPLIT)
    primitives = {primitive.id: primitive for primitive in snapshot.primitives}
    for handle_id in ("modifier_split:rotate_x", "modifier_split:rotate_y"):
        actor = ctx.selection.actor(handle_id)
        assert actor is not None
        assert (actor.metadata or {}).get("rotation_mode") == "relative_two_axis_snap"
        assert float((actor.metadata or {}).get("snap_degrees")) == 5.0
    labels = [getattr(primitive, "text", "") for primitive in primitives.values()]
    assert any("Tilt U 0° · 5°" == value for value in labels)
    assert any("Tilt V 0° · 5°" == value for value in labels)


def test_split_orientation_buttons_snap_to_common_planes() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    assert tool._handle_action_id("split_overlay_orient_yz", ctx)
    assert float(ctx.inspector.value("rx_deg")) == 0.0
    assert float(ctx.inspector.value("ry_deg")) == 90.0
    assert ctx.inspector.value("split_preset") == "center_x"

    assert tool._handle_action_id("split_overlay_orient_xz", ctx)
    assert float(ctx.inspector.value("rx_deg")) == 90.0
    assert float(ctx.inspector.value("ry_deg")) == 0.0
    assert ctx.inspector.value("split_preset") == "center_y"


def test_split_tilt_handle_updates_plane_rotation_and_inspector() -> None:
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
    # Make rotation tests independent from any local persistent parameter file.
    ctx.viewport.world_to_screen = lambda p: (float(p[0]) * 10.0, float(p[1]) * 10.0 + float(p[2]) * 5.0)
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)
    ctx.inspector.update_value("rx_deg", 0.0, notify=False)
    ctx.inspector.update_value("split_preset", "center_z", notify=False)
    tool._sync_plane_projection(ctx, render=True)
    handle = ctx.selection.actor("modifier_split:rotate_x")
    assert handle is not None

    ctx.selection.select("modifier_split:rotate_x")
    ctx.selection.begin_grab("modifier_split:rotate_x", (0.0, 0.0), handle.points[0])
    ctx.selection.update_grab_screen((0.0, 50.0))
    moved = tool.resolve_drag_positions(object(), ctx)

    assert moved and "modifier_split:rotate_x" in moved
    assert float(ctx.inspector.value("rx_deg")) % 5.0 == 0.0
    assert float(ctx.inspector.value("rx_deg")) >= 5.0
    assert ctx.inspector.value("split_preset") == "custom"
    assert owner.count >= 1


def test_split_plane_panel_exposes_only_two_useful_tilts() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    panel = ctx.inspector.panel
    assert panel is not None
    fields = {field.id: field for field in panel.fields()}
    assert "rx_deg" in fields
    assert "ry_deg" in fields
    assert "rz_deg" not in fields
    assert fields["rx_deg"].label == "Tilt U"
    assert fields["ry_deg"].label == "Tilt V"


def test_split_tilt_nudge_buttons_update_visible_values() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    assert ctx.inspector.trigger("tilt_u_plus")
    assert float(ctx.inspector.value("rx_deg")) == 5.0
    assert ctx.inspector.value("split_preset") == "custom"
    assert ctx.inspector.trigger("tilt_v_minus")
    assert float(ctx.inspector.value("ry_deg")) == -5.0
    assert ctx.inspector.trigger("tilt_reset")
    assert float(ctx.inspector.value("rx_deg")) == 0.0
    assert float(ctx.inspector.value("ry_deg")) == 0.0


def test_split_apply_button_auto_previews_commits_and_closes_tool(monkeypatch) -> None:
    import laserprog_studio.tooling.split_tool as split_module

    def fake_split(meshes, selected, *, origin, normal, tolerance):
        out = list(meshes)
        original = out[selected[0]]
        first = _box_mesh(x=12.0, y=8.0, z=4.0)
        first.name = f"{original.name} split A"
        second = _box_mesh(x=12.0, y=8.0, z=4.0)
        second.name = f"{original.name} split B"
        out[selected[0]] = first
        out.append(second)
        return out, (selected[0], len(out) - 1), 1, 2

    class Owner:
        TOOL_NONE = "none"

        def __init__(self) -> None:
            self.closed = 0
            self.active_tool = TOOL_MOD_SPLIT
            self.selected_indices = [0]
            self.active_index = 0

        def close_active_tool(self, *, log_it: bool = False, ask_preview: bool = False) -> None:
            assert ask_preview is False
            self.closed += 1
            self.active_tool = self.TOOL_NONE

    monkeypatch.setattr(split_module, "split_selected_meshes_by_plane", fake_split)
    ctx = _ctx()
    owner = Owner()
    ctx.owner = owner
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)
    store = ctx.document.raw.model_store
    assert not store.has_preview

    ctx.inspector.trigger("apply_split")

    assert owner.closed == 1
    assert owner.active_tool == owner.TOOL_NONE
    assert not store.has_preview
    assert len(store.committed_meshes) == 2
    assert store.committed_meshes[0].name.endswith("split A")
    assert store.committed_meshes[1].name.endswith("split B")


def test_split_cancel_exits_even_without_preview() -> None:
    class Owner:
        TOOL_NONE = "none"

        def __init__(self) -> None:
            self.closed = 0
            self.active_tool = TOOL_MOD_SPLIT
            self.selected_indices = [0]
            self.active_index = 0

        def close_active_tool(self, *, log_it: bool = False, ask_preview: bool = False) -> None:
            assert ask_preview is False
            self.closed += 1
            self.active_tool = self.TOOL_NONE

    ctx = _ctx()
    owner = Owner()
    ctx.owner = owner
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    assert tool.on_cancel(ctx) is True
    assert owner.closed == 1
    assert owner.active_tool == owner.TOOL_NONE
    assert "No active split preview" not in str(ctx.inspector.value("split_report", ""))


def test_split_rotation_snap_can_be_disabled_for_free_tilt_labels() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)
    ctx.inspector.update_value("rotation_snap_enabled", False, notify=False)
    tool._sync_plane_projection(ctx, render=True)

    snapshot = ctx.projected_drawing.snapshot(TOOL_MOD_SPLIT)
    primitives = {primitive.id: primitive for primitive in snapshot.primitives}
    actor = ctx.selection.actor("modifier_split:rotate_x")
    assert actor is not None
    assert (actor.metadata or {}).get("snap_enabled") is False
    labels = [getattr(primitive, "text", "") for primitive in primitives.values()]
    assert any("Tilt U 0° · free" == value for value in labels)
