# Global performance pass V8

## Timing diagnosis

The whole-app audit showed that the visible jank was still concentrated in high-frequency UI work rather than in startup or file I/O:

- `qt.event_filter.5` / mouse-move event filtering accumulated tens of seconds over the session.
- Plan Tracer cursor rendering and actor synchronisation dominated the hot path during pointer movement.
- Scene/Creator UI repainting could still redo identical persistent actor work when nothing had changed.
- The global audit itself kept bounded samples using list slicing, which becomes unnecessary overhead during long high-frequency sessions.

## Changes

1. App performance audit storage now uses bounded deques instead of list slicing.
   This preserves aggregate timers and percentiles while avoiding O(n) list trims after the sample cap is reached.

2. Audit timeline recording is now sparse for sub-frame hot events.
   Fast repeated events still update timer statistics every time, but the human-readable timeline keeps slow events and periodic breadcrumbs.

3. Creator/Tool Core viewport painter now has a context signature cache.
   If handles, preview items and camera state are unchanged, it skips rebuilding PyVista overlay batches.

4. Incremental 3D scene rebuild now has an unchanged-scene fast path.
   If mesh signatures and actor maps already match, the rebuild request performs only the required style/gizmo/UI refresh instead of removing/re-adding actors.

5. The mesh list no longer clears/recreates itself when labels are unchanged.
   This avoids useless Qt list churn during conservative scene refreshes.

## Validation

Targeted regression/performance tests passed:

- Global performance audit
- Creator API performance contract
- Native interaction styles
- Creator UI native performance interaction
- Plan Tracer Motif overlay
- Plan Tracer pattern build
- Plan Tracer metric validate commit
- Plan Tracer performance cache fix
- Plan Tracer creator chain cache

