# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any


def _owner_log(owner: Any, message: str) -> None:
    try:
        logger = getattr(owner, "ui_log", None)
        if callable(logger):
            logger(message)
    except Exception:
        pass


def texture_path_for_mesh(owner: Any, mesh: Any) -> Path | None:
    try:
        material = getattr(mesh, "material", None)
        texture_id = getattr(material, "texture_id", None) if material is not None and not isinstance(material, dict) else None
        if texture_id:
            asset = getattr(owner, "texture_assets_by_id", {}).get(str(texture_id))
            if asset is not None and Path(getattr(asset, "path", "")).expanduser().exists():
                return Path(asset.path).expanduser()
        for projection in list(getattr(mesh, "texture_projections", []) or []):
            path = getattr(projection, "texture_path", None)
            if path and Path(path).expanduser().exists():
                return Path(path).expanduser()
    except Exception as exc:
        _owner_log(owner, f"[TEXTURE][WARN] texture_path_for_mesh failed: {exc}")
    return None


def texture_repeat_for_mesh(mesh: Any) -> bool:
    try:
        for projection in list(getattr(mesh, "texture_projections", []) or []):
            return bool(getattr(projection, "repeat", False))
    except Exception:
        pass
    return False


def _parse_hex_rgba(value: Any, *, fallback: tuple[float, float, float, float] = (0.72, 0.72, 0.72, 1.0)) -> tuple[float, float, float, float]:
    text = str(value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 8:
        text = text[:6]
    if len(text) != 6:
        return fallback
    try:
        return (int(text[0:2], 16) / 255.0, int(text[2:4], 16) / 255.0, int(text[4:6], 16) / 255.0, 1.0)
    except Exception:
        return fallback


def texture_border_color_for_mesh(owner: Any, mesh: Any) -> tuple[float, float, float, float]:
    """Neutral color used when a non-repeated TEX bitmap is sampled outside 0..1."""

    try:
        mode = str(getattr(getattr(owner, "render_state", None), "display_mode", "") or "").lower()
    except Exception:
        mode = ""
    saved_attr = "texture_pre_projection_material_color" if mode == "material" else "texture_pre_projection_role_color"
    legacy_saved_attr = "texture_saved_material_color" if mode == "material" else "texture_saved_role_color"
    attr = "texture_border_material_color" if mode == "material" else "texture_border_role_color"
    value = (
        getattr(mesh, saved_attr, None)
        or getattr(mesh, legacy_saved_attr, None)
        or getattr(mesh, attr, None)
        or getattr(mesh, "texture_border_color", None)
    )
    if value is None:
        material = getattr(mesh, "material", None)
        if mode == "material":
            if isinstance(material, dict):
                value = material.get("base_color")
            else:
                value = getattr(material, "base_color", None)
        value = value or getattr(mesh, "color", None)
    return _parse_hex_rgba(value, fallback=(0.72, 0.72, 0.72, 1.0))


def _texture_cache_key(path: Path, *, repeat: bool, border_color: tuple[float, float, float, float] | None = None) -> tuple[str, int | None, int | None, bool, tuple[int, int, int, int] | None]:
    rgba = None
    if not bool(repeat) and border_color is not None:
        rgba = tuple(max(0, min(255, int(round(float(c) * 255.0)))) for c in border_color)
    try:
        stat = path.stat()
        return (str(path.resolve()), int(stat.st_mtime_ns), int(stat.st_size), bool(repeat), rgba)
    except Exception:
        return (str(path), None, None, bool(repeat), rgba)


def _padded_texture_array(path: Path, border_color: tuple[float, float, float, float], *, border_px: int = 2):
    """Return an RGBA image array with a neutral border fallback for old VTK."""

    from PIL import Image
    import numpy as np

    raw = Image.open(path).convert("RGBA")
    border_px = max(1, int(border_px))
    rgba = tuple(max(0, min(255, int(round(float(c) * 255.0)))) for c in border_color)
    padded = Image.new("RGBA", (raw.width + 2 * border_px, raw.height + 2 * border_px), rgba)
    padded.paste(raw, (border_px, border_px), raw)
    return np.asarray(padded, dtype=np.uint8)


def _read_texture(owner: Any, pv: Any, path: Path, *, repeat: bool, border_color: tuple[float, float, float, float]) -> Any:
    if bool(repeat):
        return pv.read_texture(str(path))
    try:
        array = _padded_texture_array(path, border_color)
        converter = getattr(pv, "numpy_to_texture", None)
        if callable(converter):
            return converter(array)
        return pv.Texture(array)
    except Exception as exc:
        _owner_log(owner, f"[TEXTURE][WARN] neutral-border texture fallback failed: {exc}")
        return pv.read_texture(str(path))


def _configure_texture(texture: Any, *, repeat: bool, border_color: tuple[float, float, float, float] | None = None) -> None:
    # PyVista wraps vtkTexture.  Property names changed between versions, so use
    # several safe attempts.  These calls are deliberately best-effort; a texture
    # must never disappear just because an old VTK build lacks one setter.
    for attr, value in (("repeat", bool(repeat)), ("interpolate", True)):
        try:
            setattr(texture, attr, value)
        except Exception:
            pass
    try:
        wrap_type = getattr(getattr(texture, "WrapType", None), "REPEAT" if bool(repeat) else "CLAMP_TO_BORDER", None)
        if wrap_type is not None:
            setattr(texture, "wrap", wrap_type)
        else:
            setattr(texture, "wrap", 1 if bool(repeat) else 3)
    except Exception:
        pass
    if border_color is not None:
        try:
            setattr(texture, "border_color", tuple(float(c) for c in border_color))
        except Exception:
            pass
    for method, value in (("SetRepeat", bool(repeat)), ("SetInterpolate", True), ("SetEdgeClamp", False)):
        try:
            if hasattr(texture, method):
                getattr(texture, method)(value)
        except Exception:
            pass
    for method in (("RepeatOn" if bool(repeat) else "RepeatOff"), "InterpolateOn", "EdgeClampOff"):
        try:
            if hasattr(texture, method):
                getattr(texture, method)()
        except Exception:
            pass
    try:
        # Old compatibility calls such as RepeatOff may force ClampToEdge.
        # Re-apply the modern wrap mode afterwards so non-repeated textures can
        # use a neutral ClampToBorder instead of stretching their last texel.
        wrap_type = getattr(getattr(texture, "WrapType", None), "REPEAT" if bool(repeat) else "CLAMP_TO_BORDER", None)
        setattr(texture, "wrap", wrap_type if wrap_type is not None else (1 if bool(repeat) else 3))
    except Exception:
        pass
    try:
        vtk_obj = getattr(texture, "GetTexture", lambda: None)()
        if vtk_obj is not None:
            if hasattr(vtk_obj, "SetRepeat"):
                vtk_obj.SetRepeat(bool(repeat))
            if hasattr(vtk_obj, "SetInterpolate"):
                vtk_obj.SetInterpolate(True)
            if hasattr(vtk_obj, "SetEdgeClamp"):
                vtk_obj.SetEdgeClamp(False)
            if hasattr(vtk_obj, "SetWrap"):
                try:
                    vtk_obj.SetWrap(1 if bool(repeat) else 3)
                except Exception:
                    pass
            if border_color is not None and hasattr(vtk_obj, "SetBorderColor"):
                try:
                    vtk_obj.SetBorderColor(*tuple(float(c) for c in border_color))
                except TypeError:
                    try:
                        vtk_obj.SetBorderColor(tuple(float(c) for c in border_color))
                    except Exception:
                        pass
            for method in (("RepeatOn" if bool(repeat) else "RepeatOff"), "InterpolateOn", "EdgeClampOff"):
                if hasattr(vtk_obj, method):
                    getattr(vtk_obj, method)()
            if hasattr(vtk_obj, "SetWrap"):
                try:
                    vtk_obj.SetWrap(1 if bool(repeat) else 3)
                except Exception:
                    pass
    except Exception:
        pass


def _strong_ref_texture(owner: Any, texture: Any) -> None:
    try:
        active = getattr(owner, "_active_pyvista_textures", None)
        if not isinstance(active, list):
            active = []
            owner._active_pyvista_textures = active
        if texture not in active:
            active.append(texture)
    except Exception:
        pass


def pyvista_texture_for_mesh(owner: Any, mesh: Any):
    try:
        if str(getattr(getattr(owner, "render_state", None), "display_mode", "wireframe")) != "material":
            return None
        uvs = getattr(mesh, "uvs", None)
        if uvs is None:
            return None
        path = texture_path_for_mesh(owner, mesh)
        if path is None:
            _owner_log(owner, f"[TEXTURE][WARN] mesh={getattr(mesh, 'name', '?')} has UVs but no valid texture path")
            return None
        import pyvista as pv

        repeat = texture_repeat_for_mesh(mesh)
        border_color = texture_border_color_for_mesh(owner, mesh)
        key = _texture_cache_key(path, repeat=repeat, border_color=border_color)
        cache = getattr(owner, "_pyvista_texture_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            try:
                owner._pyvista_texture_cache = cache
            except Exception:
                pass
        texture = cache.get(key)
        if texture is None:
            texture = _read_texture(owner, pv, path, repeat=repeat, border_color=border_color)
            cache[key] = texture
            _owner_log(owner, f"[TEXTURE] Loaded texture {path.name} repeat={repeat}")
        _configure_texture(texture, repeat=repeat, border_color=(None if repeat else border_color))
        _strong_ref_texture(owner, texture)
        return texture
    except Exception as exc:
        _owner_log(owner, f"[TEXTURE][ERROR] pyvista_texture_for_mesh failed: {exc}")
        return None


def _vtk_texture_object(texture: Any) -> Any:
    try:
        vtk_obj = getattr(texture, "GetTexture", lambda: None)()
        if vtk_obj is not None:
            return vtk_obj
    except Exception:
        pass
    return texture


def actor_has_texture(actor: Any) -> bool:
    """Return True when a VTK/PyVista actor currently owns a texture.

    VTK wrappers differ between versions: some expose ``GetTexture`` directly,
    while PyVista actors may only keep a Python-side reference after we attach
    the texture.  This helper intentionally accepts either signal.
    """

    try:
        if bool(getattr(actor, "_laserprog_has_texture", False)):
            return True
    except Exception:
        pass
    try:
        getter = getattr(actor, "GetTexture", None)
        if callable(getter) and getter() is not None:
            return True
    except Exception:
        pass
    return False


def configure_actor_for_texture_visibility(actor: Any) -> None:
    """Make bitmap textures visible instead of being shaded to black.

    The material renderer uses a directional light.  On vertical faces that face
    away from that light, VTK can multiply the texture by almost zero, making a
    correctly attached texture look like a black face.  Projected textures are
    editing decals, so they should be displayed unlit and white-tinted.
    """

    try:
        prop = actor.GetProperty() if hasattr(actor, "GetProperty") else getattr(actor, "prop", None)
    except Exception:
        prop = None
    if prop is None:
        return
    for method, args in (
        ("SetLighting", (False,)),
        ("SetColor", (1.0, 1.0, 1.0)),
        ("SetAmbient", (1.0,)),
        ("SetDiffuse", (1.0,)),
        ("SetSpecular", (0.0,)),
        ("SetMetallic", (0.0,)),
        ("SetRoughness", (1.0,)),
    ):
        try:
            if hasattr(prop, method):
                getattr(prop, method)(*args)
        except Exception:
            pass
    try:
        if hasattr(prop, "SetInterpolationToFlat"):
            prop.SetInterpolationToFlat()
    except Exception:
        pass


def apply_texture_to_actor(owner: Any, actor: Any, mesh: Any, texture: Any | None = None, *, reason: str = "") -> bool:
    """Force a texture back onto a VTK actor after style/display updates.

    On some PyVista/VTK builds the texture is visible for one frame, then a later
    selection/material refresh leaves the actor styled but untextured.  Reapplying
    the vtkTexture explicitly after every rebuild/style pass makes TEX previews
    stable and leaves a useful diagnostic line if the texture cannot be attached.
    """

    try:
        if actor is None or mesh is None:
            return False
        if texture is None:
            texture = pyvista_texture_for_mesh(owner, mesh)
        if texture is None:
            return False
        vtk_tex = _vtk_texture_object(texture)
        attached = False
        try:
            if hasattr(actor, "SetTexture"):
                actor.SetTexture(vtk_tex)
                attached = True
        except Exception as exc:
            _owner_log(owner, f"[TEXTURE][WARN] actor.SetTexture failed {reason}: {exc}")
        try:
            # PyVista actor wrappers often keep a Python attribute too; keeping it
            # here is harmless for raw vtkActor and helps prevent GC on wrappers.
            setattr(actor, "_laserprog_texture_ref", texture)
            setattr(actor, "_laserprog_has_texture", True)
        except Exception:
            pass
        if attached:
            configure_actor_for_texture_visibility(actor)
        _strong_ref_texture(owner, texture)
        try:
            mapper = actor.GetMapper() if hasattr(actor, "GetMapper") else None
            dataset = mapper.GetInput() if mapper is not None and hasattr(mapper, "GetInput") else None
            tcoords = dataset.GetPointData().GetTCoords() if dataset is not None and hasattr(dataset, "GetPointData") else None
            uv_count = int(tcoords.GetNumberOfTuples()) if tcoords is not None and hasattr(tcoords, "GetNumberOfTuples") else 0
        except Exception:
            uv_count = -1
        if attached:
            _owner_log(owner, f"[TEXTURE] Actor texture attached reason={reason or 'n/a'} mesh={getattr(mesh, 'name', '?')} uv_tuples={uv_count}")
        return bool(attached)
    except Exception as exc:
        _owner_log(owner, f"[TEXTURE][ERROR] apply_texture_to_actor failed {reason}: {exc}")
        return False


__all__ = ["texture_path_for_mesh", "texture_repeat_for_mesh", "texture_border_color_for_mesh", "pyvista_texture_for_mesh", "apply_texture_to_actor", "actor_has_texture", "configure_actor_for_texture_visibility"]
