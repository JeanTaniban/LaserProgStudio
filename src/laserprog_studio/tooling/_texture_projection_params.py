# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams

from laserprog_studio.geometry_ops.texture_projection_vector import _normalize_rotation_deg

from ._texture_projection_geometry import vec3_or_none


def texture_image_size(path: str | Path) -> tuple[int | None, int | None]:
    path = str(path or "").strip()
    if not path:
        return (None, None)
    try:
        from PIL import Image

        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception:
        return (None, None)


def stable_texture_id(path: str | Path) -> str:
    p = Path(str(path or "")).expanduser()
    identity = str(p.resolve() if p.exists() else p)
    return "tex_" + uuid5(NAMESPACE_URL, identity).hex[:12]


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off", ""}:
            return False
    try:
        return bool(value)
    except Exception:
        return bool(default)


def _float_clamped(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
        if not out == out:
            return float(default)
    except Exception:
        out = float(default)
    return max(float(lo), min(float(hi), out))


def texture_params_from_values(values: dict[str, Any], ctx: Any | None = None) -> TextureProjectionParams:
    path = str(values.get("texture_path", "") or "").strip()
    image_width, image_height = texture_image_size(path)
    usage = str(values.get("usage", "visual") or "visual")
    texture_id = stable_texture_id(path) if path else "texture"
    if path and ctx is not None:
        try:
            asset = ctx.assets.import_image(path, usage=usage, asset_id=texture_id, width=image_width, height=image_height)
            texture_id = str(getattr(asset, "id", texture_id) or texture_id)
            image_width = getattr(asset, "width", image_width)
            image_height = getattr(asset, "height", image_height)
            owner = getattr(ctx, "owner", None)
            store = getattr(owner, "recent_texture_store", None) if owner is not None else None
            if store is not None:
                try:
                    store.add(Path(path).expanduser())
                except Exception:
                    pass
        except Exception:
            pass
    seed_face = values.get("seed_face_index", None)
    try:
        seed_face_index = None if seed_face in (None, "", -1, "-1") else int(seed_face)
    except Exception:
        seed_face_index = None
    origin_active = seed_face_index is not None or as_bool(values.get("projection_origin_active", False))
    projection_origin = vec3_or_none(values.get("projection_origin")) if origin_active else None
    projection_normal = vec3_or_none(values.get("projection_normal")) if origin_active else None
    return TextureProjectionParams(
        texture_id=texture_id,
        texture_path=path,
        projection_mode=str(values.get("projection_mode", "planar") or "planar"),
        usage=usage,
        coverage_angle_deg=max(0.0, min(180.0, float(values.get("coverage_angle_deg", 20.0)))),
        scale=_float_clamped(values.get("scale", 1.0), 1.0, 1.0e-6, 100000.0),
        stretch_u=_float_clamped(values.get("stretch_u", 1.0), 1.0, 1.0e-6, 100000.0),
        stretch_v=_float_clamped(values.get("stretch_v", 1.0), 1.0, 1.0e-6, 100000.0),
        rotation_deg=_normalize_rotation_deg(_float_clamped(values.get("rotation_deg", 0.0), 0.0, -1000000.0, 1000000.0)),
        offset_u=float(values.get("offset_u", 0.0)),
        offset_v=float(values.get("offset_v", 0.0)),
        repeat=as_bool(values.get("repeat", False)),
        attach_to_mesh=as_bool(values.get("attach_to_mesh", False)),
        preserve_aspect=as_bool(values.get("preserve_aspect", True), default=True),
        image_width=image_width,
        image_height=image_height,
        seed_face_index=seed_face_index,
        projection_origin=projection_origin,
        projection_normal=projection_normal,
    )


__all__ = ["as_bool", "stable_texture_id", "texture_image_size", "texture_params_from_values"]
