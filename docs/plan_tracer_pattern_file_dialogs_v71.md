# v71 — Plan Tracer pattern budget and native file dialogs

## Plan Tracer 2D Pattern limit

The hard-coded Pattern segment budgets were raised from the old low interactive
caps to a project preference:

- `Preferences > Laser engraving > Max Pattern segments`
- persisted as `laser.plan_tracer_pattern_max_segments`
- default: `120000`
- valid range: `1000` to `1000000`

The Plan Tracer shell copies this value into both preview and apply Pattern
budgets when the tool opens or resets. Direct Pattern generation also reads the
state budget instead of falling back to the old constants.

## Add thickness

The explicit Plan Tracer **Add** validation button now forces the sketch
extrusion depth to `Preferences > Laser engraving > Board thickness` immediately
before applying. This avoids stale depths stored in old drafts or edited Plan
Tracer objects.

## File dialogs

The bundled appearance preference now enables native system file dialogs by
default:

```json
{
  "force_dark_mode": true,
  "use_native_dialogs": true
}
```

This gives Windows users the full Explorer-style Open, Save and Export dialogs
instead of the compact Qt fallback. A checkbox was added to
`Preferences > Project > File explorer`. Changing this setting may require a
restart because Qt reads the native-dialog application attribute during startup.
