# Joint edge margin update

This update adds an explicit edge margin parameter to the joint builder.

## Behavior

When several joints are generated with `Count`, the spacing no longer uses the old hard-coded `2.5 * joint_size` center margin.

The UI value `Edge margin` means:

```text
contact border -> real edge of the joint
```

The engine converts it internally to a center margin:

```text
center_margin = edge_margin + joint_size / 2
```

This is more intuitive than asking the user for the center position.

## Default

Default edge margin is `2.0 mm`.

## Files touched

- `src/laserprog_studio/window.py`
- `src/laser_toolbox/tools/joint_builder_core.py`
- `src/laser_toolbox/tools/joint_builder.py`
- `src/laser_toolbox/tools/joint_builder_basis.py`
- `src/laser_toolbox/settings/joint_builder.json`
