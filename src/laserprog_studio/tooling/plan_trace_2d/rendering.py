# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from .services import _PlanTrace2DService

class PlanTrace2DRenderingService(_PlanTrace2DService):
    def _sync_overlays(self, ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        if owner is None:
            return
        try:
            from laserprog_studio.application.creator_viewport_ui import sync_creator_overlay_windows

            sync_creator_overlay_windows(owner, ctx)
        except Exception:
            pass

    def _render(self, ctx: Any, *, sync_overlays: bool = False, render: bool = True) -> None:
        with _measure_perf(ctx, "plan_trace.render"):
            try:
                from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

                record_projected_overlay_event("plan_trace.render.before", owner=getattr(ctx, "owner", None), ctx=ctx, owner_tool=self.id, manager=getattr(ctx, "projected_drawing", None), render=bool(render), sync_overlays=bool(sync_overlays))
            except Exception:
                pass
            try:
                ctx.projected_drawing.for_tool(self.id).render(render=render)
                try:
                    from laserprog_studio.diagnostics.projected_overlay_debug import projected_overlay_renderer_snapshot, record_projected_overlay_event

                    record_projected_overlay_event("plan_trace.render.after", owner=getattr(ctx, "owner", None), ctx=ctx, owner_tool=self.id, manager=getattr(ctx, "projected_drawing", None), renderer_state=projected_overlay_renderer_snapshot(getattr(ctx, "owner", None), self.id), render=bool(render))
                except Exception:
                    pass
            except Exception as exc:
                try:
                    from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

                    record_projected_overlay_event("plan_trace.render.exception", owner=getattr(ctx, "owner", None), ctx=ctx, owner_tool=self.id, manager=getattr(ctx, "projected_drawing", None), error=exc, render=bool(render))
                except Exception:
                    pass
                if render:
                    try:
                        ctx.request_full_render()
                    except Exception:
                        pass
            if sync_overlays:
                self._sync_overlays(ctx)


def _measure_perf(ctx: Any, name: str) -> Any:
    profiler = getattr(ctx, "profiler", None)
    measure = getattr(profiler, "measure", None)
    if callable(measure):
        try:
            return measure(str(name))
        except Exception:
            pass
    return nullcontext()


__all__ = ["PlanTrace2DRenderingService"]
