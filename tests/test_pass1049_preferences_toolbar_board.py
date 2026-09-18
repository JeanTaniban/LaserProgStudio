# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from laserprog_studio.geometry_ops.primitive_board import (
    BoardPrimitiveSpec,
    board_axes_from_normal,
    make_board_primitive_mesh,
)
from laserprog_studio.services.project_preferences import coerce_project_preferences, save_project_preferences, load_project_preferences


def _dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def test_project_preferences_coerce_laser_defaults_and_bounds(tmp_path: Path) -> None:
    prefs = coerce_project_preferences(
        {
            "laser": {
                "default_board_thickness_mm": "5.5",
                "machine_area_x_mm": "650",
                "machine_area_y_mm": "400",
                "show_machine_area": "true",
                "primitive_board_x_mm": "320",
                "primitive_board_y_mm": "180",
            },
            "autosave_enabled": "false",
            "autosave_interval_s": "12",
            "default_floor_grid_step_mm": "25",
        }
    )
    assert prefs.laser.default_board_thickness_mm == 5.5
    assert prefs.laser.machine_area_x_mm == 650.0
    assert prefs.laser.machine_area_y_mm == 400.0
    assert prefs.laser.show_machine_area is True
    assert prefs.laser.primitive_board_x_mm == 320.0
    assert prefs.laser.primitive_board_y_mm == 180.0
    assert prefs.autosave_enabled is False
    assert prefs.autosave_interval_s == 12
    assert prefs.default_floor_grid_step_mm == 25.0

    path = tmp_path / "prefs.json"
    save_project_preferences(prefs, path=path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert load_project_preferences(path).laser.primitive_board_x_mm == 320.0


def test_board_primitive_lies_outside_clicked_face_along_normal() -> None:
    normal = (0.0, 1.0, 0.0)
    thickness = 4.0
    clicked_face_point = (10.0, 20.0, 30.0)
    center = (clicked_face_point[0], clicked_face_point[1] + thickness * 0.5, clicked_face_point[2])
    mesh = make_board_primitive_mesh(
        BoardPrimitiveSpec(width_mm=100.0, height_mm=50.0, thickness_mm=thickness, center=center, normal=normal)
    )
    distances = [_dot((v[0] - clicked_face_point[0], v[1] - clicked_face_point[1], v[2] - clicked_face_point[2]), normal) for v in mesh.vertices]
    assert min(round(d, 6) for d in distances) == 0.0
    assert max(round(d, 6) for d in distances) == thickness
    assert mesh.metadata["primitive_board"]["normal"] == [0.0, 1.0, 0.0]


def test_board_axes_are_orthonormal_for_floor_and_side_faces() -> None:
    for normal in ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.2, 0.7, 0.5)):
        u, v, n = board_axes_from_normal(normal)
        assert abs(_dot(u, v)) < 1.0e-9
        assert abs(_dot(u, n)) < 1.0e-9
        assert abs(_dot(v, n)) < 1.0e-9
        assert abs(_dot(n, n) - 1.0) < 1.0e-9


def test_toolbar_drag_and_preferences_sources_are_wired() -> None:
    toolbar_source = Path("src/laserprog_studio/application/toolbar_controller.py").read_text(encoding="utf-8")
    menus_source = Path("src/laserprog_studio/ui/actions_menus.py").read_text(encoding="utf-8")
    context_source = Path("src/laserprog_studio/controllers/selection_context_menu.py").read_text(encoding="utf-8")

    assert "ToolbarItemDragButton" in toolbar_source
    assert "def move_item" in toolbar_source
    assert "toolbarDropTarget" in toolbar_source
    assert "Preferences" in menus_source and "open_preferences_dialog" in menus_source
    assert "Primitive board" in context_source
    assert "create_primitive_board_from_context" in context_source
