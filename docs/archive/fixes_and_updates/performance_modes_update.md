# Performance modes update

This build adds two runtime profiles:

- **Mode optimisé** (default): minimal UI/file logging, throttled hover/resize overlay refresh, lighter TEX drag polling.
- **Mode debug / logs détaillés**: restores detailed diagnostic logging and tighter interaction polling for bug hunts.

The mode can be changed from `View > Performance`.

Environment variables:

- `LPS_PERF_MODE=debug` starts in debug mode.
- `LPS_VERBOSE_DIAG=1` also starts in debug mode.
- `LPS_OPTIMIZED_FILE_LOG=1` keeps more log-file echo in optimized mode.
- `LPS_UI_LOG_MAX_BLOCKS=<n>` changes the visible log line cap.
