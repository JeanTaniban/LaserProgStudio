# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Literal

from laserprog_studio.domain.work_model import WorkMesh

VentStyle = Literal["none", "holes", "slots"]


@dataclass(frozen=True, slots=True)
class AcousticDiffuserSettings:
    target_frequency_hz: float = 1000.0
    outer_diameter_mm: float = 160.0
    speaker_diameter_mm: float = 80.0
    skirt_thickness_mm: float = 30.5
    vent_style: VentStyle = "holes"
    vent_count: int = 5
    vent_size_mm: float = 10.0
    quality: int = 64
    color_skirt: str = "#8EA7B8"
    color_diffuser: str = "#D8C08A"


@dataclass(frozen=True, slots=True)
class AcousticDiffuserGeometry:
    r_out_mm: float
    r_in_mm: float
    diffuser_radius_mm: float
    gap_mm: float
    diffuser_height_mm: float
    diffuser_base_z_mm: float
    skirt_height_mm: float
    exit_height_mm: float
    vent_center_z_mm: float
    rim_thickness_mm: float
    shape_power: float


@dataclass(frozen=True, slots=True)
class AcousticDiffuserReport:
    geometry: AcousticDiffuserGeometry
    cavity_volume_cm3: float
    helmholtz_hz: float
    ring_conductance_mm: float
    vent_conductance_mm: float
    total_conductance_mm: float
    ring_fraction: float
    estimated_q: float
    estimated_bandwidth_hz: float
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def concise_text(self) -> str:
        g = self.geometry
        lines = [
            f"Volume: {self.cavity_volume_cm3:.1f} cm³",
            f"Helmholtz: {self.helmholtz_hz:.0f} Hz",
            f"Skirt height: {g.skirt_height_mm:.1f} mm",
            f"Exit gap: {g.exit_height_mm:.2f} mm",
            f"Air split: ring {self.ring_fraction * 100:.0f}% / vents {(1.0 - self.ring_fraction) * 100:.0f}%",
        ]
        if self.estimated_q > 0:
            lines.append(f"Q estimate: {self.estimated_q:.1f} · BW {self.estimated_bandwidth_hz:.0f} Hz")
        if self.warnings:
            lines.extend([f"Warning: {w}" for w in self.warnings[:3]])
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AcousticDiffuserResult:
    meshes: tuple[WorkMesh, ...]
    report: AcousticDiffuserReport


def _clamp(value: float, minimum: float, maximum: float) -> float:
    a = float(minimum)
    b = float(maximum)
    if b < a:
        return b
    return min(max(float(value), a), b)


def _round_key(value: float) -> int:
    return int(round(float(value) * 1_000_000.0))


def _quality_value(settings: AcousticDiffuserSettings) -> int:
    """Return a clamped mesh quality value.

    The acoustic diffuser can become very dense because vent contours, local
    skin tiling and the diffuser revolution all compound.  Keep one quality
    value as the public resolution knob, then derive all tessellation from it.
    """
    return max(24, min(160, int(round(float(settings.quality)))))


def _xy(radius: float, theta_index: int, theta_steps: int, z: float) -> tuple[float, float, float]:
    angle = 2.0 * math.pi * ((int(theta_index) % int(theta_steps)) / float(theta_steps))
    return (float(radius) * math.cos(angle), float(radius) * math.sin(angle), float(z))


def _smoothstep(t: float) -> float:
    t = _clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _bell(u: float, power: float) -> float:
    return (0.5 * (1.0 + math.cos(math.pi * _clamp(u, 0.0, 1.0)))) ** max(0.25, float(power))


def _under_z(u: float, height: float, power: float) -> float:
    return float(height) * (1.0 - _bell(u, power))


def compute_acoustic_diffuser_geometry(settings: AcousticDiffuserSettings) -> AcousticDiffuserGeometry:
    c_mm = 343000.0
    f0 = max(50.0, float(settings.target_frequency_hz))
    d_ext = max(40.0, float(settings.outer_diameter_mm))
    r_out = d_ext / 2.0
    wall = _clamp(float(settings.skirt_thickness_mm), 2.0, max(2.0, r_out - 2.0))
    r_in = max(2.0, r_out - wall)
    gap = _clamp(0.006 * d_ext, 0.50, 1.00)
    diffuser_radius = max(2.0, r_in - gap)

    h_target = 0.90 * c_mm / (4.0 * f0)
    h_cap = 0.55 * d_ext
    height = min(h_target, h_cap)
    b_max = height / 4.0
    b_pref = 0.20 * height
    base_z = _clamp(b_pref, 12.0, b_max)

    requested_exit = 10.0
    c_raw = base_z + height - requested_exit
    skirt_height = _clamp(c_raw, 18.0, 0.95 * d_ext)
    exit_height = max(0.40, base_z + height - skirt_height)
    vent_center_z = _clamp(0.60, 0.10, 0.90) * skirt_height
    rim_t = 3.0
    shape_power = 1.35
    return AcousticDiffuserGeometry(
        r_out_mm=float(r_out),
        r_in_mm=float(r_in),
        diffuser_radius_mm=float(diffuser_radius),
        gap_mm=float(gap),
        diffuser_height_mm=float(height),
        diffuser_base_z_mm=float(base_z),
        skirt_height_mm=float(skirt_height),
        exit_height_mm=float(exit_height),
        vent_center_z_mm=float(vent_center_z),
        rim_thickness_mm=float(rim_t),
        shape_power=float(shape_power),
    )


def _air_height_at_radius(radius: float, geom: AcousticDiffuserGeometry) -> float:
    if radius <= geom.diffuser_radius_mm:
        u = _clamp(radius / max(geom.diffuser_radius_mm, 1e-9), 0.0, 1.0)
        return min(geom.skirt_height_mm, geom.diffuser_base_z_mm + _under_z(u, geom.diffuser_height_mm, geom.shape_power))
    return geom.skirt_height_mm


def _cavity_volume_mm3(geom: AcousticDiffuserGeometry, *, steps: int = 700) -> float:
    rmax = max(geom.r_in_mm, 1e-6)
    dr = rmax / max(1, int(steps))
    vol = 0.0
    for i in range(int(steps)):
        r1 = i * dr
        r2 = (i + 1) * dr
        zm = 0.5 * (_air_height_at_radius(r1, geom) + _air_height_at_radius(r2, geom))
        vol += math.pi * (r2 * r2 - r1 * r1) * zm
    return float(vol)


@dataclass(frozen=True, slots=True)
class _VentOpening:
    center_x_mm: float
    center_z_mm: float
    loop_xz_mm: tuple[tuple[float, float], ...]
    area_mm2: float
    short_side_mm: float
    long_side_mm: float


def _rounded_rectangle_loop(cx: float, cz: float, half_w: float, half_h: float, radius: float, segments_per_corner: int) -> tuple[tuple[float, float], ...]:
    r = max(0.01, min(float(radius), float(half_w), float(half_h)))
    hw = max(r, float(half_w))
    hh = max(r, float(half_h))
    seg = max(4, int(segments_per_corner))
    centers = (
        (cx + hw - r, cz + hh - r, 0.0, 0.5 * math.pi),
        (cx - hw + r, cz + hh - r, 0.5 * math.pi, math.pi),
        (cx - hw + r, cz - hh + r, math.pi, 1.5 * math.pi),
        (cx + hw - r, cz - hh + r, 1.5 * math.pi, 2.0 * math.pi),
    )
    pts: list[tuple[float, float]] = []
    for ccx, ccz, a0, a1 in centers:
        for i in range(seg + 1):
            if pts and i == 0:
                continue
            t = a0 + (a1 - a0) * i / seg
            pts.append((float(ccx + r * math.cos(t)), float(ccz + r * math.sin(t))))
    return tuple(pts)


def _vent_opening_specs(settings: AcousticDiffuserSettings, geom: AcousticDiffuserGeometry) -> tuple[_VentOpening, ...]:
    """Return clean developed-surface openings for the skirt vents.

    The first ACD implementation removed whole cylindrical grid cells.  That made
    round holes look like coarse pixels.  This helper describes each opening as a
    continuous 2D contour on the developed cylinder; the mesh builder then
    triangulates the cylindrical wall around those contours and connects the
    inner/outer contours with proper tunnel faces.
    """
    style = str(settings.vent_style or "none").strip().lower()
    if style == "none":
        return tuple()
    if style not in {"holes", "slots"}:
        style = "holes"
    n = max(1, min(36, int(round(settings.vent_count))))
    size = max(1.0, float(settings.vent_size_mm))
    r_mid = max(1e-6, 0.5 * (geom.r_in_mm + geom.r_out_mm))
    width = 2.0 * math.pi * r_mid
    pitch = width / n
    z0 = _clamp(float(geom.vent_center_z_mm), 1.0, max(1.0, geom.skirt_height_mm - 1.0))
    z_clear = max(0.35, min(z0 - 0.75, geom.skirt_height_mm - z0 - 0.75))
    openings: list[_VentOpening] = []
    for i in range(n):
        cx = pitch * (i + 0.5)
        if style == "slots":
            half_h = min(max(0.50, size * 0.50), z_clear)
            desired_half_w = max(size * 1.20, min(size * 2.50, 0.40 * pitch))
            half_w = min(max(half_h, desired_half_w), max(half_h, 0.43 * pitch))
            corner = min(half_h, half_w) * 0.50
            quality = _quality_value(settings)
            seg = max(4, min(18, int(round(corner * max(0.85, quality / 48.0)))))
            loop = _rounded_rectangle_loop(cx, z0, half_w, half_h, corner, seg)
            area = 4.0 * half_w * half_h - (4.0 - math.pi) * corner * corner
            openings.append(_VentOpening(float(cx), float(z0), loop, float(area), float(2.0 * min(half_w, half_h)), float(2.0 * max(half_w, half_h))))
        else:
            radius = min(max(0.50, size * 0.50), max(0.50, 0.42 * pitch), z_clear)
            # Keep circles clean, but let the global Resolution knob control
            # performance.  Low resolution still gives round-looking holes, while
            # high resolution keeps sub-millimetric chords for final export.
            quality = _quality_value(settings)
            chord_mm = _clamp(96.0 / max(quality, 1), 0.65, 2.80)
            segments = max(12, min(96, int(math.ceil(2.0 * math.pi * radius / chord_mm))))
            segments = min(segments, max(12, int(round(quality * 0.85))))
            loop = tuple(
                (float(cx + radius * math.cos(2.0 * math.pi * k / segments)), float(z0 + radius * math.sin(2.0 * math.pi * k / segments)))
                for k in range(segments)
            )
            openings.append(_VentOpening(float(cx), float(z0), loop, float(math.pi * radius * radius), float(2.0 * radius), float(2.0 * radius)))
    return tuple(openings)


def _vent_conductance_mm(settings: AcousticDiffuserSettings, geom: AcousticDiffuserGeometry) -> tuple[float, int]:
    openings = _vent_opening_specs(settings, geom)
    if not openings:
        return 0.0, 0
    wall = max(0.5, geom.r_out_mm - geom.r_in_mm)
    style = str(settings.vent_style or "none").strip().lower()
    total = 0.0
    for opening in openings:
        if style == "slots":
            length = wall + 0.85 * max(0.5, opening.short_side_mm)
        else:
            length = wall
        total += max(1e-6, opening.area_mm2) / max(length, 1e-6)
    return float(total), int(len(openings))

def analyze_acoustic_diffuser(settings: AcousticDiffuserSettings) -> AcousticDiffuserReport:
    geom = compute_acoustic_diffuser_geometry(settings)
    volume_mm3 = _cavity_volume_mm3(geom)
    h_gap = max(geom.exit_height_mm, 1e-6)
    den_ring = math.log(geom.r_out_mm / max(geom.r_in_mm, 1e-9))
    ring_g = (2.0 * math.pi * h_gap) / max(den_ring, 1e-12)
    vent_g, vent_n = _vent_conductance_mm(settings, geom)
    total_g = max(ring_g + vent_g, 1e-12)
    f_h = (343000.0 / (2.0 * math.pi)) * math.sqrt(total_g / max(volume_mm3, 1e-12))

    # Lightweight resistance estimate inspired by the V17 SCAD model. It is an
    # order-of-magnitude design warning, not a full electro-acoustic simulation.
    rho_air = 1.204
    mu_air = 1.84e-5
    c_si = 343.0
    w0 = 2.0 * math.pi * max(f_h, 1e-6)
    k0 = w0 / c_si
    rin_m = geom.r_in_mm * 0.001
    rout_m = geom.r_out_mm * 0.001
    h_m = h_gap * 0.001
    ring_area_m2 = max(2.0 * math.pi * rout_m * h_m, 1e-18)
    a_ring_eq = math.sqrt(ring_area_m2 / math.pi)
    rv_ring = (12.0 * mu_air / max(2.0 * math.pi * h_m**3, 1e-18)) * math.log(max(rout_m / max(rin_m, 1e-12), 1.000001))
    rrad_ring = rho_air * c_si * (k0 * a_ring_eq) ** 2 / max(2.0 * ring_area_m2, 1e-18)
    r_ring = max(rv_ring + rrad_ring, 1e-12)
    r_eq = r_ring
    if vent_g > 0.0 and vent_n > 0:
        size_m = max(1e-6, float(settings.vent_size_mm) * 0.001)
        radius_m = size_m / 2.0
        area_m2 = math.pi * radius_m * radius_m
        rv_vent = (8.0 * mu_air * max((geom.r_out_mm - geom.r_in_mm) * 0.001, 1e-6)) / max(math.pi * radius_m**4, 1e-18)
        rrad_vent = rho_air * c_si * (k0 * radius_m) ** 2 / max(2.0 * area_m2, 1e-18)
        r_vent_one = max(rv_vent + rrad_vent, 1e-12)
        r_eq = 1.0 / ((1.0 / r_ring) + (vent_n / r_vent_one))
    m_eq = rho_air / max(total_g * 0.001, 1e-12)
    q_est = max(0.0, (w0 * m_eq) / max(r_eq, 1e-12))
    bw = f_h / max(q_est, 1e-12) if q_est > 0.0 else 0.0

    warnings: list[str] = []
    speaker_radius = max(0.0, float(settings.speaker_diameter_mm) / 2.0)
    if speaker_radius > geom.r_in_mm - 1.0:
        warnings.append("Speaker diameter is too close to the inner skirt diameter.")
    if geom.exit_height_mm < 2.0:
        warnings.append("Exit gap is narrow; air velocity may rise.")
    if abs(f_h - float(settings.target_frequency_hz)) > max(80.0, 0.20 * float(settings.target_frequency_hz)):
        warnings.append("Estimated tuning is far from target; adjust diameter, wall or vents.")
    if settings.vent_style != "none" and vent_g / total_g > 0.75:
        warnings.append("Vents dominate the acoustic conductance.")

    return AcousticDiffuserReport(
        geometry=geom,
        cavity_volume_cm3=volume_mm3 / 1000.0,
        helmholtz_hz=f_h,
        ring_conductance_mm=ring_g,
        vent_conductance_mm=vent_g,
        total_conductance_mm=total_g,
        ring_fraction=ring_g / total_g,
        estimated_q=q_est,
        estimated_bandwidth_hz=bw,
        warnings=tuple(warnings),
    )


def _add_quad(vertices: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]], cache: dict[tuple[int, int, int], int], keys: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]], xyz_of_key) -> None:
    ids: list[int] = []
    for key in keys:
        idx = cache.get(key)
        if idx is None:
            idx = len(vertices)
            cache[key] = idx
            vertices.append(xyz_of_key(key))
        ids.append(idx)
    a, b, c, d = ids
    if len({a, b, c, d}) < 4:
        return
    triangles.append((a, b, c))
    triangles.append((a, c, d))


def _triangle_area_2d(coords: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]) -> float:
    (x0, y0), (x1, y1), (x2, y2) = coords
    return 0.5 * ((x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0))


def _triangulate_polygon_with_holes(exterior: list[tuple[float, float]], holes: list[tuple[tuple[float, float], ...]]):
    try:
        from shapely.geometry import Polygon
        try:
            from shapely import constrained_delaunay_triangles
        except Exception:  # pragma: no cover - Shapely < 2 fallback
            constrained_delaunay_triangles = None
        from shapely.ops import triangulate
    except Exception as exc:  # pragma: no cover - Shapely is a project dependency
        raise RuntimeError("Acoustic diffuser vents require Shapely triangulation.") from exc

    poly = Polygon(exterior, [list(h) for h in holes])
    if not poly.is_valid:
        poly = poly.buffer(0)
    return _triangulate_shapely_polygon(poly, error_context="skirt wall")


def _triangulate_shapely_polygon(poly, *, error_context: str):
    try:
        try:
            from shapely import constrained_delaunay_triangles
        except Exception:  # pragma: no cover - Shapely < 2 fallback
            constrained_delaunay_triangles = None
        from shapely.ops import triangulate
    except Exception as exc:  # pragma: no cover - Shapely is a project dependency
        raise RuntimeError("Acoustic diffuser vents require Shapely triangulation.") from exc

    if getattr(poly, "is_empty", False):
        raise ValueError(f"Acoustic diffuser failed: {error_context} has no valid area.")
    if not getattr(poly, "is_valid", True):
        poly = poly.buffer(0)
    if getattr(poly, "is_empty", False):
        raise ValueError(f"Acoustic diffuser failed: {error_context} has no valid area.")

    raw = constrained_delaunay_triangles(poly) if constrained_delaunay_triangles is not None else triangulate(poly)
    geoms = list(getattr(raw, "geoms", raw))
    out: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]] = []
    for tri in geoms:
        if getattr(tri, "is_empty", False) or float(getattr(tri, "area", 0.0)) <= 1e-8:
            continue
        # The fallback triangulator is not constrained.  Keep only triangles that
        # are fully covered by the wall domain, so no face crosses a vent hole.
        try:
            if not poly.covers(tri):
                continue
        except Exception:
            if tri.representative_point().within(poly) is False:
                continue
        coords = [(float(x), float(y)) for x, y in list(tri.exterior.coords)[:3]]
        if len(coords) != 3:
            continue
        tri_coords = (coords[0], coords[1], coords[2])
        if abs(_triangle_area_2d(tri_coords)) <= 1e-9:
            continue
        if _triangle_area_2d(tri_coords) < 0.0:
            tri_coords = (tri_coords[0], tri_coords[2], tri_coords[1])
        out.append(tri_coords)
    if not out:
        raise ValueError(f"Acoustic diffuser failed: {error_context} triangulation produced no faces.")
    return out


def _unique_sorted(values: list[float], *, minimum_gap: float = 1e-5) -> list[float]:
    if not values:
        return []
    vals = sorted(float(v) for v in values)
    out = [vals[0]]
    for value in vals[1:]:
        if abs(value - out[-1]) > minimum_gap:
            out.append(value)
    return out


def _triangulate_cylindrical_wall_domain(
    *,
    width: float,
    height: float,
    holes: list[tuple[tuple[float, float], ...]],
    arc_step_mm: float,
    z_step_mm: float,
):
    """Triangulate a developed cylinder as local tiles, not one global membrane.

    A global Delaunay triangulation around vent holes creates very long triangles
    from hole vertices to distant top/bottom border vertices.  Once those large
    flat triangles are wrapped back to a cylinder, the outside and inside skins
    look warped even though each vertex is on the right radius.  This tiled
    triangulation keeps the cylinder regular away from holes and confines the
    irregular topology to a small area around each opening.
    """
    try:
        from shapely.geometry import Polygon, box
    except Exception as exc:  # pragma: no cover - Shapely is a project dependency
        raise RuntimeError("Acoustic diffuser vents require Shapely triangulation.") from exc

    wall = Polygon([(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))], [list(h) for h in holes])
    if not wall.is_valid:
        wall = wall.buffer(0)
    if wall.is_empty:
        raise ValueError("Acoustic diffuser failed: vent layout leaves no skirt wall.")

    arc_step = max(1.0, float(arc_step_mm))
    z_step = max(1.0, float(z_step_mm))
    nx = max(12, int(math.ceil(float(width) / arc_step)))
    nz = max(4, int(math.ceil(float(height) / z_step)))
    x_cuts = [0.0, float(width)] + [float(width) * i / nx for i in range(1, nx)]
    z_cuts = [0.0, float(height)] + [float(height) * j / nz for j in range(1, nz)]

    # Add opening extents and centres as cuts.  The exact circular/rounded edge
    # remains the hole contour, but these cuts force nearby faces to stay local.
    for loop in holes:
        if not loop:
            continue
        xs = [float(p[0]) for p in loop]
        zs = [float(p[1]) for p in loop]
        min_x, max_x = max(0.0, min(xs)), min(float(width), max(xs))
        min_z, max_z = max(0.0, min(zs)), min(float(height), max(zs))
        cx = 0.5 * (min_x + max_x)
        cz = 0.5 * (min_z + max_z)
        x_cuts.extend([min_x, cx, max_x])
        z_cuts.extend([min_z, cz, max_z])

    x_cuts = _unique_sorted([_clamp(x, 0.0, float(width)) for x in x_cuts])
    z_cuts = _unique_sorted([_clamp(z, 0.0, float(height)) for z in z_cuts])
    tris: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]] = []

    for xi in range(len(x_cuts) - 1):
        x0, x1 = x_cuts[xi], x_cuts[xi + 1]
        if x1 - x0 <= 1e-6:
            continue
        for zi in range(len(z_cuts) - 1):
            z0, z1 = z_cuts[zi], z_cuts[zi + 1]
            if z1 - z0 <= 1e-6:
                continue
            tile = box(x0, z0, x1, z1)
            clipped = wall.intersection(tile)
            if getattr(clipped, "is_empty", False) or float(getattr(clipped, "area", 0.0)) <= 1e-8:
                continue
            pieces = list(getattr(clipped, "geoms", [clipped]))
            for piece in pieces:
                if getattr(piece, "geom_type", "") != "Polygon" or float(getattr(piece, "area", 0.0)) <= 1e-8:
                    continue
                tris.extend(_triangulate_shapely_polygon(piece, error_context="local skirt wall tile"))

    if not tris:
        raise ValueError("Acoustic diffuser failed: local skirt wall triangulation produced no faces.")
    return tris




def _wall_boundary_edges(
    surface_tris: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]],
    *,
    width: float,
    height: float,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    def key(point: tuple[float, float]) -> tuple[int, int]:
        x, z = point
        return (_round_key(_clamp(float(x), 0.0, float(width))), _round_key(_clamp(float(z), 0.0, float(height))))

    edges: dict[tuple[tuple[int, int], tuple[int, int]], list[object]] = {}
    for tri in surface_tris:
        pts = (tri[0], tri[1], tri[2])
        for p0, p1 in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])):
            k0 = key(p0)
            k1 = key(p1)
            if k0 == k1:
                continue
            ek = (k0, k1) if k0 < k1 else (k1, k0)
            rec = edges.get(ek)
            if rec is None:
                edges[ek] = [1, (float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1]))]
            else:
                rec[0] = int(rec[0]) + 1

    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for rec in edges.values():
        if int(rec[0]) != 1:
            continue
        p0 = rec[1]  # type: ignore[assignment]
        p1 = rec[2]  # type: ignore[assignment]
        out.append(((float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1]))))
    return out


def _wall_hole_boundary_edges(
    surface_tris: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]],
    *,
    width: float,
    height: float,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Return 2D boundary edges that belong to vents, including clipped splits."""
    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    eps = 1e-5
    for p0, p1 in _wall_boundary_edges(surface_tris, width=width, height=height):
        x0, z0 = float(p0[0]), float(p0[1])
        x1, z1 = float(p1[0]), float(p1[1])
        on_bottom = abs(z0) <= eps and abs(z1) <= eps
        on_top = abs(z0 - height) <= eps and abs(z1 - height) <= eps
        on_left = abs(x0) <= eps and abs(x1) <= eps
        on_right = abs(x0 - width) <= eps and abs(x1 - width) <= eps
        if on_bottom or on_top or on_left or on_right:
            continue
        out.append(((x0, z0), (x1, z1)))
    return out


def _wall_cap_boundary_edges(
    surface_tris: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]],
    *,
    width: float,
    height: float,
    z_value: float,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Return exact top/bottom wall boundary splits for annular caps."""
    target = float(z_value)
    eps = 1e-5
    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for p0, p1 in _wall_boundary_edges(surface_tris, width=width, height=height):
        x0, z0 = float(p0[0]), float(p0[1])
        x1, z1 = float(p1[0]), float(p1[1])
        if abs(z0 - target) > eps or abs(z1 - target) > eps:
            continue
        # Keep a deterministic increasing-x order; x=width later maps to x=0
        # on the cylinder seam.
        if x1 < x0:
            x0, x1 = x1, x0
            z0, z1 = z1, z0
        out.append(((x0, z0), (x1, z1)))
    out.sort(key=lambda edge: (edge[0][0], edge[1][0]))
    return out

def _build_skirt_mesh(settings: AcousticDiffuserSettings, report: AcousticDiffuserReport) -> WorkMesh:
    geom = report.geometry
    quality = _quality_value(settings)
    theta_steps = max(24, min(192, quality))
    r_values = (geom.r_in_mm, geom.r_out_mm)
    r_mid = max(1e-6, 0.5 * (geom.r_in_mm + geom.r_out_mm))
    width = 2.0 * math.pi * r_mid
    height = max(1e-6, geom.skirt_height_mm)

    # The outside/inside wall is triangulated in developed cylinder coordinates
    # (arc length, z), then wrapped back to 3D.  Unlike the previous grid-cell
    # approach, vent edges are real circular/rounded contours with tunnel faces.
    openings = _vent_opening_specs(settings, geom)
    x_samples = [width * i / theta_steps for i in range(theta_steps + 1)]
    z_step_target = _clamp(115.0 / max(quality, 1), 0.90, 4.80)
    z_edge_steps = max(3, min(64, int(math.ceil(height / z_step_target))))
    z_samples = [height * j / z_edge_steps for j in range(z_edge_steps + 1)]
    exterior: list[tuple[float, float]] = []
    exterior.extend((x, 0.0) for x in x_samples)
    exterior.extend((width, z) for z in z_samples[1:])
    exterior.extend((x, height) for x in reversed(x_samples[:-1]))
    exterior.extend((0.0, z) for z in reversed(z_samples[1:-1]))
    holes = [opening.loop_xz_mm for opening in openings]
    if holes:
        surface_tris = _triangulate_cylindrical_wall_domain(
            width=width,
            height=height,
            holes=holes,
            arc_step_mm=max(1.0, width / theta_steps),
            z_step_mm=max(1.0, height / max(3, z_edge_steps)),
        )
    else:
        surface_tris = _triangulate_polygon_with_holes(exterior, holes)

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    cache: dict[tuple[int, int, int], int] = {}

    def norm_x(x: float) -> float:
        x = float(x)
        if abs(x - width) <= 1e-6 or abs(x) <= 1e-6:
            return 0.0
        return x % width

    def key_xz(x: float, z: float) -> tuple[int, int]:
        return (_round_key(norm_x(x)), _round_key(_clamp(float(z), 0.0, height)))

    def add_vertex(radius_index: int, x: float, z: float) -> int:
        kx, kz = key_xz(x, z)
        key = (int(radius_index), kx, kz)
        idx = cache.get(key)
        if idx is not None:
            return idx
        theta = (kx / 1_000_000.0) / r_mid
        radius = r_values[int(radius_index)]
        idx = len(vertices)
        cache[key] = idx
        vertices.append((float(radius * math.cos(theta)), float(radius * math.sin(theta)), float(kz / 1_000_000.0)))
        return idx

    def add_tri(a: int, b: int, c: int) -> None:
        if len({int(a), int(b), int(c)}) < 3:
            return
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        area2 = (uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2
        if area2 <= 1e-14:
            return
        triangles.append((int(a), int(b), int(c)))

    # Outer and inner cylindrical walls.  Input triangles are CCW in (arc,z),
    # which maps to outward normals on the outside; inner normals are reversed.
    for tri in surface_tris:
        ids_o = [add_vertex(1, x, z) for x, z in tri]
        add_tri(ids_o[0], ids_o[1], ids_o[2])
        ids_i = [add_vertex(0, x, z) for x, z in tri]
        add_tri(ids_i[0], ids_i[2], ids_i[1])

    # Top and bottom annular caps.  Use the exact boundary split produced by the
    # side-wall triangulation; otherwise a locally refined vent wall leaves
    # unmatched small edges on the top/bottom rings.
    for (p0, p1) in _wall_cap_boundary_edges(surface_tris, width=width, height=height, z_value=0.0):
        x0, _z0 = p0
        x1, _z1 = p1
        ob0 = add_vertex(1, x0, 0.0)
        ob1 = add_vertex(1, x1, 0.0)
        ib0 = add_vertex(0, x0, 0.0)
        ib1 = add_vertex(0, x1, 0.0)
        add_tri(ob0, ib0, ib1)
        add_tri(ob0, ib1, ob1)

    for (p0, p1) in _wall_cap_boundary_edges(surface_tris, width=width, height=height, z_value=height):
        x0, _z0 = p0
        x1, _z1 = p1
        ot0 = add_vertex(1, x0, height)
        ot1 = add_vertex(1, x1, height)
        it0 = add_vertex(0, x0, height)
        it1 = add_vertex(0, x1, height)
        add_tri(ot0, ot1, it1)
        add_tri(ot0, it1, it0)

    # Smooth radial tunnel walls for each vent contour.  Use the exact boundary
    # edges produced by the local wall triangulation so clipped/split circular
    # edges stay watertight and the cylinder skins do not get pulled into a
    # global triangulation membrane.
    for (p0, p1) in _wall_hole_boundary_edges(surface_tris, width=width, height=height):
        x0, z0 = p0
        x1, z1 = p1
        o0 = add_vertex(1, x0, z0)
        o1 = add_vertex(1, x1, z1)
        inn0 = add_vertex(0, x0, z0)
        inn1 = add_vertex(0, x1, z1)
        add_tri(o0, inn1, inn0)
        add_tri(o0, o1, inn1)

    return WorkMesh(name="acoustic_diffuser_skirt", vertices=vertices, triangles=triangles, color=settings.color_skirt)

def _build_diffuser_mesh(settings: AcousticDiffuserSettings, report: AcousticDiffuserReport) -> WorkMesh:
    geom = report.geometry
    quality = _quality_value(settings)
    theta_steps = max(24, min(192, quality))
    curve_steps = max(10, min(120, int(round(quality * 0.65))))
    axis_eps = 0.05
    r_out = geom.r_out_mm
    r_diff = max(axis_eps, geom.diffuser_radius_mm)
    rim_t = geom.rim_thickness_mm
    z0 = geom.diffuser_base_z_mm
    h = geom.diffuser_height_mm
    p = geom.shape_power

    profile: list[tuple[float, float]] = []
    profile.append((axis_eps, z0))
    for i in range(1, curve_steps + 1):
        u = _smoothstep(i / curve_steps)
        profile.append((axis_eps + (r_diff - axis_eps) * u, z0 + _under_z(u, h, p)))
    profile.append((r_out, z0 + h))
    profile.append((r_out, z0 + h + rim_t))
    profile.append((axis_eps, z0 + h + rim_t))

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    def idx(pi: int, ti: int) -> int:
        return pi * theta_steps + (ti % theta_steps)

    for r, z in profile:
        for t in range(theta_steps):
            vertices.append(_xy(r, t, theta_steps, z))

    for pi in range(len(profile)):
        pj = (pi + 1) % len(profile)
        for t in range(theta_steps):
            tn = (t + 1) % theta_steps
            a = idx(pi, t)
            b = idx(pi, tn)
            c = idx(pj, tn)
            d = idx(pj, t)
            triangles.append((a, b, c))
            triangles.append((a, c, d))

    return WorkMesh(name="acoustic_diffuser_core", vertices=vertices, triangles=triangles, color=settings.color_diffuser)


def build_acoustic_diffuser(settings: AcousticDiffuserSettings | None = None) -> AcousticDiffuserResult:
    s = settings or AcousticDiffuserSettings()
    report = analyze_acoustic_diffuser(s)
    meshes = (_build_skirt_mesh(s, report), _build_diffuser_mesh(s, report))
    return AcousticDiffuserResult(meshes=meshes, report=report)
