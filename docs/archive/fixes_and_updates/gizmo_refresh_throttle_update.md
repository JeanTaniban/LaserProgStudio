# Gizmo refresh throttle update

This update reduces transform gizmo rebuilds during camera and transform interactions.

Changes:

- Removed live gizmo rebuilds on every mouse-wheel event.
- Removed live gizmo rebuilds during right-button pan; the overlay renderer already shares the main camera.
- Limited live orbit refresh to Scale mode only, because only the adaptive scale frame needs camera-dependent face switching.
- Increased the live gizmo rebuild interval from 24 ms to 180 ms.
- Kept one exact refresh at the end of transform drags and after wheel bursts.

Goal:

- Keep the adaptive scale frame usable.
- Keep the gizmo roughly attached during transform drags.
- Avoid the UI stutter caused by continuous overlay actor rebuilds.
