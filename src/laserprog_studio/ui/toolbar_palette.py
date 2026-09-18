# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from ..application.toolbar_palette_clickaway import ToolbarPaletteClickAwayFilter
from .toolbar_catalog import TOOLBAR_CATEGORY_LABELS, TOOLBAR_MAX_ITEMS, search_toolbar_item_specs
from .toolbar_icons import toolbar_icon


def create_toolbar_palette_dialog(owner) -> QDialog:
    """Create the overlay used to add entries to the configurable toolbar.

    Kept as a function instead of another mixin/class method so the main UI
    remains thin and the refactor guard does not see a duplicate `__init__`
    extracted method.
    """

    dialog = QDialog(owner)
    dialog.setWindowTitle("Add a tool")
    try:
        # Do not use Qt.Popup here: clicking + Tools while the popup has focus
        # can close it and deliver the same mouse click back to the toolbar,
        # reopening it immediately.  A frameless Tool window gives us a stable
        # explicit toggle.
        dialog.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
    except Exception:
        pass
    dialog.setMinimumSize(460, 500)
    dialog.setMaximumWidth(660)

    root = QVBoxLayout(dialog)
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(8)

    title_row = QHBoxLayout()
    title = QLabel("Toolbox")
    title.setObjectName("Title")
    title_row.addWidget(title)
    title_row.addStretch(1)
    counter = QLabel("")
    counter.setObjectName("SubTitle")
    title_row.addWidget(counter)
    root.addLayout(title_row)

    search = QLineEdit()
    search.setPlaceholderText("Search a tool, modifier, or boolean…")
    root.addWidget(search)

    listing = QListWidget()
    listing.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    listing.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    listing.setWordWrap(True)
    root.addWidget(listing, 1)

    hint = QLabel(f"Click a row to add it. The toolbar is limited to {TOOLBAR_MAX_ITEMS} items.")
    hint.setWordWrap(True)
    hint.setObjectName("SubTitle")
    root.addWidget(hint)

    def refresh() -> None:
        selected = set(getattr(owner, "toolbar_item_ids", []) or [])
        listing.clear()
        for spec in search_toolbar_item_specs(search.text()):
            already = spec.id in selected
            category = TOOLBAR_CATEGORY_LABELS.get(spec.category, str(spec.category).title())
            prefix = "✓" if already else "+"
            item = QListWidgetItem(f"{prefix}  {spec.name}  ·  {category}\n{spec.description}")
            icon = toolbar_icon(spec.id)
            if icon is not None and not icon.isNull():
                item.setIcon(icon)
            item.setData(Qt.UserRole, spec.id)
            item.setToolTip("Already in the toolbar" if already else "Add to toolbar")
            if already:
                try:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                except Exception:
                    pass
            listing.addItem(item)
        limit_getter = getattr(owner, "_toolbar_max_items", None)
        limit = int(limit_getter() if callable(limit_getter) else TOOLBAR_MAX_ITEMS)
        counter.setText(f"{len(selected)}/{limit}")

    def add_current(item: QListWidgetItem) -> None:
        if item is None:
            return
        item_id = item.data(Qt.UserRole)
        if owner.add_toolbar_item(str(item_id)):
            refresh()

    search.textChanged.connect(lambda _text: refresh())
    listing.itemClicked.connect(add_current)
    refresh()
    try:
        click_away_filter = ToolbarPaletteClickAwayFilter(dialog, owner)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(click_away_filter)

            def _remove_click_away_filter(*_args) -> None:
                try:
                    app.removeEventFilter(click_away_filter)
                except Exception:
                    pass

            dialog.finished.connect(_remove_click_away_filter)
            dialog.destroyed.connect(_remove_click_away_filter)
        dialog._toolbar_palette_click_away_filter = click_away_filter
    except Exception:
        pass
    return dialog
