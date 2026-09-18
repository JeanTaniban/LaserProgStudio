# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import math

from PIL import Image, ImageDraw, ImageFilter


def _texture_path_for_mesh(mesh: Any, texture_assets_by_id: dict[str, Any] | None = None) -> Path | None:
    """Resolve the bitmap path stored by the TEX tool."""

    texture_assets_by_id = texture_assets_by_id or {}
    try:
        material = getattr(mesh, "material", None)
        texture_id = getattr(material, "texture_id", None) if material is not None and not isinstance(material, dict) else None
        if texture_id:
            asset = texture_assets_by_id.get(str(texture_id))
            if asset is not None:
                p = Path(getattr(asset, "path", "")).expanduser()
                if p.exists():
                    return p
    except Exception:
        pass
    try:
        for projection in list(getattr(mesh, "texture_projections", []) or []):
            raw = getattr(projection, "texture_path", None)
            if raw:
                p = Path(raw).expanduser()
                if p.exists():
                    return p
    except Exception:
        pass
    return None


def _texture_export_usage(mesh: Any) -> str:
    """Return manufacturing usage for a TEX bitmap/decal.

    Only two usages are exported by the engraving generator:
    - ``engrave`` keeps the bitmap as a grayscale raster layer;
    - ``cut`` traces the bitmap mask into vector contours.

    ``visual`` remains viewport-only. Older projects with only projection-layer
    metadata are interpreted conservatively as ``engrave`` when their projection
    was not ignored.
    """

    try:
        engraving = getattr(mesh, "engraving", None)
        usage = str(getattr(engraving, "texture_usage", "") or "").lower() if engraving is not None else ""
        if usage in {"cut", "engrave", "visual"}:
            return usage
    except Exception:
        pass
    try:
        projections = list(getattr(mesh, "texture_projections", []) or [])
        for projection in projections:
            layer = str(getattr(projection, "engraving_layer", "ignore") or "ignore").lower()
            if layer == "cut":
                return "cut"
            if layer == "engrave":
                return "engrave"
    except Exception:
        pass
    return "visual"


def _texture_export_enabled(mesh: Any, *, usage_filter: str = "engrave") -> bool:
    """Return True when a mesh texture should be exported for the requested usage."""

    try:
        if getattr(mesh, "uvs", None) is None:
            return False
        usage = _texture_export_usage(mesh)
        return usage == str(usage_filter or "engrave").lower()
    except Exception:
        return False


def _texture_repeat_for_mesh(mesh: Any) -> bool:
    try:
        for projection in list(getattr(mesh, "texture_projections", []) or []):
            return bool(getattr(projection, "repeat", False))
    except Exception:
        pass
    return False


def _triangle_area_2d(points: list[tuple[float, float]]) -> float:
    if len(points) != 3:
        return 0.0
    (x1, y1), (x2, y2), (x3, y3) = points
    return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) * 0.5


def _affine_coefficients(dst: list[tuple[float, float]], src: list[tuple[float, float]]) -> tuple[float, float, float, float, float, float] | None:
    """Solve source = A * destination for PIL's affine transform."""

    try:
        import numpy as np

        mat = np.array([[dst[0][0], dst[0][1], 1.0], [dst[1][0], dst[1][1], 1.0], [dst[2][0], dst[2][1], 1.0]], dtype=float)
        sx = np.array([src[0][0], src[1][0], src[2][0]], dtype=float)
        sy = np.array([src[0][1], src[1][1], src[2][1]], dtype=float)
        ax, bx, cx = np.linalg.solve(mat, sx)
        ay, by, cy = np.linalg.solve(mat, sy)
        return (float(ax), float(bx), float(cx), float(ay), float(by), float(cy))
    except Exception:
        return None


def _repeated_texture_for_triangle(texture: Image.Image, uv: list[tuple[float, float]]) -> tuple[Image.Image, list[tuple[float, float]]]:
    """Tile the source bitmap when projected UVs go outside 0..1.

    PIL affine sampling does not implement VTK-style texture repeat. For export
    layers we build a per-triangle tiled bitmap and remap UVs into that temporary
    image. The tile count is capped to keep pathological UVs from exploding RAM.
    """

    try:
        min_u = math.floor(min(float(u) for u, _v in uv))
        max_u = math.ceil(max(float(u) for u, _v in uv))
        min_v = math.floor(min(float(v) for _u, v in uv))
        max_v = math.ceil(max(float(v) for _u, v in uv))
        tiles_u = max(1, int(max_u - min_u))
        tiles_v = max(1, int(max_v - min_v))
        tiles_u = min(tiles_u, 32)
        tiles_v = min(tiles_v, 32)
        if tiles_u <= 1 and tiles_v <= 1 and min_u == 0 and min_v == 0:
            return texture, uv
        w, h = texture.size
        tiled = Image.new(texture.mode, (max(1, w * tiles_u), max(1, h * tiles_v)), (255, 255, 255, 0) if texture.mode == "RGBA" else "white")
        for yy in range(tiles_v):
            for xx in range(tiles_u):
                tiled.paste(texture, (xx * w, yy * h))
        u0 = float(min_u)
        v0 = float(min_v)
        span_u = float(tiles_u)
        span_v = float(tiles_v)
        mapped = [((float(u) - u0) / span_u, (float(v) - v0) / span_v) for u, v in uv]
        return tiled, mapped
    except Exception:
        return texture, uv


def _paste_textured_triangle(
    canvas: Image.Image,
    texture: Image.Image,
    *,
    dst: list[tuple[float, float]],
    uv: list[tuple[float, float]],
    repeat: bool = False,
) -> bool:
    if _triangle_area_2d(dst) < 0.5:
        return False
    if bool(repeat):
        texture, uv = _repeated_texture_for_triangle(texture, uv)
    w, h = texture.size
    if w <= 1 or h <= 1:
        return False
    # VTK/PyVista convention: V=0 is the bottom of the image.  PIL source Y grows
    # downward, hence the 1-v flip below.
    src = [(float(u) * (w - 1), (1.0 - float(v)) * (h - 1)) for u, v in uv]
    coeff = _affine_coefficients(dst, src)
    if coeff is None:
        return False
    min_x = max(0, int(min(x for x, _y in dst)) - 2)
    max_x = min(canvas.width, int(max(x for x, _y in dst)) + 3)
    min_y = max(0, int(min(y for _x, y in dst)) - 2)
    max_y = min(canvas.height, int(max(y for _x, y in dst)) + 3)
    if max_x <= min_x or max_y <= min_y:
        return False
    local_dst = [(x - min_x, y - min_y) for x, y in dst]
    a, b, c, d, e, f = coeff
    local_coeff = (a, b, c + a * min_x + b * min_y, d, e, f + d * min_x + e * min_y)
    size = (max_x - min_x, max_y - min_y)
    try:
        transform_kind = Image.Transform.AFFINE
    except AttributeError:  # pragma: no cover - old Pillow fallback
        transform_kind = Image.AFFINE
    try:
        resample = Image.Resampling.BICUBIC
    except AttributeError:  # pragma: no cover
        resample = Image.BICUBIC
    patch = texture.transform(size, transform_kind, local_coeff, resample=resample, fillcolor=(255, 255, 255, 0))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(local_dst, fill=255)
    if patch.mode != "RGBA":
        patch = patch.convert("RGBA")
    # Keep the texture alpha, then clip by the triangle mask.
    try:
        alpha = patch.getchannel("A")
        alpha = Image.composite(alpha, Image.new("L", size, 0), mask)
        patch.putalpha(alpha)
    except Exception:
        patch.putalpha(mask)
    canvas.alpha_composite(patch, dest=(min_x, min_y))
    return True


def render_texture_layer_from_meshes(
    meshes: Iterable[Any],
    *,
    texture_assets_by_id: dict[str, Any] | None,
    bounds: tuple[float, float, float, float],
    cfg: Any,
    usage_filter: str = "engrave",
    source_mode: str = "grayscale",
) -> Image.Image:
    """Render TEX-projected bitmaps as a separate top-down engraving layer.

    The geometry layer is still produced from the mesh colours/engraving roles;
    this function produces the second raster layer containing only bitmap texture
    pixels.  It uses the same CanvasTransform as the laser images, so all layers
    line up in Falcon/laser workflows.
    """

    try:
        from laserprog_studio.engraving.export_2d import CanvasTransform
    except Exception:  # package/test import fallback
        from laserprog_studio.engraving.export_2d import CanvasTransform

    tr = CanvasTransform(bounds, cfg)
    canvas = Image.new("RGBA", (tr.width, tr.height), (255, 255, 255, 255))
    texture_cache: dict[tuple[Path, str], Image.Image] = {}

    for mesh in list(meshes):
        uvs = getattr(mesh, "uvs", None)
        if not uvs or not _texture_export_enabled(mesh, usage_filter=usage_filter):
            continue
        path = _texture_path_for_mesh(mesh, texture_assets_by_id)
        if path is None:
            continue
        try:
            mode_key = str(source_mode or "grayscale").lower().strip()
            cache_key = (path, mode_key)
            texture = texture_cache.get(cache_key)
            if texture is None:
                # White compositing gives a sane laser layer for PNGs with alpha.
                raw = Image.open(path).convert("RGBA")
                white = Image.new("RGBA", raw.size, (255, 255, 255, 255))
                base_texture = Image.alpha_composite(white, raw).convert("RGBA")
                if mode_key in {"binary_boundary", "cut_boundary", "outline"}:
                    texture = _binary_boundary_texture_from_source(base_texture, threshold=245, line_width=1)
                elif mode_key in {"binary_fill", "cut_fill", "mask"}:
                    texture = _binary_fill_texture_from_source(base_texture, threshold=245)
                else:
                    texture = base_texture
                texture_cache[cache_key] = texture
        except Exception:
            continue
        vertices = [tuple(float(x) for x in v) for v in getattr(mesh, "vertices", [])]
        triangles = list(getattr(mesh, "triangles", []) or [])
        repeat = _texture_repeat_for_mesh(mesh)
        if len(uvs) != len(vertices):
            continue
        for tri in triangles:
            try:
                ids = [int(tri[0]), int(tri[1]), int(tri[2])]
                dst = [tuple(float(v) for v in tr.pt((vertices[i][0], vertices[i][1]))) for i in ids]
                tuv = [tuple(float(v) for v in uvs[i]) for i in ids]
                _paste_textured_triangle(canvas, texture, dst=dst, uv=tuv, repeat=repeat)
            except Exception:
                continue
    return canvas.convert("RGB")


def _svg_number(value: float) -> str:
    return (f"{float(value):.6f}".rstrip("0").rstrip(".") or "0")


def export_texture_layer_svg(
    texture_layer: Image.Image,
    *,
    bounds: tuple[float, float, float, float],
    cfg: Any,
    out: Path | str,
) -> Path:
    """Export the raster texture layer as a real-size SVG container.

    TEX textures are bitmaps, so converting them into true vector paths would
    either destroy the grayscale detail or create enormous traced SVGs.  For
    Falcon Design Space the useful format is a second SVG in millimetres that
    embeds the bitmap texture layer at the same canvas size as the vector mesh
    SVG.  The user can import the geometry SVG and this texture SVG as two
    aligned jobs/layers.
    """

    try:
        from laserprog_studio.engraving.export_2d import CanvasTransform
    except Exception:  # package/test import fallback
        from laserprog_studio.engraving.export_2d import CanvasTransform

    import base64
    from io import BytesIO

    out_path = Path(out)
    tr = CanvasTransform(bounds, cfg)
    width_mm = float(tr.maxx - tr.minx)
    height_mm = float(tr.maxy - tr.miny)
    img = texture_layer.convert("RGBA")
    # Make white/no-engrave pixels transparent in the SVG container so this
    # second Falcon layer does not visually cover the geometry SVG when both are
    # imported together.  Dark/grey pixels remain opaque and keep their raster
    # engraving information.
    try:
        px = img.load()
        for yy in range(img.height):
            for xx in range(img.width):
                r, g, b, a = px[xx, yy]
                if a and r >= 250 and g >= 250 and b >= 250:
                    px[xx, yy] = (255, 255, 255, 0)
    except Exception:
        pass
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    svg = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" '
                f'width="{_svg_number(width_mm)}mm" height="{_svg_number(height_mm)}mm" '
                f'viewBox="0 0 {_svg_number(width_mm)} {_svg_number(height_mm)}">'
            ),
            "  <title>LaserProg Studio - Falcon texture engraving layer</title>",
            "  <desc>Units are millimetres. This SVG embeds the TEX bitmap layer aligned with the geometry SVG.</desc>",
            '  <metadata>{"generator":"LaserProg Studio","unit":"mm","target":"Falcon Design Space","layer":"texture raster engraving"}</metadata>',
            (
                f'  <image id="falcon_texture_engrave" x="0" y="0" '
                f'width="{_svg_number(width_mm)}" height="{_svg_number(height_mm)}" '
                f'preserveAspectRatio="none" href="data:image/png;base64,{encoded}" '
                f'xlink:href="data:image/png;base64,{encoded}"/>'
            ),
            "</svg>",
        ]
    ) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    return out_path


def _binary_active_from_texture(texture_layer: Image.Image, *, threshold: int = 245) -> list[list[bool]]:
    """Return a white/non-white mask for TEX cut tracing.

    White pixels are considered empty. Black and grey pixels are active, because
    laser cut mode needs the boundary between the visible grayscale texture and
    the white/no-cut background.
    """

    gray = texture_layer.convert("L")
    w, h = gray.size
    px = gray.load()
    return [[int(px[x, y]) < int(threshold) for x in range(w)] for y in range(h)]


def _binary_boundary_texture_from_source(texture: Image.Image, *, threshold: int = 245, line_width: int = 1) -> Image.Image:
    """Convert a source bitmap to a white image with black binary boundaries only.

    This is used for TEX Cut outline preview.  It deliberately happens before
    projecting the image onto the face, so the exported layer represents the
    boundaries inside the texture itself, not merely the outside rectangle of the
    projected decal.
    """
    active = _binary_active_from_texture(texture, threshold=threshold)
    if not active or not active[0]:
        return Image.new("RGBA", texture.size, (255, 255, 255, 255))
    h = len(active)
    w = len(active[0])
    out = Image.new("L", (w, h), 255)
    px = out.load()

    def is_active(x: int, y: int) -> bool:
        return 0 <= x < w and 0 <= y < h and bool(active[y][x])

    for y in range(h):
        for x in range(w):
            if not active[y][x]:
                continue
            if (
                not is_active(x - 1, y)
                or not is_active(x + 1, y)
                or not is_active(x, y - 1)
                or not is_active(x, y + 1)
            ):
                px[x, y] = 0
    try:
        lw = max(1, int(line_width))
        if lw > 1:
            if lw % 2 == 0:
                lw += 1
            out = out.filter(ImageFilter.MinFilter(lw))
    except Exception:
        pass
    return out.convert("RGBA")


def _binary_fill_texture_from_source(texture: Image.Image, *, threshold: int = 245) -> Image.Image:
    """Return white background with black filled active mask from source texture."""
    active = _binary_active_from_texture(texture, threshold=threshold)
    if not active or not active[0]:
        return Image.new("RGBA", texture.size, (255, 255, 255, 255))
    h = len(active)
    w = len(active[0])
    out = Image.new("L", (w, h), 255)
    px = out.load()
    for y in range(h):
        for x in range(w):
            if active[y][x]:
                px[x, y] = 0
    return out.convert("RGBA")


def render_texture_cut_outline_mask(texture_layer: Image.Image, *, threshold: int = 245, line_width: int = 1) -> Image.Image:
    """Return a black/white preview mask containing only TEX cut boundaries.

    For TEX usage ``Cut outline`` the laser preview must not show the whole
    grayscale bitmap as a filled engraving layer.  We first binarize the texture
    canvas: white = 0/empty, every grey or black pixel = 1/active.  Then we keep
    only active pixels that touch an inactive neighbour.  The output is a normal
    RGB laser layer: white background and black boundary pixels.
    """

    active = _binary_active_from_texture(texture_layer, threshold=threshold)
    if not active or not active[0]:
        return Image.new("RGB", texture_layer.size, "white")
    h = len(active)
    w = len(active[0])
    out = Image.new("L", (w, h), 255)
    px = out.load()

    def is_active(x: int, y: int) -> bool:
        return 0 <= x < w and 0 <= y < h and bool(active[y][x])

    for y in range(h):
        for x in range(w):
            if not active[y][x]:
                continue
            if (
                not is_active(x - 1, y)
                or not is_active(x + 1, y)
                or not is_active(x, y - 1)
                or not is_active(x, y + 1)
            ):
                px[x, y] = 0
    try:
        lw = max(1, int(line_width))
        if lw > 1:
            if lw % 2 == 0:
                lw += 1
            out = out.filter(ImageFilter.MinFilter(lw))
    except Exception:
        pass
    return out.convert("RGB")


def _chain_boundary_edges(active: list[list[bool]]) -> list[list[tuple[int, int]]]:
    """Trace pixel-boundary edges into closed polylines in image grid units."""

    if not active or not active[0]:
        return []
    h = len(active)
    w = len(active[0])
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()

    def is_active(x: int, y: int) -> bool:
        return 0 <= x < w and 0 <= y < h and bool(active[y][x])

    for y in range(h):
        for x in range(w):
            if not active[y][x]:
                continue
            # Clockwise around each active pixel. Only edges touching empty space
            # are kept; shared edges vanish.
            if not is_active(x, y - 1):
                edges.add(((x, y), (x + 1, y)))
            if not is_active(x + 1, y):
                edges.add(((x + 1, y), (x + 1, y + 1)))
            if not is_active(x, y + 1):
                edges.add(((x + 1, y + 1), (x, y + 1)))
            if not is_active(x - 1, y):
                edges.add(((x, y + 1), (x, y)))

    starts: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for a, b in edges:
        starts.setdefault(a, []).append(b)

    paths: list[list[tuple[int, int]]] = []
    while edges:
        a, b = next(iter(edges))
        edges.remove((a, b))
        path = [a, b]
        current = b
        guard = 0
        while current != path[0] and guard < len(edges) + 4:
            guard += 1
            candidates = starts.get(current, [])
            nxt = None
            for cand in list(candidates):
                edge = (current, cand)
                if edge in edges:
                    nxt = cand
                    break
            if nxt is None:
                break
            edges.remove((current, nxt))
            path.append(nxt)
            current = nxt
        if len(path) >= 4:
            paths.append(_simplify_grid_polyline(path))
    return paths


def _simplify_grid_polyline(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(path) <= 3:
        return path
    closed = path[0] == path[-1]
    pts = path[:-1] if closed else path[:]
    out: list[tuple[int, int]] = []
    n = len(pts)
    for i, p in enumerate(pts):
        prev = pts[(i - 1) % n] if closed or i > 0 else None
        nxt = pts[(i + 1) % n] if closed or i < n - 1 else None
        if prev is None or nxt is None:
            out.append(p)
            continue
        dx1, dy1 = p[0] - prev[0], p[1] - prev[1]
        dx2, dy2 = nxt[0] - p[0], nxt[1] - p[1]
        if dx1 * dy2 - dy1 * dx2 == 0:
            continue
        out.append(p)
    if closed and out and out[0] != out[-1]:
        out.append(out[0])
    return out


def _grid_path_to_svg(path: list[tuple[int, int]], *, sx: float, sy: float) -> str:
    if len(path) < 2:
        return ""
    commands = [f"M {_svg_number(path[0][0] * sx)} {_svg_number(path[0][1] * sy)}"]
    for x, y in path[1:]:
        commands.append(f"L {_svg_number(x * sx)} {_svg_number(y * sy)}")
    if path[0] != path[-1]:
        commands.append("Z")
    return " ".join(commands)


def export_texture_cut_contours_svg(
    texture_layer: Image.Image,
    *,
    bounds: tuple[float, float, float, float],
    cfg: Any,
    out: Path | str,
    threshold: int = 245,
) -> Path:
    """Export texture cut usage as Falcon-compatible vector contours.

    The input is the same real-size texture canvas as the raster engraving layer.
    Non-white pixels are considered material to cut around; boundaries between
    non-white pixels and white background become green vector cut paths.
    """

    try:
        from laserprog_studio.engraving.export_2d import CanvasTransform
    except Exception:  # package/test import fallback
        from laserprog_studio.engraving.export_2d import CanvasTransform

    out_path = Path(out)
    tr = CanvasTransform(bounds, cfg)
    width_mm = float(tr.maxx - tr.minx)
    height_mm = float(tr.maxy - tr.miny)
    img = texture_layer.convert("RGB")
    active = _binary_active_from_texture(img, threshold=threshold)
    paths = _chain_boundary_edges(active)
    if not paths:
        raise RuntimeError("No non-white texture pixels to trace for cut SVG.")
    sx = width_mm / max(float(img.width), 1.0)
    sy = height_mm / max(float(img.height), 1.0)
    outline_width = max(float(getattr(cfg, "contour_width_mm", 0.1) or 0.1), 0.001)
    svg_paths = [_grid_path_to_svg(path, sx=sx, sy=sy) for path in paths]
    svg_paths = [p for p in svg_paths if p]
    svg = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
                f'width="{_svg_number(width_mm)}mm" height="{_svg_number(height_mm)}mm" '
                f'viewBox="0 0 {_svg_number(width_mm)} {_svg_number(height_mm)}">'
            ),
            "  <title>LaserProg Studio - Falcon texture cut contours</title>",
            "  <desc>Units are millimetres. Green paths are cut contours traced from TEX non-white/white boundaries.</desc>",
            '  <metadata>{"generator":"LaserProg Studio","unit":"mm","target":"Falcon Design Space","layer":"texture vector cut","threshold":245}</metadata>',
            (
                f'  <g id="falcon_texture_cut" fill="none" stroke="#00C853" '
                f'stroke-width="{_svg_number(outline_width)}" stroke-linecap="round" stroke-linejoin="round">'
            ),
        ]
        + [f'    <path id="texture_cut_{i:03d}" d="{path}"/>' for i, path in enumerate(svg_paths, start=1)]
        + ["  </g>", "</svg>"]
    ) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    return out_path


def texture_layer_has_marks(texture_layer: Image.Image, *, threshold: int = 245) -> bool:
    """True if an exported texture canvas contains any non-white mark."""

    try:
        gray = texture_layer.convert("L")
        return min(gray.getdata()) < int(threshold)
    except Exception:
        return False


__all__ = ["render_texture_layer_from_meshes", "render_texture_cut_outline_mask", "export_texture_layer_svg", "export_texture_cut_contours_svg", "texture_layer_has_marks"]
