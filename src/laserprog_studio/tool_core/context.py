"""ToolContext wires together all shared layers available to viewport tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .commands import CommandStack
from .app_services import (
    DocumentFacade,
    JobManager,
    OperationManager,
    PickingFacade,
    PreviewSessionManager,
    ProjectScenesFacade,
    SceneSelectionFacade,
    StatusManager,
    ViewFacade,
)
from .app_domain_services import AssetManager, EngravingManager, MaterialManager, PlanarManager
from .gizmos import GizmoManager
from .transform_gizmos import TransformGizmoManager
from .inspector import InspectorManager
from .overlay import OverlayManager
from .perf import ToolProfiler
from .preview import PreviewManager
from .projected_drawing import ProjectedDrawingManager
from .rendering import ViewportAdapter
from .scene_cache import SceneCache
from .selection import SelectionManager
from .sketch import SketchDocument
from .snap import SnapManager
from .box_selection import BoxSelectionManager
from .style import DEFAULT_STYLE, ToolStyle
from .workflow import ToolModeManager, ToolWorkflowManager


@dataclass(slots=True)
class ToolContext:
    viewport: ViewportAdapter = field(default_factory=ViewportAdapter)
    selection: SelectionManager = field(default_factory=SelectionManager)
    gizmos: GizmoManager = field(default_factory=GizmoManager)
    # Isolated API for the application Transform tool. Generic Creator tools
    # (Plan Tracer, engraving, diagnostics, etc.) continue to use ``gizmos``
    # with its historical semantics.
    transform_gizmos: TransformGizmoManager = field(default_factory=TransformGizmoManager)
    snap: SnapManager = field(default_factory=SnapManager)
    overlay: OverlayManager = field(default_factory=OverlayManager)
    preview: PreviewManager = field(default_factory=PreviewManager)
    # Projected 2D drawing API for dense geometry and lightweight interactive
    # handles. It remains independent from the historical preview/gizmo renderer
    # so tools can migrate incrementally without changing existing motifs.
    projected_drawing: ProjectedDrawingManager = field(default_factory=ProjectedDrawingManager)
    inspector: InspectorManager = field(default_factory=InspectorManager)
    scene_cache: SceneCache = field(default_factory=SceneCache)
    commands: CommandStack = field(default_factory=CommandStack)
    sketch: SketchDocument = field(default_factory=SketchDocument)
    profiler: ToolProfiler = field(default_factory=ToolProfiler)
    style: ToolStyle = DEFAULT_STYLE
    scene: Any | None = None
    owner: Any | None = None
    selection_state: Any | None = None
    document: DocumentFacade | Any = field(default_factory=DocumentFacade)
    scene_selection: SceneSelectionFacade = field(default_factory=SceneSelectionFacade)
    pick: PickingFacade = field(default_factory=PickingFacade)
    preview_session: PreviewSessionManager = field(default_factory=PreviewSessionManager)
    project_scenes: ProjectScenesFacade = field(default_factory=ProjectScenesFacade)
    operations: OperationManager = field(default_factory=OperationManager)
    jobs: JobManager = field(default_factory=JobManager)
    status: StatusManager = field(default_factory=StatusManager)
    view: ViewFacade = field(default_factory=ViewFacade)
    materials: MaterialManager = field(default_factory=MaterialManager)
    assets: AssetManager = field(default_factory=AssetManager)
    engraving: EngravingManager = field(default_factory=EngravingManager)
    planar: PlanarManager = field(default_factory=PlanarManager)
    selection_box: BoxSelectionManager = field(default_factory=BoxSelectionManager)
    workflow: ToolWorkflowManager = field(default_factory=ToolWorkflowManager)
    modes: ToolModeManager = field(default_factory=ToolModeManager)
    # Per-ctx scratch dicts for tool API caches. ``ToolContext`` is slotted so
    # plan2d/snap helpers cannot ``setattr`` ad-hoc stores; this dedicated field
    # lets ``_extra_plan2d_guide_cache`` actually persist its compiled
    # projection table across mouse-move events. Without it the heavy
    # ``world_to_plane`` walk was rebuilt on every hover in dense sketches.
    _plan2d_extra_guide_cache_store: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.document, DocumentFacade):
            self.document = DocumentFacade(self.document)
        for service_name in ("document", "scene_selection", "pick", "preview_session", "project_scenes", "operations", "jobs", "status", "view", "materials", "assets", "engraving", "planar", "selection_box", "workflow", "modes", "projected_drawing"):
            service = getattr(self, service_name, None)
            binder = getattr(service, "bind_context", None)
            if callable(binder):
                binder(self)
        if self.owner is not None:
            self._bind_live_projected_drawing_backend()

    def attach_owner(self, owner: Any | None) -> None:
        """Attach the live application owner and repair renderer bridges.

        Runtime adapters often create ``ToolContext`` before a Qt window is
        available, then attach the owner later.  A plain ``ctx.owner = owner``
        updates the data field but does not trigger ``__post_init__`` again,
        which can leave the Projected Drawing 2D renderer unbound and make Plan
        Tracer geometry disappear from the viewport.  Use this helper whenever
        a live owner is assigned after construction.
        """

        self.owner = owner
        if owner is not None:
            try:
                from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

                record_projected_overlay_event("context.attach_owner", owner=owner, ctx=self, owner_tool="*")
            except Exception:
                pass
            self.ensure_live_projected_drawing_backend()

    def ensure_live_projected_drawing_backend(self) -> bool:
        """Ensure the live Projected Drawing renderer backend is installed."""

        if self.owner is None:
            return False
        try:
            from laserprog_studio.application.projected_drawing_2d import bind_projected_drawing_2d_backend

            result = bool(bind_projected_drawing_2d_backend(self))
            try:
                from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

                record_projected_overlay_event("context.ensure_backend", owner=self.owner, ctx=self, owner_tool="*", result=result)
            except Exception:
                pass
            return result
        except Exception as exc:
            try:
                from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

                record_projected_overlay_event("context.ensure_backend.exception", owner=self.owner, ctx=self, owner_tool="*", error=exc)
            except Exception:
                pass
            return False

    def _bind_live_projected_drawing_backend(self) -> None:
        """Bind the live Projected Drawing renderer for direct ToolContext users.

        Most application paths install this from the runtime adapter. This small
        bootstrap preserves the established ``ToolContext(owner=window)`` path
        used by renderer tests and diagnostic probes while keeping
        ``tool_core.projected_drawing`` itself free of application imports.
        """

        self.ensure_live_projected_drawing_backend()

    def begin_drag(self) -> None:
        self.gizmos.begin_interactive_update()
        self.profiler.increment("drag.begin")

    def end_drag(self) -> None:
        self.gizmos.end_interactive_update()
        self.profiler.increment("drag.end")
        self.viewport.request_full_render()

    def request_light_render(self) -> None:
        if self.viewport.request_light_render():
            self.profiler.increment("render.light")
        else:
            self.profiler.increment("render.throttled")

    def request_full_render(self) -> None:
        self.viewport.request_full_render()
        self.profiler.increment("render.full")

    @property
    def actors(self):
        """Safer creator-facing actor registry.

        ``ctx.selection`` remains the low-level manager. New tools should prefer
        ``ctx.actors.add(...)`` because it validates duplicate updates and keeps
        the scene cache invalidated consistently.
        """

        from laserprog_studio.tool_api.actors import ActorRegistry

        return ActorRegistry(self)

    def actor_registry(self, owner_tool: str):
        """Return an owner-scoped actor registry for one creator tool."""

        from laserprog_studio.tool_api.actors import ActorRegistry

        return ActorRegistry(self, owner_tool)

    def cleanup_tool(self, owner_tool: str, *, include_persistent_overlays: bool = True) -> None:
        """Remove transient state owned by a creator tool.

        This is the safe default cleanup used by the creator API lifecycle: it
        clears previews, gizmos, actors, snap temp targets, tool-owned overlays
        and the right inspector panel when it belongs to the closing tool.
        """

        owner = str(owner_tool)
        self.preview.clear_tool(owner)
        self.projected_drawing.clear_tool(owner, render=False)
        self.gizmos.clear_tool(owner)
        self.transform_gizmos.clear_tool(owner)
        self.selection.clear_tool(owner)
        if getattr(self.selection_box.config, "owner_tool", None) == owner:
            self.selection_box.cancel()
        self.scene_cache.clear_tool_targets(owner)
        self.overlay.close_tool_windows(owner, include_persistent=include_persistent_overlays)
        host_owner = getattr(self, "owner", None)
        if host_owner is not None:
            try:
                from laserprog_studio.tool_core.overlay import sync_qt_overlay_windows

                sync_qt_overlay_windows(host_owner, self.overlay)
            except Exception:
                pass
        self.workflow.clear(owner)
        self.modes.clear(owner)
        panel = getattr(self.inspector, "panel", None)
        if panel is not None and getattr(panel, "owner_tool", None) == owner:
            self.inspector.clear()
        self.profiler.increment("tool.cleanup")
        self.request_full_render()

