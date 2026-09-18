# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import uuid

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


def make_project_id() -> str:
    return f"project_{uuid.uuid4().hex}"


def make_scene_id() -> str:
    return f"scene_{uuid.uuid4().hex}"


def make_history_entry_id() -> str:
    return f"history_{uuid.uuid4().hex}"


def make_snapshot_id() -> str:
    return f"snapshot_{uuid.uuid4().hex}"


def safe_slug(value: str, *, fallback: str = "item") -> str:
    raw = str(value or "").strip().replace(" ", "_")
    slug = _SAFE_NAME_RE.sub("_", raw).strip("._-")
    return slug or fallback
