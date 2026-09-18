# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math


@dataclass(frozen=True, slots=True)
class MaterialRenderSettings:
    """Global settings for Material render mode.

    The material renderer uses a deliberately small and stable VTK shadow-map
    pipeline:

    * one directional scene light, because PyVista's own examples use directed
      lights with ``enable_shadows()``;
    * one opaque thin receiver slab instead of a one-sided plane;
    * one enable/disable transition per material state signature, never a
      repeated toggle on every refresh.

    This keeps the result closer to a real render while avoiding the previous
    fragile contact-shadow decals and avoiding leaking render-pass state into
    Solid/Wireframe modes.
    """

    mode: str = "wireframe"
    light_intensity: float = 1.4
    ambient: float = 0.18
    specular: float = 0.55
    azimuth: float = -45.0
    elevation: float = 45.0
    shadows: bool = False
    # Kept in the dataclass for saved UI/state files, but the material renderer
    # no longer creates a ground receiver.
    # Shadow maps are now piece-only: meshes cast and receive shadows from
    # other meshes, with no visible floor/slab actor in the scene.
    floor_shadow: bool = False

    @property
    def material_mode(self) -> bool:
        return self.mode == "material"

    def light_vector(self) -> tuple[float, float, float]:
        az = math.radians(float(self.azimuth))
        el = math.radians(float(self.elevation))
        return (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))

    def light_signature(self) -> tuple[float, float, float, float, bool, bool]:
        return (
            round(float(self.light_intensity), 3),
            round(float(self.ambient), 3),
            round(float(self.specular), 3),
            round(float(self.azimuth), 2),
            bool(self.shadows),
            bool(self.floor_shadow),
        )


@dataclass(frozen=True, slots=True)
class MaterialFloorSpec:
    center: tuple[float, float, float]
    x_length: float
    y_length: float
    z_length: float
    top_z: float

    @property
    def signature(self) -> tuple[float, float, float, float, float, float]:
        return (
            round(float(self.center[0]), 3),
            round(float(self.center[1]), 3),
            round(float(self.center[2]), 3),
            round(float(self.x_length), 3),
            round(float(self.y_length), 3),
            round(float(self.z_length), 4),
        )


def _clamp(value: Any, lo: float, hi: float, fallback: float) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(fallback)
    return max(float(lo), min(float(hi), v))


def settings_from_state(state: Any) -> MaterialRenderSettings:
    if state is None:
        return MaterialRenderSettings()
    return MaterialRenderSettings(
        mode=str(getattr(state, "display_mode", "wireframe")),
        light_intensity=_clamp(getattr(state, "material_light_intensity", 1.4), 0.0, 4.0, 1.4),
        ambient=_clamp(getattr(state, "material_ambient", 0.18), 0.0, 1.0, 0.18),
        specular=_clamp(getattr(state, "material_specular", 0.55), 0.0, 1.0, 0.55),
        azimuth=_clamp(getattr(state, "material_light_azimuth", -45.0), -180.0, 180.0, -45.0),
        elevation=_clamp(getattr(state, "material_light_elevation", 45.0), 0.0, 89.0, 45.0),
        shadows=bool(getattr(state, "material_shadows", False)),
        floor_shadow=False,
    )


def renderer_actor_count(plotter: Any) -> int | str:
    try:
        renderer = getattr(plotter, "renderer", None)
        if renderer is None:
            return "none"
        props = renderer.GetViewProps() if hasattr(renderer, "GetViewProps") else None
        return int(props.GetNumberOfItems()) if props is not None and hasattr(props, "GetNumberOfItems") else "unknown"
    except Exception:
        return "error"


def material_floor_spec(bounds: tuple[float, float, float, float, float, float]) -> MaterialFloorSpec:
    """Return a robust opaque receiver slab for VTK shadow maps.

    A thin box is more reliable than a plane with shadow mapping because it is
    closed, opaque polygonal geometry.  This mirrors the PyVista shadow example
    pattern that adds a thin base mesh below the model.
    """
    try:
        x0, x1, y0, y1, z0, z1 = [float(v) for v in bounds]
    except Exception:
        x0, x1, y0, y1, z0, z1 = (-1.0, 1.0, -1.0, 1.0, -1.0, 1.0)
    width = max(x1 - x0, 1.0)
    depth = max(y1 - y0, 1.0)
    height = max(z1 - z0, 1.0)
    size = max(width, depth, height, 40.0)
    margin = max(size * 0.40, 20.0)
    x_len = max(width + margin, size * 1.35)
    y_len = max(depth + margin, size * 1.35)
    thickness = max(size * 0.012, 0.35)
    top_z = min(0.0, z0 - max(size * 0.002, 0.02))
    center = ((x0 + x1) * 0.5, (y0 + y1) * 0.5, top_z - thickness * 0.5)
    return MaterialFloorSpec(center=center, x_length=x_len, y_length=y_len, z_length=thickness, top_z=top_z)


# Saved-state helper name used by earlier material render code/tests.
def material_floor_z(bounds: tuple[float, float, float, float, float, float]) -> float:
    return material_floor_spec(bounds).top_z


def shadow_pass_signature(
    *,
    settings: MaterialRenderSettings,
    bounds: tuple[float, float, float, float, float, float],
    mesh_count: int,
) -> tuple[Any, ...]:
    return (
        "vtk_shadow_maps_piece_only_v5_floor_pulse",
        settings.light_signature(),
        tuple(round(float(v), 3) for v in bounds),
        int(mesh_count),
    )


def _basic_shadow_prime(plotter: Any, log=None) -> list[str]:
    """Low-level renderer invalidation used by the shadow warmup."""
    details: list[str] = []
    if plotter is None:
        return details
    renderer = getattr(plotter, "renderer", None)
    if renderer is None:
        return details
    try:
        if hasattr(renderer, "ResetCameraClippingRange"):
            renderer.ResetCameraClippingRange()
            details.append("clip")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN shadow prime ResetCameraClippingRange failed: {exc}")
    try:
        cam = renderer.GetActiveCamera() if hasattr(renderer, "GetActiveCamera") else None
        if cam is not None and hasattr(cam, "Modified"):
            cam.Modified()
            details.append("camera")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN shadow prime camera.Modified failed: {exc}")
    try:
        lights = renderer.GetLights() if hasattr(renderer, "GetLights") else None
        if lights is not None and hasattr(lights, "InitTraversal"):
            lights.InitTraversal()
            count = 0
            while True:
                light = lights.GetNextItem() if hasattr(lights, "GetNextItem") else None
                if light is None:
                    break
                if hasattr(light, "Modified"):
                    light.Modified()
                count += 1
            details.append(f"lights={count}")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN shadow prime light.Modified failed: {exc}")
    try:
        if hasattr(renderer, "SetUseShadows"):
            renderer.SetUseShadows(True)
            details.append("use_shadows")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN shadow prime SetUseShadows(True) failed: {exc}")
    try:
        if hasattr(renderer, "Modified"):
            renderer.Modified()
            details.append("renderer")
    except Exception:
        pass
    return details


def _add_shadow_warmup_receiver(plotter: Any, log=None, *, bounds: tuple[float, float, float, float, float, float] | None = None):
    """Add the same opaque slab the former user-visible floor used, for one pass only."""
    if plotter is None or bounds is None:
        return None
    temp_name = "material_shadow_warmup_receiver"
    try:
        # Remove any stale instance first.  This actor must never survive in the
        # final scene, but failed runs or interrupted refreshes can leave one.
        for target in (temp_name, getattr(plotter, "material_shadow_warmup_receiver", None)):
            if target is not None:
                try:
                    plotter.remove_actor(target, render=False)
                except Exception:
                    pass
    except Exception:
        pass
    try:
        import pyvista as pv
        spec = material_floor_spec(bounds)
        slab = pv.Cube(center=spec.center, x_length=spec.x_length, y_length=spec.y_length, z_length=spec.z_length)
        actor = plotter.add_mesh(
            slab,
            color="#D8DCE2",
            name=temp_name,
            pickable=False,
            lighting=True,
            show_edges=False,
            render=False,
        )
        try:
            actor.SetPickable(False)
        except Exception:
            pass
        try:
            prop = actor.GetProperty()
            if hasattr(prop, "SetInterpolationToPhong"):
                prop.SetInterpolationToPhong()
            if hasattr(prop, "SetAmbient"):
                prop.SetAmbient(0.30)
            if hasattr(prop, "SetDiffuse"):
                prop.SetDiffuse(0.78)
            if hasattr(prop, "SetSpecular"):
                prop.SetSpecular(0.06)
            if hasattr(prop, "SetOpacity"):
                prop.SetOpacity(1.0)
            if hasattr(prop, "SetEdgeVisibility"):
                prop.SetEdgeVisibility(False)
        except Exception:
            pass
        if callable(log):
            log("[MATERIAL_RENDER] shadow floor-pulse receiver added")
        return actor
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN shadow floor-pulse receiver add failed: {exc}")
        return None


def _remove_shadow_warmup_receiver(plotter: Any, actor: Any | None, log=None) -> None:
    if plotter is None:
        return
    removed = False
    for target in ("material_shadow_warmup_receiver", actor):
        if target is None:
            continue
        try:
            removed = bool(plotter.remove_actor(target, render=False)) or removed
        except Exception:
            pass
    if callable(log):
        log(f"[MATERIAL_RENDER] shadow floor-pulse receiver removed={removed}")


def _enable_vtk_shadows_once(plotter: Any, log=None) -> bool:
    """Enable VTK shadows once, without warmup side effects."""
    if plotter is None:
        return False
    enabled = False
    try:
        if hasattr(plotter, "enable_shadows"):
            plotter.enable_shadows()
            enabled = True
            if callable(log):
                log("[MATERIAL_RENDER] vtk shadows enabled via plotter.enable_shadows")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN plotter.enable_shadows failed: {exc}")
    if not enabled:
        try:
            renderer = getattr(plotter, "renderer", None)
            if renderer is not None and hasattr(renderer, "enable_shadows"):
                renderer.enable_shadows()
                enabled = True
                if callable(log):
                    log("[MATERIAL_RENDER] vtk shadows enabled via renderer.enable_shadows")
        except Exception as exc:
            if callable(log):
                log(f"[MATERIAL_RENDER] WARN renderer.enable_shadows failed: {exc}")
    try:
        renderer = getattr(plotter, "renderer", None)
        if renderer is not None and hasattr(renderer, "SetUseShadows"):
            renderer.SetUseShadows(True)
            enabled = True
            if callable(log):
                log("[MATERIAL_RENDER] vtk shadows enabled via renderer.SetUseShadows(True)")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN renderer.SetUseShadows(True) failed: {exc}")
    _basic_shadow_prime(plotter, log)
    return bool(enabled)


def prime_vtk_shadow_maps(plotter: Any, log=None, *, bounds: tuple[float, float, float, float, float, float] | None = None) -> bool:
    """Reproduce the manual floor ON -> OFF workaround without leaving a floor.

    The bug observed in the UI is not fixed by a simple renderer.Modified() call.
    The reliable manual sequence was:

    1. real shadows ON with a ground receiver present;
    2. render once;
    3. remove the receiver;
    4. rebuild the VTK shadow pass again;
    5. render the final piece-only scene.

    The important part is the *second* disable/enable after the receiver has been
    removed.  Earlier attempts added a temporary receiver while the pass was
    already enabled, then removed it without recreating the pass; that did not
    match the user-visible workaround and left textures/shadow maps in the same
    bad state.  This routine intentionally performs the two-pass pulse, but the
    receiver actor is removed before the final render, so no ground shadow layer
    remains in the final scene.
    """
    if plotter is None:
        return False
    details: list[str] = []
    final_enabled = False
    temp_actor = None
    try:
        # Pass A: build a classic PyVista-style shadow scene with an opaque
        # receiver.  This initializes VTK's shadow-map internals in the same way
        # the old Sol de rendu toggle did.  The pass is explicitly disabled and
        # re-enabled after adding the receiver; adding the receiver to an
        # already-enabled pass was the previous failed patch.
        try:
            disable_vtk_shadows(plotter, log)
            details.append("initial_disable")
        except Exception:
            pass
        temp_actor = _add_shadow_warmup_receiver(plotter, log, bounds=bounds)
        if temp_actor is not None:
            details.append("receiver_add")
        if _enable_vtk_shadows_once(plotter, log):
            details.append("pass_enable_with_receiver")
        if hasattr(plotter, "render"):
            plotter.render()
            details.append("receiver_render")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN shadow floor-pulse receiver render failed: {exc}")
    finally:
        # Pass B: remove the receiver, then force the shadow render pass to be
        # destroyed and rebuilt for the final actor list.  This mirrors the
        # working manual sequence: check floor, then uncheck floor.
        _remove_shadow_warmup_receiver(plotter, temp_actor, log)
        details.append("receiver_remove")
        try:
            disable_vtk_shadows(plotter, log)
            details.append("pass_disable_after_receiver")
        except Exception:
            pass
        try:
            final_enabled = bool(_enable_vtk_shadows_once(plotter, log))
            details.append("pass_reenable_piece_only" if final_enabled else "pass_reenable_piece_only_failed")
        except Exception as exc:
            if callable(log):
                log(f"[MATERIAL_RENDER] WARN shadow floor-pulse final enable failed: {exc}")
        try:
            _basic_shadow_prime(plotter, log)
            if hasattr(plotter, "render"):
                plotter.render()
                details.append("piece_only_render")
        except Exception as exc:
            if callable(log):
                log(f"[MATERIAL_RENDER] WARN shadow floor-pulse final render failed: {exc}")
    if callable(log):
        log(f"[MATERIAL_RENDER] vtk shadow maps floor-pulse piece-only enabled={final_enabled} details={','.join(details) or 'none'}")
    return bool(final_enabled)

def disable_vtk_shadows(plotter: Any, log=None) -> None:
    """Best-effort reset of the VTK/PyVista shadow-map state."""
    if plotter is None:
        return
    try:
        if hasattr(plotter, "disable_shadows"):
            plotter.disable_shadows()
            if callable(log):
                log("[MATERIAL_RENDER] vtk shadows disabled via plotter.disable_shadows")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN vtk disable_shadows failed: {exc}")
    try:
        renderer = getattr(plotter, "renderer", None)
        if renderer is not None and hasattr(renderer, "SetUseShadows"):
            renderer.SetUseShadows(False)
            if callable(log):
                log("[MATERIAL_RENDER] vtk shadows disabled via renderer.SetUseShadows(False)")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN renderer.SetUseShadows(False) failed: {exc}")
    try:
        renderer = getattr(plotter, "renderer", None)
        if renderer is not None and hasattr(renderer, "SetPass"):
            renderer.SetPass(None)
            if callable(log):
                log("[MATERIAL_RENDER] vtk render pass reset")
    except Exception as exc:
        if callable(log):
            log(f"[MATERIAL_RENDER] WARN renderer.SetPass(None) failed: {exc}")


# Import name used by earlier tests/controllers.
disable_shadows = disable_vtk_shadows


def enable_vtk_shadows(plotter: Any, log=None, *, bounds: tuple[float, float, float, float, float, float] | None = None) -> bool:
    """Enable VTK/PyVista shadow maps through the floor-pulse stabilizer.

    Do not call ``plotter.enable_shadows()`` directly here.  The observed bug is
    caused by enabling the shadow pass against the final actor list directly.
    The stable path is the old manual workaround encoded in
    ``prime_vtk_shadow_maps``: receiver present -> enable/render -> receiver
    removed -> disable/re-enable/render.  The final scene remains piece-only.
    """
    if plotter is None:
        return False
    return bool(prime_vtk_shadow_maps(plotter, log, bounds=bounds))
