# Pass58 - Scene tabs footer diagnostic and robust layout

- Replaced the footer scene tab host with direct footer-layout widgets instead of a QScrollArea.
- Added a permanent inert TEST tab for diagnostics so UI/logic issues can be separated.
- Real scene tabs are fixed-height Chrome-like widgets with explicit minimum widths.
- Kept the hidden QTabBar compatibility model for existing controller logic and tests.
