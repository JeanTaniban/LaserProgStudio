# -*- coding: utf-8 -*-
"""Plan tracer 2D pattern generators.

The Plan tracer "Build · patterns" section turns an existing sketch face into a
parametric perforation: a catalogue of motifs that range from classic structural
grids (square cells, honeycomb, brick) to organic cells and to ``living hinge``
slot patterns used to make thin plywood bendable.

Every motif is a function returning a list of candidate polygons in face-plane
coordinates.  The generator clips each candidate against the actual face (with
its holes) before sketching it: cell-style motifs require full containment so
they keep their characteristic shape, while slot-style motifs (the grid slots
and the three living-hinge variants) are intersected with the face so they can
run from edge to edge while staying inside the boundary.

The catalogue is intentionally orthogonal:

* ``cell_size`` — pitch / nominal motif size
* ``wall`` — material left between openings (also the kerf for living hinges)
* ``margin`` — distance kept from the face boundary; at zero, candidates may be clipped on the boundary
* ``angle`` — pattern rotation around the face centroid (degrees)
* ``aspect`` — per-motif secondary ratio (slot length, star pointiness, …)
* ``seed`` — deterministic stochastic patterns (organic cells, voronoi)
* ``keep_form`` — legacy compatibility flag; Pattern now always remains a compact perforation owned by the host face
"""
from __future__ import annotations

import math
import random
import time
from collections import OrderedDict
from typing import Any, Callable, Iterable

from laserprog_studio.tool_api.core import MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_api.sketch import face_signature_from_points

from .services import _PlanTrace2DService

_PATTERN_TAG = "plan_trace_2d.pattern"
_PATTERN_POINT_TAG = "plan_trace_2d.pattern.point"
_PATTERN_PREVIEW_PREFIX = "plan_trace_2d.pattern.preview:"
_PATTERN_PREVIEW_BATCH_ID = f"{_PATTERN_PREVIEW_PREFIX}segments"

# Preview must stay interactive.  A too-fine motif can create tens of thousands
# of sketch segments, which makes both Qt and the sketch solver crawl.  The
# Pattern overlay can pass tighter/looser budgets, but these defaults keep the
# generator safe when called directly.
PATTERN_PREVIEW_SEGMENT_BUDGET = 120000
PATTERN_APPLY_SEGMENT_BUDGET = 120000


PATTERN_KIND_CHOICES: tuple[tuple[str, str], ...] = (
    ("honeycomb", "Honeycomb"),
    ("square", "Squares"),
    ("circle", "Circles"),
    ("diamond", "Diamonds"),
    ("triangle", "Triangles"),
    ("brick", "Offset bricks"),
    ("cross", "Crosses"),
    ("star", "Stars"),
    ("rings", "Concentric rings"),
    ("grid", "Horizontal slots"),
    ("wave", "Sine waves"),
    ("organic", "Organic cells"),
    ("hinge_straight", "Living hinge – straight"),
    ("hinge_lattice", "Living hinge – lattice"),
    ("hinge_wave", "Living hinge – wave"),
)


# Slot-style motifs: candidates are clipped against the face polygon instead of
# being rejected when they cross the boundary.  This lets long thin shapes run
# from edge to edge while still respecting the margin.
_CLIPPED_KINDS: frozenset[str] = frozenset(
    {"grid", "wave", "rings", "hinge_straight", "hinge_lattice", "hinge_wave"}
)


# ---------------------------------------------------------------------------
# Polygon helpers
# ---------------------------------------------------------------------------


def _ring_area(points: Iterable[tuple[float, float]]) -> float:
    pts = tuple((float(x), float(y)) for x, y in points)
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for index, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(index + 1) % len(pts)]
        area += x0 * y1 - x1 * y0
    return 0.5 * area


def _ensure_ccw(points: Iterable[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    pts = tuple((float(x), float(y)) for x, y in points)
    if _ring_area(pts) < 0.0:
        return tuple(reversed(pts))
    return pts


def _bounds(points: Iterable[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    pts = tuple(points)
    if not pts:
        return None
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _point_in_poly(point: tuple[float, float], polygon: tuple[tuple[float, float], ...]) -> bool:
    x, y = float(point[0]), float(point[1])
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1.0e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def _rotate(
    polys: Iterable[tuple[tuple[float, float], ...]],
    *,
    cx: float,
    cy: float,
    angle_rad: float,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    if abs(angle_rad) < 1.0e-9:
        return tuple(polys)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    out: list[tuple[tuple[float, float], ...]] = []
    for poly in polys:
        rotated = tuple(
            (
                cx + cos_a * (x - cx) - sin_a * (y - cy),
                cy + sin_a * (x - cx) + cos_a * (y - cy),
            )
            for x, y in poly
        )
        out.append(rotated)
    return tuple(out)


def _simplify_ring(points: tuple[tuple[float, float], ...], tol: float = 1.0e-6) -> tuple[tuple[float, float], ...]:
    """Remove duplicated consecutive vertices that confuse the sketch compiler."""

    cleaned: list[tuple[float, float]] = []
    for x, y in points:
        if cleaned:
            px, py = cleaned[-1]
            if abs(px - x) <= tol and abs(py - y) <= tol:
                continue
        cleaned.append((float(x), float(y)))
    if len(cleaned) >= 2:
        fx, fy = cleaned[0]
        lx, ly = cleaned[-1]
        if abs(fx - lx) <= tol and abs(fy - ly) <= tol:
            cleaned.pop()
    return tuple(cleaned)


def _strip_collinear_vertices(
    points: tuple[tuple[float, float], ...],
    *,
    tol: float = 1.0e-7,
) -> tuple[tuple[float, float], ...]:
    """Remove collinear vertices without changing the closed-ring topology."""

    pts = _simplify_ring(points, tol=tol)
    if len(pts) < 4:
        return pts
    out: list[tuple[float, float]] = []
    n = len(pts)
    for index, point in enumerate(pts):
        prev = pts[(index - 1) % n]
        nxt = pts[(index + 1) % n]
        ax, ay = point[0] - prev[0], point[1] - prev[1]
        bx, by = nxt[0] - point[0], nxt[1] - point[1]
        cross = ax * by - ay * bx
        # Keep sharp turns and very small-but-real segments.  Only suppress
        # perfectly straight solver noise generated by clipping operations.
        if abs(cross) > tol:
            out.append(point)
    return tuple(out) if len(out) >= 3 else pts


def _safe_closed_ring(
    points: Iterable[tuple[float, float]],
    *,
    min_area: float = 1.0e-6,
) -> tuple[tuple[float, float], ...]:
    """Return a clean, CCW, solver-friendly single boundary ring."""

    ring = _strip_collinear_vertices(tuple((float(x), float(y)) for x, y in points))
    if len(ring) < 3 or abs(_ring_area(ring)) <= float(min_area):
        return ()
    return _ensure_ccw(ring)


# ---------------------------------------------------------------------------
# Tool service
# ---------------------------------------------------------------------------


class PlanTrace2DPatternService(_PlanTrace2DService):
    """Generate repeatable cut/structure patterns inside an existing sketch face."""

    _UNION_FOOTPRINT_CACHE_LIMIT = 24
    _UNION_PATTERN_CACHE_LIMIT = 12

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        # Pattern previews repeatedly rebuild from the same baseline while only
        # pitch/wall/angle change.  The selected-face union is therefore stable
        # and can be reused.  Keep the cache local and bounded so unrelated tools
        # and long sessions cannot retain arbitrary Shapely geometries.
        self._union_footprint_cache: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        # The overlay preview and the final Apply use the same selected union and
        # parameters.  Cache the generated openings *and* their per-face split so
        # Apply can commit the already validated preview instead of repeating
        # candidate clipping and GEOS intersections.
        self._union_pattern_cache: OrderedDict[
            tuple[Any, ...],
            tuple[
                tuple[tuple[tuple[float, float], ...], ...],
                tuple[tuple[str, tuple[tuple[tuple[float, float], ...], ...]], ...],
                int,
                bool,
                int,
            ],
        ] = OrderedDict()

    @staticmethod
    def _audit_timing(name: str, started: float, **values: Any) -> None:
        try:
            from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

            audit.record_timing(name, (time.perf_counter() - started) * 1000.0)
            for key, value in values.items():
                audit.set_value(f"{name}.{key}", value)
        except Exception:
            pass

    # ------------------------------------------------------------------ flow

    def begin_face_pick(self, ctx: Any) -> bool:
        if self._state.plane is None:
            try:
                ctx.status.info("Plan tracer pattern: lock a drawing plane first.")
            except Exception:
                pass
            return False
        self._state.pattern_pick_face_active = True
        try:
            ctx.status.info("Pattern: click a Plan Tracer face to receive the pattern.")
        except Exception:
            pass
        self.services.overlay._sync_reports(ctx)
        return True

    def handle_event(self, ctx: Any, event: ToolEvent) -> bool:
        if not bool(getattr(self._state, "pattern_pick_face_active", False)):
            return False
        if (
            event.type != ToolEventType.MOUSE_PRESS
            or event.button != MouseButton.LEFT
            or event.screen_pos is None
        ):
            return False
        world_to_screen = getattr(ctx.viewport, "world_to_screen", None)
        try:
            from laserprog_studio.tool_api.scene import projection_cache_signature

            hit = ctx.selection.hit_test(
                event.screen_pos,
                world_to_screen or (lambda p: (float(p[0]), float(p[1]))),
                owner_tool=self.id,
                selectable_only=True,
                projection_key=projection_cache_signature(ctx),
            )
        except Exception:
            hit = None
        if hit is None:
            try:
                ctx.status.info("Pattern: click an existing Plan Tracer face, not empty space.")
            except Exception:
                pass
            return True
        try:
            actor = ctx.selection.actor(str(hit.actor_id))
        except Exception:
            actor = None
        metadata = getattr(actor, "metadata", {}) if actor is not None else {}
        if str(metadata.get("plan_trace_role") or "") != "face":
            try:
                ctx.status.info("Pattern: the selected item is not a face.")
            except Exception:
                pass
            return True
        face_id = str(metadata.get("plan_trace_sketch_face_id") or "")
        if not face_id or face_id not in self._state.sketch.faces:
            try:
                ctx.status.info("Pattern: selected face is stale; rebuild faces and retry.")
            except Exception:
                pass
            return True
        self._state.pattern_pick_face_active = False
        self._state.pattern_face_id = face_id
        self._state.pattern_face_ids = (face_id,)
        try:
            ctx.selection.select(str(hit.actor_id), replace=True)
        except Exception:
            pass
        try:
            ctx.status.info(
                f"Pattern face selected: {face_id}. Choose a pattern and press Generate."
            )
        except Exception:
            pass
        self.services.overlay._sync_reports(ctx)
        try:
            self.services.motif_overlay.on_face_picked(ctx)
        except Exception:
            pass
        try:
            self.services.motif_overlay.refresh(ctx)
        except Exception:
            pass
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        return True

    def selected_face_text(self) -> str:
        if bool(getattr(self._state, "pattern_pick_face_active", False)):
            return "Click a face…"
        face_ids = tuple(
            str(value)
            for value in tuple(getattr(self._state, "pattern_face_ids", ()) or ())
            if str(value) in self._state.sketch.faces
        )
        if not face_ids:
            face_id = str(getattr(self._state, "pattern_face_id", "") or "")
            if face_id in self._state.sketch.faces:
                face_ids = (face_id,)
            elif face_id:
                # Preserve the legacy label across a topology rebuild where the
                # solver may assign a new face id.  The stale id is informative
                # and existing callers/tests rely on seeing the selected target.
                return face_id
        if not face_ids:
            return "No face selected"
        if len(face_ids) == 1:
            face = self._state.sketch.faces[face_ids[0]]
            try:
                area = abs(_ring_area(tuple(getattr(face, "polygon_points", ()) or ())))
                return f"{face_ids[0]} · {area:.1f} mm²"
            except Exception:
                return face_ids[0]
        try:
            footprint = self._union_face_footprint(
                tuple(self._state.sketch.faces[face_id] for face_id in face_ids),
                ignore_existing_pattern_holes=True,
            )
            if footprint is not None:
                area = float(getattr(footprint, "area", 0.0) or 0.0)
            else:
                area = sum(
                    abs(_ring_area(tuple(getattr(self._state.sketch.faces[face_id], "polygon_points", ()) or ())))
                    for face_id in face_ids
                )
            return f"Union de {len(face_ids)} faces · {area:.1f} mm²"
        except Exception:
            return f"Union de {len(face_ids)} faces"

    # ------------------------------------------------------------------ params

    @staticmethod
    def _coerce_float(value: Any, default: float, *, minimum: float = 0.0) -> float:
        try:
            number = float(value)
        except Exception:
            return default
        if number < minimum:
            return minimum
        return number

    @staticmethod
    def _coerce_int(value: Any, default: int, *, minimum: int = 0) -> int:
        try:
            number = int(float(value))
        except Exception:
            return default
        if number < minimum:
            return minimum
        return number

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "checked", "coché", "coche", "oui"}:
            return True
        if text in {"0", "false", "no", "off", "unchecked", "décoché", "decoche", "non"}:
            return False
        return bool(default)

    def generate_from_panel(self, ctx: Any) -> bool:
        values: dict[str, Any] = {}
        try:
            values = ctx.inspector.values()
        except Exception:
            values = {}
        kind = str(values.get("plan_trace_2d.pattern_kind", "honeycomb") or "honeycomb")
        cell_size = self._coerce_float(
            values.get("plan_trace_2d.pattern_cell_size", 12.0), 12.0, minimum=0.5
        )
        wall = self._coerce_float(
            values.get("plan_trace_2d.pattern_wall", 2.0), 2.0, minimum=0.1
        )
        margin = self._coerce_float(
            values.get("plan_trace_2d.pattern_margin", 2.0), 2.0, minimum=0.0
        )
        angle = self._coerce_float(
            values.get("plan_trace_2d.pattern_angle", 0.0), 0.0, minimum=-360.0
        )
        aspect = self._coerce_float(
            values.get("plan_trace_2d.pattern_aspect", 1.0), 1.0, minimum=0.05
        )
        seed = self._coerce_int(
            values.get("plan_trace_2d.pattern_seed", 7), 7, minimum=0
        )
        keep_form = self._coerce_bool(values.get("plan_trace_2d.pattern_keep_form", True), True)
        return self.generate(
            ctx,
            kind=kind,
            cell_size=cell_size,
            wall=wall,
            margin=margin,
            angle=angle,
            aspect=aspect,
            seed=seed,
            keep_form=keep_form,
        )

    def generate_from_motif_state(self, ctx: Any) -> bool:
        """Run :meth:`generate` using the live Pattern overlay state.

        The motif overlay is the source of truth when it is open; the inspector
        panel mirrors it.  Reading from state keeps the two views consistent
        without round-tripping through the inspector cache.
        """

        return self.generate(
            ctx,
            kind=str(getattr(self._state, "motif_kind", "honeycomb") or "honeycomb"),
            cell_size=self._coerce_float(getattr(self._state, "motif_cell_size", 12.0), 12.0, minimum=0.5),
            wall=self._coerce_float(getattr(self._state, "motif_wall", 2.0), 2.0, minimum=0.1),
            margin=self._coerce_float(getattr(self._state, "motif_margin", 2.0), 2.0, minimum=0.0),
            angle=self._coerce_float(getattr(self._state, "motif_angle", 0.0), 0.0, minimum=-360.0),
            aspect=self._coerce_float(getattr(self._state, "motif_aspect", 1.0), 1.0, minimum=0.05),
            seed=self._coerce_int(getattr(self._state, "motif_seed", 7), 7, minimum=0),
            keep_form=bool(getattr(self._state, "motif_keep_form", True)),
            offset_x=self._coerce_float(getattr(self._state, "motif_offset_x", 0.0), 0.0, minimum=-1.0e6),
            offset_y=self._coerce_float(getattr(self._state, "motif_offset_y", 0.0), 0.0, minimum=-1.0e6),
        )

    def generate(
        self,
        ctx: Any,
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float = 0.0,
        aspect: float = 1.0,
        seed: int = 7,
        keep_form: bool = True,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        record_history: bool = True,
        preview_only: bool = False,
        max_segments: int | None = None,
    ) -> bool:
        face_id = str(getattr(self._state, "pattern_face_id", "") or "")
        if not face_id or face_id not in self._state.sketch.faces:
            try:
                ctx.status.info("Pattern: select a face first.")
            except Exception:
                pass
            return False
        face = self._state.sketch.faces[face_id]
        before = self.services.history._snapshot_state() if record_history else None
        try:
            created = self._generate_on_face(
                face,
                kind=str(kind),
                cell_size=float(cell_size),
                wall=float(wall),
                margin=float(margin),
                angle=float(angle),
                aspect=float(aspect),
                seed=int(seed),
                keep_form=bool(keep_form),
                offset_x=float(offset_x),
                offset_y=float(offset_y),
                max_segments=max_segments if max_segments is not None else int(getattr(self._state, "motif_preview_segment_budget", PATTERN_PREVIEW_SEGMENT_BUDGET) if preview_only else getattr(self._state, "motif_apply_segment_budget", PATTERN_APPLY_SEGMENT_BUDGET)),
            )
        except Exception as exc:
            if record_history:
                try:
                    ctx.status.info(f"Pattern generation failed: {exc}")
                except Exception:
                    pass
            return False
        if created <= 0:
            if record_history:
                try:
                    ctx.status.info(
                        "Pattern: no cell fits inside the selected face. "
                        "Try smaller cell size/margin or a different pattern."
                    )
                except Exception:
                    pass
            return False
        if preview_only:
            self._sync_preview_linework(ctx)
            self.services.overlay._sync_reports(ctx)
            self.services.rendering._render(ctx, sync_overlays=True, render=True)
            return True
        self._clear_preview_linework(ctx)
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._suppress_pattern_inner_faces()
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        self._refresh_pattern_face_id()
        if record_history and before is not None:
            self.services.history._record_snapshot_command(
                ctx, f"Generate {kind} pattern", before
            )
        self.services.overlay._sync_reports(ctx)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        if record_history:
            try:
                ctx.status.info(f"Pattern generated: {created} {kind} opening(s).")
            except Exception:
                pass
        return True

    # ------------------------------------------------------------------ core

    def _generate_on_face(
        self,
        face: Any,
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float = 0.0,
        aspect: float = 1.0,
        seed: int = 7,
        keep_form: bool = True,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        max_segments: int | None = None,
    ) -> int:
        """Legacy linework generation used by the inspector action/tests.

        The Pattern overlay no longer commits through this path because it would
        expand every opening into sketch points + lines, then make the topology
        solver discover hundreds of inner faces.  It remains available for the
        lower-level pattern API and is protected by the same segment budgets.
        """

        valid = self._valid_hole_polygons_for_face(
            face,
            kind=kind,
            cell_size=cell_size,
            wall=wall,
            margin=margin,
            angle=angle,
            aspect=aspect,
            seed=seed,
            keep_form=bool(keep_form),
            offset_x=offset_x,
            offset_y=offset_y,
            max_segments=max_segments,
            ignore_existing_pattern_holes=True,
        )
        if not valid:
            return 0
        self._remove_previous_pattern_entities()
        for poly in valid:
            self._add_closed_polyline(poly, kind=str(kind))
        self._state.pattern_generated_count = len(valid)
        self._state.pattern_face_id = (
            str(getattr(face, "id", "") or getattr(self._state, "pattern_face_id", ""))
        )
        self._state.pattern_face_ids = (str(self._state.pattern_face_id),) if self._state.pattern_face_id else ()
        return len(valid)

    def apply_as_face_holes(
        self,
        ctx: Any,
        face_id: str,
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float = 0.0,
        aspect: float = 1.0,
        seed: int = 7,
        keep_form: bool = True,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        max_segments: int | None = None,
        persistent: bool = True,
        render: bool = True,
    ) -> bool:
        """Attach motif holes directly to a face and sync the face actor.

        This is the high-performance Pattern-overlay path.  It keeps the sketch
        graph small: one face actor with ``hole_polygons`` instead of hundreds
        of individual hole edge actors.  It also means the final face is already
        perforated; the user does not have to click it with Modify to make the
        holes appear.
        """

        face = self._state.sketch.faces.get(str(face_id))
        if face is None:
            self._state.pattern_generated_count = 0
            return False
        valid = self._valid_hole_polygons_for_face(
            face,
            kind=kind,
            cell_size=cell_size,
            wall=wall,
            margin=margin,
            angle=angle,
            aspect=aspect,
            seed=seed,
            keep_form=bool(keep_form),
            offset_x=offset_x,
            offset_y=offset_y,
            max_segments=max_segments,
            ignore_existing_pattern_holes=True,
        )
        if not valid:
            self._apply_holes_to_face(face, (), kind=str(kind), persistent=persistent)
            self._sync_face_actor(ctx, str(face.id), render=render)
            return False
        self._remove_previous_pattern_entities()
        self._clear_preview_linework(ctx)
        self._apply_holes_to_face(face, tuple(valid), kind=str(kind), persistent=persistent)
        if persistent:
            self._store_assignment(
                (face,),
                kind=str(kind),
                cell_size=float(cell_size),
                wall=float(wall),
                margin=float(margin),
                angle=float(angle),
                aspect=float(aspect),
                seed=int(seed),
                offset_x=float(offset_x),
                offset_y=float(offset_y),
            )
        self._state.pattern_face_id = str(face.id)
        self._state.pattern_face_ids = (str(face.id),)
        self._state.pattern_generated_count = len(valid)
        self._sync_face_actor(ctx, str(face.id), render=render)
        return True

    def _union_pattern_cache_key(
        self,
        faces: tuple[Any, ...],
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float,
        aspect: float,
        seed: int,
        keep_form: bool = True,
        offset_x: float,
        offset_y: float,
    ) -> tuple[Any, ...]:
        specs = tuple(
            (
                str(face.id),
                self._face_footprint_cache_spec(
                    face,
                    ignore_existing_pattern_holes=True,
                ),
            )
            for face in faces
        )
        return (
            specs,
            str(kind),
            round(float(cell_size), 9),
            round(float(wall), 9),
            round(float(margin), 9),
            round(float(angle), 9),
            round(float(aspect), 9),
            int(seed),
            bool(keep_form),
            round(float(offset_x), 9),
            round(float(offset_y), 9),
        )

    def apply_as_union_face_holes(
        self,
        ctx: Any,
        face_ids: Iterable[str],
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float = 0.0,
        aspect: float = 1.0,
        seed: int = 7,
        keep_form: bool = True,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        max_segments: int | None = None,
        persistent: bool = True,
        render: bool = True,
    ) -> bool:
        """Apply one globally aligned motif to the union of selected faces.

        Candidate cells are generated once from the union bounds and clipped
        against the union footprint.  The resulting openings are then split
        back onto the source faces.  A cell crossing an internal boundary keeps
        the same global geometry on both sides instead of restarting the grid on
        each face.
        """

        ordered_ids = tuple(
            dict.fromkeys(
                str(face_id)
                for face_id in face_ids
                if str(face_id) in self._state.sketch.faces
            )
        )
        faces = tuple(self._state.sketch.faces[face_id] for face_id in ordered_ids)
        if not faces:
            self._state.pattern_generated_count = 0
            return False

        # v177: Pattern is always a face-owned parametric perforation.  The old
        # ``keep_form=False`` path converted the boolean material result into
        # thousands of authored sketch points/lines, making edit/reopen costs
        # explode and allowing stale motifs to accumulate.  Preserve the host
        # face boundary instead; edge-clipped candidates are regularised inside
        # that boundary below.  Keep the argument for source/preset compatibility.
        keep_form = True

        total_started = time.perf_counter()
        prepare_started = time.perf_counter()
        cache_key = self._union_pattern_cache_key(
            faces,
            kind=kind,
            cell_size=cell_size,
            wall=wall,
            margin=margin,
            angle=angle,
            aspect=aspect,
            seed=seed,
            keep_form=bool(keep_form),
            offset_x=offset_x,
            offset_y=offset_y,
        )
        requested_budget = None if max_segments is None else max(1, int(max_segments))
        cached = self._union_pattern_cache.get(cache_key)
        if cached is not None and requested_budget is not None and int(cached[2]) > requested_budget:
            cached = None
        if cached is not None:
            self._union_pattern_cache.move_to_end(cache_key)
            valid, cached_split, estimated_segments, limit_hit, budget_used = cached
            holes_by_face = dict(cached_split)
            self._state.pattern_generated_count = len(valid)
            self._state.motif_estimated_segments = int(estimated_segments)
            self._state.motif_segment_limit_hit = bool(limit_hit)
            self._state.motif_segment_budget_used = int(requested_budget or budget_used or 0)
            try:
                from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                audit.increment("toolctx.plan_trace.motif.union_pattern.cache_hits")
            except Exception:
                pass
            cache_path = "hit"
        else:
            generation_started = time.perf_counter()
            valid = self._valid_hole_polygons_for_faces(
                faces,
                kind=kind,
                cell_size=cell_size,
                wall=wall,
                margin=margin,
                angle=angle,
                aspect=aspect,
                seed=seed,
                keep_form=bool(keep_form),
                offset_x=offset_x,
                offset_y=offset_y,
                max_segments=max_segments,
                ignore_existing_pattern_holes=True,
            )
            self._audit_timing(
                "toolctx.plan_trace.motif.generate_union_openings",
                generation_started,
                face_count=len(faces),
                opening_count=len(valid),
            )
            if len(faces) == 1:
                # ``valid`` is already clipped against this exact face.  Running
                # every opening through a second footprint intersection is both
                # redundant and particularly expensive on dense rounded faces.
                holes_by_face = {str(faces[0].id): tuple(valid)}
            else:
                holes_by_face = self._split_union_holes_by_face(faces, valid)
            limit_hit = bool(getattr(self._state, "motif_segment_limit_hit", False))
            if not limit_hit:
                self._union_pattern_cache[cache_key] = (
                    tuple(valid),
                    tuple((face_id, tuple(holes_by_face.get(face_id, ()))) for face_id in ordered_ids),
                    int(getattr(self._state, "motif_estimated_segments", 0) or 0),
                    False,
                    int(getattr(self._state, "motif_segment_budget_used", 0) or 0),
                )
                self._union_pattern_cache.move_to_end(cache_key)
                while len(self._union_pattern_cache) > self._UNION_PATTERN_CACHE_LIMIT:
                    self._union_pattern_cache.popitem(last=False)
            try:
                from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                audit.increment("toolctx.plan_trace.motif.union_pattern.cache_misses")
                if limit_hit:
                    audit.increment("toolctx.plan_trace.motif.union_pattern.cache_skip_budget_limit")
            except Exception:
                pass
            cache_path = "miss_budget_limit" if limit_hit else "miss"
        self._audit_timing(
            "toolctx.plan_trace.motif.prepare_union",
            prepare_started,
            face_count=len(faces),
            opening_count=len(valid),
            cache_path=cache_path,
            cache_size=len(self._union_pattern_cache),
        )
        apply_started = time.perf_counter()
        self._remove_previous_pattern_entities()
        self._clear_preview_linework(ctx)
        for face in faces:
            self._apply_holes_to_face(
                face,
                holes_by_face.get(str(face.id), ()),
                kind=str(kind),
                persistent=persistent,
            )
            face.metadata["plan_trace_2d.pattern.union_face_ids"] = ordered_ids
            face.metadata["plan_trace_2d.pattern.union_opening_count"] = len(valid)

        if persistent and valid:
            self._store_assignment(
                faces,
                kind=str(kind),
                cell_size=float(cell_size),
                wall=float(wall),
                margin=float(margin),
                angle=float(angle),
                aspect=float(aspect),
                seed=int(seed),
                offset_x=float(offset_x),
                offset_y=float(offset_y),
            )
        self._state.pattern_face_ids = ordered_ids
        self._state.pattern_face_id = ordered_ids[0]
        self._state.pattern_generated_count = len(valid)
        self._audit_timing(
            "toolctx.plan_trace.motif.apply_union_holes",
            apply_started,
            face_count=len(faces),
            opening_count=len(valid),
        )
        sync_started = time.perf_counter()
        self._sync_face_actors(ctx, ordered_ids, render=render)
        self._audit_timing(
            "toolctx.plan_trace.motif.sync_union_faces",
            sync_started,
            face_count=len(faces),
        )
        self._audit_timing(
            "toolctx.plan_trace.motif.union_total",
            total_started,
            face_count=len(faces),
            opening_count=len(valid),
        )
        return bool(valid)

    def _apply_as_union_material_faces(
        self,
        ctx: Any,
        faces: tuple[Any, ...],
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float = 0.0,
        aspect: float = 1.0,
        seed: int = 7,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        max_segments: int | None = None,
        persistent: bool = True,
        render: bool = True,
    ) -> bool:
        """Apply a motif as the resulting face outline instead of face holes.

        ``keep_form=False`` is a destructive contour mode: the selected face
        perimeter is not preserved as a host boundary.  The motif openings are
        subtracted from the selected-face union and the remaining material
        polygons become the new direct Plan Tracer faces.  This is what lets a
        zero-margin motif cut the outside perimeter into the final scalloped or
        lattice outline instead of merely decorating the inside of the old face.
        """

        started = time.perf_counter()
        raw_footprint = self._union_face_footprint(
            faces,
            ignore_existing_pattern_holes=True,
        )
        if raw_footprint is None:
            self._state.pattern_generated_count = 0
            return False
        openings = self._valid_hole_polygons_for_faces(
            faces,
            kind=kind,
            cell_size=cell_size,
            wall=wall,
            margin=margin,
            angle=angle,
            aspect=aspect,
            seed=seed,
            keep_form=False,
            offset_x=offset_x,
            offset_y=offset_y,
            max_segments=max_segments,
            ignore_existing_pattern_holes=True,
        )
        if not openings:
            self._state.pattern_generated_count = 0
            return False
        material = self._material_footprint_after_openings(raw_footprint, openings)
        if material is None or getattr(material, "is_empty", False):
            self._state.pattern_generated_count = 0
            return False
        new_ids = self._replace_faces_with_material_result(
            ctx,
            faces,
            material,
            kind=str(kind),
            opening_count=len(openings),
            persistent=bool(persistent),
            render=bool(render),
        )
        self._state.pattern_generated_count = len(openings) if new_ids else 0
        self._audit_timing(
            "toolctx.plan_trace.motif.apply_material_result",
            started,
            source_face_count=len(faces),
            result_face_count=len(new_ids),
            opening_count=len(openings),
        )
        return bool(new_ids)

    @staticmethod
    def _material_footprint_after_openings(
        footprint: Any,
        openings: Iterable[tuple[tuple[float, float], ...]],
    ) -> Any | None:
        try:
            from shapely.geometry import Polygon
            from shapely.ops import unary_union
        except Exception:
            return None
        cutters: list[Any] = []
        for ring in openings:
            try:
                poly = Polygon(ring)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if not poly.is_empty and float(getattr(poly, "area", 0.0) or 0.0) > 1.0e-9:
                    cutters.append(poly)
            except Exception:
                continue
        if not cutters:
            return None
        try:
            cutter = cutters[0] if len(cutters) == 1 else unary_union(cutters)
            if not cutter.is_valid:
                cutter = cutter.buffer(0)
            material = footprint.difference(cutter)
            if not material.is_valid:
                material = material.buffer(0)
            if getattr(material, "is_empty", False):
                return None
            return material
        except Exception:
            return None

    @staticmethod
    def _explode_material_polygons(
        geometry: Any,
    ) -> tuple[tuple[tuple[tuple[float, float], ...], tuple[tuple[tuple[float, float], ...], ...]], ...]:
        if geometry is None or getattr(geometry, "is_empty", False):
            return ()
        polys: list[Any] = []
        geom_type = str(getattr(geometry, "geom_type", "") or "")
        if geom_type == "Polygon":
            polys = [geometry]
        elif geom_type == "MultiPolygon":
            polys = [part for part in getattr(geometry, "geoms", ()) if not getattr(part, "is_empty", True)]
        elif hasattr(geometry, "geoms"):
            for part in getattr(geometry, "geoms", ()) or ():
                polys.extend(part for part, _holes in PlanTrace2DPatternService._explode_material_polygons(part))
            # The branch above already normalised recursively but lost holes in
            # the temporary unpacking, so fall through to the direct polygon path
            # only for actual polygon/multipolygon geometries.
            return tuple(
                item
                for part in getattr(geometry, "geoms", ()) or ()
                for item in PlanTrace2DPatternService._explode_material_polygons(part)
            )
        result: list[tuple[tuple[tuple[float, float], ...], tuple[tuple[tuple[float, float], ...], ...]]] = []
        for poly in polys:
            exterior = _safe_closed_ring(tuple((float(x), float(y)) for x, y in poly.exterior.coords[:-1]))
            if len(exterior) < 3:
                continue
            holes = tuple(
                _safe_closed_ring(tuple((float(x), float(y)) for x, y in interior.coords[:-1]))
                for interior in tuple(getattr(poly, "interiors", ()) or ())
            )
            holes = tuple(hole for hole in holes if len(hole) >= 3)
            result.append((exterior, holes))
        return tuple(result)


    def _add_material_result_linework(
        self,
        sketch: Any,
        material: Any,
    ) -> tuple[
        tuple[
            tuple[tuple[float, float], ...],
            tuple[tuple[tuple[float, float], ...], ...],
            tuple[str, ...],
            tuple[tuple[str, ...], ...],
        ],
        ...,
    ]:
        """Material-result faces must be backed by real sketch contours.

        ``keep_form=False`` replaces the old face outline with the remaining
        material outline produced by the motif boolean.  The first implementation
        stored those outlines only as direct ``SketchFace`` polygons.  That looked
        correct in the viewport, but the Add/Apply/Subtract path recompiles the
        sketch before extrusion; the compiler is linework-driven, so anonymous
        direct faces were cleared and the operation failed without closing the
        tool.

        Build explicit point/line loops for every resulting exterior and hole,
        then add the faces after all lines are created.  Adding lines clears the
        generated-face cache by design, so returning specs keeps this operation
        deterministic and makes later compiles rebuild the same geometry.
        """

        specs: list[
            tuple[
                tuple[tuple[float, float], ...],
                tuple[tuple[tuple[float, float], ...], ...],
                tuple[str, ...],
                tuple[tuple[str, ...], ...],
            ]
        ] = []

        def add_ring_linework(ring: tuple[tuple[float, float], ...]) -> tuple[str, ...]:
            cleaned = _safe_closed_ring(ring)
            if len(cleaned) < 3:
                return ()
            point_ids: list[str] = []
            for point in cleaned:
                sketch_point = sketch.add_point(point)
                try:
                    sketch_point.metadata["plan_trace_2d.pattern.material_boundary"] = True
                    # Dense motif contours can create thousands of vertices.  Keep
                    # the contour lines selectable/visible, but do not flood the
                    # viewport with individual generated vertex handles.
                    sketch_point.metadata["hidden_control"] = True
                except Exception:
                    pass
                point_ids.append(str(sketch_point.id))
            line_ids: list[str] = []
            count = len(point_ids)
            for index, start_id in enumerate(point_ids):
                end_id = point_ids[(index + 1) % count]
                if start_id == end_id:
                    continue
                try:
                    line = sketch.add_line(start_id, end_id)
                    try:
                        line.metadata["plan_trace_2d.pattern.material_boundary"] = True
                    except Exception:
                        pass
                    line_ids.append(str(line.id))
                except Exception:
                    continue
            return tuple(line_ids)

        for exterior, holes in self._explode_material_polygons(material):
            exterior = _safe_closed_ring(exterior)
            if len(exterior) < 3:
                continue
            clean_holes = tuple(_safe_closed_ring(hole) for hole in holes)
            clean_holes = tuple(hole for hole in clean_holes if len(hole) >= 3)
            for hole in clean_holes:
                try:
                    sketch.suppressed_face_signatures.add(face_signature_from_points(hole))
                except Exception:
                    pass
            boundary_ids = add_ring_linework(exterior)
            if not boundary_ids:
                continue
            hole_boundary_ids = tuple(add_ring_linework(hole) for hole in clean_holes)
            specs.append((exterior, clean_holes, boundary_ids, hole_boundary_ids))
        return tuple(specs)

    def _replace_faces_with_material_result(
        self,
        ctx: Any,
        source_faces: tuple[Any, ...],
        material: Any,
        *,
        kind: str,
        opening_count: int,
        persistent: bool,
        render: bool,
    ) -> tuple[str, ...]:
        sketch = self._state.sketch
        source_ids = tuple(str(getattr(face, "id", "") or "") for face in source_faces)
        boundary_line_ids = {
            str(value)
            for face in source_faces
            for value in tuple(getattr(face, "boundary_entity_ids", ()) or ())
            if str(value) in sketch.lines
        }
        boundary_point_ids = {
            str(point_id)
            for line_id in boundary_line_ids
            for line in (sketch.lines.get(str(line_id)),)
            if line is not None
            for point_id in (getattr(line, "start_point_id", ""), getattr(line, "end_point_id", ""))
            if str(point_id) in sketch.points
        }
        registry = self._projected_registry(ctx)
        stale_actor_ids: list[str] = []
        for face_id in source_ids:
            sketch.faces.pop(face_id, None)
            try:
                stale_actor_ids.append(self.services.sketch_sync._face_actor_id(face_id))
            except Exception:
                pass
        for line_id in boundary_line_ids:
            sketch.lines.pop(line_id, None)
            try:
                stale_actor_ids.append(self.services.sketch_sync._line_actor_id(line_id))
            except Exception:
                pass
        if boundary_line_ids or boundary_point_ids:
            try:
                sketch.remove_dimensions_referencing(set(boundary_line_ids) | set(boundary_point_ids))
            except Exception:
                pass
        referenced_point_ids = {
            str(point_id)
            for line in tuple(sketch.lines.values())
            for point_id in (getattr(line, "start_point_id", ""), getattr(line, "end_point_id", ""))
        }
        referenced_point_ids.update(
            str(point_id)
            for arc in tuple(getattr(sketch, "arcs", {}).values())
            for point_id in (getattr(arc, "start_point_id", ""), getattr(arc, "end_point_id", ""), getattr(arc, "control_point_id", ""))
        )
        referenced_point_ids.update(
            str(point_id)
            for circle in tuple(getattr(sketch, "circles", {}).values())
            for point_id in (getattr(circle, "center_point_id", ""), getattr(circle, "radius_point_id", ""))
        )
        for point_id in tuple(boundary_point_ids):
            if point_id in referenced_point_ids:
                continue
            sketch.points.pop(point_id, None)
            stale_actor_ids.append(point_id)
        if registry is not None and stale_actor_ids:
            try:
                registry.remove_many(tuple(dict.fromkeys(stale_actor_ids)), render=False)
            except Exception:
                for actor_id in tuple(dict.fromkeys(stale_actor_ids)):
                    try:
                        registry.remove(str(actor_id), render=False)
                    except Exception:
                        pass
        self._clear_preview_linework(ctx)
        new_ids: list[str] = []
        face_specs = self._add_material_result_linework(sketch, material)
        for exterior, holes, boundary_ids, hole_boundary_ids in face_specs:
            face = sketch.add_face(
                boundary_ids,
                exterior,
                hole_polygons=holes,
                hole_boundary_entity_ids=hole_boundary_ids,
            )
            if face is None:
                continue
            face.metadata["plan_trace_2d.pattern.direct_holes"] = bool(holes)
            face.metadata["plan_trace_2d.pattern.keep_form"] = False
            face.metadata["plan_trace_2d.pattern.material_result"] = True
            face.metadata["plan_trace_2d.pattern.kind"] = str(kind)
            face.metadata["plan_trace_2d.pattern.opening_count"] = int(opening_count)
            face.metadata["plan_trace_2d.pattern.material_boundary_linework"] = True
            new_ids.append(str(face.id))
        if persistent:
            for face in source_faces:
                outer_signature = self._outer_signature(face)
                if outer_signature:
                    self._state.motif_face_holes_by_outer_signature.pop(outer_signature, None)
                    self._state.motif_face_hole_kinds.pop(outer_signature, None)
        self._state.pattern_face_ids = tuple(new_ids)
        self._state.pattern_face_id = new_ids[0] if new_ids else None
        if new_ids:
            self._sync_face_actors(ctx, tuple(new_ids), render=render)
        else:
            try:
                self.services.overlay._sync_reports(ctx)
                self.services.rendering._render(ctx, sync_overlays=True, render=render)
            except Exception:
                pass
        return tuple(new_ids)

    def _native_holes_for_face(
        self,
        face: Any,
    ) -> tuple[
        tuple[tuple[tuple[float, float], ...], ...],
        tuple[tuple[str, ...], ...],
    ]:
        """Return authored/native holes, excluding only motif-derived cache holes.

        A Pattern is a *modifier of a host face*, not the owner of the face's
        topology.  Earlier builds replaced ``face.hole_polygons`` wholesale, so
        an existing circular/arc-bounded opening could disappear as soon as a
        motif was applied.  The state cache contains only derived motif rings; use
        their stable signatures to subtract them from the current face while
        preserving every native hole and its boundary entity ids.
        """

        holes = tuple(
            tuple((float(x), float(y)) for x, y in hole)
            for hole in tuple(getattr(face, "hole_polygons", ()) or ())
            if len(hole) >= 3
        )
        boundary_ids_raw = tuple(getattr(face, "hole_boundary_entity_ids", ()) or ())
        boundary_ids: tuple[tuple[str, ...], ...] = tuple(
            tuple(str(value) for value in ids) for ids in boundary_ids_raw
        )
        if len(boundary_ids) < len(holes):
            boundary_ids = boundary_ids + tuple(() for _ in range(len(holes) - len(boundary_ids)))
        elif len(boundary_ids) > len(holes):
            boundary_ids = boundary_ids[: len(holes)]

        outer_signature = self._outer_signature(face)
        motif_holes = tuple(
            tuple((float(x), float(y)) for x, y in hole)
            for hole in tuple(
                getattr(self._state, "motif_face_holes_by_outer_signature", {}).get(outer_signature, ())
                if outer_signature
                else ()
            )
            if len(hole) >= 3
        )
        if not motif_holes:
            return holes, boundary_ids

        # Use a counted signature bag rather than positional assumptions.  A
        # topology compile can reorder native holes, whereas the geometry itself
        # remains stable.
        motif_signature_counts: dict[str, int] = {}
        for hole in motif_holes:
            try:
                signature = face_signature_from_points(hole)
            except Exception:
                signature = repr(tuple((round(x, 8), round(y, 8)) for x, y in hole))
            motif_signature_counts[signature] = motif_signature_counts.get(signature, 0) + 1

        native_holes: list[tuple[tuple[float, float], ...]] = []
        native_boundary_ids: list[tuple[str, ...]] = []
        for index, hole in enumerate(holes):
            try:
                signature = face_signature_from_points(hole)
            except Exception:
                signature = repr(tuple((round(x, 8), round(y, 8)) for x, y in hole))
            remaining = motif_signature_counts.get(signature, 0)
            if remaining > 0:
                motif_signature_counts[signature] = remaining - 1
                continue
            native_holes.append(hole)
            native_boundary_ids.append(boundary_ids[index] if index < len(boundary_ids) else ())
        return tuple(native_holes), tuple(native_boundary_ids)

    def _face_footprint_cache_spec(
        self,
        face: Any,
        *,
        ignore_existing_pattern_holes: bool,
    ) -> tuple[Any, ...] | None:
        outer = _ensure_ccw(tuple(getattr(face, "polygon_points", ()) or ()))
        if len(outer) < 3:
            return None
        if ignore_existing_pattern_holes:
            holes, _boundary_ids = self._native_holes_for_face(face)
        else:
            holes = tuple(
                tuple((float(x), float(y)) for x, y in hole)
                for hole in tuple(getattr(face, "hole_polygons", ()) or ())
                if len(hole) >= 3
            )
        return (outer, holes)

    def _union_face_footprint(
        self,
        faces: Iterable[Any],
        *,
        ignore_existing_pattern_holes: bool,
        inset: float = 0.0,
    ) -> Any | None:
        started = time.perf_counter()
        try:
            from shapely.geometry import Polygon
            from shapely.ops import unary_union
        except Exception:
            return None

        specs = tuple(
            spec
            for spec in (
                self._face_footprint_cache_spec(
                    face,
                    ignore_existing_pattern_holes=ignore_existing_pattern_holes,
                )
                for face in faces
            )
            if spec is not None
        )
        if not specs:
            return None
        # Union is independent of selection order.  Sorting lets Shift-clicking
        # the same faces in another order reuse the same footprint.
        cache_key = (
            tuple(sorted(specs, key=repr)),
            bool(ignore_existing_pattern_holes),
            round(float(inset), 9),
        )
        cached = self._union_footprint_cache.get(cache_key)
        if cached is not None:
            self._union_footprint_cache.move_to_end(cache_key)
            try:
                from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                audit.increment("toolctx.plan_trace.motif.union_footprint.cache_hits")
            except Exception:
                pass
            self._audit_timing(
                "toolctx.plan_trace.motif.union_footprint",
                started,
                face_count=len(specs),
                cache_size=len(self._union_footprint_cache),
            )
            return cached

        polygons: list[Any] = []
        for outer, holes in specs:
            try:
                polygon = Polygon(outer, holes=list(holes))
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
                if not polygon.is_empty and float(getattr(polygon, "area", 0.0) or 0.0) > 1.0e-9:
                    polygons.append(polygon)
            except Exception:
                continue
        if not polygons:
            return None
        try:
            footprint = polygons[0] if len(polygons) == 1 else unary_union(polygons)
            if not footprint.is_valid:
                footprint = footprint.buffer(0)
            if float(inset) > 1.0e-9 and not footprint.is_empty:
                reduced = footprint.buffer(-float(inset), join_style=2)
                if not reduced.is_empty:
                    footprint = reduced
            if footprint.is_empty:
                return None
        except Exception:
            return None

        self._union_footprint_cache[cache_key] = footprint
        self._union_footprint_cache.move_to_end(cache_key)
        while len(self._union_footprint_cache) > self._UNION_FOOTPRINT_CACHE_LIMIT:
            self._union_footprint_cache.popitem(last=False)
        try:
            from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

            audit.increment("toolctx.plan_trace.motif.union_footprint.cache_misses")
        except Exception:
            pass
        self._audit_timing(
            "toolctx.plan_trace.motif.union_footprint",
            started,
            face_count=len(specs),
            cache_size=len(self._union_footprint_cache),
        )
        return footprint

    def _valid_hole_polygons_for_faces(
        self,
        faces: tuple[Any, ...],
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float = 0.0,
        aspect: float = 1.0,
        seed: int = 7,
        keep_form: bool = True,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        max_segments: int | None = None,
        ignore_existing_pattern_holes: bool = False,
    ) -> tuple[tuple[tuple[float, float], ...], ...]:
        if cell_size <= 0.0 or not faces:
            self._state.pattern_generated_count = 0
            return ()
        raw_footprint = self._union_face_footprint(
            faces,
            ignore_existing_pattern_holes=ignore_existing_pattern_holes,
        )
        if raw_footprint is None:
            # Dependency-free fallback keeps prior behaviour on the first face.
            return self._valid_hole_polygons_for_face(
                faces[0],
                kind=kind,
                cell_size=cell_size,
                wall=wall,
                margin=margin,
                angle=angle,
                aspect=aspect,
                seed=seed,
                keep_form=bool(keep_form),
                offset_x=offset_x,
                offset_y=offset_y,
                max_segments=max_segments,
                ignore_existing_pattern_holes=ignore_existing_pattern_holes,
            )
        try:
            bbox = tuple(float(value) for value in raw_footprint.bounds)
        except Exception:
            self._state.pattern_generated_count = 0
            return ()
        if len(bbox) != 4:
            self._state.pattern_generated_count = 0
            return ()

        budget = None if max_segments is None else max(1, int(max_segments))
        estimated_segments = self.estimate_candidate_segments(
            kind=str(kind),
            bbox=bbox,
            cell_size=float(cell_size),
            wall=float(wall),
            margin=float(margin),
            angle=float(angle),
            aspect=float(aspect),
        )
        self._state.motif_estimated_segments = int(estimated_segments)
        self._state.motif_segment_budget_used = int(budget or 0)
        if budget is not None and estimated_segments > budget:
            self._state.pattern_generated_count = 0
            self._state.motif_segment_limit_hit = True
            return ()
        self._state.motif_segment_limit_hit = False

        candidates = self._candidate_polygons(
            kind=str(kind),
            bbox=bbox,
            cell_size=cell_size,
            wall=wall,
            margin=margin,
            angle=angle,
            aspect=aspect,
            seed=seed,
            offset_x=offset_x,
            offset_y=offset_y,
            allow_edge_clipping=float(margin) <= 1.0e-9,
        )
        clip_mode = str(kind) in _CLIPPED_KINDS or float(margin) <= 1.0e-9
        # A face-owned hole must be strictly interior.  Zero-margin cells used
        # to touch/share the host boundary and were then represented as closed
        # interior rings, which is topologically ambiguous and could make an
        # opening render/extrude as a filled face.  Keep an invisible 0.1 µm
        # clearance so the face remains valid without changing the visible motif.
        safe_inset = max(
            1.0e-4,
            0.0 if float(margin) <= 1.0e-9 else max(
                float(margin),
                min(max(float(wall), 0.05) * 0.5, max(float(cell_size), 0.05) * 0.25),
                0.02,
            ),
        )
        footprint = raw_footprint
        if clip_mode and safe_inset > 1.0e-9:
            try:
                reduced = raw_footprint.buffer(-safe_inset, join_style=2)
                if not reduced.is_empty:
                    footprint = reduced
            except Exception:
                footprint = raw_footprint
        valid = self._clip_candidates(
            candidates,
            footprint=footprint,
            outer=(),
            clip_mode=clip_mode,
            max_segments=budget,
        )
        self._state.pattern_generated_count = len(valid)
        return tuple(valid)

    def _split_union_holes_by_face(
        self,
        faces: tuple[Any, ...],
        holes: tuple[tuple[tuple[float, float], ...], ...],
    ) -> dict[str, tuple[tuple[tuple[float, float], ...], ...]]:
        started = time.perf_counter()
        result: dict[str, tuple[tuple[tuple[float, float], ...], ...]] = {
            str(face.id): () for face in faces
        }
        if not holes:
            self._audit_timing(
                "toolctx.plan_trace.motif.split_union_holes",
                started,
                face_count=len(faces),
                opening_count=0,
            )
            return result
        try:
            from shapely.geometry import Polygon
        except Exception:
            return result

        opening_geometries: list[tuple[Any, tuple[float, float, float, float]]] = []
        for ring in holes:
            try:
                opening = Polygon(ring)
                if not opening.is_valid:
                    opening = opening.buffer(0)
                if not opening.is_empty:
                    opening_geometries.append((opening, tuple(float(v) for v in opening.bounds)))
            except Exception:
                continue

        tested_pairs = 0
        intersected_pairs = 0
        for face in faces:
            footprint = self._union_face_footprint(
                (face,),
                ignore_existing_pattern_holes=True,
            )
            if footprint is None:
                continue
            face_bounds = tuple(float(v) for v in footprint.bounds)
            fragments: list[tuple[tuple[float, float], ...]] = []
            for opening, opening_bounds in opening_geometries:
                # Most motif cells belong to only one face.  Reject disjoint
                # bounding boxes before invoking GEOS intersection, avoiding the
                # previous O(faces × openings) expensive geometry operations.
                if (
                    opening_bounds[2] < face_bounds[0]
                    or opening_bounds[0] > face_bounds[2]
                    or opening_bounds[3] < face_bounds[1]
                    or opening_bounds[1] > face_bounds[3]
                ):
                    continue
                tested_pairs += 1
                try:
                    clipped = footprint.intersection(opening)
                except Exception:
                    continue
                if clipped.is_empty:
                    continue
                intersected_pairs += 1
                for piece in self._explode_polygons(clipped):
                    ring = _safe_closed_ring(piece)
                    if len(ring) >= 3:
                        fragments.append(_ensure_ccw(ring))
            result[str(face.id)] = tuple(fragments)
        self._audit_timing(
            "toolctx.plan_trace.motif.split_union_holes",
            started,
            face_count=len(faces),
            opening_count=len(opening_geometries),
            tested_pairs=tested_pairs,
            intersected_pairs=intersected_pairs,
        )
        return result

    def _valid_hole_polygons_for_face(
        self,
        face: Any,
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float = 0.0,
        aspect: float = 1.0,
        seed: int = 7,
        keep_form: bool = True,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        max_segments: int | None = None,
        ignore_existing_pattern_holes: bool = False,
    ) -> tuple[tuple[tuple[float, float], ...], ...]:
        if cell_size <= 0.0:
            self._state.pattern_generated_count = 0
            return ()
        outer = _ensure_ccw(tuple(getattr(face, "polygon_points", ()) or ()))
        if ignore_existing_pattern_holes:
            holes, _native_boundary_ids = self._native_holes_for_face(face)
        else:
            holes = tuple(
                tuple((float(x), float(y)) for x, y in hole)
                for hole in tuple(getattr(face, "hole_polygons", ()) or ())
                if len(hole) >= 3
            )
        bbox = _bounds(outer)
        if bbox is None or len(outer) < 3:
            self._state.pattern_generated_count = 0
            return ()
        budget = None if max_segments is None else max(1, int(max_segments))
        estimated_segments = self.estimate_candidate_segments(
            kind=str(kind),
            bbox=bbox,
            cell_size=float(cell_size),
            wall=float(wall),
            margin=float(margin),
            angle=float(angle),
            aspect=float(aspect),
        )
        self._state.motif_estimated_segments = int(estimated_segments)
        self._state.motif_segment_budget_used = int(budget or 0)
        if budget is not None and estimated_segments > budget:
            self._state.pattern_generated_count = 0
            self._state.motif_segment_limit_hit = True
            return ()
        self._state.motif_segment_limit_hit = False
        candidates = self._candidate_polygons(
            kind=str(kind),
            bbox=bbox,
            cell_size=cell_size,
            wall=wall,
            margin=margin,
            angle=angle,
            aspect=aspect,
            seed=seed,
            offset_x=offset_x,
            offset_y=offset_y,
            allow_edge_clipping=float(margin) <= 1.0e-9,
        )
        clip_mode = str(kind) in _CLIPPED_KINDS or float(margin) <= 1.0e-9
        # Closed face holes normally stay strictly inside the outer boundary: Shapely/VTK
        # represent holes as interior rings, and rings sharing an edge with the
        # outer face make the face invalid.  Slot-style motifs are still clipped
        # so they visually follow triangular/irregular faces, but clipping is
        # done against an inward offset of the face.  This keeps the generated
        # rings closed, valid and safely inside the selected face instead of
        # producing malformed boundary-sharing vertices.
        safe_inset = max(
            1.0e-4,
            0.0 if float(margin) <= 1.0e-9 else max(
                float(margin),
                min(max(float(wall), 0.05) * 0.5, max(float(cell_size), 0.05) * 0.25),
                0.02,
            ),
        )
        footprint = self._shapely_face_polygon(outer, holes, inset=safe_inset if clip_mode else 0.0)
        valid = self._clip_candidates(
            candidates, footprint=footprint, outer=outer, clip_mode=clip_mode, max_segments=budget
        )
        self._state.pattern_generated_count = len(valid)
        return tuple(valid)

    @staticmethod
    def _outer_signature(face: Any) -> str:
        try:
            return face_signature_from_points(tuple(getattr(face, "polygon_points", ()) or ()))
        except Exception:
            return ""

    @staticmethod
    def _assignment_group_id(target_outer_signatures: Iterable[str]) -> str:
        targets = tuple(sorted(str(value) for value in target_outer_signatures if str(value)))
        return "motif:" + "|".join(targets)

    def assignment_for_face(self, face: Any) -> dict[str, Any] | None:
        signature = self._outer_signature(face)
        if not signature:
            return None
        value = getattr(self._state, "motif_assignments_by_outer_signature", {}).get(signature)
        return dict(value) if isinstance(value, dict) else None

    def _detach_assignments_for_signatures(self, signatures: Iterable[str]) -> None:
        """Remove/re-scope any previous motif touching the target faces.

        Assignments are duplicated by host signature for O(1) lookup, but a union
        motif can own several faces.  Replacing the motif on one face must not
        leave a stale group copy that later re-applies the old motif to it.
        """

        removed = {str(value) for value in signatures if str(value)}
        if not removed:
            return
        current = dict(getattr(self._state, "motif_assignments_by_outer_signature", {}) or {})
        unique: dict[str, dict[str, Any]] = {}
        for key, raw in current.items():
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            targets = tuple(str(v) for v in item.get("target_outer_signatures", ()) if str(v))
            if not targets:
                targets = (str(key),)
            gid = str(item.get("group_id") or self._assignment_group_id(targets))
            unique.setdefault(gid, item)
        rebuilt: dict[str, dict[str, Any]] = {}
        for item in unique.values():
            targets = tuple(str(v) for v in item.get("target_outer_signatures", ()) if str(v))
            remaining = tuple(value for value in targets if value not in removed)
            if not remaining:
                continue
            updated = dict(item)
            updated["target_outer_signatures"] = remaining
            updated["group_id"] = self._assignment_group_id(remaining)
            for signature in remaining:
                rebuilt[signature] = dict(updated)
        self._state.motif_assignments_by_outer_signature = rebuilt

    def _store_assignment(
        self,
        faces: Iterable[Any],
        *,
        kind: str,
        cell_size: float,
        wall: float,
        margin: float,
        angle: float,
        aspect: float,
        seed: int,
        offset_x: float,
        offset_y: float,
    ) -> None:
        signatures = tuple(
            signature for signature in (self._outer_signature(face) for face in faces) if signature
        )
        if not signatures:
            return
        self._detach_assignments_for_signatures(signatures)
        payload: dict[str, Any] = {
            "schema_version": 1,
            "group_id": self._assignment_group_id(signatures),
            "target_outer_signatures": signatures,
            "kind": str(kind),
            "cell_size": float(cell_size),
            "wall": float(wall),
            "margin": float(margin),
            "keep_form": True,
            "angle": float(angle),
            "aspect": float(aspect),
            "seed": int(seed),
            "offset_x": float(offset_x),
            "offset_y": float(offset_y),
        }
        for signature in signatures:
            self._state.motif_assignments_by_outer_signature[signature] = dict(payload)

    def _restore_parametric_assignments_after_compile(self) -> int:
        assignments = dict(getattr(self._state, "motif_assignments_by_outer_signature", {}) or {})
        if not assignments:
            return 0
        faces_by_signature = {
            self._outer_signature(face): face
            for face in tuple(self._state.sketch.faces.values())
            if self._outer_signature(face)
        }
        unique: dict[str, dict[str, Any]] = {}
        for key, raw in assignments.items():
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            targets = tuple(str(v) for v in item.get("target_outer_signatures", ()) if str(v))
            if not targets:
                targets = (str(key),)
                item["target_outer_signatures"] = targets
            gid = str(item.get("group_id") or self._assignment_group_id(targets))
            unique.setdefault(gid, item)

        restored = 0
        for assignment in unique.values():
            target_signatures = tuple(
                str(value) for value in assignment.get("target_outer_signatures", ()) if str(value)
            )
            faces = tuple(faces_by_signature[sig] for sig in target_signatures if sig in faces_by_signature)
            if not faces:
                continue
            try:
                valid = self._valid_hole_polygons_for_faces(
                    faces,
                    kind=str(assignment.get("kind") or "honeycomb"),
                    cell_size=max(0.5, float(assignment.get("cell_size", 12.0))),
                    wall=max(0.1, float(assignment.get("wall", 2.0))),
                    margin=max(0.0, float(assignment.get("margin", 2.0))),
                    angle=float(assignment.get("angle", 0.0)),
                    aspect=max(0.05, float(assignment.get("aspect", 1.0))),
                    seed=max(0, int(assignment.get("seed", 7))),
                    keep_form=True,
                    offset_x=float(assignment.get("offset_x", 0.0)),
                    offset_y=float(assignment.get("offset_y", 0.0)),
                    max_segments=int(getattr(self._state, "motif_apply_segment_budget", PATTERN_APPLY_SEGMENT_BUDGET) or PATTERN_APPLY_SEGMENT_BUDGET),
                    ignore_existing_pattern_holes=True,
                )
            except Exception:
                continue
            if not valid:
                continue
            holes_by_face = (
                {str(faces[0].id): tuple(valid)}
                if len(faces) == 1
                else self._split_union_holes_by_face(faces, tuple(valid))
            )
            for face in faces:
                self._apply_holes_to_face(
                    face,
                    holes_by_face.get(str(face.id), ()),
                    kind=str(assignment.get("kind") or "motif"),
                    persistent=True,
                )
                face.metadata["plan_trace_2d.pattern.assignment_id"] = str(assignment.get("group_id") or "")
                restored += 1
        return restored

    def _apply_holes_to_face(
        self,
        face: Any,
        holes: tuple[tuple[tuple[float, float], ...], ...],
        *,
        kind: str,
        persistent: bool,
    ) -> None:
        """Attach derived motif holes without taking ownership of native holes."""

        motif_holes = tuple(
            tuple((float(x), float(y)) for x, y in hole)
            for hole in holes
            if len(hole) >= 3
        )
        native_holes, native_boundary_ids = self._native_holes_for_face(face)
        combined = tuple(native_holes) + tuple(motif_holes)
        combined_boundary_ids = tuple(native_boundary_ids) + tuple(() for _ in motif_holes)

        face.hole_polygons = combined
        face.hole_boundary_entity_ids = combined_boundary_ids
        try:
            signature = face_signature_from_points(tuple(face.polygon_points), hole_polygons=combined)
            outer_signature = face_signature_from_points(tuple(face.polygon_points))
        except Exception:
            signature = str(getattr(face, "id", ""))
            outer_signature = signature
        face.metadata["signature"] = signature
        face.metadata["outer_signature"] = outer_signature
        face.metadata["hole_signatures"] = tuple(face_signature_from_points(hole) for hole in combined)
        face.metadata["hole_count"] = len(combined)
        face.metadata["contains_holes"] = bool(combined)
        face.metadata["plan_trace_2d.pattern.direct_holes"] = bool(motif_holes)
        face.metadata["plan_trace_2d.pattern.native_hole_count"] = len(native_holes)
        face.metadata["plan_trace_2d.pattern.opening_count"] = len(motif_holes)
        face.metadata["plan_trace_2d.pattern.keep_form"] = True
        if motif_holes:
            face.metadata["plan_trace_2d.pattern.kind"] = str(kind)
        else:
            face.metadata.pop("plan_trace_2d.pattern.kind", None)
        if persistent and outer_signature:
            if motif_holes:
                self._state.motif_face_holes_by_outer_signature[outer_signature] = motif_holes
                self._state.motif_face_hole_kinds[outer_signature] = str(kind)
            else:
                self._state.motif_face_holes_by_outer_signature.pop(outer_signature, None)
                self._state.motif_face_hole_kinds.pop(outer_signature, None)

    def restore_persistent_face_holes_after_compile(self) -> int:
        """Reattach Pattern geometry after topology regeneration.

        v177 prefers the compact parametric assignments.  The explicit hole map
        remains only as an in-session derived cache / legacy recovery path.
        """

        restored = self._restore_parametric_assignments_after_compile()
        if restored:
            return restored
        hole_map = dict(getattr(self._state, "motif_face_holes_by_outer_signature", {}) or {})
        if not hole_map:
            return 0
        kind_map = dict(getattr(self._state, "motif_face_hole_kinds", {}) or {})
        for face in tuple(self._state.sketch.faces.values()):
            outer_sig = self._outer_signature(face)
            holes = hole_map.get(outer_sig)
            if not holes:
                continue
            self._apply_holes_to_face(
                face,
                tuple(holes),
                kind=kind_map.get(outer_sig, "motif"),
                persistent=False,
            )
            restored += 1
        return restored

    def _sync_face_actor(self, ctx: Any, face_id: str, *, render: bool = True) -> None:
        self._sync_face_actors(ctx, (str(face_id),), render=render)

    def _sync_face_actors(self, ctx: Any, face_ids: Iterable[str], *, render: bool = True) -> None:
        ordered_ids = tuple(
            dict.fromkeys(
                str(face_id)
                for face_id in face_ids
                if str(face_id) in self._state.sketch.faces
            )
        )
        if not ordered_ids:
            return
        try:
            from laserprog_studio.tool_api import plan2d
            registry = ctx.projected_drawing.for_tool(self.id)
            changed: list[str] = []
            with registry.batch():
                for face_id in ordered_ids:
                    face = self._state.sketch.faces.get(str(face_id))
                    if face is None:
                        continue
                    polygon = tuple(
                        self.services.coordinates.sketch_xy_to_display_world(point)
                        for point in face.polygon_points
                    )
                    holes = tuple(
                        tuple(self.services.coordinates.sketch_xy_to_display_world(point) for point in hole)
                        for hole in tuple(getattr(face, "hole_polygons", ()) or ())
                        if len(hole) >= 3
                    )
                    actor_id = self.services.sketch_sync._face_actor_id(str(face_id))
                    plan2d.register_plan_face(
                        ctx,
                        owner_tool=self.id,
                        face_id=actor_id,
                        polygon_world_points=polygon,
                        hole_world_polygons=holes,
                        selectable=True,
                        sketch_face_id=str(face_id),
                    )
                    changed.append(actor_id)
                if changed:
                    plan2d.sync_plan_actor_visuals(
                        ctx,
                        owner_tool=self.id,
                        changed_actor_ids=tuple(changed),
                        position_only=False,
                        render=False,
                    )
            try:
                first = True
                for actor_id in changed:
                    ctx.selection.select(actor_id, replace=first)
                    first = False
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.services.overlay._sync_reports(ctx)
            self.services.rendering._render(ctx, sync_overlays=True, render=render)
        except Exception:
            pass

    def _clip_candidates(
        self,
        candidates: Iterable[tuple[tuple[float, float], ...]],
        *,
        footprint: Any | None,
        outer: tuple[tuple[float, float], ...],
        clip_mode: bool,
        max_segments: int | None = None,
    ) -> list[tuple[tuple[float, float], ...]]:
        """Validate motif cells against a face without intersecting every cell.

        At a zero edge margin every motif kind enters ``clip_mode``.  The old
        implementation then called ``footprint.intersection(candidate)`` for
        *all* cells, including the thousands that were wholly inside or wholly
        outside the face.  Rounded Plan Tracer faces can contain several
        thousand boundary vertices, so those unnecessary GEOS operations could
        block the UI for seconds or appear to freeze it.

        A prepared footprint provides fast spatial predicates.  Interior cells
        are accepted directly, exterior cells are discarded, and the expensive
        intersection is reserved for the small set that actually crosses the
        boundary.  This preserves the exact zero-margin geometry while keeping
        interaction time proportional to the boundary cells rather than the
        complete pattern.
        """

        valid: list[tuple[tuple[float, float], ...]] = []
        segment_total = 0

        def _append_if_budget(ring: tuple[tuple[float, float], ...]) -> bool:
            nonlocal segment_total
            safe = _safe_closed_ring(ring)
            if len(safe) < 3:
                return True
            seg_count = len(safe)
            if max_segments is not None and segment_total + seg_count > int(max_segments):
                self._state.motif_segment_limit_hit = True
                return False
            valid.append(_ensure_ccw(safe))
            segment_total += seg_count
            return True

        from_shapely = footprint is not None
        prepared_footprint = None
        footprint_bounds: tuple[float, float, float, float] | None = None
        if from_shapely:
            try:
                from shapely.geometry import Polygon
                from shapely.prepared import prep

                prepared_footprint = prep(footprint)
                raw_bounds = tuple(float(value) for value in footprint.bounds)
                if len(raw_bounds) == 4:
                    footprint_bounds = raw_bounds
            except Exception:
                from_shapely = False
                prepared_footprint = None
                footprint_bounds = None

        for poly in candidates:
            if len(poly) < 3:
                continue
            if from_shapely:
                try:
                    # Reject disjoint candidate bounding boxes before allocating
                    # a Shapely polygon.  Rotated patterns intentionally generate
                    # a padded working grid, so this cheap test removes many cells.
                    if footprint_bounds is not None:
                        poly_bounds = _bounds(poly)
                        if poly_bounds is None:
                            continue
                        if (
                            poly_bounds[2] < footprint_bounds[0]
                            or poly_bounds[0] > footprint_bounds[2]
                            or poly_bounds[3] < footprint_bounds[1]
                            or poly_bounds[1] > footprint_bounds[3]
                        ):
                            continue

                    candidate = Polygon(poly)
                    if not candidate.is_valid:
                        candidate = candidate.buffer(0)
                    if candidate.is_empty or candidate.area <= 1.0e-9:
                        continue

                    covers = (
                        bool(prepared_footprint.covers(candidate))
                        if prepared_footprint is not None
                        else bool(footprint.covers(candidate))
                    )
                    if covers:
                        # Builders normally return a single valid polygon.  Use
                        # its original compact ring and avoid a GEOS intersection.
                        ring = _safe_closed_ring(tuple(poly))
                        if len(ring) >= 3 and not _append_if_budget(ring):
                            return valid
                        continue

                    if not clip_mode:
                        continue

                    intersects = (
                        bool(prepared_footprint.intersects(candidate))
                        if prepared_footprint is not None
                        else bool(footprint.intersects(candidate))
                    )
                    if not intersects:
                        continue

                    # Only boundary-crossing cells reach the expensive operation.
                    clipped = footprint.intersection(candidate)
                    if clipped.is_empty:
                        continue
                    for piece in self._explode_polygons(clipped):
                        ring = _safe_closed_ring(piece)
                        if len(ring) >= 3 and not _append_if_budget(ring):
                            return valid
                    continue
                except Exception:
                    pass
            # Fallback without shapely: keep candidates whose vertices are inside
            if all(_point_in_poly(point, outer) for point in poly):
                ring = _safe_closed_ring(tuple(poly))
                if len(ring) >= 3:
                    if not _append_if_budget(ring):
                        return valid
        return valid

    @staticmethod
    def _explode_polygons(geometry: Any) -> Iterable[tuple[tuple[float, float], ...]]:
        try:
            from shapely.geometry import MultiPolygon, Polygon
        except Exception:
            return ()
        if isinstance(geometry, Polygon):
            if geometry.is_empty:
                return ()
            return (tuple((float(x), float(y)) for x, y in geometry.exterior.coords[:-1]),)
        if isinstance(geometry, MultiPolygon):
            return tuple(
                tuple((float(x), float(y)) for x, y in part.exterior.coords[:-1])
                for part in geometry.geoms
                if not part.is_empty
            )
        # GeometryCollection or other: dig polygons out
        polys: list[tuple[tuple[float, float], ...]] = []
        for sub in getattr(geometry, "geoms", ()) or ():
            if isinstance(sub, Polygon) and not sub.is_empty:
                polys.append(tuple((float(x), float(y)) for x, y in sub.exterior.coords[:-1]))
        return tuple(polys)

    def _refresh_pattern_face_id(self) -> str | None:
        faces = tuple(self._state.sketch.faces.values())
        if not faces:
            self._state.pattern_face_id = None
            self._state.pattern_face_ids = ()
            return None

        def _score(face: Any) -> tuple[int, float]:
            holes = len(tuple(getattr(face, "hole_polygons", ()) or ()))
            area = abs(_ring_area(tuple(getattr(face, "polygon_points", ()) or ())))
            return (holes, area)

        best = max(faces, key=_score)
        self._state.pattern_face_id = str(getattr(best, "id", "") or "") or None
        self._state.pattern_face_ids = (self._state.pattern_face_id,) if self._state.pattern_face_id else ()
        return self._state.pattern_face_id

    def _suppress_pattern_inner_faces(self) -> int:
        sketch = self._state.sketch
        pattern_lines = {
            line_id
            for line_id, line in sketch.lines.items()
            if line.metadata.get(_PATTERN_TAG)
        }
        if not pattern_lines:
            return 0
        removed = 0
        for face_id, face in list(sketch.faces.items()):
            boundary = {
                str(value)
                for value in tuple(getattr(face, "boundary_entity_ids", ()) or ())
            }
            if (
                boundary
                and boundary.issubset(pattern_lines)
                and not tuple(getattr(face, "hole_polygons", ()) or ())
            ):
                sketch.delete_face_only(str(face_id), compile_after=False)
                removed += 1
        return removed

    def _shapely_face_polygon(
        self,
        outer: tuple[tuple[float, float], ...],
        holes: tuple[tuple[tuple[float, float], ...], ...],
        *,
        inset: float = 0.0,
    ) -> Any | None:
        try:
            from shapely.geometry import Polygon

            poly = Polygon(outer, holes=list(holes))
            if not poly.is_valid:
                poly = poly.buffer(0)
            if float(inset) > 1.0e-9 and not getattr(poly, "is_empty", False):
                inset_poly = poly.buffer(-float(inset), join_style=2)
                if not getattr(inset_poly, "is_empty", False):
                    poly = inset_poly
            if not poly.is_valid:
                poly = poly.buffer(0)
            if getattr(poly, "is_empty", False):
                return None
            return poly
        except Exception:
            return None

    # ------------------------------------------------------------------ segment budget / estimation

    @staticmethod
    def _ceil_div_span(span: float, pitch: float) -> int:
        if span <= 0.0 or pitch <= 0.0:
            return 0
        return max(0, int(math.ceil(span / pitch)))

    def estimate_candidate_segments(
        self,
        *,
        kind: str,
        bbox: tuple[float, float, float, float],
        cell_size: float,
        wall: float,
        margin: float,
        angle: float = 0.0,
        aspect: float = 1.0,
    ) -> int:
        """Cheap upper-bound-ish estimate used before building a motif.

        This intentionally runs before the candidate builders.  It prevents a
        transient edit such as typing ``1`` before ``10`` from allocating tens
        of thousands of polygons just to discover later that the preview is too
        dense.  The exact clipped count can only be known after Shapely, so this
        is a conservative screen/solver budget guard rather than a geometric
        truth.
        """

        min_x, min_y, max_x, max_y = bbox
        width = max(0.0, float(max_x) - float(min_x) - 2.0 * max(0.0, float(margin)))
        height = max(0.0, float(max_y) - float(min_y) - 2.0 * max(0.0, float(margin)))
        pitch = max(float(cell_size), 0.001)
        if width <= 0.0 or height <= 0.0:
            return 0
        angle_rad = math.radians(float(angle))
        if abs(math.sin(angle_rad)) > 1.0e-6:
            diag = math.hypot(width, height) + 2.0 * pitch
            width = height = diag
        k = str(kind).lower()

        def grid_count(px: float = pitch, py: float = pitch, pad: int = 2) -> int:
            return (self._ceil_div_span(width, max(px, 0.001)) + pad) * (self._ceil_div_span(height, max(py, 0.001)) + pad)

        if k == "honeycomb":
            dx = math.sqrt(3.0) * pitch * 0.5
            dy = 0.75 * pitch
            return grid_count(2.0 * dx, dy, pad=3) * 6
        if k == "organic":
            dx = math.sqrt(3.0) * pitch * 0.5
            dy = 0.75 * pitch
            return grid_count(2.0 * dx, dy, pad=3) * 8
        if k == "circle":
            radius = max((pitch - float(wall)) * 0.5, 0.15)
            segments = max(12, int(min(64, math.ceil(radius * 3.0))))
            return grid_count() * segments
        if k in {"square", "diamond"}:
            return grid_count() * 4
        if k == "triangle":
            side = max(pitch - float(wall), 0.3)
            row_pitch = side * math.sqrt(3.0) * 0.5 + max(float(wall), 0.5)
            col_pitch = side * 0.5
            return grid_count(col_pitch, row_pitch, pad=3) * 3
        if k == "brick":
            brick_h = max(pitch - float(wall), 0.2)
            brick_w = max(brick_h * max(float(aspect), 0.5) * 2.0, brick_h)
            return grid_count(brick_w + float(wall), brick_h + float(wall), pad=3) * 4
        if k == "cross":
            return grid_count() * 12
        if k == "star":
            return grid_count() * 10
        if k == "rings":
            radius_max = math.hypot(width, height) * 0.5
            ring_count = self._ceil_div_span(radius_max + pitch, pitch)
            return ring_count * (96 * 2 + 2)
        if k == "grid":
            return (self._ceil_div_span(height, pitch) + 2) * 4
        if k == "wave":
            wavelength = max(pitch * 3.0, 6.0)
            samples = max(48, int(math.ceil(width / max(wavelength / 12.0, 0.5))))
            return (self._ceil_div_span(height, pitch) + 2) * (2 * (samples + 1))
        if k == "hinge_straight":
            row_pitch = max(pitch, 1.0)
            slot_length = max(row_pitch * max(float(aspect), 1.5), row_pitch * 1.5)
            count = grid_count(slot_length + max(row_pitch * 0.5, 1.0), row_pitch, pad=3)
            return count * 4
        if k == "hinge_lattice":
            row_pitch = max(pitch, 1.0)
            full_slot = max(row_pitch * max(float(aspect), 2.5), row_pitch * 2.5)
            count = grid_count(full_slot * 0.5 + max(row_pitch * 0.4, 0.8), row_pitch, pad=4)
            return count * 4
        if k == "hinge_wave":
            row_pitch = max(pitch, 1.0)
            slot_length = max(row_pitch * max(float(aspect), 2.0), row_pitch * 2.0)
            samples = max(16, int(math.ceil(slot_length / 1.5)))
            count = grid_count(slot_length + max(row_pitch * 0.5, 1.0), row_pitch, pad=3)
            return count * (2 * (samples + 1))
        return grid_count() * 4

    # ------------------------------------------------------------------ dispatch

    def _candidate_polygons(
        self,
        *,
        kind: str,
        bbox: tuple[float, float, float, float],
        cell_size: float,
        wall: float,
        margin: float,
        angle: float,
        aspect: float,
        seed: int,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        allow_edge_clipping: bool = False,
    ) -> tuple[tuple[tuple[float, float], ...], ...]:
        min_x, min_y, max_x, max_y = bbox
        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5
        min_x += margin
        min_y += margin
        max_x -= margin
        max_y -= margin
        if bool(allow_edge_clipping) and float(margin) <= 1.0e-9:
            pad = max(float(cell_size), abs(float(wall)), 0.5) * 0.5
            min_x -= pad
            min_y -= pad
            max_x += pad
            max_y += pad
        if max_x <= min_x or max_y <= min_y:
            return ()

        angle_rad = math.radians(angle)
        if abs(math.sin(angle_rad)) > 1.0e-6:
            # Expand the working bbox to a circumscribed square so rotated cells
            # at the corners are still generated; clipping later trims overflow.
            half_diag = math.hypot(max_x - min_x, max_y - min_y) * 0.5 + cell_size
            work_min_x, work_max_x = cx - half_diag, cx + half_diag
            work_min_y, work_max_y = cy - half_diag, cy + half_diag
        else:
            work_min_x, work_min_y, work_max_x, work_max_y = min_x, min_y, max_x, max_y

        builder = _PATTERN_BUILDERS.get(str(kind).lower(), _PATTERN_BUILDERS["square"])
        raw = builder(
            work_min_x,
            work_min_y,
            work_max_x,
            work_max_y,
            cell_size=cell_size,
            wall=wall,
            aspect=aspect,
            seed=seed,
        )
        if not raw:
            return ()
        rotated = _rotate(raw, cx=cx, cy=cy, angle_rad=angle_rad)
        if abs(offset_x) > 1.0e-9 or abs(offset_y) > 1.0e-9:
            return tuple(
                tuple((x + offset_x, y + offset_y) for x, y in poly)
                for poly in rotated
            )
        return rotated

    # ------------------------------------------------------------------ writeback


    def _projected_registry(self, ctx: Any):
        projected = getattr(ctx, "projected_drawing", None)
        if projected is None or not hasattr(projected, "for_tool"):
            return None
        try:
            return projected.for_tool(self.id)
        except Exception:
            return None

    def _clear_preview_linework(self, ctx: Any) -> None:
        registry = self._projected_registry(ctx)
        if registry is None:
            return
        try:
            stale = tuple(
                str(getattr(item, "id", ""))
                for item in registry.items()
                if str(getattr(item, "id", "")).startswith(_PATTERN_PREVIEW_PREFIX)
            )
            if stale:
                registry.remove_many(stale, render=False)
        except Exception:
            pass

    def _sync_preview_linework(self, ctx: Any) -> None:
        """Display motif preview linework through Projected Drawing 2D only."""

        registry = self._projected_registry(ctx)
        if registry is None:
            return
        try:
            segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
            item_ids: list[str] = []
            for line_id, line in tuple(self._state.sketch.lines.items()):
                if not line.metadata.get(_PATTERN_TAG):
                    continue
                start = self._state.sketch.points.get(line.start_point_id)
                end = self._state.sketch.points.get(line.end_point_id)
                if start is None or end is None:
                    continue
                p1 = tuple(float(v) for v in self.services.coordinates.sketch_xy_to_display_world(start.position))
                p2 = tuple(float(v) for v in self.services.coordinates.sketch_xy_to_display_world(end.position))
                if len(p1) != 3 or len(p2) != 3:
                    continue
                segments.append((p1, p2))
                item_ids.append(f"{_PATTERN_PREVIEW_PREFIX}{line_id}")
            with registry.batch():
                self._clear_preview_linework(ctx)
                if segments:
                    registry.add(
                        draw2d.segment_batch(
                            _PATTERN_PREVIEW_BATCH_ID,
                            tuple(segments),
                            item_ids=tuple(item_ids),
                            color="#7FC8FF",
                            width_px=1.5,
                            opacity=0.82,
                            layer=12,
                        ),
                        replace=True,
                        render=False,
                    )
        except Exception:
            pass
    def _add_closed_polyline(
        self,
        points: tuple[tuple[float, float], ...],
        *,
        kind: str,
    ) -> tuple[str, ...]:
        sketch = self._state.sketch
        ids: list[str] = []
        for point in points:
            item = sketch.add_point(point)
            item.metadata[_PATTERN_POINT_TAG] = True
            item.metadata[_PATTERN_TAG] = kind
            ids.append(item.id)
        line_ids: list[str] = []
        for index, point_id in enumerate(ids):
            nxt = ids[(index + 1) % len(ids)]
            line = sketch.add_line(point_id, nxt)
            line.metadata[_PATTERN_TAG] = kind
            line_ids.append(line.id)
        return tuple(line_ids)

    def _remove_previous_pattern_entities(self) -> bool:
        sketch = self._state.sketch
        pattern_points = {
            point_id
            for point_id, point in list(sketch.points.items())
            if bool(point.metadata.get(_PATTERN_POINT_TAG))
        }
        pattern_lines = {
            line_id
            for line_id, line in list(sketch.lines.items())
            if line.metadata.get(_PATTERN_TAG)
        }
        for line_id in pattern_lines:
            sketch.lines.pop(line_id, None)
        for point_id in pattern_points:
            sketch.points.pop(point_id, None)
        if pattern_points or pattern_lines:
            sketch.remove_dimensions_referencing(pattern_points | pattern_lines)
            sketch.faces.clear()
            sketch.polylines.clear()
            sketch.suppressed_face_signatures.clear()
            return True
        return False


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


PolyList = tuple[tuple[tuple[float, float], ...], ...]
Builder = Callable[..., PolyList]


def _build_square(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    out: list[tuple[tuple[float, float], ...]] = []
    side = max(cell_size - wall, 0.2)
    half = side * 0.5
    y = min_y + cell_size * 0.5
    while y <= max_y - cell_size * 0.5 + 1.0e-9:
        x = min_x + cell_size * 0.5
        while x <= max_x - cell_size * 0.5 + 1.0e-9:
            out.append(
                (
                    (x - half, y - half),
                    (x + half, y - half),
                    (x + half, y + half),
                    (x - half, y + half),
                )
            )
            x += cell_size
        y += cell_size
    return tuple(out)


def _build_honeycomb(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    out: list[tuple[tuple[float, float], ...]] = []
    # cell_size is the centre-to-centre pitch.  Hexagon radius keeps a wall of
    # ``wall`` between adjacent cells (centre distance = pitch).
    radius = max((cell_size - wall) * 0.5, 0.1)
    dx = math.sqrt(3.0) * cell_size * 0.5
    dy = 0.75 * cell_size
    row = 0
    y = min_y + cell_size * 0.5
    while y <= max_y - cell_size * 0.5 + 1.0e-9:
        # Adjacent rows are shifted by ``dx`` (half the centre-to-centre
        # horizontal pitch ``2*dx``) so the hexagons interlock.
        x = min_x + (dx if row % 2 else 0.0) + cell_size * 0.5
        while x <= max_x - cell_size * 0.5 + 1.0e-9:
            pts = []
            for k in range(6):
                angle = math.radians(30.0 + 60.0 * k)
                pts.append((x + radius * math.cos(angle), y + radius * math.sin(angle)))
            out.append(tuple(pts))
            x += 2.0 * dx
        row += 1
        y += dy
    return tuple(out)


def _build_circle(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    out: list[tuple[tuple[float, float], ...]] = []
    radius = max((cell_size - wall) * 0.5, 0.15)
    # Vertex count scales gently with radius so small circles stay light.
    segments = max(12, int(min(64, math.ceil(radius * 3.0))))
    y = min_y + cell_size * 0.5
    while y <= max_y - cell_size * 0.5 + 1.0e-9:
        x = min_x + cell_size * 0.5
        while x <= max_x - cell_size * 0.5 + 1.0e-9:
            pts = []
            for k in range(segments):
                a = 2.0 * math.pi * k / segments
                pts.append((x + radius * math.cos(a), y + radius * math.sin(a)))
            out.append(tuple(pts))
            x += cell_size
        y += cell_size
    return tuple(out)


def _build_diamond(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    out: list[tuple[tuple[float, float], ...]] = []
    side = max(cell_size - wall, 0.2)
    half_w = side * 0.5
    half_h = side * 0.5 * max(aspect, 0.2)
    y = min_y + cell_size * 0.5
    while y <= max_y - cell_size * 0.5 + 1.0e-9:
        x = min_x + cell_size * 0.5
        while x <= max_x - cell_size * 0.5 + 1.0e-9:
            out.append(
                (
                    (x, y - half_h),
                    (x + half_w, y),
                    (x, y + half_h),
                    (x - half_w, y),
                )
            )
            x += cell_size
        y += cell_size
    return tuple(out)


def _build_triangle(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    """Isolated triangular openings on a staggered grid.

    The previous dense up/down packing intentionally shared vertices and edges.
    That is fine for decorative linework, but invalid for Plan Tracer face holes:
    adjacent holes that touch make the host face non-manifold.  This builder
    keeps a real wall around every triangle, so each output ring is a clean,
    independent closed hole.
    """

    out: list[tuple[tuple[float, float], ...]] = []
    pitch = max(cell_size, 0.6)
    clearance = max(wall, 0.05)
    side = max(pitch - clearance, 0.3)
    height = side * math.sqrt(3.0) * 0.5
    row_pitch = height + clearance
    col_pitch = side + clearance
    row = 0
    y = min_y + height * 0.5 + clearance * 0.5
    while y <= max_y - height * 0.5 - clearance * 0.5 + 1.0e-9:
        x = min_x + side * 0.5 + clearance * 0.5 + (0.5 * col_pitch if row % 2 else 0.0)
        pointing_up = row % 2 == 0
        while x <= max_x - side * 0.5 - clearance * 0.5 + 1.0e-9:
            if pointing_up:
                ring = (
                    (x - side * 0.5, y - height * 0.5),
                    (x + side * 0.5, y - height * 0.5),
                    (x, y + height * 0.5),
                )
            else:
                ring = (
                    (x - side * 0.5, y + height * 0.5),
                    (x, y - height * 0.5),
                    (x + side * 0.5, y + height * 0.5),
                )
            safe = _safe_closed_ring(ring)
            if safe:
                out.append(safe)
            x += col_pitch
        row += 1
        y += row_pitch
    return tuple(out)

def _build_brick(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    out: list[tuple[tuple[float, float], ...]] = []
    pitch = max(cell_size, 0.5)
    gap = max(wall, 0.05)
    brick_h = max(pitch - gap, 0.2)
    brick_w = max(brick_h * max(aspect, 0.5) * 2.0, brick_h)
    row_pitch = brick_h + gap
    col_pitch = brick_w + gap
    row = 0
    y = min_y + gap * 0.5 + brick_h * 0.5
    while y <= max_y - gap * 0.5 - brick_h * 0.5 + 1.0e-9:
        offset = 0.5 * col_pitch if row % 2 else 0.0
        x = min_x + gap * 0.5 + brick_w * 0.5 + offset
        while x <= max_x - gap * 0.5 - brick_w * 0.5 + 1.0e-9:
            ring = (
                (x - brick_w * 0.5, y - brick_h * 0.5),
                (x + brick_w * 0.5, y - brick_h * 0.5),
                (x + brick_w * 0.5, y + brick_h * 0.5),
                (x - brick_w * 0.5, y + brick_h * 0.5),
            )
            safe = _safe_closed_ring(ring)
            if safe:
                out.append(safe)
            x += col_pitch
        row += 1
        y += row_pitch
    return tuple(out)

def _build_cross(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    out: list[tuple[tuple[float, float], ...]] = []
    arm = max(cell_size - wall, 0.3)
    thick = max(arm / max(2.5, 4.0 / max(aspect, 0.4)), 0.1)
    half_arm = arm * 0.5
    half_thick = thick * 0.5
    y = min_y + cell_size * 0.5
    while y <= max_y - cell_size * 0.5 + 1.0e-9:
        x = min_x + cell_size * 0.5
        while x <= max_x - cell_size * 0.5 + 1.0e-9:
            # plus sign as a 12-vertex polygon
            out.append(
                (
                    (x - half_thick, y - half_arm),
                    (x + half_thick, y - half_arm),
                    (x + half_thick, y - half_thick),
                    (x + half_arm, y - half_thick),
                    (x + half_arm, y + half_thick),
                    (x + half_thick, y + half_thick),
                    (x + half_thick, y + half_arm),
                    (x - half_thick, y + half_arm),
                    (x - half_thick, y + half_thick),
                    (x - half_arm, y + half_thick),
                    (x - half_arm, y - half_thick),
                    (x - half_thick, y - half_thick),
                )
            )
            x += cell_size
        y += cell_size
    return tuple(out)


def _build_star(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    out: list[tuple[tuple[float, float], ...]] = []
    outer_r = max((cell_size - wall) * 0.5, 0.2)
    inner_r = outer_r * max(min(aspect, 0.9), 0.2)
    points = 5
    y = min_y + cell_size * 0.5
    while y <= max_y - cell_size * 0.5 + 1.0e-9:
        x = min_x + cell_size * 0.5
        while x <= max_x - cell_size * 0.5 + 1.0e-9:
            pts = []
            for k in range(points * 2):
                r = outer_r if k % 2 == 0 else inner_r
                a = -math.pi * 0.5 + math.pi * k / points
                pts.append((x + r * math.cos(a), y + r * math.sin(a)))
            out.append(tuple(pts))
            x += cell_size
        y += cell_size
    return tuple(out)


def _build_rings(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    """Concentric closed bands represented as valid single-boundary slots.

    Plan Tracer currently stores holes as one exterior ring per opening.  A true
    donut with an interior island cannot be represented directly there, so each
    annulus is emitted as a very thin C-shaped band with one radial seam.  The
    seam is deliberately stable and non-self-intersecting, which avoids the old
    malformed vertices near the centre of the rings.
    """

    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5
    radius_max = math.hypot(max_x - min_x, max_y - min_y) * 0.5
    pitch = max(cell_size, 0.5)
    thickness = max(min(pitch - max(wall, 0.05), pitch * 0.65), 0.15)
    segments = 96
    out: list[tuple[tuple[float, float], ...]] = []
    r = max(pitch * 0.5, thickness * 1.25)
    while r <= radius_max + pitch:
        outer_radius = r + thickness * 0.5
        inner_radius = max(r - thickness * 0.5, 0.05)
        # Leave a tiny angular seam so the band is a simple polygon, not a
        # polygon-with-hole.  The seam is narrower than the line tolerance and
        # visually reads as a closed ring at normal zoom levels.
        seam_angle = max(0.015, min(0.08, thickness / max(outer_radius, 1.0) * 0.35))
        start_a = seam_angle * 0.5
        end_a = 2.0 * math.pi - seam_angle * 0.5
        outer = [
            (cx + outer_radius * math.cos(start_a + (end_a - start_a) * k / segments),
             cy + outer_radius * math.sin(start_a + (end_a - start_a) * k / segments))
            for k in range(segments + 1)
        ]
        inner = [
            (cx + inner_radius * math.cos(end_a - (end_a - start_a) * k / segments),
             cy + inner_radius * math.sin(end_a - (end_a - start_a) * k / segments))
            for k in range(segments + 1)
        ]
        safe = _safe_closed_ring(tuple(outer + inner))
        if safe:
            out.append(safe)
        r += pitch
    return tuple(out)

def _build_grid_slots(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    out: list[tuple[tuple[float, float], ...]] = []
    pitch = max(cell_size, 0.5)
    slot_h = max(min(pitch - wall, pitch * 0.85), 0.2)
    half = slot_h * 0.5
    y = min_y + pitch * 0.5
    while y <= max_y - pitch * 0.5 + 1.0e-9:
        out.append(
            (
                (min_x, y - half),
                (max_x, y - half),
                (max_x, y + half),
                (min_x, y + half),
            )
        )
        y += pitch
    return tuple(out)


def _build_wave(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    """Stack of sinusoidal slots running across the face."""

    out: list[tuple[tuple[float, float], ...]] = []
    pitch = max(cell_size, 0.5)
    slot_h = max(min(pitch - wall, pitch * 0.55), 0.2)
    free_gap = max(pitch - slot_h - max(wall, 0.05), 0.0)
    amplitude = min(max(slot_h * max(aspect, 0.0), 0.0), max(free_gap * 0.45, 0.0))
    wavelength = max(pitch * 3.0, 6.0)
    half = slot_h * 0.5
    samples = max(48, int(math.ceil((max_x - min_x) / max(wavelength / 12.0, 0.5))))
    y = min_y + pitch * 0.5
    while y <= max_y - pitch * 0.5 + 1.0e-9:
        top = []
        bottom = []
        for k in range(samples + 1):
            t = k / samples
            x = min_x + (max_x - min_x) * t
            offset = amplitude * math.sin(2.0 * math.pi * x / wavelength)
            top.append((x, y + half + offset))
            bottom.append((x, y - half + offset))
        ring = top + list(reversed(bottom))
        out.append(tuple(ring))
        y += pitch
    return tuple(out)


def _build_organic(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    """Jittered honeycomb cells – an organic, voronoi-like look.

    True Voronoi would require ``scipy``; this lighter approach takes the
    honeycomb lattice and perturbs each vertex per cell with a deterministic
    pseudo-random offset.  The resulting shapes stay convex and well-formed
    while losing the regularity of the strict hex grid.
    """

    rng = random.Random(seed)
    radius = max((cell_size - wall) * 0.5, 0.1)
    jitter = max(min(aspect, 1.5), 0.0) * radius * 0.35
    dx = math.sqrt(3.0) * cell_size * 0.5
    dy = 0.75 * cell_size
    out: list[tuple[tuple[float, float], ...]] = []
    row = 0
    y = min_y + cell_size * 0.5
    while y <= max_y - cell_size * 0.5 + 1.0e-9:
        x = min_x + (dx if row % 2 else 0.0) + cell_size * 0.5
        while x <= max_x - cell_size * 0.5 + 1.0e-9:
            n_vertices = rng.randint(5, 8)
            pts: list[tuple[float, float]] = []
            base_angle = rng.uniform(0.0, math.pi)
            for k in range(n_vertices):
                a = base_angle + 2.0 * math.pi * k / n_vertices
                r = radius + rng.uniform(-jitter, jitter)
                pts.append((x + r * math.cos(a), y + r * math.sin(a)))
            out.append(tuple(pts))
            x += 2.0 * dx
        row += 1
        y += dy
    return tuple(out)


# ----- Living hinge variants -----


def _build_hinge_straight(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    """Classic offset straight-cut living hinge.

    Each row is a band of slots; consecutive rows are offset by half a slot to
    create the characteristic stretchable lattice.  ``cell_size`` controls row
    pitch, ``wall`` is the kerf width, ``aspect`` is slot length / pitch.
    """

    out: list[tuple[tuple[float, float], ...]] = []
    row_pitch = max(cell_size, 1.0)
    kerf = max(wall, 0.15)
    half_kerf = kerf * 0.5
    slot_length = max(row_pitch * max(aspect, 1.5), row_pitch * 1.5)
    gap = max(row_pitch * 0.5, 1.0)  # interruption between slots in a row
    pitch_x = slot_length + gap

    row = 0
    y = min_y + row_pitch * 0.5
    while y <= max_y - row_pitch * 0.5 + 1.0e-9:
        offset = pitch_x * 0.5 if row % 2 else 0.0
        # Push the first slot start before min_x so half-slots can be clipped
        # against the face boundary.  The intersection step trims the overflow.
        x_start = min_x - slot_length * 0.5 + offset
        while x_start <= max_x + 1.0e-9:
            x_end = x_start + slot_length
            out.append(
                (
                    (x_start, y - half_kerf),
                    (x_end, y - half_kerf),
                    (x_end, y + half_kerf),
                    (x_start, y + half_kerf),
                )
            )
            x_start += pitch_x
        row += 1
        y += row_pitch
    return tuple(out)


def _build_hinge_lattice(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    """Interlocking lattice hinge.

    Three staggered rows form a denser pattern: long centre slot flanked by two
    half-length slots on the neighbour rows.  Produces a finer, more compliant
    hinge than the straight variant for the same pitch.
    """

    out: list[tuple[tuple[float, float], ...]] = []
    row_pitch = max(cell_size, 1.0)
    kerf = max(wall, 0.15)
    half_kerf = kerf * 0.5
    full_slot = max(row_pitch * max(aspect, 2.5), row_pitch * 2.5)
    half_slot = full_slot * 0.5
    gap = max(row_pitch * 0.4, 0.8)

    row = 0
    y = min_y + row_pitch * 0.5
    while y <= max_y - row_pitch * 0.5 + 1.0e-9:
        is_short_row = row % 2 == 1
        if is_short_row:
            slot_length = half_slot
            pitch_x = slot_length + gap
            # offset short-row slots so they nest between long-row slots
            x_start = min_x - slot_length * 0.5
        else:
            slot_length = full_slot
            pitch_x = slot_length + gap
            x_start = min_x - slot_length * 0.5 + (pitch_x * 0.5 if row % 4 == 2 else 0.0)
        while x_start <= max_x + 1.0e-9:
            x_end = x_start + slot_length
            out.append(
                (
                    (x_start, y - half_kerf),
                    (x_end, y - half_kerf),
                    (x_end, y + half_kerf),
                    (x_start, y + half_kerf),
                )
            )
            x_start += pitch_x
        row += 1
        y += row_pitch
    return tuple(out)


def _build_hinge_wave(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    cell_size: float,
    wall: float,
    aspect: float,
    seed: int,
) -> PolyList:
    """Living hinge with sinusoidal slots.

    Sinusoidal cuts distribute stress over the slot length better than straight
    cuts and bend more smoothly.  ``aspect`` controls the slot length relative
    to pitch; the wave amplitude is locked to a third of the pitch to keep the
    pattern continuous.
    """

    out: list[tuple[tuple[float, float], ...]] = []
    row_pitch = max(cell_size, 1.0)
    kerf = max(wall, 0.15)
    half_kerf = kerf * 0.5
    slot_length = max(row_pitch * max(aspect, 2.0), row_pitch * 2.0)
    gap = max(row_pitch * 0.5, 1.0)
    pitch_x = slot_length + gap
    # Keep the sinusoidal slot inside its row band so neighbouring rows never
    # touch and never create invalid shared-edge holes.
    amplitude = max(row_pitch - kerf, 0.0) * 0.22

    row = 0
    y = min_y + row_pitch * 0.5
    while y <= max_y - row_pitch * 0.5 + 1.0e-9:
        offset = pitch_x * 0.5 if row % 2 else 0.0
        x_start = min_x - slot_length * 0.5 + offset
        while x_start <= max_x + 1.0e-9:
            x_end = x_start + slot_length
            samples = max(16, int(math.ceil(slot_length / 1.5)))
            top: list[tuple[float, float]] = []
            bottom: list[tuple[float, float]] = []
            for k in range(samples + 1):
                t = k / samples
                x = x_start + slot_length * t
                wave = amplitude * math.sin(math.pi * t)
                top.append((x, y + half_kerf + wave))
                bottom.append((x, y - half_kerf + wave))
            ring = top + list(reversed(bottom))
            out.append(tuple(ring))
            x_start += pitch_x
        row += 1
        y += row_pitch
    return tuple(out)


_PATTERN_BUILDERS: dict[str, Builder] = {
    "honeycomb": _build_honeycomb,
    "square": _build_square,
    "circle": _build_circle,
    "diamond": _build_diamond,
    "triangle": _build_triangle,
    "brick": _build_brick,
    "cross": _build_cross,
    "star": _build_star,
    "rings": _build_rings,
    "grid": _build_grid_slots,
    "wave": _build_wave,
    "organic": _build_organic,
    "hinge_straight": _build_hinge_straight,
    "hinge_lattice": _build_hinge_lattice,
    "hinge_wave": _build_hinge_wave,
}


__all__ = ["PATTERN_KIND_CHOICES", "PlanTrace2DPatternService"]
