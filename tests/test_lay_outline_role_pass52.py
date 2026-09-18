# -*- coding: utf-8 -*-
from __future__ import annotations

import _path_setup  # noqa: F401

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.domain.material import EngravingSettings
from laserprog_studio.engraving.roles import OUTLINE_COLOR, apply_default_outline_to_unassigned


def mesh(name: str, color: str = "#B8B8B8") -> WorkMesh:
    return WorkMesh(name, [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], color=color)


def test_default_outline_role_applies_only_to_unassigned_meshes() -> None:
    unassigned = mesh("unassigned")
    already_outline = mesh("outline", OUTLINE_COLOR)
    already_fill = mesh("fill", "#E53935")
    explicit_role = mesh("explicit")
    explicit_role.engraving = EngravingSettings(role="fill", layer="engrave")

    changed = apply_default_outline_to_unassigned([unassigned, already_outline, already_fill, explicit_role])

    assert changed == 1
    assert unassigned.color == OUTLINE_COLOR
    assert unassigned.engraving.role == "outline"
    assert already_outline.color == OUTLINE_COLOR
    assert already_fill.color == "#E53935"
    assert explicit_role.engraving.role == "fill"
