# Performance pass v9 — centralised viewport rendering

## Why

The global performance audits showed that many slow interactions were not caused
by one isolated algorithm.  The same user gesture could trigger several direct
`plotter.render()` calls from camera, gizmo, scene, preview and Plan Tracer
controllers.  On dense scenes this amplified the cost of VTK redraws and made
mouse movement stutter.

## Design

`laserprog_studio.rendering.render_scheduler.CentralRenderScheduler` is now the
single render gate for the main editor viewport.

The scheduler:

- patches the main `QtInteractor.render` method at viewport creation time;
- keeps the original PyVista render method as `_lps_original_render`;
- coalesces multiple render requests in the same Qt event burst;
- throttles normal editor renders to the configured frame interval;
- exposes explicit owner helpers:
  - `request_render(reason=...)`
  - `render_now(reason=...)`
  - `flush_render(reason=...)`
- records global audit counters/timers under `render.central.*`.

This means older code paths that still call `plotter.render()` are already routed
through the central scheduler, while newer code can use the owner helpers and
provide better diagnostic reasons.

## Conservative boundaries

This pass intentionally centralises only the main editor viewport.  Independent
render windows, such as the final render preview dialog, keep their own direct
rendering path because they are not part of the high-frequency modelling event
loop.

## New diagnostics

Useful counters/timers in `diagnostics/application_performance_audit.md`:

- `render.central.request`
- `render.central.queued`
- `render.central.coalesced`
- `render.central.throttled`
- `render.central.performed`
- `render.central.perform`
- `render.scheduler.patch_installed`

## Expected impact

The biggest expected improvement is during pointer-heavy interactions:

- camera movement;
- hover/highlight refresh;
- transform gizmo drag/release;
- Plan Tracer 2D cursor updates;
- scene rebuilds followed by UI/gizmo/style refreshes.

Instead of several expensive redraws per gesture, the UI should perform one
coalesced render at the next allowed frame.
