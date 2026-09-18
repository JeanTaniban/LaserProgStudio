# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from .base import ToolSpec
from .registry import register_tool_spec, unregister_tool_spec
from .tool import StudioTool
from ..ui.toolbar_catalog import ToolbarItemSpec, register_toolbar_item, unregister_toolbar_item


@dataclass(frozen=True, slots=True)
class ToolExtensionSpec:
    """Bundle all metadata needed to add one Studio tool cleanly.

    `ToolSpec` makes the tool available to the runtime/lifecycle layer.
    `ToolbarItemSpec` is optional and makes it visible in the configurable top
    toolbar and the + Tools palette. Keeping both in a single bundle reduces the
    risk of registering one side without the other when integrating extensions.
    """

    tool: ToolSpec
    toolbar_item: ToolbarItemSpec | None = None
    runtime_tool: StudioTool | None = None


def register_tool_extension(extension: ToolExtensionSpec, *, replace: bool = False) -> None:
    """Register a runtime tool plus its optional toolbar entry atomically."""

    register_tool_spec(extension.tool, runtime_tool=extension.runtime_tool, replace=replace)
    try:
        if extension.toolbar_item is not None:
            register_toolbar_item(extension.toolbar_item, replace=replace)
    except Exception:
        unregister_tool_spec(extension.tool.id)
        raise


def unregister_tool_extension(tool_id: str, *, toolbar_item_id: str | None = None) -> None:
    """Unregister a tool and, when known, its toolbar/palette entry."""

    if toolbar_item_id:
        unregister_toolbar_item(toolbar_item_id)
    unregister_tool_spec(tool_id)
