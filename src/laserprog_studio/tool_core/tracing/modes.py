"""Neutral drawing-mode contracts shared by tracing tools.

The module deliberately contains no Qt, renderer or document dependency.  It is
used by built-in tools and re-exported through :mod:`laserprog_studio.tool_api.tracing`.
"""
from __future__ import annotations

from enum import Enum
from typing import Iterable, Mapping


class TraceMode(str, Enum):
    MODIFY = "modify"
    POINT = "point"
    LINE = "line"
    POLYLINE = "polyline"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ARC = "arc"


_COMMON_ALIASES: dict[str, str] = {
    "mod": TraceMode.MODIFY.value,
    "edit": TraceMode.MODIFY.value,
    "modify": TraceMode.MODIFY.value,
    "point": TraceMode.POINT.value,
    "line": TraceMode.LINE.value,
    "trait": TraceMode.LINE.value,
    "polyline": TraceMode.POLYLINE.value,
    "poly_line": TraceMode.POLYLINE.value,
    "ligne_brisee": TraceMode.POLYLINE.value,
    "polyligne": TraceMode.POLYLINE.value,
    "rectangle": TraceMode.RECTANGLE.value,
    "rect": TraceMode.RECTANGLE.value,
    "box": TraceMode.RECTANGLE.value,
    "circle": TraceMode.CIRCLE.value,
    "cercle": TraceMode.CIRCLE.value,
    "arc": TraceMode.ARC.value,
    "arc_circle": TraceMode.ARC.value,
    "arc_de_cercle": TraceMode.ARC.value,
}


def normalize_trace_mode(
    value: str | TraceMode | None,
    *,
    default: str | TraceMode = TraceMode.MODIFY,
    allowed: Iterable[str | TraceMode] | None = None,
    extra_aliases: Mapping[str, str | TraceMode] | None = None,
) -> str:
    """Return one stable mode id from loose UI/user input.

    ``allowed`` lets a tool add specialised modes while still sharing the common
    aliases.  Unknown values always fall back to ``default`` instead of leaking
    inconsistent spelling into a state machine.
    """

    default_value = default.value if isinstance(default, TraceMode) else str(default)
    raw = value.value if isinstance(value, TraceMode) else str(value or default_value)
    cleaned = raw.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = dict(_COMMON_ALIASES)
    if extra_aliases:
        for key, target in extra_aliases.items():
            aliases[str(key).strip().lower().replace("-", "_").replace(" ", "_")] = (
                target.value if isinstance(target, TraceMode) else str(target)
            )
    normalized = aliases.get(cleaned, cleaned)
    if allowed is None:
        allowed_values = {mode.value for mode in TraceMode}
    else:
        allowed_values = {item.value if isinstance(item, TraceMode) else str(item) for item in allowed}
    return normalized if normalized in allowed_values else default_value


__all__ = ["TraceMode", "normalize_trace_mode"]
