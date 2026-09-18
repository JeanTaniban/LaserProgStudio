"""Core public contracts for creator tools.

This module is the recommended import path for tool identity, lifecycle,
registration and version checks.  It deliberately avoids Qt/PyVista
objects so external tools can be imported in headless tests.
"""
from __future__ import annotations

from laserprog_studio.parameters import ParameterSpec
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType, ToolModeBase
from laserprog_studio.tool_core.workflow import ToolModeManager, ToolModeSpec, ToolModeState, ToolWorkflowManager, WorkflowState, WorkflowStep
from laserprog_studio.tool_core.commands import CommandStack, CompositeCommand, FunctionCommand
from laserprog_studio.tooling.base import ToolSpec
from laserprog_studio.tooling.tool import StudioTool

from .errors import ToolApiCompatibilityError, ToolApiError, ToolApiUsageError, ToolApiValidationError
from .lifecycle import CreatorTool
from .manifest import ToolManifest, ToolManifestCategory
from .runtime import CreatorStudioToolAdapter
from .versioning import CURRENT_TOOL_API_VERSION, TOOL_API_STABILITY, TOOL_API_VERSION, ToolApiVersion, require_tool_api



def register_tool(*args, **kwargs):
    """Register a Creator tool without importing the registry during tool bootstrap."""

    from .registration import register_tool as _register_tool

    return _register_tool(*args, **kwargs)


__all__ = [
    "CURRENT_TOOL_API_VERSION",
    "CommandStack",
    "CompositeCommand",
    "CreatorStudioToolAdapter",
    "CreatorTool",
    "FunctionCommand",
    "MouseButton",
    "ParameterSpec",
    "StudioTool",
    "TOOL_API_STABILITY",
    "TOOL_API_VERSION",
    "ToolApiCompatibilityError",
    "ToolApiError",
    "ToolApiUsageError",
    "ToolApiValidationError",
    "ToolApiVersion",
    "ToolContext",
    "ToolEvent",
    "ToolEventType",
    "ToolManifest",
    "ToolManifestCategory",
    "ToolModeBase",
    "ToolSpec",
    "ToolWorkflowManager",
    "WorkflowState",
    "WorkflowStep",
    "ToolModeManager",
    "ToolModeSpec",
    "ToolModeState",
    "register_tool",
    "require_tool_api",
]
