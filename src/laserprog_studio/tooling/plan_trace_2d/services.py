# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar


class _PlanTrace2DHost(Protocol):
    """Minimal protocol implemented by the Plan Trace Creator tool shell."""

    id: str
    _state: Any


class _PlanTrace2DService:
    """Base for Plan Tracer services.

    The first refactor split the tool into mixins.  This base turns those
    behavior blocks into explicit composition instead: each service receives the
    owning tool shell, reads/writes the shared state through it, and may call the
    shell's public/private coordination methods.

    The forwarding is intentionally narrow: persistent data stays on the tool
    shell, while service-local caches can still live on each service instance.
    """

    _tool: _PlanTrace2DHost

    def __init__(self, tool: _PlanTrace2DHost) -> None:
        self._tool = tool

    @property
    def id(self) -> str:
        return self._tool.id

    @property
    def _state(self) -> Any:
        return self._tool._state

    @_state.setter
    def _state(self, value: Any) -> None:
        self._tool._state = value

    @property
    def services(self) -> Any:
        """Return the explicit Plan Tracer service graph.

        Services may collaborate through this composition root, for example
        ``self.services.history._snapshot_state()``.  Keeping the dependency
        visible at the call site avoids the mixin-era pattern where a method on
        ``self`` could be implemented by any other module.
        """

        return self._tool._services


T = TypeVar("T", bound=_PlanTrace2DHost)


@dataclass(slots=True)
class PlanTrace2DServices:
    """Composition root for the Plan Tracer feature services."""

    coordinates: Any
    overlay: Any
    selection: Any
    snap: Any
    snap_targets: Any
    sketch_sync: Any
    drawing: Any
    metrics: Any
    metric_rebuilders: Any
    dimensions: Any
    history: Any
    mode_state: Any
    rendering: Any
    patterns: Any
    motif_overlay: Any
    mesh_trace: Any
    selection_edit: Any
    duplicate: Any
    mirror: Any

    @classmethod
    def create(cls, tool: T) -> "PlanTrace2DServices":
        # Imports stay local to avoid cycles: service modules inherit from the
        # base class above, while the composition root needs the concrete classes.
        from .coordinate_mapper import PlanTrace2DCoordinateMapper
        from .dimensions import PlanTrace2DDimensionsService
        from .drawing import PlanTrace2DDrawingService
        from .history import PlanTrace2DHistoryService
        from .metric_rebuilders import PlanTrace2DMetricRebuilderService
        from .metrics import PlanTrace2DMetricsService
        from .mode_state import PlanTrace2DModeStateService
        from .overlay import PlanTrace2DOverlayService
        from .rendering import PlanTrace2DRenderingService
        from .motif_overlay import PlanTrace2DMotifOverlayService
        from .patterns import PlanTrace2DPatternService
        from .selection import PlanTrace2DSelectionService
        from .sketch_sync import PlanTrace2DSketchSyncService
        from .snap import PlanTrace2DSnapService
        from .snap_targets import PlanTrace2DSnapTargetsService
        from .mesh_trace import PlanTrace2DMeshTraceService
        from .selection_edit import PlanTrace2DSelectionEditService
        from .duplicate import PlanTrace2DDuplicateService
        from .mirror import PlanTrace2DMirrorService

        return cls(
            coordinates=PlanTrace2DCoordinateMapper(tool),
            overlay=PlanTrace2DOverlayService(tool),
            selection=PlanTrace2DSelectionService(tool),
            snap=PlanTrace2DSnapService(tool),
            snap_targets=PlanTrace2DSnapTargetsService(tool),
            sketch_sync=PlanTrace2DSketchSyncService(tool),
            drawing=PlanTrace2DDrawingService(tool),
            metrics=PlanTrace2DMetricsService(tool),
            metric_rebuilders=PlanTrace2DMetricRebuilderService(tool),
            dimensions=PlanTrace2DDimensionsService(tool),
            history=PlanTrace2DHistoryService(tool),
            mode_state=PlanTrace2DModeStateService(tool),
            rendering=PlanTrace2DRenderingService(tool),
            patterns=PlanTrace2DPatternService(tool),
            motif_overlay=PlanTrace2DMotifOverlayService(tool),
            mesh_trace=PlanTrace2DMeshTraceService(tool),
            selection_edit=PlanTrace2DSelectionEditService(tool),
            duplicate=PlanTrace2DDuplicateService(tool),
            mirror=PlanTrace2DMirrorService(tool),
        )


__all__ = ["PlanTrace2DServices"]
