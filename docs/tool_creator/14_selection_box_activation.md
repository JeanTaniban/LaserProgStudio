# Selection box activation

The native rectangle-selection service is available as `ctx.selection_box`.

By default, event-driven rectangle selection uses:

```txt
Shift + left drag on an empty viewport area
```

This keeps plain left drag available for camera orbit/navigation.

```python
from laserprog_studio.tool_api.selection_box import (
    BoxSelectionActivationModifier,
    BoxSelectionMode,
    BoxSelectionTarget,
)

ctx.selection_box.configure(
    enabled=True,
    targets=[BoxSelectionTarget.TOOL_ACTORS],
    mode=BoxSelectionMode.REPLACE,
    activation_modifier=BoxSelectionActivationModifier.SHIFT,
)
```

A creator tool can opt out of the Shift requirement if it owns the full pointer gesture:

```python
ctx.selection_box.configure(
    activation_modifier=BoxSelectionActivationModifier.NONE,
)
```

Use this carefully: plain left drag is often needed by the viewport camera.
