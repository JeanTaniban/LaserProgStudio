# Feedback second pass — layout, Joint, material rendering

This pass fixes the second round of QA feedback after the missions 1–7 integration.

## Inspector sizing

- Opening a tool now restores the right inspector to the remembered user width even when Light UI is disabled.
- The splitter is only set once during the tool/light transition; the user can still drag the panels freely afterwards.
- The right inspector minimum width is raised to a usable value so tool panels no longer open locked in a tiny column.

## Joint Builder

- Joint Builder can now be opened without a pre-existing selection.
- The tool still allows the dedicated A/B two-part selection workflow after it is opened.
- The large multi-line status text was replaced with a compact one-line status so parameters stay near the top of the inspector.

## Material rendering

- Render controls moved to the left View panel under the display-mode selector.
- Material mode now has directional light controls, ambient/specular controls, optional shadows, and a shadow-receiver floor.
- Material mode keeps material colors on selected objects; selection is indicated by edges instead of overwriting the material color.
- Material actors use PBR interpolation when available, with metallic/roughness/specular settings applied to VTK properties.
