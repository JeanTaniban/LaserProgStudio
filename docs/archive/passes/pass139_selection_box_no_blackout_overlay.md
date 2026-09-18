# Pass139 – Selection Box no-blackout overlay

This pass fixes the selection rectangle overlay used by the native Creator API
box-selection service.

## Problem

The Pass138 overlay stopped stale rectangle accumulation by using one fullscreen
transparent widget and clearing it before every repaint. On some Qt/OpenGL/VTK
combinations, a fullscreen translucent child widget over the 3D viewport can be
composited with a black backing store during drag. The rectangle still works,
but the 3D viewport becomes black while selecting.

## Fix

`SelectionBoxOverlay` is now a single reusable child widget that only occupies
the current rubber-band rectangle. Before the widget moves or hides, it asks the
parent viewport to repaint the previous geometry. This keeps the anti-stacking
behavior without placing a fullscreen translucent widget over the OpenGL area.

## Interaction policy

Native box selection remains `Shift + left drag` by default so normal left-drag
camera orbit remains available.
