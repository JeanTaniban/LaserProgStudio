# Pass 309 — Plan Tracer Pattern presets and enum selector

## Goal

Make the Pattern overlay faster to navigate and allow reusable named parameter
sets without duplicating project geometry.

## State model

```text
CUSTOM / MODIFIED
  -- Save preset(name) --> SAVED PRESET
  -- Select preset -----> SAVED PRESET

SAVED PRESET
  -- Change kind/parameter/offset --> CUSTOM / MODIFIED
  -- Save same name -------------> SAVED PRESET (updated)
  -- Delete ----------------------> CUSTOM / MODIFIED
```

A saved preset contains:

```text
name + pattern kind
+ cell size + wall + margin + keep form
+ angle + aspect + seed + offset X + offset Y
```

## Persistence

User presets are written atomically to:

```text
settings/plan_trace_2d_pattern_presets.json
```

Names are matched case-insensitively. Saving a name that already exists updates
it instead of producing a duplicate.

## Overlay API

`OverlayFieldSpec(kind="select")` is now rendered as a native Qt combo box.
Each option may be either a plain string or a `(stable_value, display_label)`
pair. Tool callbacks receive the stable value, not the translated label.

## Validation

- Pattern/preset targeted tests: 76 passed.
- Preset and overlay-selector tests: 33 passed.
- Architecture quality gate: OK.
