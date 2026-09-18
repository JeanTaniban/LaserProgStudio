# -*- coding: utf-8 -*-
from __future__ import annotations

# Keep the package import lightweight.  The tooling registry imports the Plan
# Tracer shell at application startup; importing every concrete service here can
# pull the public tool_api facade while the registry is still initialising.  The
# composition root imports concrete services lazily in PlanTrace2DServices.create().
from .services import PlanTrace2DServices
from .state import _PlacementMetricDraft, _PlanTrace2DState, _PlanTrace2DSnapshot

__all__ = [
    "PlanTrace2DServices",
    "_PlacementMetricDraft",
    "_PlanTrace2DState",
    "_PlanTrace2DSnapshot",
]
