# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.acoustic_diffuser_tool import AcousticDiffuserCreatorTool
from laserprog_studio.tooling.box_tool import BoxCreatorTool
from laserprog_studio.tooling.engraving_roles_tool import EngravingRolesCreatorTool
from laserprog_studio.tooling.primitive_tool import PrimitiveCreatorTool


@pytest.mark.parametrize(
    ("tool_factory", "expected_fragment"),
    (
        (PrimitiveCreatorTool, "Primitive preview needs an active document"),
        (BoxCreatorTool, "Box preview needs an active document"),
        (AcousticDiffuserCreatorTool, "Acoustic diffuser preview needs an active document"),
    ),
)
def test_pass256_generator_preview_actions_do_not_throw_without_bound_document(tool_factory, expected_fragment: str) -> None:
    ctx = ToolContext()
    tool = tool_factory()
    tool.open(ctx)

    event = ctx.inspector.trigger("stage_preview")

    assert event.action_id == "stage_preview"
    latest_error = ctx.status.latest(level="error")
    assert latest_error is not None
    assert expected_fragment in latest_error.message


@pytest.mark.parametrize("action_id", ("assign_all", "outline_all"))
def test_pass256_engraving_all_actions_do_not_throw_without_bound_document(action_id: str) -> None:
    ctx = ToolContext()
    tool = EngravingRolesCreatorTool()
    tool.open(ctx)

    event = ctx.inspector.trigger(action_id)

    assert event.action_id == action_id
    latest_error = ctx.status.latest(level="error")
    assert latest_error is not None
    assert "Engraving role preview needs an active document" in latest_error.message
    assert "active document" in ctx.inspector.value("engraving_report")


def test_pass256_product_quality_audit_smokes_enabled_inspector_actions() -> None:
    from scripts.audit_tool_product_quality import collect_tool_product_records

    records = collect_tool_product_records()

    assert records
    assert all(record.ok for record in records)
    assert not [issue for record in records for issue in record.issues if "action smoke failed" in issue]
