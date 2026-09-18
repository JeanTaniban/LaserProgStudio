from __future__ import annotations

import pytest

from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.plan_trace_2d.panel import build_plan_trace_2d_panel
from laserprog_studio.tooling.plan_trace_2d.patterns import PATTERN_KIND_CHOICES
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _rectangle_sketch(width: float = 100.0, height: float = 60.0) -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0)).id
    p2 = sketch.add_point((width, 0.0)).id
    p3 = sketch.add_point((width, height)).id
    p4 = sketch.add_point((0.0, height)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    sketch.compile(SketchCompileOptions(split_curve_intersections=False, split_curves_at_vertices=False, solve_faces=True))
    return sketch


def test_pass311_panel_exposes_pattern_build_controls() -> None:
    panel = build_plan_trace_2d_panel(
        on_mode_changed=lambda _field, _value: None,
        on_settings_changed=lambda _field, _value: None,
        on_action=lambda _event: None,
    )
    field_ids = {field.id for field in panel.fields()}
    # Inspector section mirrors the live Pattern overlay parameters; the action
    # buttons that used to live here (pattern_pick_face / pattern_generate)
    # were removed when the dedicated Pattern overlay became the workflow.
    assert "plan_trace_2d.pattern_kind" in field_ids
    assert "plan_trace_2d.pattern_cell_size" in field_ids
    assert "plan_trace_2d.pattern_face" in field_ids
    assert "plan_trace_2d.pattern_status" in field_ids
    assert "pattern_pick_face" not in field_ids
    assert "pattern_generate" not in field_ids


def test_pass311_pattern_generation_creates_holes_not_filled_islands() -> None:
    tool = PlanTrace2DCreatorTool()
    sketch = _rectangle_sketch()
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))
    tool._state.pattern_face_id = face.id

    created = tool._services.patterns._generate_on_face(face, kind="honeycomb", cell_size=16.0, wall=3.0, margin=4.0)
    assert created > 0
    sketch.compile()
    removed = tool._services.patterns._suppress_pattern_inner_faces()
    sketch.compile()

    assert removed == created
    faces = tuple(sketch.faces.values())
    assert len(faces) == 1
    assert len(faces[0].hole_polygons) == created
    assert tool._services.patterns.selected_face_text().startswith(face.id)


def test_pass311_pattern_regeneration_replaces_previous_pattern_entities() -> None:
    tool = PlanTrace2DCreatorTool()
    sketch = _rectangle_sketch(120.0, 80.0)
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))
    tool._state.pattern_face_id = face.id

    first = tool._services.patterns._generate_on_face(face, kind="square", cell_size=20.0, wall=4.0, margin=5.0)
    first_pattern_points = sum(1 for point in sketch.points.values() if point.metadata.get("plan_trace_2d.pattern.point"))
    assert first > 0 and first_pattern_points > 0
    sketch.compile()
    face = next(face for face in sketch.faces.values() if not face.metadata.get("generated_from_hole"))
    second = tool._services.patterns._generate_on_face(face, kind="grid", cell_size=18.0, wall=3.0, margin=5.0)
    second_pattern_points = sum(1 for point in sketch.points.values() if point.metadata.get("plan_trace_2d.pattern.point"))

    assert second > 0
    assert second_pattern_points != first_pattern_points or second != first


def test_pass311_catalogue_exposes_living_hinge_and_organic_motifs() -> None:
    keys = {kind for kind, _label in PATTERN_KIND_CHOICES}
    # Classic structural motifs.
    assert {"honeycomb", "square", "grid"}.issubset(keys)
    # New parametric motifs.
    assert {"circle", "diamond", "triangle", "brick", "cross", "star", "rings", "wave", "organic"}.issubset(keys)
    # Living hinge variants for bendable plywood.
    assert {"hinge_straight", "hinge_lattice", "hinge_wave"}.issubset(keys)
    # Documented contract: at least ten motifs in total.
    assert len(PATTERN_KIND_CHOICES) >= 10


@pytest.mark.parametrize("kind", [kind for kind, _ in PATTERN_KIND_CHOICES])
def test_pass311_every_pattern_kind_generates_at_least_one_opening(kind: str) -> None:
    tool = PlanTrace2DCreatorTool()
    sketch = _rectangle_sketch(200.0, 120.0)
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))
    tool._state.pattern_face_id = face.id

    created = tool._services.patterns._generate_on_face(
        face,
        kind=kind,
        cell_size=14.0,
        wall=2.0,
        margin=3.0,
        angle=0.0,
        aspect=1.0,
        seed=11,
    )
    assert created > 0, f"motif {kind!r} produced zero openings"


def test_pass311_pattern_rotation_clips_against_face_boundary() -> None:
    tool = PlanTrace2DCreatorTool()
    sketch = _rectangle_sketch(160.0, 100.0)
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))
    tool._state.pattern_face_id = face.id

    created = tool._services.patterns._generate_on_face(
        face,
        kind="square",
        cell_size=14.0,
        wall=2.0,
        margin=3.0,
        angle=30.0,
        aspect=1.0,
        seed=0,
    )
    assert created > 0


def test_pass311_living_hinge_slots_span_face_width_via_clipping() -> None:
    """Living-hinge slot rows must run across the face, not be rejected for crossing the boundary."""

    tool = PlanTrace2DCreatorTool()
    sketch = _rectangle_sketch(180.0, 120.0)
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))
    tool._state.pattern_face_id = face.id

    created = tool._services.patterns._generate_on_face(
        face,
        kind="hinge_straight",
        cell_size=4.0,   # tight row pitch — typical for 3mm ply
        wall=0.3,        # laser kerf
        margin=3.0,
        angle=0.0,
        aspect=4.0,      # long slots
        seed=0,
    )
    # A 120mm-tall face at 4mm pitch produces ~30 rows; even with the cell
    # density variations the expected count is well above ten.
    assert created >= 10
