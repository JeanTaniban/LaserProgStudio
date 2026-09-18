# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .layers import EngravingLayerSpec, iter_export_layers


@dataclass(slots=True)
class EngravingExportPlan:
    """Layer-aware export plan for the future engraving workspace."""

    output_dir: Path
    layers: tuple[EngravingLayerSpec, ...] = field(default_factory=iter_export_layers)
    basename: str = "laserprog_export"

    def output_path_for(self, layer: EngravingLayerSpec) -> Path:
        return self.output_dir / f"{self.basename}_{layer.export_suffix}.png"
