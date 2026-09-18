# Pass 71 — Toolbar limit, transparent logo, maximized startup and viewport mouse recovery

- Reduced the configurable top toolbar cap from 20 to 18 entries and bumped the toolbar preference registry version.
- Converted the baked white/grey logo background into a real alpha channel and regenerated the `.ico` asset from the transparent PNG.
- The main window now starts maximized instead of in a fixed 1500×900 window.
- Added an extracted `InteractionPointerRecoveryMixin` with a defensive viewport pointer-state reset: if Qt/VTK misses a mouse release, the app forces VTK left/middle/right button-up events on leave, focus loss, right-release, and no-button mouse moves after a drag. This prevents the stuck vertical mouse zoom state that previously required restarting the app.
- Added regression coverage for all four requested changes.
