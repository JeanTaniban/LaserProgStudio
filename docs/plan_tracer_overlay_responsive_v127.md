# Plan Tracer v127 — responsive command overlay

## Cause of the overlap

The Command Deck builder caps the Plan Tracer overlay at 1240 px so it remains
inside a normal desktop viewport. After the **Curve** mode was added, the sum of
the fixed section widths became larger than the usable inner width. Qt still
created every section frame at its natural fixed size, so later cards painted on
top of earlier cards. In practice, **Measure** covered the right side of
**Shapes** and hid **Curve**.

## Correction

The Qt Command Deck renderer now computes a responsive width map before creating
section frames and buttons:

1. calculate every tile's natural width;
2. subtract section padding and inter-button/inter-section gaps from the real
   shell width;
3. keep all natural widths when they fit;
4. otherwise, consume only the label-safe reducible width, proportionally across
   the row;
5. use the same resolved width map for both section frames and button widgets;
6. apply a final pixel-by-pixel rounding pass so the row never exceeds the shell.

No command is hidden, moved to another section or made non-clickable. Vector
labels remain complete and the existing font fallback can still reduce the
caption size by one step where necessary.

## Regression coverage

The dedicated v127 test first confirms that the old natural fixed row is wider
than the available shell, then verifies that the responsive row fits exactly.
It also checks that **Curve** and **Dimension** are both present and that no tile
is reduced below its label-aware minimum.
