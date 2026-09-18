# Forced dark Qt mode — v20

LaserProg Studio now applies a deterministic dark Qt theme before any window is
created.  It no longer follows the Windows light/dark preference while the
setting below is enabled.

## Setting

`settings/studio_appearance.json`:

```json
{
  "force_dark_mode": true,
  "use_native_dialogs": true
}
```

- `force_dark_mode: true` is the default.
- `use_native_dialogs: true` lets Windows/macOS/Linux show native file dialogs for
  roomier Open, Save and Export workflows. Disable it only if you explicitly
  prefer compact Qt-owned dialogs that follow the forced dark palette.

Temporary process overrides are also available:

- `LPS_FORCE_DARK_MODE=0` disables forced dark mode for one run.
- `LPS_USE_NATIVE_DIALOGS=0` forces compact Qt-owned dialogs for one run.

The theme applies a Fusion style, a full `QPalette`, a global fallback
stylesheet, and a color-scheme hint.  An application event filter reapplies the
palette if Windows sends a later theme-change notification.
