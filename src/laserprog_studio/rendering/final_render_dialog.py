from __future__ import annotations

import math
from types import SimpleNamespace

from .._window_deps import *
from ..mesh_ops import scene_bounds, workmesh_to_polydata
from .textures import pyvista_texture_for_mesh, apply_texture_to_actor, configure_actor_for_texture_visibility
from .material_scene import enable_vtk_shadows


class RenderPreviewDialog(QDialog):
    """Standalone square render window, decoupled from the editor viewport."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Final render")
        self.resize(1040, 1120)
        self.setMinimumSize(920, 980)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Separate square render")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        self.info_label = QLabel("")
        self.info_label.setObjectName("SubTitle")
        header.addWidget(self.info_label)
        root.addLayout(header)

        from pyvistaqt import QtInteractor
        self.plotter = QtInteractor(self, auto_update=False)
        self.plotter.setMinimumSize(900, 900)
        self.plotter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        try:
            self.plotter.ren_win.SetMultiSamples(0)
        except Exception:
            pass
        try:
            self.plotter.enable_anti_aliasing("none")
        except Exception:
            pass
        try:
            self.plotter.set_background("#F2F2F2")
        except Exception:
            pass
        root.addWidget(self.plotter, 1, alignment=Qt.AlignCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.refresh_button = QPushButton("Refresh")
        buttons.addButton(self.refresh_button, QDialogButtonBox.ActionRole)
        buttons.rejected.connect(self.close)
        self.refresh_button.clicked.connect(self.refresh_scene)
        root.addWidget(buttons)

        QTimer.singleShot(0, self.refresh_scene)

    def closeEvent(self, event):
        try:
            self.plotter.close()
        except Exception:
            pass
        super().closeEvent(event)

    def _render_settings(self):
        state = getattr(self.owner, "render_state", None)
        return SimpleNamespace(
            material_light_intensity=float(getattr(state, "material_light_intensity", 1.4)),
            material_ambient=float(getattr(state, "material_ambient", 0.18)),
            material_specular=float(getattr(state, "material_specular", 0.55)),
            material_light_azimuth=float(getattr(state, "material_light_azimuth", -45.0)),
            material_light_elevation=float(getattr(state, "material_light_elevation", 45.0)),
        )

    def _apply_material_style(self, actor) -> None:
        try:
            if actor.GetTexture() is not None:
                configure_actor_for_texture_visibility(actor)
                return
        except Exception:
            pass
        try:
            prop = actor.GetProperty()
        except Exception:
            prop = None
        if prop is None:
            return
        state = self._render_settings()
        ambient = max(0.0, min(1.0, float(state.material_ambient)))
        specular = max(0.0, min(1.0, float(state.material_specular)))
        try:
            if hasattr(prop, "SetInterpolationToPhong"):
                prop.SetInterpolationToPhong()
            if hasattr(prop, "SetAmbient"):
                prop.SetAmbient(min(ambient, 0.35))
            if hasattr(prop, "SetDiffuse"):
                prop.SetDiffuse(max(0.22, 0.92 - ambient * 0.25))
            if hasattr(prop, "SetSpecular"):
                prop.SetSpecular(max(specular, 0.38))
            if hasattr(prop, "SetSpecularPower"):
                prop.SetSpecularPower(55.0)
            if hasattr(prop, "SetEdgeVisibility"):
                prop.SetEdgeVisibility(False)
        except Exception:
            pass

    def _camera_pose(self):
        owner = self.owner
        pose = owner._render_camera_pose_from_scene()
        if pose:
            return pose, "camera object"
        # Read the previous non-hierarchy camera state when present.
        state = getattr(owner, "render_camera_state", None)
        if state:
            return state, "previous render camera"
        pose = owner._editor_camera_pose_snapshot()
        return pose, "editor camera"

    def refresh_scene(self) -> None:
        owner = self.owner
        try:
            self.plotter.clear()
        except Exception:
            pass

        all_meshes = list(owner.current_meshes())
        render_meshes = [m for m in all_meshes if not owner._is_scene_helper_mesh(m)]
        if not render_meshes:
            self.info_label.setText("No object to render")
            try:
                self.plotter.render()
            except Exception:
                pass
            return

        for i, mesh in enumerate(render_meshes):
            try:
                poly = workmesh_to_polydata(mesh)
                texture = pyvista_texture_for_mesh(owner, mesh)
                kwargs = {"show_edges": False, "pickable": False, "lighting": True, "name": f"render_mesh_{i}"}
                if texture is not None:
                    actor = self.plotter.add_mesh(poly, texture=texture, **kwargs)
                    apply_texture_to_actor(owner, actor, mesh, texture, reason="final_render")
                else:
                    color = getattr(getattr(mesh, "material", None), "base_color", None) or getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"
                    actor = self.plotter.add_mesh(poly, color=color, **kwargs)
                self._apply_material_style(actor)
            except Exception:
                log_exception("final_render_add_mesh")

        try:
            ren = self.plotter.renderer
            ren.AutomaticLightCreationOff()
            ren.RemoveAllLights()
        except Exception:
            pass

        try:
            import pyvista as pv
            rs = self._render_settings()
            key = pv.Light()
            key.set_direction_angle(float(rs.material_light_elevation), float(rs.material_light_azimuth))
            key.intensity = float(rs.material_light_intensity)
            key.diffuse_color = (1.0, 0.98, 0.94)
            key.specular_color = (1.0, 1.0, 1.0)
            try:
                key.shadow_attenuation = 1.0
            except Exception:
                pass
            self.plotter.add_light(key)
        except Exception:
            log_exception("final_render_lights")

        bounds = scene_bounds(render_meshes)
        try:
            enable_vtk_shadows(self.plotter, owner.ui_log, bounds=bounds)
        except Exception:
            log_exception("final_render_enable_vtk_shadows")

        pose, source = self._camera_pose()
        if pose is not None:
            try:
                cam = self.plotter.camera
                cam.SetPosition(*pose["position"])
                cam.SetFocalPoint(*pose["focal_point"])
                cam.SetViewUp(*pose["view_up"])
                try:
                    cam.SetParallelProjection(False)
                except Exception:
                    pass
            except Exception:
                log_exception("final_render_apply_camera")
        else:
            try:
                self.plotter.camera_position = "iso"
            except Exception:
                pass
            source = "vue iso"

        try:
            self.plotter.reset_camera_clipping_range()
        except Exception:
            pass
        try:
            self.plotter.render()
        except Exception:
            pass
        try:
            self.info_label.setText(f"Camera source: {source}")
            owner.ui_log(f"[FINAL_RENDER] refreshed square window camera={source} meshes={len(render_meshes)}")
        except Exception:
            pass


