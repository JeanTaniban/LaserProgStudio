# -*- coding: utf-8 -*-
from __future__ import annotations

import math

import pytest

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.folding.geometry import arbitrary_face_plane, deform_mesh
from laserprog_studio.tooling.folding.models import (
    FoldingCurve,
    FoldingDeformationMode,
    FoldingMode,
    FoldingPhase,
)
from laserprog_studio.tooling.folding.serialization import attach_folding_source, restore_folding_source
from laserprog_studio.tooling.folding_tool import FoldingCreatorTool


def _plane():
    return arbitrary_face_plane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def _curve(mode: str) -> FoldingCurve:
    return FoldingCurve(
        start=(0.0, 0.0, 0.0),
        end=(10.0, 0.0, 0.0),
        mode=FoldingMode.LIVING_HINGE.value,
        fold_angle_deg=140.0,
        deformation_mode=mode,
    )


def _sparse_sheet() -> WorkMesh:
    # Deliberately no source vertex lies inside the flexible strip.  The old
    # implementation could only rotate the far side and left two huge planar
    # triangles bridging the fold.
    return WorkMesh(
        name="sparse sheet",
        vertices=[(-2.0, -2.0, 0.0), (12.0, -2.0, 0.0), (-2.0, 2.0, 0.0), (12.0, 2.0, 0.0)],
        triangles=[(0, 1, 2), (1, 3, 2)],
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)],
    )


def _sheet_with_isolated_detail() -> WorkMesh:
    return WorkMesh(
        name="sheet with internal detail",
        vertices=[
            (-2.0, -3.0, 0.0), (12.0, -3.0, 0.0), (-2.0, 3.0, 0.0), (12.0, 3.0, 0.0),
            (4.5, -0.4, 0.4), (5.5, -0.4, 0.4), (4.8, 0.5, 0.4), (4.8, 0.0, 1.4),
        ],
        triangles=[
            (0, 1, 2), (1, 3, 2),
            (4, 5, 6), (4, 7, 5), (5, 7, 6), (6, 7, 4),
        ],
    )


def _pairwise_distances(points, indices):
    return {
        (a, b): math.dist(points[a], points[b])
        for offset, a in enumerate(indices)
        for b in indices[offset + 1 :]
    }



def test_straight_living_hinge_does_not_retopologize_the_mesh() -> None:
    source = _sparse_sheet()
    curve = _curve(FoldingDeformationMode.PRESERVE_STRUCTURE.value)
    curve.fold_angle_deg = 0.0
    curve.shape_angles_deg = (0.0, 0.0, 0.0)
    result = deform_mesh(source, _plane(), curve)
    assert result.vertices == source.vertices
    assert result.triangles == source.triangles
    assert result.uvs == source.uvs

def test_sparse_faces_are_adaptively_refined_and_really_form_a_curve() -> None:
    source = _sparse_sheet()
    result = deform_mesh(source, _plane(), _curve(FoldingDeformationMode.UNIFORM.value))

    assert len(result.vertices) > len(source.vertices)
    assert len(result.triangles) > len(source.triangles)
    assert result.uvs is not None and len(result.uvs) == len(result.vertices)

    # More than the two rigid outside heights proves that the flexible region
    # contains actual curved stations instead of one stretched bridge face.
    heights = {round(point[2], 5) for point in result.vertices}
    assert len(heights) >= 8
    assert max(heights) > 1.0


def test_preserve_structure_keeps_an_isolated_internal_feature_rigid() -> None:
    source = _sheet_with_isolated_detail()
    indices = (4, 5, 6, 7)
    original = _pairwise_distances(source.vertices, indices)

    preserved = deform_mesh(source, _plane(), _curve(FoldingDeformationMode.PRESERVE_STRUCTURE.value))
    uniform = deform_mesh(source, _plane(), _curve(FoldingDeformationMode.UNIFORM.value))
    preserved_distances = _pairwise_distances(preserved.vertices, indices)
    uniform_distances = _pairwise_distances(uniform.vertices, indices)

    assert preserved_distances == pytest.approx(original, abs=1.0e-9)
    assert max(abs(uniform_distances[key] - original[key]) for key in original) > 0.03


def test_deformation_mode_round_trips_and_is_exposed_in_the_inspector() -> None:
    source = _sparse_sheet()
    curve = _curve(FoldingDeformationMode.UNIFORM.value)
    folded = attach_folding_source(source, source_mesh=source, plane=_plane(), curve=curve)
    restored = restore_folding_source(folded)
    assert restored is not None
    assert restored[2].normalized_deformation_mode() == FoldingDeformationMode.UNIFORM.value

    store = ModelStore()
    store.set_meshes([source], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    tool.session.target_object_id = source.mesh_id
    tool.session.target_index = 0
    tool.session.target_name = source.name
    tool.session.source_mesh = source
    tool.session.plane = _plane()
    tool.session.curve = _curve(FoldingDeformationMode.PRESERVE_STRUCTURE.value)
    tool.session.phase = FoldingPhase.ADJUST_CURVE
    tool._sync(ctx, "ready", render=False)

    state = ctx.inspector.field_state("folding_deformation_mode")
    assert state.visible is True
    assert state.enabled is True
    tool._on_value_changed(ctx, "folding_deformation_mode", FoldingDeformationMode.UNIFORM.value)
    assert tool.session.curve.normalized_deformation_mode() == FoldingDeformationMode.UNIFORM.value
