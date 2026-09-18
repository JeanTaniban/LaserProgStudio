# Pass 285 — Plan Tracer labelled compact toolbar polish

The previous constraints fix made the Plan Tracer overlay compact, but it also
made the vector toolbar icon-only. This pass restores visible tool captions while
keeping the API-owned auto-fit path responsible for sizing.

Changes:
- Vector toolbar slots are now label-aware instead of icon-only.
- Plan Tracer remains on `width_px=0`; the overlay API computes the final width.
- Auto-fit includes real row spacing and semantic separator width.
- Qt vector buttons keep real button text for painting/accessibility, while still
  using fixed slot sizes so stylesheet minimums cannot stretch the toolbar back
  into the old 920px ribbon.
- The vector painter uses a tighter icon-over-caption layout and elides labels
  defensively if a third-party caption is too long.
- Regression coverage added in `test_pass285_plan_tracer_toolbar_labels.py`.
