"""Stable alias module for the Plan 2D drawing API.

New tools should import ``laserprog_studio.tool_api.plan2d`` or its focused
submodules.  This module remains as a supported alias for Plan
Tracer-style code and examples.
"""
from __future__ import annotations

from laserprog_studio.tool_api.plan2d.actors import *  # noqa: F401,F403
from laserprog_studio.tool_api.plan2d.actors import __all__ as _ACTOR_ALL
from laserprog_studio.tool_api.plan2d.plane import *  # noqa: F401,F403
from laserprog_studio.tool_api.plan2d.plane import __all__ as _PLANE_ALL
from laserprog_studio.tool_api.plan2d.snap import *  # noqa: F401,F403
from laserprog_studio.tool_api.plan2d.snap import __all__ as _SNAP_ALL
from laserprog_studio.tool_api.plan2d.plane import sample_plan_arc_xy as _sample_plan_arc_xy


def sample_plan_arc_xy(*args, **kwargs):
    """Stable wrapper for ``tool_api.plan2d.plane.sample_plan_arc_xy``."""

    return _sample_plan_arc_xy(*args, **kwargs)

__all__ = sorted(set([*_ACTOR_ALL, *_PLANE_ALL, *_SNAP_ALL]))
