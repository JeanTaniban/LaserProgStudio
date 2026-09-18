# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .display_modes import DisplayModeSpec, get_display_mode


def _parse_hex_color(value: str) -> tuple[float, float, float]:
    v = (value or "").strip()
    if v.startswith("#"):
        v = v[1:]
    if len(v) == 8:
        v = v[:6]
    if len(v) != 6:
        return (0.72, 0.72, 0.72)
    try:
        return (int(v[0:2], 16) / 255.0, int(v[2:4], 16) / 255.0, int(v[4:6], 16) / 255.0)
    except Exception:
        return (0.72, 0.72, 0.72)


@dataclass(frozen=True, slots=True)
class ActorStyle:
    representation: str = "surface"  # surface or wireframe
    show_edges: bool = True
    lighting: bool = False
    color: tuple[float, float, float] = (0.72, 0.72, 0.72)
    opacity: float = 1.0
    metallic: float = 0.0
    roughness: float = 0.5


def actor_style_for_mesh(mesh: Any, mode: str | DisplayModeSpec, *, show_edges: bool | None = None) -> ActorStyle:
    spec = get_display_mode(mode) if isinstance(mode, str) else mode
    material = getattr(mesh, "material", None)
    if spec.use_materials:
        # Material mode must not fall back to engraving-role colors, otherwise
        # red/green laser roles make it look identical to Solid mode. A mesh
        # without an explicit material receives the documented neutral default.
        if material is None or isinstance(material, dict):
            try:
                from ..domain.material import MeshMaterial
                source = material or {}
                material = MeshMaterial(
                    name=str(source.get("name", "Default")) if isinstance(source, dict) else "Default",
                    base_color=str(source.get("base_color", "#B8B8B8")) if isinstance(source, dict) else "#B8B8B8",
                    opacity=float(source.get("opacity", 1.0)) if isinstance(source, dict) else 1.0,
                    metallic=float(source.get("metallic", 0.0)) if isinstance(source, dict) else 0.0,
                    roughness=float(source.get("roughness", 0.5)) if isinstance(source, dict) else 0.5,
                )
            except Exception:
                material = None
    use_material = bool(spec.use_materials and material is not None)
    # Solid/wireframe mode keeps the historical engraving-role color. Material
    # mode switches to the visual material color and physical parameters.
    base_color = getattr(material, "base_color", None) if use_material else getattr(mesh, "color", "#B8B8B8")
    opacity = float(getattr(material, "opacity", 1.0) if use_material else 1.0)
    metallic = float(getattr(material, "metallic", 0.0) if use_material else 0.0)
    roughness = float(getattr(material, "roughness", 0.5) if use_material else 0.5)
    return ActorStyle(
        representation=getattr(spec, "representation", "surface"),
        show_edges=bool(spec.default_show_edges if show_edges is None else show_edges),
        lighting=bool(spec.use_lighting),
        color=_parse_hex_color(base_color or "#B8B8B8"),
        opacity=max(0.0, min(1.0, opacity)),
        metallic=max(0.0, min(1.0, metallic)),
        roughness=max(0.0, min(1.0, roughness)),
    )


def apply_actor_style(actor: Any, style: ActorStyle) -> None:
    prop = actor.GetProperty() if hasattr(actor, "GetProperty") else getattr(actor, "prop", None)
    if prop is None:
        return
    if style.representation == "wireframe" and hasattr(prop, "SetRepresentationToWireframe"):
        prop.SetRepresentationToWireframe()
    elif hasattr(prop, "SetRepresentationToSurface"):
        prop.SetRepresentationToSurface()
    if hasattr(prop, "SetEdgeVisibility"):
        prop.SetEdgeVisibility(bool(style.show_edges))
    if hasattr(prop, "SetLighting"):
        prop.SetLighting(bool(style.lighting))
    if hasattr(prop, "SetColor"):
        prop.SetColor(*style.color)
    if hasattr(prop, "SetOpacity"):
        prop.SetOpacity(style.opacity)
    if hasattr(prop, "SetMetallic"):
        prop.SetMetallic(style.metallic)
    if hasattr(prop, "SetRoughness"):
        prop.SetRoughness(style.roughness)
