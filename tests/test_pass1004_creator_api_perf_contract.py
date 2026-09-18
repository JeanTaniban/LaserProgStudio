# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import actors
from laserprog_studio.tool_api.gizmos import refresh_creator_ui_drag
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.gizmos import GizmoHandle


class _CountingSelection:
    def __init__(self, wrapped):
        self._wrapped = wrapped
        self.actors_calls = 0

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    def actors(self, *args, **kwargs):
        self.actors_calls += 1
        return self._wrapped.actors(*args, **kwargs)


def test_pass1004_changed_actor_refresh_uses_direct_lookup_not_owner_scan() -> None:
    ctx = ToolContext()
    owner = "perf.contract"
    for index in range(80):
        ctx.actor_registry(owner).add(
            actors.point(f"p{index}", (float(index), 0.0, 0.0), interaction="grabbable", metadata={"motif_family": "plan_trace_2d", "motif_kind": "handle"}),
            replace=True,
        )
        ctx.gizmos.create_handle(GizmoHandle(id=f"p{index}", owner_tool=owner, position=(float(index), 0.0, 0.0)))

    ctx.selection = _CountingSelection(ctx.selection)
    refresh_creator_ui_drag(ctx, owner_tool=owner, changed_actor_ids=("p37",), render=False, return_snapshot=False)

    assert ctx.selection.actors_calls == 0
    assert ctx.selection.state.dirty_visual_handle_ids == ("p37",)


def test_pass1004_gizmo_manager_has_direct_handle_lookup() -> None:
    ctx = ToolContext()
    ctx.gizmos.create_handle(GizmoHandle(id="h", owner_tool="owner.a", position=(1.0, 2.0, 3.0)))

    assert ctx.gizmos.handle("h", owner_tool="owner.a").position == (1.0, 2.0, 3.0)
    assert ctx.gizmos.handle("h", owner_tool="other") is None
    assert ctx.gizmos.handle("missing") is None


def test_pass1004_docs_explain_hot_path_cache_contract() -> None:
    docs = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "docs/tool_creator/README.md",
            "docs/tool_creator/09_creator_api_checklist.md",
            "docs/tool_creator/19_performance_contract.md",
        )
    )
    assert "ctx.document.bind" in docs
    assert "viewport projection" in docs
    assert "scene_cache.snap.rebuild_screen_index" in docs
    assert "full UI rebuild" in docs
