"""Small registration facade for external tool creators."""
from __future__ import annotations

from typing import Literal

from laserprog_studio.parameters import ParameterSpec
from laserprog_studio.tooling.base import SelectionPolicy, ToolCategory, ToolSpec
from laserprog_studio.tooling.extension_api import ToolExtensionSpec, register_tool_extension
from laserprog_studio.tooling.tool import StudioTool
from laserprog_studio.ui.toolbar_catalog import ToolbarItemSpec

from .errors import ToolApiValidationError
from .lifecycle import CreatorTool
from .runtime import CreatorStudioToolAdapter

ToolbarVisibility = Literal["toolbar", "palette", "hidden"]


def register_tool(
    *,
    id: str,
    label: str,
    runtime: StudioTool | CreatorTool | None = None,
    category: ToolCategory = "tool",
    panel_index: int = 900,
    selection_policy: SelectionPolicy = "none",
    parameters: tuple[ParameterSpec, ...] = (),
    toolbar_code: str | None = None,
    description: str | None = None,
    display_order: int | None = None,
    button_attr: str | None = None,
    toolbar_visibility: ToolbarVisibility = "palette",
    replace: bool = False,
) -> ToolExtensionSpec:
    """Register a Studio tool using one concise call.

    This wraps the existing ``ToolSpec`` + ``ToolbarItemSpec`` extension system
    without hiding it.  The returned ``ToolExtensionSpec`` is useful in tests and
    allows an extension module to unregister/re-register deterministically.
    """

    tool_id = _clean_required("id", id)
    tool_label = _clean_required("label", label)
    if not (tool_id.replace(".", "_").replace("-", "_").replace(":", "_").replace("_", "").isalnum()):
        raise ToolApiValidationError(
            f"Tool id {tool_id!r} contains unsupported characters. Use letters, numbers, '.', '-' or '_'."
        )
    order = int(display_order if display_order is not None else panel_index)
    tool_spec = ToolSpec(
        id=tool_id,
        label=tool_label,
        category=category,
        panel_index=int(panel_index),
        button_attr=button_attr,
        selection_policy=selection_policy,
        display_order=order,
        parameters=tuple(parameters),
    )
    toolbar_item = None
    if toolbar_visibility != "hidden":
        code = toolbar_code or _default_toolbar_code(tool_label, tool_id)
        toolbar_item = ToolbarItemSpec(
            id=f"{category}:{tool_id}",
            code=code,
            name=tool_label,
            description=description or f"Open {tool_label}.",
            category=category,
            kind=category,
            order=order,
            tool_id=tool_id,
            button_attr=button_attr,
            default_visible=toolbar_visibility == "toolbar",
        )
    runtime_tool = CreatorStudioToolAdapter(tool_spec, runtime) if isinstance(runtime, CreatorTool) else runtime
    extension = ToolExtensionSpec(tool=tool_spec, toolbar_item=toolbar_item, runtime_tool=runtime_tool)
    register_tool_extension(extension, replace=replace)
    return extension


def _clean_required(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise ToolApiValidationError(f"Tool registration field {name!r} must be non-empty.")
    return text


def _default_toolbar_code(label: str, tool_id: str) -> str:
    words = [part for part in str(label).replace("_", " ").split() if part]
    if len(words) >= 3:
        return "".join(word[0] for word in words[:3]).upper()
    if len(words) == 2:
        return (words[0][:2] + words[1][:1]).upper()
    base = (words[0] if words else str(tool_id)).upper()
    return (base[:3] if len(base) >= 3 else base.ljust(3, "X"))


__all__ = ["ToolbarVisibility", "register_tool"]
