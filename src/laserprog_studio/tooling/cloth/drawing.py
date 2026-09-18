"""Cloth trace drafting and document materialisation.

The class bridges the shared ``TraceDraftMachine`` and the Cloth topology.  It
keeps new points transient until a primitive is committed, so Escape never
leaves orphan document points behind.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from laserprog_studio.tool_api.tracing import TraceDraftMachine, TraceDraftStatus, TraceMode

from .auto_faces import discover_auto_face_loops
from .face_geometry import analyze_curve_loop
from .models import ClothCurve, ClothCurveKind, ClothDocument, ClothFoldKind, ClothPatch, Point3
from .surface_creation import plan_closed_loop_surface
from .topology import curve_endpoint_ids, curve_patch_incidence, order_curve_loop, patch_frame


@dataclass(frozen=True, slots=True)
class ClothDrawingOutcome:
    accepted: bool
    committed: bool = False
    created_point_ids: tuple[str, ...] = ()
    created_curve_ids: tuple[str, ...] = ()
    created_patch_id: str | None = None
    message: str = ""


@dataclass(slots=True)
class ClothDrawingController:
    document: ClothDocument
    trace: TraceDraftMachine = field(default_factory=TraceDraftMachine)
    pending_positions: dict[str, Point3] = field(default_factory=dict)
    _next_pending_id: int = 1

    def begin(self, mode: str | TraceMode) -> None:
        self.cancel()
        self.trace.begin(mode)

    @property
    def active(self) -> bool:
        return self.trace.draft.status in {TraceDraftStatus.ACTIVE, TraceDraftStatus.READY}

    @property
    def mode(self) -> str:
        return self.trace.draft.mode

    @property
    def pending_world_points(self) -> tuple[Point3, ...]:
        values: list[Point3] = []
        for token in self.trace.draft.point_ids:
            if token in self.document.points:
                values.append(self.document.points[token].position)
            elif token in self.pending_positions:
                values.append(self.pending_positions[token])
        return tuple(values)

    def add_position(
        self,
        position: Iterable[float],
        *,
        existing_point_id: str | None = None,
        finish: bool = False,
        closed: bool = False,
        closure_tolerance: float = 1.0e-5,
    ) -> ClothDrawingOutcome:
        if not self.active:
            return ClothDrawingOutcome(False, message="Choose a drawing mode first.")
        draft = self.trace.draft
        world = self._point3(position)

        # Polyline points remain transient until commit. Clicking the visible
        # first node therefore cannot always return a document point id. Detect
        # the geometric closure before allocating a new transient token.
        closes_first = False
        if draft.mode == TraceMode.POLYLINE.value and len(draft.point_ids) >= 3:
            first = self._position_for_token(draft.point_ids[0])
            closes_first = first is not None and math.dist(world, first) <= max(1.0e-9, float(closure_tolerance))
        if closes_first:
            token = draft.point_ids[0]
            update = self.trace.finish(closed=True)
        else:
            token = str(existing_point_id) if existing_point_id in self.document.points else self._new_pending(world)
            if draft.mode == TraceMode.POLYLINE.value and draft.point_ids and token == draft.point_ids[0] and len(draft.point_ids) >= 3:
                update = self.trace.finish(closed=True)
            else:
                update = self.trace.add_point(token, finish=finish, closed=closed)
                if update.ready_to_commit and draft.mode != TraceMode.POLYLINE.value:
                    update = self.trace.commit()
        if not update.accepted:
            if token in self.pending_positions and token not in self.trace.draft.point_ids:
                self.pending_positions.pop(token, None)
            return ClothDrawingOutcome(False, message=update.reason or "The point was rejected.")
        if update.committed:
            return self._materialize()
        return ClothDrawingOutcome(True, message=self._progress_message())

    def finish(self, *, closed: bool = False) -> ClothDrawingOutcome:
        if not self.active:
            return ClothDrawingOutcome(False, message="No active Cloth primitive.")
        update = self.trace.finish(closed=closed)
        if not update.committed:
            return ClothDrawingOutcome(False, message=update.reason or "The primitive needs more points.")
        return self._materialize()

    def close_polyline_at(
        self,
        position: Iterable[float] | None = None,
        *,
        existing_point_id: str | None = None,
        closure_tolerance: float = 1.0e-5,
    ) -> ClothDrawingOutcome:
        """Close a polyline without duplicating the endpoint from a double click."""

        draft = self.trace.draft
        if not self.active or draft.mode != TraceMode.POLYLINE.value:
            return ClothDrawingOutcome(False, message="No active Cloth polyline.")
        if position is not None:
            world = self._point3(position)
            last = self._position_for_token(draft.point_ids[-1]) if draft.point_ids else None
            first = self._position_for_token(draft.point_ids[0]) if draft.point_ids else None
            tolerance = max(1.0e-9, float(closure_tolerance))
            near_last = last is not None and math.dist(world, last) <= tolerance
            near_first = first is not None and math.dist(world, first) <= tolerance
            if not near_last and not near_first:
                appended = self.add_position(
                    world,
                    existing_point_id=existing_point_id,
                    finish=False,
                    closed=False,
                    closure_tolerance=tolerance,
                )
                if not appended.accepted or appended.committed:
                    return appended
        return self.finish(closed=True)

    def cancel(self) -> None:
        self.trace.cancel()
        self.trace.reset()
        self.pending_positions.clear()

    def create_patch_from_curves(self, curve_ids: Iterable[str], *, name: str | None = None) -> ClothDrawingOutcome:
        ids = tuple(dict.fromkeys(str(value) for value in curve_ids if str(value) in self.document.curves))
        ordered = order_curve_loop(self.document, ids) if ids else None
        if ordered is None:
            return ClothDrawingOutcome(False, message="The selected curves do not form one closed connected loop.")
        wanted = frozenset(ids)
        for patch in self.document.patches.values():
            if frozenset(patch.outer_curve_ids) == wanted:
                return ClothDrawingOutcome(False, message=f"{patch.name} already uses this boundary.")

        # A loop made only of straight edges may be genuinely non-planar.
        # Reuse the same exact triangle-panel planner as a closed free-3D
        # polyline so Face mode never reintroduces a hidden workplane limit.
        curves = tuple(self.document.curves[curve_id] for curve_id, _reverse in ordered)
        if all(curve.kind is ClothCurveKind.LINE for curve in curves):
            point_ids: list[str] = []
            for index, (curve_id, reverse) in enumerate(ordered):
                first, second = curve_endpoint_ids(self.document.curves[curve_id])
                if reverse:
                    first, second = second, first
                if index == 0:
                    point_ids.append(first)
                point_ids.append(second)
            if point_ids and point_ids[-1] == point_ids[0]:
                point_ids.pop()
            patches, created_curves, message = self._create_closed_surface(point_ids)
            if not patches:
                return ClothDrawingOutcome(False, message=message)
            return ClothDrawingOutcome(
                True,
                True,
                created_curve_ids=tuple(created_curves),
                created_patch_id=patches[0].id,
                message=message,
            )

        # Arc/polyline loops remain one locally-planar textile panel.  Validate
        # the geometric loop before mutating the document: endpoint topology
        # alone cannot detect an arc taking the unintended side or two curved
        # boundaries crossing after projection.
        analysis = analyze_curve_loop(self.document, ids)
        if not analysis.valid:
            return ClothDrawingOutcome(False, message=analysis.reason or "The selected curves cannot form a reliable textile face.")
        patch = self.document.add_patch(ids, name=name or f"Panel {len(self.document.patches) + 1}")
        self._auto_create_folds(patch)
        return ClothDrawingOutcome(True, True, created_patch_id=patch.id, message=f"{patch.name} created.")

    def create_line_from_positions(
        self,
        start: Iterable[float],
        end: Iterable[float],
        *,
        metadata: dict[str, object] | None = None,
        tolerance: float = 1.0e-6,
        auto_faces: bool = True,
    ) -> ClothDrawingOutcome:
        """Materialise one source-mesh edge as a Cloth boundary line."""

        positions = (self._point3(start), self._point3(end))
        if math.dist(*positions) <= max(1.0e-12, float(tolerance)):
            return ClothDrawingOutcome(False, message="The selected mesh edge is degenerate.")
        created_points: list[str] = []
        resolved: list[str] = []
        for position in positions:
            existing = self._nearest_document_point(position, tolerance=tolerance)
            if existing is not None:
                resolved.append(existing)
            else:
                point = self.document.add_point(position, metadata=dict(metadata or {}))
                created_points.append(point.id)
                resolved.append(point.id)
        curve, created = self._line_between(resolved[0], resolved[1])
        if not created:
            self._rollback_new_points(created_points)
            return ClothDrawingOutcome(True, False, message="This mesh edge is already traced.")
        if metadata:
            curve.metadata.update(dict(metadata))
        auto_patch, auto_message = self._auto_create_faces((curve.id,)) if auto_faces else (None, "")
        return ClothDrawingOutcome(
            True,
            True,
            tuple(created_points),
            (curve.id,),
            auto_patch.id if auto_patch is not None else None,
            auto_message or "Mesh edge traced.",
        )

    def create_surface_from_positions(
        self,
        positions: Iterable[Iterable[float]],
        *,
        metadata: dict[str, object] | None = None,
        tolerance: float = 1.0e-6,
    ) -> ClothDrawingOutcome:
        """Create a textile surface from an ordered source-mesh boundary."""

        world = [self._point3(value) for value in positions]
        cleaned: list[Point3] = []
        for point in world:
            if not cleaned or math.dist(point, cleaned[-1]) > tolerance:
                cleaned.append(point)
        if len(cleaned) >= 2 and math.dist(cleaned[0], cleaned[-1]) <= tolerance:
            cleaned.pop()
        if len(cleaned) < 3:
            return ClothDrawingOutcome(False, message="The selected mesh face has fewer than three distinct boundary points.")

        created_points: list[str] = []
        resolved: list[str] = []
        for position in cleaned:
            existing = self._nearest_document_point(position, tolerance=tolerance)
            if existing is not None:
                resolved.append(existing)
            else:
                point = self.document.add_point(position, metadata=dict(metadata or {}))
                created_points.append(point.id)
                resolved.append(point.id)
        patches, curve_ids, message = self._create_closed_surface(resolved, metadata=metadata)
        if not patches:
            self._rollback_new_points(created_points)
            return ClothDrawingOutcome(False, message=message)
        return ClothDrawingOutcome(
            True,
            True,
            tuple(created_points),
            tuple(curve_ids),
            patches[0].id,
            message,
        )

    def create_ruled_strip_from_positions(
        self,
        rail_a: Iterable[Iterable[float]],
        rail_b: Iterable[Iterable[float]],
        *,
        metadata: dict[str, object] | None = None,
        tolerance: float = 1.0e-6,
    ) -> ClothDrawingOutcome:
        """Create a regular textile strip between two already paired rails.

        A pair of Plan Tracer arcs is not one planar polygon.  Treating the
        entire outline as such lets a generic polygon triangulator connect
        distant vertices and creates crossed or twisted cloth.  This method
        instead builds one ordered quad cell per rail interval (or two planar
        triangles only when that individual quad is measurably non-planar).
        """

        first = tuple(self._point3(value) for value in rail_a)
        second = tuple(self._point3(value) for value in rail_b)
        if len(first) != len(second) or len(first) < 2:
            return ClothDrawingOutcome(False, message="A ruled Cloth surface needs two paired rails with at least two points each.")
        if any(math.dist(first[index], second[index]) <= max(1.0e-9, float(tolerance)) for index in range(len(first))):
            return ClothDrawingOutcome(False, message="The two selected rails touch or collapse at one sample; a surface width is required.")
        if any(
            math.dist(values[index - 1], values[index]) <= max(1.0e-9, float(tolerance))
            for values in (first, second)
            for index in range(1, len(values))
        ):
            return ClothDrawingOutcome(False, message="One selected rail contains a zero-length interval.")

        original = self.document.clone()
        curves_before = set(self.document.curves)
        patches_before = set(self.document.patches)
        created_points: list[str] = []
        base_metadata = dict(metadata or {})
        strip_id = self.document.new_id("strip")

        def resolve(position: Point3, rail_index: int, sample_index: int) -> str:
            existing = self._nearest_document_point(position, tolerance=tolerance)
            if existing is not None:
                return existing
            point = self.document.add_point(
                position,
                metadata={
                    **base_metadata,
                    "cloth_surface_kind": "ruled_strip",
                    "cloth_ruled_strip_id": strip_id,
                    "cloth_ruled_strip_rail": int(rail_index),
                    "cloth_ruled_strip_sample": int(sample_index),
                },
            )
            created_points.append(point.id)
            return point.id

        try:
            first_ids = [resolve(position, 0, index) for index, position in enumerate(first)]
            second_ids = [resolve(position, 1, index) for index, position in enumerate(second)]
            created_patches: list[ClothPatch] = []
            for index in range(len(first_ids) - 1):
                cell_metadata = {
                    **base_metadata,
                    "cloth_surface_kind": "ruled_strip",
                    "cloth_ruled_strip_id": strip_id,
                    "cloth_ruled_strip_segment": index,
                    "cloth_ruled_strip_segment_count": len(first_ids) - 1,
                }
                patches, _new_curves, message = self._create_closed_surface(
                    [first_ids[index], first_ids[index + 1], second_ids[index + 1], second_ids[index]],
                    metadata=cell_metadata,
                )
                if not patches:
                    raise ValueError(message or f"Ruled strip segment {index + 1} could not form a surface.")
                created_patches.extend(patches)
        except Exception as exc:
            self._restore_document(original)
            return ClothDrawingOutcome(False, message=f"The two rails could not form a reliable Cloth cover: {exc}")

        new_curves = tuple(curve_id for curve_id in self.document.curves if curve_id not in curves_before)
        new_patches = tuple(patch_id for patch_id in self.document.patches if patch_id not in patches_before)
        if not new_patches:
            self._restore_document(original)
            return ClothDrawingOutcome(False, message="The two selected rails did not create any textile panel.")
        return ClothDrawingOutcome(
            True,
            True,
            tuple(created_points),
            new_curves,
            new_patches[0],
            f"Cloth cover created between two edge rails as {len(new_patches)} regular panel(s).",
        )

    def _materialize(self) -> ClothDrawingOutcome:
        draft = self.trace.draft
        tokens = list(draft.point_ids)
        if draft.mode == TraceMode.POLYLINE.value and draft.closed and len(tokens) >= 2 and tokens[-1] == tokens[0]:
            tokens.pop()
        created_points: list[str] = []
        resolved: list[str] = []
        for token in tokens:
            if token in self.document.points:
                resolved.append(token)
                continue
            position = self.pending_positions[token]
            existing = self._nearest_document_point(position, tolerance=1.0e-6)
            if existing is not None:
                resolved.append(existing)
                continue
            point = self.document.add_point(position)
            created_points.append(point.id)
            resolved.append(point.id)

        # A closed loop stores its first topological point only once, even when
        # the snap backend reported the same location through a new draft token.
        if draft.mode == TraceMode.POLYLINE.value and draft.closed and len(resolved) >= 2 and resolved[-1] == resolved[0]:
            resolved.pop()

        # A strong snap or a double click can legitimately resolve two
        # consecutive draft tokens to the same topological point.  Reject the
        # primitive explicitly instead of raising from ``_line_between`` and
        # leaving the Creator tool in an inconsistent state.
        if any(resolved[index] == resolved[index - 1] for index in range(1, len(resolved))):
            self._rollback_new_points(created_points)
            self._reset_after_commit()
            return ClothDrawingOutcome(False, message="Two consecutive Cloth points coincide. Move farther away or reduce the snap tolerance.")
        if draft.mode == TraceMode.LINE.value and len(set(resolved)) < 2:
            self._rollback_new_points(created_points)
            self._reset_after_commit()
            return ClothDrawingOutcome(False, message="A Cloth line needs two distinct points.")
        if draft.mode == TraceMode.ARC.value and len(set(resolved)) < 3:
            self._rollback_new_points(created_points)
            self._reset_after_commit()
            return ClothDrawingOutcome(False, message="A Cloth arc needs three distinct points.")

        created_curves: list[str] = []
        created_patch: ClothPatch | None = None
        if draft.mode == TraceMode.POINT.value:
            message = "Construction point created."
        elif draft.mode == TraceMode.LINE.value:
            curve, created = self._line_between(resolved[0], resolved[1])
            if created:
                created_curves.append(curve.id)
            message = "Line created."
        elif draft.mode == TraceMode.ARC.value:
            curve = self.document.add_arc(resolved[0], resolved[1], resolved[2])
            created_curves.append(curve.id)
            message = "Arc created. A face will appear automatically when the boundary closes."
        elif draft.mode == TraceMode.POLYLINE.value:
            if draft.closed:
                if len(resolved) < 3:
                    self._rollback_new_points(created_points)
                    self._reset_after_commit()
                    return ClothDrawingOutcome(False, message="A closed textile panel needs at least three points.")
                patches, new_curve_ids, message = self._create_closed_surface(resolved)
                created_curves.extend(new_curve_ids)
                created_patch = patches[0] if patches else None
                if created_patch is None:
                    self._rollback_new_points(created_points)
                    self._reset_after_commit()
                    return ClothDrawingOutcome(False, message=message)
            else:
                curve = self.document.add_polyline(resolved, closed=False)
                created_curves.append(curve.id)
                message = "Open polyline created. Close a loop before creating a textile face."
        else:
            self._rollback_new_points(created_points)
            self._reset_after_commit()
            return ClothDrawingOutcome(False, message=f"Unsupported Cloth trace mode: {draft.mode}")

        # Cloth behaves like a fast 3D surface sketcher: whenever the newly
        # committed boundary closes a safe loop, materialise its face
        # immediately.  Face mode remains available for ambiguous/legacy loops,
        # but the normal Line/Polyline/Arc workflow does not require it.
        if created_patch is None and created_curves:
            auto_patch, auto_message = self._auto_create_faces(created_curves)
            if auto_patch is not None:
                created_patch = auto_patch
                message = auto_message
            elif auto_message:
                message = f"{message} {auto_message}".strip()

        outcome = ClothDrawingOutcome(
            True,
            True,
            tuple(created_points),
            tuple(created_curves),
            created_patch.id if created_patch is not None else None,
            message,
        )
        self._reset_after_commit()
        return outcome

    def _auto_create_faces(self, new_curve_ids: Iterable[str]) -> tuple[ClothPatch | None, str]:
        plan = discover_auto_face_loops(self.document, new_curve_ids)
        if not plan.found:
            return None, plan.message
        first_patch: ClothPatch | None = None
        created_count = 0
        for loop in plan.loops:
            before = set(self.document.patches)
            outcome = self.create_patch_from_curves(loop.curve_ids)
            if not outcome.committed:
                continue
            new_ids = tuple(patch_id for patch_id in self.document.patches if patch_id not in before)
            if first_patch is None and new_ids:
                first_patch = self.document.patches[new_ids[0]]
            created_count += len(new_ids)
        if first_patch is None:
            return None, ""
        if created_count == 1:
            return first_patch, f"{first_patch.name} created automatically from the closed boundary."
        return first_patch, f"{created_count} textile faces created automatically from the closed 3D boundary."

    def _create_closed_surface(
        self,
        point_ids: list[str],
        *,
        metadata: dict[str, object] | None = None,
    ) -> tuple[list[ClothPatch], list[str], str]:
        plan = plan_closed_loop_surface(self.document, point_ids)
        if not plan.valid:
            return [], [], plan.message or "The closed loop cannot form a textile surface."

        created_curves: list[str] = []
        patches: list[ClothPatch] = []

        def edge(first_id: str, second_id: str) -> str:
            curve, created = self._line_between(first_id, second_id)
            if created:
                created_curves.append(curve.id)
            return curve.id

        if plan.planar:
            boundary = [edge(point_ids[index], point_ids[(index + 1) % len(point_ids)]) for index in range(len(point_ids))]
            patch = self.document.add_patch(
                boundary,
                name=f"Panel {len(self.document.patches) + 1}",
                metadata=dict(metadata or {}),
            )
            self._auto_create_folds(patch)
            patches.append(patch)
            return patches, created_curves, f"{patch.name} created."

        region_id = self.document.new_id("region")
        for triangle_index, triangle in enumerate(plan.triangles, start=1):
            a, b, c = (point_ids[index] for index in triangle)
            boundary = (edge(a, b), edge(b, c), edge(c, a))
            patch = self.document.add_patch(
                boundary,
                name=f"Panel {len(self.document.patches) + 1}",
                metadata={
                    **dict(metadata or {}),
                    "cloth_region_id": region_id,
                    "cloth_auto_triangle": True,
                    "cloth_region_triangle_index": triangle_index,
                },
            )
            self._auto_create_folds(patch)
            patches.append(patch)
        return (
            patches,
            created_curves,
            f"3D surface created as {len(patches)} planar textile faces (non-planar loop: {plan.max_planarity_error_mm:.3g} mm).",
        )

    def _line_between(self, first_id: str, second_id: str) -> tuple[ClothCurve, bool]:
        if first_id == second_id:
            raise ValueError("A Cloth edge needs two distinct points.")
        for curve in self.document.curves.values():
            if curve.kind is not ClothCurveKind.LINE:
                continue
            a, b = curve_endpoint_ids(curve)
            if {a, b} == {first_id, second_id}:
                return curve, False
        return self.document.add_line(first_id, second_id), True

    def _auto_create_folds(self, patch: ClothPatch) -> None:
        incidence = curve_patch_incidence(self.document)
        existing_by_curve = {fold.curve_id for fold in self.document.folds.values()}
        for curve_id in patch.outer_curve_ids:
            curve = self.document.curves.get(curve_id)
            patch_ids = incidence.get(curve_id, ())
            if curve is None or curve.kind is not ClothCurveKind.LINE or len(patch_ids) != 2 or curve_id in existing_by_curve:
                continue
            angle = infer_fold_angle(self.document, curve_id, patch_ids[0], patch_ids[1])
            kind = ClothFoldKind.VALLEY if angle > 1.0e-6 else ClothFoldKind.MOUNTAIN if angle < -1.0e-6 else ClothFoldKind.NEUTRAL
            self.document.add_fold(curve_id, patch_ids[0], patch_ids[1], angle_degrees=angle, kind=kind)

    def _nearest_document_point(self, position: Point3, *, tolerance: float) -> str | None:
        best: tuple[float, str] | None = None
        for point in self.document.points.values():
            distance = math.dist(position, point.position)
            if distance <= tolerance and (best is None or distance < best[0]):
                best = (distance, point.id)
        return best[1] if best is not None else None

    @staticmethod
    def _point3(position: Iterable[float]) -> Point3:
        values = tuple(float(value) for value in position)
        if len(values) != 3:
            raise ValueError("Cloth draft points require three coordinates.")
        return (values[0], values[1], values[2])

    def _position_for_token(self, token: str) -> Point3 | None:
        point = self.document.points.get(str(token))
        if point is not None:
            return point.position
        return self.pending_positions.get(str(token))

    def _new_pending(self, position: Iterable[float]) -> str:
        values = tuple(float(value) for value in position)
        if len(values) != 3:
            raise ValueError("Cloth draft points require three coordinates.")
        token = f"draft:{self._next_pending_id}"
        self._next_pending_id += 1
        self.pending_positions[token] = (values[0], values[1], values[2])
        return token

    def _rollback_new_points(self, point_ids: Iterable[str]) -> None:
        for point_id in point_ids:
            self.document.points.pop(point_id, None)

    def _restore_document(self, source: ClothDocument) -> None:
        """Restore a failed compound operation without replacing references."""

        self.document.layers = source.layers
        self.document.points = source.points
        self.document.curves = source.curves
        self.document.patches = source.patches
        self.document.folds = source.folds
        self.document.seams = source.seams
        self.document.metadata = source.metadata
        self.document.revision = source.revision
        self.document._next_id = source._next_id

    def _reset_after_commit(self) -> None:
        self.trace.reset()
        self.pending_positions.clear()

    def _progress_message(self) -> str:
        count = len(self.trace.draft.point_ids)
        mode = self.trace.draft.mode
        if mode == TraceMode.LINE.value:
            return "Place the line end." if count == 1 else "Line ready."
        if mode == TraceMode.ARC.value:
            return ("Place the arc end." if count == 1 else "Place the arc control point." if count == 2 else "Arc ready.")
        if mode == TraceMode.POLYLINE.value:
            return "Continue the polyline. Click its first point to close, or press Enter to finish open."
        return "Point placed."


def infer_fold_angle(document: ClothDocument, curve_id: str, patch_a_id: str, patch_b_id: str) -> float:
    """Return the signed dihedral angle around a shared straight edge."""

    curve = document.curves[curve_id]
    start_id, end_id = curve_endpoint_ids(curve)
    start = document.points[start_id].position
    end = document.points[end_id].position
    edge = tuple(end[index] - start[index] for index in range(3))
    edge_length = math.sqrt(sum(value * value for value in edge))
    if edge_length <= 1.0e-12:
        return 0.0
    axis = tuple(value / edge_length for value in edge)
    frame_a = patch_frame(document, patch_a_id)
    frame_b = patch_frame(document, patch_b_id)
    if frame_a is None or frame_b is None:
        return 0.0
    na, nb = frame_a.normal, frame_b.normal
    dot = max(-1.0, min(1.0, sum(na[index] * nb[index] for index in range(3))))
    cross = (
        na[1] * nb[2] - na[2] * nb[1],
        na[2] * nb[0] - na[0] * nb[2],
        na[0] * nb[1] - na[1] * nb[0],
    )
    signed = math.atan2(sum(axis[index] * cross[index] for index in range(3)), dot)
    return math.degrees(signed)


__all__ = ["ClothDrawingController", "ClothDrawingOutcome", "infer_fold_angle"]
