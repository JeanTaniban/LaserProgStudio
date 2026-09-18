# -*- coding: utf-8 -*-
from __future__ import annotations

from ..parameters import ParameterSpec, defaults_for, validate_values
from .base import PrimitiveBuildRequest, PrimitiveSpec
from .generators import build_box, build_cone, build_custom, build_cylinder, build_hex_prism, build_pyramid, build_sphere, build_triangular_prism, estimate_triangle_count

PRIMITIVE_TYPE_PARAM = ParameterSpec(
    "primitive_id",
    "Type",
    "choice",
    "box",
    choices=(
        ("box", "Box/Cube"),
        ("cylinder", "Cylinder"),
        ("sphere", "Sphere"),
        ("cone", "Cone"),
        ("pyramid", "Pyramid"),
        ("triangular_prism", "Triangular prism"),
        ("hex_prism", "Hex prism"),
        ("custom", "Custom"),
    ),
)
COMMON_PRIMITIVE_PARAMETERS: tuple[ParameterSpec, ...] = (
    ParameterSpec("size_x", "Size X", "float", 40.0, min_value=0.001, max_value=100000, step=1.0),
    ParameterSpec("size_y", "Size Y", "float", 40.0, min_value=0.001, max_value=100000, step=1.0),
    ParameterSpec("size_z", "Size Z", "float", 40.0, min_value=0.001, max_value=100000, step=1.0),
    ParameterSpec("pos_x", "Position X", "float", 0.0, min_value=-100000, max_value=100000, step=1.0),
    ParameterSpec("pos_y", "Position Y", "float", 0.0, min_value=-100000, max_value=100000, step=1.0),
    ParameterSpec("pos_z", "Position Z", "float", 0.0, min_value=-100000, max_value=100000, step=1.0),
    ParameterSpec("color", "Color", "text", "#B8B8B8", tooltip="Hex color used for display and engraving roles."),
)
CUSTOM_KIND_PARAMETER = ParameterSpec(
    "custom_kind",
    "Custom shape",
    "choice",
    "cylinder",
    choices=(("cylinder", "Cylinder"), ("sphere", "Sphere"), ("cone", "Cone")),
)
SEGMENT_PARAMETER = ParameterSpec("segments", "Sides", "int", 64, min_value=3, max_value=512, step=1, tooltip="Radial resolution for cylinders/cones. Use 6 for a hexagon.")
SPHERE_THETA_PARAMETER = ParameterSpec("theta_resolution", "Horizontal segments", "int", 64, min_value=3, max_value=512, step=1)
SPHERE_PHI_PARAMETER = ParameterSpec("phi_resolution", "Vertical segments", "int", 32, min_value=3, max_value=256, step=1)

PRIMITIVE_TOOL_PARAMETERS: tuple[ParameterSpec, ...] = (
    PRIMITIVE_TYPE_PARAM,
    CUSTOM_KIND_PARAMETER,
    *COMMON_PRIMITIVE_PARAMETERS,
    SEGMENT_PARAMETER,
    SPHERE_THETA_PARAMETER,
    SPHERE_PHI_PARAMETER,
)

PRIMITIVE_SPECS: tuple[PrimitiveSpec, ...] = (
    PrimitiveSpec("box", "Box/Cube", "box", COMMON_PRIMITIVE_PARAMETERS, build_box, 10),
    PrimitiveSpec("cylinder", "Cylinder", "cylinder", (*COMMON_PRIMITIVE_PARAMETERS, SEGMENT_PARAMETER), build_cylinder, 20),
    PrimitiveSpec("sphere", "Sphere", "sphere", (*COMMON_PRIMITIVE_PARAMETERS, SPHERE_THETA_PARAMETER, SPHERE_PHI_PARAMETER), build_sphere, 30),
    PrimitiveSpec("cone", "Cone", "cone", (*COMMON_PRIMITIVE_PARAMETERS, SEGMENT_PARAMETER), build_cone, 40),
    PrimitiveSpec("pyramid", "Pyramid", "pyramid", COMMON_PRIMITIVE_PARAMETERS, build_pyramid, 50),
    PrimitiveSpec("triangular_prism", "Triangular prism", "tri_prism", COMMON_PRIMITIVE_PARAMETERS, build_triangular_prism, 60),
    PrimitiveSpec("hex_prism", "Hex prism", "hex_prism", COMMON_PRIMITIVE_PARAMETERS, build_hex_prism, 70),
    PrimitiveSpec("custom", "Custom", "custom", (*COMMON_PRIMITIVE_PARAMETERS, CUSTOM_KIND_PARAMETER, SEGMENT_PARAMETER, SPHERE_THETA_PARAMETER, SPHERE_PHI_PARAMETER), build_custom, 80),
)

_PRIMITIVE_BY_ID = {spec.id: spec for spec in PRIMITIVE_SPECS}
_LABEL_TO_ID = {spec.label.lower(): spec.id for spec in PRIMITIVE_SPECS}
_LABEL_TO_ID.update({"box/cube": "box", "triangular prism": "triangular_prism", "hex prism": "hex_prism", "custom": "custom", "custom": "custom"})


def iter_primitive_specs() -> tuple[PrimitiveSpec, ...]:
    return tuple(sorted(PRIMITIVE_SPECS, key=lambda s: s.display_order))


def get_primitive_spec(primitive_id: str) -> PrimitiveSpec:
    return _PRIMITIVE_BY_ID.get(primitive_id, _PRIMITIVE_BY_ID["box"])


def primitive_id_from_label(label: str) -> str:
    return _LABEL_TO_ID.get(str(label or "").strip().lower(), "box")


def primitive_tool_defaults() -> dict[str, object]:
    return defaults_for(PRIMITIVE_TOOL_PARAMETERS)


def validate_primitive_tool_values(values: dict[str, object]) -> dict[str, object]:
    validated = validate_values(PRIMITIVE_TOOL_PARAMETERS, values)
    validated["primitive_id"] = get_primitive_spec(str(validated.get("primitive_id", "box"))).id
    return validated


def build_primitive_mesh(values: dict[str, object], *, name_index: int = 1):
    values = validate_primitive_tool_values(values)
    primitive_id = str(values.get("primitive_id", "box"))
    spec = get_primitive_spec(primitive_id)
    return spec.builder(PrimitiveBuildRequest(primitive_id=primitive_id, values=values, name_index=name_index))


def estimate_primitive_tool_triangles(values: dict[str, object]) -> int:
    return estimate_triangle_count(validate_primitive_tool_values(values))
