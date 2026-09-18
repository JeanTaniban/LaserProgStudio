"""Declarative overlay UI specs for tools.

The overlay layer is intentionally independent from Qt widgets. Production
controllers can translate these specs into native widgets, while tests and tools
can exercise the same behavior without touching PySide directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

OverlayAnchor = Literal["cursor", "viewport_top_left", "viewport_top_center", "viewport_top_right", "viewport_bottom_center", "selection", "center"]
OverlayKind = Literal["palette", "toolbar", "command_deck", "metric_bar", "popover", "tooltip", "inspector", "modal", "context_menu"]
OverlayButtonStyle = Literal["auto", "primary", "secondary", "ghost", "toggle", "mode", "danger", "icon"]


@dataclass(slots=True)
class ToolButtonSpec:
    id: str
    label: str
    icon: str | None = None
    checkable: bool = False
    checked: bool = False
    enabled: bool = True
    group: str | None = None
    shortcut: str | None = None
    tooltip: str | None = None
    style: OverlayButtonStyle = "auto"
    # Optional layout contract for professional, tool-owned HUD toolbars.
    # ``label`` remains the semantic/full accessible name; ``display_label`` can
    # be shorter when a dense overlay needs a clean caption. ``section`` drives
    # explicit visual dividers and ``slot_width_px`` prevents the Qt renderer
    # from guessing per-tool dimensions.
    display_label: str | None = None
    section: str | None = None
    slot_width_px: int | None = None


@dataclass(slots=True)
class ToolPanelSpec:
    id: str
    title: str
    buttons: list[ToolButtonSpec] = field(default_factory=list)
    visible: bool = True


@dataclass(slots=True)
class OverlayFieldSpec:
    """A simple declarative field for lightweight tool windows.

    ``live`` opts editable ``text``/``number`` fields into immediate
    ``textEdited`` dispatch.  It is deliberately opt-in so metric overlays and
    validation popovers keep their stable commit-on-focus-out behaviour while
    tools such as Plan Tracer's Pattern palette can drive a true live preview.
    """

    id: str
    label: str
    value: str = ""
    kind: Literal["text", "number", "toggle", "select", "separator", "info"] = "text"
    enabled: bool = True
    tooltip: str | None = None
    options: tuple[str | tuple[str, str], ...] = ()
    live: bool = False




@dataclass(slots=True)
class OverlayModeSpec:
    """High-level declaration for one exclusive toolbar mode.

    Tool authors describe the mode semantics once; the overlay API converts it
    into a checkable button with the correct exclusive group/style.  Dense tools
    can also provide explicit layout hints so the shared renderer stays generic
    without becoming a brittle per-tool auto-layout engine.
    """

    id: str
    label: str
    icon: str | None = None
    shortcut: str | None = None
    tooltip: str | None = None
    enabled: bool = True
    style: OverlayButtonStyle = "mode"
    display_label: str | None = None
    section: str | None = None
    slot_width_px: int | None = None


@dataclass(slots=True)
class OverlayActionSpec:
    """High-level declaration for a toolbar action button.

    Actions are not part of the exclusive mode group by default.  This keeps
    palettes such as Plan Tracer readable without every tool hand-writing button
    policies.  Optional layout hints let a known fixed toolbar remain precise
    while simple overlays keep the automatic defaults.
    """

    id: str
    label: str
    icon: str | None = None
    shortcut: str | None = None
    tooltip: str | None = None
    enabled: bool = True
    style: OverlayButtonStyle = "ghost"
    display_label: str | None = None
    section: str | None = None
    slot_width_px: int | None = None



@dataclass(slots=True)
class OverlayToolbarSectionSpec:
    """Declarative section for a modern Creator toolbar.

    A section groups related modes/actions and gives the renderer enough
    information to build a readable HUD without every tool hand-writing widths,
    separators or caption hacks.  The section id becomes the stable layout key;
    the label is visual only.
    """

    id: str
    label: str
    modes: tuple[OverlayModeSpec, ...] = ()
    actions: tuple[OverlayActionSpec, ...] = ()


def toolbar_button_slot_width_px(button: ToolButtonSpec) -> int:
    """Return the preferred pixel width for one CAD-style toolbar slot.

    Vector toolbars are compact but no longer icon-only.  The label is visible
    under the pictogram, so the API must size each slot from the real caption
    instead of relying on hidden Qt text minimums.  Tools with a known fixed
    palette can provide ``slot_width_px``; the API then respects that explicit
    contract instead of trying to infer a magic value.
    """

    explicit_width = getattr(button, "slot_width_px", None)
    if explicit_width is not None:
        try:
            return max(44, min(132, int(explicit_width)))
        except Exception:
            pass

    label = str(getattr(button, "display_label", None) or getattr(button, "label", "") or "")
    icon = str(getattr(button, "icon", "") or "")
    style = str(getattr(button, "style", "auto") or "auto")
    if icon:
        key = icon.replace("sketch.", "")
        # V2 toolbars are readable first: full captions are allowed to breathe
        # and the renderer computes the rail width from those captions.  This
        # replaces the old Plan Tracer-specific 50-70px slot contract.
        semantic_minimums = {
            "arc": 60,
            "line": 60,
            "point": 64,
            "circle": 68,
            "delete": 70,
            "modify": 70,
            "face": 78,
            "polyline": 78,
            "rectangle": 86,
            "half_circle": 92,
            "dimension": 86,
        }
        estimated = 32 + int(round(len(label) * 5.2))
        if style == "icon" and not label:
            return 42
        return max(56, min(96, max(semantic_minimums.get(key, 70), estimated)))
    length = len(label)
    estimated = 42 + int(round(length * 6.0))
    if bool(getattr(button, "group", None)) and bool(getattr(button, "checkable", False)):
        return max(68, min(124, estimated))
    if style == "ghost":
        return max(76, min(124, estimated))
    return max(68, min(128, estimated))


def _mode_toolbar_button_family(button: ToolButtonSpec) -> str:
    explicit_section = str(getattr(button, "section", "") or "").strip()
    if explicit_section:
        return f"section:{explicit_section}"
    if bool(getattr(button, "checkable", False)) and bool(getattr(button, "group", None)):
        return f"mode:{getattr(button, 'group', '')}"
    return "actions"


def _mode_toolbar_separator_count(buttons: list[ToolButtonSpec] | tuple[ToolButtonSpec, ...]) -> int:
    total = 0
    for index in range(max(0, len(buttons) - 1)):
        if _mode_toolbar_button_family(buttons[index]) != _mode_toolbar_button_family(buttons[index + 1]):
            total += 1
    return total


def mode_toolbar_auto_width_px(buttons: list[ToolButtonSpec] | tuple[ToolButtonSpec, ...]) -> int:
    """Return the compact outer width for a standard mode toolbar.

    ``width_px=0`` in :func:`build_mode_toolbar_window` delegates to this
    helper.  It keeps the API responsible for the default professional size,
    while tools can still request a deliberately fixed width when they need one.
    """

    button_list = tuple(buttons or ())
    if not button_list:
        return 320
    content = sum(toolbar_button_slot_width_px(button) for button in button_list)
    # Semantic dividers mark explicit tool sections when a dense CAD toolbar
    # provides them, or the generic mode/action split otherwise. Inter-item
    # spacing is part of the real Qt row geometry, so it must be included in
    # auto-fit; otherwise the last labelled buttons can look clipped even though
    # the content calculation passes.
    separator_count = _mode_toolbar_separator_count(button_list)
    dividers = separator_count * 12
    row_items = len(button_list) + separator_count
    spacing = max(0, row_items - 1) * 4
    margins = 28
    return max(420, min(880, int(content + dividers + spacing + margins)))


def mode_badge_field(
    field_id: str,
    *,
    label: str = "Drawing",
    value: str = "",
    tooltip: str | None = None,
) -> OverlayFieldSpec:
    """Return the standard compact mode badge used by CAD-style toolbars."""

    return OverlayFieldSpec(
        id=str(field_id),
        label=str(label),
        value=str(value),
        kind="info",
        tooltip=tooltip,
    )


def build_mode_toolbar_window(
    *,
    window_id: str,
    owner_tool: str,
    group_id: str,
    modes: list[OverlayModeSpec] | tuple[OverlayModeSpec, ...],
    active_mode_id: str,
    actions: list[OverlayActionSpec] | tuple[OverlayActionSpec, ...] = (),
    badge_id: str | None = None,
    badge_label: str = "Drawing",
    badge_value: str | None = None,
    badge_tooltip: str | None = None,
    title: str = "",
    anchor: OverlayAnchor = "viewport_bottom_center",
    width_px: int = 760,
    movable: bool = True,
    persistent: bool = False,
    cursor_offset_px: tuple[int, int] = (14, 18),
) -> OverlayWindowSpec:
    """Build the standard exclusive-mode toolbar window.

    This is the preferred Creator API path for compact drawing/transform
    palettes: tools provide mode/action declarations, while the overlay layer
    owns button styles, checked states, grouping and the optional mode badge.
    """

    active = str(active_mode_id)
    buttons: list[ToolButtonSpec] = []
    active_label = ""
    for mode in modes:
        if str(mode.id) == active:
            active_label = str(mode.label)
        buttons.append(
            ToolButtonSpec(
                id=str(mode.id),
                label=str(mode.label),
                icon=mode.icon,
                checkable=True,
                checked=str(mode.id) == active,
                enabled=bool(mode.enabled),
                group=str(group_id),
                shortcut=mode.shortcut,
                tooltip=mode.tooltip,
                style=mode.style,
                display_label=mode.display_label,
                section=mode.section,
                slot_width_px=mode.slot_width_px,
            )
        )
    for action in actions:
        buttons.append(
            ToolButtonSpec(
                id=str(action.id),
                label=str(action.label),
                icon=action.icon,
                checkable=False,
                checked=False,
                enabled=bool(action.enabled),
                group=None,
                shortcut=action.shortcut,
                tooltip=action.tooltip,
                style=action.style,
                display_label=action.display_label,
                section=action.section,
                slot_width_px=action.slot_width_px,
            )
        )
    fields: list[OverlayFieldSpec] = []
    if badge_id is not None:
        fields.append(
            mode_badge_field(
                str(badge_id),
                label=badge_label,
                value=str(badge_value if badge_value is not None else active_label),
                tooltip=badge_tooltip,
            )
        )
    resolved_width_px = int(width_px)
    if resolved_width_px <= 0:
        resolved_width_px = mode_toolbar_auto_width_px(buttons)
    return OverlayWindowSpec(
        id=str(window_id),
        title=str(title),
        owner_tool=str(owner_tool),
        overlay_kind="toolbar",
        anchor=anchor,
        width_px=resolved_width_px,
        movable=bool(movable),
        persistent=bool(persistent),
        fields=fields,
        buttons=buttons,
        cursor_offset_px=(int(cursor_offset_px[0]), int(cursor_offset_px[1])),
        accent_color=str(accent_color) if accent_color else None,
    )


def _sectioned_toolbar_visible_sections(
    buttons: list[ToolButtonSpec] | tuple[ToolButtonSpec, ...],
    sections: list[OverlayToolbarSectionSpec] | tuple[OverlayToolbarSectionSpec, ...],
) -> tuple[OverlayToolbarSectionSpec, ...]:
    used = {str(getattr(button, "section", "") or "") for button in buttons}
    return tuple(section for section in tuple(sections or ()) if str(section.id) in used)


def sectioned_toolbar_auto_width_px(
    buttons: list[ToolButtonSpec] | tuple[ToolButtonSpec, ...],
    sections: list[OverlayToolbarSectionSpec] | tuple[OverlayToolbarSectionSpec, ...],
    *,
    badge: bool = False,
) -> int:
    """Return the width of the sectioned HUD toolbar.

    Unlike the legacy compact mode toolbar, this calculation is based on grouped
    cards: button captions stay readable, section gutters are explicit and an
    optional status pill is accounted for as a real item in the row.
    """

    button_list = tuple(buttons or ())
    if not button_list:
        return 360
    visible_sections = _sectioned_toolbar_visible_sections(button_list, tuple(sections or ()))
    section_ids = [str(section.id) for section in visible_sections] or [""]
    by_section = {section_id: [button for button in button_list if str(getattr(button, "section", "") or "") == section_id] for section_id in section_ids}
    orphan_buttons = [button for button in button_list if str(getattr(button, "section", "") or "") not in by_section]
    if orphan_buttons:
        by_section.setdefault("", []).extend(orphan_buttons)
    content = sum(toolbar_button_slot_width_px(button) for button in button_list)
    button_spacing = sum(max(0, len(group) - 1) * 4 for group in by_section.values())
    section_padding = len(by_section) * 16
    visible_item_count = len(by_section) + (1 if badge else 0)
    section_spacing = max(0, visible_item_count - 1) * 6
    status_pill = 116 if badge else 0
    margins = 22
    return max(560, min(1120, int(content + button_spacing + section_padding + section_spacing + status_pill + margins)))


def command_deck_auto_width_px(
    buttons: list[ToolButtonSpec] | tuple[ToolButtonSpec, ...],
    sections: list[OverlayToolbarSectionSpec] | tuple[OverlayToolbarSectionSpec, ...],
    *,
    badge: bool = False,
) -> int:
    """Return the natural width for a compact HUD command deck.

    A command deck is not a ribbon. It is a small, tool-owned palette made of
    fixed command cells, so the user keeps most of the viewport visible. The
    calculation intentionally favors predictable authoring over stretching: each
    button chooses a readable slot, sections add only their real gutters, and the
    mode chip is accounted for as a fixed header item.
    """

    button_list = tuple(buttons or ())
    if not button_list:
        return 420
    visible_sections = _sectioned_toolbar_visible_sections(button_list, tuple(sections or ()))
    by_section: dict[str, list[ToolButtonSpec]] = {
        str(section.id): [button for button in button_list if str(getattr(button, "section", "") or "") == str(section.id)]
        for section in visible_sections
    }
    orphan_buttons = [button for button in button_list if str(getattr(button, "section", "") or "") not in by_section]
    if orphan_buttons:
        by_section.setdefault("", []).extend(orphan_buttons)
    section_widths = []
    for group in by_section.values():
        if not group:
            continue
        slots = [toolbar_button_slot_width_px(button) for button in group]
        section_widths.append(sum(slots) + max(0, len(slots) - 1) * 8 + 20)
    # The Command Deck is deliberately a single row of readable command tiles.
    # It should be wider than the previous compact deck because the icons are
    # the main interaction target, but it must still remain inside a normal
    # desktop viewport.
    command_row = sum(section_widths) + max(0, len(section_widths) - 1) * 10
    header_chip = 144 if badge else 0
    header_min = 320 + header_chip
    outer = 24
    return max(720, min(1240, int(max(command_row, header_min) + outer)))


def build_command_deck_window(
    *,
    window_id: str,
    owner_tool: str,
    group_id: str,
    sections: list[OverlayToolbarSectionSpec] | tuple[OverlayToolbarSectionSpec, ...],
    active_mode_id: str,
    badge_id: str | None = None,
    badge_label: str = "Mode",
    badge_value: str | None = None,
    badge_tooltip: str | None = None,
    status_id: str | None = None,
    status_label: str = "Status",
    status_value: str = "",
    title: str = "",
    anchor: OverlayAnchor = "viewport_top_left",
    width_px: int = 0,
    movable: bool = True,
    persistent: bool = False,
    cursor_offset_px: tuple[int, int] = (0, 0),
    accent_color: str | None = None,
) -> OverlayWindowSpec:
    """Build a compact floating command deck for viewport-first tools.

    This is the replacement for oversized ribbon-like HUDs. Tool authors keep a
    semantic API (sections, modes, actions), while the Qt renderer owns the real
    widget geometry and paints a dense, readable palette.
    """

    active = str(active_mode_id)
    buttons: list[ToolButtonSpec] = []
    active_label = ""
    section_list = tuple(sections or ())
    for section in section_list:
        section_id = str(section.id)
        for mode in tuple(section.modes or ()):  # stable order is part of the API contract
            if str(mode.id) == active:
                active_label = str(mode.label)
            buttons.append(
                ToolButtonSpec(
                    id=str(mode.id),
                    label=str(mode.label),
                    icon=mode.icon,
                    checkable=True,
                    checked=str(mode.id) == active,
                    enabled=bool(mode.enabled),
                    group=str(group_id),
                    shortcut=mode.shortcut,
                    tooltip=mode.tooltip,
                    style=mode.style,
                    display_label=mode.display_label or mode.label,
                    section=section_id,
                    slot_width_px=mode.slot_width_px,
                )
            )
        for action in tuple(section.actions or ()):  # actions keep their own enabled state
            buttons.append(
                ToolButtonSpec(
                    id=str(action.id),
                    label=str(action.label),
                    icon=action.icon,
                    checkable=False,
                    checked=False,
                    enabled=bool(action.enabled),
                    group=None,
                    shortcut=action.shortcut,
                    tooltip=action.tooltip,
                    style=action.style,
                    display_label=action.display_label or action.label,
                    section=section_id,
                    slot_width_px=action.slot_width_px,
                )
            )
    fields: list[OverlayFieldSpec] = []
    if badge_id is not None:
        fields.append(
            mode_badge_field(
                str(badge_id),
                label=badge_label,
                value=str(badge_value if badge_value is not None else active_label),
                tooltip=badge_tooltip,
            )
        )
    if status_id is not None:
        fields.append(
            OverlayFieldSpec(
                id=str(status_id),
                label=str(status_label),
                value=str(status_value),
                kind="info",
                tooltip=str(status_value) if status_value else None,
            )
        )
    resolved_width_px = int(width_px)
    if resolved_width_px <= 0:
        resolved_width_px = command_deck_auto_width_px(buttons, section_list, badge=bool(badge_id))
    return OverlayWindowSpec(
        id=str(window_id),
        title=str(title),
        owner_tool=str(owner_tool),
        overlay_kind="command_deck",
        anchor=anchor,
        width_px=resolved_width_px,
        movable=bool(movable),
        persistent=bool(persistent),
        fields=fields,
        buttons=buttons,
        toolbar_sections=list(section_list),
        cursor_offset_px=(int(cursor_offset_px[0]), int(cursor_offset_px[1])),
        accent_color=str(accent_color) if accent_color else None,
    )


def build_sectioned_toolbar_window(
    *,
    window_id: str,
    owner_tool: str,
    group_id: str,
    sections: list[OverlayToolbarSectionSpec] | tuple[OverlayToolbarSectionSpec, ...],
    active_mode_id: str,
    badge_id: str | None = None,
    badge_label: str = "Mode",
    badge_value: str | None = None,
    badge_tooltip: str | None = None,
    title: str = "",
    anchor: OverlayAnchor = "viewport_top_center",
    width_px: int = 0,
    movable: bool = True,
    persistent: bool = False,
    cursor_offset_px: tuple[int, int] = (0, 0),
    accent_color: str | None = None,
) -> OverlayWindowSpec:
    """Build a sectioned mode/action toolbar for complex Creator tools.

    Tool authors describe intent with sections instead of micromanaging slot
    widths.  The resulting window is still a normal ``overlay_kind='toolbar'``
    so existing overlay managers, shortcuts and mode groups keep working.
    """

    active = str(active_mode_id)
    buttons: list[ToolButtonSpec] = []
    active_label = ""
    section_list = tuple(sections or ())
    for section in section_list:
        section_id = str(section.id)
        for mode in tuple(section.modes or ()):
            if str(mode.id) == active:
                active_label = str(mode.label)
            buttons.append(
                ToolButtonSpec(
                    id=str(mode.id),
                    label=str(mode.label),
                    icon=mode.icon,
                    checkable=True,
                    checked=str(mode.id) == active,
                    enabled=bool(mode.enabled),
                    group=str(group_id),
                    shortcut=mode.shortcut,
                    tooltip=mode.tooltip,
                    style=mode.style,
                    display_label=mode.display_label or mode.label,
                    section=section_id,
                    slot_width_px=mode.slot_width_px,
                )
            )
        for action in tuple(section.actions or ()):
            buttons.append(
                ToolButtonSpec(
                    id=str(action.id),
                    label=str(action.label),
                    icon=action.icon,
                    checkable=False,
                    checked=False,
                    enabled=bool(action.enabled),
                    group=None,
                    shortcut=action.shortcut,
                    tooltip=action.tooltip,
                    style=action.style,
                    display_label=action.display_label or action.label,
                    section=section_id,
                    slot_width_px=action.slot_width_px,
                )
            )
    fields: list[OverlayFieldSpec] = []
    if badge_id is not None:
        fields.append(
            mode_badge_field(
                str(badge_id),
                label=badge_label,
                value=str(badge_value if badge_value is not None else active_label),
                tooltip=badge_tooltip,
            )
        )
    resolved_width_px = int(width_px)
    if resolved_width_px <= 0:
        resolved_width_px = sectioned_toolbar_auto_width_px(buttons, section_list, badge=bool(fields))
    return OverlayWindowSpec(
        id=str(window_id),
        title=str(title),
        owner_tool=str(owner_tool),
        overlay_kind="toolbar",
        anchor=anchor,
        width_px=resolved_width_px,
        movable=bool(movable),
        persistent=bool(persistent),
        fields=fields,
        buttons=buttons,
        toolbar_sections=list(section_list),
        cursor_offset_px=(int(cursor_offset_px[0]), int(cursor_offset_px[1])),
        accent_color=str(accent_color) if accent_color else None,
    )


@dataclass(slots=True)
class OverlayWindowSpec:
    """Declarative floating window/palette used by tools.

    These windows are meant for small tool UIs: transform inspectors, snap
    settings, Plan tracer mode palettes, confirmation popups and hover details.
    The spec keeps the state in the shared layer; a Qt adapter can render it.
    """

    id: str
    title: str
    owner_tool: str
    accent_color: str | None = None
    fields: list[OverlayFieldSpec] = field(default_factory=list)
    buttons: list[ToolButtonSpec] = field(default_factory=list)
    toolbar_sections: list[OverlayToolbarSectionSpec] = field(default_factory=list)
    anchor: OverlayAnchor = "viewport_top_right"
    overlay_kind: OverlayKind = "palette"
    width_px: int = 260
    visible: bool = True
    modal: bool = False
    movable: bool = True
    close_on_click_outside: bool = False
    persistent: bool = False
    position_px: tuple[int, int] | None = None
    cursor_offset_px: tuple[int, int] = (14, 18)
    clamp_to_viewport: bool = True
