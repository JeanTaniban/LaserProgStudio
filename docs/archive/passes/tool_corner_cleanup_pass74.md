# Pass 74 — right Tool corner cleanup

The right inspector no longer embeds scene history in the Tool stack.

- When no tool is active, the Tool group is hidden completely.
- The idle corner shows only the standalone History button, which opens the floating scene history window.
- The Help button is only visible while an actual tool is active.
- Slot 0 of the tool stack remains reserved internally for compatibility, but it renders as an empty widget.
