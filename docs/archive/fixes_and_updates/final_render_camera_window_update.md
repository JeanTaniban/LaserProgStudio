# Final render camera window update

- Interactive editor shadows are disabled.
- Real shadows are now available only through the dedicated **Rendu** button in the left View panel.
- The **Caméra** button stores the current editor camera as the render camera and displays a helper in the 3D scene.
- The render opens in a separate square window and uses that stored camera; if no render camera exists yet, it falls back to the current editor camera.

## Camera as scene object

- The **Caméra** button now creates/selects a real `Render Camera` object in the Parts hierarchy.
- This object is tagged as a scene helper, so it is visible/editable in the 3D editor but excluded from 3MF/engraving/final-render geometry.
- The standard Transform gizmos can move/rotate/scale it.
- The final render window reads the camera position/orientation from this object first, then falls back to the old stored state or the editor camera.
