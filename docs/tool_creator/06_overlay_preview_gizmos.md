# 06 - Overlay, preview and gizmos

Use these layers for viewport feedback. The visual vocabulary must stay aligned with Tool Core Analysis through the public `tool_api` motif layer:

- `ctx.preview`: temporary geometry such as lines, polylines, faces, text and meshes;
- `ctx.gizmos`: persistent handles with shared hover/grab/selected styling;
- `ctx.overlay`: floating panels, popovers, tooltips and contextual controls.

The public catalog and direction helpers for these UI families are exposed from `laserprog_studio.tool_api.gizmos`:

```python
from laserprog_studio.tool_api.gizmos import (
    iter_creator_ui_families,
    creator_ui_direction_markdown,
)

for family in iter_creator_ui_families():
    print(family.id, family.label)

print(creator_ui_direction_markdown())
```

The rule is semantic control, not custom paint code. A tool should ask for an official actor, line preview, manipulator, handle style or popover; the shared layer chooses the consistent visual implementation. Interaction and camera adaptation are also semantic and native: `CreatorStudioToolAdapter` runs the API runtime automatically for registered actors, uses the drag fast path internally, and refreshes axis-locked orientation plus field-of-view scale once after camera movement. Normal tool code does not call the runtime or refresh helpers directly. The lower-level `hover_select_grab_actors(...)` policy and `refresh_creator_ui_camera(...)` helper are kept for tests, adapters and renderer bridges, not for production tool code.

Recommended flow:

```python
from laserprog_studio.tool_api import actors

ctx.actor_registry(tool_id).add(
    actors.point(
        "demo.anchor",
        (0, 0, 0),
        owner_tool=tool_id,
        interaction="grabbable",
        point_style="target",
        line_style="grabbable",
    )
)
ctx.preview.show_line("demo.axis", tool_id, (0, 0, 0), (100, 0, 0), line_style="axis")
ctx.gizmos.translate("demo.move", owner_tool=tool_id, origin=(0, 0, 0))
ctx.overlay.show_tooltip("demo.tip", owner_tool=tool_id, text="Drag a selected point", cursor_px=(20, 20))
ctx.request_light_render()
```

Direct `ctx.gizmos.create_handle(...)` usage is lower-level. Use it only with official `style_id` values and shared style resolution; do not invent new point shapes, colors or local PyVista/Qt UI. During interaction, keep handles/previews persistent and let the native adapter update actor state and choose the optimized refresh path; do not clear and rebuild all motifs.

Tool-owned overlays are lifecycle state. When a `CreatorTool` closes or cancels, `ctx.cleanup_tool(tool_id, include_persistent_overlays=True)` closes its overlay specs and the host synchronises Qt overlay widgets immediately. A normal tool should therefore prefer the Creator lifecycle cleanup instead of hiding widgets by hand.

```python
class MyTool(CreatorTool):
    id = "example.my_tool"

    def on_open(self, ctx):
        ctx.overlay.show_tooltip(
            "example.my_tool.tip",
            owner_tool=self.id,
            text="Drag the official handle",
            cursor_px=(20, 20),
        )

    # No manual Qt cleanup: CreatorTool.close/cancel calls ctx.cleanup_tool(...).
```

Low-level cleanup remains available for tests and adapters:

```python
ctx.preview.clear_tool(tool_id)
ctx.gizmos.clear_tool(tool_id)
ctx.overlay.close_tool_windows(tool_id, include_persistent=True)
```

After overlay visibility changes, the API/runtime syncs the Qt overlay layer. Do not keep references to overlay widgets, do not call `raise_()` manually, and do not implement local drag widgets. The native overlay adapter owns the whole overlay runtime: drag capture, z-order, clamping, collision avoidance and final position commit. Draggable overlays are kept non-overlapping by default. This is deliberate: Qt child widgets are rectangular, z-ordered surfaces, and translucent overlapping child widgets are prone to repaint artifacts. The runtime therefore separates palettes/popovers instead of letting one draggable overlay pass through another.

Overlay drag uses a fast path: direct `QWidget.move(...)` while the mouse is moving, no layout rebuild, no manager resync and no parent repaint loop on every event. The declarative `OverlayManager` position is committed when the drag ends. If the overlay hits a viewport edge or another overlay, the runtime uses a native **soft-wall** policy: the overlay is constrained like it hit a physical wall and the blocked pointer delta is absorbed by rebasing the drag origin. The OS cursor is never warped during overlay drag, because cursor warping can stutter and can leave platform mouse capture in a bad state. If a constrained movement lets the pointer leave the real overlay rectangle, the runtime cancels the drag immediately, commits the current overlay position, clears the pointer offset and swallows the matching release event. This avoids a stale grab offset while keeping the next click/drag clean.

At drag release or drag cancellation, the runtime performs one bounded **release redraw**. It temporarily exposes the overlay dirty region, repaints the backing viewport, then repaints the overlay itself. This cleanup is intentionally not done during every mouse move, so the drag remains smooth while translucent-overlay traces over the 3D viewport are removed as soon as the drag ends. Tool code must not call Qt `repaint()`, `update()`, `hide()` or `show()` to fix overlay traces; this is owned by the native overlay adapter.

The built-in **Gizmo catalog** tool (`gizmo_catalog`) now displays only the new non-interactive projected drawing 2D API. Interactive Creator motifs remain documented and validated through Tool Core Analysis rather than being instantiated in that catalog. See `16_gizmo_catalog_tool.md`.

## Hot path and cache policy

During a drag, keep the Creator UI on the hot path: register `ToolActor` objects and let `CreatorStudioToolAdapter` move them through the native runtime. The adapter calls the drag refresh internally and the shared renderer mutates only the cached mesh ranges for moved handles/previews. Do not call full motif rebuilds, do not rebuild the snap cache, and do not resync static overlays on every mouse move. During empty camera pan/orbit, the bridge skips Creator UI hit-testing entirely until release, then one camera refresh updates orientation/scale.

Visibility toggles are API state, not manual cleanup. A hidden UI family remains registered for fast Show all / Hide all, but its actors are marked non-visible to the API hit-test path.

## Overlay button styles

Overlay buttons are declarative API state. Tools should pick the semantic style they need and let the shared Qt adapter render the visual treatment. Use `overlay_kind="toolbar"` for compact mode strips, and use `ToolButtonSpec(style=...)` for the button intent:

```python
from laserprog_studio.tool_core.overlay import OverlayWindowSpec, ToolButtonSpec

ctx.overlay.show_window(
    OverlayWindowSpec(
        id="example.toolbar",
        title="",
        owner_tool=tool_id,
        overlay_kind="toolbar",
        anchor="viewport_top_left",
        width_px=520,
        fields=[],
        buttons=[
            ToolButtonSpec("example.mode.modify", "Modify", checkable=True, checked=True, group="example.mode", style="mode"),
            ToolButtonSpec("example.mode.line", "Line", checkable=True, group="example.mode", style="mode"),
            ToolButtonSpec("example.snap", "Smart snap", checkable=True, style="toggle"),
            ToolButtonSpec("example.reset", "Reset", style="ghost"),
            ToolButtonSpec("example.delete", "Delete", style="danger"),
        ],
    )
)
```

Supported styles are `auto`, `primary`, `secondary`, `ghost`, `toggle`, `mode`, `danger` and `icon`. The `auto` style resolves grouped checkable buttons to `mode`, standalone checkable buttons to `toggle`, destructive buttons to `danger`, icon-only buttons to `icon`, and normal actions to `secondary`. Exclusive selection state is owned by `OverlayManager.set_group_active(...)` / `toggle_button(...)`; tool code should not manage checked Qt widgets directly.

For compact CAD/drawing toolbars, prefer the higher-level builder instead of manually assembling fields and buttons. This keeps the mode badge, exclusive group, action buttons and active checked state in the shared overlay API:

```python
from laserprog_studio.tool_core.overlay import (
    OverlayActionSpec,
    OverlayModeSpec,
    build_mode_toolbar_window,
)

ctx.overlay.show_window(
    build_mode_toolbar_window(
        window_id="example.toolbar",
        owner_tool=tool_id,
        group_id="example.mode",
        modes=(
            OverlayModeSpec("example.mode.modify", "Modify", icon="sketch.modify", shortcut="Esc"),
            OverlayModeSpec("example.mode.line", "Line", icon="sketch.line"),
        ),
        active_mode_id="example.mode.line",
        actions=(OverlayActionSpec("example.delete", "Delete", icon="sketch.delete", shortcut="Del"),),
        badge_id="example.mode_badge",
        badge_value="Line",
        width_px=520,
    )
)
```

A tool should only react to semantic ids such as `example.mode.line` or `example.delete`; the API owns the visual toolbar recipe, badge rendering and checked-state synchronization.
