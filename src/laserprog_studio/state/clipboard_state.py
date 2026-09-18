# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClipboardState:
    """Scene-independent application clipboard for copied meshes.

    It deliberately lives above individual scenes so Ctrl+C in one scene and
    Ctrl+V in another scene can duplicate parts without sharing mesh objects or
    identities. The controller remains responsible for deep-copying and assigning
    fresh mesh ids when pasting.
    """

    meshes: list[Any] = field(default_factory=list)
