# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import visual

from .models import MechanicalMode
from .session import MechanicalSession

TEST_WINDOW_ID = "mechanical.motion.test"
TEST_FIELD_PREFIX = "mechanical.motion.test.rpm."
TEST_ACTION_PREFIX = "mechanical.motion.test.action."


class MechanicalTestOverlay:
    """Compact single-driver controller shown only while Test mode is active."""

    def __init__(self, owner_tool: str, session: MechanicalSession) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session

    def sync(self, ctx: Any) -> None:
        if self.session.state.mode is not MechanicalMode.TEST:
            try:
                ctx.overlay.hide_window(TEST_WINDOW_ID)
            except Exception:
                pass
            return
        drivers = tuple(self.session.assembly.drivers.values())
        fields: list[visual.OverlayFieldSpec] = []
        if not drivers:
            fields.append(
                visual.OverlayFieldSpec(
                    "mechanical.motion.test.empty",
                    "",
                    "No driver is referenced. Create a rotary driver first.",
                    kind="info",
                )
            )
        for index, driver in enumerate(drivers, start=1):
            signed_rpm = float(driver.speed_rpm) * int(driver.direction)
            fields.append(
                visual.OverlayFieldSpec(
                    f"{TEST_FIELD_PREFIX}{driver.id}",
                    driver.name or f"Actuator {index}",
                    f"{signed_rpm:.6g}",
                    kind="number",
                    tooltip="Signed speed in rpm. Negative values reverse the driver.",
                    live=True,
                )
            )
        buttons = [
            visual.ToolButtonSpec(
                f"{TEST_ACTION_PREFIX}{'pause' if self.session.state.test_playing else 'play'}",
                "Pause" if self.session.state.test_playing else "Play",
                icon="tool.preview",
                style="primary",
            ),
            visual.ToolButtonSpec(f"{TEST_ACTION_PREFIX}reset", "Reset", icon="tool.reset", style="ghost"),
            visual.ToolButtonSpec(f"{TEST_ACTION_PREFIX}exit", "Exit test", icon="tool.close", style="secondary"),
        ]
        ctx.overlay.show_window(
            visual.OverlayWindowSpec(
                id=TEST_WINDOW_ID,
                title="Motion test",
                owner_tool=self.owner_tool,
                fields=fields,
                buttons=buttons,
                anchor="viewport_top_right",
                overlay_kind="inspector",
                width_px=300,
                movable=True,
                persistent=True,
                close_on_click_outside=False,
            )
        )

    def field_changed(self, field_id: str, value: str) -> tuple[str, float] | None:
        raw = str(field_id)
        if not raw.startswith(TEST_FIELD_PREFIX):
            return None
        driver_id = raw[len(TEST_FIELD_PREFIX):]
        driver = self.session.assembly.drivers.get(driver_id)
        if driver is None:
            return None
        try:
            signed_rpm = float(str(value).strip().replace(",", "."))
        except Exception:
            return None
        driver.direction = -1 if signed_rpm < 0.0 else 1
        driver.speed_rpm = abs(float(signed_rpm))
        driver.normalized()
        self.session.state.dirty = True
        return driver.id, signed_rpm

    @staticmethod
    def action_from_button(button_id: str) -> str | None:
        raw = str(button_id or "")
        return raw[len(TEST_ACTION_PREFIX):] if raw.startswith(TEST_ACTION_PREFIX) else None


__all__ = ["MechanicalTestOverlay", "TEST_ACTION_PREFIX", "TEST_FIELD_PREFIX", "TEST_WINDOW_ID"]
