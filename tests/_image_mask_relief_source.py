# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def read_image_mask_relief_source(root: Path) -> str:
    """Return the Image Mask Relief source after its pipeline split."""
    base = root / "src" / "laserprog_studio" / "geometry_ops"
    files = [base / "image_mask_relief.py", *sorted(base.glob("image_mask_relief_*.py"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)
