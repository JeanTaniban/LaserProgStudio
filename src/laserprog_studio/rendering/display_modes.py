# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DisplayModeId = Literal["wireframe", "solid", "material"]


@dataclass(frozen=True)
class DisplayModeSpec:
    id: DisplayModeId
    label: str
    default_show_edges: bool
    use_lighting: bool
    use_materials: bool
    representation: str = "surface"

    @property
    def show_edges(self) -> bool:
        # Stable alias used by existing tests/controllers. New code
        # should prefer default_show_edges plus the user edge toggle.
        return self.default_show_edges


DISPLAY_MODES: tuple[DisplayModeSpec, ...] = (
    # LaserProg's historical "wireframe" is an edged surface view: faces stay
    # visible and triangle edges are drawn over them.
    DisplayModeSpec("wireframe", "Wireframe", default_show_edges=True, use_lighting=True, use_materials=False),
    DisplayModeSpec("solid", "Solide", default_show_edges=False, use_lighting=True, use_materials=False),
    DisplayModeSpec("material", "Materials", default_show_edges=False, use_lighting=True, use_materials=True),
)

_DISPLAY_BY_ID = {mode.id: mode for mode in DISPLAY_MODES}


def get_display_mode(mode_id: str) -> DisplayModeSpec:
    return _DISPLAY_BY_ID.get(mode_id, _DISPLAY_BY_ID["wireframe"])
