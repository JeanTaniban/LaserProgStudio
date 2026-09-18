# v69 — English-only UI pass

LaserProg's visible UI is now standardized in English.

## Scope

- Preferences section names, labels, helper text, and the Boolean Subtract clearance field.
- Right-click scene menu and primitive board feedback.
- Plan Tracer validation actions: Add / Subtract.
- Plan Tracer existing-sketch prompt: Edit / New sketch / Cancel.
- Plan Tracer Pattern panel, Pattern overlay, pattern names, tooltips, statuses, and inspector help.
- Benchmark progress messages and several legacy status popups.

## Guardrail

`tests/test_pass314_ui_language_english_only.py` scans high-visibility UI files for French labels, accented French strings, and common French UI terms so future patches do not reintroduce mixed-language text.
