# -*- coding: utf-8 -*-
from __future__ import annotations

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.fabrication.box_generator import box_metadata
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.acoustic_diffuser_tool import AcousticDiffuserCreatorTool
from laserprog_studio.tooling.box_tool import BoxCreatorTool
from laserprog_studio.tooling.layflat_tool import LayflatCreatorTool
from laserprog_studio.tooling.primitive_tool import PrimitiveCreatorTool


def _mesh(name: str, offset: float = 0.0) -> WorkMesh:
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


def _ctx_with_store(*meshes: WorkMesh) -> tuple[ToolContext, ModelStore]:
    store = ModelStore()
    store.set_meshes(list(meshes), push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    return ctx, store


def test_pass260_primitive_repeated_preview_replaces_previous_stage_not_duplicate() -> None:
    ctx, store = _ctx_with_store()
    tool = PrimitiveCreatorTool()
    tool.open(ctx)

    ctx.inspector.update_values({"primitive_id": "box", "size": (20.0, 10.0, 5.0)}, notify=True)
    assert ctx.inspector.trigger("stage_preview").action_id == "stage_preview"
    assert store.has_preview
    assert len(store.preview_meshes or []) == 1
    first_name = (store.preview_meshes or [])[0].name
    assert first_name.startswith("box_")

    ctx.inspector.update_values({"primitive_id": "sphere", "size": (12.0, 12.0, 12.0)}, notify=True)
    assert ctx.inspector.trigger("stage_preview").action_id == "stage_preview"

    assert store.has_preview
    assert len(store.preview_meshes or []) == 1
    assert (store.preview_meshes or [])[0].name.startswith("sphere_")
    assert (store.preview_meshes or [])[0].name != first_name

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert len(store.committed_meshes) == 1
    assert store.committed_meshes[0].name.startswith("sphere_")


def test_pass260_box_generator_append_preview_does_not_accumulate_stale_boards() -> None:
    ctx, store = _ctx_with_store(_mesh("existing"))
    tool = BoxCreatorTool()
    tool.open(ctx)

    ctx.inspector.update_values({"width": 90.0, "depth": 60.0, "height": 40.0, "thickness": 2.5}, notify=True)
    assert ctx.inspector.trigger("stage_preview").action_id == "stage_preview"
    assert len(store.preview_meshes or []) == 7
    assert (store.preview_meshes or [])[0].name == "existing"
    assert sum(1 for mesh in (store.preview_meshes or []) if box_metadata(mesh)) == 6

    ctx.inspector.update_values({"width": 120.0, "depth": 80.0}, notify=True)
    assert ctx.inspector.trigger("stage_preview").action_id == "stage_preview"

    assert len(store.preview_meshes or []) == 7
    assert (store.preview_meshes or [])[0].name == "existing"
    assert sum(1 for mesh in (store.preview_meshes or []) if box_metadata(mesh)) == 6

    assert tool.apply(ctx) is True
    assert len(store.committed_meshes) == 7


def test_pass260_layflat_dynamic_controls_follow_actual_behavior_and_preview_applies() -> None:
    ctx, store = _ctx_with_store(_mesh("panel-a"), _mesh("panel-b", 30.0))
    tool = LayflatCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.field_state("minimum_overlap_mm").visible is True
    assert ctx.inspector.field_state("touch_tolerance_mm").visible is False
    assert ctx.inspector.field_state("max_length_mm").visible is True
    assert ctx.inspector.field_state("max_depth_mm").visible is False

    ctx.inspector.update_values({"fusion_mode": "touch", "packing_constraint": "max_depth"}, notify=True)

    assert ctx.inspector.field_state("minimum_overlap_mm").visible is False
    assert ctx.inspector.field_state("touch_tolerance_mm").visible is True
    assert ctx.inspector.field_state("max_length_mm").visible is False
    assert ctx.inspector.field_state("max_depth_mm").visible is True
    assert "Merging=touch" in ctx.inspector.value("layflat_report")
    assert "packing=max_depth" in ctx.inspector.value("layflat_report")

    assert ctx.inspector.trigger("preview").action_id == "preview"
    assert store.has_preview
    assert len(store.preview_meshes or []) >= 1
    assert ctx.inspector.field_state("layflat_report").error is None

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert len(store.committed_meshes) >= 1


def test_pass260_acoustic_diffuser_ventless_mode_hides_vent_fields_and_preview_applies() -> None:
    ctx, store = _ctx_with_store(_mesh("speaker-reference"))
    tool = AcousticDiffuserCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.field_state("vent_count").visible is True
    assert ctx.inspector.field_state("vent_size_mm").visible is True

    ctx.inspector.update_value("vent_style", "none", notify=True)

    assert ctx.inspector.field_state("vent_count").visible is False
    assert ctx.inspector.field_state("vent_count").enabled is False
    assert ctx.inspector.field_state("vent_size_mm").visible is False
    assert ctx.inspector.field_state("vent_size_mm").enabled is False
    assert "vents 0%" in ctx.inspector.value("acoustic_report")

    assert ctx.inspector.trigger("stage_preview").action_id == "stage_preview"
    assert store.has_preview
    assert len(store.preview_meshes or []) == 3
    assert (store.preview_meshes or [])[0].name == "speaker-reference"

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert len(store.committed_meshes) == 3
