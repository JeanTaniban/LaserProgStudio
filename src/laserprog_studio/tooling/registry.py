# -*- coding: utf-8 -*-
from __future__ import annotations

from .base import ToolSpec
from .acoustic_diffuser_tool import AcousticDiffuserTool
from .box_tool import BoxTool
from .cavity_volume_tool import CavityVolumeTool
from .engraving_roles_tool import EngravingRolesTool
from .hollow_tool import HollowTool
from .primitive_tool import PrimitiveTool
from .repair_tool import RepairMeshTool
from .simplify_tool import SimplifyTool
from .extrude_down_tool import ExtrudeDownTool
from .plan_trace_2d_tool import PlanTrace2DTool
from .joint_tool import JointTool
from .layflat_tool import LayflatTool
from .material_tool import MaterialTool
from .relief_tool import ReliefTool
from .split_tool import SplitPlaneTool
from .texture_projection_creator_tool import TextureProjectionTool
from .vent_generator_tool import VentGeneratorTool
from .mechanical_motion_tool import MechanicalMotionTool
from .folding_tool import FoldingTool
from .cloth_tool import ClothTool
from .smart_surface_selection_test_tool import SmartSurfaceSelectionTestTool
from .tool import HookToolAdapter, StudioTool
from ..primitives import PRIMITIVE_TOOL_PARAMETERS
from .ids import (
    TOOL_BOX,
    TOOL_ENGRAVING,
    TOOL_MATERIAL,
    TOOL_TEXTURE_PROJECTION,
    TOOL_JOINT,
    TOOL_LAYFLAT,
    TOOL_MOD_SPLIT,
    TOOL_MOD_SIMPLIFY,
    TOOL_MOD_RELIEF,
    TOOL_MOD_EXTRUDE_DOWN,
    TOOL_MOD_HOLLOW,
    TOOL_MOD_REPAIR,
    TOOL_NONE,
    TOOL_PRIMITIVE,
    TOOL_PLAN_TRACE,
    TOOL_VENT_GENERATOR,
    TOOL_MECHANICAL_MOTION,
    TOOL_FOLDING,
    TOOL_CLOTH,
    TOOL_VOLUME_MEASURE,
    TOOL_ACOUSTIC_DIFFUSER,
    TOOL_SMART_SURFACE_SELECTION_TEST,
)

_BUILTIN_TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        id=TOOL_PRIMITIVE,
        label="Primitives",
        category="tool",
        panel_index=1,
        button_attr="btn_tool_primitive",
        selection_policy="none",
        display_order=10,
        parameters=PRIMITIVE_TOOL_PARAMETERS,
    ),
    ToolSpec(
        id=TOOL_BOX,
        label="Box generator",
        category="tool",
        panel_index=2,
        button_attr="btn_tool_box",
        clear_selection_on_open=True,
        display_order=20,
    ),
    ToolSpec(
        id=TOOL_LAYFLAT,
        label="Lay flat",
        category="tool",
        panel_index=3,
        button_attr="btn_tool_layflat",
        selection_policy="none",
        display_order=30,
    ),
    ToolSpec(
        id=TOOL_JOINT,
        label="Joint builder",
        category="tool",
        panel_index=4,
        button_attr="btn_tool_joint",
        selection_policy="multi",
        allow_multi_selection=True,
        open_without_initial_selection=True,
        display_order=40,
    ),
    ToolSpec(
        id=TOOL_ENGRAVING,
        label="Engraving roles",
        category="tool",
        panel_index=5,
        button_attr="btn_tool_engraving",
        selection_policy="none",
        active_index_from_selection=True,
        display_order=50,
    ),

    ToolSpec(
        id=TOOL_MATERIAL,
        label="Materials",
        category="tool",
        panel_index=6,
        button_attr="btn_tool_material",
        selection_policy="multi",
        allow_multi_selection=True,
        open_without_initial_selection=True,
        display_order=55,
    ),

    ToolSpec(
        id=TOOL_TEXTURE_PROJECTION,
        label="Texture projection",
        category="tool",
        panel_index=12,
        button_attr="btn_tool_texture_projection",
        selection_policy="none",
        display_order=60,
    ),


    ToolSpec(
        id=TOOL_PLAN_TRACE,
        label="Plan tracer",
        category="tool",
        panel_index=30,
        button_attr="btn_tool_plan_trace",
        selection_policy="none",
        display_order=65,
    ),
    ToolSpec(
        id=TOOL_VENT_GENERATOR,
        label="Vent generator",
        category="tool",
        panel_index=31,
        button_attr="btn_tool_vent_generator",
        selection_policy="none",
        display_order=66,
    ),
    ToolSpec(
        id=TOOL_MECHANICAL_MOTION,
        label="Mechanical motion",
        category="tool",
        panel_index=32,
        button_attr="btn_tool_mechanical_motion",
        selection_policy="none",
        open_without_initial_selection=True,
        display_order=66,
    ),
    ToolSpec(
        id=TOOL_FOLDING,
        label="Folding",
        category="tool",
        panel_index=33,
        button_attr="btn_tool_folding",
        selection_policy="none",
        allow_multi_selection=True,
        open_without_initial_selection=True,
        display_order=67,
    ),
    ToolSpec(
        id=TOOL_CLOTH,
        label="Cloth",
        category="tool",
        panel_index=34,
        button_attr="btn_tool_cloth",
        selection_policy="none",
        open_without_initial_selection=True,
        display_order=68,
    ),

    ToolSpec(
        id=TOOL_SMART_SURFACE_SELECTION_TEST,
        label="Selection API test",
        category="tool",
        panel_index=35,
        button_attr="btn_tool_smart_surface_selection_test",
        selection_policy="none",
        open_without_initial_selection=True,
        display_order=69,
    ),

    ToolSpec(
        id=TOOL_VOLUME_MEASURE,
        label="Cavity volume",
        category="tool",
        panel_index=14,
        button_attr="btn_tool_volume_measure",
        selection_policy="multi",
        active_index_from_selection=True,
        display_order=67,
    ),

    ToolSpec(
        id=TOOL_ACOUSTIC_DIFFUSER,
        label="Acoustic diffuser",
        category="tool",
        panel_index=15,
        button_attr="btn_tool_acoustic_diffuser",
        selection_policy="none",
        display_order=68,
    ),

    ToolSpec(
        id=TOOL_MOD_RELIEF,
        label="Relief",
        category="modifier",
        panel_index=9,
        button_attr="btn_mod_relief",
        selection_policy="single",
        active_index_from_selection=True,
        display_order=85,
    ),

    ToolSpec(
        id=TOOL_MOD_REPAIR,
        label="Repair mesh",
        category="modifier",
        panel_index=13,
        button_attr="btn_mod_repair",
        selection_policy="multi",
        display_order=89,
    ),

    ToolSpec(
        id=TOOL_MOD_SIMPLIFY,
        label="Simplify",
        category="modifier",
        panel_index=8,
        button_attr="btn_mod_simplify",
        selection_policy="multi",
        display_order=90,
    ),

    ToolSpec(
        id=TOOL_MOD_EXTRUDE_DOWN,
        label="Extrude down",
        category="modifier",
        panel_index=10,
        button_attr="btn_mod_extrude_down",
        selection_policy="multi",
        display_order=95,
    ),

    ToolSpec(
        id=TOOL_MOD_HOLLOW,
        label="Hollow",
        category="modifier",
        panel_index=11,
        button_attr="btn_mod_hollow",
        selection_policy="multi",
        display_order=97,
    ),
    ToolSpec(
        id=TOOL_MOD_SPLIT,
        label="Split modifier",
        category="modifier",
        panel_index=7,
        button_attr="btn_mod_split",
        selection_policy="multi",
        display_order=100,
    ),
)


# Public registry snapshots are rebuilt by reset_tool_registry() and extension
# registration. Existing imports keep working, while new code should use the
# registry functions below.
TOOL_SPECS: tuple[ToolSpec, ...] = ()
_TOOL_BY_ID: dict[str, ToolSpec] = {}
_STUDIO_TOOL_BY_ID: dict[str, StudioTool] = {}
_tool_spec_registry: dict[str, ToolSpec] = {}
_tool_registration_order: list[str] = []


def _make_runtime_tool(spec: ToolSpec) -> StudioTool:
    if spec.id == TOOL_PRIMITIVE:
        return PrimitiveTool(spec)
    if spec.id == TOOL_BOX:
        return BoxTool(spec)
    if spec.id == TOOL_ACOUSTIC_DIFFUSER:
        return AcousticDiffuserTool(spec)
    if spec.id == TOOL_VOLUME_MEASURE:
        return CavityVolumeTool(spec)
    if spec.id == TOOL_ENGRAVING:
        return EngravingRolesTool(spec)
    if spec.id == TOOL_MOD_REPAIR:
        return RepairMeshTool(spec)
    if spec.id == TOOL_MOD_SIMPLIFY:
        return SimplifyTool(spec)
    if spec.id == TOOL_LAYFLAT:
        return LayflatTool(spec)
    if spec.id == TOOL_JOINT:
        return JointTool(spec)
    if spec.id == TOOL_MATERIAL:
        return MaterialTool(spec)
    if spec.id == TOOL_TEXTURE_PROJECTION:
        return TextureProjectionTool(spec)
    if spec.id == TOOL_MOD_RELIEF:
        return ReliefTool(spec)
    if spec.id == TOOL_MOD_EXTRUDE_DOWN:
        return ExtrudeDownTool(spec)
    if spec.id == TOOL_MOD_SPLIT:
        return SplitPlaneTool(spec)
    if spec.id == TOOL_MOD_HOLLOW:
        return HollowTool(spec)
    if spec.id == TOOL_PLAN_TRACE:
        return PlanTrace2DTool(spec)
    if spec.id == TOOL_VENT_GENERATOR:
        return VentGeneratorTool(spec)
    if spec.id == TOOL_MECHANICAL_MOTION:
        return MechanicalMotionTool(spec)
    if spec.id == TOOL_FOLDING:
        return FoldingTool(spec)
    if spec.id == TOOL_CLOTH:
        return ClothTool(spec)
    if spec.id == TOOL_SMART_SURFACE_SELECTION_TEST:
        return SmartSurfaceSelectionTestTool(spec)
    return HookToolAdapter(spec)


def _sorted_tool_specs() -> tuple[ToolSpec, ...]:
    return tuple(sorted(_tool_spec_registry.values(), key=lambda s: (int(s.display_order), s.category, s.id)))


def _rebuild_compat_maps() -> None:
    global TOOL_SPECS, _TOOL_BY_ID
    TOOL_SPECS = _sorted_tool_specs()
    _TOOL_BY_ID = {spec.id: spec for spec in TOOL_SPECS}


def validate_tool_registry(specs: tuple[ToolSpec, ...] | None = None) -> tuple[ToolSpec, ...]:
    """Validate the Studio tool registry without importing Qt/PyVista.

    The checks intentionally focus on metadata that future contributors are most
    likely to duplicate accidentally: stable ids and button attributes.
    Panel indexes are allowed to overlap only when an extension deliberately
    reuses an existing panel through replacement.
    """

    seen_ids: set[str] = set()
    seen_attrs: set[str] = set()
    validated: list[ToolSpec] = []
    for spec in specs if specs is not None else tuple(_tool_spec_registry.values()):
        if not spec.id or not str(spec.id).strip():
            raise ValueError("ToolSpec.id must be non-empty")
        if spec.category not in {"tool", "modifier"}:
            raise ValueError(f"Invalid tool category: {spec.category!r}")
        if spec.selection_policy not in {"none", "single", "multi"}:
            raise ValueError(f"Invalid selection policy for {spec.id!r}: {spec.selection_policy!r}")
        if spec.panel_index < 0:
            raise ValueError(f"Tool {spec.id!r} has an invalid panel index: {spec.panel_index!r}")
        if spec.id in seen_ids:
            raise ValueError(f"Duplicate tool id: {spec.id!r}")
        seen_ids.add(spec.id)
        if spec.button_attr:
            if spec.button_attr in seen_attrs:
                raise ValueError(f"Duplicate tool button_attr: {spec.button_attr!r}")
            seen_attrs.add(spec.button_attr)
        validated.append(spec)
    return tuple(validated)


def register_tool_spec(spec: ToolSpec, *, runtime_tool: StudioTool | None = None, replace: bool = False) -> None:
    """Register a Studio tool or modifier at startup.

    Parameters
    ----------
    spec:
        Static metadata consumed by lifecycle, selection-policy and UI code.
    runtime_tool:
        Optional object implementing ``StudioTool``. When omitted, LaserProg uses
        ``HookToolAdapter`` so lightweight extension specs can still delegate to
        owner/controller methods. Built-in tools should register explicit runtime
        classes instead.
    replace:
        Set to True only when intentionally overriding an existing tool id.
    """

    if spec.id in _tool_spec_registry and not replace:
        raise ValueError(f"Tool already registered: {spec.id!r}")

    existed = spec.id in _tool_spec_registry
    previous_spec = _tool_spec_registry.get(spec.id)
    previous_tool = _STUDIO_TOOL_BY_ID.get(spec.id)
    added_order_entry = False
    if not existed:
        _tool_registration_order.append(spec.id)
        added_order_entry = True
    _tool_spec_registry[spec.id] = spec
    _STUDIO_TOOL_BY_ID[spec.id] = runtime_tool if runtime_tool is not None else _make_runtime_tool(spec)
    try:
        validate_tool_registry()
    except Exception:
        if existed and previous_spec is not None:
            _tool_spec_registry[spec.id] = previous_spec
            if previous_tool is not None:
                _STUDIO_TOOL_BY_ID[spec.id] = previous_tool
        else:
            _tool_spec_registry.pop(spec.id, None)
            _STUDIO_TOOL_BY_ID.pop(spec.id, None)
        if added_order_entry:
            try:
                _tool_registration_order.remove(spec.id)
            except ValueError:
                pass
        raise
    _rebuild_compat_maps()


def unregister_tool_spec(tool_id: str) -> None:
    tool_id = str(tool_id)
    if tool_id in _tool_spec_registry:
        _tool_spec_registry.pop(tool_id, None)
        _STUDIO_TOOL_BY_ID.pop(tool_id, None)
        try:
            _tool_registration_order.remove(tool_id)
        except ValueError:
            pass
        _rebuild_compat_maps()


def reset_tool_registry() -> None:
    _tool_spec_registry.clear()
    _STUDIO_TOOL_BY_ID.clear()
    _tool_registration_order.clear()
    for spec in _BUILTIN_TOOL_SPECS:
        register_tool_spec(spec, replace=True)


def get_tool_spec(tool_id: str | None) -> ToolSpec | None:
    if tool_id in (None, TOOL_NONE):
        return None
    return _TOOL_BY_ID.get(str(tool_id))


def tool_label(tool_id: str | None) -> str:
    if tool_id in (None, TOOL_NONE):
        return "No tool"
    spec = get_tool_spec(tool_id)
    return spec.label if spec is not None else "Tool"


def iter_tool_specs(*, category: str | None = None) -> tuple[ToolSpec, ...]:
    specs = TOOL_SPECS
    if category is None:
        return tuple(specs)
    return tuple(spec for spec in specs if spec.category == category)


def get_studio_tool(tool_id: str | None) -> StudioTool | None:
    if tool_id in (None, TOOL_NONE):
        return None
    return _STUDIO_TOOL_BY_ID.get(str(tool_id))


def iter_studio_tools(*, category: str | None = None) -> tuple[StudioTool, ...]:
    specs = iter_tool_specs(category=category)
    return tuple(_STUDIO_TOOL_BY_ID[spec.id] for spec in specs if spec.id in _STUDIO_TOOL_BY_ID)


reset_tool_registry()
