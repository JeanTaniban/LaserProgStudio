# Selection box overlay rendering

The native `ctx.selection_box` rectangle is painted with a small reusable Qt
child widget, not a fullscreen translucent overlay.

Why:

- fullscreen translucent children can black out QVTK/OpenGL viewports on some
  platforms;
- resizing a single widget to the current rectangle avoids covering the 3D view;
- repainting the old geometry prevents stale rectangles from accumulating.

Default activation remains:

```python
Shift + left drag
```

A plain left drag is reserved for camera orbit/navigation unless a tool opts into
a different activation policy.
