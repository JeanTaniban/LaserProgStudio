# LaserProg v129 — Folding professional deformation

Folding now automatically refines sparse triangles inside the flexible strip
and offers explicit **Preserve internal structure** and **Uniform deformation**
behaviours. The first uses local edge-length constraints plus exact rigid
transport for small disconnected details; the second applies the analytic sweep
directly to all refined vertices. Metadata schema 5 persists the choice while
remaining compatible with previous Folding results.
