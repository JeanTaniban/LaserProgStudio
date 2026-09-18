# LaserProg v87 — Plan Tracer circle/rectangle faces

This build repairs the Plan Tracer 2D arrangement face solver. A circle crossing or contained by a rectangle now creates stable, non-overlapping and independently selectable regions. Deleting one generated region suppresses only that region without destructively converting the authored circle into arcs.

The pinned Python 3.12.4 and runtime package versions from v86 are unchanged.
