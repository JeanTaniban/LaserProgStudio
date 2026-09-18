# Texture projection aspect-ratio fix

This update makes the TEX projected-texture workflow more stable and predictable:

- projected images keep their original bitmap aspect ratio by default;
- a new **Keep image ratio** toggle is available in the Texture projection tool;
- clicking a mesh face now records the picked triangle and uses that face normal for planar projection;
- texture previews keep strong PyVista texture references to avoid blinking/disappearing after scene rebuilds;
- UV export now stores texture coordinates through several PyVista/VTK-compatible paths.

The tool still supports the old stretch behaviour by disabling **Keep image ratio**.
