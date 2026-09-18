"""Overlay state manager independent from Qt widgets."""
from __future__ import annotations

from dataclasses import replace

from .diagnostics import OverlayDragDiagnostics, OverlayDragReport
from .specs import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec, ToolPanelSpec


class OverlayManager:
    def __init__(self) -> None:
        self.panels: dict[str, ToolPanelSpec] = {}
        self.windows: dict[str, OverlayWindowSpec] = {}
        self.buttons: dict[str, ToolButtonSpec] = {}
        self.group_active: dict[str, str | None] = {}
        self._drag_window_id: str | None = None
        self._drag_offset_px: tuple[int, int] = (0, 0)
        self.drag_diagnostics = OverlayDragDiagnostics()


    def clear_drag_diagnostics(self) -> None:
        self.drag_diagnostics.clear()

    def drag_report(self) -> OverlayDragReport:
        return self.drag_diagnostics.report()

    def show_panel(self, panel: ToolPanelSpec) -> None:
        self.panels[panel.id] = panel
        for button in panel.buttons:
            self.buttons[button.id] = button
            if button.group and button.checked:
                self.set_group_active(button.group, button.id)

    def hide_panel(self, panel_id: str) -> None:
        panel = self.panels.get(panel_id)
        if panel is not None:
            panel.visible = False

    def close_other_panels(self, keep_panel_id: str | None = None) -> None:
        for panel_id, panel in self.panels.items():
            if panel_id != keep_panel_id:
                panel.visible = False

    def show_window(self, window: OverlayWindowSpec) -> None:
        """Show or replace a lightweight floating tool window.

        Button state is registered in the same table as panel buttons, so
        exclusive groups and enable/checked state work consistently everywhere.
        When an existing movable window is refreshed declaratively, keep its last
        concrete position unless the caller explicitly provides a new position.
        This prevents anchored palettes from fighting the drag constraint.
        """
        old = self.windows.get(window.id)
        if old is not None and window.position_px is None and old.position_px is not None:
            window = replace(window, position_px=old.position_px)
        self.windows[window.id] = window
        for button in window.buttons:
            self.buttons[button.id] = button
            if button.group and button.checked:
                self.set_group_active(button.group, button.id)

    def show_message_window(
        self,
        window_id: str,
        *,
        owner_tool: str,
        title: str,
        message: str,
        anchor: str = "cursor",
        close_on_click_outside: bool = True,
    ) -> OverlayWindowSpec:
        window = OverlayWindowSpec(
            id=window_id,
            title=title,
            owner_tool=owner_tool,
            fields=[OverlayFieldSpec(f"{window_id}.message", "", message, kind="info")],
            anchor=anchor,  # type: ignore[arg-type]
            close_on_click_outside=close_on_click_outside,
            persistent=False,
        )
        self.show_window(window)
        return window

    def show_popover_at_cursor(
        self,
        window_id: str,
        *,
        owner_tool: str,
        title: str,
        cursor_px: tuple[int, int],
        fields: list[OverlayFieldSpec] | None = None,
        buttons: list[ToolButtonSpec] | None = None,
        width_px: int = 260,
        movable: bool = True,
        close_on_click_outside: bool = True,
        overlay_kind: str = "popover",
        offset_px: tuple[int, int] = (14, 18),
    ) -> OverlayWindowSpec:
        """Show a small overlay under the pointer, like Blender-style popovers."""
        x = int(cursor_px[0]) + int(offset_px[0])
        y = int(cursor_px[1]) + int(offset_px[1])
        window = OverlayWindowSpec(
            id=window_id,
            title=title,
            owner_tool=owner_tool,
            fields=list(fields or []),
            buttons=list(buttons or []),
            anchor="cursor",
            overlay_kind=overlay_kind,  # type: ignore[arg-type]
            width_px=int(width_px),
            movable=bool(movable),
            close_on_click_outside=bool(close_on_click_outside),
            position_px=(x, y),
            cursor_offset_px=offset_px,
        )
        self.show_window(window)
        return window


    def show_context_popover_at_cursor(
        self,
        window_id: str,
        *,
        owner_tool: str,
        title: str,
        cursor_px: tuple[int, int],
        fields: list[OverlayFieldSpec] | None = None,
        buttons: list[ToolButtonSpec] | None = None,
        width_px: int = 240,
        offset_px: tuple[int, int] = (18, 14),
    ) -> OverlayWindowSpec:
        """Show a non-draggable Blender-style popover next to the pointer.

        This is the safe default for transient viewport options: it appears next
        to the cursor, does not participate in the draggable-window system, and
        closes on the next viewport click outside the widget. Tools should prefer
        this for middle-click/context popovers instead of building ad-hoc Qt
        windows.
        """
        return self.show_popover_at_cursor(
            window_id,
            owner_tool=owner_tool,
            title=title,
            cursor_px=cursor_px,
            fields=fields,
            buttons=buttons,
            width_px=width_px,
            movable=False,
            close_on_click_outside=True,
            overlay_kind="context_menu",
            offset_px=offset_px,
        )

    def show_tooltip(
        self,
        window_id: str,
        *,
        owner_tool: str,
        text: str,
        cursor_px: tuple[int, int],
        width_px: int = 220,
    ) -> OverlayWindowSpec:
        return self.show_popover_at_cursor(
            window_id,
            owner_tool=owner_tool,
            title="",
            cursor_px=cursor_px,
            fields=[OverlayFieldSpec(f"{window_id}.text", "", text, kind="info")],
            width_px=width_px,
            movable=False,
            close_on_click_outside=True,
            overlay_kind="tooltip",
            offset_px=(12, 16),
        )

    def begin_window_drag(self, window_id: str, pointer_px: tuple[int, int]) -> bool:
        window = self.windows.get(window_id)
        if window is None or not window.visible or not window.movable:
            return False
        x, y = window.position_px or (0, 0)
        self._drag_window_id = window_id
        self._drag_offset_px = (int(pointer_px[0]) - int(x), int(pointer_px[1]) - int(y))
        return True

    def drag_window(self, pointer_px: tuple[int, int]) -> bool:
        window_id = self._drag_window_id
        if window_id is None:
            return False
        window = self.windows.get(window_id)
        if window is None or not window.visible or not window.movable:
            self.end_window_drag()
            return False
        x = int(pointer_px[0]) - int(self._drag_offset_px[0])
        y = int(pointer_px[1]) - int(self._drag_offset_px[1])
        self.windows[window_id] = replace(window, position_px=(x, y))
        return True

    def end_window_drag(self) -> str | None:
        window_id = self._drag_window_id
        self._drag_window_id = None
        self._drag_offset_px = (0, 0)
        return window_id


    def hide_window(self, window_id: str) -> bool:
        window = self.windows.get(window_id)
        if window is None:
            return False
        self.windows[window_id] = replace(window, visible=False)
        return True

    def close_tool_windows(self, owner_tool: str, *, include_persistent: bool = False) -> int:
        count = 0
        for window_id, window in list(self.windows.items()):
            if window.owner_tool != owner_tool:
                continue
            if window.persistent and not include_persistent:
                continue
            if window.visible:
                self.windows[window_id] = replace(window, visible=False)
                count += 1
        return count

    def close_transient_windows(self) -> int:
        count = 0
        for window_id, window in list(self.windows.items()):
            if window.persistent or not window.visible:
                continue
            self.windows[window_id] = replace(window, visible=False)
            count += 1
        return count

    def handle_click_outside(self, *, owner_tool: str | None = None) -> int:
        """Close click-away windows without every tool writing its own handler."""
        count = 0
        for window_id, window in list(self.windows.items()):
            if owner_tool is not None and window.owner_tool != owner_tool:
                continue
            if not window.visible or not window.close_on_click_outside:
                continue
            self.windows[window_id] = replace(window, visible=False)
            count += 1
        return count

    def set_window_position(self, window_id: str, x_px: int, y_px: int) -> bool:
        window = self.windows.get(window_id)
        if window is None:
            return False
        self.windows[window_id] = replace(window, position_px=(int(x_px), int(y_px)))
        return True

    def update_field(self, window_id: str, field_id: str, value: str) -> bool:
        window = self.windows.get(window_id)
        if window is None:
            return False
        fields = [replace(field, value=str(value)) if field.id == field_id else field for field in window.fields]
        self.windows[window_id] = replace(window, fields=fields)
        return any(field.id == field_id for field in window.fields)


    def _replace_button_everywhere(self, button_id: str, new_button: ToolButtonSpec) -> None:
        """Keep the global button table and declarative specs in sync.

        Qt rebuilds windows from ``OverlayWindowSpec.buttons``.  If a click only
        updates ``self.buttons``, the next adapter sync still reads stale checked
        values from the window spec, so exclusive palettes appear to update only
        after an unrelated hover/rebuild.
        """

        self.buttons[button_id] = new_button
        for panel_id, panel in list(self.panels.items()):
            changed = False
            buttons = []
            for button in panel.buttons:
                if button.id == button_id:
                    buttons.append(new_button)
                    changed = True
                else:
                    buttons.append(button)
            if changed:
                self.panels[panel_id] = replace(panel, buttons=buttons)
        for window_id, window in list(self.windows.items()):
            changed = False
            buttons = []
            for button in window.buttons:
                if button.id == button_id:
                    buttons.append(new_button)
                    changed = True
                else:
                    buttons.append(button)
            if changed:
                self.windows[window_id] = replace(window, buttons=buttons)

    def set_button_checked(self, button_id: str, checked: bool) -> bool:
        button = self.buttons.get(button_id)
        if button is None or not button.checkable:
            return False
        self._replace_button_everywhere(button_id, replace(button, checked=checked))
        return True

    def set_button_enabled(self, button_id: str, enabled: bool) -> bool:
        button = self.buttons.get(button_id)
        if button is None:
            return False
        self._replace_button_everywhere(button_id, replace(button, enabled=enabled))
        return True

    def set_group_active(self, group: str, button_id: str | None) -> None:
        self.group_active[group] = button_id
        for existing_id, button in list(self.buttons.items()):
            if button.group == group and button.checkable:
                self._replace_button_everywhere(existing_id, replace(button, checked=(existing_id == button_id)))

    def toggle_button(self, button_id: str) -> bool:
        button = self.buttons.get(button_id)
        if button is None or not button.enabled:
            return False
        if button.group:
            # Tool palettes are exclusive groups: clicking an enabled grouped
            # button selects it, but never leaves the group without an active
            # value.  This avoids transient "no tool" states in Creator tools
            # such as Plan tracer.
            self.set_group_active(button.group, button_id)
            return True
        if button.checkable:
            return self.set_button_checked(button_id, not button.checked)
        return True

    def button(self, button_id: str) -> ToolButtonSpec | None:
        return self.buttons.get(button_id)

    def window(self, window_id: str) -> OverlayWindowSpec | None:
        return self.windows.get(window_id)
