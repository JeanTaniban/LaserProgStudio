# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

import _path_setup  # noqa: F401
from laserprog_studio.modifiers.registry import MODIFIER_SPECS, get_modifier_spec_for_tool
from laserprog_studio.parameters import ParameterSpec, defaults_for, validate_values
from laserprog_studio.rendering import DISPLAY_MODES, get_display_mode
from laserprog_studio.state import UiLayoutState
from laserprog_studio.tooling.ids import TOOL_ENGRAVING, TOOL_LAYFLAT, TOOL_MOD_SIMPLIFY, TOOL_MOD_SPLIT, TOOL_PRIMITIVE
from laserprog_studio.tooling.registry import get_tool_spec, iter_tool_specs, tool_label


class ExtensionArchitectureTest(unittest.TestCase):
    def test_existing_tools_are_registered(self) -> None:
        primitive = get_tool_spec(TOOL_PRIMITIVE)
        self.assertIsNotNone(primitive)
        self.assertEqual(primitive.label, "Primitives")
        self.assertEqual(primitive.panel_index, 1)
        self.assertFalse(primitive.requires_selection)
        self.assertEqual(primitive.selection_policy, "none")
        layflat = get_tool_spec(TOOL_LAYFLAT)
        self.assertIsNotNone(layflat)
        self.assertFalse(layflat.requires_selection)
        self.assertEqual(layflat.selection_policy, "none")
        engraving = get_tool_spec(TOOL_ENGRAVING)
        self.assertIsNotNone(engraving)
        self.assertFalse(engraving.requires_selection)
        self.assertEqual(engraving.selection_policy, "none")
        self.assertEqual(tool_label(TOOL_MOD_SPLIT), "Split modifier")
        self.assertIn(TOOL_MOD_SPLIT, {spec.id for spec in iter_tool_specs(category="modifier")})
        self.assertEqual(tool_label(TOOL_MOD_SIMPLIFY), "Simplify")
        self.assertIn(TOOL_MOD_SIMPLIFY, {spec.id for spec in iter_tool_specs(category="modifier")})

    def test_split_modifier_has_registry_entry(self) -> None:
        self.assertGreaterEqual(len(MODIFIER_SPECS), 2)
        split = get_modifier_spec_for_tool(TOOL_MOD_SPLIT)
        self.assertIsNotNone(split)
        self.assertTrue(split.interactive)
        self.assertEqual(split.operation_module, "laserprog_studio.modifiers.split_plane")
        simplify = get_modifier_spec_for_tool(TOOL_MOD_SIMPLIFY)
        self.assertIsNotNone(simplify)
        self.assertFalse(simplify.interactive)
        self.assertEqual(simplify.operation_module, "laserprog_studio.geometry_ops.simplify")

    def test_parameter_specs_validate_values(self) -> None:
        params = (
            ParameterSpec("segments", "Segments", "int", 32, min_value=3, max_value=256),
            ParameterSpec("ratio", "Ratio", "float", 0.5, min_value=0.0, max_value=1.0),
            ParameterSpec("mode", "Mode", "choice", "solid", choices=(("solid", "Solid"), ("wire", "Wire"))),
        )
        self.assertEqual(defaults_for(params), {"segments": 32, "ratio": 0.5, "mode": "solid"})
        self.assertEqual(validate_values(params, {"segments": 2, "ratio": 2.0, "mode": "bad"}), {"segments": 3, "ratio": 1.0, "mode": "solid"})

    def test_ui_layout_state_detects_light_only_when_both_side_panes_collapsed(self) -> None:
        state = UiLayoutState()
        state.update_from_splitter_sizes([0, 900, 0], threshold=12)
        self.assertEqual(state.mode, "light")
        state.update_from_splitter_sizes([220, 600, 0], threshold=12)
        self.assertEqual(state.mode, "full")
        self.assertEqual(state.last_full_splitter_sizes, [220, 600, 0])

    def test_display_modes_prepare_future_render_options(self) -> None:
        ids = {mode.id for mode in DISPLAY_MODES}
        self.assertEqual(ids, {"wireframe", "solid", "material"})
        self.assertTrue(get_display_mode("material").use_materials)
        self.assertEqual(get_display_mode("unknown").id, "wireframe")


if __name__ == "__main__":
    unittest.main()
