# Performance / overlay cleanup pass

Changes:

- High-volume diagnostic logs are disabled by default. Set `LPS_VERBOSE_DIAG=1` to restore detailed traces.
- The on-screen QTextEdit log is bounded to avoid unbounded memory/layout cost.
- The global QApplication event filter is installed only during an active TEX gizmo drag.
- Light UI read-only checks no longer save layout preferences or schedule timers.
- Programmatic splitter no-op changes no longer schedule overlay syncs.
- Gizmo main-renderer fallback actors are tracked by name and removed defensively.
- TEX polar polling is reduced to 30 fps to avoid excessive preview rebuilds.
