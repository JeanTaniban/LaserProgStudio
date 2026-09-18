# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

_WORD_RE = re.compile(r"([A-Za-z])\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))")
_PAREN_COMMENT_RE = re.compile(r"\([^)]*\)")


@dataclass(frozen=True, slots=True)
class MachineEnvelope:
    """Conservative machine movement envelope in millimetres."""

    width_mm: float
    height_mm: float
    inset_mm: float = 0.0
    max_feed_mm_min: float = 30_000.0
    max_power_s: int = 1000

    @property
    def min_x_mm(self) -> float:
        return max(0.0, float(self.inset_mm))

    @property
    def min_y_mm(self) -> float:
        return max(0.0, float(self.inset_mm))

    @property
    def max_x_mm(self) -> float:
        return max(self.min_x_mm, float(self.width_mm) - max(0.0, float(self.inset_mm)))

    @property
    def max_y_mm(self) -> float:
        return max(self.min_y_mm, float(self.height_mm) - max(0.0, float(self.inset_mm)))


@dataclass(frozen=True, slots=True)
class SafetyIssue:
    line_number: int
    line: str
    message: str

    def format(self) -> str:
        prefix = f"Line {self.line_number}: " if self.line_number > 0 else ""
        suffix = f" [{self.line}]" if self.line else ""
        return f"{prefix}{self.message}{suffix}"


@dataclass(frozen=True, slots=True)
class GCodeSafetyReport:
    violations: tuple[SafetyIssue, ...]
    warnings: tuple[SafetyIssue, ...]
    motion_lines: int
    laser_on_lines: int
    min_x_mm: float
    min_y_mm: float
    max_x_mm: float
    max_y_mm: float

    @property
    def safe(self) -> bool:
        return not self.violations

    def blocking_text(self, *, limit: int = 12) -> str:
        items = [issue.format() for issue in self.violations[: max(1, int(limit))]]
        remaining = len(self.violations) - len(items)
        if remaining > 0:
            items.append(f"… and {remaining} other blocking issue(s).")
        return "\n".join(items)


def validate_gcode(
    lines: Iterable[str],
    envelope: MachineEnvelope,
    *,
    allow_laser: bool,
    allow_relative_z: bool = False,
    max_relative_z_depth_mm: float = 0.0,
    z_down_sign: int = -1,
) -> GCodeSafetyReport:
    """Validate a restricted, auditable GRBL program before transmission.

    LaserProg deliberately accepts only the small G-code subset it generates.
    Unsupported modal or coordinate-changing commands are rejected rather than
    guessed, because a permissive parser would make the envelope check unsafe.
    """

    violations: list[SafetyIssue] = []
    warnings: list[SafetyIssue] = []
    unit_scale = 1.0
    absolute_mode: bool | None = None
    motion_mode: int | None = None
    current_x = 0.0
    current_y = 0.0
    relative_z = 0.0
    laser_on = False
    saw_explicit_m5 = False
    motion_lines = 0
    laser_on_lines = 0
    xs = [current_x]
    ys = [current_y]
    tol = 1.0e-6
    allowed_g = {0, 1, 4, 20, 21, 90, 91, 94}
    allowed_m = {3, 4, 5}

    for line_number, raw in enumerate(lines, start=1):
        original = str(raw or "").strip()
        line = _strip_comments(original)
        if not line:
            continue
        words = _words(line)
        if not words:
            violations.append(SafetyIssue(line_number, original, "Unrecognised or non-numeric machine command."))
            continue
        unsupported_letters = sorted(set(words) - {"G", "M", "X", "Y", "Z", "F", "S", "P"})
        if unsupported_letters:
            violations.append(
                SafetyIssue(
                    line_number,
                    original,
                    "Unsupported G-code word(s): " + ", ".join(unsupported_letters) + ".",
                )
            )

        g_codes = [_code_int(v) for v in words.get("G", ())]
        m_codes = [_code_int(v) for v in words.get("M", ())]
        for code in g_codes:
            if code is None or code not in allowed_g:
                violations.append(SafetyIssue(line_number, original, f"Unsupported G-code G{_display_code(code)}."))
        for code in m_codes:
            if code is None or code not in allowed_m:
                violations.append(SafetyIssue(line_number, original, f"Unsupported machine command M{_display_code(code)}."))

        if 20 in g_codes:
            unit_scale = 25.4
        if 21 in g_codes:
            unit_scale = 1.0
        if 90 in g_codes:
            absolute_mode = True
        if 91 in g_codes:
            absolute_mode = False
        if 0 in g_codes:
            motion_mode = 0
        if 1 in g_codes:
            motion_mode = 1

        for m_code in m_codes:
            if m_code in (3, 4):
                laser_on_lines += 1
                if not allow_laser:
                    violations.append(SafetyIssue(line_number, original, "Laser-on commands are forbidden in this operation."))
                power_values = words.get("S", ())
                if not power_values:
                    violations.append(SafetyIssue(line_number, original, "Laser-on command has no explicit S power value."))
                if not saw_explicit_m5:
                    violations.append(SafetyIssue(line_number, original, "Laser enable occurs before an explicit M5 safety command."))
                laser_on = True
            elif m_code == 5:
                laser_on = False
                saw_explicit_m5 = True

        if "S" in words:
            power = float(words["S"][-1])
            if power < -tol or power > float(envelope.max_power_s) + tol:
                violations.append(
                    SafetyIssue(
                        line_number,
                        original,
                        f"Laser power S{power:g} is outside 0…{int(envelope.max_power_s)}.",
                    )
                )

        if 4 in g_codes and "P" in words:
            dwell_s = float(words["P"][-1])
            if dwell_s < 0.0 or dwell_s > 10.0:
                violations.append(SafetyIssue(line_number, original, "Dwell G4 must remain between 0 and 10 seconds."))

        if "F" in words:
            feed = float(words["F"][-1]) * unit_scale
            if not math.isfinite(feed) or feed <= 0.0 or feed > float(envelope.max_feed_mm_min) + tol:
                violations.append(
                    SafetyIssue(
                        line_number,
                        original,
                        f"Feed {feed:g} mm/min is outside 0…{float(envelope.max_feed_mm_min):g}.",
                    )
                )

        has_xy = "X" in words or "Y" in words
        has_z = "Z" in words
        if has_xy or has_z:
            if not saw_explicit_m5:
                violations.append(SafetyIssue(line_number, original, "Movement occurs before an explicit M5 safety command."))
            if absolute_mode is None:
                violations.append(SafetyIssue(line_number, original, "Movement occurs before an explicit G90 or G91 mode."))
            if motion_mode not in (0, 1) and not any(code in (0, 1) for code in g_codes):
                violations.append(SafetyIssue(line_number, original, "Movement has no explicit or active G0/G1 mode."))

        if has_xy:
            motion_lines += 1
            active_motion = 0 if 0 in g_codes else (1 if 1 in g_codes else motion_mode)
            if active_motion == 0 and laser_on:
                violations.append(SafetyIssue(line_number, original, "Rapid G0 movement is forbidden while the laser is enabled."))
            if absolute_mode is True:
                next_x = float(words.get("X", (current_x,))[-1]) * unit_scale if "X" in words else current_x
                next_y = float(words.get("Y", (current_y,))[-1]) * unit_scale if "Y" in words else current_y
            elif absolute_mode is False:
                next_x = current_x + (float(words.get("X", (0.0,))[-1]) * unit_scale if "X" in words else 0.0)
                next_y = current_y + (float(words.get("Y", (0.0,))[-1]) * unit_scale if "Y" in words else 0.0)
            else:
                next_x, next_y = current_x, current_y
            if not _inside(next_x, envelope.min_x_mm, envelope.max_x_mm, tol):
                violations.append(
                    SafetyIssue(
                        line_number,
                        original,
                        f"X={next_x:.3f} mm is outside the permitted range {envelope.min_x_mm:.3f}…{envelope.max_x_mm:.3f} mm.",
                    )
                )
            if not _inside(next_y, envelope.min_y_mm, envelope.max_y_mm, tol):
                violations.append(
                    SafetyIssue(
                        line_number,
                        original,
                        f"Y={next_y:.3f} mm is outside the permitted range {envelope.min_y_mm:.3f}…{envelope.max_y_mm:.3f} mm.",
                    )
                )
            current_x, current_y = next_x, next_y
            xs.append(current_x)
            ys.append(current_y)

        if has_z:
            if laser_on:
                violations.append(SafetyIssue(line_number, original, "Z movement is forbidden while the laser is enabled."))
            z_value = float(words["Z"][-1]) * unit_scale
            if absolute_mode is True:
                violations.append(SafetyIssue(line_number, original, "Absolute Z movement is forbidden; LaserProg only permits bounded relative Z steps."))
            elif not allow_relative_z:
                violations.append(SafetyIssue(line_number, original, "Z movement is disabled for this operation."))
            else:
                relative_z += z_value
                sign = -1 if int(z_down_sign) < 0 else 1
                depth = relative_z * sign
                allowed_depth = max(0.0, float(max_relative_z_depth_mm))
                if depth < -tol:
                    violations.append(SafetyIssue(line_number, original, "Z movement rises above the recorded starting height."))
                if depth > allowed_depth + tol:
                    violations.append(
                        SafetyIssue(
                            line_number,
                            original,
                            f"Relative Z depth {depth:.3f} mm exceeds the permitted {allowed_depth:.3f} mm.",
                        )
                    )

    if laser_on:
        violations.append(SafetyIssue(0, "", "Program can finish with the laser enabled; a final M5 is required."))
    if abs(relative_z) > 1.0e-6:
        violations.append(SafetyIssue(0, "", f"Program does not retract Z to its starting offset ({relative_z:.3f} mm remains)."))
    if motion_lines == 0:
        warnings.append(SafetyIssue(0, "", "Program contains no XY movement."))

    return GCodeSafetyReport(
        tuple(violations),
        tuple(warnings),
        motion_lines,
        laser_on_lines,
        min(xs),
        min(ys),
        max(xs),
        max(ys),
    )


def _strip_comments(line: str) -> str:
    text = str(line).split(";", 1)[0]
    text = _PAREN_COMMENT_RE.sub("", text)
    return text.strip().upper()


def _words(line: str) -> dict[str, tuple[float, ...]]:
    out: dict[str, list[float]] = {}
    for letter, value in _WORD_RE.findall(line):
        try:
            out.setdefault(letter.upper(), []).append(float(value))
        except Exception:
            continue
    return {key: tuple(values) for key, values in out.items()}


def _code_int(value: float) -> int | None:
    rounded = int(round(float(value)))
    return rounded if abs(float(value) - rounded) <= 1.0e-6 else None


def _display_code(code: int | None) -> str:
    return "?" if code is None else str(code)


def _inside(value: float, lower: float, upper: float, tolerance: float) -> bool:
    return math.isfinite(value) and float(lower) - tolerance <= value <= float(upper) + tolerance


__all__ = [
    "GCodeSafetyReport",
    "MachineEnvelope",
    "SafetyIssue",
    "validate_gcode",
]
