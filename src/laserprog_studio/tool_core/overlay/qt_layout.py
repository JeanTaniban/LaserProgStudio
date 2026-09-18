# -*- coding: utf-8 -*-
"""Layout builder for Tool Core Qt overlay widgets."""

from __future__ import annotations

from typing import Any

from .specs import OverlayWindowSpec, toolbar_button_slot_width_px


_SECTIONED_TOOLBAR_MARGIN_X = 11
_SECTIONED_TOOLBAR_MARGIN_Y = 6
_SECTIONED_TOOLBAR_GAP = 6
_SECTIONED_TOOLBAR_SECTION_PAD_X = 8
_SECTIONED_TOOLBAR_SECTION_PAD_Y = 5
_SECTIONED_TOOLBAR_SECTION_TITLE_HEIGHT = 14
_SECTIONED_TOOLBAR_SECTION_TITLE_GAP = 2
_SECTIONED_TOOLBAR_BUTTON_GAP = 4
_SECTIONED_TOOLBAR_BUTTON_HEIGHT = 58
_SECTIONED_TOOLBAR_PILL_WIDTH = 116
_SECTIONED_TOOLBAR_PILL_HEIGHT = 70

_COMMAND_DECK_MARGIN_X = 9
_COMMAND_DECK_MARGIN_Y = 6
_COMMAND_DECK_HEADER_HEIGHT = 28
_COMMAND_DECK_HEADER_GAP = 6
_COMMAND_DECK_SECTION_TITLE_HEIGHT = 15
_COMMAND_DECK_SECTION_GAP = 8
_COMMAND_DECK_ROW_GAP = 0
_COMMAND_DECK_BUTTON_GAP = 6
_COMMAND_DECK_BUTTON_HEIGHT = 64
_COMMAND_DECK_CHIP_WIDTH = 128
_COMMAND_DECK_CHIP_HEIGHT = 26
_COMMAND_DECK_SECTION_PAD_X = 8
_COMMAND_DECK_SECTION_PAD_TOP = 6
_COMMAND_DECK_SECTION_PAD_BOTTOM = 7
_COMMAND_DECK_SECTION_TITLE_GAP = 3

_METRIC_BAR_MARGIN_X = 12
_METRIC_BAR_MARGIN_Y = 10
_METRIC_BAR_HEIGHT = 98
_METRIC_BAR_TITLE_WIDTH = 154
_METRIC_BAR_FIELD_WIDTH = 114
_METRIC_BAR_FIELD_HEIGHT = 68
_METRIC_BAR_ACTION_WIDTH = 96
_METRIC_BAR_ACTION_GAP = 6


def _connect_editable_overlay_field(edit: Any, field: Any, spec: Any, adapter: Any) -> None:
    """Wire the shared editable-field commit contract.

    Most overlays commit only on ``editingFinished``.  Fields that opt in with
    ``OverlayFieldSpec.live=True`` additionally dispatch ``textEdited`` so a tool
    can drive live previews without hand-building Qt widgets.
    """

    def _record(event: str, *, value: Any | None = None, extra: dict[str, Any] | None = None) -> None:
        try:
            from .qt_edit_diagnostics import record_qt_overlay_edit_event

            record_qt_overlay_edit_event(
                event,
                adapter=adapter,
                window_id=str(spec.id),
                field_id=str(field.id),
                value=value,
                extra=extra,
            )
        except Exception:
            pass

    def _commit(fid: str = field.id, w: str = spec.id, e: Any = edit) -> None:
        try:
            value = e.text()
        except Exception:
            value = ""
        _record("qt.editing_finished", value=value)
        adapter._overlay_field_committed(w, fid, value)

    edit.editingFinished.connect(_commit)
    if bool(getattr(field, "live", False)):
        # Use textChanged rather than only textEdited.  Some platform/input
        # method combinations (and a few delegated Qt renderers) do not emit
        # textEdited consistently, while textChanged is the stable signal used
        # by the metric-validation-style live commit contract.  Programmatic
        # syncs are protected with QSignalBlocker in the adapter, so this does
        # not loop when sibling fields are refreshed.
        try:
            edit.textChanged.connect(
                lambda text, fid=field.id, w=spec.id: (
                    _record("qt.text_changed", value=text),
                    adapter._overlay_field_edited(w, fid, text),
                )
            )
        except Exception:
            try:
                edit.textEdited.connect(
                    lambda text, fid=field.id, w=spec.id: (
                        _record("qt.text_edited", value=text),
                        adapter._overlay_field_edited(w, fid, text),
                    )
                )
            except Exception as exc:
                _record("qt.connect_live_failed", extra={"error": repr(exc)})


def _select_options(field: Any) -> tuple[tuple[str, str], ...]:
    """Normalise declarative select options into ``(value, label)`` pairs."""

    result: list[tuple[str, str]] = []
    for option in tuple(getattr(field, "options", ()) or ()):
        if isinstance(option, (tuple, list)) and len(option) >= 2:
            value, label = option[0], option[1]
        else:
            value = label = option
        result.append((str(value), str(label)))
    return tuple(result)


def _connect_select_overlay_field(combo: Any, field: Any, spec: Any, adapter: Any) -> None:
    def _changed(_index: int, fid: str = field.id, w: str = spec.id, box: Any = combo) -> None:
        try:
            value = box.currentData()
        except Exception:
            value = None
        if value is None:
            try:
                value = box.currentText()
            except Exception:
                value = ""
        adapter._overlay_field_committed(w, fid, str(value))

    combo.currentIndexChanged.connect(_changed)


def metric_bar_shell_height_px() -> int:
    """Return the deterministic outer height of the placement validation HUD."""

    return _METRIC_BAR_HEIGHT


def command_deck_section_height_px() -> int:
    """Return the exact height of one Command Deck section card."""

    return (
        _COMMAND_DECK_SECTION_PAD_TOP
        + _COMMAND_DECK_SECTION_TITLE_HEIGHT
        + _COMMAND_DECK_SECTION_TITLE_GAP
        + _COMMAND_DECK_BUTTON_HEIGHT
        + _COMMAND_DECK_SECTION_PAD_BOTTOM
    )


def command_deck_shell_height_px() -> int:
    """Return the deterministic outer height of the Command Deck overlay.

    The deck is now a single readable command row.  Earlier versions used two
    compact rows, which left a large black panel while the real buttons remained
    tiny.  One row of larger command cells gives the icons enough room and keeps
    the overlay height predictable.
    """

    return (
        _COMMAND_DECK_MARGIN_Y * 2
        + _COMMAND_DECK_HEADER_HEIGHT
        + _COMMAND_DECK_HEADER_GAP
        + command_deck_section_height_px()
    )


def sectioned_toolbar_shell_height_px() -> int:
    """Return the exact outer height needed by the compact command rail.

    The value is derived from the same margins used by the Qt layout.  The Plan
    Tracer toolbar is intentionally a compact HUD rail: one status pill, grouped
    command cells, no oversized ribbon cards and no clipped captions.
    """

    section_content = (
        _SECTIONED_TOOLBAR_SECTION_PAD_Y * 2
        + _SECTIONED_TOOLBAR_SECTION_TITLE_HEIGHT
        + _SECTIONED_TOOLBAR_SECTION_TITLE_GAP
        + _SECTIONED_TOOLBAR_BUTTON_HEIGHT
    )
    return _SECTIONED_TOOLBAR_MARGIN_Y * 2 + max(_SECTIONED_TOOLBAR_PILL_HEIGHT, section_content)


def _clear_layout_tree(layout: Any) -> None:
    """Recursively detach and delete widgets/layouts owned by an overlay.

    Qt layouts can contain nested layouts (toolbar rows, field cells).  Deleting
    only direct widgets leaves orphan child labels/buttons alive until a later
    event-loop pass, which makes overlay text stack and old checked mode buttons
    remain visible during fast rebuilds.
    """

    if layout is None:
        return
    while True:
        try:
            item = layout.takeAt(0)
        except Exception:
            item = None
        if item is None:
            break
        try:
            child_layout = item.layout()
        except Exception:
            child_layout = None
        if child_layout is not None:
            _clear_layout_tree(child_layout)
            try:
                child_layout.deleteLater()
            except Exception:
                pass
        try:
            child = item.widget()
        except Exception:
            child = None
        if child is not None:
            try:
                child.hide()
            except Exception:
                pass
            try:
                child.deleteLater()
            except Exception:
                pass


def _is_command_deck(spec: OverlayWindowSpec) -> bool:
    if str(getattr(spec, "overlay_kind", "")) == "command_deck":
        return True
    return any(str(getattr(field, "id", "")).endswith(".command_status") for field in getattr(spec, "fields", ()) or ())


def _is_metric_bar(spec: OverlayWindowSpec) -> bool:
    return str(getattr(spec, "overlay_kind", "")) == "metric_bar"


def _toolbar_has_vector_icons(spec: OverlayWindowSpec) -> bool:
    return any(bool(getattr(button, "icon", None)) for button in getattr(spec, "buttons", ()) or ())


def _toolbar_has_badge(spec: OverlayWindowSpec) -> bool:
    return any(str(getattr(field, "id", "")).endswith("mode_badge") for field in getattr(spec, "fields", ()) or ())


def _toolbar_editable_fields(spec: OverlayWindowSpec) -> list[Any]:
    return [field for field in getattr(spec, "fields", ()) or () if field.kind in {"number", "text"} and bool(field.enabled)]




def _toolbar_button_family(button: Any) -> str:
    """Return the visual section key used by CAD toolbar separators.

    Separators should mark semantic groups instead of every button.  Tools can
    provide an explicit ``section`` for deterministic pro layouts; otherwise the
    renderer falls back to the generic mode/action split.
    """

    explicit_section = str(getattr(button, "section", "") or "").strip()
    if explicit_section:
        return f"section:{explicit_section}"
    if bool(getattr(button, "checkable", False)) and bool(getattr(button, "group", None)):
        return f"mode:{getattr(button, 'group', '')}"
    return "actions"


def _toolbar_should_insert_separator(buttons: tuple[Any, ...], index: int) -> bool:
    """Return True only at semantic section boundaries.

    This keeps Plan Tracer compact and readable: Modify/Point/Line/... remain a
    continuous mode rail, while Rebuild/Delete are visually separated as actions.
    """

    next_index = int(index) + 1
    if next_index >= len(buttons):
        return False
    return _toolbar_button_family(buttons[int(index)]) != _toolbar_button_family(buttons[next_index])


def _toolbar_separator_count(spec: OverlayWindowSpec) -> int:
    buttons = tuple(getattr(spec, "buttons", ()) or ())
    return sum(1 for index in range(max(0, len(buttons) - 1)) if _toolbar_should_insert_separator(buttons, index))


def _toolbar_button_slot_width(spec: OverlayWindowSpec, button: Any | None = None) -> int:
    """Return the preferred width of one icon-toolbar slot.

    The old implementation divided the requested outer width equally between
    every button.  That made the Plan Tracer depend on a tool-side 920px width
    and still allowed Qt to render the actual buttons at their tiny natural
    width on some platforms.  The renderer now uses the same label-aware sizing
    as the public API: each slot is explicit, deterministic and readable.
    """

    if button is not None:
        return int(toolbar_button_slot_width_px(button))
    buttons = tuple(getattr(spec, "buttons", ()) or ())
    if not buttons:
        return 72
    return max(int(toolbar_button_slot_width_px(btn)) for btn in buttons)


def _toolbar_button_slot_widths(spec: OverlayWindowSpec) -> list[int]:
    return [int(toolbar_button_slot_width_px(button)) for button in tuple(getattr(spec, "buttons", ()) or ())]


def _toolbar_button_display_label(button: Any) -> str:
    return str(getattr(button, "display_label", None) or getattr(button, "label", "") or "")


def _toolbar_content_width(spec: OverlayWindowSpec) -> int:
    buttons = tuple(getattr(spec, "buttons", ()) or ())
    if not buttons:
        return 0
    separator_count = _toolbar_separator_count(spec)
    row_items = len(buttons) + separator_count
    spacing = max(0, row_items - 1) * 4
    return sum(toolbar_button_slot_width_px(button) for button in buttons) + separator_count * 12 + spacing


def _is_inline_metric_toolbar(spec: OverlayWindowSpec) -> bool:
    """Return True for compact numeric confirmation overlays.

    Metric confirmations are toolbar overlays with numeric fields, no mode badge
    and no vector-mode icons.  They need a single horizontal row; the normal
    drawing toolbar still keeps its badge row plus icon row.
    """

    return (
        str(getattr(spec, "overlay_kind", "")) == "toolbar"
        and bool(_toolbar_editable_fields(spec))
        and bool(getattr(spec, "buttons", ()) or ())
        and not _toolbar_has_badge(spec)
        and not _toolbar_has_vector_icons(spec)
    )




def _toolbar_sections(spec: OverlayWindowSpec) -> tuple[Any, ...]:
    return tuple(getattr(spec, "toolbar_sections", ()) or ())


def _section_buttons(spec: OverlayWindowSpec, section_id: str) -> tuple[Any, ...]:
    return tuple(button for button in tuple(getattr(spec, "buttons", ()) or ()) if str(getattr(button, "section", "") or "") == str(section_id))


def _sectioned_toolbar_natural_section_width(buttons: tuple[Any, ...]) -> int:
    if not buttons:
        return 0
    return (
        sum(int(toolbar_button_slot_width_px(button)) for button in buttons)
        + max(0, len(buttons) - 1) * _SECTIONED_TOOLBAR_BUTTON_GAP
        + _SECTIONED_TOOLBAR_SECTION_PAD_X * 2
    )


def _sectioned_toolbar_allocations(spec: OverlayWindowSpec, sections: tuple[Any, ...], has_badge: bool) -> tuple[dict[str, int], dict[str, int]]:
    """Return natural card/button widths for the compact sectioned command rail.

    The previous renderer tried to scale every section until the painted shell was
    full.  That made single-button groups balloon, while Qt still had to squeeze
    the actual labels inside fixed children.  A toolbar should instead advertise a
    trustworthy natural width, then paint child widgets at that size.
    """

    visible_sections = [section for section in sections if _section_buttons(spec, str(getattr(section, "id", "")))]
    frame_widths: dict[str, int] = {}
    button_widths: dict[str, int] = {}
    for section in visible_sections:
        section_id = str(getattr(section, "id", ""))
        buttons = _section_buttons(spec, section_id)
        slots = [int(toolbar_button_slot_width_px(button)) for button in buttons]
        frame_widths[section_id] = (
            sum(slots)
            + max(0, len(slots) - 1) * _SECTIONED_TOOLBAR_BUTTON_GAP
            + _SECTIONED_TOOLBAR_SECTION_PAD_X * 2
        )
        for button, width in zip(buttons, slots, strict=True):
            button_widths[str(button.id)] = int(width)
    return frame_widths, button_widths


def _command_deck_status_field(spec: OverlayWindowSpec) -> Any | None:
    for field in tuple(getattr(spec, "fields", ()) or ()):  # first non-mode info field is the deck status line
        if str(getattr(field, "id", "")).endswith("mode_badge"):
            continue
        if str(getattr(field, "kind", "")) == "info":
            return field
    return None


def _command_deck_badge_field(spec: OverlayWindowSpec) -> Any | None:
    for field in tuple(getattr(spec, "fields", ()) or ()):
        if str(getattr(field, "id", "")).endswith("mode_badge"):
            return field
    return None


def _command_deck_slot_width(button: Any) -> int:
    explicit = getattr(button, "slot_width_px", None)
    if explicit is not None:
        try:
            return max(58, min(118, int(explicit)))
        except Exception:
            pass
    label = str(getattr(button, "display_label", None) or getattr(button, "label", "") or "")
    # Large touch/readability target: the icon is the primary visual object and
    # the caption must fit without the renderer shrinking it into noise.
    return max(64, min(112, 36 + int(round(len(label) * 5.4))))


def _command_deck_min_slot_width(button: Any) -> int:
    """Smallest safe width for a command tile during responsive compaction.

    Command Deck buttons paint the icon above a short caption.  Their natural
    width remains the preferred geometry, but a deck with many sections (Plan
    Tracer after the Curve tool was added) must be able to recover a modest
    amount of horizontal room instead of letting fixed section frames overlap.
    The lower bound is label-aware and deliberately conservative; the vector
    painter can still reduce the caption font by one step when required.
    """

    label = str(getattr(button, "display_label", None) or getattr(button, "label", "") or "")
    estimated_caption = 30 + int(round(len(label) * 4.0))
    return max(46, min(_command_deck_slot_width(button), min(78, estimated_caption)))


def _command_deck_section_width(
    buttons: tuple[Any, ...],
    slot_widths: dict[str, int] | None = None,
) -> int:
    if not buttons:
        return 0

    def _width(button: Any) -> int:
        if slot_widths is not None:
            resolved = slot_widths.get(str(getattr(button, "id", "") or ""))
            if resolved is not None:
                return int(resolved)
        return _command_deck_slot_width(button)

    return (
        sum(_width(button) for button in buttons)
        + max(0, len(buttons) - 1) * _COMMAND_DECK_BUTTON_GAP
        + _COMMAND_DECK_SECTION_PAD_X * 2
    )


def _command_deck_responsive_slot_widths(
    spec: OverlayWindowSpec,
    sections: tuple[Any, ...] | list[Any],
) -> dict[str, int]:
    """Allocate fixed tile widths that always fit inside the deck shell.

    The old renderer gave every section its natural fixed width even after the
    public builder capped the outer window at 1240 px.  Adding one new mode could
    therefore make later cards paint over earlier cards.  This allocator keeps
    the natural sizes whenever they fit and proportionally consumes only the
    available label-safe slack when the row is wider than the shell.
    """

    visible = tuple(sections or ())
    ordered_buttons: list[Any] = []
    for section in visible:
        ordered_buttons.extend(_section_buttons(spec, str(getattr(section, "id", ""))))
    if not ordered_buttons:
        return {}

    widths = {str(button.id): _command_deck_slot_width(button) for button in ordered_buttons}
    minimums = {str(button.id): _command_deck_min_slot_width(button) for button in ordered_buttons}
    section_count = len(visible)
    button_gap_count = sum(max(0, len(_section_buttons(spec, str(getattr(section, "id", "")))) - 1) for section in visible)
    fixed_overhead = (
        section_count * (_COMMAND_DECK_SECTION_PAD_X * 2)
        + button_gap_count * _COMMAND_DECK_BUTTON_GAP
        + max(0, section_count - 1) * _COMMAND_DECK_SECTION_GAP
    )
    available_buttons = max(0, int(getattr(spec, "width_px", 0)) - (_COMMAND_DECK_MARGIN_X * 2) - fixed_overhead)
    natural_total = sum(widths.values())
    deficit = natural_total - available_buttons
    if deficit <= 0:
        return widths

    reducible = sum(max(0, widths[key] - minimums[key]) for key in widths)
    if reducible <= 0:
        return widths

    ratio = min(1.0, float(deficit) / float(reducible))
    for key in tuple(widths):
        slack = max(0, widths[key] - minimums[key])
        widths[key] = max(minimums[key], widths[key] - int(slack * ratio))

    # Integer rounding may leave a handful of pixels.  Consume them uniformly
    # rather than allowing the last section to overlap its neighbour.
    remaining = sum(widths.values()) - available_buttons
    while remaining > 0:
        changed = False
        for key in tuple(widths):
            if widths[key] <= minimums[key]:
                continue
            widths[key] -= 1
            remaining -= 1
            changed = True
            if remaining <= 0:
                break
        if not changed:
            break

    return widths


def _metric_bar_validate_button_id(spec: OverlayWindowSpec) -> str | None:
    for button in tuple(getattr(spec, "buttons", ()) or ()):  # primary action wins
        style = str(getattr(button, "style", "") or "")
        button_id = str(getattr(button, "id", "") or "")
        if style == "primary" or any(token in button_id.lower() for token in ("validate", "apply", "confirm", "ok")):
            return button_id
    return None


def _rebuild_metric_bar_widget(
    adapter: Any,
    widget: Any,
    spec: OverlayWindowSpec,
    QLabel: Any,
    QLineEdit: Any,
    QPushButton: Any,
    QSizePolicy: Any,
    QVBoxLayout: Any,
    QHBoxLayout: Any,
    Qt: Any | None,
    layout: Any,
    field_edits: dict[str, Any],
    _Qt: Any | None,
) -> None:
    """Build the dedicated numeric placement validation bar.

    This is intentionally not a normal toolbar: fields are the primary content,
    actions are fixed, and command buttons do not steal focus from QLineEdit.
    The Validate click therefore flushes the text and commits in one physical
    click instead of causing a focus-out rebuild first.
    """

    layout.setContentsMargins(_METRIC_BAR_MARGIN_X, _METRIC_BAR_MARGIN_Y, _METRIC_BAR_MARGIN_X, _METRIC_BAR_MARGIN_Y)
    layout.setSpacing(0)
    try:
        if _Qt is not None:
            layout.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
    except Exception:
        pass

    root = QHBoxLayout()
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(10)
    try:
        if _Qt is not None:
            root.setAlignment(_Qt.AlignVCenter)
    except Exception:
        pass

    try:
        from PySide6.QtWidgets import QFrame as _QFrame
    except Exception:  # pragma: no cover - PySide is optional in headless tests
        _QFrame = None

    title_box = QVBoxLayout()
    title_box.setContentsMargins(0, 0, 0, 0)
    title_box.setSpacing(1)
    title = QLabel(str(getattr(spec, "title", "") or "Placement"))
    title.setObjectName("ToolCoreMetricBarTitle")
    subtitle = QLabel("Edit dimensions")
    subtitle.setObjectName("ToolCoreMetricBarSubtitle")
    try:
        title.setMinimumHeight(22)
        title.setMaximumHeight(22)
        subtitle.setMinimumHeight(16)
        subtitle.setMaximumHeight(16)
        if _Qt is not None:
            title.setAlignment(_Qt.AlignLeft | _Qt.AlignVCenter)
            subtitle.setAlignment(_Qt.AlignLeft | _Qt.AlignVCenter)
    except Exception:
        pass
    title_box.addWidget(title)
    title_box.addWidget(subtitle)
    title_holder = None
    if _QFrame is not None:
        title_holder = _QFrame(widget)
        title_holder.setObjectName("ToolCoreMetricBarTitleCell")
        holder_layout = QVBoxLayout(title_holder)
        holder_layout.setContentsMargins(10, 8, 8, 8)
        holder_layout.setSpacing(0)
        holder_layout.addLayout(title_box)
        try:
            title_holder.setFixedSize(_METRIC_BAR_TITLE_WIDTH, _METRIC_BAR_FIELD_HEIGHT)
        except Exception:
            pass
        root.addWidget(title_holder)
    else:
        root.addLayout(title_box)

    validate_button_id = _metric_bar_validate_button_id(spec)
    for field in tuple(getattr(spec, "fields", ()) or ()):  # numeric fields only; info fields stay out of the HUD
        if str(getattr(field, "kind", "")) not in {"number", "text"} or not bool(getattr(field, "enabled", True)):
            continue
        if _QFrame is not None:
            card = _QFrame(widget)
            card.setObjectName("ToolCoreMetricFieldCard")
            cell = QVBoxLayout(card)
            try:
                card.setFixedSize(_METRIC_BAR_FIELD_WIDTH, _METRIC_BAR_FIELD_HEIGHT)
            except Exception:
                pass
            root.addWidget(card)
        else:
            card = None
            cell = QVBoxLayout()
            root.addLayout(cell)
        cell.setContentsMargins(8, 6, 8, 7)
        cell.setSpacing(4)
        caption = QLabel(str(getattr(field, "label", "") or "Value"))
        caption.setObjectName("ToolCoreMetricFieldLabel")
        caption.setWordWrap(False)
        try:
            caption.setMinimumHeight(15)
            caption.setMaximumHeight(15)
            if _Qt is not None:
                caption.setAlignment(_Qt.AlignLeft | _Qt.AlignVCenter)
        except Exception:
            pass
        cell.addWidget(caption)
        edit = QLineEdit(str(getattr(field, "value", "") or ""))
        edit.setObjectName("ToolCoreMetricFieldEdit")
        edit.setProperty("toolCoreOverlayFieldId", str(field.id))
        edit.setProperty("toolCoreOverlayWindowId", str(spec.id))
        field_edits[str(field.id)] = edit
        edit.setEnabled(bool(getattr(field, "enabled", True)))
        try:
            edit.setMinimumHeight(30)
            edit.setMaximumHeight(32)
            edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            if _Qt is not None:
                edit.setAlignment(_Qt.AlignRight | _Qt.AlignVCenter)
        except Exception:
            pass
        tooltip = getattr(field, "tooltip", None)
        if tooltip:
            edit.setToolTip(tooltip)
        _connect_editable_overlay_field(edit, field, spec, adapter)
        if validate_button_id:
            # Enter validates after Qt has processed the line edit event.
            try:
                edit.returnPressed.connect(lambda bid=validate_button_id: adapter._overlay_button_clicked(bid))
            except Exception:
                pass
        cell.addWidget(edit)

    actions = QVBoxLayout()
    actions.setContentsMargins(0, 0, 0, 0)
    actions.setSpacing(_METRIC_BAR_ACTION_GAP)
    try:
        if _Qt is not None:
            actions.setAlignment(_Qt.AlignVCenter)
    except Exception:
        pass
    for button_spec in tuple(getattr(spec, "buttons", ()) or ()):  # stable API order
        style = adapter._resolve_button_style(button_spec)
        label = adapter._button_label(button_spec, style)
        button = QPushButton(label)
        button.setObjectName("ToolCoreMetricActionButton")
        button.setProperty("toolCoreButtonId", str(button_spec.id))
        button.setProperty("overlayButtonStyle", str(style))
        button.setEnabled(bool(button_spec.enabled))
        button.setCheckable(False)
        try:
            button.setFixedSize(_METRIC_BAR_ACTION_WIDTH, 34 if style == "primary" else 28)
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            if hasattr(button, "setAutoDefault"):
                button.setAutoDefault(False)
            if hasattr(button, "setDefault"):
                button.setDefault(False)
        except Exception:
            pass
        tooltip = adapter._button_tooltip(button_spec)
        if tooltip:
            button.setToolTip(tooltip)
        if "close" in str(button_spec.id).lower():
            button.clicked.connect(lambda _checked=False, window_id=spec.id, w=widget: adapter._close(window_id, w))
        else:
            button.clicked.connect(lambda _checked=False, bid=button_spec.id: adapter._overlay_button_clicked(bid))
        actions.addWidget(button)
    root.addLayout(actions)
    layout.addLayout(root)
    try:
        widget._tool_core_overlay_field_edits = field_edits
        widget._tool_core_overlay_button_groups = ()
    except Exception:
        pass
    adapter._stabilize_geometry(widget, spec)


def _rebuild_command_deck_widget(
    adapter: Any,
    widget: Any,
    spec: OverlayWindowSpec,
    QLabel: Any,
    QPushButton: Any,
    QSizePolicy: Any,
    QVBoxLayout: Any,
    QHBoxLayout: Any,
    QButtonGroup: Any,
    Qt: Any | None,
    layout: Any,
    field_edits: dict[str, Any],
    _Qt: Any | None,
) -> None:
    """Build a new compact command deck overlay.

    This renderer deliberately avoids the old ribbon failure mode: no stretched
    cards, no global black bar, and no button children smaller than their label.
    Every cell receives a fixed readable hit target, and the deck width comes
    from the public command-deck API.
    """

    layout.setContentsMargins(_COMMAND_DECK_MARGIN_X, _COMMAND_DECK_MARGIN_Y, _COMMAND_DECK_MARGIN_X, _COMMAND_DECK_MARGIN_Y)
    layout.setSpacing(_COMMAND_DECK_HEADER_GAP)
    try:
        if _Qt is not None:
            layout.setAlignment(_Qt.AlignTop | _Qt.AlignLeft)
    except Exception:
        pass

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(6)
    try:
        if _Qt is not None:
            header.setAlignment(_Qt.AlignVCenter)
    except Exception:
        pass

    title_block = QVBoxLayout()
    title_block.setContentsMargins(0, 0, 0, 0)
    title_block.setSpacing(0)
    title = QLabel(str(getattr(spec, "title", "") or "Tool"))
    title.setObjectName("ToolCoreCommandDeckTitle")
    subtitle_field = _command_deck_status_field(spec)
    subtitle_value = str(getattr(subtitle_field, "value", "") or "") if subtitle_field is not None else ""
    subtitle = QLabel(subtitle_value)
    subtitle.setObjectName("ToolCoreCommandDeckSubtitle")
    subtitle.setWordWrap(False)
    try:
        title.setMinimumHeight(15)
        title.setMaximumHeight(15)
        subtitle.setMinimumHeight(12)
        subtitle.setMaximumHeight(12)
    except Exception:
        pass
    title_block.addWidget(title)
    title_block.addWidget(subtitle)
    header.addLayout(title_block, 1)

    badge_field = _command_deck_badge_field(spec)
    if badge_field is not None:
        badge_text = str(getattr(badge_field, "value", "") or "")
        badge_label = str(getattr(badge_field, "label", "") or "")
        badge = QLabel(f"{badge_label}: {badge_text}" if badge_label else badge_text)
        badge.setObjectName("ToolCoreCommandDeckChip")
        try:
            badge.setMinimumSize(_COMMAND_DECK_CHIP_WIDTH, _COMMAND_DECK_CHIP_HEIGHT)
            badge.setMaximumSize(_COMMAND_DECK_CHIP_WIDTH, _COMMAND_DECK_CHIP_HEIGHT)
            if _Qt is not None:
                badge.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
        except Exception:
            pass
        tooltip = getattr(badge_field, "tooltip", None)
        if tooltip:
            badge.setToolTip(tooltip)
        header.addWidget(badge)
    layout.addLayout(header)

    body = QVBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(_COMMAND_DECK_ROW_GAP)
    try:
        if _Qt is not None:
            body.setAlignment(_Qt.AlignLeft | _Qt.AlignTop)
    except Exception:
        pass

    try:
        from PySide6.QtWidgets import QFrame as _QFrame
    except Exception:  # pragma: no cover
        _QFrame = None

    button_groups: dict[str, Any] = {}
    rendered_button_ids: set[str] = set()
    responsive_slot_widths: dict[str, int] = {}

    def _add_button(parent_layout: Any, button_spec: Any) -> None:
        style = adapter._resolve_button_style(button_spec)
        label = adapter._button_label(button_spec, style)
        display_label = _toolbar_button_display_label(button_spec)
        vector_icon = str(getattr(button_spec, "icon", "") or "")
        button = QPushButton(display_label if vector_icon else label)
        button.setObjectName("ToolCoreOverlayButton")
        if vector_icon:
            button.setProperty("toolCoreVectorIcon", vector_icon)
            button.setProperty("toolCoreVectorIconSet", True)
            button.setProperty("toolCoreVectorCommandDeck", True)
            button.setProperty("toolCoreVectorLabel", display_label)
            button.setProperty("toolCoreVectorFullLabel", label)
            button.setProperty("toolCoreVectorNoElide", True)
            try:
                button.setAccessibleName(label)
                button.setAccessibleDescription(display_label)
            except Exception:
                pass
        button.setProperty("toolCoreButtonId", str(button_spec.id))
        button.setProperty("toolPaletteButton", bool(button_spec.group))
        button.setProperty("overlayButtonGroup", str(button_spec.group or ""))
        button.setProperty("overlayButtonStyle", str(style))
        try:
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            slot_width = responsive_slot_widths.get(str(button_spec.id), _command_deck_slot_width(button_spec))
            button.setFixedSize(int(slot_width), _COMMAND_DECK_BUTTON_HEIGHT)
            button.setCursor(Qt.PointingHandCursor)
        except Exception:
            pass
        button.setEnabled(bool(button_spec.enabled))
        button.setCheckable(bool(button_spec.checkable))
        if button_spec.group and button_spec.checkable:
            group_key = str(button_spec.group)
            group = button_groups.get(group_key)
            if group is None:
                group = QButtonGroup(widget)
                group.setExclusive(True)
                button_groups[group_key] = group
            group.addButton(button)
        if button_spec.checkable:
            button.setChecked(bool(button_spec.checked))
        tooltip = adapter._button_tooltip(button_spec)
        if tooltip:
            button.setToolTip(tooltip)
        if "close" in str(button_spec.id).lower():
            button.clicked.connect(lambda _checked=False, window_id=spec.id, w=widget: adapter._close(window_id, w))
        else:
            button.clicked.connect(lambda _checked=False, bid=button_spec.id: adapter._overlay_button_clicked(bid))
        parent_layout.addWidget(button)
        rendered_button_ids.add(str(button_spec.id))

    visible_sections = [section for section in _toolbar_sections(spec) if _section_buttons(spec, str(getattr(section, "id", "")))]
    responsive_slot_widths = _command_deck_responsive_slot_widths(spec, visible_sections)
    if visible_sections:
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(_COMMAND_DECK_SECTION_GAP)
        try:
            if _Qt is not None:
                row_layout.setAlignment(_Qt.AlignLeft | _Qt.AlignVCenter)
        except Exception:
            pass
        for section in visible_sections:
            section_id = str(getattr(section, "id", ""))
            buttons = _section_buttons(spec, section_id)
            if not buttons:
                continue
            section_w = _command_deck_section_width(buttons, responsive_slot_widths)
            section_h = command_deck_section_height_px()
            if _QFrame is not None:
                frame = _QFrame(widget)
                frame.setObjectName("ToolCoreCommandDeckSection")
                section_layout = QVBoxLayout(frame)
                try:
                    frame.setMinimumSize(section_w, section_h)
                    frame.setMaximumSize(section_w, section_h)
                except Exception:
                    pass
                row_layout.addWidget(frame)
            else:
                frame = None
                section_layout = QVBoxLayout()
                row_layout.addLayout(section_layout)
            section_layout.setContentsMargins(
                _COMMAND_DECK_SECTION_PAD_X,
                _COMMAND_DECK_SECTION_PAD_TOP,
                _COMMAND_DECK_SECTION_PAD_X,
                _COMMAND_DECK_SECTION_PAD_BOTTOM,
            )
            section_layout.setSpacing(_COMMAND_DECK_SECTION_TITLE_GAP)
            section_title = QLabel(str(getattr(section, "label", "") or getattr(section, "id", "")))
            section_title.setObjectName("ToolCoreCommandDeckSectionTitle")
            section_title.setWordWrap(False)
            try:
                section_title.setMinimumHeight(_COMMAND_DECK_SECTION_TITLE_HEIGHT)
                section_title.setMaximumHeight(_COMMAND_DECK_SECTION_TITLE_HEIGHT)
                if _Qt is not None:
                    section_title.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
            except Exception:
                pass
            section_layout.addWidget(section_title)
            button_row = QHBoxLayout()
            button_row.setContentsMargins(0, 0, 0, 0)
            button_row.setSpacing(_COMMAND_DECK_BUTTON_GAP)
            for button_spec in buttons:
                _add_button(button_row, button_spec)
            section_layout.addLayout(button_row)
        body.addLayout(row_layout)

    orphan_buttons = tuple(button for button in tuple(getattr(spec, "buttons", ()) or ()) if str(button.id) not in rendered_button_ids)
    if orphan_buttons:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_COMMAND_DECK_BUTTON_GAP)
        for button_spec in orphan_buttons:
            _add_button(row, button_spec)
        body.addLayout(row)

    layout.addLayout(body)
    try:
        widget._tool_core_overlay_button_groups = tuple(button_groups.values())
        widget._tool_core_overlay_field_edits = field_edits
    except Exception:
        pass
    adapter._stabilize_geometry(widget, spec)

def _rebuild_sectioned_toolbar_widget(
    adapter: Any,
    widget: Any,
    spec: OverlayWindowSpec,
    QLabel: Any,
    QPushButton: Any,
    QSizePolicy: Any,
    QVBoxLayout: Any,
    QHBoxLayout: Any,
    QButtonGroup: Any,
    Qt: Any | None,
    layout: Any,
    field_edits: dict[str, Any],
    _Qt: Any | None,
) -> None:
    """Build the compact command rail: status pill + labelled section groups.

    The shell width is derived from natural child sizes.  This avoids both bad
    extremes seen in earlier passes: a tiny island in a huge black panel, and an
    overgrown ribbon that forces Qt to clip the labels.
    """

    layout.setContentsMargins(
        _SECTIONED_TOOLBAR_MARGIN_X,
        _SECTIONED_TOOLBAR_MARGIN_Y,
        _SECTIONED_TOOLBAR_MARGIN_X,
        _SECTIONED_TOOLBAR_MARGIN_Y,
    )
    layout.setSpacing(0)
    root = QHBoxLayout()
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(_SECTIONED_TOOLBAR_GAP)
    try:
        if _Qt is not None:
            root.setAlignment(_Qt.AlignVCenter)
    except Exception:
        pass

    badge_field = None
    for field in tuple(getattr(spec, "fields", ()) or ()):
        if str(getattr(field, "id", "")).endswith("mode_badge"):
            badge_field = field
            break

    sections = _toolbar_sections(spec)
    frame_widths, button_widths = _sectioned_toolbar_allocations(spec, sections, badge_field is not None)

    if badge_field is not None:
        badge_text = str(getattr(badge_field, "value", "") or "")
        badge_label = str(getattr(badge_field, "label", "") or "")
        pill = QLabel(f"{badge_label}\n{badge_text}" if badge_label else badge_text)
        pill.setObjectName("ToolCoreOverlayStatusPill")
        pill.setWordWrap(False)
        try:
            pill.setMinimumSize(_SECTIONED_TOOLBAR_PILL_WIDTH, _SECTIONED_TOOLBAR_PILL_HEIGHT)
            pill.setMaximumSize(_SECTIONED_TOOLBAR_PILL_WIDTH, _SECTIONED_TOOLBAR_PILL_HEIGHT)
            if _Qt is not None:
                pill.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
        except Exception:
            pass
        tooltip = getattr(badge_field, "tooltip", None)
        if tooltip:
            pill.setToolTip(tooltip)
        root.addWidget(pill)

    try:
        from PySide6.QtWidgets import QFrame as _QFrame
    except Exception:  # pragma: no cover - PySide is optional in headless tests
        _QFrame = None

    button_groups: dict[str, Any] = {}
    rendered_button_ids: set[str] = set()

    def _add_button(parent_layout: Any, button_spec: Any) -> None:
        style = adapter._resolve_button_style(button_spec)
        label = adapter._button_label(button_spec, style)
        display_label = _toolbar_button_display_label(button_spec) if str(getattr(spec, "overlay_kind", "")) == "toolbar" else label
        vector_icon = str(getattr(button_spec, "icon", "") or "")
        button = QPushButton(display_label if vector_icon else label)
        button.setObjectName("ToolCoreOverlayButton")
        if vector_icon:
            button.setProperty("toolCoreVectorIcon", vector_icon)
            button.setProperty("toolCoreVectorIconSet", True)
            button.setProperty("toolCoreVectorToolbarV2", True)
            button.setProperty("toolCoreVectorLabel", display_label)
            button.setProperty("toolCoreVectorFullLabel", label)
            button.setProperty("toolCoreVectorNoElide", True)
            try:
                button.setAccessibleName(label)
                button.setAccessibleDescription(display_label)
            except Exception:
                pass
        button.setProperty("toolCoreButtonId", str(button_spec.id))
        button.setProperty("toolPaletteButton", bool(button_spec.group))
        button.setProperty("overlayButtonGroup", str(button_spec.group or ""))
        button.setProperty("overlayButtonStyle", str(style))
        if vector_icon:
            try:
                toolbar_slot_width = int(button_widths.get(str(button_spec.id), toolbar_button_slot_width_px(button_spec)))
                button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                button.setFixedSize(toolbar_slot_width, _SECTIONED_TOOLBAR_BUTTON_HEIGHT)
            except Exception:
                pass
        button.setEnabled(bool(button_spec.enabled))
        button.setCheckable(bool(button_spec.checkable))
        try:
            button.setCursor(Qt.PointingHandCursor)
        except Exception:
            pass
        if button_spec.group and button_spec.checkable:
            group_key = str(button_spec.group)
            group = button_groups.get(group_key)
            if group is None:
                group = QButtonGroup(widget)
                group.setExclusive(True)
                button_groups[group_key] = group
            group.addButton(button)
        if button_spec.checkable:
            button.setChecked(bool(button_spec.checked))
        tooltip = adapter._button_tooltip(button_spec)
        if tooltip:
            button.setToolTip(tooltip)
        if "close" in str(button_spec.id).lower():
            button.clicked.connect(lambda _checked=False, window_id=spec.id, w=widget: adapter._close(window_id, w))
        else:
            button.clicked.connect(lambda _checked=False, bid=button_spec.id: adapter._overlay_button_clicked(bid))
        parent_layout.addWidget(button)
        rendered_button_ids.add(str(button_spec.id))

    for section in sections:
        section_id = str(getattr(section, "id", ""))
        section_buttons = _section_buttons(spec, section_id)
        if not section_buttons:
            continue
        if _QFrame is not None:
            section_frame = _QFrame(widget)
            section_frame.setObjectName("ToolCoreOverlayToolbarSection")
            section_layout = QVBoxLayout(section_frame)
            try:
                section_w = int(frame_widths.get(section_id, 0))
                section_h = (
                    _SECTIONED_TOOLBAR_SECTION_PAD_Y * 2
                    + _SECTIONED_TOOLBAR_SECTION_TITLE_HEIGHT
                    + _SECTIONED_TOOLBAR_SECTION_TITLE_GAP
                    + _SECTIONED_TOOLBAR_BUTTON_HEIGHT
                )
                section_frame.setMinimumSize(section_w, section_h)
                section_frame.setMaximumSize(section_w, section_h)
            except Exception:
                pass
            root.addWidget(section_frame)
        else:
            section_frame = None
            section_layout = QVBoxLayout()
            root.addLayout(section_layout)
        section_layout.setContentsMargins(
            _SECTIONED_TOOLBAR_SECTION_PAD_X,
            _SECTIONED_TOOLBAR_SECTION_PAD_Y,
            _SECTIONED_TOOLBAR_SECTION_PAD_X,
            _SECTIONED_TOOLBAR_SECTION_PAD_Y,
        )
        section_layout.setSpacing(_SECTIONED_TOOLBAR_SECTION_TITLE_GAP)
        title = QLabel(str(getattr(section, "label", "") or getattr(section, "id", "")))
        title.setObjectName("ToolCoreOverlayToolbarSectionTitle")
        title.setWordWrap(False)
        try:
            title.setMinimumHeight(_SECTIONED_TOOLBAR_SECTION_TITLE_HEIGHT)
            title.setMaximumHeight(_SECTIONED_TOOLBAR_SECTION_TITLE_HEIGHT)
            if _Qt is not None:
                title.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
        except Exception:
            pass
        section_layout.addWidget(title)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_SECTIONED_TOOLBAR_BUTTON_GAP)
        try:
            if _Qt is not None:
                row.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
        except Exception:
            pass
        for button_spec in section_buttons:
            _add_button(row, button_spec)
        section_layout.addLayout(row)

    orphan_buttons = tuple(button for button in tuple(getattr(spec, "buttons", ()) or ()) if str(button.id) not in rendered_button_ids)
    if orphan_buttons:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_SECTIONED_TOOLBAR_BUTTON_GAP)
        for button_spec in orphan_buttons:
            _add_button(row, button_spec)
        root.addLayout(row)

    try:
        widget._tool_core_overlay_button_groups = tuple(button_groups.values())
    except Exception:
        pass
    layout.addLayout(root)
    try:
        widget._tool_core_overlay_field_edits = field_edits
    except Exception:
        pass
    adapter._stabilize_geometry(widget, spec)


def rebuild_overlay_widget(
    adapter: Any,
    widget: Any,
    spec: OverlayWindowSpec,
    QLabel: Any,
    QLineEdit: Any,
    QPushButton: Any,
    QSizePolicy: Any,
    QVBoxLayout: Any,
    QHBoxLayout: Any,
    QButtonGroup: Any,
    Qt: Any | None = None,
) -> None:
    old = widget.layout()
    if old is not None:
        # Reuse the installed top-level layout instead of deleting it and
        # immediately assigning a new one.  Qt keeps the old layout installed
        # until the deferred delete event is processed; creating QVBoxLayout(widget)
        # in the same sync can therefore be rejected and leaves the overlay frame
        # visible but empty after a mode-toolbar rebuild.
        _clear_layout_tree(old)
        layout = old
    else:
        layout = QVBoxLayout(widget)
    field_edits: dict[str, Any] = {}
    field_selects: dict[str, Any] = {}
    try:
        widget._tool_core_overlay_field_selects = field_selects
    except Exception:
        pass
    kind = str(spec.overlay_kind)
    has_badge = _toolbar_has_badge(spec) if kind == "toolbar" else False
    inline_metric_toolbar = _is_inline_metric_toolbar(spec)
    if kind == "toolbar":
        if inline_metric_toolbar:
            layout.setContentsMargins(10, 6, 10, 6)
            layout.setSpacing(0)
        else:
            layout.setContentsMargins(8, 3 if has_badge else 7, 8, 7)
            layout.setSpacing(4 if has_badge else 3)
    else:
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(7)
    try:
        from PySide6.QtCore import Qt as _Qt

        layout.setAlignment(_Qt.AlignTop | (_Qt.AlignHCenter if kind == "toolbar" else _Qt.AlignLeft))
    except Exception:
        _Qt = None
    try:
        widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    except Exception:
        pass
    is_command_deck_spec = kind == "command_deck" or _is_command_deck(spec)
    if _is_metric_bar(spec):
        _rebuild_metric_bar_widget(
            adapter,
            widget,
            spec,
            QLabel,
            QLineEdit,
            QPushButton,
            QSizePolicy,
            QVBoxLayout,
            QHBoxLayout,
            Qt,
            layout,
            field_edits,
            _Qt,
        )
        return
    if spec.title and not is_command_deck_spec:
        title = QLabel(spec.title)
        title.setObjectName("ToolCoreOverlayTitle")
        title.setWordWrap(False)
        try:
            if _Qt is not None:
                title.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
        except Exception:
            pass
        if spec.movable:
            title.setToolTip("Drag this overlay to move it")
        if kind == "toolbar" and _Qt is not None:
            layout.addWidget(title, 0, _Qt.AlignHCenter)
        else:
            layout.addWidget(title)
    editable_fields = _toolbar_editable_fields(spec)
    if inline_metric_toolbar:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        try:
            if _Qt is not None:
                row.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
        except Exception:
            pass
        for field in spec.fields:
            if field.kind not in {"number", "text"} or not bool(field.enabled):
                continue
            cell = QHBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.setSpacing(4)
            if field.label:
                caption = QLabel(str(field.label))
                caption.setObjectName("ToolCoreOverlayFieldCaption")
                caption.setWordWrap(False)
                cell.addWidget(caption)
            edit = QLineEdit(str(field.value))
            edit.setObjectName("ToolCoreOverlayFieldEdit")
            edit.setProperty("toolCoreOverlayFieldId", str(field.id))
            edit.setProperty("toolCoreOverlayWindowId", str(spec.id))
            field_edits[str(field.id)] = edit
            edit.setEnabled(bool(field.enabled))
            edit.setMinimumWidth(82)
            edit.setMaximumWidth(112)
            if field.tooltip:
                edit.setToolTip(field.tooltip)
            _connect_editable_overlay_field(edit, field, spec, adapter)
            cell.addWidget(edit)
            row.addLayout(cell)
        button_groups: dict[str, Any] = {}
        for button_spec in spec.buttons:
            style = adapter._resolve_button_style(button_spec)
            label = adapter._button_label(button_spec, style)
            display_label = _toolbar_button_display_label(button_spec) if kind == "toolbar" else label
            vector_icon = str(getattr(button_spec, "icon", "") or "") if kind == "toolbar" else ""
            button = QPushButton(display_label if vector_icon else label)
            button.setObjectName("ToolCoreOverlayButton")
            button.setProperty("toolCoreButtonId", str(button_spec.id))
            button.setProperty("toolPaletteButton", bool(button_spec.group))
            button.setProperty("overlayButtonGroup", str(button_spec.group or ""))
            button.setProperty("overlayButtonStyle", str(style))
            button.setEnabled(button_spec.enabled)
            button.setCheckable(bool(button_spec.checkable))
            try:
                button.setMinimumHeight(28)
                button.setMaximumHeight(32)
                button.setCursor(Qt.PointingHandCursor)
            except Exception:
                pass
            tooltip = adapter._button_tooltip(button_spec)
            if tooltip:
                button.setToolTip(tooltip)
            if "close" in button_spec.id.lower():
                button.clicked.connect(lambda _checked=False, window_id=spec.id, w=widget: adapter._close(window_id, w))
            else:
                button.clicked.connect(lambda _checked=False, bid=button_spec.id: adapter._overlay_button_clicked(bid))
            row.addWidget(button)
        try:
            widget._tool_core_overlay_button_groups = tuple(button_groups.values())
        except Exception:
            pass
        layout.addLayout(row)
        try:
            widget._tool_core_overlay_field_edits = field_edits
        except Exception:
            pass
        adapter._stabilize_geometry(widget, spec)
        return
    if is_command_deck_spec:
        _rebuild_command_deck_widget(
            adapter,
            widget,
            spec,
            QLabel,
            QPushButton,
            QSizePolicy,
            QVBoxLayout,
            QHBoxLayout,
            QButtonGroup,
            Qt,
            layout,
            field_edits,
            _Qt,
        )
        return
    if kind == "toolbar" and _toolbar_sections(spec):
        _rebuild_sectioned_toolbar_widget(
            adapter,
            widget,
            spec,
            QLabel,
            QPushButton,
            QSizePolicy,
            QVBoxLayout,
            QHBoxLayout,
            QButtonGroup,
            Qt,
            layout,
            field_edits,
            _Qt,
        )
        return
    field_row = None
    for field in spec.fields:
        if str(getattr(field, "kind", "") or "") == "select":
            try:
                from PySide6.QtWidgets import QComboBox

                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(6)
                if field.label:
                    caption = QLabel(str(field.label))
                    caption.setObjectName("ToolCoreOverlayFieldCaption")
                    row.addWidget(caption)
                combo = QComboBox()
                combo.setObjectName("ToolCoreOverlayFieldSelect")
                combo.setProperty("toolCoreOverlayFieldId", str(field.id))
                combo.setProperty("toolCoreOverlayWindowId", str(spec.id))
                combo.setEnabled(bool(field.enabled))
                if field.tooltip:
                    combo.setToolTip(field.tooltip)
                for option_value, option_label in _select_options(field):
                    combo.addItem(option_label, option_value)
                desired = str(getattr(field, "value", "") or "")
                index = combo.findData(desired)
                if index < 0:
                    index = combo.findText(desired)
                if index >= 0:
                    combo.setCurrentIndex(index)
                field_selects[str(field.id)] = combo
                _connect_select_overlay_field(combo, field, spec, adapter)
                row.addWidget(combo, 1)
                layout.addLayout(row)
                continue
            except Exception:
                # Toolkit import/render failures degrade to the existing read-only
                # text representation instead of hiding the field entirely.
                pass
        is_badge = kind == "toolbar" and str(getattr(field, "id", "")).endswith("mode_badge")
        is_editable = field.kind in {"number", "text"} and bool(field.enabled)
        if is_editable:
            if kind == "toolbar":
                if field_row is None:
                    field_row = QHBoxLayout()
                    field_row.setContentsMargins(6, 0, 6, 0)
                    field_row.setSpacing(8)
                    try:
                        if _Qt is not None:
                            field_row.setAlignment(_Qt.AlignHCenter)
                    except Exception:
                        pass
                    layout.addLayout(field_row)
                cell = QHBoxLayout()
                cell.setContentsMargins(0, 0, 0, 0)
                cell.setSpacing(4)
                if field.label:
                    caption = QLabel(str(field.label))
                    caption.setObjectName("ToolCoreOverlayFieldCaption")
                    caption.setWordWrap(False)
                    cell.addWidget(caption)
                edit = QLineEdit(str(field.value))
                edit.setObjectName("ToolCoreOverlayFieldEdit")
                edit.setProperty("toolCoreOverlayFieldId", str(field.id))
                edit.setProperty("toolCoreOverlayWindowId", str(spec.id))
                field_edits[str(field.id)] = edit
                edit.setEnabled(bool(field.enabled))
                edit.setMinimumWidth(78)
                edit.setMaximumWidth(112)
                if field.tooltip:
                    edit.setToolTip(field.tooltip)
                _connect_editable_overlay_field(edit, field, spec, adapter)
                cell.addWidget(edit)
                field_row.addLayout(cell)
            else:
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(6)
                if field.label:
                    caption = QLabel(str(field.label))
                    caption.setObjectName("ToolCoreOverlayFieldCaption")
                    row.addWidget(caption)
                edit = QLineEdit(str(field.value))
                edit.setObjectName("ToolCoreOverlayFieldEdit")
                edit.setProperty("toolCoreOverlayFieldId", str(field.id))
                edit.setProperty("toolCoreOverlayWindowId", str(spec.id))
                field_edits[str(field.id)] = edit
                edit.setEnabled(bool(field.enabled))
                if field.tooltip:
                    edit.setToolTip(field.tooltip)
                _connect_editable_overlay_field(edit, field, spec, adapter)
                row.addWidget(edit)
                layout.addLayout(row)
            continue
        text = f"{field.label}: {field.value}" if field.label else str(field.value)
        label = QLabel(text)
        if is_badge:
            label.setObjectName("ToolCoreOverlayBadge")
            label.setWordWrap(False)
            label.setMinimumHeight(26)
            label.setMaximumHeight(28)
            try:
                badge_w = min(190, max(126, int(getattr(spec, "width_px", 760) * 0.22)))
                label.setMinimumWidth(badge_w)
                label.setMaximumWidth(badge_w)
            except Exception:
                pass
            try:
                if _Qt is not None:
                    label.setAlignment(_Qt.AlignHCenter | _Qt.AlignVCenter)
            except Exception:
                pass
        else:
            label.setObjectName("ToolCoreOverlayField")
            label.setWordWrap(True)
            label.setMinimumHeight(20)
        if field.tooltip:
            label.setToolTip(field.tooltip)
        if is_badge and _Qt is not None:
            layout.addWidget(label, 0, _Qt.AlignHCenter)
        else:
            layout.addWidget(label)
    if spec.buttons:
        row = QHBoxLayout()
        row.setContentsMargins(0 if kind == "toolbar" else 0, 1 if kind == "toolbar" else 2, 0 if kind == "toolbar" else 0, 0)
        # CAD toolbars are easier to scan when each tool owns a deterministic
        # compact slot: icon plus caption in one cell, with spacing included in
        # the public auto-fit calculation.
        row.setSpacing(4 if kind == "toolbar" else 6)
        toolbar_slot_widths = _toolbar_button_slot_widths(spec) if kind == "toolbar" else []
        buttons_tuple = tuple(getattr(spec, "buttons", ()) or ())
        try:
            if _Qt is not None and kind == "toolbar":
                row.setAlignment(_Qt.AlignHCenter)
        except Exception:
            pass
        button_groups: dict[str, Any] = {}
        for index, button_spec in enumerate(spec.buttons):
            style = adapter._resolve_button_style(button_spec)
            label = adapter._button_label(button_spec, style)
            display_label = _toolbar_button_display_label(button_spec) if kind == "toolbar" else label
            vector_icon = str(getattr(button_spec, "icon", "") or "") if kind == "toolbar" else ""
            button = QPushButton(display_label if vector_icon else label)
            button.setObjectName("ToolCoreOverlayButton")
            if vector_icon:
                button.setProperty("toolCoreVectorIcon", vector_icon)
                button.setProperty("toolCoreVectorIconSet", True)
                button.setProperty("toolCoreVectorLabel", display_label)
                button.setProperty("toolCoreVectorFullLabel", label)
                button.setProperty("toolCoreVectorNoElide", bool(getattr(button_spec, "display_label", None)))
                try:
                    button.setAccessibleName(label)
                    button.setAccessibleDescription(display_label)
                except Exception:
                    pass
            button.setProperty("toolCoreButtonId", str(button_spec.id))
            button.setProperty("toolPaletteButton", bool(button_spec.group))
            button.setProperty("overlayButtonGroup", str(button_spec.group or ""))
            button.setProperty("overlayButtonStyle", str(style))
            if vector_icon:
                # Fixed-size labelled slots keep icon centres and captions aligned
                # with the visual separators even as labels vary
                # (Polyline/Dimension/etc.). Apply the fixed size after
                # stylesheet-affecting properties are set so Qt cannot expand a
                # long label into the neighbouring cell.
                try:
                    toolbar_slot_width = toolbar_slot_widths[index] if index < len(toolbar_slot_widths) else _toolbar_button_slot_width(spec, button_spec)
                    button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    button.setFixedSize(toolbar_slot_width, 66)
                except Exception:
                    toolbar_slot_width = toolbar_slot_widths[index] if index < len(toolbar_slot_widths) else _toolbar_button_slot_width(spec, button_spec)
                    button.setMinimumSize(toolbar_slot_width, 66)
                    button.setMaximumSize(toolbar_slot_width, 66)
            button.setEnabled(button_spec.enabled)
            button.setCheckable(bool(button_spec.checkable))
            try:
                button.setCursor(Qt.PointingHandCursor)
            except Exception:
                pass
            if button_spec.group and button_spec.checkable:
                group_key = str(button_spec.group)
                group = button_groups.get(group_key)
                if group is None:
                    group = QButtonGroup(widget)
                    group.setExclusive(True)
                    button_groups[group_key] = group
                group.addButton(button)
            if button_spec.checkable:
                button.setChecked(bool(button_spec.checked))
            tooltip = adapter._button_tooltip(button_spec)
            if tooltip:
                button.setToolTip(tooltip)
            if "close" in button_spec.id.lower():
                button.clicked.connect(lambda _checked=False, window_id=spec.id, w=widget: adapter._close(window_id, w))
            else:
                button.clicked.connect(lambda _checked=False, bid=button_spec.id: adapter._overlay_button_clicked(bid))
            row.addWidget(button)
            if kind == "toolbar" and _toolbar_should_insert_separator(buttons_tuple, index):
                try:
                    from PySide6.QtWidgets import QFrame as _QFrame

                    separator = _QFrame(widget)
                    separator.setObjectName("ToolCoreOverlaySeparator")
                    separator.setFrameShape(_QFrame.VLine)
                    separator.setFixedWidth(12)
                    try:
                        separator.setMinimumHeight(42)
                        separator.setMaximumHeight(50)
                    except Exception:
                        pass
                    separator.setStyleSheet("QFrame#ToolCoreOverlaySeparator { background: transparent; border-left: 1px solid rgba(96, 118, 145, 82); margin-left: 5px; margin-right: 5px; margin-top: 5px; margin-bottom: 5px; }")
                    if _Qt is not None:
                        row.addWidget(separator, 0, _Qt.AlignVCenter)
                    else:
                        row.addWidget(separator)
                except Exception:
                    pass
        try:
            widget._tool_core_overlay_button_groups = tuple(button_groups.values())
        except Exception:
            pass
        layout.addLayout(row)
    try:
        widget._tool_core_overlay_field_edits = field_edits
        widget._tool_core_overlay_field_selects = field_selects
    except Exception:
        pass
    adapter._stabilize_geometry(widget, spec)
