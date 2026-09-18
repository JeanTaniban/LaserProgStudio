# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

import _path_setup  # noqa: F401
from laserprog_studio.app_context import AppContext
from laserprog_studio.modifiers import get_mesh_modifier_for_tool, iter_mesh_modifiers
from laserprog_studio.parameters import ParameterSpec
from laserprog_studio.parameters.panel_factory import ParameterPanel
from laserprog_studio.tooling import (
    TOOL_JOINT,
    TOOL_MOD_SIMPLIFY,
    TOOL_MOD_SPLIT,
    TOOL_PRIMITIVE,
    ToolSpec,
    get_studio_tool,
    get_tool_spec,
    iter_studio_tools,
    register_tool_spec,
    reset_tool_registry,
    unregister_tool_spec,
)
from laserprog_studio.tooling.extension_api import ToolExtensionSpec, register_tool_extension, unregister_tool_extension
from laserprog_studio.ui.toolbar_catalog import ToolbarItemSpec, get_toolbar_item_spec, reset_toolbar_item_registry


class DummyOwner:
    def __init__(self) -> None:
        from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState

        self.selection_state = SelectionState()
        self.transform_state = TransformState()
        self.tool_state = ToolState(active_tool="none")
        self.preview_state = PreviewState()
        self.ui_layout_state = UiLayoutState()
        self.render_state = RenderState()
        self.clipboard_state = ClipboardState()
        self.calls: list[tuple[str, dict]] = []
        self.mesh_store = object()
        self.scene_renderer = object()

    def _clear_joint_selection_state(self, **kwargs) -> None:
        self.calls.append(("joint_clear", kwargs))

    def ui_log(self, message: str) -> None:
        self.calls.append(("log", {"message": message}))


class Pass16RuntimeContractsTest(unittest.TestCase):
    def test_tools_are_runtime_objects_not_only_specs(self) -> None:
        primitive = get_studio_tool(TOOL_PRIMITIVE)
        joint = get_studio_tool(TOOL_JOINT)
        self.assertIsNotNone(primitive)
        self.assertIsNotNone(joint)
        self.assertEqual(primitive.spec.id, TOOL_PRIMITIVE)
        self.assertTrue(primitive.can_open(None, selected_count=0))
        self.assertFalse(joint.can_open(None, selected_count=0))
        self.assertTrue(joint.can_open(None, selected_count=2))
        self.assertIn(TOOL_PRIMITIVE, {tool.spec.id for tool in iter_studio_tools(category="tool")})

    def test_legacy_tool_adapter_invokes_owner_hooks_through_context(self) -> None:
        spec = ToolSpec(
            id="legacy_hook_probe",
            label="Legacy hook probe",
            category="tool",
            panel_index=98,
            button_attr="btn_tool_legacy_hook_probe",
            selection_policy="none",
            close_hook="_clear_joint_selection_state",
            display_order=998,
        )
        try:
            register_tool_spec(spec)
            owner = DummyOwner()
            context = AppContext.from_window(owner)
            runtime = get_studio_tool("legacy_hook_probe")
            runtime.on_close(context, render=False)
            self.assertEqual(owner.calls[0][0], "joint_clear")
            self.assertEqual(owner.calls[0][1], {"render": False})
        finally:
            unregister_tool_spec("legacy_hook_probe")
            reset_tool_registry()


    def test_extension_api_registers_tool_and_toolbar_item_together(self) -> None:
        extension = ToolExtensionSpec(
            tool=ToolSpec(
                id="future_bundle",
                label="Future bundle",
                category="tool",
                panel_index=100,
                button_attr="btn_tool_future_bundle",
                selection_policy="none",
                display_order=1000,
            ),
            toolbar_item=ToolbarItemSpec(
                id="tool:future_bundle",
                code="FBD",
                name="Future bundle",
                description="Bundled extension registration.",
                category="tool",
                kind="tool",
                order=1000,
                tool_id="future_bundle",
                button_attr="btn_tool_future_bundle",
                default_visible=False,
            ),
        )
        try:
            register_tool_extension(extension)
            self.assertIsNotNone(get_studio_tool("future_bundle"))
            self.assertIsNotNone(get_toolbar_item_spec("tool:future_bundle"))
        finally:
            unregister_tool_extension("future_bundle", toolbar_item_id="tool:future_bundle")
            reset_tool_registry()
            reset_toolbar_item_registry()

    def test_tool_registry_can_register_future_hook_based_tool_without_qt(self) -> None:
        spec = ToolSpec(
            id="future_probe",
            label="Future probe",
            category="tool",
            panel_index=99,
            button_attr="btn_tool_future_probe",
            selection_policy="none",
            open_hook="_open_future_probe",
            display_order=999,
        )
        try:
            register_tool_spec(spec)
            self.assertEqual(get_tool_spec("future_probe"), spec)
            runtime = get_studio_tool("future_probe")
            self.assertIsNotNone(runtime)
            self.assertEqual(runtime.spec.id, "future_probe")
            self.assertIn("future_probe", {tool.spec.id for tool in iter_studio_tools(category="tool")})
        finally:
            unregister_tool_spec("future_probe")
            reset_tool_registry()

    def test_modifiers_are_runtime_objects_too(self) -> None:
        split = get_mesh_modifier_for_tool(TOOL_MOD_SPLIT)
        self.assertIsNotNone(split)
        self.assertTrue(split.can_start(None, selected_count=1))
        self.assertFalse(split.can_start(None, selected_count=0))
        ids = {modifier.spec.id for modifier in iter_mesh_modifiers()}
        self.assertIn("split_plane", ids)
        self.assertIn("simplify", ids)
        simplify = get_mesh_modifier_for_tool(TOOL_MOD_SIMPLIFY)
        self.assertIsNotNone(simplify)
        self.assertTrue(simplify.can_start(None, selected_count=1))
        self.assertFalse(split.preview(None, {}).ok)

    def test_parameter_panel_bundle_exposes_set_and_reset_contract_without_qt(self) -> None:
        class Editor:
            def __init__(self, value=0):
                self._value = value
            def value(self):
                return self._value
            def setValue(self, value):
                self._value = value

        params = (ParameterSpec("segments", "Segments", "int", 32, min_value=3, max_value=256),)
        bundle = ParameterPanel(widget=None, editors={"segments": Editor()}, parameters=params)
        bundle.set_values({"segments": 2})
        self.assertEqual(bundle.values()["segments"], 3)
        bundle.set_values({"segments": 100})
        self.assertEqual(bundle.values()["segments"], 100)
        bundle.reset()
        self.assertEqual(bundle.values()["segments"], 32)


if __name__ == "__main__":
    unittest.main()
