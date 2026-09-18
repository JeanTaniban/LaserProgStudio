# -*- coding: utf-8 -*-
from __future__ import annotations

from ..tooling.ids import TOOL_MOD_EXTRUDE_DOWN, TOOL_MOD_HOLLOW, TOOL_MOD_RELIEF, TOOL_MOD_SIMPLIFY, TOOL_MOD_SPLIT
from .base import ModifierSpec
from .modifier import MeshModifier, ToolHostedModifier

MODIFIER_SPECS: tuple[ModifierSpec, ...] = (

    ModifierSpec(
        id="relief",
        label="Relief",
        tool_id=TOOL_MOD_RELIEF,
        requires_selection=True,
        interactive=True,
        panel_index=9,
        operation_module="laserprog_studio.geometry_ops.text_relief",
    ),
    ModifierSpec(
        id="simplify",
        label="Simplify",
        tool_id=TOOL_MOD_SIMPLIFY,
        requires_selection=True,
        interactive=False,
        panel_index=8,
        operation_module="laserprog_studio.geometry_ops.simplify",
    ),

    ModifierSpec(
        id="extrude_down",
        label="Extrude down",
        tool_id=TOOL_MOD_EXTRUDE_DOWN,
        requires_selection=True,
        interactive=True,
        panel_index=10,
        operation_module="laserprog_studio.geometry_ops.extrude_down",
    ),

    ModifierSpec(
        id="hollow",
        label="Hollow",
        tool_id=TOOL_MOD_HOLLOW,
        requires_selection=True,
        interactive=False,
        panel_index=11,
        operation_module="laserprog_studio.geometry_ops.hollow",
    ),
    ModifierSpec(
        id="split_plane",
        label="Split by plane",
        tool_id=TOOL_MOD_SPLIT,
        requires_selection=True,
        interactive=True,
        panel_index=7,
        operation_module="laserprog_studio.modifiers.split_plane",
    ),
)

_MODIFIER_BY_ID = {spec.id: spec for spec in MODIFIER_SPECS}
_MODIFIER_BY_TOOL_ID = {spec.tool_id: spec for spec in MODIFIER_SPECS}


def get_modifier_spec(modifier_id: str) -> ModifierSpec | None:
    return _MODIFIER_BY_ID.get(modifier_id)


def get_modifier_spec_for_tool(tool_id: str) -> ModifierSpec | None:
    return _MODIFIER_BY_TOOL_ID.get(tool_id)


_RUNTIME_MODIFIER_BY_ID: dict[str, MeshModifier] = {spec.id: ToolHostedModifier(spec) for spec in MODIFIER_SPECS}
_RUNTIME_MODIFIER_BY_TOOL_ID: dict[str, MeshModifier] = {spec.tool_id: _RUNTIME_MODIFIER_BY_ID[spec.id] for spec in MODIFIER_SPECS}


def get_mesh_modifier(modifier_id: str) -> MeshModifier | None:
    return _RUNTIME_MODIFIER_BY_ID.get(modifier_id)


def get_mesh_modifier_for_tool(tool_id: str) -> MeshModifier | None:
    return _RUNTIME_MODIFIER_BY_TOOL_ID.get(tool_id)


def iter_mesh_modifiers() -> tuple[MeshModifier, ...]:
    return tuple(_RUNTIME_MODIFIER_BY_ID[spec.id] for spec in MODIFIER_SPECS if spec.id in _RUNTIME_MODIFIER_BY_ID)
