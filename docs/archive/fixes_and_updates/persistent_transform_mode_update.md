# Persistent transform mode update

Transform mode is now controlled explicitly by the user. Selecting, deselecting, opening tools, or deleting the selected part no longer forces the mode back to None.

Behavior:

- Press N to disable transform overlays.
- Press T/R/S to keep Translate/Rotate/Scale active.
- Empty-click selection clears the selected part and removes the current gizmo, but keeps the chosen transform mode active.
- Selecting another part recreates the same transform gizmo automatically.
- Deleting a selected or dragged part cancels the drag and clears the overlay, but does not switch the mode back to None.
