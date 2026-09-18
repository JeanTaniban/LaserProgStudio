# Layout stabilization pass 16

This pass fixes the main splitter model after the architecture migrations.

## User-visible contract

- In normal/non-Light UI, opening an inspector tool must not resize the left pane, the 3D viewport, or the right pane.
- If the right inspector is collapsed, opening a tool may temporarily open only the right pane.
- If full Light UI was active, tool close restores the previous collapsed Light UI sizes.
- During a tool, visible side panes stay protected by readable minimum widths and remain draggable.
- The center 3D toolbar must not impose a huge minimum width on the viewport; otherwise the left and right panes push each other.

## Implementation

A new pure policy object lives in:

```text
src/laserprog_studio/application/splitter_layout_policy.py
```

`LayoutController.ensure_inspector_open()` delegates splitter decisions to this policy. The key rule is conservative: if the right inspector is already visible and a tool opens, the controller keeps the current splitter sizes unchanged.

The 3D top toolbar is now hosted inside a horizontal `QScrollArea`. This prevents the toolbar's fixed-size buttons from becoming the minimum width of the whole center viewport, which was the main reason the side panes appeared to fight each other.

`_set_main_splitter_sizes_coalesced(..., save_full=False)` no longer schedules preference writes for temporary tool/light transitions.
