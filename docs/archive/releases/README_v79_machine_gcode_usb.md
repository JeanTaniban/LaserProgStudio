# LaserProg v79 — Machine G-code + USB manual focus

This build adds the first clean machine-facing section for Falcon A1 Pro style workflows.

Open it from:

- `Machine > Machine / G-code + USB...`
- or the engraving workspace button `Machine / G-code + USB`

Main additions:

- Falcon A1 Pro machine profile.
- Manual known-height focus settings.
- G-code export from the same geometry used by Falcon SVG.
- Hatch engraving for red fill geometry.
- Outline cutting for green geometry.
- Optional Z-step per cut pass for thick material.
- USB GRBL-style connection panel.
- Safe frame motion with `M5` laser off.
- Explicit confirmation before streaming laser-on G-code.

Autofocus is not triggered automatically in this version because the Falcon A1 Pro autofocus command is not hardcoded until it is identified safely from official configuration or a real USB capture.
