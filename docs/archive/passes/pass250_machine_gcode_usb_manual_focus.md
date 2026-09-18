# Pass 250 — Machine G-code + USB manual focus module

## Goal
Add a clean machine-facing section without mixing USB/G-code logic into the historical engraving exporter.

## Research notes
- Falcon A1 Pro exposes GRBL-style workflows over USB in the ecosystem, but autofocus is a Creality-specific command/macro and is not hardcoded here.
- Z-step per pass is a valid laser CAM concept for thick materials; the implementation keeps it explicit and opt-in.
- The first driver is USB GRBL-style only. Wi-Fi/Falcon proprietary protocol is deliberately not implemented.

## New architecture

```text
laserprog_studio/machine/
  profiles.py                    # Falcon A1 Pro machine profile
  gcode/
    models.py                    # manual focus + job settings dataclasses
    planner.py                   # geometry -> ordered toolpaths / hatches
    generator.py                 # toolpaths -> safe inspectable G-code
  transport/
    base.py                      # transport errors + serial port model
    serial_grbl.py               # optional pyserial GRBL streaming
  ui/
    machine_dialog.py            # Machine / Engraving dialog
```

Application integration:

```text
application/machine_controller.py
controllers/machine.py
ui/actions_menus.py
ui/layout_panels.py
```

## User-facing behavior
- New **Machine** menu.
- New **Machine / G-code + USB...** action.
- New button in the engraving workspace: **Machine / G-code + USB**.
- The dialog can:
  - export Falcon SVG,
  - generate G-code,
  - save G-code,
  - list USB serial ports,
  - connect to GRBL-style USB,
  - send `?`, `$I`, `$X`, `M5`,
  - frame the current job with laser off,
  - stream the current G-code after a confirmation.

## Safety model
- Autofocus is **not emitted** until the real Falcon A1 Pro command is known.
- Known-height mode asks for:
  - support/honeycomb height,
  - material thickness,
  - focus distance,
  - safety margin,
  - max focus depth,
  - optional Z step per pass.
- Unsafe Z-depth settings block USB sending.
- G-code comments include the manual focus model for inspection.
- The UI warns before any laser-on streaming.

## Validation
- `python -m pytest tests/test_machine_gcode_generator.py -q` → 3 passed.
- `python scripts/quality_gate.py` → OK.
