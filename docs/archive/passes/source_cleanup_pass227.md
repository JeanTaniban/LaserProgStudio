# Source cleanup pass 227 — Qt overlay adapter split

`tool_core/overlay/qt_adapter.py` no longer owns every Qt overlay concern directly.
The public adapter API is unchanged, but the implementation is split by responsibility:

- `qt_adapter.py`: synchronization between `OverlayManager` specs and live Qt widgets.
- `qt_widgets.py`: native `QFrame`/`QPushButton` subclasses and event handlers.
- `qt_layout.py`: layout rebuild logic for fields, toolbars and button groups.
- `qt_style.py`: stylesheet assembly and overlay frame painting.

This keeps the optional PySide dependency lazy while making the runtime easier to package,
review and continue migrating.
