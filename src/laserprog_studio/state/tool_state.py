# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolState:
    active_tool: str = "none"
    preview_reason: str | None = None
