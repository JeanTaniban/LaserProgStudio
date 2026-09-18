# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from ..rendering.textures import actor_has_texture, configure_actor_for_texture_visibility, apply_texture_to_actor
from ..rendering.material_scene import (
    disable_shadows,
    enable_vtk_shadows,
    renderer_actor_count,
    settings_from_state,
    shadow_pass_signature,
)


def _safe_hex_color(value: str, fallback: str = "#B8B8B8") -> str:
    raw = str(value or "").strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) == 8:
        raw = raw[:6]
    if len(raw) != 6:
        return fallback
    try:
        int(raw, 16)
    except Exception:
        return fallback
    return "#" + raw.upper()


class MaterialToolLayer:
    """Simple material painter used by the global Material render mode."""

    def _current_material_from_ui(self):
        from ..domain.material import MeshMaterial
        name = "Material"
        color = "#B8B8B8"
        opacity = 1.0
        metallic = 0.0
        roughness = 0.55
        try:
            name = str(self.material_name.text() or "Material").strip() or "Material"
        except Exception:
            pass
        try:
            color = _safe_hex_color(self.material_color.text(), "#B8B8B8")
        except Exception:
            pass
        for attr, fallback in (("material_opacity", 1.0), ("material_metallic", 0.0), ("material_roughness", 0.55)):
            try:
                value = float(getattr(self, attr).value())
            except Exception:
                value = fallback
            if attr == "material_opacity":
                opacity = max(0.05, min(1.0, value))
            elif attr == "material_metallic":
                metallic = max(0.0, min(1.0, value))
            elif attr == "material_roughness":
                roughness = max(0.0, min(1.0, value))
        return MeshMaterial(name=name, base_color=color, opacity=opacity, metallic=metallic, roughness=roughness)

    def _on_material_params_changed(self, *_args) -> None:
        try:
            self._sync_material_light_settings(render=False)
            if getattr(self, "active_tool", self.TOOL_NONE) == self.TOOL_MATERIAL and self.has_preview():
                # Re-apply parameters to the currently selected preview objects, not every mesh.
                selected = self._selected_transform_indices()
                if selected:
                    self.apply_material_to_indices(selected)
                else:
                    self.refresh_actor_styles(render=True)
        except Exception:
            log_exception("material_params_changed")

    def _on_material_render_params_changed(self, *_args) -> None:
        try:
            self._sync_material_light_settings(render=False)
            self._sync_material_render_controls_visibility()
            self.ui_log(
                "[MATERIAL_RENDER] ui changed "
                f"mode={getattr(getattr(self, 'render_state', None), 'display_mode', 'none')} "
                f"shadows={getattr(getattr(self, 'render_state', None), 'material_shadows', None)} "
                f"floor=False"
            )
            self.refresh_actor_styles(render=False)
            self._sync_material_scene_rendering(render=True)
        except Exception:
            log_exception("material_render_params_changed")

    def _sync_material_render_controls_visibility(self) -> None:
        try:
            state = getattr(self, "render_state", None)
            mode = str(getattr(state, "display_mode", "wireframe")) if state is not None else "wireframe"
            box = getattr(self, "material_render_box", None)
            if box is not None:
                box.setVisible(mode == "material")
        except Exception:
            pass

    def _sync_material_light_settings(self, *, render: bool = True) -> None:
        try:
            state = getattr(self, "render_state", None)
            if state is None:
                return

            def _value(names, fallback):
                for name in names:
                    widget = getattr(self, name, None)
                    if widget is not None and hasattr(widget, "value"):
                        try:
                            return float(widget.value())
                        except Exception:
                            pass
                return float(getattr(state, names[0], fallback) if isinstance(names, tuple) else fallback)

            state.material_light_intensity = max(0.0, min(4.0, _value(("material_render_light_intensity", "material_light_intensity"), 1.4)))
            state.material_ambient = max(0.0, min(1.0, _value(("material_render_ambient", "material_ambient"), 0.18)))
            state.material_specular = max(0.0, min(1.0, _value(("material_render_specular", "material_specular"), 0.55)))
            state.material_light_azimuth = max(-180.0, min(180.0, _value(("material_render_azimuth",), -45.0)))
            state.material_light_elevation = max(0.0, min(90.0, _value(("material_render_elevation",), 45.0)))
            # Interactive editor shadows are disabled on purpose.  Real shadows
            # now live only in the dedicated final render window.
            state.material_shadows = False
            shadows = getattr(self, "material_render_shadows", None)
            if shadows is not None and hasattr(shadows, "blockSignals"):
                try:
                    shadows.blockSignals(True)
                    shadows.setChecked(False)
                finally:
                    shadows.blockSignals(False)
            # Ground receiver shadows were removed. Keep this persisted state
            # pinned to False so saved sessions cannot recreate the floor.
            state.material_floor_shadow = False
            if render:
                self.refresh_actor_styles(render=True)
        except Exception:
            log_exception("sync_material_light_settings")

    def _apply_material_lighting_to_actor(self, actor) -> None:
        try:
            state = getattr(self, "render_state", None)
            mode = str(getattr(state, "display_mode", "wireframe")) if state is not None else "wireframe"
            prop = actor.GetProperty() if hasattr(actor, "GetProperty") else None
            if prop is None:
                return
            if actor_has_texture(actor):
                configure_actor_for_texture_visibility(actor)
                return
            if mode != "material":
                try:
                    if hasattr(prop, "SetInterpolationToPhong"):
                        prop.SetInterpolationToPhong()
                    if hasattr(prop, "SetAmbient"):
                        prop.SetAmbient(0.0)
                    if hasattr(prop, "SetDiffuse"):
                        prop.SetDiffuse(1.0)
                    if hasattr(prop, "SetSpecular"):
                        prop.SetSpecular(0.0)
                    if hasattr(prop, "SetMetallic"):
                        prop.SetMetallic(0.0)
                    if hasattr(prop, "SetRoughness"):
                        prop.SetRoughness(0.5)
                except Exception:
                    pass
                return

            ambient = max(0.0, min(1.0, float(getattr(state, "material_ambient", 0.18))))
            specular = max(0.0, min(1.0, float(getattr(state, "material_specular", 0.55))))
            shadows = bool(getattr(state, "material_shadows", False))
            metallic = float(getattr(prop, "GetMetallic", lambda: 0.0)())
            roughness = float(getattr(prop, "GetRoughness", lambda: 0.45)())

            # VTK shadow maps are reliable with the classic Phong path.  PBR is
            # kept for shadowless material preview, but true shadows switch to a
            # Phong approximation of metal/roughness that works with shadows.
            if shadows:
                if hasattr(prop, "SetInterpolationToPhong"):
                    prop.SetInterpolationToPhong()
                if hasattr(prop, "SetAmbient"):
                    prop.SetAmbient(min(ambient, 0.35))
                if hasattr(prop, "SetDiffuse"):
                    prop.SetDiffuse(max(0.22, 0.92 - metallic * 0.35 - ambient * 0.25))
                if hasattr(prop, "SetSpecular"):
                    prop.SetSpecular(max(specular, min(1.0, 0.35 + metallic * 0.45)))
                if hasattr(prop, "SetSpecularPower"):
                    prop.SetSpecularPower(25.0 + 140.0 * (1.0 - max(0.0, min(1.0, roughness))))
                return

            if hasattr(prop, "SetInterpolationToPBR"):
                prop.SetInterpolationToPBR()
            elif hasattr(prop, "SetInterpolationToPhong"):
                prop.SetInterpolationToPhong()
            if hasattr(prop, "SetAmbient"):
                prop.SetAmbient(ambient)
            if hasattr(prop, "SetDiffuse"):
                prop.SetDiffuse(max(0.2, min(1.0, 1.0 - ambient * 0.4)))
            if hasattr(prop, "SetSpecular"):
                prop.SetSpecular(specular)
            if hasattr(prop, "SetSpecularPower"):
                prop.SetSpecularPower(20.0 + 110.0 * (1.0 - max(0.0, min(1.0, roughness))))
        except Exception:
            pass

    def _material_light_vector(self) -> tuple[float, float, float]:
        try:
            state = getattr(self, "render_state", None)
            az = math.radians(float(getattr(state, "material_light_azimuth", -45.0)))
            el = math.radians(float(getattr(state, "material_light_elevation", 45.0)))
            return (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
        except Exception:
            return (0.55, -0.55, 0.65)

    def _remove_material_floor_actor(self, *, reason: str = "cleanup") -> None:
        """Remove the optional material render floor.

        The floor is a normal actor owned by material mode.  It must never leak
        into Solid/Wireframe.  We remove by stable name and by handle because
        PyVista versions differ in what remove_actor returns for named actors.
        """
        plotter = getattr(self, "plotter", None)
        before = renderer_actor_count(plotter)
        actor = getattr(self, "material_floor_actor", None)
        removed = False
        if plotter is not None:
            for target in ("material_render_floor", "material_shadow_floor", "material_shadow_warmup_receiver", actor):
                if target is None:
                    continue
                try:
                    result = plotter.remove_actor(target, render=False)
                    removed = bool(result) or removed
                except Exception as exc:
                    try:
                        self.ui_log(f"[MATERIAL_RENDER] floor remove target={type(target).__name__} failed: {exc}")
                    except Exception:
                        pass
        self.material_floor_actor = None
        self._material_floor_signature = None
        after = renderer_actor_count(plotter)
        try:
            self.ui_log(f"[MATERIAL_RENDER] floor cleanup reason={reason} removed={removed} props={before}->{after}")
        except Exception:
            pass

    def _remove_material_shadow_actors(self, *, reason: str = "cleanup") -> None:
        """Remove stale fake shadow actors created by older material previews."""
        plotter = getattr(self, "plotter", None)
        before = renderer_actor_count(plotter)
        actors = getattr(self, "material_shadow_actors", None) or {}
        removed = 0
        if plotter is not None:
            names = {f"material_contact_shadow_{i}" for i in range(max(16, len(actors) + 8))}
            names.update(str(name) for name in actors.keys())
            for target in list(names) + list(actors.values()):
                if target is None:
                    continue
                try:
                    result = plotter.remove_actor(target, render=False)
                    if result:
                        removed += 1
                except Exception:
                    pass
        self.material_shadow_actors = {}
        try:
            self.ui_log(f"[MATERIAL_RENDER] stale shadow actors cleanup reason={reason} removed={removed} props={before}->{renderer_actor_count(plotter)}")
        except Exception:
            pass

    def _disable_material_shadow_pass(self, *, reason: str = "cleanup") -> None:
        plotter = getattr(self, "plotter", None)
        before = renderer_actor_count(plotter)
        try:
            disable_shadows(plotter, getattr(self, "ui_log", None))
        finally:
            self._material_shadow_signature = None
            self._material_shadow_pass_enabled = False
        try:
            self.ui_log(f"[MATERIAL_RENDER] real shadows disabled reason={reason} props={before}->{renderer_actor_count(plotter)}")
        except Exception:
            pass

    def _enable_material_shadow_pass(self, signature: tuple, *, bounds=None) -> None:
        plotter = getattr(self, "plotter", None)
        if plotter is None:
            return
        if getattr(self, "_material_shadow_pass_enabled", False) and getattr(self, "_material_shadow_signature", None) == signature:
            try:
                self.ui_log(f"[MATERIAL_RENDER] real shadows unchanged signature={signature}")
            except Exception:
                pass
            return
        # Rebuild the pass only when the signature changes. This avoids the
        # old repeated enable/disable loop that poisoned the renderer state.
        self._disable_material_shadow_pass(reason="rebuild real shadow pass")
        enabled = enable_vtk_shadows(plotter, getattr(self, "ui_log", None), bounds=bounds)
        self._material_shadow_pass_enabled = bool(enabled)
        self._material_shadow_signature = signature if enabled else None
        try:
            self.ui_log(f"[MATERIAL_RENDER] real shadows enabled={enabled} signature={signature} props={renderer_actor_count(plotter)}")
        except Exception:
            pass

    def _restore_textured_actors_after_shadow_sync(self, *, reason: str = "shadow-sync") -> None:
        """Re-apply texture state after VTK shadow-pass changes.

        Toggling the retired render floor accidentally caused a full style/texture
        refresh after VTK rebuilt its shadow maps.  Without that final texture
        pass, decals can look black, unlit, or stale even though the texture is
        technically still attached.  Keep the final scene piece-only, but finish
        every shadow sync by putting textured actors back into the known-good
        unlit decal state.
        """
        try:
            meshes = list(self.current_meshes())
            restored = 0
            for idx, actor in list((getattr(self, "actors_by_index", {}) or {}).items()):
                try:
                    i = int(idx)
                except Exception:
                    continue
                if not (0 <= i < len(meshes)):
                    continue
                mesh = meshes[i]
                if apply_texture_to_actor(self, actor, mesh, reason=reason):
                    restored += 1
                    configure_actor_for_texture_visibility(actor)
                else:
                    # If the actor already has a texture but the asset lookup did
                    # not need to run, still force the visibility-safe properties.
                    if actor_has_texture(actor):
                        configure_actor_for_texture_visibility(actor)
                        restored += 1
            try:
                self.ui_log(f"[MATERIAL_RENDER] textures restored after {reason} count={restored}")
            except Exception:
                pass
        except Exception:
            log_exception("restore_textured_actors_after_shadow_sync")

    def _sync_material_real_shadows(self, settings=None, *, bounds=None) -> None:
        try:
            state = getattr(self, "render_state", None)
            settings = settings or settings_from_state(state)
            if state is None or not settings.material_mode or not settings.shadows:
                self._disable_material_shadow_pass(reason="shadow toggle off/non-material")
                return
            meshes = list(self.current_meshes())
            b = bounds or scene_bounds(meshes)
            signature = shadow_pass_signature(settings=settings, bounds=b, mesh_count=len(meshes))
            self._enable_material_shadow_pass(signature, bounds=b)
        except Exception:
            log_exception("sync_material_real_shadows")

    def _sync_material_scene_rendering(self, *, render: bool = False) -> None:
        """Synchronise the real Material render pipeline.

        State machine rules:
        1. Solid/Wireframe: remove material-only actors, disable VTK shadow maps,
           and restore automatic/default lighting.
        2. Material: create/update the optional opaque receiver slab, install a
           single directional key light, apply actor lighting for the shadow path,
           then enable/disable the VTK shadow pass only when its signature changed.
        3. The shadow pass is never toggled repeatedly during normal refreshes.
        """
        if getattr(self, "_material_scene_syncing", False):
            return
        self._material_scene_syncing = True
        try:
            self._sync_material_light_settings(render=False)
            self._sync_material_render_controls_visibility()
            state = getattr(self, "render_state", None)
            settings = settings_from_state(state)
            plotter = getattr(self, "plotter", None)
            renderer = getattr(plotter, "renderer", None) if plotter is not None else None
            before = renderer_actor_count(plotter)
            try:
                self.ui_log(
                    "[MATERIAL_RENDER] sync begin "
                    f"mode={settings.mode} intensity={settings.light_intensity:g} ambient={settings.ambient:g} "
                    f"specular={settings.specular:g} azimuth={settings.azimuth:g} elevation={settings.elevation:g} "
                    f"shadows={settings.shadows} floor=False props={before} engine=vtk_shadow_maps_piece_only"
                )
            except Exception:
                pass

            if renderer is None or plotter is None:
                try:
                    self.ui_log("[MATERIAL_RENDER] sync skipped: no renderer/plotter")
                except Exception:
                    pass
                return

            if not settings.material_mode:
                self._remove_material_shadow_actors(reason=f"leave {settings.mode}")
                self._disable_material_shadow_pass(reason=f"leave {settings.mode}")
                self._remove_material_floor_actor(reason=f"leave {settings.mode}")
                try:
                    renderer.AutomaticLightCreationOn()
                except Exception as exc:
                    try:
                        self.ui_log(f"[MATERIAL_RENDER] WARN AutomaticLightCreationOn failed: {exc}")
                    except Exception:
                        pass
                for attr in ("_material_key_light", "_material_fill_light"):
                    old = getattr(self, attr, None)
                    if old is not None:
                        try:
                            renderer.RemoveLight(old)
                        except Exception:
                            pass
                    setattr(self, attr, None)
                try:
                    self.ui_log(f"[MATERIAL_RENDER] sync end non-material props={renderer_actor_count(plotter)}")
                except Exception:
                    pass
                if render:
                    plotter.render()
                return

            bounds = scene_bounds(self.current_meshes())
            self._remove_material_shadow_actors(reason="stale shadow cleanup before real shadows")

            # Piece-only shadow maps: no visible floor/slab receiver.
            # The previous receiver slab accidentally fixed stale VTK shadow-map
            # matrices by forcing a renderer rebuild.  That rebuild is now done
            # by a temporary hidden warmup receiver in prime_vtk_shadow_maps(), so no floor remains visible.
            self._remove_material_floor_actor(reason="piece-only shadows: floor disabled")

            try:
                renderer.AutomaticLightCreationOff()
            except Exception as exc:
                try:
                    self.ui_log(f"[MATERIAL_RENDER] WARN AutomaticLightCreationOff failed: {exc}")
                except Exception:
                    pass
            try:
                renderer.RemoveAllLights()
            except Exception as exc:
                try:
                    self.ui_log(f"[MATERIAL_RENDER] WARN RemoveAllLights failed: {exc}")
                except Exception:
                    pass
            self._material_key_light = None
            self._material_fill_light = None

            try:
                import pyvista as pv
                key = pv.Light()
                key.set_direction_angle(float(settings.elevation), float(settings.azimuth))
                key.intensity = float(settings.light_intensity)
                key.diffuse_color = (1.0, 0.98, 0.94)
                key.specular_color = (1.0, 1.0, 1.0)
                try:
                    key.shadow_attenuation = 1.0
                except Exception:
                    pass
                plotter.add_light(key)
                self._material_key_light = key
                self.ui_log(
                    "[MATERIAL_RENDER] directional key light applied "
                    f"elev={settings.elevation:g} azim={settings.azimuth:g} intensity={settings.light_intensity:g}"
                )
            except Exception:
                # Fallback for unusual environments: use vtkLight directly.
                try:
                    import vtk
                    c = ((bounds[0] + bounds[1]) * 0.5, (bounds[2] + bounds[3]) * 0.5, (bounds[4] + bounds[5]) * 0.5)
                    d = max(bounds_size(bounds), 60.0) * 2.5
                    vx, vy, vz = settings.light_vector()
                    key = vtk.vtkLight()
                    key.SetLightTypeToSceneLight()
                    key.SetPosition(c[0] + vx * d, c[1] + vy * d, c[2] + vz * d)
                    key.SetFocalPoint(c[0], c[1], c[2])
                    key.SetIntensity(settings.light_intensity)
                    key.SetColor(1.0, 0.98, 0.94)
                    renderer.AddLight(key)
                    self._material_key_light = key
                    self.ui_log("[MATERIAL_RENDER] vtk fallback key light applied")
                except Exception:
                    log_exception("material_scene_lights")

            # Material actors must be refreshed after the shadow flag changed so
            # they switch between PBR preview and Phong shadow-path style.
            for actor in list((getattr(self, "actors_by_index", {}) or {}).values()):
                self._apply_material_lighting_to_actor(actor)

            if settings.shadows:
                self._sync_material_real_shadows(settings, bounds=bounds)
                self._restore_textured_actors_after_shadow_sync(reason="shadow-pass-piece-only")
            else:
                self._disable_material_shadow_pass(reason="shadow toggle off")
                self._restore_textured_actors_after_shadow_sync(reason="shadow-off-material")

            try:
                self.ui_log(f"[MATERIAL_RENDER] sync end material props={renderer_actor_count(plotter)} engine=vtk_shadow_maps_piece_only")
            except Exception:
                pass
            if render:
                plotter.render()
        except Exception:
            log_exception("sync_material_scene_rendering")
        finally:
            self._material_scene_syncing = False

    def apply_material_to_indices(self, indices: list[int]) -> None:
        try:
            indices = sorted({int(i) for i in indices})
            base_meshes = [copy.deepcopy(m) for m in self.current_meshes()]
            if not base_meshes:
                return
            material = self._current_material_from_ui()
            changed: list[int] = []
            for idx in indices:
                if 0 <= idx < len(base_meshes):
                    base_meshes[idx].material = copy.deepcopy(material)
                    changed.append(idx)
            if not changed:
                return
            self.selected_indices = changed
            self.active_index = changed[-1]
            self._clear_gizmo_interaction(clear_highlight=True)
            self.set_preview_meshes(base_meshes, f"Material preview {changed}")
            self._sync_material_light_settings(render=False)
            try:
                self.display_mode_combo.setCurrentIndex(self.display_mode_combo.findData("material"))
            except Exception:
                pass
            if hasattr(self, "material_report"):
                self.material_report.setText(
                    f"Material preview: {material.name} {material.base_color}\n"
                    f"Parts: {changed}\nApply keeps it, Cancel discards it."
                )
            self.ui_log(f"[MATERIAL] Preview indices={changed} color={material.base_color} opacity={material.opacity:g} metallic={material.metallic:g} roughness={material.roughness:g}")
        except Exception:
            log_exception("apply_material_to_indices")

    def apply_material_to_index(self, idx: int) -> None:
        try:
            from ..tooling.ids import TOOL_MATERIAL
            from ..tooling.registry import get_studio_tool

            if getattr(self, "active_tool", None) == TOOL_MATERIAL:
                tool = get_studio_tool(TOOL_MATERIAL)
                context = getattr(self, "app_context", None) or getattr(self, "context", None)
                if tool is not None and hasattr(tool, "apply_index") and context is not None:
                    tool.apply_index(context, int(idx))
                    return
        except Exception:
            pass
        self.apply_material_to_indices([int(idx)])

    def apply_material_to_selected(self) -> None:
        indices = self._selected_transform_indices()
        if not indices:
            self.ui_log("[MATERIAL] No selected part")
            if hasattr(self, "material_report"):
                self.material_report.setText("Select at least one part, or click a part.")
            return
        self.apply_material_to_indices(indices)

    def apply_material_to_all(self) -> None:
        try:
            meshes = self.current_meshes()
            self.apply_material_to_indices(list(range(len(meshes))))
        except Exception:
            log_exception("apply_material_to_all")
