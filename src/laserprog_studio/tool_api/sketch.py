"""Plan-sketch document contracts for Creator tools.

This module exposes the neutral sketch data model used by Plan 2D tools without
requiring tool implementations to import from ``tool_core`` directly.
"""
from __future__ import annotations

from laserprog_studio.tool_core.sketch import (
    FaceSolveOptions,
    FaceSolver,
    SketchArc,
    SketchBezier,
    SketchCircle,
    SketchCompileOptions,
    SketchCompileResult,
    SketchCompiler,
    SketchDimension,
    SketchDocument,
    SketchEntityType,
    SketchFace,
    SketchLine,
    SketchPoint,
    SketchPolyline,
    SketchValidationIssue,
    SketchValidationReport,
    SketchValidationSeverity,
    assert_sketch_valid,
    face_signature_from_points,
    validate_sketch,
)

__all__ = [
    "FaceSolveOptions",
    "FaceSolver",
    "SketchArc",
    "SketchBezier",
    "SketchCircle",
    "SketchCompileOptions",
    "SketchCompileResult",
    "SketchCompiler",
    "SketchDimension",
    "SketchDocument",
    "SketchEntityType",
    "SketchFace",
    "SketchLine",
    "SketchPoint",
    "SketchPolyline",
    "SketchValidationIssue",
    "SketchValidationReport",
    "SketchValidationSeverity",
    "assert_sketch_valid",
    "face_signature_from_points",
    "validate_sketch",
]
