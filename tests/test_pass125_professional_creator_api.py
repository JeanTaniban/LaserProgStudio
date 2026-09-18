# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from laserprog_studio.tool_api import (
    TOOL_API_VERSION,
    ToolApiCompatibilityError,
    ToolApiValidationError,
    ToolContext,
    ToolManifest,
    actors,
    audit,
    inspector,
    require_tool_api,
)


def test_pass125_creator_api_has_version_and_manifest_contract() -> None:
    assert TOOL_API_VERSION == "0.13.0"
    assert str(require_tool_api("0.9.0", max_major=0)) == "0.13.0"
    with pytest.raises(ToolApiCompatibilityError):
        require_tool_api("99.0.0")

    manifest = ToolManifest(
        id="com.example.safe_tool",
        label="Safe Tool",
        entrypoint="example.safe:create_tool",
        api_min="0.13.0",
        permissions=("scene:read",),
    )
    manifest.validate_runtime()
    assert manifest.to_dict()["id"] == "com.example.safe_tool"
    assert ToolManifest.from_dict(manifest.to_dict()).permissions == ("scene:read",)

    with pytest.raises(ToolApiValidationError, match="entrypoint"):
        ToolManifest(id="broken", label="Broken", entrypoint="missing_separator")


def test_pass125_actor_registry_attaches_owner_rejects_silent_overwrite_and_invalidates_cache() -> None:
    ctx = ToolContext()
    registry = ctx.actor_registry("tool.pro")
    ctx.scene_cache.rebuild(ctx, scope="snap")
    version_before = ctx.scene_cache.version

    actor = registry.add(actors.point("handle", (0.0, 0.0, 0.0)))
    assert actor.owner_tool == "tool.pro"
    assert ctx.scene_cache.valid is False
    assert ctx.scene_cache.version > version_before

    with pytest.raises(ToolApiValidationError, match="already registered"):
        registry.add(actors.point("handle", (1.0, 0.0, 0.0)))

    registry.add(actors.point("handle", (1.0, 0.0, 0.0)), replace=True)
    assert registry.get("handle").points[0] == (1.0, 0.0, 0.0)


def test_pass125_inspector_field_state_is_dynamic_and_diagnostic_friendly() -> None:
    ctx = ToolContext()
    ctx.inspector.set_panel(
        inspector.panel(
            "Pro Panel",
            sections=[
                inspector.section(
                    "Geometry",
                    [
                        inspector.float_field("length", "Length", default=10.0),
                        inspector.button("apply", "Apply"),
                    ],
                )
            ],
        )
    )

    ctx.inspector.set_error("length", "Length is too small")
    ctx.inspector.set_readonly("length", True)
    state = ctx.inspector.field_state("length")
    assert state.error == "Length is too small"
    assert state.readonly is True
    assert ctx.inspector.describe()["field_states"]["length"]["error"] == "Length is too small"
    with pytest.raises(ValueError, match="read-only"):
        ctx.inspector.update_value("length", 20.0)

    ctx.inspector.set_enabled("apply", False)
    with pytest.raises(ValueError, match="disabled"):
        ctx.inspector.trigger("apply")


def test_pass125_command_transaction_rolls_back_on_failure() -> None:
    ctx = ToolContext()
    state: list[str] = []

    with pytest.raises(RuntimeError, match="boom"):
        with ctx.commands.transaction("failing transaction"):
            ctx.commands.do("add a", do=lambda: state.append("a"), undo=lambda: state.remove("a"))
            raise RuntimeError("boom")

    assert state == []
    assert ctx.commands.undo_count == 0


def test_pass125_external_examples_pass_import_audit() -> None:
    for path in Path("examples/tool_creator").glob("*.py"):
        audit.assert_no_forbidden_imports(path)
