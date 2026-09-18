from __future__ import annotations

from laserprog_studio.tool_core.dimensions import DimensionKind, DimensionReference, DimensionReferenceType
from laserprog_studio.tool_core.sketch import SketchDocument, validate_sketch


def test_sketch_validation_reports_missing_dimension_reference() -> None:
    sketch = SketchDocument()
    sketch.add_dimension(
        DimensionKind.EDGE_LENGTH,
        (DimensionReference(DimensionReferenceType.LINE, "missing-line", "edge"),),
        dimension_id="d-missing",
    )

    report = validate_sketch(sketch)

    assert not report.ok
    assert any(issue.code == "dimension_missing_reference" for issue in report.issues)
    assert any("validation_error:dimension_missing_reference" in note for note in report.compact_notes())


def test_compile_result_contains_validation_summary_for_invalid_reference() -> None:
    sketch = SketchDocument()
    sketch.add_dimension(
        DimensionKind.EDGE_LENGTH,
        (DimensionReference(DimensionReferenceType.LINE, "missing-line", "edge"),),
        dimension_id="d-missing",
    )

    result = sketch.compile()

    assert result.validation_issues >= 1
    assert any("dimension_missing_reference" in note for note in result.notes)


def test_delete_arc_cascade_removes_dimensions_on_generated_companion_line() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="p-a")
    b = sketch.add_point((10.0, 0.0), point_id="p-b")
    c = sketch.add_point((5.0, 5.0), point_id="p-c")
    arc = sketch.add_arc(a.id, b.id, c.id, arc_id="arc-1")
    diameter = sketch.add_line(a.id, b.id, line_id="line-diameter")
    diameter.metadata["half_circle_arc_id"] = arc.id
    sketch.add_dimension(
        DimensionKind.EDGE_LENGTH,
        (DimensionReference(DimensionReferenceType.LINE, diameter.id, "edge"),),
        dimension_id="d-diameter",
    )

    sketch.delete_arc_cascade(arc.id, compile_after=False)

    assert arc.id not in sketch.arcs
    assert diameter.id not in sketch.lines
    assert "d-diameter" not in sketch.dimensions
    assert validate_sketch(sketch).ok


def test_sketch_kernel_architecture_doc_mentions_validation_boundary() -> None:
    from pathlib import Path

    doc = Path("docs/tool_creator/18_plan_tracer_sketch_kernel.md").read_text(encoding="utf-8")

    assert "tool_core.sketch.validation" in doc
    assert "Compiler pipeline" in doc
    assert "Topology invariants" in doc
