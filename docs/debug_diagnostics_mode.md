# Debug diagnostics mode

LaserProg must stay fluid by default.  Normal editing runs in **Optimized mode** with high-volume diagnostics disabled.

## User control

Use **View > Performance / Debug**:

- **Optimized mode — diagnostics OFF**: default for normal work.  Hot-path JSONL traces, application-wide timing samples and automatic diagnostic exports are disabled.
- **Debug diagnostics mode — ON**: enable only while reproducing a bug or performance issue.  Diagnostics may write files in `diagnostics/` and may record per-event timings.

The state is stored in `settings/studio_debug.json`.  It can also be forced for a session with environment variables such as `LASERPROG_DEBUG_MODE=1` or `LPS_PERF_MODE=debug`.

## Rule for future diagnostics

Every new diagnostic feature must pass through the shared gate:

```python
from laserprog_studio.services.debug_mode import should_record_diagnostics

if not should_record_diagnostics(owner):
    return
```

For global, owner-less diagnostics:

```python
from laserprog_studio.services.debug_mode import is_debug_mode_enabled

if not is_debug_mode_enabled():
    return
```

Do not add unconditional hot-path disk writes, JSONL appends, performance counters, `time.perf_counter()` wrappers, or automatic process-exit exports.  Manual project saves, autosaves, user exports, persistent preferences, and crash/error logs are not debug diagnostics and may remain outside this gate.

## Existing gated systems

- Application performance audit (`diagnostics/application_performance_audit.md`)
- Tool `ToolProfiler` timings and global audit mirroring
- Cloth workflow trace (`diagnostics/cloth_workflow_debug.jsonl`, `.json`, `.md`)
- Plan Tracer input JSONL (`diagnostics/plan_trace_input_debug.jsonl`)
- Plan Tracer Motif overlay JSONL (`diagnostics/plan_trace_2d_motif_overlay_debug.jsonl`)
- Transform Gizmo JSONL (`diagnostics/transform_gizmo_debug.jsonl`)
- Overlay edit JSONL (`diagnostics/overlay_edit_events.jsonl`)
- Joint Builder debug logs

When Debug Mode is OFF, these systems return immediately and do not create/append diagnostic files.
