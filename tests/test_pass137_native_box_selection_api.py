# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from laserprog_studio.tool_api import actors
from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab, LabActorKind, LabInteraction
from laserprog_studio.tool_api.selection_box import BoxSelectionInsidePolicy, BoxSelectionMode, BoxSelectionTarget
from laserprog_studio.tool_core import ToolContext


def _identity_screen(point):
    return (float(point[0]), float(point[1]))


def test_pass137_box_selection_selects_tool_actors_lines_and_ignores_fixed() -> None:
    ctx = ToolContext()
    owner = "test.pass137"
    registry = ctx.actor_registry(owner)
    fixed = registry.add(actors.point("fixed", (4, 4, 0), interaction="fixed"))
    point = registry.add(actors.point("selectable", (10, 10, 0), interaction="selectable"))
    line = registry.add(actors.line("line", (20, 5, 0), (35, 5, 0), interaction="grabbable"))

    ctx.selection_box.configure(
        enabled=True,
        targets=[BoxSelectionTarget.TOOL_ACTORS],
        mode=BoxSelectionMode.REPLACE,
        inside_policy=BoxSelectionInsidePolicy.PARTIAL,
        owner_tool=owner,
        selectable_only=True,
    )
    ctx.selection_box.begin((0, 0))
    assert ctx.selection_box.update((28, 16))
    result = ctx.selection_box.finish((28, 16), world_to_screen=_identity_screen)

    assert result.completed
    assert fixed.id not in result.tool_actor_ids
    assert point.id in result.tool_actor_ids
    assert line.id in result.tool_actor_ids
    assert set(ctx.selection.ids()) == {point.id, line.id}


def test_pass137_box_selection_modes_add_subtract_and_toggle() -> None:
    ctx = ToolContext()
    owner = "test.pass137.modes"
    registry = ctx.actor_registry(owner)
    a = registry.add(actors.point("a", (2, 2, 0), interaction="selectable"))
    b = registry.add(actors.point("b", (12, 2, 0), interaction="selectable"))

    ctx.selection_box.configure(enabled=True, targets=["tool_actors"], owner_tool=owner, mode="replace")
    ctx.selection_box.begin((0, 0)); ctx.selection_box.update((5, 5)); ctx.selection_box.finish((5, 5), world_to_screen=_identity_screen)
    assert ctx.selection.ids() == (a.id,)

    ctx.selection_box.configure(mode="add")
    ctx.selection_box.begin((10, 0)); ctx.selection_box.update((15, 5)); ctx.selection_box.finish((15, 5), world_to_screen=_identity_screen)
    assert set(ctx.selection.ids()) == {a.id, b.id}

    ctx.selection_box.configure(mode="subtract")
    ctx.selection_box.begin((0, 0)); ctx.selection_box.update((5, 5)); ctx.selection_box.finish((5, 5), world_to_screen=_identity_screen)
    assert ctx.selection.ids() == (b.id,)

    ctx.selection_box.configure(mode="toggle")
    ctx.selection_box.begin((0, 0)); ctx.selection_box.update((15, 5)); ctx.selection_box.finish((15, 5), world_to_screen=_identity_screen)
    assert ctx.selection.ids() == (a.id,)


@dataclass
class _Mesh:
    name: str
    points: list[tuple[float, float, float]]
    mesh_id: str = ""


class _Store:
    def __init__(self) -> None:
        self.committed_meshes = [
            _Mesh("inside", [(1, 1, 0), (4, 1, 0), (1, 4, 0)], mesh_id="inside"),
            _Mesh("outside", [(50, 50, 0), (60, 50, 0), (50, 60, 0)], mesh_id="outside"),
        ]
        self._selected_mesh_indices: list[int] = []

    @property
    def selected_mesh_indices(self):
        return tuple(self._selected_mesh_indices)

class _Scene:
    def __init__(self) -> None:
        self.model_store = _Store()


def test_pass137_box_selection_can_target_scene_objects_separately() -> None:
    ctx = ToolContext()
    ctx.document.bind(_Scene())
    ctx.selection_box.configure(
        enabled=True,
        targets=[BoxSelectionTarget.SCENE_OBJECTS],
        mode=BoxSelectionMode.REPLACE,
        inside_policy=BoxSelectionInsidePolicy.PARTIAL,
        clear_on_empty=True,
    )
    ctx.selection_box.begin((0, 0)); ctx.selection_box.update((10, 10))
    result = ctx.selection_box.finish((10, 10), world_to_screen=_identity_screen)

    assert result.scene_object_indices == (0,)
    assert result.scene_object_ids == ("inside",)
    assert ctx.scene_selection.selected_indices() == (0,)
    assert ctx.selection.ids() == ()


def test_pass137_diagnostic_lab_exposes_box_selection_options_and_result() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diag")
    lab.setup()
    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.SELECTABLE.value, box_enabled="enabled", box_target="tool_actors", box_mode="replace", box_inside_policy="partial")
    added = lab.add_actor(LabActorKind.POINT, LabInteraction.SELECTABLE, position=(3, 3, 0.42))
    result = lab.box_select((0, 0), (8, 8), world_to_screen=_identity_screen)

    assert added.id in result.tool_actor_ids
    assert ctx.selection.is_selected(added.id)
    assert ctx.selection_box.config.enabled
    assert ctx.selection_box.config.targets == (BoxSelectionTarget.TOOL_ACTORS,)


def test_pass137_tool_core_diagnostic_panel_mentions_box_selection() -> None:
    source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])

    assert "box_enabled" in source
    assert "box_target" in source
    assert "box_mode" in source
    assert "selection_box.finish" in controller
    assert "SelectionBoxOverlay" in controller
