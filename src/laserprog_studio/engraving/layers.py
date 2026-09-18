# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LayerKind = Literal["cut", "engrave", "preview"]


@dataclass(frozen=True, slots=True)
class EngravingLayerSpec:
    id: str
    label: str
    kind: LayerKind
    export_suffix: str
    visible_by_default: bool = True


ENGRAVING_LAYERS: tuple[EngravingLayerSpec, ...] = (
    EngravingLayerSpec("cut", "Cut layer", "cut", "cut"),
    EngravingLayerSpec("engrave", "Engraving layer", "engrave", "engrave"),
    EngravingLayerSpec("composite", "Composite preview", "preview", "preview", visible_by_default=False),
)

_LAYER_BY_ID = {layer.id: layer for layer in ENGRAVING_LAYERS}


def get_engraving_layer(layer_id: str) -> EngravingLayerSpec:
    return _LAYER_BY_ID.get(layer_id, _LAYER_BY_ID["engrave"])


def iter_export_layers() -> tuple[EngravingLayerSpec, ...]:
    return tuple(layer for layer in ENGRAVING_LAYERS if layer.kind in {"cut", "engrave"})
