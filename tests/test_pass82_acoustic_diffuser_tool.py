from __future__ import annotations

import math
from pathlib import Path

from laserprog_studio.boolean_ops import is_closed_triangle_mesh
from laserprog_studio.geometry_ops.acoustic_diffuser import AcousticDiffuserSettings, build_acoustic_diffuser
from laserprog_studio.tooling.help_docs import get_tool_help_document
from laserprog_studio.tooling.ids import TOOL_ACOUSTIC_DIFFUSER
from laserprog_studio.tooling.registry import get_tool_spec, validate_tool_registry
from laserprog_studio.ui.toolbar_catalog import default_toolbar_item_ids, get_toolbar_item_spec, validate_toolbar_item_registry
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def test_acoustic_diffuser_builds_native_closed_meshes() -> None:
    result = build_acoustic_diffuser(AcousticDiffuserSettings(quality=72, vent_style="holes", vent_count=6, vent_size_mm=8))

    assert len(result.meshes) == 2
    assert result.report.cavity_volume_cm3 > 0
    assert result.report.helmholtz_hz > 0
    assert result.report.total_conductance_mm > result.report.ring_conductance_mm
    for mesh in result.meshes:
        assert mesh.vertices
        assert mesh.triangles
        closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(mesh.vertices, mesh.triangles)
        assert closed, (mesh.name, boundary_edges, nonmanifold_edges)


def test_acoustic_diffuser_round_holes_use_clean_contours() -> None:
    from laserprog_studio.geometry_ops.acoustic_diffuser import analyze_acoustic_diffuser, _vent_opening_specs

    settings = AcousticDiffuserSettings(quality=72, vent_style="holes", vent_count=4, vent_size_mm=12)
    report = analyze_acoustic_diffuser(settings)
    openings = _vent_opening_specs(settings, report.geometry)

    assert len(openings) == 4
    assert min(len(opening.loop_xz_mm) for opening in openings) >= 28

    first = openings[0]
    distances = [((x - first.center_x_mm) ** 2 + (z - first.center_z_mm) ** 2) ** 0.5 for x, z in first.loop_xz_mm]
    average_radius = sum(distances) / len(distances)
    assert max(abs(d - average_radius) for d in distances) < 1e-6

    mesh = build_acoustic_diffuser(settings).meshes[0]
    closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(mesh.vertices, mesh.triangles)
    assert closed, (boundary_edges, nonmanifold_edges)


def test_acoustic_diffuser_is_registered_as_non_default_toolbar_tool() -> None:
    validate_tool_registry()
    validate_toolbar_item_registry()

    tool = get_tool_spec(TOOL_ACOUSTIC_DIFFUSER)
    assert tool is not None
    assert tool.label == "Acoustic diffuser"
    assert tool.panel_index == 15

    panel = get_tool_panel_spec(TOOL_ACOUSTIC_DIFFUSER)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"

    toolbar = get_toolbar_item_spec("tool:acoustic_diffuser")
    assert toolbar is not None
    assert toolbar.tool_id == TOOL_ACOUSTIC_DIFFUSER
    assert toolbar.code == "ACD"
    assert toolbar.default_visible is False
    assert "tool:acoustic_diffuser" not in default_toolbar_item_ids()


def test_acoustic_diffuser_has_help_documentation() -> None:
    doc = get_tool_help_document(TOOL_ACOUSTIC_DIFFUSER)
    assert doc is not None
    assert "OpenSCAD" in doc.body
    assert "Generate preview" in doc.body


def test_acoustic_diffuser_vented_cylinder_skins_stay_locally_tessellated() -> None:
    from laserprog_studio.geometry_ops.acoustic_diffuser import analyze_acoustic_diffuser

    settings = AcousticDiffuserSettings(quality=72, vent_style="holes", vent_count=6, vent_size_mm=8)
    geom = analyze_acoustic_diffuser(settings).geometry
    mesh = build_acoustic_diffuser(settings).meshes[0]

    max_side_edge = 0.0
    side_triangles = 0
    for tri in mesh.triangles:
        pts = [mesh.vertices[int(index)] for index in tri]
        radii = [math.hypot(float(p[0]), float(p[1])) for p in pts]
        on_inner_skin = max(abs(r - geom.r_in_mm) for r in radii) < 1e-5
        on_outer_skin = max(abs(r - geom.r_out_mm) for r in radii) < 1e-5
        if not (on_inner_skin or on_outer_skin):
            continue
        side_triangles += 1
        for a, b in ((0, 1), (1, 2), (2, 0)):
            max_side_edge = max(max_side_edge, math.dist(pts[a], pts[b]))

    assert side_triangles > 0
    assert max_side_edge < 12.0


def test_acoustic_diffuser_resolution_controls_mesh_density() -> None:
    low = build_acoustic_diffuser(AcousticDiffuserSettings(quality=32, vent_style="holes", vent_count=6, vent_size_mm=8))
    high = build_acoustic_diffuser(AcousticDiffuserSettings(quality=112, vent_style="holes", vent_count=6, vent_size_mm=8))

    low_vertices = sum(len(mesh.vertices) for mesh in low.meshes)
    high_vertices = sum(len(mesh.vertices) for mesh in high.meshes)
    low_triangles = sum(len(mesh.triangles) for mesh in low.meshes)
    high_triangles = sum(len(mesh.triangles) for mesh in high.meshes)

    assert low_vertices < high_vertices * 0.45
    assert low_triangles < high_triangles * 0.45
    for mesh in low.meshes + high.meshes:
        closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(mesh.vertices, mesh.triangles)
        assert closed, (mesh.name, boundary_edges, nonmanifold_edges)


def test_acoustic_diffuser_low_resolution_uses_fewer_vent_points() -> None:
    from laserprog_studio.geometry_ops.acoustic_diffuser import analyze_acoustic_diffuser, _vent_opening_specs

    low_settings = AcousticDiffuserSettings(quality=32, vent_style="holes", vent_count=4, vent_size_mm=12)
    high_settings = AcousticDiffuserSettings(quality=112, vent_style="holes", vent_count=4, vent_size_mm=12)
    low_openings = _vent_opening_specs(low_settings, analyze_acoustic_diffuser(low_settings).geometry)
    high_openings = _vent_opening_specs(high_settings, analyze_acoustic_diffuser(high_settings).geometry)

    assert min(len(opening.loop_xz_mm) for opening in low_openings) >= 12
    assert max(len(opening.loop_xz_mm) for opening in low_openings) < min(len(opening.loop_xz_mm) for opening in high_openings)


def test_acoustic_diffuser_creator_panel_exposes_resolution_control() -> None:
    source = Path("src/laserprog_studio/tooling/acoustic_diffuser_tool.py").read_text(encoding="utf-8")
    assert 'ChoiceField("resolution"' in source
    assert '"Low"' in source and '"Medium"' in source and '"High"' in source
    factory_source = Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8")
    assert "acoustic_diffuser_resolution" not in factory_source
