# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.box_tool import BoxCreatorTool
from laserprog_studio.tooling.engraving_roles_tool import EngravingRolesCreatorTool
from laserprog_studio.tooling.layflat_tool import LayflatCreatorTool
from laserprog_studio.tooling.primitive_tool import PrimitiveCreatorTool
from laserprog_studio.tooling.split_tool import SplitPlaneCreatorTool


def _panel_mesh(name: str = "panel", offset: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name,
        [
            (offset + 0.0, 0.0, 0.0),
            (offset + 20.0, 0.0, 2.0),
            (offset + 20.0, 15.0, 4.0),
            (offset + 0.0, 15.0, 1.0),
        ],
        [(0, 1, 2), (0, 2, 3)],
        color="#AABBCC",
    )


def _box_mesh(name: str = "solid") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (-1.0, -1.0, -1.0),
            (1.0, -1.0, -1.0),
            (1.0, 1.0, -1.0),
            (-1.0, 1.0, -1.0),
            (-1.0, -1.0, 1.0),
            (1.0, -1.0, 1.0),
            (1.0, 1.0, 1.0),
            (-1.0, 1.0, 1.0),
        ],
        triangles=[
            (0, 1, 2),
            (0, 2, 3),
            (4, 6, 5),
            (4, 7, 6),
            (0, 4, 5),
            (0, 5, 1),
            (1, 5, 6),
            (1, 6, 2),
            (2, 6, 7),
            (2, 7, 3),
            (3, 7, 4),
            (3, 4, 0),
        ],
        color="#AABBCC",
    )


def _ctx_with_store(*meshes: WorkMesh) -> tuple[ToolContext, ModelStore]:
    store = ModelStore()
    store.set_meshes(list(meshes), push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    return ctx, store


def test_pass261_primitive_edits_discard_stale_preview_before_global_apply() -> None:
    ctx, store = _ctx_with_store()
    tool = PrimitiveCreatorTool()
    tool.open(ctx)

    ctx.inspector.trigger("stage_preview")
    assert store.has_preview

    ctx.inspector.update_value("size", (50.0, 10.0, 5.0), notify=True)

    assert not store.has_preview
    assert tool.apply(ctx) is False
    assert len(store.committed_meshes) == 0
    assert any("parameters changed" in message.message for message in ctx.status.messages())


def test_pass261_box_edits_discard_stale_preview_before_global_apply() -> None:
    ctx, store = _ctx_with_store(_panel_mesh("existing"))
    tool = BoxCreatorTool()
    tool.open(ctx)

    ctx.inspector.trigger("stage_preview")
    assert store.has_preview
    assert len(store.preview_meshes or []) > len(store.committed_meshes)

    ctx.inspector.update_value("width", 180.0, notify=True)

    assert not store.has_preview
    assert tool.apply(ctx) is False
    assert [mesh.name for mesh in store.committed_meshes] == ["existing"]


def test_pass261_layflat_edits_discard_stale_preview_before_global_apply() -> None:
    ctx, store = _ctx_with_store(_panel_mesh("a"), _panel_mesh("b", 35.0))
    tool = LayflatCreatorTool()
    tool.open(ctx)

    ctx.inspector.trigger("preview")
    assert store.has_preview

    ctx.inspector.update_value("spacing_mm", 12.0, notify=True)

    assert not store.has_preview
    assert tool.apply(ctx) is False
    assert len(store.committed_meshes) == 2
    assert ctx.inspector.value("layflat_report").startswith("Scene objects: 2")


def test_pass261_split_recenter_discards_stale_preview_before_global_apply(monkeypatch) -> None:
    import laserprog_studio.tooling.split_tool as split_module

    def fake_split(meshes, selected, *, origin, normal, tolerance):
        out = list(meshes)
        original = out[selected[0]]
        first = _box_mesh(f"{original.name} split A")
        second = _box_mesh(f"{original.name} split B")
        out[selected[0]] = first
        out.append(second)
        return out, (selected[0], len(out) - 1), 1, 2

    monkeypatch.setattr(split_module, "split_selected_meshes_by_plane", fake_split)

    ctx, store = _ctx_with_store(_box_mesh("a"), _box_mesh("b"))
    ctx.scene_selection.select_indices((0,), active_index=0)
    tool = SplitPlaneCreatorTool()
    tool.open(ctx)

    ctx.inspector.trigger("preview")
    assert store.has_preview
    assert len(store.preview_meshes or []) == 3

    ctx.inspector.trigger("reset_plane")

    assert not store.has_preview
    assert "Plane recentered" in ctx.inspector.value("split_report")
    assert tool.apply(ctx) is False
    assert [mesh.name for mesh in store.committed_meshes] == ["a", "b"]


def test_pass261_engraving_role_change_discards_stale_preview_before_global_apply() -> None:
    ctx, store = _ctx_with_store(_panel_mesh("a"), _panel_mesh("b"))
    ctx.scene_selection.select_indices((0,), active_index=0)
    tool = EngravingRolesCreatorTool()
    tool.open(ctx)

    ctx.inspector.trigger("assign_selected")
    assert store.has_preview

    ctx.inspector.update_value("role", "fill", notify=True)

    assert not store.has_preview
    assert tool.apply(ctx) is False
    assert getattr(store.committed_meshes[0], "engraving", None) is None
    assert "Preview again" in ctx.inspector.value("engraving_report")
