# -*- coding: utf-8 -*-
from __future__ import annotations

from .layers import ENGRAVING_LAYERS, EngravingLayerSpec, get_engraving_layer, iter_export_layers
from .pipeline import EngravingExportPlan
from .roles import OUTLINE_COLOR, OUTLINE_ROLE, apply_default_outline_to_unassigned, mesh_has_explicit_engraving_role

__all__ = ["ENGRAVING_LAYERS", "EngravingLayerSpec", "get_engraving_layer", "iter_export_layers", "EngravingExportPlan", "OUTLINE_COLOR", "OUTLINE_ROLE", "apply_default_outline_to_unassigned", "mesh_has_explicit_engraving_role"]
