# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
from uuid import uuid4

from ..domain import TextureAsset


class RecentTextureStore:
    """Small in-memory recent texture list used by the future texture tool.

    It deliberately stores paths, not image pixels. The GUI/tool can decide when
    to load thumbnails, and tests can exercise this class without Pillow/Qt.
    """

    def __init__(self, *, limit: int = 5, storage_path: str | Path | None = None) -> None:
        self.limit = max(1, int(limit))
        self.storage_path = Path(storage_path).expanduser() if storage_path is not None else None
        self._paths: deque[Path] = deque(maxlen=self.limit)
        self.load()

    def add(self, path: str | Path) -> TextureAsset:
        p = Path(path).expanduser()
        self._paths = deque([x for x in self._paths if x != p], maxlen=self.limit)
        self._paths.appendleft(p)
        self.save()
        return TextureAsset(id=f"tex_{uuid4().hex[:10]}", path=p)

    def recent_paths(self) -> tuple[Path, ...]:
        return tuple(self._paths)

    def clear(self) -> None:
        self._paths.clear()
        self.save()

    def load(self) -> None:
        if self.storage_path is None or not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
            paths = payload.get("recent_textures", []) if isinstance(payload, dict) else []
            self._paths = deque((Path(str(p)).expanduser() for p in paths[: self.limit]), maxlen=self.limit)
        except Exception:
            self._paths = deque(maxlen=self.limit)

    def save(self) -> None:
        if self.storage_path is None:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"recent_textures": [str(p) for p in self._paths]}
            self.storage_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            # Recent textures are convenience data; failing to persist them must
            # not interrupt modelling work.
            return
