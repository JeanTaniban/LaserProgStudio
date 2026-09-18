# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tooling.ids import TOOL_FOLDING
from laserprog_studio.tooling.registry import get_tool_spec


ROOT = Path(__file__).resolve().parents[1]


def test_folding_registry_explicitly_allows_host_multi_selection() -> None:
    spec = get_tool_spec(TOOL_FOLDING)
    assert spec is not None
    assert spec.selection_policy == "none"
    assert spec.open_without_initial_selection is True
    assert spec.allow_multi_selection is True
    assert spec.allows_multi_selection is True


def test_tool_open_policy_keeps_multi_selection_for_opted_in_tools() -> None:
    source = (ROOT / "src/laserprog_studio/controllers/tool_selection_policy.py").read_text(encoding="utf-8")
    assert "if not spec.allows_multi_selection and len(self.selected_indices) > 1:" in source
    assert "self.selected_indices = self.selected_indices[-1:]" in source
