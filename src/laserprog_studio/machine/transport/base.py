# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


class MachineTransportError(RuntimeError):
    """Raised when direct machine communication fails."""


@dataclass(frozen=True, slots=True)
class PortInfo:
    device: str
    description: str = ""
    hwid: str = ""

    @property
    def label(self) -> str:
        suffix = f" — {self.description}" if self.description else ""
        return f"{self.device}{suffix}"
