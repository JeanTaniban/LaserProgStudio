"""Creator API self-tests used by the diagnostic tool and SDK checks.

The suite intentionally exercises the public creator-facing surface without Qt,
PyVista or a live viewport.  It is small enough to run from the Tool Core
Diagnostic panel, but broad enough to detect missing bindings after refactors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import copy
import time
from typing import Any, Callable, Iterable

from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tool_core.app_services import OperationResult

from . import actors, inspector, snap, styles
from .selection_box import BoxSelectionInsidePolicy, BoxSelectionMode, BoxSelectionTarget
from .lifecycle import CreatorTool
from .manifest import ToolManifest
from .cleanup import audit_tool_api_surface
from .surface import active_import_paths
from .versioning import TOOL_API_VERSION, require_tool_api
from .diagnostic_lab import CreatorApiDiagnosticLab


@dataclass(frozen=True, slots=True)
class ApiDiagnosticCase:
    """One diagnostic check result."""

    name: str
    category: str
    passed: bool
    details: str = ""
    duration_ms: float = 0.0

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"


@dataclass(frozen=True, slots=True)
class ApiDiagnosticReport:
    """Serializable report for the creator API diagnostic suite."""

    api_version: str
    cases: tuple[ApiDiagnosticCase, ...]
    started_at: float = field(default_factory=time.time)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def summary_line(self) -> str:
        return f"Creator API self-tests: {self.passed}/{self.total} passed"

    def to_markdown(self) -> str:
        lines = [
            "# Creator API self-tests",
            "",
            f"API version: `{self.api_version}`",
            f"Status: **{'PASS' if self.ok else 'FAIL'}**",
            f"Cases: {self.passed}/{self.total} passed",
            "",
            "| Status | Category | Case | Details | ms |",
            "|---|---|---|---|---:|",
        ]
        for case in self.cases:
            details = case.details.replace("|", "\\|")
            lines.append(f"| {case.status} | {case.category} | {case.name} | {details} | {case.duration_ms:.2f} |")
        return "\n".join(lines)


def run_creator_api_self_test(ctx: ToolContext | None = None, *, owner_tool: str = "tool_api.self_test") -> ApiDiagnosticReport:
    """Run the public creator API diagnostic suite.

    ``ctx`` may be the live Tool Core Diagnostic context.  The suite owns only
    data tagged with ``owner_tool`` and cleans it before starting.  Document and
    scene services are rebound to a deterministic in-memory scene so the tests
    do not depend on the user's current project.
    """

    context = ctx or ToolContext()
    owner = str(owner_tool)
    context.cleanup_tool(owner, include_persistent_overlays=True)
    scene = _DiagnosticScene()
    context.scene = scene
    context.viewport = _DiagnosticViewport()
    context.document.bind(scene)
    context.scene_selection.set_selected([0])
    context.status.clear()
    cases: list[ApiDiagnosticCase] = []

    def run(category: str, name: str, check: Callable[[ToolContext], str]) -> None:
        started = time.perf_counter()
        try:
            details = check(context)
            cases.append(ApiDiagnosticCase(name=name, category=category, passed=True, details=details, duration_ms=(time.perf_counter() - started) * 1000.0))
        except Exception as exc:  # pragma: no cover - exercised by diagnostic failures, not normal tests
            cases.append(ApiDiagnosticCase(name=name, category=category, passed=False, details=f"{type(exc).__name__}: {exc}", duration_ms=(time.perf_counter() - started) * 1000.0))

    run("Core", "version + manifest", _check_version_and_manifest)
    run("Core", "public surface map", _check_public_surface_map)
    run("UI", "declarative inspector", lambda c: _check_inspector(c, owner))
    run("UI", "native interaction styles", _check_native_styles)
    run("Interaction", "actors + scene cache + smart snap", lambda c: _check_actors_snap(c, owner))
    run("Interaction", "selection box typed targets", lambda c: _check_selection_box(c, owner))
    run("Workflow", "workflow steps + modes", lambda c: _check_workflow_modes(c, owner))
    run("Document", "document + scene selection + preview session", _check_document_preview)
    run("Viewport", "picking facade", _check_picking)
    run("Operations", "operations + jobs + status", lambda c: _check_operations_jobs_status(c, owner))
    run("Domain", "materials + assets + engraving", _check_material_assets_engraving)
    run("Planar", "planar SDK + high-level gizmos", lambda c: _check_planar_gizmos(c, owner))
    run("Lifecycle", "creator lifecycle cleanup", lambda c: _check_lifecycle_cleanup(c, owner))
    run("Diagnostics", "interactive creator API lab", lambda c: _check_interactive_api_lab(c, owner))

    report = ApiDiagnosticReport(api_version=TOOL_API_VERSION, cases=tuple(cases))
    context.status.info(report.summary_line() if report.ok else f"Creator API self-tests failed: {report.failed}/{report.total}")
    return report


def _check_public_surface_map(_ctx: ToolContext) -> str:
    paths = active_import_paths()
    assert "laserprog_studio.tool_api.core" in paths
    assert "laserprog_studio.tool_api.scene" in paths
    assert "laserprog_studio.tool_api.visual" in paths
    assert "laserprog_studio.tool_api.application" in paths
    assert "laserprog_studio.tool_api.workflow" in paths
    findings = audit_tool_api_surface()
    blockers = [finding for finding in findings if finding.severity == "blocker"]
    assert not blockers, "; ".join(finding.message for finding in blockers)
    return f"domains={len(paths)}, cleanup_blockers=0"


def _check_native_styles(_ctx: ToolContext) -> str:
    point_ids = {style.id for style in styles.list_point_styles()}
    line_ids = {style.id for style in styles.list_line_styles()}
    assert {"solid", "ring", "target", "diamond", "square", "arrow", "axis", "chevron", "triad", "minimal", "translate_arrow"}.issubset(point_ids)
    assert {"solid", "selectable", "grabbable", "hover", "selected", "grabbed", "fixed", "guide", "construction", "axis", "preview", "warning", "error"}.issubset(line_ids)
    visual = styles.resolve_actor_visual(interaction="grabbable", point_style_id="triad", line_style_id="guide", visual_state="hover")
    assert visual.point_style_id == "triad"
    assert visual.line_style_id == "guide"
    assert visual.visual_state.value == "hover"
    assert visual.radius_px > 0
    assert visual.line_payload["style_id"] == "guide"
    return f"point_styles={len(point_ids)}, line_styles={len(line_ids)}, state={visual.visual_state.value}"


def _check_version_and_manifest(_ctx: ToolContext) -> str:
    current = require_tool_api(TOOL_API_VERSION, max_major=0)
    manifest = ToolManifest(
        id="com.laserprog.diag.creator_api",
        label="Creator API Diagnostic",
        entrypoint="laserprog_studio.tool_api.diagnostics:run_creator_api_self_test",
        api_min=TOOL_API_VERSION,
        permissions=("scene:read", "scene:write"),
    )
    manifest.validate_runtime()
    assert str(current) == TOOL_API_VERSION
    assert manifest.to_dict()["id"] == manifest.id
    return f"api={current}, manifest={manifest.id}"


def _check_inspector(ctx: ToolContext, owner: str) -> str:
    clicked: list[str] = []
    ctx.inspector.set_panel(
        inspector.panel(
            "API Self-Test",
            id=f"{owner}.panel",
            owner_tool=owner,
            sections=[
                inspector.section(
                    "Inputs",
                    [
                        inspector.float_field("length", "Length", default=12.0, min_value=1.0, max_value=100.0),
                        inspector.slider_field("density", "Density", default=0.25, min_value=0.0, max_value=1.0),
                        inspector.vector2_field("uv", "UV", default=(0.25, 0.75)),
                        inspector.vector3_field("origin", "Origin", default=(1, 2, 3)),
                        inspector.font_field("font", "Font", default="DejaVu Sans"),
                        inspector.readonly_field("report", "Report", default="Ready"),
                        inspector.help_text("help", "Use this panel without touching Qt."),
                    ],
                ),
                inspector.section("Actions", [inspector.button_row("actions", "Actions", buttons=(("preview", "Preview"), ("apply", "Apply")), on_click=lambda event: clicked.append(event.action_id))]),
            ],
        )
    )
    assert ctx.inspector.value("uv") == (0.25, 0.75)
    assert ctx.inspector.value("origin") == (1.0, 2.0, 3.0)
    assert ctx.inspector.value("font") == "DejaVu Sans"
    assert ctx.inspector.update_value("length", 200.0) == 100.0
    ctx.inspector.set_error("length", "clamped during diagnostic")
    ctx.inspector.set_enabled("actions", True)
    ctx.inspector.trigger("preview")
    ctx.inspector.trigger("apply")
    assert clicked == ["preview", "apply"]
    state = ctx.inspector.describe()["field_states"]["length"]
    assert state["error"] == "clamped during diagnostic"
    return "fields=7, vector2+font+button-row OK"


def _check_actors_snap(ctx: ToolContext, owner: str) -> str:
    registry = ctx.actor_registry(owner)
    registry.clear()
    registry.add(actors.point("p1", (0, 0, 0), interaction="grabbable"))
    registry.add(actors.point("p2", (10, 0, 0), interaction="grabbable"))
    registry.add(actors.line("edge", (0, 0, 0), (10, 0, 0), interaction="selectable"))
    ctx.scene_cache.rebuild(ctx, scope="snap")
    assert any(point.source == "tool_actor_point" for point in ctx.scene_cache.points())
    assert any(segment.source == "tool_actor_edge" for segment in ctx.scene_cache.segments())
    rebuilds_before = ctx.snap.cache_rebuilds
    result = ctx.snap.smart(
        (5.1, 0.0, 0.0),
        (5.1, 0.0),
        ctx,
        extra_targets=[
            snap.tool_point("guide.mid", (5, 0, 0), owner_tool=owner, priority=1),
            snap.ui_point("ui.mid", (5, 0), world_pos=(5, 0, 0), priority=20),
        ],
        exclude_ids=("p2",),
        rebuild_cache=False,
    )
    assert result.snapped
    assert result.source_id == "guide.mid"
    assert result.source.value == "tool_temp_point"
    assert ctx.snap.cache_rebuilds == rebuilds_before
    ctx.scene_cache.add_ui_point("persistent.ui", (12, 12), world_pos=(1, 1, 0), owner_tool=owner)
    assert ctx.scene_cache.summary().ui_targets >= 1
    return f"actors={len(registry.all())}, snap={result.source.value}, no-rebuild OK"



def _check_selection_box(ctx: ToolContext, owner: str) -> str:
    registry = ctx.actor_registry(owner)
    registry.clear()
    fixed = registry.add(actors.point("box.fixed", (2, 2, 0), interaction="fixed"))
    selectable = registry.add(actors.point("box.selectable", (8, 8, 0), interaction="selectable"))
    line = registry.add(actors.line("box.line", (15, 5, 0), (28, 5, 0), interaction="grabbable"))
    ctx.selection_box.configure(
        enabled=True,
        targets=[BoxSelectionTarget.TOOL_ACTORS],
        mode=BoxSelectionMode.REPLACE,
        inside_policy=BoxSelectionInsidePolicy.PARTIAL,
        owner_tool=owner,
        selectable_only=True,
        clear_on_empty=True,
    )
    ctx.selection_box.begin((0, 0))
    ctx.selection_box.update((30, 12))
    result = ctx.selection_box.finish((30, 12), world_to_screen=lambda p: (float(p[0]), float(p[1])))
    assert result.completed
    assert fixed.id not in result.tool_actor_ids
    assert selectable.id in result.tool_actor_ids and line.id in result.tool_actor_ids
    assert set(ctx.selection.ids()) == {selectable.id, line.id}
    ctx.selection_box.configure(mode=BoxSelectionMode.SUBTRACT)
    ctx.selection_box.begin((5, 5))
    ctx.selection_box.update((12, 12))
    result2 = ctx.selection_box.finish((12, 12), world_to_screen=lambda p: (float(p[0]), float(p[1])))
    assert selectable.id in result2.tool_actor_ids
    assert set(ctx.selection.ids()) == {line.id}
    return f"box_selected={len(result.tool_actor_ids)}, subtract_ok, fixed_ignored"


def _check_workflow_modes(ctx: ToolContext, owner: str) -> str:
    workflow = ctx.workflow.start(
        owner,
        [
            ctx.workflow.require_scene_object("pick_a", "Pick first part", help="Select part A"),
            ctx.workflow.require_scene_object("pick_b", "Pick second part", help="Select part B"),
            ctx.workflow.step("preview", "Preview result"),
        ],
    )
    assert workflow.active_id == "pick_a"
    ctx.workflow.record_active({"object_index": 0})
    assert ctx.workflow.state.active_id == "pick_b"
    ctx.workflow.record("pick_b", {"object_index": 1}, advance=True)
    assert ctx.workflow.state.active_id == "preview"
    ctx.workflow.complete()
    assert ctx.workflow.state.completed

    modes = ctx.modes.register(
        owner,
        [
            ctx.modes.define("add", "Add", help="Add mode"),
            ctx.modes.define("edit", "Edit", help="Edit mode"),
            ctx.modes.define("delete", "Delete", help="Delete mode"),
        ],
        active="add",
    )
    assert modes.active_id == "add"
    ctx.modes.set(owner, "edit")
    active = ctx.modes.active(owner)
    assert active is not None and active.id == "edit"
    assert ctx.workflow.describe()["completed"] is True
    assert ctx.modes.describe(owner)["tools"][0]["active"] == "edit"
    return "steps=3, modes=3"


def _check_document_preview(ctx: ToolContext) -> str:
    assert [obj.name for obj in ctx.document.objects(include_preview=False)] == ["panel_a", "panel_b"]
    added = ctx.document.add_mesh(_mesh("panel_c"), label="diag add")
    assert added.name == "panel_c"
    ctx.scene_selection.set_selected([0, 2])
    assert [obj.name for obj in ctx.scene_selection.selected_objects()] == ["panel_a", "panel_c"]
    session = ctx.preview_session.start(owner_tool="diag.preview", label="diag preview")
    session.replace_object_preview(added.id, _mesh("panel_c_preview"))
    assert ctx.document.has_preview
    assert ctx.document.objects()[2].name == "panel_c_preview"
    assert session.cancel()
    assert not ctx.document.has_preview
    session = ctx.preview_session.start(owner_tool="diag.preview", label="diag apply")
    session.show_mesh(_mesh("generated"), append=True)
    assert session.apply(label="diag apply")
    assert ctx.document.objects(include_preview=False)[-1].name == "generated"
    return f"objects={len(ctx.document.objects(include_preview=False))}, preview apply/cancel OK"


def _check_picking(ctx: ToolContext) -> str:
    obj = ctx.pick.object_at((10, 20))
    face = ctx.pick.face_at((10, 20), only_selected=True)
    ray = ctx.pick.ray((10, 20))
    plane = ctx.pick.plane_intersection((10, 20), ((0, 0, 0), (0, 0, 1)))
    assert obj.hit and obj.object_index == 0
    assert face.hit and face.kind == "face" and face.normal == (0.0, 0.0, 1.0)
    assert ray.hit and ray.kind == "ray"
    assert plane.hit and plane.kind == "point"
    return "object+face+ray+plane OK"


def _check_operations_jobs_status(ctx: ToolContext, owner: str) -> str:
    result = ctx.operations.simplify(params={"ratio": 0.5}, preview=True, owner_tool=owner)
    assert result.ok and result.meshes
    assert ctx.document.has_preview
    assert ctx.preview_session.apply(label="diag simplify")
    assert any(obj.name.startswith("simplified") for obj in ctx.document.objects())
    job = ctx.jobs.start("diag job", lambda progress: (progress(0.25, "quarter"), progress(0.75, "almost"), "done")[-1])
    assert job.state.value == "done" and job.result == "done"
    ctx.status.warning("diagnostic warning")
    summary = ctx.status.summary()
    assert "diagnostic warning" in summary["warnings"]
    return f"operation={result.report}, job={job.state.value}, status={summary['count']} messages"


def _check_material_assets_engraving(ctx: ToolContext) -> str:
    material = ctx.materials.create("Diagnostic plywood", base_color="#B77A33", opacity=0.7)
    assigned = ctx.materials.assign(0, material)
    assert assigned.mesh.material.name == "Diagnostic plywood"
    texture = ctx.assets.import_image("/tmp/diagnostic_texture.png", usage="engrave", asset_id="diag.texture")
    ctx.assets.attach_to_material(0, texture.id)
    assert ctx.materials.get(0).texture_id == "diag.texture"
    ctx.engraving.assign_role(0, "outline")
    assert ctx.engraving.role_for(0) == "outline"
    return f"materials={len(ctx.materials.list())}, textures={len(ctx.assets.list_textures())}, role=outline"


def _check_planar_gizmos(ctx: ToolContext, owner: str) -> str:
    ctx.planar.clear()
    ctx.planar.set_plane(origin=(2, 0, 0), normal=(0, 0, 1))
    p1 = ctx.planar.add_point(plane_pos=(0, 0), point_id="diag.p1")
    p2 = ctx.planar.add_point(plane_pos=(3, 0), point_id="diag.p2")
    p3 = ctx.planar.add_point(plane_pos=(3, 2), point_id="diag.p3")
    p4 = ctx.planar.add_point(plane_pos=(0, 2), point_id="diag.p4")
    ctx.planar.add_line(p1.id, p2.id)
    ctx.planar.add_line(p2.id, p3.id)
    ctx.planar.add_line(p3.id, p4.id)
    ctx.planar.add_line(p4.id, p1.id)
    regions = ctx.planar.solve_regions()
    assert len(regions) == 1 and abs(regions[0].area - 6.0) < 1e-9
    mesh = ctx.planar.generate_mesh(regions[0], name="diag planar mesh")
    assert len(mesh.vertices) == 4
    plane = ctx.gizmos.plane(id="diag.plane", owner_tool=owner, origin=(0, 0, 0), normal=(0, 0, 1))
    translate = ctx.gizmos.translate(id="diag.move", owner_tool=owner)
    rotate = ctx.gizmos.rotate(id="diag.rotate", owner_tool=owner)
    scale = ctx.gizmos.scale(id="diag.scale", owner_tool=owner)
    box = ctx.gizmos.box_bounds(id="diag.box", owner_tool=owner, bounds=(0, 1, 0, 1, 0, 1))
    assert plane.kind == "plane" and translate.kind == "translate" and rotate.kind == "rotate" and scale.kind == "scale" and box.kind == "box_bounds"
    return f"region_area={regions[0].area:g}, gizmo_handles={len(ctx.gizmos.handles(owner_tool=owner))}"


def _check_lifecycle_cleanup(ctx: ToolContext, owner: str) -> str:
    class _DiagTool(CreatorTool):
        id = owner
        label = "Lifecycle diagnostic"

        def on_open(self, context: ToolContext) -> None:
            context.inspector.set_panel(inspector.panel("Lifecycle", id=owner, owner_tool=owner, sections=[inspector.section("A", [inspector.float_field("v", "Value", default=1.0)])]))
            context.actor_registry(owner).add(actors.point("life.point", (0, 0, 0), interaction="grabbable"))
            context.preview.show_line("life.preview", owner, (0, 0, 0), (1, 0, 0))
            context.gizmos.translate(id="life.move", owner_tool=owner)
            context.scene_cache.add_point("life.snap", (0, 0, 0), owner_tool=owner)

    tool = _DiagTool()
    tool.open(ctx)
    assert ctx.inspector.panel is not None
    assert ctx.selection.actors(owner_tool=owner)
    assert ctx.preview.items(owner_tool=owner)
    assert ctx.gizmos.handles(owner_tool=owner)
    assert ctx.scene_cache.summary().tool_points >= 1
    tool.close(ctx)
    assert ctx.inspector.panel is None
    assert not ctx.selection.actors(owner_tool=owner)
    assert not ctx.preview.items(owner_tool=owner)
    assert not ctx.gizmos.handles(owner_tool=owner)
    return "open state cleaned automatically"


def _check_interactive_api_lab(ctx: ToolContext, owner: str) -> str:
    lab = CreatorApiDiagnosticLab(ctx, owner_tool=owner)
    snap0 = lab.setup()
    assert snap0.actors >= 6
    lab.set_options(actor_kind="line", interaction="grabbable", move="+X", point_style="triad", line_style="guide", visual_state="hover")
    snap1 = lab.add_from_options()
    assert snap1.lines >= 3
    actor_id = lab.select_at((45.0, 0.0), lambda p: (float(p[0]), float(p[1])), additive=False)
    assert actor_id is not None
    lab.begin_grab_if_possible(actor_id, (45.0, 0.0), (45.0, 0.0, 0.42))
    moved = lab.move_selected((2.0, 0.0, 0.0))
    lab.end_grab()
    assert moved >= 1
    bench = lab.run_benchmark(iterations=40)
    assert bench.cases and bench.ok
    deleted = lab.delete_selected()
    assert deleted.actors >= 1
    return f"lab_actors={deleted.actors}, bench_cases={len(bench.cases)}, styled_drag_move OK"


@dataclass
class _DiagnosticMesh:
    name: str
    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]
    mesh_id: str = ""
    color: str = "#B8B8B8"


class _DiagnosticModelStore:
    def __init__(self, meshes: Iterable[_DiagnosticMesh]) -> None:
        self.committed_meshes = list(copy.deepcopy(tuple(meshes)))
        self.preview_meshes: list[_DiagnosticMesh] | None = None
        self._selected_mesh_indices: list[int] = []
        self.changed = 0

    @property
    def has_preview(self) -> bool:
        return self.preview_meshes is not None

    @property
    def selected_mesh_indices(self) -> tuple[int, ...]:
        return tuple(self._selected_mesh_indices)

    def set_meshes(self, meshes: Iterable[_DiagnosticMesh], **_kwargs: Any) -> None:
        self.committed_meshes = list(copy.deepcopy(tuple(meshes)))
        self.preview_meshes = None
        self.changed += 1

    def snapshot(self):
        return copy.deepcopy(self.committed_meshes), None

    def set_preview_meshes(self, meshes: Iterable[_DiagnosticMesh], **_kwargs: Any) -> None:
        self.preview_meshes = list(copy.deepcopy(tuple(meshes)))

    def commit_preview(self) -> bool:
        if self.preview_meshes is None:
            return False
        self.committed_meshes = list(copy.deepcopy(self.preview_meshes))
        self.preview_meshes = None
        self.changed += 1
        return True

    def discard_preview(self) -> bool:
        if self.preview_meshes is None:
            return False
        self.preview_meshes = None
        return True

    def _notify(self) -> None:
        self.changed += 1


class _DiagnosticViewport:
    def request_light_render(self) -> bool:
        return True

    def request_full_render(self) -> bool:
        return True

    def world_to_screen(self, pos):
        return (float(pos[0]), float(pos[1]))

    def screen_to_ray(self, screen_pos):
        return {"kind": "ray", "world_pos": (float(screen_pos[0]), float(screen_pos[1]), 1.0), "metadata": {"direction": (0.0, 0.0, -1.0)}}

    def screen_to_world_on_plane(self, screen_pos, _plane=None):
        return (float(screen_pos[0]), float(screen_pos[1]), 0.0)


class _DiagnosticScene:
    def __init__(self) -> None:
        self.model_store = _DiagnosticModelStore([_mesh("panel_a", mesh_id="a"), _mesh("panel_b", mesh_id="b")])
        self.texture_assets_by_id: dict[str, Any] = {}
        self.messages: list[str] = []

    def ui_log(self, message: str) -> None:
        self.messages.append(str(message))

    def snap_points(self):
        return [("scene.origin", (0.0, 0.0, 0.0)), ("scene.corner", (10.0, 10.0, 0.0))]

    def snap_segments(self):
        return [("scene.edge", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0))]

    def bounds_for_snap(self):
        return [((0.0, 0.0, 0.0), (10.0, 10.0, 2.0))]

    def pick_object_at(self, screen_pos, **_filters):
        return {"kind": "object", "object_id": "a", "object_index": 0, "world_pos": (float(screen_pos[0]), float(screen_pos[1]), 0.0)}

    def pick_face_at(self, screen_pos, **_filters):
        return {"kind": "face", "object_id": "a", "object_index": 0, "element_index": 0, "world_pos": (float(screen_pos[0]), float(screen_pos[1]), 0.0), "normal": (0.0, 0.0, 1.0)}

    def operation_simplify(self, inputs, params, ctx):  # noqa: ARG002
        ratio = float(params.get("ratio", 1.0))
        return OperationResult.success([*inputs, _mesh(f"simplified_{ratio:g}", mesh_id="simplified")], report="simplified")

    def record_modification(self, *_args: Any, **_kwargs: Any) -> None:
        self.model_store.changed += 1


def _mesh(name: str, *, mesh_id: str | None = None) -> _DiagnosticMesh:
    return _DiagnosticMesh(
        name=name,
        mesh_id=mesh_id or name,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        triangles=[(0, 1, 2)],
    )


__all__ = [
    "ApiDiagnosticCase",
    "ApiDiagnosticReport",
    "run_creator_api_self_test",
]
