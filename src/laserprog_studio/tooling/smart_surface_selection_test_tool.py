# -*- coding: utf-8 -*-
"""Interactive test harness for the public intelligent surface-selection API."""
from __future__ import annotations

import time
from typing import Any, Iterable

from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool, MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_api.inspector import BoolField, ButtonRow, ChoiceField, HelpText, Panel, ReadonlyField, Section, SliderField, Title
from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_api import surface_selection

from .base import ToolSpec
from .smart_surface_selection_diagnostics import SurfaceSelectionPerformanceRecorder
from .ids import TOOL_SMART_SURFACE_SELECTION_TEST

class SmartSurfaceSelectionTestCreatorTool(CreatorTool):
    """Viewport-only laboratory for tuning logical mesh-face selection."""

    id = TOOL_SMART_SURFACE_SELECTION_TEST
    label = "Selection API test"

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._allow_multiple_meshes = True
        self._session = surface_selection.SurfaceSelectionSession(mesh_policy=surface_selection.SurfaceSelectionMeshPolicy.MULTIPLE_MESHES)
        self._pointer = surface_selection.SurfaceSelectionPointerMachine()
        self._hover_result: surface_selection.SurfaceRegionResult | None = None
        self._hover_snapshot: surface_selection.SurfaceMeshSnapshot | None = None
        self._hover_face: int | None = None
        self._camera_active = False
        self._show_hover = True
        self._show_boundary = True
        self._profile_id = "cloth_support"
        self._cache: dict[tuple[Any, ...], surface_selection.SurfaceMeshSnapshot] = {}
        self._alternative_index = -1
        self._diagnostics_enabled = True
        self._diagnostic_verbose = True
        self._diagnostics = SurfaceSelectionPerformanceRecorder(enabled=True)
        self._last_hover_ms = 0.0
        self._last_click_ms = 0.0
        self._last_pick_status = "—"

    def _profile(self) -> surface_selection.SurfaceSelectionProfile:
        if self._profile_id == "exact_face":
            return surface_selection.SurfaceSelectionProfile.exact_face()
        return surface_selection.SurfaceSelectionProfile.cloth_support()

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        self._ctx = ctx
        self._session = surface_selection.SurfaceSelectionSession(
            tolerance=0.35,
            automatic=True,
            mesh_policy=(
                surface_selection.SurfaceSelectionMeshPolicy.MULTIPLE_MESHES
                if self._allow_multiple_meshes
                else surface_selection.SurfaceSelectionMeshPolicy.SINGLE_MESH
            ),
        )
        self._pointer.reset()
        self._hover_result = None
        self._hover_snapshot = None
        self._hover_face = None
        self._camera_active = False
        self._cache.clear()
        self._alternative_index = -1
        self._last_hover_ms = 0.0
        self._last_click_ms = 0.0
        self._last_pick_status = "—"
        self._diagnostics.enabled = self._diagnostics_enabled
        self._diagnostic_verbose = self._diagnostics_enabled
        self._diagnostics.reset(reason="tool_open")
        ctx.inspector.set_panel(self._panel(ctx))
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("pick", "Pick a logical surface", help="Hover a mesh, then click a proposed region."),
                ctx.workflow.step("tune", "Build a multiple selection", help="Click replaces the selection. Shift+click adds another complete logical region. Double-click empty space clears."),
            ),
        )
        self._sync(ctx, "Hover a mesh face. Auto proposes a complete logical surface before the click.")

    def on_close(self, ctx: Any) -> None:
        if self._diagnostics_enabled:
            self._diagnostics.export(reason="tool_close")
        ctx.projected_drawing.for_tool(self.id).clear(render=False)
        ctx.workflow.clear(self.id)
        ctx.inspector.clear()
        self._ctx = None

    def on_cancel(self, ctx: Any) -> bool:
        self._clear(ctx, status="Selection API test closed.")
        return True

    def can_apply(self, ctx: Any) -> bool:  # noqa: ARG002
        return False

    def _panel(self, ctx: Any) -> Panel:
        return Panel(
            "Selection API test",
            id="smart_surface_selection_test.panel",
            owner_tool=self.id,
            description="Isolated test harness for the future shared intelligent face-selection API.",
            sections=(
                Section(
                    "Interaction",
                    fields=(
                        Title("surface_test_title", "Logical surface selection"),
                        HelpText("surface_test_help", "Click: replace with one logical region · Shift+click: add another logical region · Double-click empty space: clear."),
                        BoolField("automatic", "Hover Auto", default=True, tooltip="Find a stable semantic proposal under the pointer and expose its calculated continuity.", on_change=lambda _id, value: self._set_auto(ctx, bool(value))),
                        SliderField("tolerance", "Continuity", default=0.35, min_value=0.0, max_value=1.0, step=0.01, on_change=lambda _id, value: self._set_tolerance(ctx, float(value))),
                        ChoiceField(
                            "profile",
                            "Profile",
                            default="cloth_support",
                            choices=(("cloth_support", "Cloth support"), ("exact_face", "Strict face")),
                            on_change=lambda _id, value: self._set_profile(ctx, str(value)),
                        ),
                        BoolField("show_hover", "Show hover proposal", default=True, on_change=lambda _id, value: self._set_show_hover(ctx, bool(value))),
                        BoolField("show_boundary", "Show logical boundary", default=True, on_change=lambda _id, value: self._set_show_boundary(ctx, bool(value))),
                        BoolField(
                            "allow_multiple_meshes",
                            "Allow multiple meshes",
                            default=True,
                            tooltip="When enabled, Shift+click can add logical regions from different scene meshes.",
                            on_change=lambda _id, value: self._set_multi_mesh(ctx, bool(value)),
                        ),
                        BoolField(
                            "reuse_logical_cache",
                            "Reuse learned logical regions",
                            default=False,
                            tooltip="Optional conservative reuse on flat interior triangles. Exact seed results and accessibility fields remain cached even when disabled.",
                            on_change=lambda _id, value: self._set_logical_reuse(ctx, bool(value)),
                        ),
                    ),
                ),
                Section(
                    "Result",
                    fields=(
                        ReadonlyField("object_name", "Object", default="None"),
                        ReadonlyField("seed_face", "Seed", default="None"),
                        ReadonlyField("selection_mode", "Mode", default="Empty"),
                        ReadonlyField("region_count", "Logical regions", default="0"),
                        ReadonlyField("mesh_count", "Meshes", default="0"),
                        ReadonlyField("pick_status", "Exact hit", default="—"),
                        ReadonlyField("face_count", "Triangles", default="0"),
                        ReadonlyField("confidence", "Confidence", default="0 %"),
                        ReadonlyField("angles", "Curvature", default="—"),
                        ReadonlyField("last_hover_ms", "Last hover", default="0.0 ms"),
                        ReadonlyField("last_click_ms", "Last click", default="0.0 ms"),
                        ReadonlyField("cache_stats", "Selection cache", default="0 field · 0 result · 0 logical"),
                        ReadonlyField("result_status", "Status", default="Ready."),
                    ),
                ),
                Section(
                    "Diagnostics",
                    fields=(
                        BoolField(
                            "capture_diagnostics",
                            "Capture performance diagnostics",
                            default=True,
                            tooltip="Buffer detailed timings in memory. Files are written only on Export or when the tool closes.",
                            on_change=lambda _id, value: self._set_diagnostics_enabled(ctx, bool(value)),
                        ),
                        ReadonlyField("diagnostics_path", "Output", default="diagnostics/smart_surface_selection_performance.*"),
                        ButtonRow(
                            "surface_test_diagnostics",
                            "Diagnostics",
                            buttons=(("reset_diagnostics", "Reset"), ("export_diagnostics", "Export")),
                            callbacks={
                                "reset_diagnostics": lambda _event: self._reset_diagnostics(ctx),
                                "export_diagnostics": lambda _event: self._export_diagnostics(ctx),
                            },
                        ),
                    ),
                ),
                Section(
                    "Test actions",
                    fields=(
                        ButtonRow(
                            "surface_test_actions",
                            "Actions",
                            buttons=(("clear_cache", "Clear cache"), ("clear", "Clear")),
                            callbacks={
                                "clear_cache": lambda _event: self._clear_selection_cache(ctx),
                                "clear": lambda _event: self._clear(ctx),
                            },
                        ),
                    ),
                ),
            ),
        )

    def wants_pointer_press_passthrough(self, event: ToolEvent, ctx: Any) -> bool:  # noqa: ARG002
        if event.type is ToolEventType.MOUSE_PRESS and event.button is MouseButton.LEFT and event.screen_pos is not None:
            self._pointer.press(event.screen_pos)
            return False
        return False

    def wants_pointer_release_passthrough(self, event: ToolEvent, ctx: Any) -> bool:  # noqa: ARG002
        return bool(
            event.type is ToolEventType.MOUSE_RELEASE
            and event.button in {MouseButton.LEFT, MouseButton.NONE}
            and self._pointer.state is not surface_selection.SurfaceSelectionPointerState.READY
        )

    def on_camera_interaction_begin(self, ctx: Any, **_: Any) -> None:
        self._camera_active = True
        self._pointer.begin_camera_drag()
        self._hover_result = None
        self._render(ctx)

    def on_camera_interaction_end(self, ctx: Any, *, screen_pos=None, **_: Any) -> None:
        self._camera_active = False
        if screen_pos is not None:
            self._update_hover(ctx, screen_pos)

    def on_event(self, event: ToolEvent, ctx: Any) -> bool:
        if event.is_escape:
            self._pointer.reset()
            self._clear(ctx)
            return True
        if event.type is ToolEventType.KEY_PRESS and (event.key or "").lower() == "a":
            self._set_auto(ctx, not self._session.automatic)
            return True
        if event.type is ToolEventType.MOUSE_MOVE:
            if event.screen_pos is not None:
                self._pointer.move(event.screen_pos)
            if (
                not self._camera_active
                and self._pointer.state is surface_selection.SurfaceSelectionPointerState.READY
                and event.screen_pos is not None
                and event.button is MouseButton.NONE
            ):
                self._update_hover(ctx, event.screen_pos)
            return False
        if event.type is ToolEventType.MOUSE_PRESS and event.button is MouseButton.LEFT and event.screen_pos is not None:
            self._pointer.press(event.screen_pos)
            return False
        if event.type is ToolEventType.MOUSE_DOUBLE_CLICK and event.button is MouseButton.LEFT and event.screen_pos is not None:
            # Qt emits this in place of the second press.  When the first release
            # was observed, the API applies its shorter interval on the final
            # release.  The fallback preserves bridges that swallowed it.
            if self._pointer.last_click_time_s is None:
                self._pointer.double_click(event.screen_pos)
                return self._handle_double_click(ctx, event)
            self._pointer.press(event.screen_pos)
            return True
        if event.type is not ToolEventType.MOUSE_RELEASE or event.button not in {MouseButton.LEFT, MouseButton.NONE} or event.screen_pos is None:
            return False
        action = self._pointer.release(event.screen_pos)
        if action is surface_selection.SurfaceSelectionPointerAction.DOUBLE_CLICK:
            return self._handle_double_click(ctx, event)
        if action is surface_selection.SurfaceSelectionPointerAction.CLICK:
            return self._handle_click(ctx, event)
        return True

    def _pick(self, ctx: Any, screen_pos: tuple[float, float], *, operation=None):
        started = time.perf_counter()
        try:
            pick = ctx.pick.face_at(screen_pos, exact_screen=True)
            pick_error = None
        except Exception as exc:
            pick = None
            pick_error = f"{type(exc).__name__}: {exc}"
        pick_ms = (time.perf_counter() - started) * 1000.0
        if operation is not None:
            operation.sink(
                "pick.face_at",
                elapsed_ms=pick_ms,
                screen_pos=screen_pos,
                hit=bool(pick is not None and getattr(pick, "hit", False)),
                error=pick_error,
            )
        if pick is None or not bool(getattr(pick, "hit", False)):
            return pick, None, None
        snapshot = self._snapshot_for_pick(ctx, pick, operation=operation)
        if snapshot is None:
            return pick, None, None
        started = time.perf_counter()
        raw_face_index = surface_selection.face_index_from_pick(pick)
        face_index = surface_selection.face_index_from_pick(pick, snapshot)
        if operation is not None:
            operation.sink(
                "pick.face_index",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                raw_face_index=raw_face_index,
                face_index=face_index,
                remapped=raw_face_index != face_index,
                exact_screen=bool((getattr(pick, "metadata", None) or {}).get("exact_screen")),
                coordinate_mode=(getattr(pick, "metadata", None) or {}).get("coordinate_mode"),
                object_id=getattr(pick, "object_id", None),
                object_index=getattr(pick, "object_index", None),
            )
        if face_index is None or not 0 <= face_index < len(snapshot.triangles):
            self._last_pick_status = "No canonical face"
            return pick, None, None
        self._last_pick_status = (
            f"cell {raw_face_index} → face {face_index}"
            if raw_face_index != face_index
            else f"face {face_index}"
        )
        return pick, snapshot, face_index

    def _snapshot_for_pick(self, ctx: Any, pick: Any, *, operation=None):
        started_total = time.perf_counter()
        object_id = str(getattr(pick, "object_id", "") or getattr(pick, "object_index", "") or "unknown")
        obj = None
        started = time.perf_counter()
        try:
            if getattr(pick, "object_id", None) is not None:
                obj = ctx.document.get(str(pick.object_id))
        except Exception:
            obj = None
        if obj is None:
            try:
                obj = ctx.document.objects()[int(pick.object_index)]
            except Exception:
                pass
        resolve_ms = (time.perf_counter() - started) * 1000.0
        mesh = getattr(obj, "mesh", None) if obj is not None else None
        mesh = mesh or obj
        try:
            revision = str(
                getattr(mesh, "geometry_revision", "")
                or getattr(mesh, "revision", "")
                or getattr(obj, "geometry_revision", "")
                or getattr(obj, "revision", "")
            )
            key = (
                object_id,
                id(mesh),
                id(mesh.vertices),
                id(mesh.triangles),
                len(mesh.vertices),
                len(mesh.triangles),
                revision,
            )
            mesh_vertices = len(mesh.vertices)
            mesh_faces = len(mesh.triangles)
        except Exception:
            sink = self._diagnostics.core_sink(operation) if operation is not None else None
            snapshot = surface_selection.snapshot_from_pick(ctx, pick, diagnostics=sink)
            if operation is not None:
                operation.sink(
                    "snapshot.fallback",
                    elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
                    object_id=object_id,
                    object_resolve_ms=resolve_ms,
                    snapshot_ok=snapshot is not None,
                )
            return snapshot
        started = time.perf_counter()
        cached = self._cache.get(key)
        cache_lookup_ms = (time.perf_counter() - started) * 1000.0
        hit = cached is not None
        if operation is not None:
            operation.sink(
                "snapshot.cache",
                elapsed_ms=cache_lookup_ms,
                hit=hit,
                object_id=object_id,
                object_name=getattr(obj, "name", ""),
                mesh_vertices=mesh_vertices,
                mesh_faces=mesh_faces,
                revision=revision,
                object_resolve_ms=resolve_ms,
            )
        if cached is None:
            sink = self._diagnostics.core_sink(operation) if operation is not None else None
            cached = surface_selection.snapshot_from_pick(ctx, pick, diagnostics=sink)
            if cached is not None:
                self._cache[key] = cached
                while len(self._cache) > 24:
                    self._cache.pop(next(iter(self._cache)))
        if operation is not None:
            operation.sink(
                "snapshot.total",
                elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
                hit=hit,
                object_id=object_id,
                object_name=getattr(obj, "name", ""),
                mesh_vertices=mesh_vertices,
                mesh_faces=mesh_faces,
                revision=revision,
                snapshot_ok=cached is not None,
            )
        return cached

    def _evaluate(self, snapshot: surface_selection.SurfaceMeshSnapshot, face_index: int, *, operation=None):
        sink = self._diagnostics.core_sink(operation) if operation is not None else None
        started = time.perf_counter()
        if self._session.automatic:
            result = surface_selection.auto_surface_region(
                snapshot,
                face_index,
                profile=self._profile(),
                cache=self._session.cache,
                diagnostics=sink,
            )
        else:
            result = surface_selection.select_surface_region(
                snapshot,
                face_index,
                self._session.tolerance,
                profile=self._profile(),
                cache=self._session.cache,
                diagnostics=sink,
            )
        if operation is not None:
            operation.sink(
                "evaluate.total",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                object_id=snapshot.object_id,
                object_name=snapshot.name,
                mesh_vertices=len(snapshot.vertices),
                mesh_faces=len(snapshot.triangles),
                seed_face=face_index,
                automatic=self._session.automatic,
                tolerance=self._session.tolerance,
                profile=self._profile_id,
                selected_faces=result.metrics.face_count,
                boundary_edges=len(result.boundary_edges),
                cache_field_hits=self._session.cache.field_hits,
                cache_field_misses=self._session.cache.field_misses,
                cache_result_hits=self._session.cache.result_hits,
                cache_logical_hits=self._session.cache.logical_hits,
            )
        return result

    def _update_hover(self, ctx: Any, screen_pos: tuple[float, float]) -> None:
        operation = self._diagnostics.begin(
            "hover",
            screen_pos=screen_pos,
            automatic=self._session.automatic,
            tolerance=self._session.tolerance,
            profile=self._profile_id,
        ) if self._diagnostics_enabled else None
        _pick, snapshot, face_index = self._pick(ctx, screen_pos, operation=operation)
        if snapshot is None or face_index is None:
            changed = self._hover_result is not None
            self._hover_result = None
            self._hover_snapshot = None
            self._hover_face = None
            self._last_pick_status = "No visible face"
            if changed:
                self._render(ctx, operation=operation)
            if operation is not None:
                self._last_hover_ms = operation.finish(outcome="no_face", overlay_changed=changed)
                self._update_timing_fields(ctx)
            return
        if self._hover_snapshot is snapshot and self._hover_face == face_index:
            if operation is not None:
                operation.sink(
                    "hover.skip",
                    reason="same_snapshot_and_face",
                    object_id=snapshot.object_id,
                    face_index=face_index,
                )
                self._last_hover_ms = operation.finish(outcome="same_face")
                self._update_timing_fields(ctx)
            return
        self._hover_snapshot = snapshot
        self._hover_face = face_index
        self._hover_result = self._evaluate(snapshot, face_index, operation=operation)
        self._render(ctx, operation=operation)
        if operation is not None:
            self._last_hover_ms = operation.finish(
                outcome="ok",
                object_id=snapshot.object_id,
                object_name=snapshot.name,
                mesh_vertices=len(snapshot.vertices),
                mesh_faces=len(snapshot.triangles),
                face_index=face_index,
                selected_faces=self._hover_result.metrics.face_count,
            )
            self._update_timing_fields(ctx)

    def _handle_click(self, ctx: Any, event: ToolEvent) -> bool:
        operation = self._diagnostics.begin(
            "click",
            screen_pos=event.screen_pos,
            shift=bool(event.shift),
            automatic=self._session.automatic,
            tolerance=self._session.tolerance,
            profile=self._profile_id,
        ) if self._diagnostics_enabled else None
        _pick, snapshot, face_index = self._pick(ctx, event.screen_pos, operation=operation)
        if snapshot is None or face_index is None:
            self._sync(ctx, "No face under the pointer. The current selection is unchanged.", render=False, operation=operation)
            if operation is not None:
                self._last_click_ms = operation.finish(outcome="no_face")
                self._update_timing_fields(ctx)
            return True

        started_selection = time.perf_counter()
        reused_hover = False
        if (
            self._hover_snapshot is snapshot
            and self._hover_face == face_index
            and self._hover_result is not None
            and not self._session.cache.logical_reuse
        ):
            region = self._hover_result
            reused_hover = True
        else:
            logical_reuse = self._session.cache.logical_reuse
            self._session.cache.logical_reuse = False
            try:
                region = self._evaluate(snapshot, face_index, operation=operation)
            finally:
                self._session.cache.logical_reuse = logical_reuse

        if event.shift:
            previous_mesh_count = self._session.selected_mesh_count
            result = self._session.add_region(snapshot, region)
            if self._session.selected_mesh_count > previous_mesh_count:
                action = f"Added mesh {self._session.selected_mesh_count}"
            elif self._session.selected_region_count > 1:
                action = f"Added logical region {self._session.selected_region_count}"
            else:
                action = "Selected one logical region"
        else:
            result = self._session.adopt(snapshot, region)
            action = "Selected one logical region"

        if operation is not None:
            operation.sink(
                "click.selection",
                elapsed_ms=(time.perf_counter() - started_selection) * 1000.0,
                reused_hover=reused_hover,
                interaction_mode=self._session.selection_mode,
                logical_regions=self._session.selected_region_count,
                object_id=snapshot.object_id,
                object_name=snapshot.name,
                mesh_vertices=len(snapshot.vertices),
                mesh_faces=len(snapshot.triangles),
                face_index=face_index,
                selected_faces=result.metrics.face_count,
            )
        self._alternative_index = -1
        self._hover_result = None
        self._hover_snapshot = None
        self._hover_face = None
        self._sync(ctx, f"{action}. {result.explanation}", operation=operation)
        if operation is not None:
            self._last_click_ms = operation.finish(
                outcome="ok",
                reused_hover=reused_hover,
                interaction_mode=self._session.selection_mode,
                logical_regions=self._session.selected_region_count,
                object_id=snapshot.object_id,
                object_name=snapshot.name,
                mesh_vertices=len(snapshot.vertices),
                mesh_faces=len(snapshot.triangles),
                face_index=face_index,
                selected_faces=result.metrics.face_count,
            )
            self._update_timing_fields(ctx)
        return True

    def _handle_double_click(self, ctx: Any, event: ToolEvent) -> bool:
        operation = self._diagnostics.begin(
            "double_click",
            screen_pos=event.screen_pos,
            profile=self._profile_id,
        ) if self._diagnostics_enabled else None
        _pick, snapshot, face_index = self._pick(ctx, event.screen_pos, operation=operation)
        if snapshot is None or face_index is None:
            self._clear(ctx, status="Selection cleared by double-click in empty space.")
            if operation is not None:
                self._last_click_ms = operation.finish(outcome="cleared_empty")
                self._update_timing_fields(ctx)
            return True

        self._sync(ctx, "Double-click on a surface has no special action. Use click or Shift+click.", render=False, operation=operation)
        if operation is not None:
            self._last_click_ms = operation.finish(
                outcome="surface_noop",
                interaction_mode=self._session.selection_mode,
                logical_regions=self._session.selected_region_count,
                object_id=snapshot.object_id,
                object_name=snapshot.name,
                face_index=face_index,
                selected_faces=self._session.result.metrics.face_count if self._session.result is not None else 0,
            )
            self._update_timing_fields(ctx)
        return True

    def _set_diagnostics_enabled(self, ctx: Any, enabled: bool) -> None:
        self._diagnostics_enabled = bool(enabled)
        self._diagnostic_verbose = self._diagnostics_enabled
        self._diagnostics.enabled = self._diagnostics_enabled
        ctx.inspector.update_value("capture_diagnostics", self._diagnostics_enabled, notify=False)
        if self._diagnostics_enabled:
            self._diagnostics.reset(reason="capture_enabled")
            self._sync(ctx, "Performance diagnostics enabled. Timings are buffered in memory.", render=False)
        else:
            self._sync(ctx, "Performance diagnostics disabled.", render=False)

    def _reset_diagnostics(self, ctx: Any) -> None:
        self._diagnostics.reset(reason="manual_reset")
        self._last_hover_ms = 0.0
        self._last_click_ms = 0.0
        self._update_timing_fields(ctx)
        self._sync(ctx, "Performance diagnostics reset.", render=False)

    def _export_diagnostics(self, ctx: Any) -> None:
        paths = self._diagnostics.export(reason="manual_export")
        names = ", ".join(path.name for path in paths)
        self._sync(ctx, f"Diagnostics exported: {names}", render=False)

    def _update_timing_fields(self, ctx: Any) -> None:
        try:
            ctx.inspector.update_values(
                {
                    "last_hover_ms": f"{self._last_hover_ms:.1f} ms",
                    "last_click_ms": f"{self._last_click_ms:.1f} ms",
                    "cache_stats": (
                        f"{self._session.cache.field_hits} field · "
                        f"{self._session.cache.result_hits} result · "
                        f"{self._session.cache.logical_hits} logical"
                    ),
                },
                notify=False,
            )
        except Exception:
            pass

    def _set_auto(self, ctx: Any, enabled: bool) -> None:
        self._session.automatic = bool(enabled)
        ctx.inspector.update_value("automatic", self._session.automatic, notify=False)
        if self._hover_snapshot is not None and self._hover_face is not None:
            self._hover_result = self._evaluate(self._hover_snapshot, self._hover_face)
        self._alternative_index = -1
        self._sync(ctx, "Auto mode enabled." if enabled else "Manual continuity enabled.")

    def _set_tolerance(self, ctx: Any, value: float) -> None:
        self._session.tolerance = max(0.0, min(1.0, float(value)))
        self._session.automatic = False
        ctx.inspector.update_values({"automatic": False, "tolerance": self._session.tolerance}, notify=False)
        if self._hover_snapshot is not None and self._hover_face is not None:
            self._hover_result = self._evaluate(self._hover_snapshot, self._hover_face)
        self._alternative_index = -1
        self._sync(ctx, f"Manual continuity: {self._session.tolerance:.2f}.")

    def _set_profile(self, ctx: Any, value: str) -> None:
        self._profile_id = "exact_face" if value == "exact_face" else "cloth_support"
        if self._hover_snapshot is not None and self._hover_face is not None:
            self._hover_result = self._evaluate(self._hover_snapshot, self._hover_face)
        self._alternative_index = -1
        self._sync(ctx, f"Profile: {'Strict face' if self._profile_id == 'exact_face' else 'Cloth support'}.")

    def _set_show_hover(self, ctx: Any, value: bool) -> None:
        self._show_hover = bool(value)
        self._render(ctx)

    def _set_show_boundary(self, ctx: Any, value: bool) -> None:
        self._show_boundary = bool(value)
        self._render(ctx)

    def _set_multi_mesh(self, ctx: Any, value: bool) -> None:
        self._allow_multiple_meshes = bool(value)
        self._session.mesh_policy = (
            surface_selection.SurfaceSelectionMeshPolicy.MULTIPLE_MESHES
            if self._allow_multiple_meshes
            else surface_selection.SurfaceSelectionMeshPolicy.SINGLE_MESH
        )
        ctx.inspector.update_value("allow_multiple_meshes", self._allow_multiple_meshes, notify=False)
        self._sync(
            ctx,
            "Shift+click can add regions from different meshes."
            if self._allow_multiple_meshes
            else "Selection is restricted to one mesh; another mesh restarts it.",
            render=False,
        )

    def _set_logical_reuse(self, ctx: Any, value: bool) -> None:
        self._session.cache.logical_reuse = bool(value)
        self._session.cache.clear()
        ctx.inspector.update_value("reuse_logical_cache", bool(value), notify=False)
        self._hover_result = None
        self._hover_snapshot = None
        self._hover_face = None
        self._sync(ctx, "Logical-region reuse enabled; cache cleared." if value else "Logical-region reuse disabled; cache cleared.")

    def _clear_selection_cache(self, ctx: Any) -> None:
        self._session.cache.clear()
        self._sync(ctx, "Progressive selection cache cleared.", render=False)

    def _clear(self, ctx: Any, *, status: str = "Selection cleared.") -> None:
        self._pointer.reset()
        self._session.clear()
        self._hover_result = None
        self._hover_snapshot = None
        self._hover_face = None
        self._last_pick_status = "—"
        self._alternative_index = -1
        self._sync(ctx, status)

    @staticmethod
    def _mesh_primitive(primitive_id: str, snapshot, faces: Iterable[int], *, fill: str, opacity: float, outline: str, layer: int):
        face_values = tuple(sorted(set(int(value) for value in faces)))
        if not face_values:
            return None
        used = sorted({vertex for face in face_values for vertex in snapshot.triangles[face]})
        remap = {vertex: index for index, vertex in enumerate(used)}
        vertices = tuple(snapshot.vertices[index] for index in used)
        triangles = tuple(tuple(remap[index] for index in snapshot.triangles[face]) for face in face_values)
        return draw2d.triangle_mesh(
            primitive_id,
            vertices,
            triangles,
            fill_color=fill,
            fill_opacity=opacity,
            outline_color=outline,
            outline_width_px=1.2,
            outline_opacity=0.72,
            layer=layer,
            metadata={"surface_selection_role": primitive_id, "projected_no_selection_actor": True},
        )

    def _render(self, ctx: Any, *, render: bool = True, operation=None) -> None:
        started_total = time.perf_counter()
        primitives: list[Any] = []
        selected_items = self._session.selected_items
        current = self._session.result
        snapshot = self._session.snapshot
        selected_build_ms = 0.0
        constraints_build_ms = 0.0
        boundary_build_ms = 0.0
        hover_build_ms = 0.0
        selected_faces = 0
        hover_faces = 0
        boundary_edges = 0
        if selected_items:
            started = time.perf_counter()
            for item_index, (item_snapshot, item_result) in enumerate(selected_items):
                selected_faces += item_result.metrics.face_count
                primitive = self._mesh_primitive(
                    f"surface_selection_test.selected.{item_index}",
                    item_snapshot,
                    item_result.face_indices,
                    fill="#22D3EE",
                    opacity=0.28,
                    outline="#67E8F9",
                    layer=70,
                )
                if primitive is not None:
                    primitives.append(primitive)
            selected_build_ms = (time.perf_counter() - started) * 1000.0
            started = time.perf_counter()
            if self._session.required_faces and snapshot is not None:
                required = self._mesh_primitive("surface_selection_test.required", snapshot, self._session.required_faces, fill="#2563EB", opacity=0.46, outline="#93C5FD", layer=73)
                if required is not None:
                    primitives.append(required)
            if self._session.excluded_faces and snapshot is not None:
                excluded = self._mesh_primitive("surface_selection_test.excluded", snapshot, self._session.excluded_faces, fill="#EF4444", opacity=0.42, outline="#FCA5A5", layer=74)
                if excluded is not None:
                    primitives.append(excluded)
            constraints_build_ms = (time.perf_counter() - started) * 1000.0
            if self._show_boundary:
                started = time.perf_counter()
                for item_index, (item_snapshot, item_result) in enumerate(selected_items):
                    boundary_edges += len(item_result.boundary_edges)
                    if item_result.boundary_edges:
                        primitives.append(
                            draw2d.segment_batch(
                                f"surface_selection_test.boundary.{item_index}",
                                tuple((item_snapshot.vertices[edge[0]], item_snapshot.vertices[edge[1]]) for edge in item_result.boundary_edges),
                                color="#E0F2FE",
                                width_px=3.3,
                                opacity=0.98,
                                layer=76,
                            )
                        )
                boundary_build_ms = (time.perf_counter() - started) * 1000.0
        hover = self._hover_result
        hover_snapshot = self._hover_snapshot
        if self._show_hover and hover is not None and hover_snapshot is not None:
            hover_faces = hover.metrics.face_count
            started = time.perf_counter()
            primitive = self._mesh_primitive("surface_selection_test.hover", hover_snapshot, hover.face_indices, fill="#A3E635", opacity=0.16, outline="#D9F99D", layer=66)
            hover_build_ms = (time.perf_counter() - started) * 1000.0
            if primitive is not None:
                primitives.append(primitive)
        started = time.perf_counter()
        ctx.projected_drawing.for_tool(self.id).replace_all(tuple(primitives), render=render)
        replace_all_ms = (time.perf_counter() - started) * 1000.0
        if operation is not None:
            operation.sink(
                "render.overlay",
                elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
                selected_build_ms=selected_build_ms,
                constraints_build_ms=constraints_build_ms,
                boundary_build_ms=boundary_build_ms,
                hover_build_ms=hover_build_ms,
                replace_all_ms=replace_all_ms,
                selected_faces=selected_faces,
                hover_faces=hover_faces,
                boundary_edges=boundary_edges,
                primitive_count=len(primitives),
                render_requested=bool(render),
            )

    def _sync(self, ctx: Any, status: str, *, render: bool = True, operation=None) -> None:
        started_total = time.perf_counter()
        result = self._session.result
        snapshot = self._session.snapshot
        values = {
            "automatic": self._session.automatic,
            "tolerance": self._session.tolerance,
            "profile": self._profile_id,
            "show_hover": self._show_hover,
            "show_boundary": self._show_boundary,
            "allow_multiple_meshes": self._allow_multiple_meshes,
            "reuse_logical_cache": self._session.cache.logical_reuse,
            "capture_diagnostics": self._diagnostics_enabled,
            "diagnostics_path": "diagnostics/smart_surface_selection_performance.*",
            "object_name": (
                snapshot.name if self._session.selected_mesh_count <= 1 and snapshot is not None
                else f"{self._session.selected_mesh_count} meshes"
                if self._session.selected_mesh_count
                else "None"
            ),
            "seed_face": str(result.seed_face) if result is not None else "None",
            "selection_mode": ({"automatic": "Logical region", "multiple": "Multiple logical regions", "exact": "Exact", "empty": "Empty"}.get(self._session.selection_mode, self._session.selection_mode)),
            "region_count": str(self._session.selected_region_count),
            "mesh_count": str(self._session.selected_mesh_count),
            "face_count": str(result.metrics.face_count) if result is not None else "0",
            "confidence": f"{result.confidence:.0%}" if result is not None else "0 %",
            "angles": (f"local {result.metrics.maximum_local_angle_degrees:.1f}° · drift {result.metrics.maximum_seed_angle_degrees:.1f}°" if result is not None else "—"),
            "last_hover_ms": f"{self._last_hover_ms:.1f} ms",
            "last_click_ms": f"{self._last_click_ms:.1f} ms",
            "cache_stats": (
                f"{self._session.cache.field_hits} field · "
                f"{self._session.cache.result_hits} result · "
                f"{self._session.cache.logical_hits} logical"
            ),
            "result_status": str(status),
        }
        started = time.perf_counter()
        try:
            ctx.inspector.update_values(values, notify=False)
        except Exception:
            pass
        inspector_ms = (time.perf_counter() - started) * 1000.0
        self._render(ctx, render=render, operation=operation)
        started = time.perf_counter()
        try:
            ctx.status.info(str(status))
        except Exception:
            pass
        status_ms = (time.perf_counter() - started) * 1000.0
        if operation is not None:
            operation.sink(
                "sync.total",
                elapsed_ms=(time.perf_counter() - started_total) * 1000.0,
                inspector_ms=inspector_ms,
                status_ms=status_ms,
                render_requested=bool(render),
            )


class SmartSurfaceSelectionTestTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=SmartSurfaceSelectionTestCreatorTool())


__all__ = ["SmartSurfaceSelectionTestCreatorTool", "SmartSurfaceSelectionTestTool"]
