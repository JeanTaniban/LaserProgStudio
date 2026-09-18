from __future__ import annotations

from laserprog_studio.tool_api import plan2d
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.projected_drawing import ProjectedText
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE


def test_plan_tracer_dimension_label_is_dark_bold_and_backed_by_cyan_badge() -> None:
    ctx = ToolContext()
    plan2d.register_plan_dimension(
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        dimension_id="dimension.visible",
        dimension_world_line=((0.0, 0.0, 0.0), (20.0, 0.0, 0.0)),
        label_world_pos=(10.0, 3.0, 0.0),
        label="20.00 mm",
    )

    label = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get("dimension.visible:label")
    assert isinstance(label, ProjectedText)
    assert label.style.color.lower() == "#075985"
    assert label.style.size_px == 14
    assert label.style.bold is True
    assert label.layer == 64

    metadata = dict(label.metadata)
    assert metadata["text_background_color"].lower() == "#e0f2fe"
    assert metadata["text_background_opacity"] == 0.90
    assert metadata["text_frame_color"].lower() == "#38bdf8"
    assert metadata["text_frame_width"] == 1
    assert metadata["text_frame"] is True
