"""Headless Cloth foundation demo.

Run with ``PYTHONPATH=src python examples/tool_creator/cloth_architecture_demo.py``.
The interactive Creator adapter is intentionally not registered yet.
"""
from __future__ import annotations

from laserprog_studio.tooling.cloth import ClothDocument, ClothFoldKind, build_cloth_apply_plan


def build_demo_document() -> ClothDocument:
    document = ClothDocument()
    for point_id, position in {
        "a": (0.0, 0.0, 0.0),
        "b": (100.0, 0.0, 0.0),
        "c": (100.0, 60.0, 0.0),
        "d": (0.0, 60.0, 0.0),
        "e": (100.0, 60.0, 40.0),
        "f": (100.0, 0.0, 40.0),
    }.items():
        document.add_point(position, point_id=point_id)
    ab = document.add_line("a", "b", curve_id="ab")
    bc = document.add_line("b", "c", curve_id="bc")
    cd = document.add_line("c", "d", curve_id="cd")
    da = document.add_line("d", "a", curve_id="da")
    ce = document.add_line("c", "e", curve_id="ce")
    ef = document.add_line("e", "f", curve_id="ef")
    fb = document.add_line("f", "b", curve_id="fb")
    base = document.add_patch((ab.id, bc.id, cd.id, da.id), patch_id="base", name="Base panel")
    flap = document.add_patch((bc.id, ce.id, ef.id, fb.id), patch_id="flap", name="Folded panel")
    document.add_fold(bc.id, base.id, flap.id, kind=ClothFoldKind.VALLEY, angle_degrees=90.0)
    return document


def main() -> None:
    plan = build_cloth_apply_plan(build_demo_document(), name="Cloth demo")
    if not plan.ready:
        raise SystemExit("Cloth demo failed: " + "; ".join(plan.issues))
    print(f"3D surface: {len(plan.folded_mesh.vertices)} vertices / {len(plan.folded_mesh.triangles)} triangles")
    print(f"Flat pattern: {len(plan.flat_mesh.vertices)} vertices / {len(plan.flat_mesh.triangles)} triangles")
    print(f"Requested scene: {plan.flat_scene_name}")


if __name__ == "__main__":
    main()
