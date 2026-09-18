# Texture projection polar gizmo update

The TEX rotation ring now behaves as a polar control:

- tangential mouse movement around the decal centre updates texture rotation;
- radial movement away from or toward the centre updates texture scale;
- the update is incremental, using the previous mouse sample as the reference, matching the behaviour of transform gizmos;
- logs now use `[TEXTURE_GIZMO] polar ...` and include angular delta, radius ratio and scale changes.

This lets the user rotate and resize a texture decal with the same ring control.
