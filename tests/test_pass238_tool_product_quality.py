from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _path_setup import ROOT  # noqa: F401

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from laserprog_studio.tool_core.workflow import ToolWorkflowManager
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR

from scripts.audit_tool_product_quality import collect_tool_product_records


def test_every_builtin_tool_has_user_facing_creator_contract() -> None:
    records = collect_tool_product_records()
    assert len(records) == 21
    assert [record.id for record in records if not record.ok] == []
    assert all(record.panel_id for record in records)
    assert all(record.panel_description for record in records)
    assert all(record.workflow_steps for record in records)




def test_product_audit_does_not_pollute_tool_parameter_preferences(tmp_path: Path, monkeypatch) -> None:
    prefs = tmp_path / "tool_params.json"
    seed = {"schema_version": 1, "tools": {"layflat": {"fusion_mode": "overlap"}}}
    prefs.write_text(json.dumps(seed, indent=2), encoding="utf-8")
    monkeypatch.setenv("LASERPROG_TOOL_PARAMETER_PREFERENCES", str(prefs))
    monkeypatch.delenv("LASERPROG_DISABLE_TOOL_PARAMETER_PERSISTENCE", raising=False)

    records = collect_tool_product_records()

    assert len(records) == 21
    assert json.loads(prefs.read_text(encoding="utf-8")) == seed
    assert os.environ.get("LASERPROG_DISABLE_TOOL_PARAMETER_PERSISTENCE") is None


def test_vent_generator_now_has_creator_panel_workflow_and_modes() -> None:
    record = {item.id: item for item in collect_tool_product_records()}[TOOL_VENT_GENERATOR]
    assert record.panel_id == "vent.generator"
    assert record.field_count >= 15
    assert record.workflow_steps == ("pick_plane", "draw_path", "apply_mesh")
    assert record.workflow_requirements[0] == "face"
    assert record.modes == ("ADD", "MOD", "SUPP", "RST")
    assert {"refresh", "reset_path"}.issubset(set(record.action_ids))


def test_retired_diagnostic_and_catalog_tools_are_not_product_tools() -> None:
    ids = {item.id for item in collect_tool_product_records()}
    assert "tool_core_diagnostic" not in ids
    assert "gizmo_catalog" not in ids

def test_workflow_manager_declares_multi_object_selection_steps() -> None:
    step = ToolWorkflowManager().require_scene_objects("select", "Select parts")
    assert step.requirement == "scene_objects"


def test_quality_gate_runs_product_tool_audit() -> None:
    gate = (ROOT / "scripts" / "quality_gate.py").read_text(encoding="utf-8")
    assert "audit_tool_product_quality.py" in gate
    result = subprocess.run(
        [sys.executable, "scripts/audit_tool_product_quality.py", "--strict"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    assert "Tools checked: 21" in result.stdout
    assert "Issues       : 0" in result.stdout


def test_overlay_feedback_buttons_are_routed_through_creator_tools() -> None:
    records = collect_tool_product_records()
    overlay_records = [record for record in records if record.overlay_button_ids]

    assert {record.id for record in overlay_records} >= {
        "material",
        "modifier_repair",
        "modifier_simplify",
        "modifier_extrude_down",
        "modifier_hollow",
        "modifier_split",
        "vent_generator",
        "mechanical_motion",
    }
    assert all("overlay buttons are not routed to the tool" not in record.issues for record in overlay_records)
