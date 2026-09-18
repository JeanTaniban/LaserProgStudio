# Scale frame smart snap pass 28

The transform gizmo now extends Smart Snap to the square/bounds-frame scale handles.

Scope:

- enabled only when `Smart snap` is active;
- applies only to `scale_edge_*` handles, i.e. the square frame sides around the selection;
- does not apply to the X/Y/Z axis cube handles, which remain free-form one-axis scaling controls;
- works with the local scale axis used by the oriented scale frame;
- snaps the dragged side to another part's min/center/max projection on that local axis;
- keeps the opposite side fixed, then converts the snapped side position back into the scale factor.

This keeps the same useful part-to-part alignment/contact behavior as translation Smart Snap, but avoids making direct axis scaling sticky.
