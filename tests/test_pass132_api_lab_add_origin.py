# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab, LabActorKind, LabInteraction
from laserprog_studio.tool_core import ToolContext


def test_pass132_add_actor_button_places_point_at_world_origin_without_setup() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="test.pass132")

    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.GRABBABLE.value)
    snap = lab.add_from_options()

    assert snap.points == 1
    actor = next(actor for actor in ctx.selection.actors(owner_tool="test.pass132") if actor.id.startswith("api_lab:point_"))
    assert actor.points == ((0.0, 0.0, 0.0),)
    assert "origin" in snap.report.lower()


def test_pass132_add_actor_button_places_line_from_world_origin() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="test.pass132.line")

    lab.setup()
    lab.set_options(actor_kind=LabActorKind.LINE.value, interaction=LabInteraction.GRABBABLE.value)
    before = lab.snapshot().lines
    snap = lab.add_from_options()

    assert snap.lines == before + 1
    actor = next(
        actor
        for actor in ctx.selection.actors(owner_tool="test.pass132.line")
        if actor.id.startswith("api_lab:line_") and actor.points[0] == (0.0, 0.0, 0.0)
    )
    assert actor.points[1] == (18.0, 7.0, 0.0)
    assert actor.grabbable
