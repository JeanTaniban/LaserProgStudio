# -*- coding: utf-8 -*-
"""Machine-facing laser job tools.

This package is intentionally separate from the historical engraving exporter:
``engraving`` converts meshes into 2D manufacturing geometry, while ``machine``
turns that geometry into a safe, inspectable job and optionally streams it to a
controller.
"""
from __future__ import annotations

from .profiles import FALCON_A1_PRO_PROFILE, MachineProfile

__all__ = ["FALCON_A1_PRO_PROFILE", "MachineProfile"]
