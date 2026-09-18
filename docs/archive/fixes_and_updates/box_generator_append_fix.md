# Box generator append fix

The box generator now appends generated boards to the committed scene instead of replacing the entire model.

Behavior:

- Existing committed parts are copied into the preview.
- Generated box boards are appended after the existing parts.
- Re-running Generate preview starts from the committed scene again, so previous box previews are not duplicated.
- Cancel removes only the preview changes.
- Apply commits the combined scene.
