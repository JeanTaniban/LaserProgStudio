# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.folding.models import FoldingCurve, FoldingMode, FoldingPhase
from laserprog_studio.tooling.folding.serialization import folding_group_info
from laserprog_studio.tooling.folding_tool import FoldingCreatorTool


def _strip(name: str, y0: float) -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (-5.0, y0 - 1.0, 0.0),
            (0.0, y0 - 1.0, 0.0),
            (5.0, y0 - 1.0, 0.0),
            (-5.0, y0 + 1.0, 0.0),
            (0.0, y0 + 1.0, 0.0),
            (5.0, y0 + 1.0, 0.0),
        ],
        triangles=[(0, 1, 3), (1, 4, 3), (1, 2, 4), (2, 5, 4)],
        color="#AACCEE",
    )


def _plane() -> LockedPlaneSpec:
    return LockedPlaneSpec(
        FixedPlanarView.TOP,
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        0.0,
    )


def _configure_fold(tool: FoldingCreatorTool) -> None:
    tool.session.plane = _plane()
    tool.session.curve = FoldingCurve(
        start=(-1.0, 0.0, 0.0),
        end=(1.0, 0.0, 0.0),
        mode=FoldingMode.LIVING_HINGE.value,
        fold_angle_deg=90.0,
    )
    tool.session.phase = FoldingPhase.ADJUST_CURVE


def test_selected_meshes_fold_as_one_group_but_remain_separate_objects() -> None:
    meshes = [_strip("left panel", -3.0), _strip("right panel", 3.0)]
    store = ModelStore()
    store.set_meshes(meshes, push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0, 1), active_index=1)

    tool = FoldingCreatorTool()
    tool.open(ctx)
    assert tool.session.target_count == 2
    assert tool.session.target_object_ids == tuple(mesh.mesh_id for mesh in meshes)
    assert tool.session.source_meshes[0] is not tool.session.source_meshes[1]

    _configure_fold(tool)
    assert tool._update_preview(ctx, force=True)
    assert len(store.preview_meshes) == 2
    assert [mesh.name for mesh in store.preview_meshes] == ["left panel", "right panel"]
    assert [mesh.mesh_id for mesh in store.preview_meshes] == [mesh.mesh_id for mesh in meshes]
    assert store.preview_meshes[0].vertices != meshes[0].vertices
    assert store.preview_meshes[1].vertices != meshes[1].vertices

    first_group = folding_group_info(store.preview_meshes[0])
    second_group = folding_group_info(store.preview_meshes[1])
    assert first_group is not None and second_group is not None
    assert first_group[0] == second_group[0]
    assert first_group[1] == tuple(mesh.mesh_id for mesh in meshes)
    assert second_group[1] == tuple(mesh.mesh_id for mesh in meshes)
    assert first_group[2] == 0
    assert second_group[2] == 1

    assert tool.apply(ctx)
    assert len(store.committed_meshes) == 2
    assert [mesh.name for mesh in store.committed_meshes] == ["left panel", "right panel"]


def test_reopening_one_group_member_restores_the_complete_separate_group() -> None:
    meshes = [_strip("panel A", -3.0), _strip("panel B", 3.0)]
    store = ModelStore()
    store.set_meshes(meshes, push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0, 1), active_index=0)

    first = FoldingCreatorTool()
    first.open(ctx)
    _configure_fold(first)
    assert first._update_preview(ctx, force=True)
    assert first.apply(ctx)

    # Select only one output. Folding must discover the persisted group without
    # merging its members into one document object.
    ctx.scene_selection.select_indices((0,), active_index=0)
    reopened = FoldingCreatorTool()
    reopened.open(ctx)
    assert reopened.session.editing_existing is True
    assert reopened.session.phase is FoldingPhase.ADJUST_CURVE
    assert reopened.session.target_count == 2
    assert len(reopened.session.source_meshes) == 2
    assert len(store.committed_meshes) == 2
