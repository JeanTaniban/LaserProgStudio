# Pass 193 - Overlay button styles and compact toolbars

This pass promotes overlay controls from ad-hoc QPushButton styling to semantic API styles.

Changes:

- adds `OverlayButtonStyle` values: `auto`, `primary`, `secondary`, `ghost`, `toggle`, `mode`, `danger`, `icon`;
- adds `ToolButtonSpec.style` while keeping old positional call sites compatible through the default `auto` value;
- adds the `toolbar` overlay kind for compact transform-style mode strips;
- renders style-specific Qt dynamic properties in the native overlay adapter;
- keeps grouped checkable buttons exclusive through the existing `OverlayManager` / `QButtonGroup` path;
- migrates Plan tracer 2D toolbox to a compact toolbar without the large empty panel area.

A tool should describe overlay intent semantically and should not paint or manage Qt widgets directly.
