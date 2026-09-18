# Light UI restore after tool close

When a classic tool is opened from the compact light transform UI, the right
inspector is opened automatically so the tool controls are usable. The app now
remembers that the user was in light UI before opening the tool.

On Apply, Cancel, or normal tool close, the splitter is restored to the compact
light state. If the tool was opened while the full inspector was already open,
the inspector remains open after the tool is closed.

Boolean actions are unchanged: they do not force the inspector open.
