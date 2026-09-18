# Pass 242 — Vent Generator apply preflight

Vent Generator now validates the final Apply action through the Creator API before the application tries to stage the generated mesh.

Changes:

- added `tooling/vent_generator/apply_validation.py`;
- added an `Apply check` inspector field;
- connected invalid route/profile/opening states to inspector field errors;
- preflights the actual final mesh on Apply;
- clears the rectangular-only fill option when switching to a round pipe;
- added `tests/test_pass242_vent_generator_apply_preflight.py`.

Validation:

- `python scripts/quality_gate.py` OK;
- `python -m pytest -q` OK: 887 passed, 3 skipped.
