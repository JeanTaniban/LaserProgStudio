# -*- coding: utf-8 -*-
from __future__ import annotations

from shapely.geometry import Polygon

from laserprog_studio.engraving.export_2d import Instance2D, RenderConfig
from laserprog_studio.machine.gcode import GCodeJobSettings, ManualFocusSettings, generate_gcode
from laserprog_studio.machine.profiles import FALCON_A1_PRO_PROFILE


def _square_instances():
    outline = Instance2D("cut", "#00C853", Polygon([(0, 0), (20, 0), (20, 10), (0, 10)]), 3.0)
    fill = Instance2D("fill", "#E53935", Polygon([(2, 2), (8, 2), (8, 6), (2, 6)]), 3.0)
    return [outline, fill]


def test_machine_gcode_generates_svg_sized_xy_and_laser_off_footer():
    cfg = RenderConfig()
    cfg.page_margin_ratio = 0.0
    settings = GCodeJobSettings(
        cut_passes=1,
        hatch_spacing_mm=1.0,
        focus=ManualFocusSettings(material_thickness_mm=3.0, focus_distance_mm=7.0, max_focus_depth_mm=0.0),
    )
    job = generate_gcode(_square_instances(), cfg, settings, FALCON_A1_PRO_PROFILE)
    text = job.text
    assert job.cut_paths >= 1
    assert job.engrave_paths >= 1
    assert "G21 ; millimetres" in text
    assert "M4 S" in text
    assert text.rstrip().endswith("; End of LaserProg G-code")
    assert "no automatic return-to-origin move" in text
    assert "G0 X0 Y0" not in text


def test_machine_gcode_blocks_unsafe_requested_z_depth_in_validation():
    settings = GCodeJobSettings(
        cut_passes=3,
        focus=ManualFocusSettings(
            material_thickness_mm=3.0,
            focus_distance_mm=7.0,
            safety_margin_mm=0.5,
            max_focus_depth_mm=1.0,
            enable_z_steps=True,
            z_step_per_pass_mm=1.0,
        ),
    )
    warnings = settings.validate()
    assert any("exceed" in warning.lower() for warning in warnings)


def test_machine_gcode_emits_relative_z_steps_when_enabled():
    cfg = RenderConfig(); cfg.page_margin_ratio = 0.0
    settings = GCodeJobSettings(
        cut_passes=2,
        include_fill_engraving=False,
        focus=ManualFocusSettings(
            material_thickness_mm=10.0,
            focus_distance_mm=7.0,
            safety_margin_mm=0.5,
            max_focus_depth_mm=6.0,
            enable_z_steps=True,
            z_step_per_pass_mm=2.0,
            z_down_sign=-1,
        ),
    )
    job = generate_gcode(_square_instances(), cfg, settings)
    assert "; Pass 2/2 focus_depth=2.000mm" in job.text
    assert "G91 ; relative coordinates for bounded Z step" in job.text
    assert "G0 Z-2" in job.text
    assert "G0 Z2" in job.text
    assert job.text.count("G90 ; restore absolute XY coordinates") == 2
