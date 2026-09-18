# Window refactor pass 12 — Lay flat selection policy

## Change

`Lay flat` is a scene-level arrangement/preparation tool. It can operate without a
preselected mesh, so its tool registry entry now uses:

```python
selection_policy="none"
```

This matches the behavior already applied to `Primitives` and `Engraving roles`.

## Guard rails

The extension architecture tests and `scripts/verify_refactor_structure.py` now
assert that `Primitives`, `Lay flat`, and `Engraving roles` do not require a
selection before opening.
