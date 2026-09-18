# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..domain.material import EngravingSettings, MeshMaterial

OUTLINE_ROLE = "outline"
OUTLINE_COLOR = "#00C853"
FILL_ROLE = "fill"
FILL_COLOR = "#E53935"
IGNORE_ROLE = "ignore"
NEUTRAL_COLOR = "#B8B8B8"


def role_from_color_hint(color: str | None) -> str | None:
    try:
        c = str(color or "").strip()
        if c.startswith("#"):
            c = c[1:]
        if len(c) >= 6:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            if g > r and g > b:
                return OUTLINE_ROLE
            if r > g and r > b:
                return FILL_ROLE
    except Exception:
        pass
    return None


def role_from_color_hint_or_ignore(color: str | None) -> str:
    """Return the UI/export role represented by a color-coded mesh."""

    return role_from_color_hint(color) or IGNORE_ROLE


def engraving_role_color(role: str | None) -> str:
    key = str(role or IGNORE_ROLE).strip().lower()
    if key == OUTLINE_ROLE:
        return OUTLINE_COLOR
    if key == FILL_ROLE:
        return FILL_COLOR
    return NEUTRAL_COLOR


def apply_engraving_role(mesh: Any, role: str, *, layer: str | None = None, enabled: bool = True) -> Any:
    """Apply an engraving role to a mesh copy without depending on Qt controllers."""

    key = str(role or IGNORE_ROLE).strip().lower()
    if key not in {OUTLINE_ROLE, FILL_ROLE, IGNORE_ROLE}:
        key = IGNORE_ROLE
    resolved_layer = str(layer or ("ignore" if key == IGNORE_ROLE else "engrave"))
    color = engraving_role_color(key)
    try:
        mesh.color = color
    except Exception:
        pass
    try:
        mesh.engraving = EngravingSettings(role=key, layer=resolved_layer, enabled=bool(enabled))
    except Exception:
        try:
            mesh.engraving = {"role": key, "layer": resolved_layer, "enabled": bool(enabled)}
        except Exception:
            pass
    material = getattr(mesh, "material", None)
    if isinstance(material, dict):
        material["base_color"] = color
        material.setdefault("name", key.title())
        try:
            mesh.material = material
        except Exception:
            pass
    elif material is not None:
        try:
            material.base_color = color
        except Exception:
            pass
    else:
        try:
            mesh.material = MeshMaterial(name=key.title(), base_color=color)
        except Exception:
            pass
    return mesh


def mesh_has_explicit_engraving_role(mesh: Any) -> bool:
    engraving = getattr(mesh, "engraving", None)
    role = str(getattr(engraving, "role", "") or "").strip().lower() if engraving is not None else ""
    if role in {OUTLINE_ROLE, FILL_ROLE}:
        return True
    # Imported parts may store the role only through color.
    return role_from_color_hint(getattr(mesh, "color", None)) in {OUTLINE_ROLE, FILL_ROLE}


def apply_outline_role(mesh: Any) -> None:
    try:
        mesh.color = OUTLINE_COLOR
    except Exception:
        pass
    engraving = getattr(mesh, "engraving", None)
    if isinstance(engraving, dict):
        engraving.update({"role": OUTLINE_ROLE, "layer": "engrave", "enabled": True})
        try:
            mesh.engraving = engraving
        except Exception:
            pass
    elif engraving is not None:
        try:
            engraving.role = OUTLINE_ROLE
            engraving.layer = "engrave"
            engraving.enabled = True
        except Exception:
            try:
                mesh.engraving = EngravingSettings(role=OUTLINE_ROLE, layer="engrave", enabled=True)
            except Exception:
                pass
    else:
        try:
            mesh.engraving = EngravingSettings(role=OUTLINE_ROLE, layer="engrave", enabled=True)
        except Exception:
            pass
    material = getattr(mesh, "material", None)
    if isinstance(material, dict):
        material["base_color"] = OUTLINE_COLOR
        try:
            mesh.material = material
        except Exception:
            pass
    elif material is not None:
        try:
            material.base_color = OUTLINE_COLOR
        except Exception:
            pass
    else:
        try:
            mesh.material = MeshMaterial(name="Outline", base_color=OUTLINE_COLOR)
        except Exception:
            pass


def apply_default_outline_to_unassigned(meshes: list[Any]) -> int:
    """Set outline/green role on meshes that do not already have a role."""

    changed = 0
    for mesh in meshes:
        if mesh_has_explicit_engraving_role(mesh):
            continue
        apply_outline_role(mesh)
        changed += 1
    return changed
