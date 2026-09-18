"""Stable aggregate module for the Plan 2D dimension API.

New sketch-like tools should import from ``laserprog_studio.tool_api.plan2d.dimensions``
or from the lazy package facade ``laserprog_studio.tool_api.plan2d``.
"""
from __future__ import annotations

from laserprog_studio.tool_api.plan2d.dimensions import *  # noqa: F401,F403
from laserprog_studio.tool_api.plan2d.dimensions import __all__ as _PLAN2D_DIMENSION_ALL

__all__ = list(_PLAN2D_DIMENSION_ALL)
