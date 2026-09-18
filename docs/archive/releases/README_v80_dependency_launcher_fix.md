# LaserProg v80 — Launcher dependency compatibility fix

This build fixes a v79 launch blocker where the Windows launcher rejected newer installed package versions in the user's central Python.

The dependency check now accepts package versions at or above the tested runtime floors. It still blocks missing packages and packages that are too old.

If v79 showed messages like `numpy installed=2.4.6 required=2.0.1` or `PySide6 installed=6.11.1 required=6.8.3`, use this v80 build instead.
