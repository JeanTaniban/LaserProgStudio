# Pass68 — Logo and startup branding

This pass adds a first minimal LaserProg Studio logo and wires it into the app startup flow.

## Added
- `src/laserprog_studio/assets/logo.png`
- `src/laserprog_studio/assets/logo.ico`
- `src/laserprog_studio/assets/logo_assets.py`

## Integration
- The application now sets a window/app icon using the new logo asset.
- A lightweight `QSplashScreen` is shown at startup with the logo and a compact branded card.
- The main window also applies the icon so it appears in the top-left corner and taskbar.

## Notes
- The splash logic is defensive: if the splash cannot be created, startup continues normally.
- The logo loading helpers are lazy so non-GUI tests can import the asset module safely.
