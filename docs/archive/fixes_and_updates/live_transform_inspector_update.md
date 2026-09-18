# Live transform inspector update

The Transform inspector no longer uses a local Apply button.

## Behavior

- Editing Position X/Y/Z immediately moves the active part center.
- Editing Rotation X/Y/Z immediately rotates the active part to the requested absolute session angle.
- Editing Size X/Y/Z immediately scales the active part bounds to the requested dimensions.
- The Reload button only refreshes the displayed values from the active part.

## Safety

Programmatic inspector refreshes block spin-box signals, so mesh updates do not recursively trigger more live updates.

Preview tools still keep their own Apply/Cancel workflow. Live transform edits are ignored while a preview is active to avoid accidentally committing preview meshes.
