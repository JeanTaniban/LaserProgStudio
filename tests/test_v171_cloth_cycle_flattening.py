from __future__ import annotations

from laserprog_studio.tooling.cloth.apply_pipeline import apply_plan_snapshot
from laserprog_studio.tooling.cloth.flattening import flatten_cloth_document
from laserprog_studio.tooling.cloth.groups import create_textile_group
from laserprog_studio.tooling.cloth.mesh_builder import build_cloth_surface_mesh
from laserprog_studio.tooling.cloth.mesh_welding import build_shared_boundary_samples
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.output import build_cloth_apply_plan
from laserprog_studio.tooling.cloth.validation import validate_cloth_document


def _three_panel_cycle(*, logical_groups: bool) -> ClothDocument:
    document = ClothDocument()
    for point_id, position in {
        "p0": (0.0, 0.0, 0.0),
        "p1": (20.0, 0.0, 0.0),
        "p2": (10.0, 15.0, 0.0),
        "p3": (10.0, -15.0, 0.0),
    }.items():
        document.add_point(position, point_id=point_id)

    e01 = document.add_line("p0", "p1", curve_id="e01")
    e12 = document.add_line("p1", "p2", curve_id="e12")
    e20 = document.add_line("p2", "p0", curve_id="e20")
    e23 = document.add_line("p2", "p3", curve_id="e23")
    e31 = document.add_line("p3", "p1", curve_id="e31")
    e30 = document.add_line("p3", "p0", curve_id="e30")

    a = document.add_patch((e01.id, e12.id, e20.id), patch_id="a", name="A")
    b = document.add_patch((e12.id, e23.id, e31.id), patch_id="b", name="B")
    c = document.add_patch((e01.id, e31.id, e30.id), patch_id="c", name="C")
    document.add_fold(e12.id, a.id, b.id, fold_id="fab")
    document.add_fold(e31.id, b.id, c.id, fold_id="fbc")
    document.add_fold(e01.id, c.id, a.id, fold_id="fca")

    if logical_groups:
        create_textile_group(document, ("a",), group_id="take_a", origin="take_face")
        create_textile_group(document, ("b",), group_id="close_b", origin="close", parent_group_ids=("take_a", "take_c"))
        create_textile_group(document, ("c",), group_id="take_c", origin="take_face")
    return document


def test_closed_fold_cycle_is_applyable_with_virtual_pattern_cut() -> None:
    document = _three_panel_cycle(logical_groups=False)

    validation = validate_cloth_document(document)
    assert validation.can_apply
    assert "cloth.fold.cycle_virtual_cut" in {issue.code for issue in validation.warnings}

    flattened = flatten_cloth_document(document)
    assert flattened.success
    assert len(flattened.virtual_cut_fold_ids) == 1
    assert len(flattened.virtual_cut_curve_ids) == 1
    assert len(flattened.component_patch_ids) == 1
    assert flattened.virtual_cut_reasons[flattened.virtual_cut_fold_ids[0]] == "cycle_break"


def test_persistent_textile_groups_become_independent_flat_components() -> None:
    document = _three_panel_cycle(logical_groups=True)

    flattened = flatten_cloth_document(document)

    assert flattened.success
    assert set(flattened.virtual_cut_fold_ids) == {"fab", "fbc", "fca"}
    assert set(flattened.virtual_cut_reasons.values()) == {"logical_group_boundary"}
    assert {frozenset(component) for component in flattened.component_patch_ids} == {
        frozenset(("a",)),
        frozenset(("b",)),
        frozenset(("c",)),
    }


def test_virtual_cut_curves_are_not_welded_in_flat_mesh() -> None:
    document = _three_panel_cycle(logical_groups=True)
    flattened = flatten_cloth_document(document)

    samples = build_shared_boundary_samples(
        document,
        flattened=True,
        arc_segments=12,
        excluded_curve_ids=flattened.virtual_cut_curve_ids,
    )
    assert all(not patch_samples for patch_samples in samples.values())

    flat = build_cloth_surface_mesh(document, flattened=flattened, name="Cycle flat")
    assert flat.success, flat.issues
    assert flat.mesh is not None
    assert flat.mesh.metadata["cloth_virtual_cut_count"] == 3
    assert set(flat.mesh.metadata["cloth_virtual_cut_curve_ids"]) == {"e01", "e12", "e31"}


def test_apply_plan_accepts_close_cycle_and_reports_virtual_cuts() -> None:
    document = _three_panel_cycle(logical_groups=True)

    plan = build_cloth_apply_plan(document, name="Closed textile")

    assert plan.ready, plan.issues
    assert plan.flattening is not None
    assert plan.flattening.success
    assert len(plan.flattening.virtual_cut_fold_ids) == 3
    snapshot = apply_plan_snapshot(plan)
    assert snapshot["flattening_virtual_cut_count"] == 3
    assert set(snapshot["flattening_virtual_cut_fold_ids"]) == {"fab", "fbc", "fca"}


def _technical_u_group(document: ClothDocument, *, z: float, group_id: str) -> tuple[str, ...]:
    import math

    from laserprog_studio.tooling.cloth.drawing import ClothDrawingController

    centerline: list[tuple[float, float, float]] = []
    for index in range(7):
        centerline.append((0.0, 100.0 - index * 10.0, z))
    for index in range(1, 13):
        angle = math.pi - math.pi * index / 12.0
        centerline.append((20.0 + 20.0 * math.cos(angle), 40.0 - 20.0 * math.sin(angle), z))
    for index in range(1, 7):
        centerline.append((40.0, 40.0 + index * 10.0, z))

    first: list[tuple[float, float, float]] = []
    second: list[tuple[float, float, float]] = []
    for index, point in enumerate(centerline):
        previous = centerline[max(0, index - 1)]
        following = centerline[min(len(centerline) - 1, index + 1)]
        tangent_x = following[0] - previous[0]
        tangent_y = following[1] - previous[1]
        length = max(1.0e-9, math.hypot(tangent_x, tangent_y))
        normal_x = -tangent_y / length
        normal_y = tangent_x / length
        first.append((point[0] + normal_x * 2.0, point[1] + normal_y * 2.0, point[2]))
        second.append((point[0] - normal_x * 2.0, point[1] - normal_y * 2.0, point[2]))

    before = set(document.patches)
    outcome = ClothDrawingController(document).create_ruled_strip_from_positions(first, second)
    assert outcome.committed, outcome.message
    members = tuple(patch_id for patch_id in document.patches if patch_id not in before)
    create_textile_group(document, members, group_id=group_id, origin="take_face")
    return members


def test_realistic_take_face_close_cycle_enables_apply_and_flat_preview() -> None:
    from types import SimpleNamespace

    from laserprog_studio.tooling.cloth.join_faces import analyze_textile_close_groups, commit_join_proposal
    from laserprog_studio.tooling.cloth.models import ClothWorkflowPhase
    from laserprog_studio.tooling.cloth_tool import ClothCreatorTool

    document = ClothDocument()
    first_group = _technical_u_group(document, z=0.0, group_id="take_first")
    second_group = _technical_u_group(document, z=30.0, group_id="take_second")
    proposals = analyze_textile_close_groups(document, (first_group, second_group))
    assert proposals

    before = set(document.patches)
    outcome = commit_join_proposal(document, proposals[0])
    assert outcome.committed, outcome.message
    closure = tuple(patch_id for patch_id in document.patches if patch_id not in before)
    create_textile_group(
        document,
        closure,
        group_id="close_result",
        origin="close",
        parent_group_ids=("take_first", "take_second"),
    )

    validation = validate_cloth_document(document)
    assert validation.can_apply
    plan = build_cloth_apply_plan(document, name="User U closure")
    assert plan.ready, plan.issues
    assert plan.flattening is not None and plan.flattening.success
    assert plan.flattening.virtual_cut_fold_ids

    tool = ClothCreatorTool()
    tool.session.document = document
    tool.session.phase = ClothWorkflowPhase.EDITING
    tool._validation_cache.reset()
    assert tool.can_apply(SimpleNamespace())


def _two_group_grid_cycle() -> ClothDocument:
    document = ClothDocument()
    for y in range(3):
        for x in range(3):
            document.add_point((x * 10.0, y * 10.0, 0.0), point_id=f"p{x}{y}")

    curves = {
        "h0a": document.add_line("p00", "p10", curve_id="h0a"),
        "h0b": document.add_line("p10", "p20", curve_id="h0b"),
        "h1a": document.add_line("p01", "p11", curve_id="h1a"),
        "h1b": document.add_line("p11", "p21", curve_id="h1b"),
        "h2a": document.add_line("p02", "p12", curve_id="h2a"),
        "h2b": document.add_line("p12", "p22", curve_id="h2b"),
        "v0a": document.add_line("p00", "p01", curve_id="v0a"),
        "v0b": document.add_line("p01", "p02", curve_id="v0b"),
        "v1a": document.add_line("p10", "p11", curve_id="v1a"),
        "v1b": document.add_line("p11", "p12", curve_id="v1b"),
        "v2a": document.add_line("p20", "p21", curve_id="v2a"),
        "v2b": document.add_line("p21", "p22", curve_id="v2b"),
    }
    document.add_patch(("h0a", "v1a", "h1a", "v0a"), patch_id="a1")
    document.add_patch(("h1a", "v1b", "h2a", "v0b"), patch_id="a2")
    document.add_patch(("h0b", "v2a", "h1b", "v1a"), patch_id="b1")
    document.add_patch(("h1b", "v2b", "h2b", "v1b"), patch_id="b2")
    document.add_fold(curves["h1a"].id, "a1", "a2", fold_id="fold_a")
    document.add_fold(curves["h1b"].id, "b1", "b2", fold_id="fold_b")
    document.add_fold(curves["v1a"].id, "a1", "b1", fold_id="join_lower")
    document.add_fold(curves["v1b"].id, "a2", "b2", fold_id="join_upper")
    create_textile_group(document, ("a1", "a2"), group_id="group_a", origin="take_face")
    create_textile_group(document, ("b1", "b2"), group_id="group_b", origin="close")
    return document


def test_flat_components_do_not_reweld_shared_endpoints_after_virtual_cut() -> None:
    document = _two_group_grid_cycle()
    flattened = flatten_cloth_document(document)
    assert flattened.success
    assert len(flattened.component_patch_ids) == 2

    shared_world = document.points["p11"].position
    point_a = flattened.placements["a1"].map_world(shared_world)
    point_b = flattened.placements["b1"].map_world(shared_world)
    assert point_a != point_b

    built = build_cloth_surface_mesh(document, flattened=flattened, name="Separated groups")
    assert built.success, built.issues
    assert built.mesh is not None
    positions = {(round(vertex[0], 7), round(vertex[1], 7)) for vertex in built.mesh.vertices}
    assert (round(point_a[0], 7), round(point_a[1], 7)) in positions
    assert (round(point_b[0], 7), round(point_b[1], 7)) in positions


def test_real_overlay_apply_commits_closed_cycle_outputs() -> None:
    from types import SimpleNamespace

    from laserprog_studio.project import ProjectStore
    from laserprog_studio.tool_api.core import ToolContext
    from laserprog_studio.tooling.cloth.models import ClothWorkflowPhase
    from laserprog_studio.tooling.cloth_tool import ClothCreatorTool

    store = ProjectStore.new_empty(scene_name="Main")
    owner = SimpleNamespace(
        project_store=store,
        rebuild_scene=lambda **_kwargs: None,
        update_preview_state=lambda: None,
        _sync_history_buttons=lambda: None,
        sync_scene_tabs=lambda: None,
        update_project_title=lambda: None,
        update_inspector=lambda: None,
    )
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store.active_model_store)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))

    document = _three_panel_cycle(logical_groups=True)
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    tool.session.document = document
    tool._drawing.document = document
    tool.session.phase = ClothWorkflowPhase.EDITING
    tool.session.dirty = True
    tool._validation_cache.reset()

    tool.on_overlay_button_clicked("cloth.workflow.action.apply_output", ctx)

    assert store.active_model_store.committed_meshes
    assert tool.session.editing_existing is True
    assert tool.session.phase is ClothWorkflowPhase.EDITING
